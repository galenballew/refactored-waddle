# Aviary

**Run a fleet of browsers, watch them all at once, and only get interrupted when
one of them needs you.**

Aviary runs N real Chromium windows and shows them as live tiles in a single
dashboard — the only window you ever see. The browsers themselves are parked off
the desktop: no taskbar buttons, no Alt-Tab entries, nowhere on screen. Each one
has its own agent driving it, its own conversation, and its own state. You hand
out the work, and they come back when they are done or when they are stuck.

### ▶ [Watch the two-and-a-half-minute demo](https://youtu.be/Tm1ukBRyQ7w)

Six browsers, given work at once, on camera.

---

## Why

One agent driving one browser is a window you sit and watch. Five of them is five
windows fighting for your desktop, and no way to tell at a glance which one has
finished, which one has failed, and which one is quietly waiting for an answer.

Aviary makes that a hypervisor console instead. Every browser is a live tile —
real page pixels, updating continuously, not a screenshot taken once at startup —
and its state is written under it in words and repeated as a colour around it. A
count along the top says how the fleet is doing, and one amber button takes you
straight to whichever box is waiting on you. Work goes out in parallel; your
attention only goes where it is asked for.

There is no coordination layer and no shared queue. It is N conversations with N
browsers, kept legible.

## Quick start

Windows only — the live tiles and the window handling both use Windows APIs
directly. Python 3.12 is what this has been run on.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install playwright PySide6
```

```bash
.venv\Scripts\python.exe -m playwright install chromium
```

```bash
.venv\Scripts\python.exe main.py
```

Five Chromium windows open — one per name in `config.json` — and park themselves
off the edge of the screen. What is left on your desktop is one ordinary window
you can move and resize: the dashboard.

## The dashboard

**The overview** is the grid of live tiles. Under each one is the box's name,
what it is doing and the page it is on; around it is a ring in its state's
colour. Hovering lifts a tile's frame and caption. The last cell is
**+ Add box**, which starts another browser there and then. Tiles never reorder,
so the fleet always looks the same shape.

Five states, and no others:

| State | Means |
| --- | --- |
| **Idle** | no task has been given to this box |
| **Working** | it is being driven right now |
| **Needs input** | it stopped and asked you something |
| **Done** | the task finished |
| **Failed** | it gave up, or something broke |

`Needs input` and `Failed` are the two that want you, and the header button
counts them: it wears their amber while any box is waiting, swells twice when the
queue first opens, then goes quiet. Nothing in the app blinks, breathes or loops
— a state change crossfades, gets two beats of attention if it matters, and then
stops. An idle fleet animates nothing at all.

**Double-click a tile** to open that box on its own:

- **The live view**, as large as the window allows.
- **A chat panel** that already has the keyboard. Type a task, press Enter, and
  what the box says comes back here. Every box keeps its own thread; nothing is
  shared, and nothing survives the app closing.
- **Send and Stop.** The input is disabled while a box is working — a message
  that vanishes is worse than a greyed-out box — and **Stop** ends the run.
- **A trajectory panel** listing what the box actually did: pages opened, things
  clicked. Kept separate from the chat so the chat stays short enough to read.
- **Take control** summons the real browser onto the screen and hands it the
  keyboard, for when you need to type into a page yourself. Click back on the
  dashboard and it returns to its parking slot, tile still live. Only one box is
  ever out at a time.
- **Close box** ends that browser, its agent and its conversation, for good.

Nothing is ever broadcast to the fleet from the dashboard — no clicks, no
keystrokes, no fan-out URL bar. One box at a time.

## Who is driving

Each box gets its own agent process, which attaches to that box's browser over
the DevTools protocol and really does drive it. What it does next depends on
which agent you asked for.

| Command | Agent |
| --- | --- |
| `main.py` | **Script.** A fixed sequence: find a URL in what you typed, go there, screenshot the page, read its title and count its links, click the first link, report where it landed. No model, no cost. |
| `main.py --agent demo` | The same script, paced for a camera — staggered starts, longer trajectories, body links only, and a 404 counts as a failure. Still no model. |
| `main.py --agent claude` | **Claude decides instead.** The only path that spends money. |

Given a task with no URL in it, an agent works with the page the box is already
on. Only a box that has never been anywhere — blank, or still on its start page —
stops and asks you for one, which is what `Needs input` looks like. A page that
will not load, or a click that times out, ends in `Failed` with a reason.

What the script does is real: the browser really navigates, and you can watch it
happen in the tile. What it *decides* is not intelligence.

### Letting Claude drive

```bash
.venv\Scripts\python.exe -m pip install anthropic
```

```bash
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

```bash
.venv\Scripts\python.exe main.py --agent claude
```

**This spends money on your Anthropic account, once per task.** There is no
config key for it on purpose: the paid path is something you ask for on the day
you want it, not something a file in the repository can switch on behind you. Get
a key from [console.anthropic.com](https://console.anthropic.com) and set it in
the terminal you start the app from — the agent processes inherit their
environment from the dashboard. `setx ANTHROPIC_API_KEY "..."` keeps it across
terminals. **Do not put the key in `config.json`**; that file is checked in.

Claude still opens pages, reads them, screenshots them and clicks things — it
just chooses which, in what order, and when it has enough to answer. It can also
stop and ask you a question of its own, which is the same `Needs input` state,
and your reply goes straight back to it.

- **Twelve model turns per task**, then the box gives up and says so. A loop that
  will not converge is a bill, not a feature.
- **Every task reports what it cost** on the last line of its trajectory: how
  many turns, and the input and output tokens. The model is Claude Opus 5 unless
  you set `AVIARY_MODEL`.
- **Stop takes effect between turns.** It cannot interrupt a model call that is
  already in flight.

Without credentials a box says so in its chat and ends `Failed`; nothing else
breaks.

## Adding and removing boxes while it runs

**+ Add box** launches one more: it parks itself, gets a tile, an agent process
and its own conversation, and the grid reflows to fit. **Close box** in a box's
own view is the opposite, and it is final.

Two things to know. The dashboard **stops responding for a second or two while
Chromium starts** — the launch is on the same thread as the interface, and there
is nowhere else to put it. The existing tiles keep updating throughout, because
Windows composites them, and a second click during that pause is dropped rather
than queued, so you get one box and not two. And **boxes added this way are not
saved**: `config.json` is never written back, so a restart brings back exactly
the configured list, the same as the transcripts and the browser profiles.

`max_boxes` is the ceiling, and the add tile says so when it is reached.

<details>
<summary><b>Configuration</b></summary>

Edit `config.json` and restart the app.

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

- **`boxes`** — the names, in order. **The length of this list is the number of
  boxes.** Any names will do; the defaults come from an ordered list of birds in
  `boxes.AVIARY`, and "+ Add box" takes the first one not in use — so closing
  `Finch` and adding another gives you `Finch` back rather than shuffling every
  name along.
- **`start_url`** — where each box opens. A **path** is a page this repo ships,
  resolved against the repo folder and opened as a `file://` URL; the default,
  `sites/start.html`, is a quiet page with a few bookmarks on it, so a fresh grid
  is something to look at rather than five blank white rectangles. A **URL**
  (anything with `://`, or `about:blank`) is opened exactly as written. A
  **list** is dealt out to the boxes in turn and wraps around:

  ```json
  "start_url": ["sites/start.html", "https://en.wikipedia.org", "about:blank"]
  ```

  Worth knowing before pointing boxes at real pages: a box that has already been
  somewhere will never ask you for a URL. A start page counts as no page; a real
  one does not.
- **`window_size`** — `[width, height]` per browser window, both parked and
  summoned. It is also the largest anything is ever drawn: Windows will not
  reliably paint a live thumbnail bigger than its source, so neither a tile nor
  the detail view scales past it. If the dashboard is very large and the picture
  stops growing, raise this. Parked windows are off-screen, so a bigger number
  costs memory rather than desk space.
- **`max_boxes`** — the most **+ Add box** will let you reach, including the ones
  listed in `boxes`. There to stop a stuck finger opening thirty browsers.
- **`window_layout`** — `hidden` (default) parks the browsers off the desktop and
  out of the taskbar and Alt-Tab. Any other value leaves them on the desktop as
  ordinary staggered windows, for when you need to see what one is really doing.
- **`dashboard.size`** — `[width, height]` for the dashboard, which opens centred
  on the screen. Move or resize it afterwards and the tiles reflow.
- **`dashboard.columns`** — tiles per row on the overview. `"auto"` (the default)
  picks whichever count makes the tiles biggest; set a number to override it.
- **`dashboard.gap`** — pixels between tiles. Each tile's frame is drawn a few
  pixels outside its cell, so this has to leave room for two of them.
- **`dashboard.refresh_ms`** — how often the captions are rewritten and the
  browser window positions rechecked. The tile images themselves are always live
  and are not affected by this.

If the dashboard window is too small to draw the tiles at a usable size, the
overview says so instead of going blank.

</details>

<details>
<summary><b>Recording the demo</b></summary>

```bash
.venv\Scripts\python.exe demo.py --no-claude
```

```bash
.venv\Scripts\python.exe demo.py
```

`demo.py` drives the real dashboard through the reel linked at the top: six
boxes, half the pages real websites and half a fictional internal tool suite
served from `sites/` over local HTTP. The last act swaps three boxes onto Claude,
which is the only part that spends money — `--no-claude` sends the same three
questions to the demo agent instead, and is what rehearsals should use. `--pace`
stretches the holds for a slower narrator.

**It drives the real mouse.** The pointer travels to each control and the button
goes down and up, because the recording is as much about the cursor as about the
screen. Between clicks it does not move at all: eight moves, eight presses, and
the cursor parked for about 148 of the 152 seconds. The one exception is the
moment six boxes are given work at once, which is the thing a person cannot do by
hand and the reason the app exists.

**Do not touch the machine while a take is running.** Synthetic clicks land
wherever the pointer is, on whatever window is in front; the demo checks before
every one and tells you at the end how many it skipped, but a hand on the mouse
beats any check. One beat also summons a real browser window and hands it the
keyboard.

Four files, in order: `storyboard.md` is what the reel is, `demo.py` implements
it beat for beat, `transcript.md` is what is said over it, and `narration.txt` is
the spoken words with nothing else in them, generated by:

```bash
.venv\Scripts\python.exe narrate.py
```

If a recording ever shows the cursor doing something the screen did not — sliding
between clicks, or never moving at all — record this instead of another take:

```bash
.venv\Scripts\python.exe cursorcheck.py
```

Forty seconds of pointer movement with no clicks in it. It answers whether the
recorder sees the cursor at all, which is a different question from whether the
cursor is moving, and the two were confused for three attempts.

</details>

<details>
<summary><b>Checking that it works</b></summary>

The quick one needs no browsers and takes about a second — run it while you work:

```bash
.venv\Scripts\python.exe smoke.py
```

It builds the real dashboard against stand-in boxes and spawns the real agent
processes, then checks the views, the message protocol, the five states, that the
chrome moves when something changes and stops moving when it stops, that the
header button arms, swells once and goes quiet again, what happens when an agent
process dies mid-task, that closing the dashboard takes its agent processes with
it, which agent each `--agent` value actually builds, and that every page this
repo ships resolves and serves — including the one that has to answer 404.

The thorough one needs real windows and about a minute:

```bash
.venv\Scripts\python.exe verify.py
```

Eleven checks: every box is a live Chromium process with its own window;
summoning one puts it on screen and in the foreground within 5 seconds, and
parking it takes it back off every monitor; every box has its own live tile; the
grid is laid out sanely and double-clicking tile *i* opens box *i*; the tiles
show current page content, proven by flipping every page from red to blue and
reading the pixels back off the screen while every window is parked off-screen; a
full dashboard refresh stays inside its time budget; the tiles are still whole
after the dashboard is maximised; a parked window has no taskbar button and no
Alt-Tab entry; a box added while the app is running is a real one with its own
processes and its own window; an agent told to open a page really does drive its
own browser there, screenshot and all; and closing the dashboard takes every
agent process with it. It prints PASS or FAIL for each, then closes everything.
Pass a URL as an argument to point the boxes at it instead of the built-in local
test page.

Because it reads pixels off the screen, `verify.py` needs a desktop session, and
it will steal focus and cover part of your screen while it runs. **Do not use the
machine while it runs.** If another window takes the foreground mid-check, it
reports `NO VERDICT (outside interference)` and names the window that interrupted
it, rather than a failure that is not real. A box losing focus to *another box*
is still a genuine failure and is still reported as one.

</details>

## Quitting

Close the dashboard as you would any window; it shuts down every Chromium window
on the way out. Closing a summoned browser by hand instead leaves the dashboard
running with a tile that reads "no window", so use the dashboard.

That matters more here than usual: parked browsers have no taskbar button and no
Alt-Tab entry, so anything that outlives a force-killed dashboard is running
somewhere you cannot click on. To clear those out without touching your normal
Chrome:

```bash
powershell -c "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force"
```

The agent processes look after themselves. Each one exits the moment the
dashboard's pipe to it closes, so a crash or a force-kill leaves none of them
behind.

## What this is not

Deliberately left out. These are decisions, not gaps:

- No scoring, ranking, prioritising, or automatic task swapping between boxes.
- No messaging between boxes and no shared work queue.
- No login handling, credential storage, containers, or remote execution.
- No charts, progress bars, or metrics.

A model call is possible but never automatic: started without `--agent claude`,
nothing in this program contacts Anthropic, and every decision comes from the
fixed script. That flag is the only thing here that costs money, and it cannot be
switched on from a config file.

Profiles are temporary and thrown away when the app closes. The boxes are
separate browser launches, which keeps their cookies and storage apart in
practice, but nothing here is built or tested as a security boundary. Do not rely
on it as one.
