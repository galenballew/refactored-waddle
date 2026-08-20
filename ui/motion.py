"""How the chrome moves, and the one rule about when it is allowed to.

A dashboard whose whole point is *quiet until something needs you* is the worst
possible place to animate everything. So motion here says exactly one thing:
**this just changed.** It runs, it finishes, and then the tile is still again.
Nothing loops, nothing breathes, and nothing moves while the fleet is idle.

Three vocabularies, and no fourth without a reason:

  - **blend** -- a state change crossfades the frame from the old colour and
    weight to the new one, instead of being a different colour next time you
    look.
  - **attention** -- the two states that actually want you, `needs input` and
    `failed`, additionally swell twice and settle. Two beats is enough to catch
    an eye that was elsewhere; a pulse that never stops is just a colour you
    learn to ignore, and it would compete with five live browsers forever.
  - **hover** and **opacity** -- an affordance, and a tile arriving.

Qt animates a *property of a QObject*, and almost nothing this app draws is a
widget: tiles are painted by hand and the live views belong to DWM. So the
animated thing here is a bare number with a callback attached, and what that
number means is entirely the caller's business. `Value` is the whole mechanism.

This is not a third timer. Qt drives these off its own animation clock, only
while something is actually moving, and the redraws they ask for are coalesced
by `App.request_draw` into at most one per event-loop turn -- so an idle
dashboard is as quiet as it was before any of this existed.
"""

from PySide6.QtCore import (
    Property, QEasingCurve, QObject, QPropertyAnimation, Signal,
)

import session

# Durations, in one place so the app moves at one speed rather than five.
HOVER_MS = 120    # an affordance should feel instant, not animated
STATE_MS = 260    # long enough to read as a change, short enough to ignore
SWELL_MS = 1100   # the whole two-beat attention swell, start to still
FADE_MS = 300     # a thumbnail arriving

# The states worth interrupting someone for. The same two `session.py` calls
# "the reason to look at the dashboard at all".
WANTS_YOU = (session.NEEDS_INPUT, session.FAILED)


class Value(QObject):
    """One number Qt can animate, and a callback for when it moves.

    Deliberately not a widget property: the things that move here are a painted
    border and a DWM thumbnail's opacity, neither of which Qt owns.
    """

    changed = Signal()

    def __init__(self, value=0.0, on_change=None):
        super().__init__()
        self._value = float(value)
        self._target = float(value)
        self._anim = QPropertyAnimation(self, b"value")
        if on_change is not None:
            self.changed.connect(on_change)

    def _get(self):
        return self._value

    def _set(self, value):
        value = float(value)
        if value != self._value:
            self._value = value
            self.changed.emit()

    value = Property(float, _get, _set, notify=changed)

    # -- driving it ---------------------------------------------------------

    def to(self, target, ms, curve=QEasingCurve.OutCubic):
        """Animate to `target`. Restarting mid-flight is fine and is the point:
        a state that changes twice quickly should not queue two crossfades."""
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setEasingCurve(curve)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(float(target))
        self._target = float(target)
        self._anim.start()

    def swell(self, ms=SWELL_MS):
        """Up, down, up, down -- then still.

        Two beats written as key values rather than as a chain of animations,
        so there is one object to stop and no half-finished sequence to reason
        about if the state changes again mid-swell.
        """
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.setStartValue(0.0)
        for at, level in ((0.22, 1.0), (0.45, 0.15), (0.68, 0.85), (1.0, 0.0)):
            self._anim.setKeyValueAt(at, level)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def jump(self, target):
        """Set it without moving. What a value does when nobody is watching --
        a tile that is off-screen, or a view that is not showing."""
        self._anim.stop()
        self._target = float(target)
        self._set(target)

    def get(self):
        return self._value

    def headed_for(self, target):
        """Is it already there, or already on its way there?

        Asked before starting anything, and it has to be about the destination
        rather than the current value: a value one frame into a fade is still
        sitting at where it started, so testing `get()` would decide a reversal
        was a no-op and leave the original animation running to its old end.
        That is how a tile stays lit after the pointer has gone.
        """
        return self._target == target if self.moving else self._value == target

    @property
    def moving(self):
        return self._anim.state() == QPropertyAnimation.Running


class TileMotion:
    """Everything one box's chrome is currently doing.

    One of these per box, owned by the app rather than by a view, because a box
    changes state whether or not you are looking at its tile -- and both views
    draw the same state vocabulary.
    """

    def __init__(self, state, on_change):
        self.state = state       # what it is now
        self.previous = state    # what it was, for as long as `blend` is < 1
        self.blend = Value(1.0, on_change)
        self.attention = Value(0.0, on_change)
        self.hover = Value(0.0, on_change)
        self.opacity = Value(1.0, on_change)

    def to_state(self, state, animate=True):
        """Notice a state change. False means nothing changed.

        `animate=False` is for a tile nobody can see -- there is no point
        crossfading a frame that is not on screen, and a swell that plays to an
        empty room has spent its one chance to be noticed.
        """
        if state == self.state:
            return False
        self.previous, self.state = self.state, state
        if not animate:
            self.blend.jump(1.0)
            self.attention.jump(0.0)
            return True
        self.blend.jump(0.0)
        self.blend.to(1.0, STATE_MS)
        if state in WANTS_YOU:
            self.attention.swell()
        elif not self.attention.headed_for(0.0):
            # Only if there is something to put down. Animating nothing to
            # nothing still counts as moving, and `motion_idle` would be lying.
            self.attention.to(0.0, STATE_MS)
        return True

    def set_hover(self, on):
        target = 1.0 if on else 0.0
        if not self.hover.headed_for(target):
            self.hover.to(target, HOVER_MS)

    def fade_in(self):
        """A tile arriving: a box just launched, or a view just opened."""
        self.opacity.jump(0.0)
        self.opacity.to(1.0, FADE_MS)

    @property
    def moving(self):
        return any(v.moving for v in
                   (self.blend, self.attention, self.hover, self.opacity))
