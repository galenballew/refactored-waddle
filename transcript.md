# Demo narration

Voiceover for `demo.py`. The headings are the beat names the script prints to the
console as it runs, so a take can be lined up against its own log:

```bash
.venv\Scripts\python.exe demo.py
```

Times are nominal, from a run at `--pace 1.0`. Real ones move — a cold agent
child spends a second or two starting Playwright, and the model beat takes as
long as the model takes — so cut against the beat sheet `demo.py` prints when it
finishes, not against the numbers here.

Read at about 150 words a minute. Each beat gives its word budget; every line
below is inside it, most with room to spare. Nothing here needs to be said over
the top of the action — the holds are long enough to land a sentence and then
show the thing.

Rehearse with `--no-claude`. It is the same film minus the last beat, and the
last beat is the only one that spends money.

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

## four boxes get a task inside two seconds · 0:05 · 2s · 8 words

**On screen:** four tasks typed into four boxes in under two seconds. box4 is
left alone on purpose; it is needed cold later.

> Four of them get a task at once.

---

## states diverge: working to done, and one stops to ask · 0:07 · ~10s · 60 words

**On screen:** the counts in the header moving on their own, rings going amber
then green, URLs changing under the tiles, and box5 landing on `needs input` —
which lights up the jump button.

> Nobody is driving now. The counts move on their own, pages load in windows that
> are nowhere on your screen, and the tiles stay where they are — nothing here
> reorders, ranks or scores anything. One box stops. It was not given a URL and it
> is not going to guess, so it asks. That is `needs input`, and it is one of the
> two states worth looking for.

---

## jump straight to the box that needs you · 0:17 · ~3s · 22 words

**On screen:** the pointer glides to the header button, which now reads
`go to box5 →`, and the detail view opens on box5 with its question in the chat.

> The button in the corner goes to whoever is waiting. It points at the next one;
> it does not decide which one matters.

---

## answer its question; it carries on from there · 0:20 · ~8s · 25 words

**On screen:** a URL typed into box5's chat, Send, and the run resuming — the
trajectory filling and the state going to `done`.

> Answer in its own chat, and it picks up where it stopped. Every box keeps its
> own conversation, and they are gone when the app closes.

---

## detail view: live mirror, trajectory, chat · 0:28 · ~8s · 55 words

**On screen:** back to the overview, double-click box1, hold on the full detail
view — big live mirror, trajectory panel, chat, the state chip beside the name.

> Double-click any tile to get that box on its own. The same live mirror, bigger.
> Its conversation along the bottom. And on the right, the trajectory: every page
> it opened, every screenshot it took, everything it clicked. Kept apart from the
> chat on purpose, so the chat stays short enough to read.

---

## stop a run mid-flight · 0:36 · ~11s · 55 words

**On screen:** box4 gets its first task. The input greys out and Stop becomes the
live button; the pointer moves to Stop and presses it. The box drops to `idle`
and the trajectory stays on screen.

> While a box is working the input is disabled. The agent would drop what you
> typed, and a message that vanishes is worse than a box you cannot type into. Stop
> interrupts it between steps. The trajectory stays where it is — it is a record of
> what happened, not of what was going to.

---

## take control: the real window, on the desktop, with the keyboard · 0:47 · ~9s · 45 words

**On screen:** Take control, the real Chromium window arriving on the middle of
the screen, real characters appearing in the page's text field, and the tile
behind it still updating.

> The mirror cannot be clicked into. When you need to type into a page yourself,
> Take control brings the real window out and gives it the keyboard. Only one is
> ever out at a time.

---

## look back at the dashboard and it parks itself · 0:56 · ~3s · 18 words

**On screen:** focus returns to the dashboard; the browser window vanishes back
to its slot; its tile carries on as if nothing happened.

> Look back at the dashboard and it goes straight back. Its tile never stopped
> updating.

---

## + Add box, live · 0:59 · ~13s · 50 words

**On screen:** the add tile, the `launching…` frame, the grid reflowing to six,
and box6 taking a task of its own.

> The fleet is not fixed at five. Add box starts another one: it launches, parks
> itself, and gets a tile, an agent process and a conversation like everything
> else. The dashboard stops answering while Chromium starts. The tiles do not —
> Windows composites those.

---

## close box: window, agent and conversation, gone · 1:12 · ~5s · 25 words

**On screen:** box6's detail view, Close box, the grid back to five.

> Close box is the other direction, and it is final. Nothing is written back to
> the config file, so a restart is five boxes again.

---

## same seam, different driver: Claude takes box2 · 1:17 · ~8s · 45 words

**On screen:** box2's detail view — its earlier conversation still in the chat —
and a question typed in that no fixed script could answer.

> Everything so far ran on a script: find a URL, open it, look at it, click the
> first link. Nothing called a model. This is the same box and the same interface,
> but its agent process is a Claude loop now.

---

## the model picks its own tools, and reports what it cost · 1:25 · 20–40s · 70 words

**On screen:** the trajectory filling with tool calls nobody scripted — `goto`,
`read_page`, `screenshot`, `click` — then the answer in the chat and the cost on
the last trajectory line.

**Variable length.** The model decides how many turns it needs, so hold the last
sentence until the cost line appears. `demo.py` prints how box2 ended.

> It chooses what to do: open the page, read it, look at it, click something. The
> question needs the page read and a judgement about what it says, which the script
> could not do at all. The last line of the trajectory is what it cost — turns,
> tokens in, tokens out. Twelve turns and it gives up. A loop that will not
> converge is a bill.

**If it ends `needs input` instead** (the model asks something back), the beat is
better, not worse:

> It can also stop and ask you something of its own. Same state, same chat, and
> your answer goes straight back to it.

**If it ends `failed`**, say so and move on — do not cut around it:

> That one failed, and it says why. Nothing else in the fleet noticed.

---

## close the dashboard; every window goes with it · ~1:55 · ~3s · 25 words

**On screen:** the overview, then the app closing. Optionally cut to Task Manager
with no Chromium left.

> Close the dashboard and every window goes with it, along with every agent
> process, every conversation and every profile.

---

## Cutting it shorter

Roughly two minutes as written. To get under ninety seconds, drop in this order:

1. **close box** (1:12) — add box already makes the point.
2. **look back at the dashboard and it parks itself** — fold its one line into
   the take-control beat.
3. **detail view: live mirror, trajectory, chat** — the answer-its-question beat
   has already shown the detail view; this one only dwells on it.

Do not drop the divergence beat at 0:07 or the model beat at 1:25. The first is
the only shot that shows a fleet rather than an app, and the second is the only
one that shows the seam holding when the driver changes.

## Things worth not saying

The app is careful about a few claims, and the narration should be too.

- The boxes are **parked**, not hidden. A hidden or minimized window is not
  composited and its tile goes blank; that is why they are off-screen instead.
- Separate browser launches keep cookies apart **in practice**. It is not a
  security boundary and is not tested as one.
- The scripted agent really drives the browser, but what it *decides* is a fixed
  sequence. Do not call it intelligent.
- Nothing is broadcast to the boxes — no clicks, no keystrokes, no fan-out URL
  bar. If someone asks, that is a decision, not a gap.
