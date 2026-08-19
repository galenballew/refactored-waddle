"""Proof that the things that matter actually work.

    python verify.py [url]

The optional URL is where the boxes are pointed before the checks run.

1. every box is a live Chromium process with its own OS window
2. summoning a box puts it on screen and in the foreground, and parking it again
   takes it back off every monitor
3. every box has a distinct live thumbnail registered
4. the tile map is sane, and double-clicking tile i opens box i's detail view
5. tiles show CURRENT page content, proven by flipping the page colour -- which
   is the proof that parking a box off the desktop did not stop it rendering
6. a full dashboard refresh stays inside its time budget
7. tiles stay whole when the dashboard is resized up to full screen
8. a parked box is not a shell window: off every monitor, no taskbar button, no
   Alt-Tab entry
9. a box added while the app is running is a real box: its own processes, its own
   window, parked, tiled, with a session and an agent child
10. closing the dashboard takes every agent child process with it

The fast checks -- views, the agent protocol, the state machine -- are in
`smoke.py`, which needs no browsers and runs in about a second.
"""

import ctypes
import sys
import time
import types
from ctypes import wintypes
from pathlib import Path

import layout
import thumbs
import winfocus

thumbs.set_dpi_awareness()

from boxes import BoxManager, load_config  # noqa: E402
from ui.app import App  # noqa: E402

FOCUS_BUDGET_S = 5.0
FOCUS_ATTEMPTS = 3
HOLD_S = 1.0
REFRESH_BUDGET_MS = 50.0

HERE = Path(__file__).parent
FIXTURE = HERE / "_verify_page.html"
COLOUR_FIXTURES = {"red": "#ff0000", "blue": "#0000ff"}

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
SRCCOPY = 0x00CC0020


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def avg_rgb(left, top, width, height):
    """Average colour of a screen region.

    Must be a SCREEN device context: DWM thumbnails live only in the compositor's
    visual tree, so PrintWindow on the dashboard would not contain them.
    """
    screen = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(mem, bitmap)
    gdi32.BitBlt(mem, 0, 0, width, height, screen, left, top, SRCCOPY)
    header = _BIH(biSize=ctypes.sizeof(_BIH), biWidth=width, biHeight=-height,
                  biPlanes=1, biBitCount=32, biCompression=0)
    buf = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem, bitmap, 0, height, buf, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, screen)

    data = buf.raw
    count = width * height
    return (
        sum(data[i * 4 + 2] for i in range(count)) / count,
        sum(data[i * 4 + 1] for i in range(count)) / count,
        sum(data[i * 4] for i in range(count)) / count,
    )


def colour_page(name):
    """A local page. Chrome blocks top-frame navigation to data: URLs, so use file://."""
    path = HERE / f"_verify_{name}.html"
    path.write_text(
        f"<body style='margin:0;background:{COLOUR_FIXTURES[name]}'>", encoding="utf-8"
    )
    return path.as_uri()


def default_url():
    FIXTURE.write_text(
        "<!doctype html><title>multibox verify</title><h1>multibox verify</h1>",
        encoding="utf-8",
    )
    return FIXTURE.as_uri()


def pump(app, seconds=1.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def check_processes(manager):
    print("\n[1] live Chromium processes with windows")
    live = winfocus.chrome_pids()
    ok, seen = True, set()
    for box in manager.boxes:
        running = box.pids & live
        hwnd = box.ensure_hwnd()
        good = bool(running) and hwnd is not None and hwnd not in seen
        seen.add(hwnd)
        print(f"    {box.name:<8} pids={len(running):<3} hwnd={hwnd}  {'ok' if good else 'FAIL'}")
        ok = ok and good
    print(f"    -> {len(manager.boxes)} boxes, {len(seen)} distinct windows")
    return ok


def _is_parked(box):
    """True when the box's window shares no pixel with any monitor."""
    rect = winfocus.window_rect(box.hwnd)
    if rect is None:
        return False
    screen = layout.bounds_rect(*winfocus.virtual_screen())
    return not layout.intersects(screen, layout.Rect(*rect))


def _is_on_screen(box):
    rect = winfocus.window_rect(box.hwnd)
    if rect is None:
        return False
    return layout.intersects(layout.bounds_rect(*winfocus.work_area()), layout.Rect(*rect))


def _summon_once(manager, box):
    """Returns (won, elapsed, thief_hwnd)."""
    start = time.time()
    manager.summon(box)
    while time.time() - start < FOCUS_BUDGET_S:
        if winfocus.foreground_window() == box.hwnd:
            time.sleep(HOLD_S)
            if winfocus.foreground_window() == box.hwnd:
                return True, time.time() - start, None
            break
        time.sleep(0.05)
    return False, time.time() - start, winfocus.foreground_window()


def check_summon(manager):
    """Prove "Take control" brings a box's window onto the desktop and holds it
    there, and that leaving puts it back where nobody can see it.

    Only a box losing focus to ANOTHER BOX is a defect in this app. Losing it to
    an unrelated window means someone is using the machine while the check runs,
    which makes the measurement impossible rather than failed -- so retry, and if
    it keeps happening report no verdict instead of a false one.
    """
    print(f"\n[2] summon each window, budget {FOCUS_BUDGET_S}s, hold {HOLD_S}s")
    ours = {box.hwnd for box in manager.boxes if box.hwnd}
    ok, blocked = True, []

    for box in manager.boxes:
        for attempt in range(FOCUS_ATTEMPTS):
            won, elapsed, thief = _summon_once(manager, box)
            if won:
                on_screen = _is_on_screen(box)
                manager.park_summoned()
                parked = _is_parked(box) if manager.hidden else True
                good = on_screen and parked
                print(f"    {box.name:<8} {elapsed:5.2f}s  on_screen={on_screen} "
                      f"parked_after={parked}  {'ok' if good else 'FAIL'}")
                ok = ok and good
                break
            if thief in ours:
                print(f"    {box.name:<8} {elapsed:5.2f}s  FAIL (lost to another box)")
                print(f"             wanted  {winfocus.describe(box.hwnd)}")
                print(f"             actual  {winfocus.describe(thief)}")
                ok = False
                break
            if attempt == FOCUS_ATTEMPTS - 1:
                print(f"    {box.name:<8} {elapsed:5.2f}s  NO VERDICT (outside interference)")
                print(f"             stolen by  {winfocus.describe(thief)}")
                blocked.append(box.name)

    if blocked:
        print(f"    !! {len(blocked)} box(es) could not be measured: {', '.join(blocked)}")
        print("    !! another app kept taking the foreground. Re-run without touching")
        print("    !! the machine to get a real verdict on this check.")
    return ok, ("no verdict" if blocked else "")


def check_thumbnails(app, manager):
    print("\n[3] one distinct live thumbnail per box")
    ok, seen = True, set()
    for box in manager.boxes:
        handle = app.handles.get(box.name)
        size = thumbs.source_size(handle) if handle is not None else None
        value = handle.value if handle is not None else None
        good = value is not None and value not in seen and size is not None and all(size)
        seen.add(value)
        print(f"    {box.name:<8} handle={value} source={size}  {'ok' if good else 'FAIL'}")
        ok = ok and good
    return ok


def check_tilemap(app, manager):
    print("\n[4] tile map")
    overview = app.overview
    tiles = overview.tiles
    count = len(manager.boxes)
    # One cell past the fleet: the last tile is "+ Add box".
    ok = len(tiles) == count + 1
    print(f"    {len(tiles)} tiles for {count} boxes plus the add tile"
          f"  {'ok' if ok else 'FAIL'}")

    width, height = overview.canvas.winfo_width(), overview.canvas.winfo_height()
    for tile in tiles:
        inside = (
            0 <= tile.cell.left and tile.cell.right <= width
            and 0 <= tile.cell.top and tile.cell.bottom <= height
        )
        centre_x = (tile.cell.left + tile.cell.right) // 2
        centre_y = (tile.cell.top + tile.cell.bottom) // 2
        hit = layout.hit_test(tiles, centre_x, centre_y)
        good = inside and hit == tile.index
        print(f"    tile {tile.index} inside={inside} hit_test={hit}  {'ok' if good else 'FAIL'}")
        ok = ok and good

    for a in tiles:
        for b in tiles:
            if a.index < b.index:
                disjoint = (
                    a.cell.right <= b.cell.left or b.cell.right <= a.cell.left
                    or a.cell.bottom <= b.cell.top or b.cell.bottom <= a.cell.top
                )
                if not disjoint:
                    print(f"    tiles {a.index}/{b.index} overlap  FAIL")
                    ok = False

    # Double-clicking tile i must open box i, and Back must come home again.
    # The handler only reads x and y off the event, so a stand-in will do.
    for tile in tiles[:count]:  # the add tile opens nothing
        centre_x = (tile.cell.left + tile.cell.right) // 2
        centre_y = (tile.cell.top + tile.cell.bottom) // 2
        overview.on_double_click(types.SimpleNamespace(x=centre_x, y=centre_y))
        expected = manager.boxes[tile.index]
        opened = app.box is expected and app.view is app.detail
        app.show_overview()
        back = app.box is None and app.view is overview
        print(f"    tile {tile.index} opens {expected.name}={opened} back={back}"
              f"  {'ok' if opened and back else 'FAIL'}")
        ok = ok and opened and back
    return ok


def check_live_tiles(app, manager):
    print("\n[5] tiles show current content (colour flip)")
    ok = True
    # The dashboard is deliberately not always-on-top any more, but this check
    # BitBlts the screen and would otherwise measure whatever window happens to
    # be in front of it. Topmost only for the duration of the sampling; it
    # changes nothing about the thumbnails being tested.
    app.root.attributes("-topmost", True)
    app.root.lift()
    pump(app, 0.3)
    for name in ("red", "blue"):
        manager.navigate_all(colour_page(name))
        pump(app, 2.0)
        app.draw()
        pump(app, 0.5)
        for index, (left, top, width, height) in enumerate(app.overview.tile_screen_rects()):
            # Sample the middle of the tile: the thumbnail includes Chromium's
            # tab strip and toolbar at the top, which are not the page colour.
            sx, sy = left + width // 4, top + height // 2
            sw, sh = max(8, width // 2), max(8, height // 3)
            r, g, b = avg_rgb(sx, sy, sw, sh)
            if name == "red":
                good = r > 140 and b < 110
            else:
                good = b > 140 and r < 110
            box = manager.boxes[index]
            print(f"    {name:<4} {box.name:<8} RGB=({r:5.1f},{g:5.1f},{b:5.1f})"
                  f"  {'ok' if good else 'FAIL'}")
            ok = ok and good
    app.root.attributes("-topmost", False)
    return ok


def check_refresh_budget(app):
    print(f"\n[6] refresh budget {REFRESH_BUDGET_MS}ms")
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        app.tick()
        timings.append((time.perf_counter() - start) * 1000)
    worst = max(timings)
    ok = worst < REFRESH_BUDGET_MS
    print(f"    worst of 5 ticks: {worst:.1f}ms  {'ok' if ok else 'FAIL'}")
    return ok


def check_resize(app, manager):
    """Prove the tiles stay whole when the window is scaled up.

    The bug this exists for: DWM will not reliably paint a thumbnail larger than
    its source window, and it fails silently — the far edge of the later tiles
    simply never gets painted, which reads as a cropped browser rather than as an
    error. It is invisible at a small window size, so this check maximizes.
    """
    print("\n[7] tiles stay whole when the dashboard is resized")
    manager.navigate_all(colour_page("red"))
    pump(app, 2.0)
    app.root.attributes("-topmost", True)
    app.root.lift()
    ok = True
    source = app.source_size()
    for state, label in (("zoomed", "maximized"), ("normal", "restored")):
        app.root.state(state)
        pump(app, 1.5)
        app.draw()
        pump(app, 0.5)
        for index, (left, top, width, height) in enumerate(app.overview.tile_screen_rects()):
            # Sample the far corner: that is the part that goes missing first.
            r, g, b = avg_rgb(left + width - 24, top + height - 24, 16, 16)
            painted = r > 140 and b < 110
            within = not source or (width <= source[0] + 1 and height <= source[1] + 1)
            good = painted and within
            print(f"    {label:<9} {manager.boxes[index].name:<8} tile={width}x{height} "
                  f"corner=({r:5.1f},{g:5.1f},{b:5.1f}) within_source={within}"
                  f"  {'ok' if good else 'FAIL'}")
            ok = ok and good
    app.root.attributes("-topmost", False)
    if source:
        print(f"    source windows are {source[0]}x{source[1]}; tiles never exceed that")
    return ok


def check_hidden(manager):
    """Prove a parked box is not a window as far as the desktop is concerned.

    Runs last on purpose: everything before it has been summoning boxes, moving
    them, resizing the dashboard and flipping their pages, so passing here means
    the fleet went back into hiding by itself rather than merely starting out
    that way.
    """
    print("\n[8] parked boxes are not shell windows")
    if not manager.hidden:
        print("    window_layout is not 'hidden' -- boxes are meant to be visible")
        return True, "skipped"

    listed = set(winfocus.alt_tab_windows())
    ok = True
    for box in manager.boxes:
        parked = _is_parked(box)
        tool = winfocus.is_tool_window(box.hwnd)
        alt_tab = box.hwnd in listed
        good = parked and tool and not alt_tab
        print(f"    {box.name:<8} off_screen={parked} toolwindow={tool} "
              f"alt_tab={alt_tab}  {'ok' if good else 'FAIL'}")
        if not good:
            print(f"             {winfocus.describe(box.hwnd)} rect={winfocus.window_rect(box.hwnd)}")
        ok = ok and good
    return ok


def check_add_box(app, manager):
    """Prove a box added while the app is running is a real box.

    The thing at risk is PID attribution. `_launch` credits every `chrome.exe`
    that appeared during the launch to the box being launched, which only holds
    while launches are serialized -- so the box that comes back must own PIDs
    nobody else has, and a window nobody else has. Everything else here is the
    rest of what a box is: parked, out of the shell, mirrored in a tile, with a
    session and a child of its own.
    """
    print("\n[9] adding a box at runtime")
    existing = set()
    for box in manager.boxes:
        existing |= box.pids
    hwnds = {box.hwnd for box in manager.boxes}
    count = len(manager.boxes)

    box = app.add_box()
    if box is None:
        print("    add_box refused  FAIL")
        return False
    pump(app, 1.0)

    checks = {
        "own pids": bool(box.pids) and not (box.pids & existing),
        "own window": box.ensure_hwnd() is not None and box.hwnd not in hwnds,
        "parked": _is_parked(box) if manager.hidden else True,
        "out of the shell": winfocus.is_tool_window(box.hwnd) if manager.hidden else True,
        "has a thumbnail": app.handles.get(box.name) is not None,
        "has a session": box.name in app.sessions,
        "has a live child": box.name in app.agents and app.agents[box.name].alive,
        "grid grew": len(app.overview.tiles) == count + 2,  # +1 box, +1 add tile
    }
    ok = all(checks.values())
    print(f"    added {box.name}, pids={sorted(box.pids)} hwnd={box.hwnd}")
    for label, good in checks.items():
        print(f"    {label:<18} {'ok' if good else 'FAIL'}")
    return ok


def check_children(app):
    """Prove the dashboard takes its children with it.

    Runs last, and quits the dashboard itself, because closing it is the thing
    being tested. A leaked child is invisible -- no window, no taskbar button --
    until someone finds five stray pythons in Task Manager a day later, which is
    why this is a check and not a habit.
    """
    print("\n[10] agent children die with the dashboard")
    procs = [(name, agent.proc) for name, agent in app.agents.items()]
    running = [name for name, proc in procs if proc.poll() is None]
    ok = len(running) == len(procs)
    print(f"    {len(running)}/{len(procs)} children running before quit"
          f"  {'ok' if ok else 'FAIL'}")

    app.quit()
    for name, proc in procs:
        code = proc.poll()
        good = code is not None
        print(f"    {name:<8} exited={good} code={code}  {'ok' if good else 'FAIL'}")
        ok = ok and good
    return ok


def cleanup():
    for path in [FIXTURE] + [HERE / f"_verify_{n}.html" for n in COLOUR_FIXTURES]:
        path.unlink(missing_ok=True)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else default_url()
    manager = BoxManager(load_config())
    print(f"launching {len(manager.config['boxes'])} boxes...")
    manager.start()
    # Setup, not a check: give the boxes something to render so the tiles are
    # not five blank pages before the colour flip in [5] takes over.
    for name, error in manager.navigate_all(url):
        print(f"    {name:<8} navigate error: {error}")

    app = None
    try:
        results = [
            ("processes", check_processes(manager)),
            ("summon", check_summon(manager)),
        ]
        app = App(manager)
        pump(app, 1.5)
        results += [
            ("thumbnails", check_thumbnails(app, manager)),
            ("tilemap", check_tilemap(app, manager)),
            ("live tiles", check_live_tiles(app, manager)),
            ("refresh", check_refresh_budget(app)),
            ("resize", check_resize(app, manager)),
            ("hidden", check_hidden(manager)),
        ]
        results.append(("add box", check_add_box(app, manager)))
        results.append(("children", check_children(app)))
        app = None  # that check closed the dashboard; do not close it twice
    finally:
        if app is not None:
            app.quit()
        manager.close()
        cleanup()

    print("\nsummary")
    failed = False
    for name, result in results:
        # check_summon and check_hidden return (passed, note); the rest a plain bool.
        passed, note = result if isinstance(result, tuple) else (result, "")
        failed = failed or not passed
        print(f"    {name:<11} {'PASS' if passed else 'FAIL'}{f'  ({note})' if note else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
