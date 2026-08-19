"""The overview: every box as a live tile, and a way into one of them.

Double-click enters a box's detail view. That is the only gesture here -- a
single click used to summon the real window onto the desktop, and no longer
does anything, because you are meant to work through the detail view rather than
through the browser.
"""

import tkinter as tk
from tkinter import ttk

import layout

from . import theme
from .text import clip, short_url

LABEL_PAD = 6
PAD = 12


class OverviewView:
    def __init__(self, app):
        self.app = app
        self.tiles = []
        self.offset = (0, 0)

        self.font = app.fonts["small"]
        self.label_h = self.font.metrics("linespace") + LABEL_PAD

        self.frame = ttk.Frame(app.root)

        header = ttk.Frame(self.frame)
        header.pack(side="top", fill="x", padx=PAD, pady=(PAD, 4))
        ttk.Label(header, text="multibox", style="Head.TLabel").pack(side="left")
        ttk.Label(
            header, text="double-click a box to open it", style="Muted.TLabel"
        ).pack(side="right")

        self.canvas = tk.Canvas(self.frame, bg=theme.BG, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True, padx=PAD, pady=(0, PAD))
        self.canvas.bind("<Configure>", lambda _e: self.relayout())
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

    # -- view protocol ------------------------------------------------------

    def show(self):
        self.frame.pack(fill="both", expand=True)

    def hide(self):
        self.frame.pack_forget()

    def relayout(self):
        self.offset = self.app.client_offset(self.canvas)
        self.tiles = layout.tile_rects(
            self.canvas.winfo_width(),
            self.canvas.winfo_height(),
            len(self.app.manager.boxes),
            aspect=self.app.aspect(),
            columns=self.app.dash.get("columns", "auto"),
            gap=self.app.dash.get("gap", 10),
            label_h=self.label_h,
            max_thumb=self.app.source_size(),
        )
        self.draw()

    def draw(self):
        dx, dy = self.offset
        self.canvas.delete("all")
        for tile, box in zip(self.tiles, self.app.manager.boxes):
            rect = (
                tile.thumb.left + dx, tile.thumb.top + dy,
                tile.thumb.right + dx, tile.thumb.bottom + dy,
            )
            if not self.app.place(box, rect):
                self._draw_empty(tile)
            # Labels must sit outside the thumb rect: thumbnails always
            # composite above anything the canvas draws.
            width = tile.label.right - tile.label.left
            name_px = self.font.measure(box.name + "  ")
            self.canvas.create_text(
                tile.label.left, tile.label.top + 2, anchor="nw",
                text=box.name, fill=theme.TEXT, font=self.font,
            )
            self.canvas.create_text(
                tile.label.left + name_px, tile.label.top + 2, anchor="nw",
                text=clip(self.font, short_url(box.url), width - name_px),
                fill=theme.MUTED, font=self.font,
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
        """Thumb rects in screen coordinates -- used by verify.py to sample pixels."""
        return [
            (
                self.canvas.winfo_rootx() + tile.thumb.left,
                self.canvas.winfo_rooty() + tile.thumb.top,
                tile.thumb.right - tile.thumb.left,
                tile.thumb.bottom - tile.thumb.top,
            )
            for tile in self.tiles
        ]

    # -- actions ------------------------------------------------------------

    def on_double_click(self, event):
        index = layout.hit_test(self.tiles, event.x, event.y)
        if index is None:
            return
        self.app.enter_detail(self.app.manager.boxes[index])
