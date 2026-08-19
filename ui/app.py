"""The dashboard window: two views, one set of live thumbnails, one refresh tick.

It is still the only window the user ever sees. The boxes are parked off the
desktop; this file owns the two triggers that send a summoned one back, and the
thumbnail handles that make the parked ones visible.

Views come and go, thumbnails do not. A DWM thumbnail is registered against a
top-level window, and both views live inside the same top-level, so switching
between them only moves the thumbnails -- nothing is re-registered, and no tile
ever goes blank on a view change. Handles therefore belong here rather than to
either view.

Nothing in here captures pixels: the compositor draws the tiles out-of-process,
which is the whole reason this stays single-threaded.
"""

import tkinter as tk

import layout
import thumbs
import winfocus
from fake_agent import FakeAgent
from session import Session

from . import theme
from .detail import DetailView
from .overview import OverviewView

DEFAULT_ASPECT = 4 / 3


class App:
    def __init__(self, manager):
        self.manager = manager
        self.config = manager.config
        self.dash = self.config.get("dashboard", {})
        self.handles = {}
        self.dest = None
        self.box = None  # the box being looked at, or None on the overview
        self.sessions = {box.name: Session(box.name) for box in manager.boxes}
        # One driver per box. A stand-in today; a subprocess later, reached
        # through the same two calls (send, and a change notification back).
        self.agents = {
            name: FakeAgent(session, self._schedule, self._session_changed)
            for name, session in self.sessions.items()
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

    def _schedule(self, delay_ms, callback):
        """The driver's timer. Tk's `after`, kept behind a call so that nothing
        outside this package has to know that."""
        self.root.after(delay_ms, callback)

    def _session_changed(self):
        """A box said or did something. Redraw now rather than waiting for the
        next tick -- a second's lag between pressing Send and anything happening
        reads as a broken app."""
        if self.view is not None:
            self.view.sync()

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
        for handle in self.handles.values():
            thumbs.unregister(handle)
        self.handles.clear()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
