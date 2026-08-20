# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A multibox window manager for browser sandboxes: run N headed Chromium windows at
once, see them all as live tiles in one dashboard, and open any one of them to
work on it. Python + Playwright (sync API) + Tkinter + ctypes. Windows only.

The dashboard has two views: an **overview** of every box as a live tile, and a
**detail view** — double-click a tile — showing one box large, with a chat panel
and a trajectory panel beside it. Those two panels are where an agent will
eventually live. What is behind them today is `agent_host.py`, one child process
per box, driving that box's browser over CDP: it opens pages, screenshots them,
reads them and clicks links, and everything it reports really happened. Which of
those it does is decided by a fixed script by default, or by Claude when the app
is started with `--agent claude` — the only path that calls a model, and the only
one that costs money.

The dashboard is the **only window the user ever sees**. The boxes are *parked* —
positioned clear of every monitor and dropped from the taskbar and Alt-Tab — and a
box is *summoned* onto the desktop only while it holds the keyboard. The model to
have in mind is a hypervisor console: N guests running somewhere you cannot see,
and one window showing a live view of each. Parked is not hidden, and that
distinction is load-bearing: a hidden, minimized or cloaked window is not
composited, and its tile goes blank. This is about desktop citizenship, not
isolation — see the ephemeral-profiles note below.

## Commands

```bash
.venv\Scripts\python.exe main.py       # run the app (scripted agents, free)
.venv\Scripts\python.exe main.py --agent claude   # ... with Claude driving, which costs money
.venv\Scripts\python.exe smoke.py      # fast checks: no browsers, ~1s
.venv\Scripts\python.exe verify.py     # the eleven proof checks; exits non-zero on failure
```

Two entry points, no pytest. `smoke.py` builds the real dashboard against fake
boxes and spawns the real agent children, so views, the protocol and the state
machine are covered without a browser, a desktop session or stolen focus — run it
while editing. `verify.py [url]` is the one that proves the window management:
real windows, pixels read off the screen, so it is slow (~60s), needs a desktop
session, steals focus, and covers part of the screen while it runs.

Setup: `python -m venv .venv`, then `pip install playwright` and
`playwright install chromium` inside it. The system `python` on this machine is 3.9
and will not work — use the venv (3.12).

## Layout

```
config.json   box names, start URL, window layout, dashboard size
main.py       entry point: DPI awareness, launch boxes, run the dashboard
boxes.py      only file that touches Playwright — one browser+page per box
session.py    per-box state, transcript and trajectory. The model the UI renders;
              it decides nothing. In memory, dies with the process
agents.py     the dashboard's half of the agent boundary: spawn a child per box,
              send it a line, drain what comes back into the session
agent_host.py the child, one process per box. Three agents share one state
              machine: ModelAgent (a Claude tool loop — the only model call in
              the repo), BrowserAgent (the same browser, fixed script) and
              StandInAgent (no browser at all, for the fast checks)
pipes.py      ctypes/kernel32: reading a pipe without blocking, and telling an
              empty one from a broken one. Used by both ends
ui/           only package that touches Tkinter
  app.py      the window: the two views, the thumbnail handles, both timers, and
              the two triggers that send a summoned box back to its slot
  overview.py the tile grid. Double-click opens a box
  detail.py   one box: live view, trajectory panel, chat
  theme.py    the palette, and the ttk styling that makes it stick
  text.py     URL captions
thumbs.py     ctypes/dwmapi: live window thumbnails
winfocus.py   ctypes/user32: match windows to PIDs, force foreground, move
              windows, and drop them from the taskbar and Alt-Tab
layout.py     pure geometry — grid rects, the detail viewport, hit testing,
              park/summon/cascade rects. No Tk, no Win32. `columns="auto"` picks
              the count that maximises tile area; in a tall narrow window that is
              usually 1, and 2 wastes two thirds of the panel.
smoke.py      the fast checks: dashboard plus agent children, no browsers
verify.py     the eleven proof checks
```

Panel geometry inside a view is Tk's packer, not `layout.py`. Only rectangles a
thumbnail goes into are computed as pure geometry, because those are the ones
with a correctness constraint worth testing.

## Architectural constraints

- **One Playwright `launch()` per box.** Each box needs its own real OS window, so no
  shared page or context objects, and no multiple pages in one browser.
- **Single-threaded, and it stays that way.** Playwright's sync API and Tkinter's
  `mainloop` both want to own the calling thread. This survives a live dashboard only
  because DWM composites the tiles out-of-process — no capture work ever runs on the Tk
  thread. A full tick — re-assert the parked layout, then redraw — measures ~2.5ms.
  The agent children do not change this: they are separate processes, and reading
  from them never blocks. If you ever move tiles to `page.screenshot()`, or give a
  child a reader thread, that guarantee is gone and the concurrency problem comes
  back.
- **The agent is a separate process, and the seam is two calls.** `Agent.send(text)`
  writes a line to a child; `Agent.pump()` drains whatever came back into the
  session and says whether anything changed. That is the entire interface. The
  dashboard knows nothing about what the child does, and the child is never handed
  the box's page — it will reach its browser over CDP, like any other client.
  Adding a back channel around this seam is how the boundary stops being real.
- **The protocol is one JSON object per line, and both ends are dumb.** In:
  `input`, `cancel`. Out: `task`, `state`, `say`, `step`, `url`. The child owns the
  state — the dashboard mirrors it and never sets one itself. An unparseable line
  is ignored rather than fatal, because a stray print in a child should not take
  the UI down.
- **The agent reaches its box over CDP, and the dashboard hands it the endpoint.**
  Each box launches with its own `--remote-debugging-port` (`boxes.free_port`),
  and that URL is the only thing about the box a child is told. No endpoint means
  no browser, and `agent_host.py` falls back to a scripted stand-in — which is
  what `smoke.py` runs, and the only reason the fast checks need no Chromium.
- **The child must attach to the page the box already has.** Over CDP the box's
  page can turn up in any context, and `contexts[0].pages` is often empty; taking
  that blindly and falling through to `new_page()` opens a *second* window, which
  is invisible in the dashboard's mirror and quietly driven while the tile shows
  an unchanged page. `_existing_page` searches every context for exactly this
  reason.
- **`page.url` in this process does not see the agent's navigations.** Playwright
  caches it per connection, and the child is a different CDP client — so after an
  agent moves a page, the dashboard's own `box.page.url` still reads about:blank
  while `page.evaluate("location.href")` gives the truth. Captions therefore use
  `session.url`, which the child reports, not `box.page.url`. Do not "fix" this by
  evaluating on the Tk thread once per tick per box.
- **The model loop lives behind the same seam as everything else.** `ModelAgent`
  is one queued action per model turn, so cancel is noticed between turns — never
  during one, because a model call blocks that process for as long as it takes.
  It appends `response.content` unchanged (thinking blocks have to go back
  exactly as they came), answers every `tool_use` in a turn in a single user
  message (which is why `ask_user` parks the other results until the user
  replies), and stops at `MAX_TURNS`: a loop that will not converge is a bill.
- **A child drops input while it is working, and the UI must not pretend
  otherwise.** The detail view disables the input and the Send button while a box
  is working, and offers Stop instead. Do not add a queue in the child to "fix"
  this: queueing is behaviour, and inventing behaviour for a stand-in is how a
  placeholder turns into a design.
- **Nothing waits on a pipe.** `pipes.py` uses `PeekNamedPipe` to read only what
  has already arrived, so draining five children costs nothing when they are
  quiet. Do not "simplify" this into `readline()` on a reader thread: the
  single-threaded rule above is the reason this app survives a live dashboard, and
  it is worth a small ctypes module to keep it literally true.
- **A child exits when its stdin goes away.** Its loop polls rather than blocks —
  a task has to be interruptible, and a stop noticed only when the work finishes
  is not a stop — so `pipes.py` reports BROKEN as distinct from empty, and that is
  the child's only signal that the dashboard has gone. Losing it would mean
  orphaned processes after a force-kill; check [9] proves it has not been lost.
- **Two timers, deliberately.** `refresh` is the layout tick at 1s; `pump` drains
  the children at 50ms. Do not merge them: chat on a one-second boundary reads as
  broken, and running the desktop-repair work fifty times a second is waste.
- **`session.py` decides nothing.** State changes come from the driver. A view
  that sets a state itself is a bug, however convenient.
- **Nothing is broadcast any more.** The dashboard has no fan-out control at all: a
  box is driven through its own chat, one box at a time. `BoxManager.navigate_all`
  survives with no caller in the UI because `verify.py` drives pages through it to
  prove tiles are live. If broadcast ever returns it stays navigation-only — never
  clicks, keystrokes, or screen coordinates.
- **Window handles come from PID diffing.** Playwright exposes no OS window handle, so
  `BoxManager.start` snapshots `chrome.exe` PIDs around each launch and attributes the
  new ones to that box; `winfocus.top_level_window` then finds the matching HWND. If
  you change how boxes are launched, this attribution is the thing most likely to break.
  It is also inherently racy — Chromium spawns helpers asynchronously, so a late child
  of box *k* can be credited to box *k+1*. It holds today only because launches are
  serialized.
- **Focus is Win32, not Playwright.** `SetForegroundWindow` with an `AttachThreadInput`
  fallback. There is no `page.bring_to_front()` fallback any more: without an HWND we
  cannot move the window either, so activating it would only put the keyboard
  somewhere off-screen. `summon` returns False and the dashboard says so. (A late
  async activation was once blamed for an intermittent `LOST FOCUS` in verify; that
  turned out to be another app taking the foreground, not this.)
- **Exactly one box is summoned at a time, and the dashboard decides when.** Summon
  is now a secondary path: "Take control" in the detail view, for the times a
  mirror is not enough, rather than the main way to use a box. Two triggers send it
  back, both in `ui/app.py`: Tk's `<FocusIn>` for the user coming
  back to the dashboard, and a per-tick backstop for focus going to a third app,
  which Tk never hears about. The backstop asks whether the foreground window's
  **PID** is the box's, not whether its HWND is — Chromium puts `<select>` popups,
  the print dialog and download bubbles in their own top-level windows, and an HWND
  test would park the box out from under someone mid-click.
- **Parking is a position, not a visibility state.** `hide_from_shell` sets
  `WS_EX_TOOLWINDOW` on Chromium's HWND to drop the taskbar button and Alt-Tab entry,
  and `SetWindowPos` puts the window past `SM_CXVIRTUALSCREEN`. Both are edits to
  another process's window: allowed because we launched it at our own integrity
  level, but not a contract. `reassert_layout` re-applies them every tick, which is
  what makes a display change or a self-repositioning Chromium correct itself. The
  taskbar only re-reads the ex-style across a hide/show cycle, so `hide_from_shell`
  briefly hides the window — it must therefore run **before** thumbnails are
  registered.
- **Window placement uses `SetWindowPos`, not Chromium flags.** `--window-position` is
  in DIPs and would need DPI conversion; HWND coordinates are already physical pixels.
- **DPI awareness must be set before Tk is created** (`thumbs.set_dpi_awareness()` in
  `main.py`). With it on, Tk pixel units and DWM client coordinates are both physical
  pixels and no conversion is needed anywhere. Dev machine runs at 150%.
- **Ephemeral profiles.** No persistent user-data-dir, no isolation guarantees, no
  cross-box checks. Do not describe this as a security boundary.
- **The fleet changes at runtime.** `config.json` is only the starting list: "+ Add
  box" launches another one and "Close box" ends one, so nothing may hardcode or
  cache the count. Config is never written back — an added box is gone on restart,
  like the transcripts and the profiles.
- **Adds must stay serialized, and the UI is what guarantees it.** PID attribution
  credits every `chrome.exe` that appeared during a launch to the box being
  launched, so two overlapping launches would mix up two boxes' processes. A
  launch blocks the Tk thread, which means clicks queue up in the OS and arrive
  the instant it finishes — hence `ADD_DEBOUNCE_S` in `ui/app.py`, which drops
  them. Removing that guard reintroduces a bug that looks like a window-management
  failure, not a click-handling one.
- **The overview grid is `len(boxes) + 1` cells.** The last one is the add tile,
  and it is part of the same grid so the layout stays one shape. Anything indexing
  tiles against boxes has to account for it — `tile_screen_rects` returns box
  tiles only, for exactly this reason.

## DWM thumbnail rules

Learned the hard way; all of these will silently produce a blank or wrong tile.

- The destination must be a **top-level** window. Tk's `winfo_id()` is a child and
  returns `E_INVALIDARG`; use `thumbs.dest_hwnd()`, which walks to `GA_ROOT`.
- `rcDestination` is in the destination window's **client** coordinates. Offset canvas
  coordinates by `thumbs.client_offset()`.
- Thumbnails always composite **above** the destination's own content. Anything drawn
  under a tile is invisible, so labels go outside the tile rect.
- A **minimized or virtual-desktop-cloaked** source renders nothing. Occluded is fine,
  and so is **entirely off-screen** — that is what makes parked boxes work at all.
  Verified: check [5] flips every page red then blue and reads the pixels back while
  all five boxes sit past the edge of the virtual screen. Chromium does not throttle
  them there, because Playwright's default args already include
  `--disable-backgrounding-occluded-windows` and `--disable-renderer-backgrounding`.
  If tiles ever do freeze, `--disable-features=CalculateNativeWinOcclusion` is the
  next lever.
- A thumbnail **larger than its source window** is not reliably painted. It fails
  silently and partially: the first tiles come out whole and the later ones are
  missing their right or bottom edge, which reads as a cropped browser rather than
  as an error. Total area is not the constraint — five 1200x930 tiles from
  1200x930 windows are fine — only the ratio to the source. `tile_rects` therefore
  takes `max_thumb` and never scales a tile past the source's own size, and
  `viewport_rect` applies the identical cap to the detail view's single large
  mirror — one tile instead of five changes nothing about the rule. This is
  invisible in a small window and obvious maximized; check [7] exists for it.
- **A thumbnail composites above the whole destination window, not just the widget
  it was placed over.** Anything overlapping a thumbnail rect is invisible, so the
  detail view's chat and trajectory panels must not overlap the viewport.
- `fSourceClientAreaOnly` does **not** strip browser chrome; Chromium's toolbar is
  client area. Cropping to page pixels only would need `rcSource`.
- Unregister every handle on exit.

## Verification notes

- Proving a tile is live needs a **screen** DC BitBlt. `PrintWindow` on the dashboard
  will not contain thumbnails — they exist only in the compositor's visual tree.
- Chrome blocks top-frame navigation to `data:` URLs. Test pages must be `file://`.
- `verify.py` samples the middle of each tile, because the top of the tile is
  Chromium's tab strip and toolbar, not page content.
- The summon check cannot be measured while someone is using the machine — alt-tab
  and any other app taking the foreground will beat it. It retries, then reports
  `NO VERDICT` and names the interfering window instead of failing. Losing focus to
  *another box* is still a real failure. Do not "fix" a flaky focus result before
  reading which window actually took the foreground; it is usually a browser or
  Task View, not this code.
- The app is no longer always-on-top, so check [5] makes the dashboard topmost for
  the duration of its sampling and drops it again afterwards. Without that it
  BitBlts whatever window happens to be in front and reads plausible-looking garbage
  — muddy mixed RGB rather than the flat 255/0/0 a real tile gives. Do not read that
  failure as a broken thumbnail.
- Check [8] runs late on purpose: everything before it summons boxes, moves them
  around and resizes the window, so passing means the fleet went back into hiding
  by itself rather than merely starting out that way. Check [9] adds a sixth box,
  so nothing after it may assume five. Check [10] navigates box1 away from the
  colour fixtures, so it has to come after the pixel checks. Check [11] runs last
  because it closes the dashboard to test what closing the dashboard does — it
  owns the shutdown, and `main()` must not quit the app a second time.
- Check [10] asks two independent sources where the page went: what the agent
  reported, and what the browser says when evaluated directly. An agent's own
  word about its work is not evidence.
- Checks that read pixels off tiles need the **overview** showing. Check [4] enters
  and leaves the detail view, so it puts the overview back before it returns.

## What this is not — do not add

Deliberately out of scope. Do not add these even if they seem useful:

- Any scoring, ranking, prioritizing, or automatic task swapping between boxes.
- Cross-box messaging or a shared work queue. N conversations, N agents, no
  coordination layer.
- Login handling, credential storage, containers, or remote execution.
- Charts, progress bars, or metrics. The trajectory panel is a list of what one
  agent did, not a dashboard about the dashboard.

There **is** a model call now, in exactly one place: `ModelAgent` in
`agent_host.py`, reached only when the app is started with `--agent claude`. Keep
it that way. Nothing else in this repo may call a model, and the paid path stays a
command-line flag — never a config key, never a default. A dashboard that starts
spending money because someone launched it, or because a checked-in file said so,
is not a dashboard anyone should trust. `BrowserAgent`'s script is deliberately dumb
(find a URL, click the first link); if it needs to decide something, that is what
`ModelAgent` is for, not a cleverer script.

Two things to protect on the way there: DWM never returns pixels to Python, so agent
perception needs a separate `page.screenshot()` path; and the eventual shape is one
subprocess per box, so never let the dashboard reach through `box.page` directly.

## README rule

`README.md` must be updated in the same change as any behavior change. If a flag, config
key, or run command changes and the README still describes the old one, the change is
incomplete.
