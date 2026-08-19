# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A multibox window manager for browser sandboxes: run N headed Chromium windows at
once, see them all as live tiles in one dashboard, jump to any one of them fast,
and drive all of them from a single input. Python + Playwright (sync API) +
Tkinter + ctypes. Windows only.

The dashboard is the **only window the user ever sees**. The boxes are *parked* —
positioned clear of every monitor and dropped from the taskbar and Alt-Tab — and a
box is *summoned* onto the desktop only while it holds the keyboard. The model to
have in mind is a hypervisor console: N guests running somewhere you cannot see,
and one window showing a live view of each. Parked is not hidden, and that
distinction is load-bearing: a hidden, minimized or cloaked window is not
composited, and its tile goes blank. This is about desktop citizenship, not
isolation — see the ephemeral-profiles note below.

## Commands

```bash
.venv\Scripts\python.exe main.py       # run the app
.venv\Scripts\python.exe verify.py     # the nine proof checks; exits non-zero on failure
```

`verify.py [url]` is the whole test suite — there is no pytest. It launches real
windows and reads pixels off the screen, so it is slow (~60s), needs a desktop
session, steals focus, and covers part of the screen while it runs.

Setup: `python -m venv .venv`, then `pip install playwright` and
`playwright install chromium` inside it. The system `python` on this machine is 3.9
and will not work — use the venv (3.12).

## Layout

```
config.json   box names, start URL, window layout, dashboard size
main.py       entry point: DPI awareness, launch boxes, run the dashboard
boxes.py      only file that touches Playwright — one browser+page per box
control.py    only file that touches Tkinter — the tile grid, and the two
              triggers that send a summoned box back to its slot
thumbs.py     ctypes/dwmapi: live window thumbnails
winfocus.py   ctypes/user32: match windows to PIDs, force foreground, move
              windows, and drop them from the taskbar and Alt-Tab
layout.py     pure geometry — grid rects, hit testing, park/summon/cascade rects.
              No Tk, no Win32. `columns="auto"` picks the count that maximises tile
              area; in a tall narrow window that is usually 1, and 2 wastes two
              thirds of the panel.
verify.py     the nine proof checks
```

## Architectural constraints

- **One Playwright `launch()` per box.** Each box needs its own real OS window, so no
  shared page or context objects, and no multiple pages in one browser.
- **Single-threaded, and it stays that way.** Playwright's sync API and Tkinter's
  `mainloop` both want to own the calling thread. This survives a live dashboard only
  because DWM composites the tiles out-of-process — no capture work ever runs on the Tk
  thread. A full tick — re-assert the parked layout, then redraw — measures ~2.5ms.
  If you ever move tiles to `page.screenshot()`, that guarantee is gone and the
  concurrency problem comes back.
- **Broadcast is navigate and reload only.** Never broadcast clicks, keystrokes, or
  screen coordinates.
- **Window handles come from PID diffing.** Playwright exposes no OS window handle, so
  `BoxManager.start` snapshots `chrome.exe` PIDs around each launch and attributes the
  new ones to that box; `winfocus.top_level_window` then finds the matching HWND. If
  you change how boxes are launched, this attribution is the thing most likely to break.
  It is also inherently racy — Chromium spawns helpers asynchronously, so a late child
  of box *k* can be credited to box *k+1*. It holds today only because launches are
  serialized.
- **Focus is Win32, not Playwright.** `SetForegroundWindow` with an `AttachThreadInput`
  fallback. There is no `page.bring_to_front()` fallback any more: without an HWND we
  cannot move the window either, so activating it would only put the keyboard
  somewhere off-screen. `summon` returns False and the dashboard says so. (A late
  async activation was once blamed for an intermittent `LOST FOCUS` in verify; that
  turned out to be another app taking the foreground, not this.)
- **Exactly one box is summoned at a time, and the dashboard decides when.** Two
  triggers send it back, both in `control.py`: Tk's `<FocusIn>` for the user coming
  back to the dashboard, and a per-tick backstop for focus going to a third app,
  which Tk never hears about. The backstop asks whether the foreground window's
  **PID** is the box's, not whether its HWND is — Chromium puts `<select>` popups,
  the print dialog and download bubbles in their own top-level windows, and an HWND
  test would park the box out from under someone mid-click.
- **Parking is a position, not a visibility state.** `hide_from_shell` sets
  `WS_EX_TOOLWINDOW` on Chromium's HWND to drop the taskbar button and Alt-Tab entry,
  and `SetWindowPos` puts the window past `SM_CXVIRTUALSCREEN`. Both are edits to
  another process's window: allowed because we launched it at our own integrity
  level, but not a contract. `reassert_layout` re-applies them every tick, which is
  what makes a display change or a self-repositioning Chromium correct itself. The
  taskbar only re-reads the ex-style across a hide/show cycle, so `hide_from_shell`
  briefly hides the window — it must therefore run **before** thumbnails are
  registered.
- **Window placement uses `SetWindowPos`, not Chromium flags.** `--window-position` is
  in DIPs and would need DPI conversion; HWND coordinates are already physical pixels.
- **DPI awareness must be set before Tk is created** (`thumbs.set_dpi_awareness()` in
  `main.py`). With it on, Tk pixel units and DWM client coordinates are both physical
  pixels and no conversion is needed anywhere. Dev machine runs at 150%.
- **Ephemeral profiles.** No persistent user-data-dir, no isolation guarantees, no
  cross-box checks. Do not describe this as a security boundary.
- **Config drives box count and names.** `len(config["boxes"])` is the window count;
  nothing hardcodes 5.

## DWM thumbnail rules

Learned the hard way; all of these will silently produce a blank or wrong tile.

- The destination must be a **top-level** window. Tk's `winfo_id()` is a child and
  returns `E_INVALIDARG`; use `thumbs.dest_hwnd()`, which walks to `GA_ROOT`.
- `rcDestination` is in the destination window's **client** coordinates. Offset canvas
  coordinates by `thumbs.client_offset()`.
- Thumbnails always composite **above** the destination's own content. Anything drawn
  under a tile is invisible, so labels go outside the tile rect.
- A **minimized or virtual-desktop-cloaked** source renders nothing. Occluded is fine,
  and so is **entirely off-screen** — that is what makes parked boxes work at all.
  Verified: check [6] flips every page red then blue and reads the pixels back while
  all five boxes sit past the edge of the virtual screen. Chromium does not throttle
  them there, because Playwright's default args already include
  `--disable-backgrounding-occluded-windows` and `--disable-renderer-backgrounding`.
  If tiles ever do freeze, `--disable-features=CalculateNativeWinOcclusion` is the
  next lever.
- A thumbnail **larger than its source window** is not reliably painted. It fails
  silently and partially: the first tiles come out whole and the later ones are
  missing their right or bottom edge, which reads as a cropped browser rather than
  as an error. Total area is not the constraint — five 1200x930 tiles from
  1200x930 windows are fine — only the ratio to the source. `tile_rects` therefore
  takes `max_thumb` and never scales a tile past the source's own size. This is
  invisible in a small window and obvious maximized; check [8] exists for it.
- `fSourceClientAreaOnly` does **not** strip browser chrome; Chromium's toolbar is
  client area. Cropping to page pixels only would need `rcSource`.
- Unregister every handle on exit.

## Verification notes

- Proving a tile is live needs a **screen** DC BitBlt. `PrintWindow` on the dashboard
  will not contain thumbnails — they exist only in the compositor's visual tree.
- Chrome blocks top-frame navigation to `data:` URLs. Test pages must be `file://`.
- `verify.py` samples the middle of each tile, because the top of the tile is
  Chromium's tab strip and toolbar, not page content.
- The summon check cannot be measured while someone is using the machine — alt-tab
  and any other app taking the foreground will beat it. It retries, then reports
  `NO VERDICT` and names the interfering window instead of failing. Losing focus to
  *another box* is still a real failure. Do not "fix" a flaky focus result before
  reading which window actually took the foreground; it is usually a browser or
  Task View, not this code.
- The app is no longer always-on-top, so check [6] makes the dashboard topmost for
  the duration of its sampling and drops it again afterwards. Without that it
  BitBlts whatever window happens to be in front and reads plausible-looking garbage
  — muddy mixed RGB rather than the flat 255/0/0 a real tile gives. Do not read that
  failure as a broken thumbnail.
- Check [9] runs last on purpose: everything before it summons boxes, moves them
  around and resizes the window, so passing means the fleet went back into hiding
  by itself rather than merely starting out that way.

## What this is not — do not add

Deliberately out of scope. Do not add these even if they seem useful:

- Any AI or model call anywhere in the codebase.
- Any agent loop, task runner, or harness integration.
- Charts, progress bars, metrics, or log panes. The tile grid is the whole UI.
- Any scoring, ranking, prioritizing, or automatic task swapping.
- Cross-box messaging or a shared work queue.
- Login handling, credential storage, containers, or remote execution.

The AI/agent items are deferred, not permanent — attaching a computer-use agent
runtime per box is the intended direction. Two things to protect for that: DWM never
returns pixels to Python, so agent perception needs a separate `page.screenshot()`
path; and the eventual shape is one subprocess per box, so never let the dashboard
reach through `box.page` directly.

## README rule

`README.md` must be updated in the same change as any behavior change. If a flag, config
key, or run command changes and the README still describes the old one, the change is
incomplete.
