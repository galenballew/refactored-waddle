
# Multiboxing for Agents

Runs several real Chromium windows at once and shows them all as live tiles in a
single dashboard — the only window you ever see. The browser windows themselves
are parked off the desktop: no taskbar buttons, no Alt-Tab entries, nowhere on
screen. Click a tile to bring that one out for as long as you are using it, or
type a URL and send every window to it at the same time.

## What you need

- Python 3.9 or newer. Only 3.12 has actually been run; nothing in the code
  needs anything newer than 3.8, but the other versions are untested.
- Playwright, plus its Chromium build

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install playwright
.venv\Scripts\python.exe -m playwright install chromium
```

Windows only. The live tiles and the window focusing both use Windows APIs
directly.

## How to run it

```bash
.venv\Scripts\python.exe main.py
```

Five Chromium windows open — one per name in `config.json` — and go straight to
their parking slots off the edge of the screen. What you see is one ordinary
window, the dashboard, which you can move and resize like anything else. It
shows:

- **A grid of live tiles**, one per window. Each tile is a real, continuously
  updating view of that browser — not a screenshot taken once at startup. The
  window name and current page are printed under each tile. Tiles show the whole
  browser window, so you will see its tab strip and address bar above the page
  itself.
- **Click a tile** and that window is *summoned*: it appears in the middle of the
  screen and takes the keyboard, so you can use it normally. Click back on the
  dashboard, or switch to any other app, and it goes back to its slot — its tile
  keeps updating the whole time. Only one window is ever out at once, so the
  desktop never fills up with browsers. That is the only per-window action.
- **A URL box and "Send to all"** — type a URL, press the button (or hit Enter),
  and every window navigates there. `example.com` works; you do not need to type
  `https://`.
- **"Reload all"** — reloads every window.

Navigate and reload are the only things that get broadcast. Clicks, typing, and
mouse positions are never sent to the windows.

The browser windows are deliberately not on your desktop. You do not need to see
them directly — that is what the tiles are for. They are still running normally
while parked: a tile shows live page content whether its window is off-screen,
covered by other windows, or in front of you.

## Changing the number of windows or their names

Edit `config.json`:

```json
{
  "boxes": ["box1", "box2", "box3", "box4", "box5"],
  "start_url": "about:blank",
  "window_size": [900, 700],
  "window_layout": "hidden",
  "dashboard": {
    "size": [900, 1000],
    "columns": "auto",
    "gap": 10,
    "refresh_ms": 1000
  }
}
```

- `boxes` — the window names, in order. **The length of this list is the number of
  windows.** Add or remove entries to get more or fewer.
- `start_url` — the page every window opens on.
- `window_size` — `[width, height]` for each browser window, both while parked and
  when summoned onto the screen. This is also the largest a tile will ever be
  drawn: a tile is never scaled past its window's real size, because Windows will
  not reliably paint a live thumbnail bigger than its source. So if you make the
  dashboard very large and the tiles stop growing, raise `window_size`.
- `window_layout` — `hidden` (default) parks the windows off the desktop and out
  of the taskbar and Alt-Tab. Any other value puts them back on the desktop as
  ordinary staggered windows, which is there for when you need to look at what a
  browser is actually doing.
- `dashboard.size` — `[width, height]` for the dashboard window, which opens
  centred on the screen. Move or resize it afterwards and the tiles re-flow.
- `dashboard.columns` — how many tiles per row. `"auto"` (the default) picks
  whichever count makes the tiles biggest, which is usually what you want; set
  a number to override it.
- `dashboard.gap` — pixels between tiles.
- `dashboard.refresh_ms` — how often the dashboard rewrites the tile captions and
  re-checks where the browser windows are. The tile images themselves are always
  live and are not affected by this.

Restart the app after editing.

## How to quit

Close the dashboard (the X, as normal). It shuts down every Chromium window on
the way out. Closing a summoned window by hand instead leaves the dashboard
running with a tile that reads "no window", so use the dashboard.

Quitting through the dashboard matters more than it used to. The browser windows
have no taskbar button and no Alt-Tab entry, so if the dashboard is force-killed
— Task Manager, a crash — any window that outlives it is running somewhere you
cannot click on. To clear those out without touching your normal Chrome:

```bash
powershell -c "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force"
```

## Checking that it works

```bash
.venv\Scripts\python.exe verify.py
```

This launches the windows, builds the dashboard, and runs nine checks: each box
is a live Chromium process with its own window; a broadcast URL lands in all of
them; summoning a window puts it on screen and in the foreground within 5 seconds
and parking it takes it back off every monitor; every box has its own live tile;
the tile grid is laid out sanely and clicking tile *i* selects box *i*; the tiles
show current page content (proven by flipping every page from red to blue and
reading the pixels back off the screen, while every window is parked off-screen);
a full dashboard refresh stays under its time budget; the tiles are still whole
after the dashboard is maximised; and a parked window has no taskbar button and
no Alt-Tab entry. It prints PASS or FAIL for each, then closes everything. Pass a
URL as an argument to broadcast that instead of the built-in local test page.

Because it reads pixels off the screen, `verify.py` needs a desktop session, and
it will steal focus and cover part of your screen while it runs. **Do not use the
machine while it runs.** The summon check works by taking the foreground and
checking it keeps it, so clicking another window, or alt-tabbing, will take the
foreground away from it. When that happens the check says `NO VERDICT (outside
interference)` and names the window that interrupted it, rather than reporting a
failure that is not real. A box losing focus to *another box* is still a genuine
failure and is still reported as one.

## What this is not

Deliberately left out. These are not missing features, they are decisions:

- No AI or model calls anywhere in the codebase.
- No agent loop, task runner, or harness integration.
- No charts, progress bars, metrics, or log panes. The tile grid is the whole UI.
- No scoring, ranking, prioritising, or automatic task swapping.
- No messaging between windows and no shared work queue.
- No login handling, credential storage, containers, or remote execution.

Connecting an AI agent runtime to each window is the intended long-term
direction, but none of it exists yet and none of it is in this codebase.

Also worth knowing: profiles are temporary and thrown away when the app closes.
The windows are separate browser launches, which keeps their cookies and storage
apart in practice, but nothing here is built or tested as a security boundary.
Do not rely on it as one.
