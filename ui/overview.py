"""The overview: every box as a live tile, and a way into one of them.

Double-click enters a box's detail view. That is the only gesture here -- a
single click used to summon the real window onto the desktop, and no longer
does anything, because you are meant to work through the detail view rather than
through the browser.
"""

import tkinter as tk
from tkinter import ttk

import layout
import session

from . import theme
from .text import clip, short_url

LABEL_PAD = 6
PAD = 12
RING = 3  # how far outside the thumb the state ring sits


class OverviewView:
    def __init__(self, app):
        self.app = app
        self.tiles = []
        self.offset = (0, 0)
        self._launching = False

        self.font = app.fonts["small"]
        self.label_h = self.font.metrics("linespace") + LABEL_PAD

        self.frame = ttk.Frame(app.root)

        header = ttk.Frame(self.frame)
        header.pack(side="top", fill="x", padx=PAD, pady=(PAD, 4))
        ttk.Label(header, text="multibox", style="Head.TLabel").pack(side="left")
        ttk.Label(
            header, text="double-click a box to open it", style="Muted.TLabel"
        ).pack(side="left", padx=(12, 0))
        # Rightmost first: [ summary ] [ go to the box that needs you ]
        self.jump = ttk.Button(header, text="", command=self.go_to_waiting)
        self.jump.pack(side="right")
        # One label per state rather than one string, so each count is in its own
        # colour -- the same colour as the ring on the tiles it is counting.
        summary = ttk.Frame(header)
        summary.pack(side="right", padx=(0, 14))
        self.counts = {}
        for state in session.STATES:
            label = tk.Label(summary, text="", bg=theme.BG,
                             fg=theme.state_colour(state), font=self.font)
            self.counts[state] = label

        self.canvas = tk.Canvas(self.frame, bg=theme.BG, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True, padx=PAD, pady=(0, PAD))
        self.canvas.bind("<Configure>", lambda _e: self.relayout())
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-1>", self.on_click)

    # -- view protocol ------------------------------------------------------

    def show(self):
        self.frame.pack(fill="both", expand=True)

    def hide(self):
        self.frame.pack_forget()

    def relayout(self):
        self.offset = self.app.client_offset(self.canvas)
        # One cell past the fleet: the last tile is "+ Add box", laid out with
        # the others so the grid stays one shape rather than a grid plus a
        # button stuck somewhere.
        self.tiles = layout.tile_rects(
            self.canvas.winfo_width(),
            self.canvas.winfo_height(),
            len(self.app.manager.boxes) + 1,
            aspect=self.app.aspect(),
            columns=self.app.dash.get("columns", "auto"),
            gap=self.app.dash.get("gap", 10),
            label_h=self.label_h,
            max_thumb=self.app.source_size(),
        )
        self.draw()

    def sync(self):
        """Something a box is doing changed. Same work as a redraw."""
        self.draw()

    def _draw_header(self):
        """A count per state, and a way to reach whoever is waiting.

        Pointing at a box is navigation, not prioritising: the tiles never
        reorder, nothing is scored, and nothing moves unless you click.
        """
        counts = self.app.state_counts()
        # Re-pack every time: packing order is insertion order, so a label that
        # comes back after being hidden would otherwise jump to the end and the
        # states would drift out of their fixed order.
        for label in self.counts.values():
            label.pack_forget()
        for state in session.STATES:
            if counts.get(state):
                self.counts[state].configure(text=f"{counts[state]} {state}")
                self.counts[state].pack(side="left", padx=(0, 12))
        waiting = self.app.waiting()
        if not waiting:
            self.jump.configure(text="nothing needs you", state="disabled")
            return
        extra = f"  (+{len(waiting) - 1} more)" if len(waiting) > 1 else ""
        self.jump.configure(text=f"go to {waiting[0].name}{extra}  →", state="normal")

    def go_to_waiting(self):
        waiting = self.app.waiting()
        if waiting:
            self.app.enter_detail(waiting[0])

    def draw(self):
        dx, dy = self.offset
        self._draw_header()
        self.canvas.delete("all")
        boxes = self.app.manager.boxes
        if not self.tiles:
            self._draw_too_small(len(boxes))
            return
        self._draw_add_tile(self.tiles[-1])
        for tile, box in zip(self.tiles, boxes):
            state = self.app.sessions[box.name].state
            rect = (
                tile.thumb.left + dx, tile.thumb.top + dy,
                tile.thumb.right + dx, tile.thumb.bottom + dy,
            )
            if not self.app.place(box, rect):
                self._draw_empty(tile)
            self._draw_ring(tile, state)
            self._draw_caption(tile, box, state)

    def _draw_ring(self, tile, state):
        """A state-coloured ring around the tile, drawn OUTSIDE the thumb rect --
        a thumbnail composites above the canvas, so anything inside it is
        invisible. Idle gets no ring: five glowing tiles say nothing."""
        if state == session.IDLE:
            return
        self.canvas.create_rectangle(
            tile.thumb.left - RING, tile.thumb.top - RING,
            tile.thumb.right + RING, tile.thumb.bottom + RING,
            outline=theme.state_colour(state), width=2,
        )

    def _draw_caption(self, tile, box, state):
        """name — state — url, on the strip under the tile."""
        width = tile.label.right - tile.label.left
        top = tile.label.top + 2
        x = tile.label.left
        self.canvas.create_text(
            x, top, anchor="nw", text=box.name, fill=theme.TEXT, font=self.font
        )
        x += self.font.measure(box.name + "  ")
        label = f"● {state}"
        self.canvas.create_text(
            x, top, anchor="nw", text=label, fill=theme.state_colour(state),
            font=self.font,
        )
        x += self.font.measure(label + "  ")
        self.canvas.create_text(
            x, top, anchor="nw",
            text=clip(self.font, short_url(self.app.url_of(box)), tile.label.right - x),
            fill=theme.MUTED, font=self.font,
        )

    def _draw_add_tile(self, tile):
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
        self.canvas.create_rectangle(
            *tile.thumb, outline=theme.EDGE, dash=(4, 4)
        )
        self.canvas.create_text(
            (tile.thumb.left + tile.thumb.right) // 2,
            (tile.thumb.top + tile.thumb.bottom) // 2,
            text=text, fill=colour, font=self.app.fonts["body"],
        )

    def _draw_too_small(self, count):
        """`tile_rects` gives up rather than drawing tiles too small to see. Say
        so, or the overview is just blank and nobody knows why."""
        self.canvas.create_text(
            self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2,
            text=f"{count} boxes will not fit in a window this size —\n"
                 "make the dashboard bigger",
            fill=theme.MUTED, font=self.app.fonts["body"], justify="center",
        )

    def _draw_empty(self, tile):
        self.canvas.create_rectangle(
            *tile.thumb, outline=theme.EMPTY_EDGE, fill=theme.EMPTY_BG
        )
        self.canvas.create_text(
            (tile.thumb.left + tile.thumb.right) // 2,
            (tile.thumb.top + tile.thumb.bottom) // 2,
            text="no window", fill=theme.EMPTY_TEXT, font=self.font,
        )

    def tile_screen_rects(self):
        """Thumb rects in screen coordinates -- used by verify.py to sample pixels.

        Box tiles only: the add tile is the app's own drawing, and sampling it
        would be sampling ourselves.
        """
        return [
            (
                self.canvas.winfo_rootx() + tile.thumb.left,
                self.canvas.winfo_rooty() + tile.thumb.top,
                tile.thumb.right - tile.thumb.left,
                tile.thumb.bottom - tile.thumb.top,
            )
            for tile in self.tiles[:len(self.app.manager.boxes)]
        ]

    # -- actions ------------------------------------------------------------

    def on_double_click(self, event):
        index = layout.hit_test(self.tiles, event.x, event.y)
        if index is None or index >= len(self.app.manager.boxes):
            return  # the add tile is a button; one click is enough
        self.app.enter_detail(self.app.manager.boxes[index])

    def on_click(self, event):
        index = layout.hit_test(self.tiles, event.x, event.y)
        if index is None or index < len(self.app.manager.boxes):
            return  # a single click on a box does nothing; double-click opens it
        self.add_box()

    def add_box(self):
        """Launch one more box, having first said that it is happening.

        The launch owns this thread for a second or two, so the "launching…"
        frame has to be painted and flushed *before* the call. Painted after, the
        only frame anyone sees is the one where it is already over.
        """
        if self.app.adding or not self.app.can_add():
            return
        self._launching = True
        self.draw()
        self.canvas.update_idletasks()
        try:
            self.app.add_box()
        finally:
            self._launching = False
        self.relayout()
