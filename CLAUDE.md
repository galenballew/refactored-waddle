# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A bare-minimum multibox window manager for browser sandboxes: run N headed Chromium
windows at once, jump to any one of them fast, and drive all of them from a single
input. Python + Playwright (sync API) + Tkinter. Windows only.

## Commands

```bash
.venv\Scripts\python.exe main.py       # run the app
.venv\Scripts\python.exe verify.py     # the three proof checks; exits non-zero on failure
```

`verify.py [url]` is the whole test suite — there is no pytest. It launches real
windows, so it is slow (~20s) and needs a desktop session; it will steal focus while
the focus check runs.

Setup: `python -m venv .venv`, then `pip install playwright` and
`playwright install chromium` inside it. The system `python` on this machine is 3.9
and will not work — use the venv (3.12).

## Layout

```
config.json   box names + start URL + window size
main.py       entry point: launch boxes, then run the control window
boxes.py      only file that touches Playwright — one browser+page per box
control.py    only file that touches Tkinter — row list, URL field, broadcast buttons
winfocus.py   ctypes/user32: match windows to PIDs, force foreground
verify.py     the three proof checks
```

## Architectural constraints

- **One Playwright `launch()` per box.** Each box needs its own real OS window, so no
  shared page or context objects, and no multiple pages in one browser.
- **Single-threaded.** Playwright's sync API and Tkinter's `mainloop` both want to own
  the calling thread. Playwright calls from Tkinter callbacks work fine and are tested;
  do not add threads.
- **Broadcast is navigate and reload only.** Never broadcast clicks, keystrokes, or
  screen coordinates.
- **Window handles come from PID diffing.** Playwright exposes no OS window handle, so
  `BoxManager.start` snapshots `chrome.exe` PIDs around each launch and attributes the
  new ones to that box; `winfocus.top_level_window` then finds the matching HWND. If
  you change how boxes are launched, this attribution is the thing most likely to break.
- **Focus** is `SetForegroundWindow` with an `AttachThreadInput` fallback, because
  Windows only lets the current foreground process hand off focus.
- **Ephemeral profiles.** No persistent user-data-dir, no isolation guarantees, no
  cross-box checks. Do not describe this as a security boundary.
- **Config drives box count and names.** `len(config["boxes"])` is the window count;
  nothing hardcodes 5.

## What this is not — do not add

Deliberately out of scope. Do not add these even if they seem useful:

- Any AI or model call anywhere in the codebase.
- Any agent loop, task runner, or harness integration.
- A dashboard, charts, progress bars, or live logs.
- Any scoring, ranking, prioritizing, or automatic task swapping.
- Cross-box messaging or a shared work queue.
- Login handling, credential storage, containers, or remote execution.

## README rule

`README.md` must be updated in the same change as any behavior change. If a flag, config
key, or run command changes and the README still describes the old one, the change is
incomplete.
