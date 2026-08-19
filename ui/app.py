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


class App:
    def __init__(self, manager):
        self.manager = manager
        self.config = manager.config
        self.dash = self.config.get("dashboard", {})
        self.handles = {}
        self.dest = None
        self.box = None  # the box being looked at, or None on the overview
        self.sessions = {box.name: Session(box.name) for box in manager.boxes}
        # One child process per box. What it runs is a stand-in; that it is a
        # separate process, reached only by sending a line and draining a pipe,
        # is real and is the point.
        self.agents = {
            name: Agent(session) for name, session in self.sessions.items()
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
        self.dest = thumbs.dest_hwnd(self.root)
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
        """Where a widget sits inside the root's client area -- rcDestination units."""
        return thumbs.client_offset(self.dest, widget) if self.dest else (0, 0)

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

    def send(self, box, text):
        self.agents[box.name].send(text)

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
