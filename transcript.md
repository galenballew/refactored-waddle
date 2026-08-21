# Reel narration

Voiceover for `demo.py`. The headings are the beat names the script prints to the
console as it runs, so a take can be lined up against its own log:

```bash
.venv\Scripts\python.exe demo.py
```

`storyboard.md` is what the reel is; this is what is said over it. If a beat
moves, it moves there first.

**This is a reel, not a walkthrough, and the narration is the main reason.** It
does not say what is happening on screen, because the screen is already saying
that. It says what the thing is for. A phone demo does not say "press one, press
two, press three"; it says you can call a friend. Every line below is checked
against that: if it describes a click, it is the wrong line.

**It is written to be spoken, by the person doing the demo.** First person,
contractions, full sentences, and the plainest words that will carry the idea.
Read one of these lines out loud and it should sound like somebody talking you
through what they are doing, not like a caption being read. That rules out most
of what written copy reaches for: no sentence fragments, no colons setting up a
reveal, no lists of three, and no em dashes. If a line cannot be said in one
breath without the reader working out where the emphasis goes, it is too written.

**Say the product's name.** "Aviary" lands four times: at the top, at the end of
the fan-out, at the end of the model act, and on the way out. A reel where nobody
ever says the name is an advert for a category.

Times are nominal, at `--pace 1.0`. **The whole thing runs about 2:18 to 3:08**,
and the range is the model act at the end -- three model loops decide how many
turns they need. Cut against the beat sheet `demo.py` prints when it finishes.

Read at about 150 words a minute. Each beat gives its word budget and every line
is inside it, with room left over: about 2:15 of speech across a 2:28 film, so
there is silence to sit in.

`narration.txt` is this file with everything but the spoken words taken out. It
is generated -- `narrate.py` -- so edit a line here.

Rehearse with `--no-claude`. Same reel, with the demo agent driving the last act
instead of three Claude loops, and it is the only way to run this without
spending money.

## The sites

**Real:** NPR, CNN, Wikipedia, Hacker News, the Python docs. Ordinary Chromium
windows on the ordinary internet. Nothing signs in, fills in a form, or changes
anything anywhere.

**Invented:** Pinion Ops, a fictional company's internal tools, served from
`sites/` by `demo.py` itself. Their content does not move between takes, so the
narration can name an answer out loud -- "the top story on Hacker News" is a
different story by the time the take is cut. One of their URLs answers 404 on
purpose: that is the failed tile, and it is a real HTTP response rather than a
state anybody set. Never describe Pinion as a product or a partner. It is a set
of pages in this repository.

---

## Cold open — the launch · 0:00 · ~10s · 20 words

**On screen:** a terminal, `demo.py` running, five Chromium windows appearing and
immediately leaving the screen, the dashboard opening centred.

> This is Aviary. I'm running five browsers here, and instead of them covering
> my desktop, they all sit somewhere off-screen.

---

## five live windows, one dashboard · 0:00 · 9s · 21 words

**On screen:** five large tiles, all on the same quiet start page. The pointer
drifts across the grid, lifting a frame as it passes.

> Each tile is one of those browsers, live. I can see what all five are doing
> without opening a single window.

---

## one more, on camera · 0:09 · 8s · 18 words

**On screen:** the pointer travels to the add tile and presses it. A window
launches, parks itself, and the grid reflows to six.

> If I need another one, I just add it. That's a whole new browser with its own
> agent.

---

## six tasks, three seconds · 0:16 · 38s · 90 words

**On screen:** six boxes given work inside three seconds, then thirty seconds of
the grid diverging on its own — tiles going blue, then green, one going red, one
going amber. The counts move in the header. The pointer wanders the grid.
Nothing changes position.

> This is what I use it for. I'm giving all six of them something to do
> at once, then leaving them alone.
>
> They're all working in parallel now. When one of them finishes, it tells me.
> This one hit a link that doesn't exist, so it stopped and said so instead of
> pretending it worked. And this one didn't have enough to go on, so it's asking
> me a question.
>
> That's the whole point of Aviary. I hand out the work, and they only come back
> when they need me.

---

## the one that needs you, and answering it · 0:54 · 22s · 52 words

**On screen:** the amber button in the corner is pressed; the detail view opens
on the box that asked; a URL is typed into its chat a character at a time and
sent; the run picks up where it stopped.

> That amber button means one of them is waiting on me. I click it and I'm
> straight into that box's conversation. I answer it the way I'd answer a person,
> and it picks up where it left off. Every box keeps its own thread, so nothing I
> say here goes anywhere else.

---

## take control: the real window, with the keyboard · 1:16 · 10s · 20 words

**On screen:** Take control, and the real Chromium window arrives on the desktop.
Ctrl+F opens Chrome's own find bar, `Degraded` is typed into it, matches
highlight. Escape, and the window goes back to its slot.

> Sometimes I need the page myself. I take the window, do what I need to do, and
> hand it back.

---

## same seam, different driver · 1:26 · 1s · no line

**On screen:** three notes in the console as each child is replaced. One second
long — nothing to say over it; the line below covers both beats.

**With `--no-claude`** the beat prints as **the same three questions, with the
script still driving**. Use it to rehearse; do not narrate it as the real thing.

---

## three questions no script could answer · 1:27 · 55s · 88 words

**On screen:** three questions sent at once; three tiles going to work; then one
box up close, its trajectory filling with tool calls nobody scripted. The answers
land in three chats, and the last line of each trajectory is what it cost.

**Variable length.** The models decide how many turns they need. Hold the last
sentence until the cost lines appear.

> Everything I've shown you so far was running on a script. Now Claude is driving
> three of these instead.
>
> I'm asking them things a script could never work out. One is finding which
> ticket has been open the longest. Another is reading up on two kinds of
> hypervisor. They read the pages and decide what to do next on their own, and
> when they're done they tell me what it cost.
>
> And the way I work with them hasn't changed at all. That's what I wanted from
> Aviary.

---

## close the dashboard; every window goes with it · ~2:22 · ~6s · 13 words

**On screen:** back to the grid, then the app closing.

> When I close Aviary, all of it goes with it. Nothing's left running.

---

## If it needs to be shorter still

Drop in this order. The reel is already cut to the bone, so each of these costs
something real:

1. **one more, on camera** (0:08) — seven seconds, and the only thing that says
   the fleet is elastic.
2. **take control** (1:14) — ten seconds, and the only thing that says you are
   not stuck behind a mirror.

Do not drop the fan-out at 0:14 or the model act. The first is the only shot that
shows a fleet rather than an app; the second is the only one that shows the seam
holding when the driver changes.

## Things worth not saying

- **Do not narrate the mechanics.** "Click the button in the corner" is what the
  picture is already doing. Say what it is for.
- The windows are **parked**, not hidden. A hidden or minimized window is not
  composited and its tile goes blank; that is why they are off-screen instead.
- Separate browser launches keep cookies apart **in practice**. It is not a
  security boundary and is not tested as one.
- The demo agent really drives the browser, and everything it reports really
  happened — but what it *decides* is a fixed sequence. Do not call it
  intelligent, and do not imply the model act was running earlier.
- The box that fails got a real 404 from a real HTTP server. Do not describe it
  as simulated, and do not describe the states as being set by the dashboard —
  every one is reported by the child that earned it.
- Nothing is broadcast to the boxes — no clicks, no keystrokes, no fan-out URL
  bar. If someone asks, that is a decision, not a gap.
- The model act spends money: three tasks, once per take.
