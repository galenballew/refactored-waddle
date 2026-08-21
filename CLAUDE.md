# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Aviary is a multibox window manager for browser sandboxes: run N headed Chromium windows at
once, see them all as live tiles in one dashboard, and open any one of them to
work on it. Python + Playwright (sync API) + PySide6 + ctypes. Windows only.

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

**Everything a person reads is capitalised**, including the state words and the
box names. `session.IDLE` is `"Idle"`, `session.USER` is `"You"`, and the birds
in `boxes.AVIARY` are `"Wren"`, `"Finch"` and so on. The state words are protocol
values shared with the child over the wire as well as labels, so they are
capitalised at the constant and never at the point of display -- both ends import
them from `session.py`, which is what makes changing one safe. Same for the
birds: the name *is* `Wren`, in the config, in the session keys, in the
screenshot path, so nothing has to remember to title-case it on the way out.

Agent text is capitalised at its source too, in `agent_host.py`, rather than by
the view. A view that capitalised the first letter of everything it drew would
also capitalise whatever the user had just typed into the chat, which is not the
view's to change.

`TRAJECTORY` stays as letter-spaced small caps -- it is a section label, not a
sentence.

The app is called **Aviary**, and the name lives in one place: `theme.NAME`. The
window title, the taskbar identity and the icon all read it from there. The
overview does not: its heading greets whoever is logged in, because the title bar
has already said the name and repeating it would spend the largest type on
screen on something you have read. Boxes are named after birds from `boxes.AVIARY` rather than numbered. The
overview's heading is a greeting rather than the app's name, because the title
bar already carries the name; `ui/text.greeting` builds it.

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

Setup: `python -m venv .venv`, then `pip install playwright PySide6` and
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
ui/           only package that touches Qt
  app.py      the window: the two views, the thumbnail handles, both timers, and
              the two triggers that send a summoned box back to its slot
  overview.py the tile grid. Double-click opens a box
  detail.py   one box: live view, trajectory panel, chat
  motion.py   the animation vocabulary: one animatable number with a callback,
              and the per-box `TileMotion` both views read. Not a timer
  theme.py    the palette, the fonts, and the stylesheet
  text.py     URL captions. `clip` takes a measuring function, not a font,
              so nothing here knows which toolkit is drawing
thumbs.py     ctypes/dwmapi: live window thumbnails
winfocus.py   ctypes/user32: match windows to PIDs, force foreground, move
              windows, and drop them from the taskbar and Alt-Tab
layout.py     pure geometry — grid rects, the detail viewport, hit testing,
              park/summon/cascade rects. No Qt, no Win32. `columns="auto"` picks
              the count that maximises tile area; in a tall narrow window that is
              usually 1, and 2 wastes two thirds of the panel.
smoke.py      the fast checks: dashboard plus agent children, no browsers
verify.py     the eleven proof checks
demo.py       the demo video: the real dashboard and real boxes, driven through
              a fixed script for the camera. Every beat goes through the same
              seam a click would, and like the checks it touches no widget
```

Panel geometry inside a view is Qt's layouts, not `layout.py`. Only rectangles a
thumbnail goes into are computed as pure geometry, because those are the ones
with a correctness constraint worth testing.

## Architectural constraints

- **One Playwright `launch()` per box.** Each box needs its own real OS window, so no
  shared page or context objects, and no multiple pages in one browser.
- **Single-threaded, and it stays that way.** Playwright's sync API and Qt's
  `exec()` both want to own the calling thread. This survives a live dashboard only
  because DWM composites the tiles out-of-process — no capture work ever runs on the UI
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
  evaluating on the UI thread once per tick per box.
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
- **Animation is not a third timer, and must not become one.** `ui/motion.py`
  runs on Qt's own animation clock, only while something is moving, and every
  redraw it asks for goes through `App.request_draw`, which collapses a frame's
  worth of moved values into one `draw()` on the next turn of the event loop.
  Without that coalescing, five boxes with four animated values each ask for
  twenty redraws per frame, and a draw re-places every thumbnail. An idle fleet
  must animate nothing: `App.motion_idle()` is what says so, and `verify.py`
  waits on it before reading pixels, because a tile caught mid-fade is a real
  colour and the wrong answer.
- **Motion says "this just changed" and then stops.** Nothing loops, blinks or
  breathes. The attention swell on `needs input` and `failed` is two beats and
  done — a pulse that never stops is a colour you learn to ignore, and it would
  compete with five live browsers forever. Anything perpetual is a bug.
- **Reversing an animation asks about its destination, not its value.** A value
  one frame into a fade has not moved yet, so a guard that compares `get()`
  decides the reversal is a no-op and leaves the original running to its old
  end. That is how a tile stays lit after the pointer has left it.
  `Value.headed_for` exists for this and is what `set_hover` asks.
- **Hover lives outside the tile rect, like everything else this app paints.**
  Frame, caption and cursor. A scrim or a label across a tile is invisible —
  thumbnails composite above it — and the only way to draw there is to hide the
  live view of the box being pointed at, which is worse than having no hover
  state. `CARD_INSET` is the whole budget: a heavier frame or an outer glow runs
  into the neighbouring card.
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
  back, both in `ui/app.py`: Qt's `ActivationChange` for the user coming
  back to the dashboard, and a per-tick backstop for focus going to a third app,
  which no toolkit hears about. The backstop asks whether the foreground window's
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
- **DPI awareness must be set before Qt starts** (`thumbs.set_dpi_awareness()` in
  `main.py`), or Qt sets its own and every rectangle means something else. Dev
  machine runs at 150%.
- **Qt lays out in logical pixels; every Win32 API here speaks physical.** This is
  the sharpest edge in the codebase and it has no compiler to catch it.
  `devicePixelRatioF()` is 1.5 here. Exactly two functions convert —
  `App.thumb_rect` for `rcDestination` and `App.screen_rect` for anything that
  will be BitBlt'd or fed to `SetCursorPos` — and the views never see a ratio.
  `thumb_rect` uses `mapTo(window, ...)`, not `mapToGlobal`: the window's origin
  *is* the client origin, so there is no screen origin to get wrong when a second
  monitor sits at a negative offset.
- **`source_size()` is physical and `layout` runs in logical, so views pass
  `source_size_logical()`.** Handing `layout` the raw source size lets a tile be
  1.5x larger than the window it mirrors, which DWM paints partially and in
  silence. Check [7] only catches that on a display where the cap actually binds,
  and this machine is not one — tiles top out at 1226x654 against a 1440x770 page
  — so smoke check [15] pins the arithmetic in both directions instead.
- **The grid's spare height belongs to the captions, never to the thumbnails.**
  Aspect-locked cells cannot fill their area in both directions, so one axis is
  always slack — ~230px of it vertically at 1600x1000. It is not removable:
  bigger tiles need a different aspect or fewer columns, and fewer columns makes
  them smaller, which `_best_columns` has already established by picking the
  count it did. `label_max` spends what it needs of that slack on the caption
  strip and the rest stays a centred margin on purpose; distributing it between
  the rows would fill the panel but leave a grid gapped 66px vertically and 20px
  horizontally, which reads as a mistake. Growing a *thumbnail* out of slack
  instead is the silent-crop bug the `max_thumb` cap exists to prevent, and
  smoke check [15] pins the two against each other.
- **`show`/`hide` on the view protocol have a caller now.** They had none
  through the port, which meant `DetailView.show` never ran and opening a box
  left the keyboard nowhere — you had to click the chat input before you could
  type. `App._switch` calls both. Smoke check [7] pins it.
- **Never change a Qt window flag to raise, lower or restyle the window.** Qt
  destroys and recreates the native window when a flag changes, and every DWM
  thumbnail is registered against that HWND: they would all go blank at once, with
  nothing in any log. `App.set_topmost` goes through `winfocus.set_topmost`, which
  is a `SetWindowPos` on the handle. `showMaximized`/`showNormal` are safe — they
  are `ShowWindow`, not a flag change.
- **Ephemeral profiles.** No persistent user-data-dir, no isolation guarantees, no
  cross-box checks. Do not describe this as a security boundary.
- **The fleet changes at runtime.** `config.json` is only the starting list: "+ Add
  box" launches another one and "Close box" ends one, so nothing may hardcode or
  cache the count. Config is never written back — an added box is gone on restart,
  like the transcripts and the profiles.
- **Adds must stay serialized, and the UI is what guarantees it.** PID attribution
  credits every `chrome.exe` that appeared during a launch to the box being
  launched, so two overlapping launches would mix up two boxes' processes. A
  launch blocks the UI thread, which means clicks queue up in the OS and arrive
  the instant it finishes — hence `ADD_DEBOUNCE_S` in `ui/app.py`, which drops
  them. Removing that guard reintroduces a bug that looks like a window-management
  failure, not a click-handling one.
- **The overview grid is `len(boxes) + 1` cells.** The last one is the add tile,
  and it is part of the same grid so the layout stays one shape. Anything indexing
  tiles against boxes has to account for it — `tile_screen_rects` returns box
  tiles only, for exactly this reason.

## DWM thumbnail rules

Learned the hard way; all of these will silently produce a blank or wrong tile.

- The destination must be a **top-level** window. Qt's `winId()` on a top-level
  widget already is one, so `thumbs.top_level()` is a no-op here; it stays because
  the rule is real and the next toolkit may not be so obliging. (Tk's `winfo_id()`
  was a child, and returned `E_INVALIDARG`.)
- `rcDestination` is in the destination window's **client** coordinates, in
  **physical** pixels. `App.thumb_rect` is the only thing that builds one.
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
- `fSourceClientAreaOnly` does **not** strip browser chrome; Chromium's toolbar and
  tab strip are client area. Tiles show page pixels only because `rcSource` is
  pointed at the renderer's own child window — `winfocus.page_rect` finds
  `Chrome_RenderWidgetHostHWND` and measures it rather than assuming a chrome
  height (130px here at 150%, different with a bookmarks bar or at another zoom).
  `CROP_TO_PAGE` in `ui/app.py` turns it off.
- **A cropped source changes the aspect, and DWM stretches rather than
  letterboxes.** `source_size()` therefore reports the *cropped* region, so the
  tile aspect follows it (1.87, not 1.60). Report the whole window while cropping
  the source and every page comes out subtly squashed — which looks like a font
  problem, not a geometry one.
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
  so nothing after it may assume five. Check [10] navigates the first box away from the
  colour fixtures, so it has to come after the pixel checks. Check [11] runs last
  because it closes the dashboard to test what closing the dashboard does — it
  owns the shutdown, and `main()` must not quit the app a second time.
- Check [10] asks two independent sources where the page went: what the agent
  reported, and what the browser says when evaluated directly. An agent's own
  word about its work is not evidence.
- Checks that read pixels off tiles need the **overview** showing. Check [4] enters
  and leaves the detail view, so it puts the overview back before it returns.
- **Nothing outside `ui/` may touch a Qt widget.** Not `smoke.py`, not
  `verify.py`, not `demo.py`. They drive the app through
  `App.update/set_topmost/set_maximized/flush/schedule/focus_window` and read the
  views through the inspection methods on each — `canvas_size`, `jump_text`,
  `transcript_text`, `trajectory_text`, `hint_text`, `entry_text`, `controls`,
  `transcript_scroll`, `tile_centre`, `control_centre` — and they ask for a
  double-click as `overview.double_click(x, y)` rather than by faking an event.
  A check written against a widget's own API is a check about Qt, not about the
  dashboard, and the Tk-to-Qt port cost roughly a day precisely because that rule
  did not exist yet. `control_centre` is a lookup in a dict each view builds of
  its own controls; `demo.py` used to walk the widget tree comparing button
  labels.

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
