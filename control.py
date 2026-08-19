"""The dashboard: an ordinary window holding a grid of live browser tiles.

It is also the only window the user ever sees. The boxes are parked off the
desktop; clicking a tile summons one back for as long as it holds the keyboard,
and this file owns the two triggers that send it away again.

Still the only file that touches Tkinter. Each tile is a DWM thumbnail composited
by Windows itself, so nothing here captures or draws pixels -- the refresh loop
only rewrites label text, which is why this stays single-threaded.
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import layout
import thumbs
import winfocus

DEFAULT_ASPECT = 4 / 3
LABEL_PAD = 6


def _short(url):
    """Shorten for a caption.

    Local files show just their filename -- captions are clipped from the right,
    and every local path shares a long identical prefix, so keeping the head
    would make every tile read the same.
    """
    if not url:
        return "(blank)"
    if url.startswith("file:///"):
        return url.rsplit("/", 1)[-1] or url
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            return url[len(prefix):]
    return url


class ControlWindow:
    def __init__(self, manager):
        self.manager = manager
        self.config = manager.config
        self.dash = self.config.get("dashboard", {})
        self.tiles = []
        self.handles = {}
        self.dest = None
        self.offset = (0, 0)

        self.root = tk.Tk()
        self.root.title("multibox")
        self.root.configure(bg="#1b1b1b")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        # Focus returning here means the user is done with whatever box was
        # summoned. This fires before the click that may summon the next one, so
        # going straight from one tile to another still works.
        self.root.bind("<FocusIn>", lambda _e: self.manager.park_summoned())

        rect = layout.centred_rect(winfocus.work_area(), self.dash.get("size", [900, 1000]))
        self.root.geometry(
            f"{rect.right - rect.left}x{rect.bottom - rect.top}+{rect.left}+{rect.top}"
        )

        controls = ttk.Frame(self.root, padding=6)
        controls.pack(side="bottom", fill="x")
        self.url_var = tk.StringVar()
        entry = ttk.Entry(controls, textvariable=self.url_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry.bind("<Return>", lambda _e: self.send_to_all())
        ttk.Button(controls, text="Send to all", command=self.send_to_all).pack(side="left")
        ttk.Button(controls, text="Reload all", command=self.reload_all).pack(
            side="left", padx=(6, 0)
        )

        self.status = ttk.Label(self.root, text="", anchor="w")
        self.status.pack(side="bottom", fill="x", padx=8)

        self.font = tkfont.nametofont("TkDefaultFont")
        self.label_h = self.font.metrics("linespace") + LABEL_PAD

        self.canvas = tk.Canvas(self.root, bg="#1b1b1b", highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", lambda _e: self.relayout())

        self.root.update_idletasks()
        self.root.update()
        self.register_all()
        self.relayout()
        entry.focus_set()
        self.refresh()

    # -- thumbnails ---------------------------------------------------------

    def register_all(self):
        self.dest = thumbs.dest_hwnd(self.canvas)
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

    def _source_size(self):
        """The source window's own pixel size: both the tile aspect and the size
        past which scaling a tile up buys nothing. Boxes are all launched at the
        same size, so the first one that answers speaks for all of them."""
        for box in self.manager.boxes:
            handle = self.handles.get(box.name)
            if handle is not None:
                size = thumbs.source_size(handle)
                if size and size[0] and size[1]:
                    return size
        return None

    def _aspect(self):
        size = self._source_size()
        return size[0] / size[1] if size else DEFAULT_ASPECT

    def relayout(self):
        self.offset = thumbs.client_offset(self.dest, self.canvas) if self.dest else (0, 0)
        source = self._source_size()
        self.tiles = layout.tile_rects(
            self.canvas.winfo_width(),
            self.canvas.winfo_height(),
            len(self.manager.boxes),
            aspect=self._aspect(),
            columns=self.dash.get("columns", "auto"),
            gap=self.dash.get("gap", 10),
            label_h=self.label_h,
            max_thumb=source,
        )
        self.draw()

    def _clip(self, text, max_px):
        """Truncate to fit the cell, or captions bleed into the next tile."""
        if self.font.measure(text) <= max_px:
            return text
        while text and self.font.measure(text + "…") > max_px:
            text = text[:-1]
        return text + "…"

    def draw(self):
        dx, dy = self.offset
        self.canvas.delete("all")
        for tile, box in zip(self.tiles, self.manager.boxes):
            handle = self.handles.get(box.name)
            placed = False
            if handle is not None:
                rect = (
                    tile.thumb.left + dx, tile.thumb.top + dy,
                    tile.thumb.right + dx, tile.thumb.bottom + dy,
                )
                placed = thumbs.place(handle, rect)
                if not placed:
                    # Source died or was recreated; one retry, then give up.
                    handle = self._register(box)
                    if handle is not None:
                        placed = thumbs.place(handle, rect)
            if not placed:
                self.canvas.create_rectangle(
                    *tile.thumb, outline="#5a3030", fill="#2a1c1c"
                )
                self.canvas.create_text(
                    (tile.thumb.left + tile.thumb.right) // 2,
                    (tile.thumb.top + tile.thumb.bottom) // 2,
                    text="no window", fill="#a06060",
                )
            # Labels must sit outside the thumb rect: thumbnails always
            # composite above anything the canvas draws.
            width = tile.label.right - tile.label.left
            name_px = self.font.measure(box.name + "  ")
            self.canvas.create_text(
                tile.label.left, tile.label.top + 2, anchor="nw",
                text=box.name, fill="#f0f0f0", font=self.font,
            )
            self.canvas.create_text(
                tile.label.left + name_px, tile.label.top + 2, anchor="nw",
                text=self._clip(_short(box.url), width - name_px),
                fill="#909090", font=self.font,
            )

    def tile_screen_rects(self):
        """Thumb rects in screen coordinates -- used by verify.py to sample pixels."""
        rects = []
        for tile in self.tiles:
            rects.append((
                self.canvas.winfo_rootx() + tile.thumb.left,
                self.canvas.winfo_rooty() + tile.thumb.top,
                tile.thumb.right - tile.thumb.left,
                tile.thumb.bottom - tile.thumb.top,
            ))
        return rects

    # -- actions ------------------------------------------------------------

    def on_click(self, event):
        index = layout.hit_test(self.tiles, event.x, event.y)
        if index is None:
            return
        box = self.manager.boxes[index]
        if self.manager.summon(box):
            self.status.config(text=f"summoned {box.name}")
        else:
            self.status.config(text=f"{box.name}: no window to summon")

    def send_to_all(self):
        url = self.url_var.get()
        if url.strip():
            self._report(self.manager.navigate_all(url), f"sent {url.strip()}")

    def reload_all(self):
        self._report(self.manager.reload_all(), "reloaded all")

    def _report(self, failed, ok_message):
        names = ", ".join(name for name, _ in failed)
        self.status.config(text=f"failed: {names}" if failed else ok_message)

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
