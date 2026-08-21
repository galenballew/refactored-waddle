# Reel storyboard

What the demo is, shot by shot, before it is a script. `demo.py` is built from
this and `transcript.md` is narrated against it; if a beat is not here, it should
not be in either.

**It is a reel, not a walkthrough.** Two and a half minutes. The job is not to
demonstrate the app, it is to say what the app is for, and then get out. A viewer
does not need to watch a thing happen; they need to see that it happened.

Target: **2:28 nominal, 2:18 to 3:08 in practice**. The range is the model act at
the end -- three model loops decide how many turns they need.

---

## The three rules this version is built on

**1. The cursor is real.** Every control the reel presses is pressed: the pointer
travels to it and the left button goes down and up, through `clicks.py`, and
Windows delivers the click to the dashboard's own widget. This is not about
authenticity for its own sake -- video editors track the cursor, and a demo that
changes the app by calling its methods produces footage where things happen and
nothing moves. Between beats the pointer drifts across the grid rather than
parking, so there is always something to follow, and drifting over a tile lifts
its frame on the way past, which is the app's own hover state doing the work.

The single exception is **the fan-out**, and it cannot be anything else. Six
boxes get a task inside three seconds; a person can only type into one box at a
time, which is exactly why a fleet is worth having and exactly why that shot
cannot be performed by hand. It goes through `App.send`, the same call the chat
box makes. Nothing else in the film is cast that way, and the docstring says so
where it happens.

**2. The narration says what it is for, not what is happening.** The screen is
already showing what is happening. A phone demo does not say "press one, press
two, press three"; it says you can call a friend. Every line in `transcript.md`
is checked against that, and `narration.txt` is generated from it.

**3. Nothing is faked.** Every state is reported by the child that earned it. The
failed tile is a real 404 from this repo's own server; the box that asks is one
that genuinely has nothing to work with.

---

## What was cut, and what it cost

The previous version was 4:32 and showed everything the app can do. This is the
same app with two thirds of it removed.

| Cut | What it cost |
|---|---|
| The fleet arc, 3 -> 8 -> 5 | The grid reflowed three times on camera. One add survives, at 0:09, because "the fleet is not a fixed size" is a product claim and the rest was choreography. |
| Stop a run mid-flight | The clearest statement that you are in charge of a running agent. The narration now carries that instead of the picture. |
| Close a box | Add box already makes the point in one direction; the other direction is not worth twelve seconds. |
| Two boxes waiting, answered one after the other | Showed that the button is a queue rather than a notification. One waiter still shows the button working; the queue idea moved into the line. |
| "Look back and it parks itself" as its own beat | Folded into the take-control beat, where it happens anyway. |
| Five model tasks | Three. The act reads identically and costs 40% less per take. |

None of these are gone from the app. They are gone from the film.

---

## The cast

**Six boxes.** Five from `config.json`, one added on camera. Six is the largest
grid where a tile is still big enough to show what page it is on at 1600x1000,
and it is enough boxes to read as a fleet rather than a handful.

**The pages, half invented and half real.**

| | |
|---|---|
| Pinion Ops (`sites/pinion/`) | A fictional company's status board, ticket queue and incident runbook, served over local HTTP by `demo.py`. Their content does not move between takes, so the narration can name an answer out loud. |
| `/pinion/deploys/482` | Answers **404**. This is the failed tile: a real HTTP response, not a staged state. |
| NPR, CNN | The real internet, in the fan-out. |
| Wikipedia, the Python docs | The real internet, in the model act. |

**The start page.** `sites/start.html` -- six bookmarks and nothing else. It says
nothing about Aviary, boxes or dashboards, because a page inside a window
describing the application drawing the window reads as strange as it sounds.

It is also load-bearing: **a box only asks for a URL while it is still on its
start page.** Given a task with no URL, an agent works with whatever page the box
is on and only comes back to ask when there is none. Kestrel is added at 0:09 and
given a task with no URL at 0:16, and it is the box that has been nowhere, which
is what makes it able to ask at all.

---

## Beat sheet

| # | Beat | At | Length |
|---|---|---|---|
| 1 | five live windows, one dashboard | 0:00 | 9s |
| 2 | one more, on camera | 0:09 | 8s |
| 3 | six tasks, three seconds | 0:16 | 38s |
| 4 | the one that needs you, and answering it | 0:54 | 22s |
| 5 | take control: the real window, with the keyboard | 1:16 | 10s |
| 6 | same seam, different driver | 1:26 | 1s |
| 7 | three questions no script could answer | 1:27 | 55s |
| 8 | close the dashboard; every window goes with it | 2:22 | 6s |

Computed from `demo.py`'s own holds plus the measured length of each wait -- a
cold demo-agent task is about 13 seconds, a real Chromium launch about 3, a
resumed task about 12, and the model act 20 to 70. Every beat's hold is at least
as long as its narration needs at 150 words a minute; that is arithmetic, not
taste, and `--pace` is the lever for a slower narrator.

---

## The shots

### 1 - Five live windows, one dashboard - 0:00 - 9s

Five large tiles, all on the same quiet start page. Every count in the header is
hidden and the button in the corner is grey. The pointer drifts across the grid
and a frame lifts as it passes.

The opening has to establish two things before anything happens: these are real
windows, and there is only one of them on your desktop.

### 2 - One more, on camera - 0:09 - 8s

The pointer travels to the add tile and presses it. Chromium launches, parks
itself, and the grid reflows to six.

Eight seconds for a product claim -- the fleet is whatever size you need -- and
the first real click of the film, which sets the expectation that the cursor is
doing the work.

### 3 - Six tasks, three seconds - 0:16 - 38s

Six boxes given work inside three seconds, then thirty seconds of the grid
diverging on its own. Tiles go blue, then green; one goes red; one goes amber.
The counts move. The pointer wanders the grid. Nothing changes position.

The centre of the reel, and the only shot that shows a fleet rather than an app.
Three of the pages are ours and two are the real internet, and the dashboard does
not know the difference. The red tile is a genuine 404 and the amber one genuinely
has nothing to work with -- both states come from the child that earned them.

### 4 - The one that needs you, and answering it - 0:54 - 22s

The amber button is pressed. The detail view opens on the box that asked, with
its question already in the chat. A URL is typed in on the real keyboard, a
character at a time, and sent. The run picks up where it stopped.

The answer is the incident runbook, which is also the page the next beat needs --
so the reel spends no time getting there.

### 5 - Take control: the real window, with the keyboard - 1:16 - 10s

Take control, and the real Chromium window arrives on the desktop. Ctrl+F opens
Chrome's own find bar, `Degraded` is typed into it, matches highlight down the
page. Escape, and focus returns to the dashboard; the window goes back to its
slot.

Ten seconds, and it is the only thing in the film that proves the tiles are
windows rather than pictures. The find term is on **our** page -- the runbook says
it six times -- because a find that matches nothing reads as a broken browser, and
a real site can drop a word between takes.

The return to the dashboard is `App.focus_window()` rather than a click: the
dashboard is behind a browser window at that moment, so a click would land on the
page.

### 6 and 7 - Three questions no script could answer - 1:26 - 56s

Three children swapped for Claude loops through the ordinary constructor, onto
the same sessions, so every conversation so far is still there. Three questions
go out at once; one box is opened up close while the other two work behind it,
its trajectory filling with tool calls nobody scripted. The answers land, and the
last line of each trajectory is what it cost.

| Box | Page | Question |
|---|---|---|
| Wren | Pinion tickets | What is the oldest unassigned P1, and which service is it filed against? |
| Finch | Wikipedia, hypervisors | Type 1 versus type 2, in one sentence, with an example of each |
| Swift | Python `pathlib` docs | Which method writes text to a file, and what does it do if it already exists? |

One invented page and two real ones. The invented one is there so the narration
can say what the answer is without it going stale between takes.

### 8 - Close - 2:22 - 6s

Back to the grid, then the app closing. Every window, every agent process, every
conversation, every profile.

---

## What could ruin a take

- **A hand on the mouse.** Synthetic clicks land wherever the pointer is, on
  whatever window is in front. The director checks `App.holds_foreground()`
  before every one and reports how many it skipped, but nothing beats leaving the
  machine alone.
- **The add at 0:09.** A real Chromium launch blocks the UI thread. The click that
  starts it is queued by the OS and delivered when the thread resumes, which is
  what `ADD_DEBOUNCE_S` exists to survive.
- **The real sites.** Four appear. `main()` probes them before launching anything.
- **The model act's length**, which is the only thing that can push the reel past
  three minutes.
