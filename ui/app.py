"""The dashboard window: two views, one set of live thumbnails, two timers.

It is still the only window the user ever sees. The boxes are parked off the
desktop; this file owns the two triggers that send a summoned one back, and the
thumbnail handles that make the parked ones visible.

Views come and go, thumbnails do not. A DWM thumbnail is registered against a
top-level window, and both views live inside the same top-level, so switching
between them only moves the thumbnails -- nothing is re-registered, and no tile
ever goes blank on a view change. Handles therefore belong here rather than to
either view.

The two timers do unrelated jobs at unrelated rates. `refresh` is the layout
tick: put wandering windows back, redraw captions, once a second. `pump` drains
the agent children, fifty times a second, because a chat that answers on a
one-second boundary reads as broken. Both are cheap, and neither blocks.

Nothing in here captures pixels, and nothing in here waits on a pipe: the
compositor draws the tiles out-of-process and `pipes.py` reads only what has
already arrived. That is what keeps a single thread enough.
"""

import time
import tkinter as tk

import layout
import thumbs
import winfocus
from agents import Agent
from session import Session

from . import theme
from .detail import DetailView
from .overview import OverviewView

DEFAULT_ASPECT = 4 / 3

# How often the children are drained. Fast enough that a reply feels immediate,
# and unrelated to the layout tick, which is slow work done rarely.
PUMP_MS = 50

# A launch blocks this thread, so clicks land in the queue and arrive the moment
# it lets go. Long enough to swallow those, short enough that adding two boxes on
# purpose still works.
ADD_DEBOUNCE_S = 0.4


class App:
    def __init__(self, manager):
        self.manager = manager
        self.config = manager.config
        self.dash = self.config.get("dashboard", {})
        self.handles = {}
        self.dest = None
        self.box = None  # the box being looked at, or None on the overview
        self.adding = False   # a launch is running on this thread right now
        self._added_at = 0.0
        self.sessions = {box.name: Session(box.name) for box in manager.boxes}
        # One child process per box. What it runs is a stand-in; that it is a
        # separate process, reached only by sending a line and draining a pipe,
        # is real and is the point.
        self.agents = {
            box.name: self._spawn(box) for box in manager.boxes
        }

        self.root = tk.Tk()
        self.root.title("multibox")
        self.fonts = theme.fonts()
        theme.apply(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        # Focus returning here means the user is done with whatever box was
        # summoned. Fires for clicks into our own widgets too, which is harmless:
        # parking an already-parked fleet is a no-op.
        self.root.bind("<FocusIn>", lambda _e: self.manager.park_summoned())

        rect = layout.centred_rect(winfocus.work_area(), self.dash.get("size", [1600, 1000]))
        self.root.geometry(
            f"{rect.right - rect.left}x{rect.bottom - rect.top}+{rect.left}+{rect.top}"
        )

        self.overview = OverviewView(self)
        self.detail = DetailView(self)
        self.view = None

        self.root.update_idletasks()
        self.root.update()
        self.register_all()
        self.show_overview()
        self.refresh()
        self._pump_loop()

    # -- views --------------------------------------------------------------

    def show_overview(self):
        self.box = None
        self._switch(self.overview)

    def enter_detail(self, box):
        self.box = box
        self.detail.bind_box(box)
        self._switch(self.detail)

    def _switch(self, view):
        if self.view is view:
            view.relayout()
            return
        if self.view is not None:
            self.view.hide()
        # The outgoing view leaves its thumbnails wherever it put them, and DWM
        # would happily keep compositing them over the new one.
        self.hide_thumbs()
        self.view = view
        view.show()
        self.root.update_idletasks()
        view.relayout()

    # -- thumbnails ---------------------------------------------------------

    def register_all(self):
        self.dest = thumbs.top_level(self.root.winfo_id())
        for box in self.manager.boxes:
            self._register(box)

    def _register(self, box):
        old = self.handles.pop(box.name, None)
        if old is not None:
            thumbs.unregister(old)
        if not box.ensure_hwnd():
            return None
        handle = thumbs.register(self.dest, box.hwnd)
        if handle is not None:
            self.handles[box.name] = handle
        return handle

    def place(self, box, rect):
        """Show one box's live window in `rect` (client coordinates of the root).

        One retry through re-registration, because a source that died and came
        back gets a new HWND and the old handle will never paint again.
        """
        handle = self.handles.get(box.name)
        if handle is not None and thumbs.place(handle, rect):
            return True
        handle = self._register(box)
        return handle is not None and thumbs.place(handle, rect)

    def hide_thumbs(self):
        for handle in self.handles.values():
            thumbs.place(handle, (0, 0, 0, 0), visible=False)

    def client_offset(self, widget):
        """Where a widget sits inside the root's client area -- rcDestination units.

        The one place the toolkit's coordinate system meets DWM's, and so the one
        place a toolkit that lays out in logical rather than physical pixels would
        have to scale. Tk needs no scaling because DPI awareness makes its units
        physical already; that is a fact about Tk, not about thumbnails.
        """
        if not self.dest:
            return (0, 0)
        origin_x, origin_y = thumbs.client_origin(self.dest)
        return widget.winfo_rootx() - origin_x, widget.winfo_rooty() - origin_y

    def source_size(self):
        """The source windows' own pixel size: both the tile aspect and the size
        past which scaling buys nothing. Boxes all launch the same size, so the
        first one that answers speaks for all of them."""
        for box in self.manager.boxes:
            handle = self.handles.get(box.name)
            if handle is not None:
                size = thumbs.source_size(handle)
                if size and size[0] and size[1]:
                    return size
        return None

    def aspect(self):
        size = self.source_size()
        return size[0] / size[1] if size else DEFAULT_ASPECT

    # -- driving the boxes --------------------------------------------------

    def _spawn(self, box):
        """One child for one box. `agent` in the config decides what runs inside
        it -- a script, or a model that costs money per task."""
        return Agent(self.sessions[box.name], getattr(box, "cdp", None),
                     self.config.get("agent", "script"))

    def send(self, box, text):
        self.agents[box.name].send(text)

    def cancel(self, box):
        self.agents[box.name].cancel()

    # -- growing and shrinking the fleet ------------------------------------

    def can_add(self):
        return len(self.manager.boxes) < self.manager.max_boxes

    def add_box(self):
        """Launch one more box and give it everything a box has.

        This blocks the UI for a second or two: Playwright's sync API runs on
        this thread and there is nowhere else to put it. The tiles stay live
        throughout, because DWM composites them out-of-process; only the
        dashboard stops answering.

        Two clicks must not become two launches when the second one was queued
        behind the first -- PID attribution only works while launches are
        serialized -- so a launch in flight refuses, and so does anything that
        arrives in the moment after one finishes.
        """
        if self.adding or not self.can_add():
            return None
        if time.monotonic() - self._added_at < ADD_DEBOUNCE_S:
            return None
        self.adding = True
        try:
            box = self.manager.add_box()
        finally:
            self.adding = False
            self._added_at = time.monotonic()
        if box is None:
            return None
        self.sessions[box.name] = Session(box.name)
        self.agents[box.name] = self._spawn(box)
        self._register(box)
        self.overview.relayout()
        return box

    def remove_box(self, box):
        """Close a box for good, and forget everything it said.

        Refuses the last one: a dashboard with no boxes is not a state worth
        having, and the app cannot get back out of it.
        """
        if len(self.manager.boxes) <= 1:
            return False
        if self.box is box:
            self.show_overview()
        agent = self.agents.pop(box.name, None)
        if agent is not None:
            agent.close()
        self.sessions.pop(box.name, None)
        handle = self.handles.pop(box.name, None)
        if handle is not None:
            thumbs.unregister(handle)
        self.manager.remove_box(box)
        self.overview.relayout()
        return True

    def url_of(self, box):
        """What to put under a tile.

        The agent's word first: it is the one driving, and this process's
        Playwright does not see navigations made from another CDP client.
        """
        session = self.sessions.get(box.name)
        if session is not None and session.url:
            return session.url
        return box.url

    def waiting(self):
        """Boxes that have stopped and asked the user something, in fleet order.

        Order, not ranking: there is no scoring here and there never will be.
        It exists so the overview can point at the next one rather than making
        you scan five tiles.
        """
        return [box for box in self.manager.boxes
                if self.sessions[box.name].wants_user]

    def state_counts(self):
        """How many boxes are in each state, for the overview's summary line."""
        counts = {}
        for session in self.sessions.values():
            counts[session.state] = counts.get(session.state, 0) + 1
        return counts

    def pump(self):
        """Drain every child into its session, and redraw if anything moved.

        Its own timer, much faster than the layout tick: chat that updates once a
        second reads as a broken app, and speeding the layout tick up to match
        would run the desktop-repair work fifty times as often for nothing.
        Draining is cheap -- a PeekNamedPipe per child, and nothing else when
        there is nothing waiting.
        """
        # Every child, every time: `any()` over a generator would stop draining
        # at the first one with news.
        moved = [agent.pump() for agent in self.agents.values()]
        if any(moved) and self.view is not None:
            self.view.sync()

    def _pump_loop(self):
        self.pump()
        self.root.after(PUMP_MS, self._pump_loop)

    # -- the tick -----------------------------------------------------------

    def _settle(self):
        """Keep the desktop honest between clicks.

        The <FocusIn> binding covers the user coming back here; this covers focus
        going somewhere that is neither the dashboard nor the summoned box, which
        Tk never hears about. Then everything else is pushed back into its slot.
        """
        box = self.manager.summoned
        if box is not None and not self.manager.holds_foreground(box):
            self.manager.park_summoned()
        self.manager.reassert_layout()

    def draw(self):
        self.view.draw()

    def tick(self):
        """One full refresh: fix the desktop, then redraw. This is what the
        refresh budget in verify.py measures."""
        self._settle()
        self.draw()

    def refresh(self):
        self.tick()
        self.root.after(self.dash.get("refresh_ms", 1000), self.refresh)

    # -- the window ---------------------------------------------------------
    #
    # Everything outside this class asks for window behaviour through these three
    # rather than reaching for `self.root`, so the checks in smoke.py and
    # verify.py are written against the dashboard and not against Tk.

    def update(self):
        """Process whatever events are already pending, once. Never blocks."""
        self.root.update()

    def set_topmost(self, on):
        """Float the dashboard above other windows, or stop.

        verify.py needs this: it BitBlts the screen to prove tiles are live, and
        without it would sample whatever window happens to be in front and read
        plausible-looking garbage.
        """
        self.root.attributes("-topmost", bool(on))
        if on:
            self.root.lift()

    def set_maximized(self, on):
        """Fill the work area, or go back.

        Check [7] resizes because DWM will not reliably paint a thumbnail larger
        than its source, and that failure is invisible at a small window size.
        """
        self.root.state("zoomed" if on else "normal")

    def quit(self):
        # Children first: they exit on their own when the pipe closes, but
        # waiting for them here is what makes "closed the dashboard" mean
        # "nothing of ours is still running".
        for agent in self.agents.values():
            agent.close()
        for handle in self.handles.values():
            thumbs.unregister(handle)
        self.handles.clear()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
