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


class OverviewView:
    def __init__(self, app):
        self.app = app
        self.tiles = []
        self._empty = set()      # tile indices with no window behind them
        self._launching = False

        self.font = app.fonts["small"]
        self.body = app.fonts["body"]
        self.name_font = app.fonts["name"]
        self.metrics = QFontMetrics(self.font)
        self.name_metrics = QFontMetrics(self.name_font)
        # The strip the caption sits in, and therefore how much of each cell is
        # not thumbnail. Measured rather than guessed, so a different font size
        # does not quietly clip the captions.
        self.label_h = self.name_metrics.height() + LABEL_PAD

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
        pass

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
            state = self.app.sessions[box.name].state
            self._paint_card(painter, tile, state)
            if tile.index in self._empty:
                self._paint_empty(painter, tile)
            self._paint_caption(painter, tile, box, state)

    def _paint_card(self, painter, tile, state):
        """The frame a tile sits in.

        Drawn on the CELL grown by a few pixels, so every edge of it falls
        outside the thumbnail: a thumbnail composites above this widget, and a
        frame on the boundary would be half eaten. The fill only ever shows in
        the caption strip and the margin, which is the point -- it gives the
        caption a surface to sit on rather than floating on the background.

        Every tile is framed, idle included. An unframed tile has no edge of its
        own and reads as a screenshot lying on the background; the state is said
        in the border's colour and weight, and again in words underneath.
        """
        rect = self._rectf(tile.cell).adjusted(
            -theme.CARD_INSET, -theme.CARD_INSET, theme.CARD_INSET, theme.CARD_INSET)
        painter.setBrush(theme.qcolour(theme.PANEL))
        if state == session.IDLE:
            painter.setPen(QPen(theme.qcolour(theme.EDGE_BRIGHT), 1))
        else:
            painter.setPen(QPen(theme.state_qcolour(state), 2))
        painter.drawRoundedRect(rect, theme.RADIUS, theme.RADIUS)

    def _paint_caption(self, painter, tile, box, state):
        """name · state · url, on the strip under the tile.

        Three weights rather than three colours doing all the work: the name is
        the only thing you scan for, the state is second, and the URL is there
        when you look for it. At 30-60% of the source window a tile is a texture
        rather than a document -- you can tell a form from a table but not read
        a word -- so this strip is where the box actually says what it is.
        """
        top = tile.label.top + 5
        x = tile.label.left + 8
        right = tile.label.right - 8

        painter.setFont(self.name_font)
        baseline = top + self.name_metrics.ascent()
        painter.setPen(theme.qcolour(theme.TEXT))
        painter.drawText(x, baseline, box.name)
        x += self.name_metrics.horizontalAdvance(box.name) + 10

        # A painted dot rather than the "●" glyph: it lands on a whole pixel at
        # any size, and the glyph's own side bearing was doing the spacing.
        radius = 3.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.state_qcolour(state))
        painter.drawEllipse(QRectF(x, baseline - self.metrics.ascent() / 2 - radius,
                                   radius * 2, radius * 2))
        x += radius * 2 + 6

        painter.setFont(self.font)
        painter.setPen(theme.state_qcolour(state))
        painter.drawText(x, baseline, state)
        x += self.metrics.horizontalAdvance(state) + 10

        painter.setPen(theme.qcolour(theme.DIM))
        painter.drawText(x, baseline, clip(
            self.metrics.horizontalAdvance,
            short_url(self.app.url_of(box)),
            right - x,
        ))

    def _paint_add_tile(self, painter, tile):
        """The last cell: a way to get one more box.

        Dashed, and captionless, so it never reads as a window that failed to
        appear.
        """
        if self._launching:
            text, colour = "launching…", theme.MUTED
        elif self.app.can_add():
            text, colour = "+   Add box", theme.MUTED
        else:
            text, colour = f"limit reached ({self.app.manager.max_boxes})", theme.DIM
        pen = QPen(theme.qcolour(theme.EDGE), 1, Qt.DashLine)
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
