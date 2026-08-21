# Demo storyboard

What the demo film is, shot by shot, before it is a script. `demo.py` is built
from this and `transcript.md` is narrated against it; if a beat is not here, it
should not be in either.

The original demo had a storyboard once and it was not checked in, which is why
the film was hard to change afterwards: every timing decision had to be
re-derived from the code that implemented it. This file is that missing
document, rewritten for the longer version.

Target: **about four and a half minutes**, one film, one take. The last act is
variable -- five model loops decide how many turns they need -- so 4:30 is the
floor and 5:15 is a slow take. The first draft of this storyboard said four
minutes; the narration is what pushed it, and the holds were fitted to the lines
rather than the other way round.

---

## What this version adds, and what each addition costs

Six asks, and the decision each one turned into.

| Ask | Decision |
|---|---|
| A broader variety of viewport counts | The fleet is **3 at the start, 8 at its peak, 5 at the end**. The grid reflows on camera twice, in both directions. |
| Highlight the needs-your-attention button more | **A product change, not staging.** The jump button fills amber -- the `needs input` colour, the same one on the tiles it is counting -- and swells twice when it arms. The demo then arms it with two boxes at once and answers them one after the other. |
| A good-looking homepage for new boxes | A bundled **start page**, shipped as `start_url` in `config.json`, so it is the product's default and not demo dressing. Six bookmarks and nothing else -- the first draft put the box's bird name across it in large type and described the dashboard, which read as recursive, and was. `start_url` also takes a list now, one page per box. |
| A balance of invented and real websites | An invented internal ops suite -- **Pinion Ops** -- served over local HTTP, alongside NPR, CNN, CERN, the RFC editor, Wikipedia, Hacker News and the Python docs. Roughly half and half in every act that has more than one box working. |
| Many tasks at once, tiles toggling between states | A fourth agent kind, `--agent demo`, in `agent_host.py`. It really drives its browser over CDP -- real navigations, real screenshots, real clicks -- but along a deterministic score, so eight boxes churn through all five states on cue instead of whenever the network feels like it. |
| Actual Claude output in the chat | The final act is **five boxes on Claude at once**, two of them reading Pinion Ops and three reading the real internet. |

### Two of these have a bill or a rule attached

**The state churn is choreographed, not faked.** `session.py` decides nothing and
neither does the director: every state in this film is reported by a child that
had just done the thing. `DemoAgent` gets its failure from a URL that really
404s -- our own server, so it fails identically with no network -- and its `needs
input` from a task that really names no page. What the demo agent adds over the
scripted one is *pacing*: a longer, varied action score, not authority over the
state machine.

**The paid act is five model loops per take, not three.** `MAX_TURNS` is 12, so
the worst case is sixty model turns. Rehearse with `--no-claude`, which sends the
same five questions to the demo agent and gets as far as a script can get.

---

## The cast

### The fleet

| Beat | Boxes | Why that number |
|---|---|---|
| 0:00-1:16 | **3** -- Wren, Finch, Swift | Big tiles. You can read a page in one, which is what makes "this is a live window, not a screenshot" land. |
| 1:16-3:03 | **8** -- plus Heron, Robin, Kestrel, Plover, Egret | Small enough to read as a fleet, large enough that each tile still shows what page it is on. Nine cells with the add tile; at 1600x1000 that is a 3x3 grid of roughly 450x240 tiles, comfortably above `layout.MIN_TILE`. |
| 3:03-end | **5** | Back to the shipped default, and the size the Claude act is legible at. |

`config.json` stays at five boxes -- `verify.py` is choreographed against it.
`demo.py` trims its own copy of the config to three at launch and grows from
there.

### The websites

**Invented -- Pinion Ops.** One fictional company's internal tools, served from
`sites/` over `http://127.0.0.1:<port>/` by the demo itself.

| Page | What it is | Why it is here |
|---|---|---|
| `/` | Service status board: services, state, uptime, last deploy | Dense, glanceable, and it changes colour in a 450px tile |
| `/tickets` | The ticket queue: id, priority, opened, assignee | Every column is a question a model can be asked |
| `/changelog` | Deploy log with timestamps | Something to cross-reference the status board against |
| `/inventory` | A hardware table | A page whose answer needs the whole table read |
| `/runbook` | One incident runbook | The take-control beat's page; its text is ours, so Ctrl+F is guaranteed to match |
| `/deploys/482` | **404** | The honest failure in the churn act |

Two things the invented sites buy that the real ones cannot. Their first
`a[href]` is a real, visible link, so a scripted agent is not fighting a hidden
"Skip to content" link. And their answers do not change between takes, so
narration written against them does not go stale -- which is exactly the problem
with narrating "the top story on Hacker News".

They are **light**, deliberately, against the dashboard's dark chrome. Eight dark
tiles inside a dark window read as one texture; a light page in a dark frame
reads as a website.

**Real.** NPR (`text.npr.org`), CNN (`lite.cnn.com`), the first website ever
published at CERN, the RFC editor, Wikipedia, Hacker News, the Python docs.
Nothing signs in, submits a form, or changes anything anywhere.

**The start page.** `sites/start.html`, in the app's palette: six bookmarks and
nothing else. It says nothing about Aviary, nothing about boxes, and nothing
about the window it is in -- the first version put the box's own bird name across
it in large type and explained that it was a browser being mirrored in a
dashboard, which is a page inside a window describing the application drawing the
window. The tile caption already says which bird it is.

It is also load-bearing, and not only as furniture: **a box only asks for a URL
while it is still on its start page.** Given a task with no URL, an agent works
with whatever page the box is on, and only comes back to ask when there is none.
So `needs input` is a state each box can produce exactly once, and the three
beats that want it on camera each have to spend a box that has never navigated.

### The drivers

| Act | Driver | Money |
|---|---|---|
| 0-8 | `--agent demo` | none |
| 9 | five children swapped to `claude` through the ordinary constructor | yes |

---

## Beat sheet

Nominal, at `--pace 1.0`. Real times move; cut against the beat sheet `demo.py`
prints when it finishes.

| # | Beat | At | Length | Fleet |
|---|---|---|---|---|
| 1 | overview - three live tiles, each on its own start page | 0:00 | 10s | 3 |
| 2 | one box gets a page; two get tasks with no page in them | 0:10 | 26s | 3 |
| 3 | two boxes need you, and the button says so | 0:36 | 20s | 3 |
| 4 | answer one, and the button is still lit for the other | 0:55 | 21s | 3 |
| 5 | + Add box, five times, live | 1:16 | 30s | 3 to 8 |
| 6 | four boxes go to work at once | 1:46 | 12s | 8 |
| 7 | a second wave, while the first is still going | 1:58 | 25s | 8 |
| 8 | detail view: live mirror, trajectory, chat | 2:23 | 13s | 8 |
| 9 | stop a run mid-flight | 2:36 | 13s | 8 |
| 10 | take control: the real window, on the desktop, with the keyboard | 2:49 | 10s | 8 |
| 11 | look back at the dashboard and it parks itself | 2:59 | 5s | 8 |
| 12 | close three; the grid comes back down | 3:04 | 16s | 8 to 5 |
| 13 | same seam, different driver: Claude takes five boxes | 3:20 | 10s | 5 |
| 14 | five boxes, five questions, at once | 3:30 | 16s | 5 |
| 15 | watch one of them think | 3:46 | 13s | 5 |
| 16 | the answers, and what they cost | 3:59 | 25-70s | 5 |
| 17 | close the dashboard; every window goes with it | 4:24 | 8s | 5 |

These are the beat names `demo.py` prints, and the times assume every wait
resolves at its measured length: a cold demo-agent task is about 13 seconds, a
real Chromium launch about 3, a resumed task about 11. The total is **4:32 plus
whatever the five model loops take**, so a take runs about 4:30 to 5:15.

Every beat's hold is at least as long as its narration needs at 150 words a
minute. That is arithmetic rather than taste, and it is why several holds are
longer than the first draft of this storyboard guessed: the lines came first,
the holds were fitted to them.

---

## The shots

### 0 - Cold open: three windows leave the desktop - 0:00 - 12s

A terminal, `demo.py` running, three Chromium windows appearing and immediately
leaving the screen, the dashboard opening centred. Alt-Tab shows nothing but the
dashboard; the taskbar is empty.

Unchanged from the original except the count. Three windows leaving is easier to
follow than five.

### 1 - Three live tiles, nothing needs you - 0:00 - 10s

Three large tiles, all on the same quiet start page. The header greets whoever is
logged in, every count is hidden, and the jump button is grey and reads **Nothing
needs you**.

At three-up the tiles are large enough to read a page in, which is what makes
"this is a live window, not a screenshot" land. Hold on the grid, then hover one
tile so the frame and caption lift.

### 2 - One box works; two come back and ask - 0:10 - 24s

Wren gets the status board. Finch and Swift get tasks that name no page at all --
what the on-call rota says this week, and read the second paragraph of nothing in
particular -- and neither box has been anywhere, so both stop and ask.

On screen: one tile goes blue and starts moving, captions filling with a real
URL. Two go amber almost immediately, and the button in the corner lights.

Two askers at once, here and nowhere else, because this is the only moment in the
film when two boxes are still fresh. It is also why Finch does not simply open
the ticket queue: the queue arrives in the next beat, as the answer to its
question, which is a better way to show the page than opening it.

### 3 - Two boxes need you, and the button says so - 0:34 - 41s

The button is amber-filled and reads **Go to Finch (+1 more)**, having swelled
twice as it armed. Finch first because the button lists waiting boxes in fleet
order -- ordering them any other way would be ranking them, and nothing here
ranks anything.

The pointer glides onto it; the detail view opens on Finch with its question
already in the chat; the ticket queue's URL is typed in and sent; Finch carries
on and finishes.

Back to the overview -- and the button is still armed, now reading **Go to
Swift**. Press it again and answer that one with the inventory table. That second
press is the whole point of the beat: the button is a queue of what is waiting,
not a notification you dismiss.

### 4 - + Add box, five times, live - 1:15 - 30s

The pointer glides to the add tile and presses it five times, roughly four seconds
apart. Each press: the tile shows `launching...`, the dashboard stops answering
for a moment while Chromium starts, the grid reflows, and the new box arrives
already on its own start page with its own name.

3, 4, 5, 6, 7, 8, reflowing every time. The tiles never stop updating during the
freeze, because Windows composites them and not us -- worth saying out loud.

Adds must stay at least `ADD_DEBOUNCE_S` apart, and each one blocks the UI thread
for a second or two anyway.

### 5 - Eight boxes, mixed work, every state on screen - 1:32 - 45s

The centrepiece. Two waves.

**Wave one** -- four boxes get tasks in three seconds: the deploy log, NPR, the
incident runbook, and CNN. Four tiles turn blue at once.

**Wave two**, as the first ones land -- three more go out: CERN's first website,
`http://127.0.0.1:<port>/pinion/deploys/482` (which 404s, and that box really
fails), and one with no URL at all. That last one goes to Plover, a box added
four minutes ago and never given anything, because a box that has already been
somewhere cannot ask. Egret is the other one held back, for the stop beat.

What the grid does over the next thirty seconds is the reason the demo agent
exists: eight tiles crossing between idle, working, done, needs input and failed
on different clocks, the header counts moving with them, one red frame and one
amber frame swelling as they arrive, and the jump button arming again mid-act.
Nothing reorders. Nothing is scored. The tile that failed stays exactly where it
was.

Half the pages are invented and half are real, and both halves are being driven
identically.

### 6 - Detail view, and Stop mid-flight - 2:17 - 22s

Into Robin, which clicked through from the NPR front page to a story: the live
mirror large, the trajectory panel's list of what it actually did, its chat, its
state chip.

Then Egret -- the box added last and never given a task -- gets its first one. Its
child spends a second or two importing Playwright and attaching over CDP, and that
is the window Stop lands in. The input greys out, Stop becomes the live button, the
pointer presses it, the box drops to idle and the trajectory stays on screen.

Egret is left out of act 5 for exactly this reason: on a warm child the cancel
arrives after the run is already over.

### 7 - Take control: the real window and the real keyboard - 2:39 - 20s

Take control on Kestrel, which is showing the Pinion runbook. The real Chromium window
arrives in the middle of the screen. Ctrl+F opens Chrome's own find bar,
`Degraded` is typed into it, matches highlight down the page, Escape closes it. The
tile behind is still updating.

Then focus goes back to the dashboard and the window parks itself.

The find term is on **our** page now rather than on lite.cnn.com. A find that
matches nothing reads as a broken browser, and a real site can drop the word
between takes.

### 8 - Close three; the grid comes back down - 2:59 - 12s

Three boxes closed one after another from their detail views. 8, 7, 6, 5,
reflowing each time. Windows, agent processes and conversations go with them, and
nothing is written back to `config.json`.

The counterpart to act 4, and the reason the fleet arc is a shape rather than a
ramp.

### 9 - Five boxes on Claude, five real questions - 3:11 - 40-70s

Five children swapped for Claude loops through the ordinary constructor, onto the
same sessions, so every conversation so far is still there.

| Box | Page | Question |
|---|---|---|
| Wren | Pinion status board | Which service is degraded, and how long has it been? |
| Finch | Pinion tickets, then the status board | What is the oldest unassigned P1, and who owns the service it is filed against? |
| Swift | Wikipedia, hypervisors | Type 1 versus type 2 in one sentence, with an example of each from the page |
| Heron | Hacker News front page | Which story has the most points right now, and how many comments? |
| Robin | Python `pathlib` docs | Which method writes text to a file, and what does it do if it already exists? |

All five sent within three seconds. Then Finch up close while the other four work
behind it: its question needs two pages, so its trajectory fills with tool calls
nobody scripted -- `goto`, `read_page`, `screenshot`, `click`, `goto` again.

Back to the overview for the answers landing in five chats, and the cost line at
the end of each trajectory.

The two invented pages are here on purpose: their answers are the same in every
take, so the narration can name them out loud. The three real ones are here for
the opposite reason.

### 10 - Close the dashboard - ~4:00 - 5s

Every window, every agent process, every conversation, every profile.

---

## What this implies in code

| File | Change |
|---|---|
| `sites/` | New. `start.html` plus the Pinion Ops pages and one shared stylesheet. No build step and no binary assets -- hand-written HTML and CSS, the same way the app's icon is a painted `QIcon` rather than a `.ico`. |
| `sites.py` | New. Resolve a bundled page to a `file://` URL for ordinary runs; `serve()` a directory over local HTTP for the demo. |
| `boxes.py` | `load_config` resolves a relative `start_url` to a bundled page; a bundled start page gets `?box=<name>` so each copy knows its bird. Absolute URLs are left exactly as configured. |
| `config.json` | `start_url` becomes `sites/start.html`. |
| `agent_host.py` | `DemoAgent(BrowserAgent)` -- same browser, same honesty about state, a longer deterministic score. Reached by `--agent demo`. |
| `ui/theme.py`, `ui/overview.py`, `ui/motion.py` | The jump button: amber fill when armed, a two-beat swell on the rising edge only. |
| `demo.py` | Rewritten script -- ten acts, the fleet arc, the local server's lifetime, five Claude swaps. |
| `transcript.md` | Rewritten. It is also **stale today**: it still narrates `box1` to `box6`, from before the boxes were birds. |
| `README.md` | The `--agent demo` kind, the `sites/` pages, the `start_url` key. Required by the README rule. |
| `smoke.py` | The start page resolves and carries its box name; `DemoAgent` reaches all five states against a stand-in; the jump button arms, swells once, and does not swell again while it stays armed. |
| `verify.py` | Untouched. It is choreographed against the five boxes in `config.json`, which do not change -- but it has not been re-run since `start_url` changed, and it is the only thing that covers the launch path with real windows. |
| `narrate.py` | New, and not in the original plan. `narration.txt` is generated from `transcript.md` rather than maintained, and smoke fails if it is stale -- the transcript had already drifted once, describing boxes renamed two changes earlier. |

## What could ruin a take

- **The adds.** Five launches in twenty-six seconds is the least forgiving part of
  the film. Each one blocks the UI thread, and PID attribution is racy if two ever
  overlap -- `ADD_DEBOUNCE_S` is what stops that, and the script must respect it
  rather than rely on it.
- **The real sites.** Four of them appear in act 5 and three in act 9. `main()`
  probes them before launching anything; a warning there means re-shoot rather
  than record seven failures.
- **The Claude act's length.** Five loops, up to twelve turns each. The narration
  for that act is written to be paused on.
- **Anything touching the machine during act 7.** The summoned window holds the
  keyboard, and a stray click parks it early.
