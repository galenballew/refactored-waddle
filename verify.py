"""Proof that the three things that matter actually work.

    python verify.py [url]

1. every box is a live Chromium process with its own OS window
2. a broadcast URL lands in every box
3. clicking a row puts that window in the foreground, and it stays there
"""

import sys
import time
from pathlib import Path

import winfocus
from boxes import BoxManager, load_config, normalize_url

FOCUS_BUDGET_S = 5.0
HOLD_S = 1.0

FIXTURE = Path(__file__).with_name("_verify_page.html")
FIXTURE_HTML = "<!doctype html><title>multibox verify</title><h1>multibox verify</h1>"


def default_url():
    """A local page, so this check does not depend on the network."""
    FIXTURE.write_text(FIXTURE_HTML, encoding="utf-8")
    return FIXTURE.as_uri()


def check_processes(manager):
    print("\n[1] live Chromium processes with windows")
    live = winfocus.chrome_pids()
    ok = True
    seen_hwnds = set()
    for box in manager.boxes:
        running = box.pids & live
        hwnd = box.hwnd or winfocus.top_level_window(box.pids)
        box.hwnd = hwnd
        good = bool(running) and hwnd is not None and hwnd not in seen_hwnds
        seen_hwnds.add(hwnd)
        print(f"    {box.name:<8} pids={len(running):<3} hwnd={hwnd}  {'ok' if good else 'FAIL'}")
        ok = ok and good
    print(f"    -> {len(manager.boxes)} boxes, {len(seen_hwnds)} distinct windows")
    return ok


def check_broadcast(manager, url):
    print(f"\n[2] broadcast {url}")
    expected = normalize_url(url)
    failed = manager.navigate_all(expected)
    for name, error in failed:
        print(f"    {name:<8} navigate error: {error}")

    deadline = time.time() + 15
    while time.time() < deadline:
        if all(box.url == expected for box in manager.boxes):
            break
        time.sleep(0.2)

    ok = True
    for box in manager.boxes:
        landed = box.url == expected
        print(f"    {box.name:<8} {box.url}  {'ok' if landed else 'FAIL'}")
        ok = ok and landed
    return ok


def check_focus(manager):
    print(f"\n[3] focus each window, budget {FOCUS_BUDGET_S}s, hold {HOLD_S}s")
    ok = True
    for box in manager.boxes:
        start = time.time()
        manager.focus(box)
        got = False
        while time.time() - start < FOCUS_BUDGET_S:
            if winfocus.foreground_window() == box.hwnd:
                got = True
                break
            time.sleep(0.05)
        elapsed = time.time() - start

        held = False
        if got:
            time.sleep(HOLD_S)
            held = winfocus.foreground_window() == box.hwnd

        verdict = "ok" if got and held else ("LOST FOCUS" if got else "FAIL")
        print(f"    {box.name:<8} {elapsed:5.2f}s  {verdict}")
        ok = ok and got and held
    return ok


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else default_url()
    manager = BoxManager(load_config())
    print(f"launching {len(manager.config['boxes'])} boxes...")
    manager.start()
    try:
        results = [
            ("processes", check_processes(manager)),
            ("broadcast", check_broadcast(manager, url)),
            ("focus", check_focus(manager)),
        ]
    finally:
        manager.close()
        FIXTURE.unlink(missing_ok=True)

    print("\nsummary")
    for name, passed in results:
        print(f"    {name:<10} {'PASS' if passed else 'FAIL'}")
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    sys.exit(main())
