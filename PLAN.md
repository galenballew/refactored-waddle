# Plan: agents in the boxes

Half built now. **M1 through M5 have landed; M6 and M7 have not.** The app today is
a window manager whose chat is answered by a scripted stand-in running in its own
child process per box: you can give a box a task, answer it, stop it, and add or
close boxes while it runs. No model call, and no browser automation beyond what
the window manager already did.

The goal: each box gets its own agent, and the dashboard becomes the place you
talk to all of them. You give a box a task in chat, watch what its agent does,
answer it when it needs you, and see at a glance which of them is working,
stuck, or done. The browser windows stay parked exactly as they are — the agent
drives its box over CDP, which needs no focus and no visible window, so the
existing park/summon model survives untouched.

Mocks are expected and fine at every stage. No model call happens until M7, and
stopping at M6 with a fleet of scripted agents is a legitimate outcome.

## Decisions already made

| Decision | Choice |
| --- | --- |
| Navigation | Two views: an overview grid, and a detail view entered by double-clicking a tile, with a Back button |
| Chat | Detail view only. One transcript per box. Kept condensed so the last exchange is always visible |
| Trajectory | A separate panel beside the viewport — tool calls and pages visited — so the chat does not fill up with them |
| States | Idle / Working / Needs input / Done / Failed |
| Broadcast bar | Removed. The URL box and Send-to-all/Reload-all go away |
| Taking control | A nice-to-have, not a core path. Chat is the interface; you should never *have* to drive a box by hand |
| Agent boundary | One subprocess per box, line-delimited JSON over stdio |
| Real agent, eventually | Claude Agent SDK, driving its own box over CDP |
| Persistence | In memory only, like the browser profiles. Nothing on disk |
| Verification | Repair `verify.py` where this work breaks it, rather than growing it. Since M3 there is also `smoke.py`: browserless, one second, safe to run mid-edit |
| Sizing | Boxes launch at 1440x900, dashboard opens at 1600x1000 |
| Fleet size | Changes at runtime since M5: **+ Add box** on the overview, **Close box** in a detail view, `max_boxes` as the ceiling. `config.json` is only the starting list and is never written back |

Two of these are worth their reasoning:

**Taking control stays in the code.** `summon`/`park` are built and check [3]
proves them. Demoting the feature does not mean deleting the machinery — the
detail view gets a small "Take control" button, and only *tile-click-to-summon*
goes away. Removing working, verified code to save nothing would be a bad trade.

**The subprocess boundary arrives at M3, not M1 and not M7.** M1 and M2 fake
everything in-process, because the fastest way to settle a UI is to build the UI.
From M3 on, every milestone works against the real boundary, so M7 changes one
process's insides and nothing else. Building all the mock milestones in-process
and splitting at the end would mean rewriting the interface at the exact moment
the real agent is also new.

## Milestones

### M1 — Two-view dashboard, no agent anywhere — DONE

Overview grid, detail view, chat shell, trajectory panel, dark styling pass.
Nothing agent-shaped in the code: chat takes your message into an in-memory
transcript and nothing answers it, and the trajectory panel is empty. Full spec
below.

### M2 — The five states, faked in-process — DONE

A per-box state object, drawn as a tile treatment in the overview and a chip in
the detail header. A scripted fake on `root.after` walks a box through
Working → Needs input → Done or Failed when you send a prompt, and writes
plausible entries into the trajectory panel as it goes. The point is to settle
the visual language while changing it is still free. No process, no protocol.

Landed as `session.py` (the model the UI renders) and `fake_agent.py` (the
driver, deleted again at M3). The seam that matters is the one M3 inherited: the dashboard calls
`send(text)` and gets a change notification back, the driver takes its timer as
an injected `schedule(delay_ms, callback)` so it never imports Tk, and it never
touches `box.page`. Two extras beyond the plan, both for reachability rather than
realism: the first task on a box always stops to ask a question, and a prompt
containing "fail" fails.

### M3 — The subprocess boundary — DONE

The fake moves out into `agent_host.py`: one child process per box, speaking
line-delimited JSON over stdio. Dashboard side is spawn-at-start, non-blocking
pump, kill-on-exit, and crashed-child maps to Failed.

The pump needs its own fast timer. The existing 1s refresh tick is a layout tick
— chat polled at 1s feels underwater, and slowing the whole app down to fix that
would put real work on the Tk thread, which is the one thing the architecture
does not allow. Two timers, one cheap.

This is the milestone that makes the CLAUDE.md rule real: the dashboard never
reaches through `box.page`, because the thing that touches the page lives in
another process.

Landed as `agents.py` (spawn, send, drain), `agent_host.py` (the child) and
`pipes.py` (`PeekNamedPipe`, so a read never blocks and no reader threads are
needed — the single-threaded rule stays literally true). A force-killed dashboard
leaves nothing behind, because the child notices its pipe has gone and exits by
itself. (Its loop was a blocking read here; M4 turned it into a poll so that a
task could be interrupted.) Two extras
beyond the plan: `smoke.py` is now a committed second entry point covering the
protocol and the state machine without browsers, and `verify.py` gained check [9]
for children dying with the dashboard.

### M4 — Interaction completeness — DONE

The needs-input round trip (agent asks, you answer in the pane, agent resumes),
cancel/stop on a running task, attention routing so the overview tells you *which*
box is waiting on you rather than making you check five of them, trajectory
scrollback, and the "Take control" button if it has not already landed.

Stop is the part with teeth. A stop noticed only when the work finishes is not a
stop, so the child stopped blocking on stdin and now polls it between steps —
which is why `pipes.py` had to learn the difference between an empty pipe and a
broken one, since a broken one is the only thing that tells a child its dashboard
is gone. `cancel` joins the protocol, and the buttons became honest: input is
refused while a box is working, because the child drops it, and a message that
silently vanishes is worse than a disabled field.

Attention routing is navigation, not prioritisation: a per-state count in the
header and a button that opens whoever is waiting. Tiles never reorder and
nothing is scored — that stays on the do-not-add list.

### M5 — Growing the fleet: add a box at runtime — DONE

Landed with both decisions taken the permissive way. **Removing a box shipped in
the same milestone**, as "Close box" in the detail view rather than on the
overview, so it cannot be hit while reaching for a tile; it is final and
unconfirmed, like everything else here, and the last box refuses to go. **Nothing
is written back to `config.json`**, which keeps an added box exactly as durable as
the transcript it holds.

The `MIN_TILE` floor got the third answer rather than a scroll or a cap: a
`max_boxes` ceiling (12) stops the fleet running away, and when the grid genuinely
cannot fit the overview now says so instead of going blank. `verify.py` gained
check [9], which adds a real box and proves it owns processes and a window nobody
else has — the PID-attribution risk below, tested rather than argued about.

The original plan follows.

A **+ Add box** tile at the end of the overview grid. Pressing it launches one
more Chromium, parks it, registers its thumbnail, gives it a session and a driver
process, and reflows the grid. `config.json` stops being the only thing that
decides how many boxes exist.

It lands here because by the end of M4 a box is a complete thing — window,
session, subprocess — so "add one" has a single obvious meaning. Before M3 it
would be adding plumbing that M3 rewrites; after M6 it would mean threading a CDP
port through a code path that is already new.

Four things to get right, and they are all in the launch:

- **PID attribution is the thing most likely to break.** `BoxManager.start`
  snapshots `chrome.exe` PIDs around each launch and attributes the new ones to
  that box; CLAUDE.md already warns this holds only because launches are
  serialized. A runtime add is still serialized *if nothing else can launch while
  it runs* — so the button must disable itself for the duration and a second
  click must be dropped, not queued.
- **The launch blocks the UI for a second or two.** Playwright's sync API on the
  Tk thread, which is architectural and not being changed. The existing tiles stay
  live throughout, because DWM composites them out-of-process — only the dashboard
  itself stops responding. Put the tile into a "launching…" state and let Tk paint
  one frame before making the call, or it looks like a freeze.
- **The grid has a floor.** `tile_rects` returns nothing once tiles would fall
  below `MIN_TILE`, so past some count the overview goes blank rather than
  degrading. Whatever the answer is — a scroll, a cap, a smaller minimum — it has
  to be decided here rather than discovered by the person who adds the tenth box.
- **Naming.** Auto-name from the highest existing index rather than from the
  count, so names stay unique after a box is removed.

Two decisions to make when it is built, not now:

- **Does removing a box land in the same milestone?** It is cheap once add works —
  close the browser, unregister the thumbnail, kill the child, drop the session —
  but it is also the first way to lose a transcript, so it is a decision rather
  than a freebie.
- **Does an added box persist to `config.json`?** Default no: transcripts and
  profiles are already in-memory-only, and a restart returning to the configured
  fleet is consistent with that.

### M6 — Real perception and action, still no model

Each child connects to its own box's Chromium over CDP, takes `page.screenshot()`,
and runs a hardcoded scripted browse: real clicks, real pages, real trajectory
entries, real results in chat. Zero AI.

This is the best place to stop if the prototype turns out to be good enough as a
prototype. What you have at the end of M6 is a working multi-agent console whose
agents happen to be scripts, and the only thing missing is the part that decides
what to do next.

Unproven piece: per-box CDP. Boxes will need `--remote-debugging-port` at launch
(one port each) and the endpoint passed down to the child. Playwright-launched
Chromium supports this, but this app has never done it, and box launch is also
where PID attribution happens — the raciest thing in the codebase. Change launch
carefully.

### M7 — Swap in the model

Replace the scripted driver inside the child with a Claude Agent SDK loop: API key
handling, streaming turns into the transcript, cost. If M3 was done right, nothing
outside `agent_host.py` changes. That is the test.

## M1 in detail

### Detail view

```
┌ ← Back    box3                                   [Idle] [Take control] ┐
│ ┌──────────────────────────────┐ ┌───────────────────────────────────┐ │
│ │  live view (DWM mirror)      │ │ trajectory                        │ │
│ │  never scaled past 1440x900  │ │  · goto example.com               │ │
│ │                              │ │  · click "Pricing"                │ │
│ │                              │ │  · screenshot                     │ │
│ └──────────────────────────────┘ └───────────────────────────────────┘ │
│ ┌ chat ────────────────────────────────────────────────────────────── ┐ │
│ │ you: find the pricing page                                          │ │
│ │ [________________________________________________________] [Send]   │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

Chat spans the bottom so the last exchange is always visible without scrolling.
The trajectory sits beside the viewport, which is what keeps the chat readable
once an agent is doing twenty things per task.

The live view is a mirror, not the window: you cannot click into it. That is what
the "Take control" button is for, and why it stays even though it is not a core
path.

### Sizing, and why the viewport is capped

DWM will not reliably paint a thumbnail larger than its source window. It fails
silently and partially — the far edge simply is not drawn — which reads as a
cropped browser rather than as an error. So the detail viewport is capped at the
box's own 1440x900 and centred in whatever space is left over. Downscaling is
fine; upscaling is the bug. Check [8] exists for exactly this.

Boxes go from 900x700 to 1440x900 because the detail view wants the headroom and
pages deserve a realistic desktop viewport. Parked windows are off-screen, so the
only cost is memory.

### File by file

- **`config.json`** — `window_size` to `[1440, 900]`, `dashboard.size` to
  `[1600, 1000]`. Nothing else changes.
- **`control.py` becomes a `ui/` package** — `ui/app.py` (root window and view
  router), `ui/overview.py`, `ui/detail.py`, `ui/theme.py`. control.py is 256
  lines today and M1 alone roughly doubles it, before M2–M4 add states, attention
  cues and trajectory rendering. The architectural rule survives with its boundary
  moved: **only `ui/` touches Tkinter.**
- **`layout.py`** — keeps `tile_rects` for the overview and gains `viewport_rect`
  for the detail view's live view, with the same `max_thumb` cap. The chat and
  trajectory panels are laid out by Tk's packer instead: only rectangles a
  thumbnail goes into need to be pure geometry, because those are the ones with a
  correctness constraint worth testing. Still no Tk and no Win32 in this file.
- **`thumbs.py`** — unchanged. Handles stay registered across a view switch,
  because the destination is the same top-level window either way, and
  `place(..., visible=False)` already exists for the four thumbnails the detail
  view is not showing.
- **`boxes.py`** — `reload_all` and `_broadcast` are deleted. `navigate_all`
  survives as a **test fixture only**, with no UI: checks [6] and [8] both drive
  pages through it to flip colours, and rewriting them buys nothing.
- **`verify.py`** — check [2] (`check_broadcast`) is deleted; it proved a UI
  feature that no longer exists. Nine checks become eight. Check [5]
  (`check_tilemap`) needs its click assertion changed from "click tile *i* summons
  box *i*" to "double-click tile *i* enters box *i*".
- **`README.md` and `CLAUDE.md`** — the broadcast sections go. The "What this is
  not" lists lose the no-log-panes item, because the trajectory panel is one, and
  gain an honest note that the agent work is in progress rather than deferred.

### Done when

The app opens on a styled overview of five tiles. Double-clicking one fills the
window with that box's live view, an empty trajectory panel and a working chat
input. Back returns to the overview. Tiles stay live in both views, boxes stay
parked throughout, and the eight remaining checks pass.

## Things this plan is deliberately not doing

The out-of-scope list in CLAUDE.md and the README is being partly reversed on
purpose, and only partly. Still out, and not quietly coming back:

- No scoring, ranking, prioritising, or automatic task swapping between boxes.
- No cross-box messaging and no shared work queue. Five conversations, five
  agents, no coordination layer.
- No login handling, credential storage, containers, or remote execution.
- No charts, metrics, or progress bars. The trajectory panel is a list of what an
  agent did, not a dashboard about the dashboard.
