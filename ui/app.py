"""The dashboard window: two views, one set of live thumbnails, two timers.

The Qt half of what `ui/app.py` does, and deliberately the same shape. What is
genuinely different is written down here rather than left to be rediscovered:

  - **Qt lays out in logical units, DWM wants physical.** Tk with DPI awareness
    on reports physical pixels, so the Tk dashboard never converts anything.
    Qt does not, and `devicePixelRatioF()` is 1.5 on a 150% display. Every
    conversion happens in `thumb_rect` and `screen_rect` and nowhere else; the
    views work in Qt's own units throughout and never see a ratio.

  - **`source_size()` is physical, and layout runs in logical.** Feeding the raw
    source size to `layout` as `max_thumb` would let a tile be dpr times larger
    than the window it mirrors, which DWM will not reliably paint -- the exact
    silently-cropped failure check [7] exists for. `source_size_logical()` is
    what the views pass.

  - **Never change a window flag to raise the window.** Qt destroys and recreates
    the native window when a flag changes, and every thumbnail is registered
    against that HWND. `set_topmost` goes through `winfocus`, which is a
    SetWindowPos on the handle and leaves it alone.

Views come and go, thumbnails do not: both views live in the same top-level, so
switching only moves the thumbnails and no tile ever goes blank on a view change.

The two timers do unrelated jobs at unrelated rates. `refresh` is the layout
tick, once a second. `pump` drains the agent children fifty times a second,
because a chat that answers on a one-second boundary reads as broken.

Animation is not a third timer. `ui/motion.py` runs on Qt's own animation clock,
only while something is actually moving, and every redraw it asks for goes
through `request_draw` -- which collapses however many values moved this frame
into a single draw on the next turn of the event loop. An idle fleet animates
nothing and therefore costs nothing.
"""

import time

from PySide6.QtCore import QEvent, QPoint, QTimer
from PySide6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QStackedLayout, QWidget,
)

import layout
import thumbs
import winfocus
from agents import Agent
from session import Session

from . import motion, theme
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

# Whether a tile shows the page or the whole browser window. On, a tile is page
# pixels only; off, it wears Chromium's tab strip and toolbar the way it always
# did. Here rather than in config.json because it is a decision about what the
# dashboard looks like, not a knob for a run.
CROP_TO_PAGE = True


class Window(QWidget):
    """The top-level window. A QWidget rather than a QMainWindow: there is no
    menu bar, status bar or dock to justify one, and a plain widget's (0, 0) is
    the Win32 client origin, which is what `rcDestination` is measured from."""

    def __init__(self, app):
        super().__init__()
        self._app = app

    def changeEvent(self, event):
        # Focus returning here means the user is done with whatever box was
        # summoned. Fires for clicks into our own widgets too, which is
        # harmless: parking an already-parked fleet is a no-op.
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._app.manager.park_summoned()
        super().changeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._app.relayout()

    def closeEvent(self, event):
        self._app.quit()
        event.accept()


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
        self._quitting = False
        self._draw_queued = False
        self.sessions = {box.name: Session(box.name) for box in manager.boxes}
        # What each box's chrome is doing right now. Owned here rather than by a
        # view because a box changes state whether or not you are looking at it,
        # and both views draw the same state vocabulary.
        self.motion = {box.name: self._new_motion(box) for box in manager.boxes}
        # One child process per box, driving that box's browser over CDP. That
        # it is a separate process, reached only by sending a line and draining
        # a pipe, is the point.
        self.agents = {box.name: self._spawn(box) for box in manager.boxes}

        # Before the first window exists, or the taskbar button keeps Python's
        # icon no matter what the window carries.
        winfocus.set_app_id(f"galenballew.{theme.NAME}")
        self.qt = QApplication.instance() or QApplication([])
        self.qt.setApplicationName(theme.NAME)
        self.qt.setWindowIcon(theme.icon())
        self.window = Window(self)
        self.window.setWindowIcon(theme.icon())
        self._update_title()
        self.fonts = theme.fonts()
        theme.apply(self.window)

        self.stack = QStackedLayout(self.window)
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.overview = OverviewView(self)
        self.detail = DetailView(self)
        self.stack.addWidget(self.overview.frame)
        self.stack.addWidget(self.detail.frame)
        # One effect per view, made once and left switched off. Creating it on
        # demand would mean building it in the same frame the fade starts, and
        # the first frame of the fade is the one that matters.
        for view in (self.overview, self.detail):
            effect = QGraphicsOpacityEffect(view.frame)
            effect.setOpacity(1.0)
            effect.setEnabled(False)
            view.frame.setGraphicsEffect(effect)
            view.fade = effect
        self.view = None

        self.window.show()
        # Physical pixels, like every other window this app places. Going through
        # the HWND rather than Qt's setGeometry keeps `config.json`'s dashboard
        # size meaning the same thing it means under Tk.
        rect = layout.centred_rect(winfocus.work_area(),
                                   self.dash.get("size", [1600, 1000]))
        winfocus.move_window(int(self.window.winId()), rect.left, rect.top,
                             rect.right - rect.left, rect.bottom - rect.top)
        self.qt.processEvents()

        self.register_all()
        self.show_overview()
        self.tick()

        self._pump_timer = QTimer(self.window)
        self._pump_timer.timeout.connect(self.pump)
        self._pump_timer.start(PUMP_MS)

        self._refresh_timer = QTimer(self.window)
        self._refresh_timer.timeout.connect(self.tick)
        self._refresh_timer.start(self.dash.get("refresh_ms", 1000))

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
        # The outgoing view leaves its thumbnails wherever it put them, and DWM
        # would happily keep compositing them over the new one.
        self.hide_thumbs()
        # Both halves of the view protocol, which until now nothing called: the
        # detail view's `show` is what puts the keyboard in the chat box, so
        # opening a box and typing worked only if you clicked the input first.
        if self.view is not None:
            self.view.hide()
        self.view = view
        self.stack.setCurrentWidget(view.frame)
        self.qt.processEvents()
        # A view change is the largest thing that happens in this app, and it
        # used to be the only one that happened instantly: the chrome cut over
        # in a single frame while the mirrors faded, so the cut was what you
        # saw. Both halves arrive together now, and over longer than a single
        # tile takes, because more of the screen is changing.
        motion.fade_widget_in(view.fade)
        for box in self._shown_by(view):
            mover = self.motion.get(box.name)
            if mover is not None:
                mover.fade_in(motion.VIEW_MS, motion.VIEW_CURVE)
        view.relayout()
        view.show()

    def _shown_by(self, view):
        """Which boxes that view is about to mirror. The detail view shows one."""
        if view is self.detail:
            return [self.box] if self.box is not None else []
        return list(self.manager.boxes)

    def relayout(self):
        if self.view is not None:
            self.view.relayout()

    # -- motion -------------------------------------------------------------

    def _new_motion(self, box):
        return motion.TileMotion(self.sessions[box.name].state, self.request_draw)

    def motion_of(self, box):
        """How this box's chrome is moving. Both views ask through this."""
        return self.motion.get(box.name)

    def request_draw(self):
        """Something moved; draw once, soon.

        Coalesced on purpose. Five boxes with four animated values each would
        otherwise ask for twenty redraws in a single frame, and a draw is not
        free -- it re-places every thumbnail. One per turn of the event loop is
        both enough and the most Qt would paint anyway.
        """
        if self._quitting or self._draw_queued:
            return
        self._draw_queued = True
        QTimer.singleShot(0, self._flush_draw)

    def _flush_draw(self):
        self._draw_queued = False
        if not self._quitting:
            self.draw()

    def _on_screen(self, box):
        """Is this box's chrome somewhere the user can see it right now?

        A swell that plays to an empty room has spent its one chance to be
        noticed, so a box whose tile is behind another box's detail view changes
        state without animating. Coming back to the overview fades the tiles in
        anyway, which is the announcement that matters.
        """
        return self.view is not self.detail or box is self.box

    def _note_states(self):
        """Start whatever motion the last pump's state changes deserve."""
        for box in self.manager.boxes:
            mover = self.motion.get(box.name)
            sess = self.sessions.get(box.name)
            if mover is not None and sess is not None:
                mover.to_state(sess.state, animate=self._on_screen(box))

    def motion_idle(self):
        """True when nothing is moving.

        `verify.py` reads pixels off tiles, and a tile caught mid-fade is a real
        colour that is nonetheless the wrong answer. This lets a check wait for
        the dashboard to be still rather than sleep a guessed number of
        milliseconds and hope.
        """
        return (not any(mover.moving for mover in self.motion.values())
                and not self.overview.attention_moving())

    # -- thumbnails ---------------------------------------------------------

    def register_all(self):
        # Qt's winId() is already the top-level handle; top_level() is a no-op
        # here rather than the GA_ROOT walk Tk needs. Asking anyway keeps the
        # rule in one place.
        self.dest = thumbs.top_level(int(self.window.winId()))
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

    def _crop(self, box):
        """The part of a box worth mirroring: the page, not the browser.

        Chromium's tab strip and toolbar are client area, so nothing DWM offers
        strips them for free -- but the renderer has its own child window, and
        `rcSource` can be pointed at it. Five tiles of pure page read as a
        dashboard; five tiles each wearing their own tab strip and URL bar read
        as five screenshots of a browser.

        Recomputed rather than cached, because it is two Win32 calls and it
        moves: a bookmarks bar appearing would otherwise crop the page in the
        wrong place until the next restart. None means show the whole window.
        """
        if not CROP_TO_PAGE:
            return None
        return winfocus.page_rect(box.hwnd)

    def place(self, box, rect):
        """Show one box's live window in `rect` -- already in client pixels.

        One retry through re-registration, because a source that died and came
        back gets a new HWND and the old handle will never paint again.

        Opacity comes from the box's own motion rather than from the caller: a
        tile fading in is a property of the box having just arrived, and every
        view that draws it should agree about how far along that is. A fully
        transparent thumbnail is hidden outright instead -- there is nothing to
        composite, and hidden says so.
        """
        crop = self._crop(box)
        mover = self.motion.get(box.name)
        level = 1.0 if mover is None else mover.opacity.get()
        opacity = max(0, min(255, round(level * 255)))
        handle = self.handles.get(box.name)
        if handle is not None and thumbs.place(handle, rect, source=crop,
                                               opacity=opacity, visible=opacity > 0):
            return True
        handle = self._register(box)
        return handle is not None and thumbs.place(
            handle, rect, source=crop, opacity=opacity, visible=opacity > 0)

    def hide_thumbs(self):
        for handle in self.handles.values():
            thumbs.place(handle, (0, 0, 0, 0), visible=False)

    def dpr(self):
        return self.window.devicePixelRatioF()

    def thumb_rect(self, widget, rect):
        """A rect in `widget`'s own coordinates -> `rcDestination` client pixels.

        The one place Qt's units meet DWM's. `mapTo(window, ...)` rather than
        `mapToGlobal` on purpose: it answers in the window's own coordinates,
        whose origin is the client origin already, so there is no screen origin
        to get wrong when a second monitor sits at a negative offset.
        """
        if not self.dest:
            return (0, 0, 0, 0)
        scale = self.dpr()
        origin = widget.mapTo(self.window, QPoint(0, 0))
        x, y = round(origin.x() * scale), round(origin.y() * scale)
        return (x + round(rect[0] * scale), y + round(rect[1] * scale),
                x + round(rect[2] * scale), y + round(rect[3] * scale))

    def screen_rect(self, widget, rect):
        """The same rect in physical SCREEN pixels, as (left, top, w, h).

        What `verify.py` BitBlts. Built from the client rect plus the client
        origin, so it inherits the multi-monitor safety above.
        """
        if not self.dest:
            return (0, 0, 0, 0)
        origin_x, origin_y = thumbs.client_origin(self.dest)
        left, top, right, bottom = self.thumb_rect(widget, rect)
        return (origin_x + left, origin_y + top, right - left, bottom - top)

    def source_size(self):
        """The size of the region a tile mirrors, in PHYSICAL pixels.

        The cropped page when cropping is on, because that -- and not the whole
        window -- is what a tile actually shows: both the tile aspect and the
        size past which scaling buys nothing follow from it. Get this wrong and
        every page comes out stretched, since DWM scales the source region to
        fill the destination rather than letterboxing it.

        Boxes all launch the same size, so the first one that answers speaks for
        all of them.
        """
        for box in self.manager.boxes:
            handle = self.handles.get(box.name)
            if handle is None:
                continue
            crop = self._crop(box)
            if crop and crop[2] - crop[0] > 0 and crop[3] - crop[1] > 0:
                return (crop[2] - crop[0], crop[3] - crop[1])
            size = thumbs.source_size(handle)
            if size and size[0] and size[1]:
                return size
        return None

    def source_size_logical(self):
        """The same size in the units the views lay out in.

        `layout`'s `max_thumb` cap compares against tile sizes, and those are
        logical here -- so handing it physical pixels would permit a tile dpr
        times larger than its source, which DWM paints only partially and
        without complaining.
        """
        size = self.source_size()
        if not size:
            return None
        scale = self.dpr()
        return (int(size[0] / scale), int(size[1] / scale))

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
        self.motion[box.name] = self._new_motion(box)
        self.motion[box.name].fade_in()
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
        self.motion.pop(box.name, None)
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

    # -- the children -------------------------------------------------------

    def pump(self):
        """Drain every child. Never blocks: `pipes.py` reads only what has
        already arrived."""
        moved = [agent.pump() for agent in self.agents.values()]
        if any(moved):
            # Before the redraw, not after: a view paints the state vocabulary
            # through the motion, so the crossfade has to have been started by
            # the time it asks what colour a frame is.
            self._note_states()
            if self.view is not None:
                self.view.sync()

    # -- the tick -----------------------------------------------------------

    def _settle(self):
        """Keep the desktop honest between clicks.

        Activation covers the user coming back here; this covers focus going
        somewhere that is neither the dashboard nor the summoned box, which no
        toolkit hears about. Then everything else is pushed back into its slot.
        """
        box = self.manager.summoned
        if box is not None and not self.manager.holds_foreground(box):
            self.manager.park_summoned()
        self.manager.reassert_layout()

    def _update_title(self):
        """What the window says it is, in the one place the app is not.

        The wordmark inside the window already gives the name, so repeating it
        in the title bar spends the only channel left when the dashboard is
        behind something or minimised. This is the whole point of the app --
        quiet until a box needs you -- said where you can see it without
        looking at the app at all.
        """
        waiting = len(self.waiting())
        # "waiting" rather than "needs you" because the count makes the second
        # one disagree with itself at one box, and a title bar is the last place
        # to be fixing up plurals.
        self.window.setWindowTitle(
            f"{theme.NAME} — {waiting} waiting" if waiting else theme.NAME)

    def draw(self):
        self._update_title()
        if self.view is not None:
            self.view.draw()

    def tick(self):
        """One full refresh: fix the desktop, then redraw. This is what the
        refresh budget in verify.py measures."""
        self._settle()
        # Cheap, and a no-op unless something actually changed: `pump` is the
        # only path a state arrives by today, and this is here so that stays a
        # fact about the protocol rather than an assumption the chrome depends
        # on to show the right colour.
        self._note_states()
        self.draw()

    # -- the window ---------------------------------------------------------
    #
    # Everything outside this class asks for window behaviour through these
    # three rather than reaching for `self.window`, so the checks in smoke.py and
    # verify.py are written against the dashboard and not against Qt.

    def update(self):
        """Process whatever events are already pending, once. Never blocks."""
        self.qt.processEvents()

    def flush(self):
        """Let pending layout and painting happen before something is measured."""
        self.qt.processEvents()

    def schedule(self, ms, function, *args):
        """Run `function` on this thread after `ms`. The director's clock."""
        QTimer.singleShot(ms, lambda: function(*args))

    def focus_window(self):
        """Take the keyboard, as clicking the dashboard would."""
        self.window.activateWindow()
        self.window.raise_()

    def holds_foreground(self):
        """Is the dashboard the window a click would land on right now?

        `demo.py` asks before every synthetic click, because a click goes
        wherever the cursor is and lands on whatever window is under it.
        """
        return winfocus.foreground_window() == int(self.window.winId())

    def foreground_name(self):
        """Whoever has the foreground, in enough detail to name them."""
        return winfocus.describe(winfocus.foreground_window())

    def take_foreground(self):
        """Put the dashboard back in front. True if Windows agreed.

        A box is a real Chromium window being driven by a real browser, and
        Chromium takes the foreground when it launches and when it is navigated.
        Parked past the edge of the virtual screen it does that *invisibly*:
        nothing on the desktop changes, the dashboard is still the only window
        anyone can see, and the keyboard and the next click quietly belong to a
        browser sitting at -30000.

        So the dashboard asks for it back rather than assuming it still has it.
        This is not stagecraft -- `SetForegroundWindow` on a window that is
        already the only one on screen changes nothing a camera can see.
        """
        hwnd = int(self.window.winId())
        winfocus.focus_window(hwnd)
        return winfocus.foreground_window() == hwnd

    def centre_of(self, widget):
        """A widget's middle in physical screen pixels, for the demo's pointer."""
        left, top, width, height = self.screen_rect(
            widget, (0, 0, widget.width(), widget.height()))
        return (left + width // 2, top + height // 2)

    def set_topmost(self, on):
        """Float the dashboard above other windows, or stop.

        Through the HWND, never through a Qt window flag: changing a flag
        recreates the native window and every thumbnail is registered against
        it. verify.py needs this at all because it BitBlts the screen, and would
        otherwise sample whatever window happens to be in front.
        """
        winfocus.set_topmost(int(self.window.winId()), on)
        if on:
            self.window.raise_()

    def set_maximized(self, on):
        """Fill the work area, or go back.

        Check [7] resizes because DWM will not reliably paint a thumbnail larger
        than its source, and that failure is invisible at a small window size.
        ShowWindow, not a flag change, so the HWND survives.
        """
        if on:
            self.window.showMaximized()
        else:
            self.window.showNormal()

    def quit(self):
        # Children first: they exit on their own when the pipe closes, but
        # waiting for them here is what makes "closed the dashboard" mean
        # "nothing of ours is still running".
        if self._quitting:
            return
        self._quitting = True
        for timer in (getattr(self, "_pump_timer", None),
                      getattr(self, "_refresh_timer", None)):
            if timer is not None:
                timer.stop()
        for agent in self.agents.values():
            agent.close()
        for handle in self.handles.values():
            thumbs.unregister(handle)
        self.handles.clear()
        self.window.close()
        self.qt.processEvents()

    def run(self):
        self.qt.exec()
