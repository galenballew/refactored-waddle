"""The overview: every box as a live tile, and a way into one of them.

Double-click enters a box's detail view. That is the only gesture here -- a
single click used to summon the real window onto the desktop, and no longer
does anything, because you are meant to work through the detail view rather than
through the browser.

Painting is split from placing on purpose. `draw()` positions the thumbnails and
works out which tiles have no window behind them; `paint()` is the only thing
that touches a QPainter, and Qt calls it when it wants a frame. Moving a
thumbnail is not a repaint and a repaint is not a thumbnail move.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

import layout
import session

from . import theme
from .text import clip, short_url

LABEL_PAD = 12   # caption strip padding, above and below the text
PAD = 14


class TileCanvas(QWidget):
    """The grid area. Owns no state -- it asks the view what to draw."""

    def __init__(self, view):
        super().__init__()
        self._view = view
        # Without this Qt only reports the pointer while a button is held, and
        # hover would only ever happen mid-drag.
        self.setMouseTracking(True)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        self._view.paint(painter)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._view.relayout()

    # Qt sends a press before a double-click, exactly as Tk sends <Button-1>
    # before <Double-Button-1>. The two handlers do not overlap: one acts only
    # on the add tile, the other only on box tiles.

    def mousePressEvent(self, event):
        point = event.position().toPoint()
        self._view.click(point.x(), point.y())

    def mouseDoubleClickEvent(self, event):
        point = event.position().toPoint()
        self._view.double_click(point.x(), point.y())

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        self._view.hover(point.x(), point.y())

    def leaveEvent(self, event):
        # The pointer can leave the canvas without ever crossing a tile edge --
        # straight off the window, or up into the header -- and no move event
        # says so. Without this the last tile stays lit for good.
        super().leaveEvent(event)
        self._view.hover(None, None)


class OverviewView:
    def __init__(self, app):
        self.app = app
        self.tiles = []
        self._empty = set()      # tile indices with no window behind them
        self._launching = False
        self._hovered = None     # tile index under the pointer, add tile included

        self.font = app.fonts["small"]
        self.body = app.fonts["body"]
        self.name_font = app.fonts["name"]
        self.metrics = QFontMetrics(self.font)
        self.name_metrics = QFontMetrics(self.name_font)
        # The strip the caption sits in, and therefore how much of each cell is
        # not thumbnail. Measured rather than guessed, so a different font size
        # does not quietly clip the captions.
        self.label_h = self.name_metrics.height() + LABEL_PAD
        # What the strip may grow to if the grid has vertical space going spare,
        # which it usually does -- see `layout.tile_rects`. Enough for a second
        # line and no more: past that the caption stops being a caption and the
        # tile it belongs to starts looking like an afterthought.
        self.label_max = self.label_h + self.metrics.height() + 4

        self.frame = QWidget()
        outer = QVBoxLayout(self.frame)
        outer.setContentsMargins(PAD, PAD, PAD, PAD)
        outer.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("multibox")
        title.setObjectName("head")
        hint = QLabel("double-click a box to open it")
        hint.setObjectName("muted")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(hint)
        header.addStretch(1)

        # One label per state rather than one string, so each count is in its own
        # colour -- the same colour as the frame on the tiles it is counting.
        # Added once, in order, and only shown or hidden after that: a Qt layout
        # skips a hidden widget's spacing too, so the states cannot drift out of
        # their fixed order the way re-packing would let them.
        counts_row = QHBoxLayout()
        counts_row.setSpacing(12)
        self.counts = {}
        for state in session.STATES:
            label = QLabel("")
            label.setFont(self.font)
            label.setStyleSheet(f"color: {theme.state_colour(state)}; background: transparent;")
            label.hide()
            self.counts[state] = label
            counts_row.addWidget(label)
        header.addLayout(counts_row)
        header.addSpacing(14)

        self.jump = QPushButton("")
        self.jump.clicked.connect(self.go_to_waiting)
        header.addWidget(self.jump)
        outer.addLayout(header)

        self.canvas = TileCanvas(self)
        outer.addWidget(self.canvas, 1)

        self._controls = {"jump": self.jump}

    # -- view protocol ------------------------------------------------------

    # Visibility is the stacked layout's job; these exist for the things a view
    # wants to do on the way in and out, and the overview wants nothing.

    def show(self):
        pass

    def hide(self):
        # Leaving by double-click means the pointer never crosses a tile edge on
        # the way out, so nothing else would ever put this tile down.
        self.hover(None, None)

    def relayout(self):
        # One cell past the fleet: the last tile is "+ Add box", laid out with
        # the others so the grid stays one shape rather than a grid plus a
        # button stuck somewhere.
        self.tiles = layout.tile_rects(
            self.canvas.width(),
            self.canvas.height(),
            len(self.app.manager.boxes) + 1,
            aspect=self.app.aspect(),
            columns=self.app.dash.get("columns", "auto"),
            gap=self.app.dash.get("gap", 10),
            label_h=self.label_h,
            # Logical, not physical: a tile is measured in the units Qt lays out
            # in, and the cap has to be in the same ones or it does not cap.
            max_thumb=self.app.source_size_logical(),
            label_max=self.label_max,
        )
        self.draw()

    def sync(self):
        """Something a box is doing changed. Same work as a redraw."""
        self.draw()

    def draw(self):
        """Put every thumbnail where its tile is, then ask for a repaint."""
        self._draw_header()
        self._empty = set()
        for tile, box in zip(self.tiles, self.app.manager.boxes):
            rect = self.app.thumb_rect(self.canvas, tile.thumb)
            if not self.app.place(box, rect):
                self._empty.add(tile.index)
        self.canvas.update()

    def _draw_header(self):
        """A count per state, and a way to reach whoever is waiting.

        Pointing at a box is navigation, not prioritising: the tiles never
        reorder, nothing is scored, and nothing moves unless you click.
        """
        counts = self.app.state_counts()
        for state in session.STATES:
            label = self.counts[state]
            if counts.get(state):
                label.setText(f"{counts[state]} {state}")
                label.show()
            else:
                label.hide()
        waiting = self.app.waiting()
        if not waiting:
            self.jump.setText("nothing needs you")
            self.jump.setEnabled(False)
            return
        extra = f"  (+{len(waiting) - 1} more)" if len(waiting) > 1 else ""
        self.jump.setText(f"go to {waiting[0].name}{extra}  →")
        self.jump.setEnabled(True)

    def go_to_waiting(self):
        waiting = self.app.waiting()
        if waiting:
            self.app.enter_detail(waiting[0])

    # -- painting -----------------------------------------------------------

    def paint(self, painter):
        painter.fillRect(self.canvas.rect(), theme.qcolour(theme.BG))
        boxes = self.app.manager.boxes
        if not self.tiles:
            self._paint_too_small(painter, len(boxes))
            return
        self._paint_add_tile(painter, self.tiles[-1])
        for tile, box in zip(self.tiles, boxes):
            mover = self.app.motion_of(box)
            self._paint_card(painter, tile, mover)
            if tile.index in self._empty:
                self._paint_empty(painter, tile)
            self._paint_caption(painter, tile, box, mover)

    def _paint_card(self, painter, tile, mover):
        """The frame a tile sits in.

        Drawn on the CELL grown by a few pixels, so every edge of it falls
        outside the thumbnail: a thumbnail composites above this widget, and a
        frame on the boundary would be half eaten. The fill only ever shows in
        the caption strip and the margin, which is the point -- it gives the
        caption a surface to sit on rather than floating on the background.

        Every tile is framed, idle included. An unframed tile has no edge of its
        own and reads as a screenshot lying on the background; the state is said
        in the border's colour and weight, and again in words underneath.

        All three of the things a frame can be doing land here, because they all
        end up as one pen: a state crossfading into another, an attention swell
        on the two states that want you, and the pointer being on this tile.
        Everything stays inside CARD_INSET -- there is nowhere else for it to go,
        since a wider frame would run into the neighbouring card and a glow
        outside the rect would be eaten by the next tile's thumbnail.
        """
        rect = self._rectf(tile.cell).adjusted(
            -theme.CARD_INSET, -theme.CARD_INSET, theme.CARD_INSET, theme.CARD_INSET)
        hover = mover.hover.get()
        painter.setBrush(theme.mix(theme.PANEL, theme.HOVER_PANEL, hover))

        colour, width = self._frame_pen(mover)
        painter.setPen(QPen(colour, width))
        painter.drawRoundedRect(rect, theme.RADIUS, theme.RADIUS)

    @staticmethod
    def _frame_pen(mover):
        """What colour and how heavy this tile's frame is this frame.

        Idle is a plain edge rather than a state colour, so the weight has to
        crossfade along with the hue -- otherwise a box leaving idle snaps from
        1px to 2px in the middle of an otherwise smooth transition and the whole
        effect reads as a glitch.
        """
        def pen_for(state):
            if state == session.IDLE:
                return theme.qcolour(theme.EDGE_BRIGHT), 1.0
            return theme.state_qcolour(state), 2.0

        was_colour, was_width = pen_for(mover.previous)
        now_colour, now_width = pen_for(mover.state)
        blend = mover.blend.get()
        colour = theme.mix(was_colour, now_colour, blend)
        width = was_width + (now_width - was_width) * blend

        # A swell brightens and thickens the colour the tile already has, rather
        # than introducing one of its own: the state vocabulary stays five
        # colours, and the movement is what carries the interruption.
        attention = mover.attention.get()
        if attention:
            colour = theme.mix(colour, theme.TEXT, 0.45 * attention)
            width += 1.6 * attention

        # Hover lifts whatever is already there. Never toward the accent: that
        # is reserved for things you can act on, and every tile is one, so
        # spending it here would say nothing.
        hover = mover.hover.get()
        if hover:
            colour = theme.mix(colour, theme.TEXT, 0.28 * hover)
            width += 0.6 * hover
        return colour, width

    def _paint_caption(self, painter, tile, box, mover):
        """name · state · url, on the strip under the tile.

        Three weights rather than three colours doing all the work: the name is
        the only thing you scan for, the state is second, and the URL is there
        when you look for it. At 30-60% of the source window a tile is a texture
        rather than a document -- you can tell a form from a table but not read
        a word -- so this strip is where the box actually says what it is.
        """
        state = mover.state
        top = tile.label.top + 5
        x = tile.label.left + 8
        right = tile.label.right - 8
        hover = mover.hover.get()

        painter.setFont(self.name_font)
        baseline = top + self.name_metrics.ascent()
        painter.setPen(theme.mix(theme.TEXT, "#ffffff", 0.5 * hover))
        painter.drawText(x, baseline, box.name)
        x += self.name_metrics.horizontalAdvance(box.name) + 10

        # A painted dot rather than the "●" glyph: it lands on a whole pixel at
        # any size, and the glyph's own side bearing was doing the spacing.
        # It swells with the frame, so the interruption is said twice in the one
        # place you are already looking to find out which box it came from.
        colour = theme.mix(theme.state_qcolour(mover.previous),
                           theme.state_qcolour(state), mover.blend.get())
        radius = 3.0 + 1.6 * mover.attention.get()
        centre_y = baseline - self.metrics.ascent() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(colour)
        painter.drawEllipse(QRectF(x, centre_y - radius, radius * 2, radius * 2))
        x += 3.0 * 2 + 6   # the settled size, so the words never shift with it

        painter.setFont(self.font)
        painter.setPen(colour)
        painter.drawText(x, baseline, state)
        x += self.metrics.horizontalAdvance(state) + 10

        painter.setPen(theme.mix(theme.DIM, theme.MUTED, hover))
        painter.drawText(x, baseline, clip(
            self.metrics.horizontalAdvance,
            short_url(self.app.url_of(box)),
            right - x,
        ))
        self._paint_last_action(painter, tile, box, baseline, hover)

    def _paint_last_action(self, painter, tile, box, first_baseline, hover):
        """The last thing this box actually did, when there is room to say it.

        The room comes from the grid's vertical slack, which `label_max` spends
        here instead of leaving it as background -- so this line exists at the
        sizes where it fits and simply does not at the sizes where it would
        crowd the tile, rather than being a setting anyone has to know about.

        It is the trajectory's last entry, which is a record of something that
        happened. Not a summary, not a score, and not a count of anything: an
        overview that ranked its boxes would be a different app.
        """
        second = first_baseline + self.metrics.height() + 2
        if second > tile.label.bottom - 2:
            return
        sess = self.app.sessions.get(box.name)
        line = sess.steps[-1] if sess and sess.steps else ""
        if not line:
            return
        painter.setFont(self.font)
        painter.setPen(theme.mix(theme.DIM, theme.MUTED, hover))
        painter.drawText(tile.label.left + 8, second, clip(
            self.metrics.horizontalAdvance,
            str(line),
            tile.label.right - 8 - (tile.label.left + 8),
        ))

    def _paint_add_tile(self, painter, tile):
        """The last cell: a way to get one more box.

        Dashed, and captionless, so it never reads as a window that failed to
        appear.
        """
        hovered = self._hovered == tile.index
        if self._launching:
            text, colour = "launching…", theme.MUTED
        elif self.app.can_add():
            text, colour = "+   Add box", theme.TEXT if hovered else theme.MUTED
        else:
            text, colour = f"limit reached ({self.app.manager.max_boxes})", theme.DIM
        pen = QPen(theme.qcolour(theme.EDGE_BRIGHT if hovered else theme.EDGE),
                   1, Qt.DashLine)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self._rectf(tile.thumb), theme.RADIUS, theme.RADIUS)
        painter.setFont(self.body)
        painter.setPen(theme.qcolour(colour))
        painter.drawText(self._rectf(tile.thumb), Qt.AlignCenter, text)

    def _paint_too_small(self, painter, count):
        """`tile_rects` gives up rather than drawing tiles too small to see. Say
        so, or the overview is just blank and nobody knows why."""
        painter.setFont(self.body)
        painter.setPen(theme.qcolour(theme.MUTED))
        painter.drawText(
            QRectF(self.canvas.rect()), Qt.AlignCenter,
            f"{count} boxes will not fit in a window this size —\n"
            "make the dashboard bigger",
        )

    def _paint_empty(self, painter, tile):
        rect = self._rectf(tile.thumb)
        painter.setPen(QPen(theme.qcolour(theme.EMPTY_EDGE), 1))
        painter.setBrush(theme.qcolour(theme.EMPTY_BG))
        painter.drawRoundedRect(rect, theme.RADIUS, theme.RADIUS)
        painter.setFont(self.font)
        painter.setPen(theme.qcolour(theme.EMPTY_TEXT))
        painter.drawText(rect, Qt.AlignCenter, "no window")

    @staticmethod
    def _rectf(rect):
        return QRectF(rect.left, rect.top,
                      rect.right - rect.left, rect.bottom - rect.top)

    def tile_screen_rects(self):
        """Thumb rects in physical screen pixels -- verify.py samples them.

        Box tiles only: the add tile is the app's own drawing, and sampling it
        would be sampling ourselves.
        """
        return [
            self.app.screen_rect(self.canvas, tile.thumb)
            for tile in self.tiles[:len(self.app.manager.boxes)]
        ]

    # -- actions ------------------------------------------------------------

    def hover(self, x, y):
        """The pointer moved. `None` means it left the grid entirely.

        Hover lives in the frame, the caption and the cursor -- never over the
        tile itself. A thumbnail composites above everything this app paints, so
        a scrim or a caption laid across a tile would simply be invisible, and
        the only way to draw there at all would be to hide the live view of the
        box you are pointing at. That trade is not worth making: a dashboard
        that blanks a box the moment you look at it is worse than one with no
        hover state.
        """
        index = None if x is None else layout.hit_test(self.tiles, x, y)
        boxes = self.app.manager.boxes
        if index is not None and index >= len(boxes):
            index = None if not self.app.can_add() else index
        if index == self._hovered:
            return
        self._hovered = index
        for at, box in enumerate(boxes):
            mover = self.app.motion_of(box)
            if mover is not None:
                mover.set_hover(at == index)
        # A tile you can open, and an add tile you can click, both deserve to
        # say so with the pointer. The grid's dead space does not.
        self.canvas.setCursor(
            Qt.PointingHandCursor if index is not None else Qt.ArrowCursor)
        self.canvas.update()

    def double_click(self, x, y):
        index = layout.hit_test(self.tiles, x, y)
        if index is None or index >= len(self.app.manager.boxes):
            return  # the add tile is a button; one click is enough
        self.app.enter_detail(self.app.manager.boxes[index])

    def click(self, x, y):
        index = layout.hit_test(self.tiles, x, y)
        if index is None or index < len(self.app.manager.boxes):
            return  # a single click on a box does nothing; double-click opens it
        self.add_box()

    def add_box(self):
        """Launch one more box, having first said that it is happening.

        The launch owns this thread for a second or two, so the "launching…"
        frame has to be painted and flushed *before* the call -- hence repaint()
        rather than update(), which would only schedule one for a loop that is
        about to stop turning.
        """
        if self.app.adding or not self.app.can_add():
            return
        self._launching = True
        self.canvas.repaint()
        try:
            self.app.add_box()
        finally:
            self._launching = False
        self.relayout()

    # -- inspection ---------------------------------------------------------
    #
    # smoke.py and verify.py ask their questions through these rather than
    # through widget APIs, so a check reads as a claim about the dashboard.

    def tile_centre(self, index):
        """Screen centre of tile `index`; -1 is the add tile. Physical pixels,
        because the only caller drives the real cursor with SetCursorPos."""
        if not self.tiles:
            return None
        tile = self.tiles[index]
        left, top, width, height = self.app.screen_rect(self.canvas, tile.thumb)
        return (left + width // 2, top + height // 2)

    def control_centre(self, name):
        """Screen centre of one named control, for the demo's pointer.

        A lookup rather than a walk over the widget tree comparing labels: the
        view knows what its own controls are called, and a director should not
        have to know what they are made of.
        """
        widget = self._controls.get(name)
        return self.app.centre_of(widget) if widget is not None else None

    def canvas_size(self):
        """The tile area, in the units `layout.tile_rects` lays out in."""
        return self.canvas.width(), self.canvas.height()

    def jump_text(self):
        """What the go-to-the-waiting-box button is currently offering."""
        return self.jump.text()
