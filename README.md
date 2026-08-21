# Aviary

Runs several real Chromium windows at once and shows them all as live tiles in a
single dashboard — the only window you ever see. The browser windows themselves
are parked off the desktop: no taskbar buttons, no Alt-Tab entries, nowhere on
screen. Double-click a tile to open that window large, with a chat panel beside
it.

Each window has its own agent process, which drives that window's browser over
the DevTools protocol: it opens pages, reads them, takes screenshots and clicks
links. By default a fixed script decides what to do next and nothing calls a
model. Start it with `--agent claude` and Claude decides instead — that is the
only path that costs money, and you have to ask for it every time.

## What you need

- Python 3.9 or newer. Only 3.12 has actually been run; nothing in the code
  needs anything newer than 3.8, but the other versions are untested.
- Playwright, plus its Chromium build
- PySide6, which draws the dashboard
- The `anthropic` package, only if you want Claude driving the windows

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install playwright PySide6
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m pip install anthropic      # only for --agent claude
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
read the fleet at a glance. When the grid has room to spare, a second line under
each tile shows the last thing that window actually did. Along the top is a count
of how many windows are in each state, and a button that opens whichever one is
waiting on you. That button is the one loud control in the app: while at least
one window is waiting it fills in the same amber those windows' rings are wearing
and swells twice to say it has just started counting, and when nothing is waiting
it goes quiet and greys out. It swells on the way up only — a second window
joining the queue is not news, and a control that pulses forever is a colour you
learn to ignore. Tiles never reorder themselves, so the fleet always looks the
same shape. Tiles show the page only: the browser's own tab strip and address bar
are cropped out, so five tiles read as a dashboard rather than as five
screenshots of a browser. The last cell of the grid is **+ Add box**, which starts
another window there and then.

Moving the pointer over a tile lifts its frame and caption and turns the cursor
into a hand, which is the affordance for double-clicking it open. Nothing is ever
drawn *over* a tile — the live mirror is composited above everything the app
paints, so the only way to draw across one would be to blank the window you are
pointing at.

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

A window changing state does not simply be a different colour the next time you
look: its frame crossfades to the new one, and for `needs input` and `failed` it
also swells twice and settles. Two beats is enough to catch an eye that was
somewhere else, and then it stops — nothing here blinks, breathes or loops, and
an idle fleet animates nothing at all.

**Double-click a tile** to open that window's own view, which fills the
dashboard:

- **The live view** — the same live mirror, as large as the window allows.
- **A chat panel** along the bottom. It already has the keyboard when the view
  opens, so you can type straight away. Type and press Enter to give that window
  a task; what it says back appears here. Each window keeps its own conversation,
  and they are forgotten when the app closes. A line under the transcript says
  what the window will do with what you type next.
- **Send and Stop.** While a window is working the input is disabled — it would
  be ignored, and a message that vanishes is worse than a greyed-out box — and
  **Stop** interrupts it. Stopping returns the window to `idle` and leaves the
  trajectory alone: it is a record of what happened.
- **A trajectory panel** beside the live view, listing what the window did while
  working — pages opened, things clicked. It is separate from the chat on
  purpose, so the chat stays short enough to read. A new task clears it. Both
  panels scroll, and scrolling back through one does not get yanked to the bottom
  when the window says something new.
- **The state**, as a coloured word next to the window's name.
- **"Take control"** summons the real browser window onto the middle of the
  screen and gives it the keyboard, for when you need to type into the page
  yourself. Click back on the dashboard, or switch to any other app, and it goes
  back to its parking slot; its tile keeps updating the whole time. Only one
  window is ever out at once. You are not expected to need this often — the live
  view is a mirror, so it cannot be clicked into, and this is the way around
  that.
- **"Close box"** shuts that window down for good: its browser, its agent
  process and its conversation, none of which come back. There is no
  confirmation, and the last remaining window cannot be closed.
- **"Back"** returns to the overview.

Nothing is broadcast to the windows: no clicks, no typing, no mouse positions,
and no fan-out URL bar. Each window is dealt with one at a time.

## What actually answers you

A script, not a mind. Every window has its own agent process, which attaches to
that window's browser over the DevTools protocol and really does drive it — but
what it does next is decided by a fixed sequence, not by anything that thinks.
**Started without `--agent claude`, nothing in this program calls a model.**

Given a task, an agent:

1. looks for a URL in what you typed — `example.com` counts, so does a full
   `https://…` or a `file:///…` path;
2. goes there, and says so;
3. **takes a screenshot** of the page (written to your temp folder as
   `aviary-<window>.png`);
4. reads the page's title and counts its links;
5. clicks the first link and reports where that landed;
6. finishes, with the title and the final address.

If you give it no URL and the window has no page to work with — a blank page, or
still on its start page — it stops and asks you for one. That is `needs input`,
and answering with a URL carries it on. If it is already on a real page, it works
with that one. If a page will not load or a click times out, it says what went
wrong and ends in `failed`. **Stop** ends the run between steps; a page load
already in flight finishes first.

What it does is real: the window really navigates, and you can watch it happen in
the tile. What it *decides* is not intelligence, and the results it reports are
only ever what a fixed script found.

### `--agent demo`

The same script, paced for a camera:

```bash
.venv\Scripts\python.exe main.py --agent demo
```

Every window moves at its own speed rather than all of them at once, the
trajectory it reports is longer, it clicks the first link in the *body* of the
page rather than the first in the markup — so it never lands on a hidden "skip to
content" link, and five windows reading five pages of one site do not all end up
on that site's front page — and a page that answers 404 is a **failure** rather
than a page it successfully loaded. Nothing here calls a model either. This is
what `demo.py` runs.

## Recording the demo

```bash
.venv\Scripts\python.exe demo.py --no-claude     # rehearse, free
.venv\Scripts\python.exe demo.py                 # the real thing, ~2.5 minutes
```

`demo.py` drives the real dashboard through a two-and-a-half-minute reel: six
windows, half the pages real websites and half a fictional internal tool suite
served from `sites/` over local HTTP. The last act swaps three windows onto
Claude, which is the only part that spends money — `--no-claude` sends the same
three questions to the demo agent instead, and is what rehearsals should use.

**It drives the real mouse.** The pointer travels to each control and the button
goes down and up, because the recording is as much about the cursor as the
screen. Between clicks it does not move at all: eight moves, eight presses, and
the cursor is parked for about 148 of the 152 seconds. The exception is the moment six windows are given work at once, which is
the thing a person cannot do by hand and the reason the app exists; that goes
through the same call the chat box makes.

Four files, in order: `storyboard.md` is what the reel is, `demo.py` implements
it, `transcript.md` is what is said over it, and `narration.txt` is the spoken
words with nothing else in it, generated by:

```bash
.venv\Scripts\python.exe narrate.py
```

If a recording ever shows the cursor doing something the screen did not — sliding
between clicks, or never moving at all — record this instead of another take:

```bash
.venv\Scripts\python.exe cursorcheck.py
```

Forty seconds of pointer movement with no clicks in it. It tells you whether the
recorder is seeing the cursor, which is a different question from whether the
cursor is moving, and the two were confused for three attempts.

**Do not touch the machine while a take is running.** Synthetic clicks land
wherever the pointer is, on whatever window is in front; the demo checks before
every one and tells you at the end how many it skipped, but a hand on the mouse
beats any check. One beat also summons a real browser window and hands it the
keyboard.

## Letting Claude drive instead

```bash
.venv\Scripts\python.exe main.py --agent claude
```

Every window gets a real Claude loop in place of the script. **This spends money
on your Anthropic account, once per task.** There is no config setting for it on
purpose: the paid path is something you ask for on the day you want it, not
something a file in the repository can switch on behind you.

You need the `anthropic` package installed (see above) and an API key in the
environment. Get a key from [console.anthropic.com](https://console.anthropic.com)
and set it in the terminal you start the app from — the agent processes inherit
their environment from the dashboard, so that is all it takes:

```bash
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

```bash
.venv\Scripts\python.exe main.py --agent claude
```

To keep it across terminals, `setx ANTHROPIC_API_KEY "sk-ant-your-key-here"` sets
it for your account and applies to terminals opened afterwards. **Do not put the
key in `config.json`** — that file is checked into the repository.

(The SDK will also use a profile from Anthropic's `ant` CLI if you have one, but
nothing here installs that and an API key is all this needs.)

Without credentials, a window tells you so in its chat and ends up `failed`;
nothing else breaks.

What changes: the window still opens pages, reads them, screenshots them and
clicks things, but Claude chooses which, in what order, and when it has enough to
answer. It can also stop and ask you a question of its own — that is the same
`needs input` state, and your reply goes straight back to it.

Two limits worth knowing:

- **Twelve model turns per task.** After that the window gives up and says so. A
  loop that will not converge is a bill, not a feature.
- **Every task reports what it cost** as the last line of its trajectory — how
  many turns, and the input and output tokens. Model is Claude Opus 5 unless you
  set `AVIARY_MODEL`.

Cancel still works, but only between turns: **Stop** cannot interrupt a model
call that is already in flight, so it takes effect when the current turn returns.

The browser windows are deliberately not on your desktop. You do not need to see
them directly — that is what the tiles are for. They are still running normally
while parked: a tile shows live page content whether its window is off-screen,
covered by other windows, or in front of you.

## Adding and removing windows while it runs

**+ Add box** on the overview starts one more window: it launches, parks itself
off the desktop, gets a tile, an agent process and its own conversation, and the
grid reflows to fit. **Close box** in a window's own view is the opposite, and it
is final — the browser closes and the conversation is gone.

Two things to know about it:

- **The dashboard stops responding for a second or two while Chromium starts.**
  The launch happens on the same thread as the interface and there is nowhere
  else to put it. The existing tiles keep updating throughout, because Windows
  composites them; it is only the dashboard that pauses. A second click on the
  tile during that pause is dropped rather than queued, so you get one window and
  not two.
- **Windows added this way are not saved.** `config.json` is untouched, and a
  restart brings back exactly the list below — the same as the transcripts and
  the browser profiles, which are also forgotten on exit.

`max_boxes` in the config is the ceiling; the add tile says so when it is
reached. If the dashboard window is too small to draw the tiles at a usable size,
the overview says that instead of going blank — make the window bigger.

## Changing the number of windows or their names

Edit `config.json`:

```json
{
  "boxes": ["Wren", "Finch", "Swift", "Heron", "Robin"],
  "start_url": "sites/start.html",
  "window_size": [1440, 900],
  "window_layout": "hidden",
  "max_boxes": 12,
  "dashboard": {
    "size": [1600, 1000],
    "columns": "auto",
    "gap": 20,
    "refresh_ms": 1000
  }
}
```

- `boxes` — the window names, in order. **The length of this list is the number of
  windows.** Add or remove entries to get more or fewer. Any names will do; the
  defaults come from an ordered list of birds in `boxes.AVIARY`, and "+ Add box"
  takes the first one not in use — so closing `Finch` and adding another gives
  you `Finch` back rather than shuffling every name along.
- `start_url` — where each window opens. A **path** is a page this repo ships,
  resolved against the repo folder and opened as a `file://` URL; the default,
  `sites/start.html`, is a quiet start page with a few bookmarks on it, so a
  grid of freshly opened windows is something to look at rather than a grid of
  blank white rectangles. A **URL** (anything with `://`, or `about:blank`) is
  opened exactly as written. It can also be a **list**, in which case the
  windows take the entries in turn and wrap around — so a fleet can open on
  several different pages:

  ```json
  "start_url": ["sites/start.html", "https://en.wikipedia.org", "about:blank"]
  ```

  One thing to know before pointing windows at real pages: a window that has
  already been somewhere will never ask you for a URL. Given a task with no URL
  in it, an agent works with the page the window is on, and only stops to ask
  when there is no such page. A start page counts as no page; a real one does
  not.
- `window_size` — `[width, height]` for each browser window, both while parked and
  when summoned onto the screen. This is also the largest anything will ever be
  drawn: neither a tile nor the detail view's live view is scaled past its
  window's real size, because Windows will not reliably paint a live thumbnail
  bigger than its source. So if you make the dashboard very large and the picture
  stops growing, raise `window_size`. Parked windows are off-screen, so a bigger
  number costs memory rather than desk space.
- `max_boxes` — the most windows **+ Add box** will let you get to, including the
  ones listed in `boxes`. There to stop a stuck finger opening thirty browsers.
- `window_layout` — `hidden` (default) parks the windows off the desktop and out
  of the taskbar and Alt-Tab. Any other value puts them back on the desktop as
  ordinary staggered windows, which is there for when you need to look at what a
  browser is actually doing.
- `dashboard.size` — `[width, height]` for the dashboard window, which opens
  centred on the screen. Move or resize it afterwards and the tiles re-flow.
- `dashboard.columns` — how many tiles per row on the overview. `"auto"` (the
  default) picks whichever count makes the tiles biggest, which is usually what
  you want; set a number to override it.
- `dashboard.gap` — pixels between tiles. Each tile's frame is drawn a few
  pixels outside its cell, so this has to leave room for two of them.
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

The agent processes look after themselves. Each one exits the moment the
dashboard's pipe to it closes, so a crash or a force-kill leaves none of them
behind — there is nothing to clean up there.

## Checking that it works

There are two of these. The quick one needs no browsers and takes about a
second:

```bash
.venv\Scripts\python.exe smoke.py
```

It builds the real dashboard against stand-in windows and spawns the real agent
processes, then checks the views, the message protocol, the five states, that the
chrome moves when something changes and stops moving when it stops, that the
header button arms, swells once and goes quiet again, what happens when an agent
process dies mid-task, that closing the dashboard takes its agent processes with
it, which agent each `--agent` value actually builds, and that every page this
repo ships resolves and serves — including the one that has to answer 404. Run
this one while you work.

The thorough one needs real windows:

```bash
.venv\Scripts\python.exe verify.py
```

This launches the windows, builds the dashboard, and runs eleven checks: each box
is a live Chromium process with its own window; summoning a window puts it on
screen and in the foreground within 5 seconds and parking it takes it back off
every monitor; every box has its own live tile; the tile grid is laid out sanely
and double-clicking tile *i* opens box *i*; the tiles show current page content
(proven by flipping every page from red to blue and reading the pixels back off
the screen, while every window is parked off-screen); a full dashboard refresh
stays under its time budget; the tiles are still whole after the dashboard is
maximised; a parked window has no taskbar button and no Alt-Tab entry; a window
added while the app is running is a real one, with its own processes and its own
window rather than someone else's; an agent told to open a page really does drive
its own browser there, screenshot and all; and closing the dashboard takes every
agent process with it. It prints PASS or FAIL
for each, then closes everything. Pass a URL as an argument
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

A model call is possible but never automatic: run it without `--agent claude` and
nothing in this program contacts Anthropic, with every decision coming from the
fixed script described above. That flag is the only thing here that costs money,
and it cannot be turned on from a config file.

Also worth knowing: profiles are temporary and thrown away when the app closes.
The windows are separate browser launches, which keeps their cookies and storage
apart in practice, but nothing here is built or tested as a security boundary.
Do not rely on it as one.
