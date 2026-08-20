"""Spike: is a PySide6 window a valid DWM thumbnail destination?

Throwaway. Answers the one question that could sink a Qt port, and answers it
with pixels rather than by eye: launch one real box the way the app does
(parked past the virtual screen, dropped from the taskbar), mirror it into a Qt
window, flip the page red then blue, and BitBlt the tile back off the screen.

Needs a dependency the app itself does not:

    .venv\\Scripts\\python.exe -m pip install PySide6
    .venv\\Scripts\\python.exe spike_qt.py

Delete this file, and uninstall PySide6, if the port does not happen.
"""

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

import boxes as boxes_mod
import thumbs

# Before QApplication, exactly as main.py does it before Tk. Qt sets its own DPI
# awareness if we don't get there first, and then these numbers mean something
# different.
DPI_MODE = thumbs.set_dpi_awareness()

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

HERE = Path(__file__).parent
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
SRCCOPY = 0x00CC0020

BG, PANEL, EDGE, TEXT, MUTED, ACCENT = (
    "#141414", "#1c1c1c", "#2f2f2f", "#f0f0f0", "#8a8a8a", "#6aa9e0",
)
FIXTURES = {"red": "#ff0000", "blue": "#0000ff"}


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def avg_rgb(left, top, width, height):
    """Average colour of a screen region.

    Screen DC on purpose: thumbnails live only in the compositor's visual tree,
    so PrintWindow on our own window would not contain them.
    """
    screen = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(mem, bitmap)
    gdi32.BitBlt(mem, 0, 0, width, height, screen, left, top, SRCCOPY)
    header = _BIH(biSize=ctypes.sizeof(_BIH), biWidth=width, biHeight=-height,
                  biPlanes=1, biBitCount=32, biCompression=0)
    buf = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem, bitmap, 0, height, buf, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, screen)
    data, count = buf.raw, width * height
    return tuple(sum(data[i * 4 + c] for i in range(count)) / count for c in (2, 1, 0))


def fixture(name):
    """Chrome blocks top-frame navigation to data: URLs, so use file://."""
    path = HERE / f"_spike_{name}.html"
    path.write_text(f"<body style='margin:0;background:{FIXTURES[name]}'>",
                    encoding="utf-8")
    return path.as_uri()


class Card(QWidget):
    """The chrome around one tile: antialiased rounded frame, drop shadow, a pill.

    Every painted thing sits OUTSIDE self.tile. That is not a stylistic choice --
    a DWM thumbnail composites above the whole destination window, so anything
    drawn across the tile rect is invisible in Qt exactly as it is in Tk.
    """

    RADIUS, INSET, HEADER = 14, 12, 44

    def __init__(self):
        super().__init__()
        shadow = QGraphicsDropShadowEffect(self, blurRadius=28, xOffset=0, yOffset=6)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.setGraphicsEffect(shadow)
        self.tile = QWidget(self)  # placeholder rect; the thumbnail lands here

    def resizeEvent(self, _event):
        self.tile.setGeometry(
            self.INSET, self.HEADER,
            self.width() - 2 * self.INSET, self.height() - self.HEADER - self.INSET,
        )

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), self.RADIUS, self.RADIUS)
        p.fillPath(path, QColor(PANEL))
        p.strokePath(path, QColor(EDGE))

        p.setPen(QColor(TEXT))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(self.INSET + 4, 28, "spike")

        # A state pill -- rounded, antialiased, and not available in Tk's canvas.
        p.setFont(QFont("Segoe UI", 8))
        width = p.fontMetrics().horizontalAdvance("WORKING") + 24
        pill = self.rect().adjusted(
            self.width() - width - self.INSET - 4, 12,
            -self.INSET - 4, -self.height() + 34,
        )
        p.setBrush(QColor(ACCENT).darker(240))
        p.setPen(QColor(ACCENT))
        p.drawRoundedRect(pill, 11, 11)
        p.drawText(pill, Qt.AlignCenter, "WORKING")


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qt + dwm spike")
        # Set topmost BEFORE the native window exists. Toggling a Qt window flag
        # later destroys and recreates the HWND, which would silently invalidate
        # every thumbnail registered against it -- a real hazard for the port,
        # since verify.py toggles topmost with Tk's -topmost today.
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setStyleSheet(f"QWidget{{background:{BG};}}")
        self.resize(980, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 18)
        head = QHBoxLayout()
        title = QLabel("multibox")
        title.setStyleSheet(f"color:{TEXT};")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        note = QLabel(f"PySide6 spike - DPI {DPI_MODE}")
        note.setStyleSheet(f"color:{MUTED};")
        head.addWidget(title)
        head.addWidget(note)
        head.addStretch(1)
        outer.addLayout(head)

        self.card = Card()
        outer.addWidget(self.card, 1)


def physical_rect(hwnd, widget, dpr):
    """Widget geometry in the destination's CLIENT pixels, which is what
    rcDestination wants.

    Qt lays out in logical units and DWM is physical, so the conversion happens
    here and nowhere else. (Single-origin assumption: a real port must do this
    per-screen.)
    """
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    top_left = widget.mapToGlobal(QPoint(0, 0))
    x = round(top_left.x() * dpr) - origin.x
    y = round(top_left.y() * dpr) - origin.y
    return x, y, x + round(widget.width() * dpr), y + round(widget.height() * dpr)


def settle(app, handle, rect, seconds=1.2):
    """Keep Qt painting and the thumbnail placed for real wall-clock time.

    verify.py pumps for a full second before reading pixels; Chromium has to
    paint and DWM has to composite, and neither is instant.
    """
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        thumbs.place(handle, rect)
        time.sleep(0.01)


def main():
    results = []
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    app.processEvents()

    config = boxes_mod.load_config()
    config["boxes"] = ["spike"]
    manager = boxes_mod.BoxManager(config)
    print("launching one box (parked, off-screen)...")
    manager.start()
    box = manager.boxes[0]
    box.ensure_hwnd()

    try:
        # [1] Is winId() the top-level HWND? In Tk it is not -- winfo_id() is a
        # child, and DwmRegisterThumbnail rejects it with E_INVALIDARG.
        raw = int(window.winId())
        root = user32.GetAncestor(raw, thumbs.GA_ROOT)
        results.append(("[1] winId() is the top-level HWND", raw == root,
                        f"winId={raw} GA_ROOT={root}"))

        handle = thumbs.register(root, box.hwnd)
        results.append(("[2] DwmRegisterThumbnail accepts a Qt window",
                        handle is not None, f"source hwnd={box.hwnd}"))
        if handle is None:
            return results

        dpr = window.devicePixelRatioF()
        rect = physical_rect(root, window.card.tile, dpr)
        placed = thumbs.place(handle, rect)
        results.append(("[3] Thumbnail placed", placed,
                        f"dpr={dpr} rect={rect} source={thumbs.source_size(handle)}"))

        origin = wintypes.POINT(0, 0)
        user32.ClientToScreen(root, ctypes.byref(origin))
        left, top, right, bottom = rect
        settle(app, handle, rect, seconds=2.0)
        print("  client origin:", origin.x, origin.y)
        for label, fx, fy in (("centre", 0.5, 0.5), ("upper-left", 0.2, 0.3),
                              ("lower-right", 0.8, 0.75)):
            px = origin.x + round(left + (right - left) * fx)
            py = origin.y + round(top + (bottom - top) * fy)
            print(f"  probe {label:12s} at ({px},{py}) ->",
                  tuple(round(c) for c in avg_rgb(px, py, 24, 16)))

        # [4] The real question: are those tile pixels live page pixels? Sample
        # the middle -- the top of a tile is Chromium's toolbar, not the page.
        sx = origin.x + (left + right) // 2 - 40
        sy = origin.y + (top + bottom) // 2 - 20

        seen = {}
        for name in ("red", "blue"):
            box.page.goto(fixture(name), wait_until="commit")
            settle(app, handle, rect, seconds=1.5)
            seen[name] = avg_rgb(sx, sy, 80, 40)

        red, blue = seen["red"], seen["blue"]
        live = (red[0] > 140 and red[0] > red[2] + 60
                and blue[2] > 140 and blue[2] > blue[0] + 60)
        results.append(("[4] Tile shows live page pixels", live,
                        f"red={tuple(round(c) for c in red)} "
                        f"blue={tuple(round(c) for c in blue)}"))

        # [5] Playwright's blocking sync calls ran on the Qt thread throughout,
        # which is the same deal Tk gets today.
        results.append(("[5] Qt loop survives blocking Playwright calls", True,
                        "no deadlock, no reader thread"))

        settle(app, handle, rect, seconds=1.0)  # leave it up briefly to eyeball
        thumbs.unregister(handle)
    finally:
        manager.close()
        for name in FIXTURES:
            (HERE / f"_spike_{name}.html").unlink(missing_ok=True)
    return results


if __name__ == "__main__":
    rows = main()
    print()
    failed = 0
    for label, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
        print(f"      {detail}")
        failed += not ok
    print(f"\n{len(rows) - failed}/{len(rows)} passed")
    sys.exit(1 if failed else 0)
