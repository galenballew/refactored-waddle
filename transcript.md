# Reel narration

Voiceover for `demo.py`. The headings are the beat names the script prints to the
console as it runs, so a take can be lined up against its own log:

```bash
.venv\Scripts\python.exe demo.py
```

`storyboard.md` is what the reel is; this is what is said over it. If a beat
moves, it moves there first.

**This is a reel, not a walkthrough, and the narration is the main reason.** It
does not say what is happening on screen -- the screen is already saying that.
It says what the thing is for. A phone demo does not say "press one, press two,
press three"; it says you can call a friend. Every line below is checked against
that: if it describes a click, it is the wrong line.

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

## Cold open — the launch · 0:00 · ~10s · 23 words

**On screen:** a terminal, `demo.py` running, five Chromium windows appearing and
immediately leaving the screen, the dashboard opening centred.

> Every browser agent you run needs a window of its own. Run five and your
> desktop is gone. So they go somewhere else.

---

## five live windows, one dashboard · 0:00 · 9s · 21 words

**On screen:** five large tiles, all on the same quiet start page. The pointer
drifts across the grid, lifting a frame as it passes.

> Five real Chromium windows, running off-screen. This is the only one you keep:
> somewhere to watch all of them at once.

---

## one more, on camera · 0:09 · 8s · 19 words

**On screen:** the pointer travels to the add tile and presses it. A window
launches, parks itself, and the grid reflows to six.

> Need another? Add it whenever. Each one is a full browser with its own profile
> and its own agent.

---

## six tasks, three seconds · 0:16 · 38s · 89 words

**On screen:** six boxes given work inside three seconds, then thirty seconds of
the grid diverging on its own — tiles going blue, then green, one going red, one
going amber. The counts move in the header. The pointer wanders the grid.
Nothing changes position.

> Now the part you cannot do by hand: six jobs, started at once, running in
> parallel. Nobody is driving them. They work while you do something else.
>
> When one finishes, it says so. When one hits a dead link it fails and tells you
> why, instead of reporting that it is done. And when one does not have enough to
> go on, it stops and asks rather than guessing.
>
> That is the whole idea. You hand work out, and the fleet only interrupts you
> when it actually needs you.

---

## the one that needs you, and answering it · 0:54 · 22s · 52 words

**On screen:** the amber button in the corner is pressed; the detail view opens
on the box that asked; a URL is typed into its chat a character at a time and
sent; the run picks up where it stopped.

> The corner tells you who is waiting. One click and you are in that box's own
> conversation — answer it the way you would answer a colleague, and it carries
> on from there. Every box keeps its own thread. Nothing is shared, nothing is
> broadcast, and nothing is reordered behind your back.

---

## take control: the real window, with the keyboard · 1:16 · 10s · 25 words

**On screen:** Take control, and the real Chromium window arrives on the desktop.
Ctrl+F opens Chrome's own find bar, `Degraded` is typed into it, matches
highlight. Escape, and the window goes back to its slot.

> When looking is not enough, take the window. It arrives with the keyboard, you
> do the part only you can do, and it goes back.

---

## same seam, different driver · 1:26 · 1s · no line

**On screen:** three notes in the console as each child is replaced. One second
long — nothing to say over it; the line below covers both beats.

**With `--no-claude`** the beat prints as **the same three questions, with the
script still driving**. Use it to rehearse; do not narrate it as the real thing.

---

## three questions no script could answer · 1:27 · 55s · 87 words

**On screen:** three questions sent at once; three tiles going to work; then one
box up close, its trajectory filling with tool calls nobody scripted. The answers
land in three chats, and the last line of each trajectory is what it cost.

**Variable length.** The models decide how many turns they need. Hold the last
sentence until the cost lines appear.

> Everything up to here ran on a script. Same fleet, same windows — now Claude is
> driving three of them.
>
> Real questions, on real pages. Which ticket has been sitting longest. What
> separates two kinds of hypervisor. What a method does when the file is already
> there. It reads, it looks, it clicks, it decides what to do next, and it tells
> you what that cost.
>
> That is what the dashboard is for. Whatever is behind the window, the way you
> work with it does not change.

---

## close the dashboard; every window goes with it · ~2:22 · ~6s · 13 words

**On screen:** back to the grid, then the app closing.

> Close the dashboard and all of it goes with it. Nothing left running.

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
