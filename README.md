
# Multiboxing for Agents

Runs several real Chromium windows at once and gives you one small always-on-top
panel to control them. Click a row to jump to that window, or type a URL and send
every window to it at the same time.

## What you need

- Python 3.10 or newer (this repo was tested on 3.12)
- Playwright, plus its Chromium build

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install playwright
.venv\Scripts\python.exe -m playwright install chromium
```

Windows only. The focus behaviour uses Windows APIs directly.

## How to run it

```bash
.venv\Scripts\python.exe main.py
```

Five Chromium windows open in a cascade, and a small control panel appears on top
of everything. The panel has:

- **One row per window**, showing its name and the page it is currently on. Click
  a row and that Chromium window comes to the front. That is the only per-window
  action.
- **A URL box and "Send to all"** — type a URL, press the button (or hit Enter),
  and every window navigates there. `example.com` works; you do not need to type
  `https://`.
- **"Reload all"** — reloads every window.

Navigate and reload are the only things that get broadcast. Clicks, typing, and
mouse positions are never sent to the windows.

## Changing the number of windows or their names

Edit `config.json`:

```json
{
  "boxes": ["box1", "box2", "box3", "box4", "box5"],
  "start_url": "about:blank",
  "window_size": [900, 700]
}
```

- `boxes` — the window names, in order. **The length of this list is the number of
  windows.** Add or remove entries to get more or fewer.
- `start_url` — the page every window opens on.
- `window_size` — `[width, height]` in pixels for each window.

Restart the app after editing.

## How to quit

Close the control panel (the X, as normal). It shuts down every Chromium window
on the way out. Closing the Chromium windows by hand instead will leave the panel
running with dead rows, so use the panel.

## Checking that it works

```bash
.venv\Scripts\python.exe verify.py
```

This launches the windows and checks three things: that each box is a live
Chromium process with its own window, that a broadcast URL lands in all of them,
and that focusing a window puts it in the foreground within 5 seconds and keeps
it there. It prints PASS or FAIL for each, then closes everything. Pass a URL as
an argument to broadcast that instead of the built-in local test page.

## What this is not

Deliberately left out. These are not missing features, they are decisions:

- No AI or model calls anywhere in the codebase.
- No agent loop, task runner, or harness integration.
- No dashboard, charts, progress bars, or live logs.
- No scoring, ranking, prioritising, or automatic task swapping.
- No messaging between windows and no shared work queue.
- No login handling, credential storage, containers, or remote execution.

Also worth knowing: profiles are temporary and thrown away when the app closes.
The windows are separate browser launches, which keeps their cookies and storage
apart in practice, but nothing here is built or tested as a security boundary.
Do not rely on it as one.
