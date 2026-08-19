# Multiboxing for Agents

Runs several real Chromium windows at once and shows them all as live tiles in a
single dashboard — the only window you ever see. The browser windows themselves
are parked off the desktop: no taskbar buttons, no Alt-Tab entries, nowhere on
screen. Double-click a tile to open that window large, with a chat panel beside
it.

The chat is where a per-window agent will eventually be. Nothing is connected
yet: what answers you is a scripted stand-in that walks a fixed sequence on a
timer. There is no AI anywhere in this program. `PLAN.md` has the milestones.

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
window, the dashboard, which you can move and resize like anything else. It has
two views.

**The overview** is a grid of live tiles, one per window. Each tile is a real,
continuously updating view of that browser — not a screenshot taken once at
startup. The window name, what it is doing, and its current page are printed
under each tile, and a coloured ring around a tile repeats its state so you can
read the fleet at a glance. Tiles show the whole browser window, so you will see
its tab strip and address bar above the page itself.

Five states, and no others:

| State | Means |
| --- | --- |
| **idle** | no task has been given to this window |
| **working** | it is being driven right now |
| **needs input** | it stopped and asked you something |
| **done** | the task finished |
| **failed** | it gave up, or something broke |

`needs input` and `failed` are the two worth looking for — they are the ones that
want you. Every state is spelled out in words next to its colour, so the colour
is never the only signal.

**Double-click a tile** to open that window's own view, which fills the
dashboard:

- **The live view** — the same live mirror, as large as the window allows.
- **A chat panel** along the bottom. Type and press Enter to give that window a
  task; what it says back appears here. Each window keeps its own conversation,
  and they are forgotten when the app closes.
- **A trajectory panel** beside the live view, listing what the window did while
  working — pages opened, things clicked. It is separate from the chat on
  purpose, so the chat stays short enough to read. A new task clears it.
- **The state**, as a coloured word next to the window's name.

## What actually answers you

Nothing real, yet. Every window is driven by a scripted stand-in that ignores
what you asked and follows a fixed sequence on a timer. It exists so the states
and the panels can be built and looked at before anything expensive is connected.
Knowing its script makes the app predictable to demo:

- Every task starts with an opening line, then a few trajectory steps.
- **The first task you give a window stops halfway and asks you a question.**
  That is how `needs input` is reachable without special effort — answer it in
  the chat and the window carries on to `done`.
- **A task whose text contains the word "fail" ends in `failed`.** The only way
  to see that state, and a deliberate cheat.
- Anything else finishes with an answer.

The pages in the windows do not change while this happens. The stand-in never
touches them: it makes up everything it claims to have done.
- **"Take control"** summons the real browser window onto the middle of the
  screen and gives it the keyboard, for when you need to type into the page
  yourself. Click back on the dashboard, or switch to any other app, and it goes
  back to its parking slot; its tile keeps updating the whole time. Only one
  window is ever out at once. You are not expected to need this often — the live
  view is a mirror, so it cannot be clicked into, and this is the way around
  that.
- **"Back"** returns to the overview.

Nothing is broadcast to the windows: no clicks, no typing, no mouse positions,
and no fan-out URL bar. Each window is dealt with one at a time.

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
  "window_size": [1440, 900],
  "window_layout": "hidden",
  "dashboard": {
    "size": [1600, 1000],
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
  when summoned onto the screen. This is also the largest anything will ever be
  drawn: neither a tile nor the detail view's live view is scaled past its
  window's real size, because Windows will not reliably paint a live thumbnail
  bigger than its source. So if you make the dashboard very large and the picture
  stops growing, raise `window_size`. Parked windows are off-screen, so a bigger
  number costs memory rather than desk space.
- `window_layout` — `hidden` (default) parks the windows off the desktop and out
  of the taskbar and Alt-Tab. Any other value puts them back on the desktop as
  ordinary staggered windows, which is there for when you need to look at what a
  browser is actually doing.
- `dashboard.size` — `[width, height]` for the dashboard window, which opens
  centred on the screen. Move or resize it afterwards and the tiles re-flow.
- `dashboard.columns` — how many tiles per row on the overview. `"auto"` (the
  default) picks whichever count makes the tiles biggest, which is usually what
  you want; set a number to override it.
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

This launches the windows, builds the dashboard, and runs eight checks: each box
is a live Chromium process with its own window; summoning a window puts it on
screen and in the foreground within 5 seconds and parking it takes it back off
every monitor; every box has its own live tile; the tile grid is laid out sanely
and double-clicking tile *i* opens box *i*; the tiles show current page content
(proven by flipping every page from red to blue and reading the pixels back off
the screen, while every window is parked off-screen); a full dashboard refresh
stays under its time budget; the tiles are still whole after the dashboard is
maximised; and a parked window has no taskbar button and no Alt-Tab entry. It
prints PASS or FAIL for each, then closes everything. Pass a URL as an argument
to point the windows at it instead of the built-in local test page.

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

- No scoring, ranking, prioritising, or automatic task swapping between windows.
- No messaging between windows and no shared work queue.
- No login handling, credential storage, containers, or remote execution.
- No charts, progress bars, or metrics.

There is **no AI or model call anywhere in this codebase**, and no agent loop.
What answers in the chat is the scripted stand-in described above — it makes no
decisions and never touches the pages. `PLAN.md` describes how a real agent is
meant to get there.

Also worth knowing: profiles are temporary and thrown away when the app closes.
The windows are separate browser launches, which keeps their cookies and storage
apart in practice, but nothing here is built or tested as a security boundary.
Do not rely on it as one.
