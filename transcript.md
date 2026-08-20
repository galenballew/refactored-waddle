# Demo narration

Voiceover for `demo.py`. The headings are the beat names the script prints to the
console as it runs, so a take can be lined up against its own log:

```bash
.venv\Scripts\python.exe demo.py
```

Times are nominal, from a run at `--pace 1.0`. Real ones move — these are real
websites over a real network, a cold agent child spends a second or two starting
Playwright, and the model act takes as long as the models take. Cut against the
beat sheet `demo.py` prints when it finishes, not against the numbers here.

Read at about 150 words a minute. Each beat gives its word budget; every line
below is inside it. Nothing needs to be said over the top of the action — the
holds are long enough to land a sentence and then show the thing.

Rehearse with `--no-claude`. It is the same film with the script driving the last
act instead of three Claude agents, and it is the only way to run this without
spending money.

## The sites, and why those sites

Eight real websites appear: NPR, CNN, the first website ever published at CERN,
example.com, the RFC editor, Wikipedia, Hacker News and the Python docs. Nothing
signs in, fills in a form, or changes anything anywhere — every box reads pages
and clicks links, which is all the agents can do.

The split between them is load-bearing, and worth knowing before anyone edits the
list. The scripted agent clicks the **first** `a[href]` on the page, and on most
modern sites that is a hidden "Skip to content" link: Playwright waits for it to
become clickable, times out, and the box ends `failed`. Wikipedia, MDN and the
Python docs all behave that way. So the boxes driven by the script get pages whose
first link is really on the page, and the harder sites are given to the model act,
which clicks by visible text and never touches a skip link. Swapping Wikipedia
into the opening fan-out will break the take.

---

## Cold open — the launch · 0:00 · ~12s · 30 words

**On screen:** a terminal, `demo.py` running, five Chromium windows appearing and
immediately leaving the screen, the dashboard opening centred. Then an Alt-Tab
that shows nothing but the dashboard, and an empty taskbar.

> Five Chromium windows just started. They are already off the desktop — no
> taskbar buttons, no Alt-Tab entries. This dashboard is the only window you will
> ever see.

---

## overview - five live tiles, nothing needs you · 0:00 · 5s · 20 words

**On screen:** the grid, all five idle, no rings, the header button greyed out.

> Each tile is a live view of one of those windows. Not a screenshot — the real
> window, updating while it sits parked off-screen.

---

## three boxes open three real websites at once · 0:05 · 2s · 15 words

**On screen:** three tasks typed into three boxes in under two seconds. box4 is
left alone on purpose; it is needed cold later.

> Three of them get a task at once. Real sites, on the real internet.

---

## states diverge: working to done, and one stops to ask · 0:07 · ~15s · 70 words

**On screen:** NPR, CNN and the first website ever published, loading in three
tiles at the same time. The NPR tile turns from a page of text into an ordinary
news homepage when the agent clicks through to the full site. Counts move in the
header, rings go amber then green, and box5 lands on `needs input`, which lights
up the jump button.

> Nobody is driving now. Three ordinary Chromium windows, three real websites,
> loading at once in windows that are nowhere on your screen. The counts move on
> their own and the tiles stay where they are — nothing here reorders, ranks or
> scores anything. Then one box stops. It was not given a URL and it is not going
> to guess, so it asks. That is `needs input`, and it is one of the two states
> worth looking for.

---

## jump straight to the box that needs you · 0:24 · ~3s · 22 words

**On screen:** the pointer glides to the header button, now reading `go to box5 →`,
and the detail view opens on box5 with its question in the chat.

> The button in the corner goes to whoever is waiting. It points at the next one;
> it does not decide which one matters.

---

## answer its question; it carries on from there · 0:27 · ~9s · 25 words

**On screen:** a URL typed into box5's chat, Send, and the run resuming — the
trajectory filling and the state going to `done`.

> Answer in its own chat, and it picks up where it stopped. Every box keeps its
> own conversation, and they are gone when the app closes.

---

## detail view: live mirror, trajectory, chat · 0:36 · ~8s · 55 words

**On screen:** back to the overview, into box1, and a hold on the full detail
view — the NPR homepage mirrored large, trajectory panel, chat, state chip.

> Double-click any tile to get that box on its own. The same live mirror, bigger.
> Its conversation along the bottom. And on the right, the trajectory: every page
> it opened, every screenshot it took, everything it clicked. Kept apart from the
> chat on purpose, so the chat stays short enough to read.

---

## stop a run mid-flight · 0:44 · ~12s · 55 words

**On screen:** box4 gets its first task. The input greys out and Stop becomes the
live button; the pointer moves to Stop and presses it. The box drops to `idle`
and the trajectory stays on screen.

> While a box is working the input is disabled. The agent would drop what you
> typed, and a message that vanishes is worse than a box you cannot type into. Stop
> interrupts it between steps. The trajectory stays where it is — it is a record of
> what happened, not of what was going to.

---

## take control: the real window, on the desktop, with the keyboard · 0:56 · ~10s · 55 words

**On screen:** Take control, and the real Chromium window arrives on the middle of
the screen. Ctrl+F opens Chrome's own find bar, `CNN` is typed into it, and the
matches highlight down the page. Escape closes it. The tile behind is still
updating.

> The mirror cannot be clicked into. When you need the page yourself, Take control
> brings the real window out and gives it the keyboard — and that is Chrome's own
> find bar answering it, on a real page. Only one window is ever out at a time.

---

## look back at the dashboard and it parks itself · 1:06 · ~3s · 18 words

**On screen:** focus returns to the dashboard; the browser window vanishes back
to its slot; its tile carries on as if nothing happened.

> Look back at the dashboard and it goes straight back. Its tile never stopped
> updating.

---

## + Add box, live · 1:09 · ~13s · 50 words

**On screen:** the add tile, the `launching…` frame, the grid reflowing to six,
and box6 opening an RFC of its own.

> The fleet is not fixed at five. Add box starts another one: it launches, parks
> itself, and gets a tile, an agent process and a conversation like everything
> else. The dashboard stops answering while Chromium starts. The tiles do not —
> Windows composites those.

---

## close box: window, agent and conversation, gone · 1:22 · ~6s · 25 words

**On screen:** box6's detail view, Close box, the grid back to five.

> Close box is the other direction, and it is final. Nothing is written back to
> the config file, so a restart is five boxes again.

---

## same seam, different driver: Claude takes three boxes · 1:28 · ~4s · 40 words

**On screen:** three notes in the console as each child is replaced; the boxes'
existing conversations still in place.

**With `--no-claude`** the beat prints as
**the same three questions, with the script still driving** instead, and the act
below shows the script getting as far as a script can. Use it to rehearse; do not
narrate it as the real thing.

> Everything so far ran on a script: find a URL, open it, look at it, click the
> first link. Nothing called a model. Now three of these boxes get a Claude loop
> instead — same interface, same seam, different thing behind it.

---

## three boxes, three real sites, three questions at once · 1:32 · ~10s · 45 words

**On screen:** three questions sent in under two seconds — Wikipedia on
hypervisors, the Hacker News front page, the Python `pathlib` docs — and three
tiles going to work at the same time.

> Three questions, three real sites, at once. Which hypervisor is which, and name
> an example of each. What is top of Hacker News right now and how many comments
> it has. Which pathlib method writes a file, and what it does if the file is
> already there.

---

## watch one of them think · 1:42 · ~11s · 45 words

**On screen:** box2's detail view while it works — the trajectory filling with
tool calls nobody scripted: `goto`, `read_page`, `screenshot`, `click`. The other
two carry on behind it.

> It chooses what to do and in what order: open the page, read it, look at it,
> click something. None of these questions is answerable by opening a URL and
> clicking the first link, which is all the script could ever do.

---

## the answers, and what they cost · 1:53 · 20–60s · 60 words

**On screen:** the three answers landing in three chats, then the overview with
three boxes on `done`. The last line of each trajectory is its cost.

**Variable length.** The models decide how many turns they need. Hold the last
sentence until the cost lines appear; `demo.py` prints how each box ended.

> Three answers, from three pages that none of us read. The last line of each
> trajectory is what it cost — turns, tokens in, tokens out. Twelve turns and a box
> gives up and says so. A loop that will not converge is a bill.

**If one ends `needs input`** (a model asks something back), the beat is better,
not worse:

> That one stopped to ask a question of its own. Same state, same chat, and your
> answer goes straight back to it.

**If one ends `failed`**, say so and move on — do not cut around it:

> That one failed, and it says why. The other two never noticed.

---

## close the dashboard; every window goes with it · ~2:45 · ~3s · 25 words

**On screen:** the overview, then the app closing. Optionally cut to Task Manager
with no Chromium left.

> Close the dashboard and every window goes with it, along with every agent
> process, every conversation and every profile.

---

## Cutting it shorter

Roughly two and three quarter minutes as written; the model act is what varies.
To get under two minutes, drop in this order:

1. **close box** (1:22) — add box already makes the point.
2. **look back at the dashboard and it parks itself** — fold its one line into
   the take-control beat.
3. **detail view: live mirror, trajectory, chat** — the answer-its-question beat
   has already shown the detail view; this one only dwells on it.
4. **watch one of them think** — the trajectory is visible again in the beat
   after it, though this is the clearest look at a model choosing its own tools.

Do not drop the divergence beat at 0:07 or the two model beats. The first is the
only shot that shows a fleet rather than an app; the others are the only ones that
show the seam holding when the driver changes, on questions no script could
answer.

## Things worth not saying

The app is careful about a few claims, and the narration should be too.

- The boxes are **parked**, not hidden. A hidden or minimized window is not
  composited and its tile goes blank; that is why they are off-screen instead.
- Separate browser launches keep cookies apart **in practice**. It is not a
  security boundary and is not tested as one.
- The scripted agent really drives the browser, but what it *decides* is a fixed
  sequence. Do not call it intelligent — and do not imply the model act is what
  was running earlier.
- Nothing is broadcast to the boxes — no clicks, no keystrokes, no fan-out URL
  bar. If someone asks, that is a decision, not a gap.
- The model act spends money: three tasks, once per take. Worth saying out loud
  to anyone asked to reproduce the recording.
