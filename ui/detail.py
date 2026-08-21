"""One box, up close: a live view of it, its chat, and what it has been doing.

The chat is where the work happens. What answers is `agent_host.py`, one child
process per box, reached over a pipe: it drives that box's browser over CDP, so
the states are real, the transitions are real, and so is everything they
describe.

The view decides none of it. It sends what was typed and redraws what the session
says; the driver is a subprocess on the far side of that seam, and this view
knows nothing about what it does.

The trajectory panel is separate from the chat on purpose. An agent's tool calls
and page visits belong somewhere you can ignore, so that the chat stays short
enough to show the last thing you said without scrolling.

The live view is a mirror, not the window -- DWM composites it, so you cannot
click into it. "Take control" summons the real window for that, and is meant to
be a rare thing to need. The chat and trajectory panels must not overlap it: a
thumbnail composites above the whole window, not merely above the widget it was
placed over, so an overlapping panel would simply be invisible.

Qt needs no wheel-routing hack here. Tk delivers the wheel to the focused
widget, which is the input box while you are typing, so scrolling back through a
trajectory did nothing without a global binding; Qt sends it to the widget under
the pointer.
"""

from collections import namedtuple
from html import escape

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
    QWidget,
)

import layout
import session as session_model

from . import theme
from .text import short_url

# What the three chat controls are doing: "normal" or "disabled" each. A child
# drops input while it is working, and this is how the checks read whether the
# view is telling the truth about that. The words are Tk's, kept deliberately:
# the checks are about the dashboard's behaviour, and renaming them would be
# churn dressed up as a port.
Controls = namedtuple("Controls", "send stop input")
NORMAL, DISABLED = "normal", "disabled"

PAD = 14
TRAJECTORY_MIN_W = 300
TRAJECTORY_MAX_W = 460
CHAT_LINES = 5
EMPTY_CHAT = ("No task yet. Whatever you send goes to this box's agent — a "
              "separate process, driving the browser in the live view.")
EMPTY_TRAJECTORY = "No activity yet"


class ViewportCanvas(QWidget):
    """The live view's area. Owns no state -- it asks the view what to draw."""

    def __init__(self, view):
        super().__init__()
        self._view = view

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        self._view.paint(painter)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._view.relayout()


class DetailView:
    def __init__(self, app):
        self.app = app
        self.box = None
        self.viewport = layout.Rect(0, 0, 0, 0)
        self._empty = False
        self.font = app.fonts["body"]
        self.small = app.fonts["small"]

        self.frame = QWidget()
        outer = QVBoxLayout(self.frame)
        outer.setContentsMargins(PAD, PAD, PAD, PAD)
        outer.setSpacing(6)

        outer.addLayout(self._build_header())
        outer.addLayout(self._build_middle(), 1)
        outer.addWidget(self._build_chat())

        # Named so a director can point at one without walking the widget tree
        # comparing labels. The view knows what its own controls are called.
        self._controls = {
            "back": self.back_button, "close box": self.close_button,
            "take control": self.control_button, "input": self.entry,
            "send": self.send_button, "stop": self.stop_button,
        }

    # -- construction -------------------------------------------------------

    def _build_header(self):
        header = QHBoxLayout()
        self.back_button = QPushButton("←  Back")
        self.back_button.setObjectName("compact")
        self.back_button.clicked.connect(self.app.show_overview)
        header.addWidget(self.back_button)

        self.title = QLabel("")
        self.title.setObjectName("head")
        header.addSpacing(12)
        header.addWidget(self.title)

        self.url = QLabel("")
        self.url.setObjectName("muted")
        header.addSpacing(8)
        header.addWidget(self.url)
        header.addStretch(1)

        # The same state word the tile shows, so the two views teach one
        # vocabulary rather than two.
        self.chip = QLabel("")
        self.chip.setFont(self.font)
        header.addWidget(self.chip)
        header.addSpacing(14)

        self.note = QLabel("")
        self.note.setObjectName("muted")
        header.addWidget(self.note)
        header.addSpacing(10)

        self.close_button = QPushButton("Close box")
        self.close_button.setObjectName("compact")
        self.close_button.clicked.connect(self.close_box)
        header.addWidget(self.close_button)
        header.addSpacing(8)

        self.control_button = QPushButton("Take control")
        self.control_button.setObjectName("compact")
        self.control_button.clicked.connect(self.take_control)
        header.addWidget(self.control_button)
        return header

    def _build_middle(self):
        middle = QHBoxLayout()
        middle.setSpacing(PAD)

        self.canvas = ViewportCanvas(self)
        middle.addWidget(self.canvas, 5)

        panel = QFrame()
        panel.setObjectName("panel")
        # Proportional between bounds rather than one fixed width. The mirror
        # beside it is aspect-locked and letterboxed inside whatever it is given,
        # so on a wide display a fixed 340px panel does not take space from the
        # live view -- it leaves it as background either side of it. Below the
        # minimum a trajectory line is all ellipsis; above the maximum the panel
        # is mostly empty and reading across to it becomes a head movement.
        panel.setMinimumWidth(TRAJECTORY_MIN_W)
        panel.setMaximumWidth(TRAJECTORY_MAX_W)
        column = QVBoxLayout(panel)
        column.setContentsMargins(10, 10, 10, 10)
        column.setSpacing(4)
        heading = QLabel("TRAJECTORY")
        heading.setObjectName("section")
        column.addWidget(heading)
        self.trajectory = self._text(self.small)
        column.addWidget(self.trajectory, 1)
        middle.addWidget(panel, 2)
        return middle

    def _build_chat(self):
        chat = QFrame()
        chat.setObjectName("panel")
        column = QVBoxLayout(chat)
        column.setContentsMargins(10, 10, 10, 10)
        column.setSpacing(4)

        self.transcript = self._text(self.font)
        metrics = QFontMetrics(self.font)
        self.transcript.setFixedHeight(metrics.lineSpacing() * CHAT_LINES + 12)
        column.addWidget(self.transcript)

        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        column.addWidget(self.hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.entry = QLineEdit()
        self.entry.setFont(self.font)
        self.entry.returnPressed.connect(self.send)
        row.addWidget(self.entry, 1)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(self.send)
        row.addWidget(self.send_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop)
        row.addWidget(self.stop_button)
        column.addLayout(row)
        return chat

    def _text(self, font):
        """A read-only text panel. Qt gives it a scrollbar when it needs one."""
        widget = QTextEdit()
        widget.setReadOnly(True)
        widget.setFont(font)
        widget.setFrameShape(QFrame.NoFrame)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return widget

    # -- scrolling ----------------------------------------------------------

    @staticmethod
    def _fractions(widget):
        """(first, last) as fractions of the content height -- Tk's yview units.

        Qt counts in scroll steps rather than fractions, and the full range is
        the maximum plus one page: at the bottom, value is maximum and the page
        below it is the rest.
        """
        bar = widget.verticalScrollBar()
        span = bar.maximum() + bar.pageStep()
        if span <= 0:
            return (0.0, 1.0)
        return (bar.value() / span, (bar.value() + bar.pageStep()) / span)

    def _rewrite(self, widget, html):
        """Re-render a panel without stealing the reader's place in it.

        Everything is redrawn from the session on every change, which would
        otherwise yank the view back to the bottom fifty times a second while
        someone is reading back through a trajectory. Follow the end only if
        they were already at the end.
        """
        bar = widget.verticalScrollBar()
        at_end = self._fractions(widget)[1] >= 0.999
        value = bar.value()
        widget.setHtml(html)
        if at_end:
            bar.setValue(bar.maximum())
        else:
            bar.setValue(min(value, bar.maximum()))

    def _session(self):
        return self.app.sessions[self.box.name] if self.box else None

    # -- view protocol ------------------------------------------------------

    def show(self):
        self.entry.setFocus()

    def hide(self):
        pass

    def bind_box(self, box):
        self.box = box
        self.title.setText(box.name)
        self.note.setText("")
        self.sync()

    def sync(self):
        """Redraw everything that follows the session: chip, controls, panels."""
        sess = self._session()
        state = sess.state if sess else session_model.IDLE
        self.chip.setText(f"● {state}")
        self.chip.setStyleSheet(
            f"color: {theme.state_colour(state)}; background: transparent;")
        # Input is refused while a box is working, because the agent would drop
        # it: better a disabled box and a reason than a message that vanishes.
        working = state == session_model.WORKING
        self.entry.setEnabled(not working)
        self.send_button.setEnabled(not working)
        self.stop_button.setEnabled(sess is not None and sess.active)
        self.hint.setText(self._hint(state))

        self._render_chat()
        self._render_trajectory()
        self.draw()

    def _hint(self, state):
        name = self.box.name if self.box else "this box"
        if state == session_model.WORKING:
            return f"{name} is working — Stop to interrupt it"
        if state == session_model.NEEDS_INPUT:
            return f"{name} is waiting on you — what you send next answers its question"
        return ""

    def relayout(self):
        # Laid out inside a margin the width of the frame, then shifted back
        # into the middle of it. Without that the mirror fills the canvas edge
        # to edge and its frame -- which has to sit outside the thumbnail, or be
        # composited over -- is clipped away on three sides.
        inset = theme.CARD_INSET
        rect = layout.viewport_rect(
            self.canvas.width() - inset * 2,
            self.canvas.height() - inset * 2,
            aspect=self.app.aspect(),
            max_thumb=self.app.source_size_logical(),
        )
        self.viewport = layout.Rect(rect.left + inset, rect.top + inset,
                                    rect.right + inset, rect.bottom + inset)
        self.draw()

    def draw(self):
        """Put the thumbnail in the viewport, then ask for a repaint."""
        if self.box is None:
            return
        self.url.setText(short_url(self.app.url_of(self.box)))
        rect = self.app.thumb_rect(self.canvas, self.viewport)
        self._empty = not self.app.place(self.box, rect)
        self.canvas.update()

    def paint(self, painter):
        painter.fillRect(self.canvas.rect(), theme.qcolour(theme.BG))
        if self.box is None:
            return
        rect = QRectF(self.viewport.left, self.viewport.top,
                      self.viewport.right - self.viewport.left,
                      self.viewport.bottom - self.viewport.top)
        if self._empty:
            painter.setPen(QPen(theme.qcolour(theme.EMPTY_EDGE), 1))
            painter.setBrush(theme.qcolour(theme.EMPTY_BG))
            painter.drawRoundedRect(rect, theme.RADIUS, theme.RADIUS)
            painter.setFont(self.font)
            painter.setPen(theme.qcolour(theme.EMPTY_TEXT))
            painter.drawText(rect, Qt.AlignCenter, "No window")
            return
        # The same frame a tile gets, outside the mirror for the same reason: a
        # thumbnail composites above this widget, so a border on the boundary
        # would be half eaten by it. It carries the state the same way too --
        # crossfading, and swelling when the box wants you -- because you can be
        # in here watching a box work and the moment it stops to ask something
        # is the moment worth catching.
        painter.setPen(QPen(*self._frame_pen()))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(
            rect.adjusted(-theme.CARD_INSET, -theme.CARD_INSET,
                          theme.CARD_INSET, theme.CARD_INSET),
            theme.RADIUS, theme.RADIUS)

    def _frame_pen(self):
        """Colour and weight for the mirror's frame, mid-transition included.

        Idle is a plain edge here rather than the tile's brighter one: this
        frame is a single large rectangle with nothing to be told apart from,
        and at that size the same grey reads considerably louder.
        """
        mover = self.app.motion_of(self.box)
        if mover is None:
            return theme.qcolour(theme.EDGE), 1.0

        def pen_for(state):
            if state == session_model.IDLE:
                return theme.qcolour(theme.EDGE), 1.0
            return theme.state_qcolour(state), 2.0

        was_colour, was_width = pen_for(mover.previous)
        now_colour, now_width = pen_for(mover.state)
        blend = mover.blend.get()
        colour = theme.mix(was_colour, now_colour, blend)
        width = was_width + (now_width - was_width) * blend
        attention = mover.attention.get()
        if attention:
            colour = theme.mix(colour, theme.TEXT, 0.45 * attention)
            width += 1.6 * attention
        return colour, width

    # -- inspection ---------------------------------------------------------
    #
    # The checks read the view through these rather than through widget APIs.
    # `viewport` needs no accessor: it is already a layout.Rect and owes nothing
    # to the toolkit.

    def transcript_text(self):
        return self.transcript.toPlainText()

    def trajectory_text(self):
        return self.trajectory.toPlainText()

    def entry_text(self):
        """What is currently typed but not yet sent."""
        return self.entry.text()

    def hint_text(self):
        return self.hint.text()

    def transcript_scroll(self):
        """Where the transcript is scrolled, as (first, last) fractions."""
        return self._fractions(self.transcript)

    def scroll_transcript_to(self, fraction):
        bar = self.transcript.verticalScrollBar()
        bar.setValue(round(fraction * bar.maximum()))

    def controls(self):
        """Whether send, stop and the input are each enabled right now."""
        return Controls(
            NORMAL if self.send_button.isEnabled() else DISABLED,
            NORMAL if self.stop_button.isEnabled() else DISABLED,
            NORMAL if self.entry.isEnabled() else DISABLED,
        )

    def control_centre(self, name):
        """Screen centre of one named control, for the demo's pointer."""
        widget = self._controls.get(name)
        return self.app.centre_of(widget) if widget is not None else None

    def focused_control(self):
        """Which named control the keyboard would land in, or None.

        `focusWidget()` rather than `hasFocus()` on purpose: the checks run
        against a window that is not necessarily the active one, and a widget
        that is this view's focus while the window is inactive still answers the
        question being asked -- where does typing go when you come back.
        """
        focused = self.frame.focusWidget()
        for name, widget in self._controls.items():
            if widget is focused:
                return name
        return None

    def type_char(self, char):
        """Append one character to the chat box, as a keystroke would.

        The input is disabled while a box is working, and the demo types during
        exactly that -- so it is enabled first. Cosmetic: `send()` is still what
        actually delivers the message.
        """
        self.entry.setEnabled(True)
        self.entry.setFocus()
        self.entry.setText(self.entry.text() + char)

    def viewport_screen_rect(self):
        """The live view in physical screen pixels, for verify.py."""
        return self.app.screen_rect(self.canvas, self.viewport)

    # -- chat ---------------------------------------------------------------

    def send(self):
        if self.box is None:
            return
        text = self.entry.text()
        if not text.strip():
            return
        self.entry.clear()
        # What this means -- a new task, or an answer to a question -- is the
        # driver's decision, not the view's.
        self.app.send(self.box, text)
        self.sync()

    def stop(self):
        """Interrupt whatever the box is doing. Its trajectory stays: it is a
        record of what happened, not of what was going to happen."""
        if self.box is None:
            return
        self.app.cancel(self.box)
        self.sync()

    def _render_chat(self):
        sess = self._session()
        if sess is None or not sess.turns:
            html = self._muted(EMPTY_CHAT)
        else:
            lines = []
            for turn in sess.turns:
                colour = (theme.ACCENT if turn.speaker == session_model.USER
                          else theme.AGENT)
                lines.append(
                    f'<span style="color:{colour}">{escape(turn.speaker)}</span>'
                    f'&nbsp;&nbsp;{escape(turn.text)}'
                )
            html = self._body("<br>".join(lines))
        self._rewrite(self.transcript, html)

    def _render_trajectory(self):
        sess = self._session()
        if sess is None or not sess.steps:
            html = self._muted(EMPTY_TRAJECTORY)
        else:
            html = self._body("<br>".join(
                f"·&nbsp;&nbsp;{escape(str(step))}" for step in sess.steps))
        self._rewrite(self.trajectory, html)

    @staticmethod
    def _body(inner):
        return f'<div style="color:{theme.TEXT}">{inner}</div>'

    @staticmethod
    def _muted(text):
        return f'<div style="color:{theme.MUTED}">{escape(text)}</div>'

    # -- actions ------------------------------------------------------------

    def close_box(self):
        """Shut this box down for good: its window, its agent, its conversation.

        No confirmation, because nothing else in this app asks for one -- but it
        is in here rather than on the overview, so it cannot be hit while
        reaching for a tile.
        """
        if self.box is None:
            return
        if not self.app.remove_box(self.box):
            self.note.setText("The last box stays")

    def take_control(self):
        """Put the real window on the desktop. Clicking back here parks it again.

        Not the main way to use a box, and not expected to be: it exists because
        a mirror cannot be typed into, and occasionally you need to.
        """
        if self.box is None:
            return
        if self.app.manager.summon(self.box):
            self.note.setText("Summoned — click here to send it back")
        else:
            self.note.setText("No window to summon")
