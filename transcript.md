# Demo narration

Voiceover for `demo.py`. The headings are the beat names the script prints to the
console as it runs, so a take can be lined up against its own log:

```bash
.venv\Scripts\python.exe demo.py
```

`storyboard.md` is what the film is; this is what is said over it. If a beat
moves, it moves there first.

Times are nominal, from a run at `--pace 1.0`. Real ones move — half the pages
are real websites over a real network, a cold agent child spends a second or two
starting Playwright, and the model act takes as long as the models take. **The
whole thing runs about 4:10 to 5:00**, and the range is the model act. Cut
against the beat sheet `demo.py` prints when it finishes, not against the numbers
here.

Read at about 150 words a minute. Each beat gives its word budget; every line
below is inside it. Nothing needs to be said over the top of the action — the
holds are long enough to land a sentence and then show the thing.

`narration.txt` is this file with everything but the spoken words taken out. It
is generated from this one, so edit a line here.

Rehearse with `--no-claude`. It is the same film with the demo agent driving the
last act instead of five Claude loops, and it is the only way to run this without
spending money.

## The sites, and why both kinds

**Real:** NPR, CNN, the first website ever published at CERN, the RFC editor,
Wikipedia, Hacker News, the Python docs. These are the point — ordinary Chromium
windows on the ordinary internet. Nothing signs in, fills in a form, or changes
anything anywhere; every box reads pages and clicks links, which is all the
agents can do.

**Invented:** Pinion Ops, a fictional company's internal tools, served from
`sites/` over local HTTP by `demo.py` itself. They are here for two reasons a
real site cannot cover. Their content does not move between takes, so the
narration below can say what an answer *is* — "the top story on Hacker News" is a
different story by the time the take is cut. And one of their URLs,
`/pinion/deploys/482`, answers 404 on purpose: that is where the red tile in the
churn act comes from, and it is a real HTTP response rather than a state anybody
set.

Do not describe Pinion as a product, a partner, or anything real. It is a set of
pages in this repository.

---

## Cold open — the launch · 0:00 · ~12s · 28 words

**On screen:** a terminal, `demo.py` running, three Chromium windows appearing
and immediately leaving the screen, the dashboard opening centred. Then an
Alt-Tab that shows nothing but the dashboard, and an empty taskbar.

> Three Chromium windows just started. They are already off the desktop — no
> taskbar buttons, no Alt-Tab entries. This dashboard is the only window you will
> ever see.

---

## overview - three live tiles, each on its own start page · 0:00 · 10s · 23 words

**On screen:** three large tiles, all showing the same quiet start page — a few
bookmarks and nothing else. Every count in the header is hidden and the button in
the corner is grey and reads "Nothing needs you". The pointer crosses a tile and
its frame and caption lift.

> Each tile is a live view of one of those windows. Not a screenshot — the real
> window, updating while it sits off-screen.

---

## one box gets a page; two get tasks with no page in them · 0:10 · 26s · 47 words

**On screen:** three tasks typed into three boxes in under three seconds. Wren
turns blue and opens a service status board. Finch and Swift go amber almost
immediately.

> One of them gets a page to read. The other two get tasks that name no page at
> all, and neither window has been anywhere yet — so rather than guess, both stop
> and ask. That is `needs input`, one of the two states worth looking for.

---

## two boxes need you, and the button says so · 0:36 · 20s · 42 words

**On screen:** the button in the corner is filled amber and reads `Go to Finch
(+1 more)`, having swelled twice as it armed. Finch is named first because the
button lists waiting boxes in fleet order, not by who asked first. The pointer
glides onto it, the detail view opens on Finch with its question in the chat, the
ticket queue's URL is typed in, Send, and the run picks up where it stopped.

> The button counts whoever is waiting, and wears their colour. It swelled twice
> when it lit and then stopped — a thing that pulses forever is a colour you learn
> to ignore. Answer in the box's own chat and it carries on.

---

## answer one, and the button is still lit for the other · 0:55 · 21s · 35 words

**On screen:** back to the overview. The button is still amber and now reads `Go
to Swift` — one waiter left. Press it again, answer it with the inventory table,
and it finishes too. The button goes quiet and grey.

> Still lit, because somebody is still waiting. It is a queue, not a
> notification: it points at the next one and it does not decide which one
> matters. Nothing here ranks, scores or reorders anything.

---

## + Add box, five times, live · 1:16 · 30s · 43 words

**On screen:** the add tile pressed five times, four seconds apart. Each press:
`launching…`, a pause, the grid reflowing, and a new box arriving already parked
and already on its start page. Three, four, five, six, seven, eight.

> The fleet is not a fixed size. Each one launches, parks itself off the desktop,
> and gets a tile, an agent process and a conversation like everything else. The
> dashboard stops answering while Chromium starts. The tiles do not — Windows
> composites those.

---

## four boxes go to work at once · 1:46 · 12s · 21 words

**On screen:** four boxes given tasks in three seconds — a deploy log, NPR, an
incident runbook, CNN. Four tiles turn blue at once while three others sit
idle.

> Four get work at once. Two on our own pages, two on the real internet, and
> nothing here knows the difference.

---

## a second wave, while the first is still going · 1:58 · 25s · 56 words

**On screen:** three more tasks as the first ones start landing — the first
website ever published, a URL that 404s, and one with no page in it, which goes
to a box added minutes ago and never used. The grid crosses through every state
it has: blue, green, amber, and one red. The counts in the header move. The jump
button lights again. Nothing moves position.

> Now nobody is driving. Eight windows, nowhere on your screen, on their own
> clocks. One was sent to a link that does not exist — it got a 404, and it says
> so rather than claiming it finished. One stopped to ask. The tile that failed
> is still exactly where it was. Nothing here reorders itself.

---

## detail view: live mirror, trajectory, chat · 2:23 · 13s · 29 words

**On screen:** into Robin — the NPR story it clicked through to, mirrored large,
with the trajectory panel and the chat beside it.

> Double-click a tile to get that box on its own. The same mirror, bigger. On
> the right, the trajectory: every page it opened, every screenshot, every link
> it clicked.

---

## stop a run mid-flight · 2:36 · 13s · 31 words

**On screen:** Egret — the one box that has had no work all film — gets its first
task. The input greys out and Stop becomes the live button. The pointer presses
it. The box drops to idle and the trajectory stays on screen.

> While a box is working the input is disabled: a message that vanishes is worse
> than a box you cannot type into. Stop interrupts it between steps, and the
> trajectory stays.

---

## take control: the real window, on the desktop, with the keyboard · 2:49 · 10s · 25 words

**On screen:** Take control on Kestrel, and the real Chromium window arrives in
the middle of the screen showing the incident runbook. Ctrl+F opens Chrome's own
find bar, `Degraded` is typed into it, the matches highlight down the page.
Escape closes it. The tile behind is still updating.

> The mirror cannot be clicked into. Take control brings the real window out and
> gives it the keyboard. That is Chrome's own find bar answering.

---

## look back at the dashboard and it parks itself · 2:59 · 5s · 11 words

**On screen:** focus returns to the dashboard; the browser window vanishes back
to its slot; its tile carries on as if nothing happened.

> Look back at the dashboard and it parks itself, still updating.

---

## close three; the grid comes back down · 3:04 · 16s · 35 words

**On screen:** three boxes closed one after another from their detail views.
Eight, seven, six, five — the grid reflowing each time, back to the shape it
ships with.

> Close box is the other direction, and it is final: the window, the agent
> process and the conversation go together. Nothing is written back to the config
> file, so a restart is five boxes again.

---

## same seam, different driver: Claude takes five boxes · 3:20 · 10s · 24 words

**On screen:** five notes in the console as each child is replaced; the boxes'
existing conversations still in place.

**With `--no-claude`** the beat prints as **the same five questions, with the
script still driving** instead. Use it to rehearse; do not narrate it as the real
thing.

> Everything so far ran on a script. Now five of these boxes get a Claude loop
> instead — same seam, different thing behind it.

---

## five boxes, five questions, at once · 3:30 · 16s · 33 words

**On screen:** five questions sent in under three seconds, and five tiles going
to work at the same time.

> Five questions at once. Which service is degraded and for how long. Which team
> owns the oldest unassigned P1 — that one is on two pages. And three more, on
> the real internet.

---

## watch one of them think · 3:46 · 13s · 24 words

**On screen:** Finch's detail view while it works — the trajectory filling with
tool calls nobody scripted: `goto`, `read_page`, `screenshot`, `click`, `goto`
again. The other four carry on behind it.

> It chooses what to do and in what order, and this one needs two pages to
> answer at all. No script could do that.

---

## the answers, and what they cost · 3:59 · 25–70s · 45 words

**On screen:** five answers landing in five chats, then the overview with five
boxes on `done`. The last line of each trajectory is its cost.

**Variable length.** The models decide how many turns they need. Hold the last
sentence until the cost lines appear; `demo.py` prints how each box ended.

> Five answers, from five pages that none of us read. The last line of each
> trajectory is what it cost — turns, tokens in, tokens out. Twelve turns and a
> box gives up and says so. A loop that will not converge is a bill.

**If one ends `needs input`** (a model asks something back), the beat is better,
not worse:

> That one stopped to ask a question of its own. Same state, same chat, and your
> answer goes straight back to it.

**If one ends `failed`**, say so and move on — do not cut around it:

> That one failed, and it says why. The other four never noticed.

---

## close the dashboard; every window goes with it · 4:24 · 8s · 17 words

**On screen:** the overview, then the app closing. Optionally cut to Task Manager
with no Chromium left.

> Close the dashboard and every window goes with it — every agent process, every
> conversation, every profile.

---

## Cutting it shorter

Roughly four minutes plus the model act. To get under three, drop in this order:

1. **close three** (2:53) — Add box already makes the point in both directions.
2. **look back at the dashboard and it parks itself** — fold its one line into
   the take-control beat.
3. **detail view: live mirror, trajectory, chat** — the answer-its-question beat
   has already shown the detail view; this one only dwells on it.
4. **stop a run mid-flight** — the most product you lose per second saved, so
   only if you have to.

Do not drop the second wave at 1:55 or the two model beats. The first is the only
shot that shows a fleet rather than an app; the others are the only ones that
show the seam holding when the driver changes, on questions no script could
answer.

## Things worth not saying

The app is careful about a few claims, and the narration should be too.

- The boxes are **parked**, not hidden. A hidden or minimized window is not
  composited and its tile goes blank; that is why they are off-screen instead.
- Separate browser launches keep cookies apart **in practice**. It is not a
  security boundary and is not tested as one.
- The demo agent really drives the browser, and everything it reports really
  happened — but what it *decides* is a fixed sequence. Do not call it
  intelligent, and do not imply the model act is what was running earlier.
- The box that fails got a real 404 from a real HTTP server. Do not describe it
  as a simulated failure, and do not describe the states as being set by the
  dashboard — every one of them is reported by the child that earned it.
- Pinion Ops is fictional and lives in this repository. Do not imply otherwise.
- Nothing is broadcast to the boxes — no clicks, no keystrokes, no fan-out URL
  bar. If someone asks, that is a decision, not a gap.
- The model act spends money: five tasks, once per take. Worth saying out loud to
  anyone asked to reproduce the recording.
