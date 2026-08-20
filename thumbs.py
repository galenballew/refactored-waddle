"""DWM live thumbnails: mirror a real window into a rectangle of our own window.

This is the mechanism behind Alt-Tab and taskbar previews. We hand the compositor
a standing instruction and it blits the source window's live surface on the GPU;
after registration the per-frame cost in Python is zero. That is why the dashboard
stays single-threaded -- no capture work ever happens on the Tk thread.

Rules worth knowing (all learned the hard way, see CLAUDE.md):
  - The destination must be a top-level window. Tk's winfo_id() is a child and
    fails with E_INVALIDARG; use top_level() below.
  - rcDestination is in the destination window's CLIENT coordinates.
  - Thumbnails always composite ABOVE the destination's own content, so anything
    you draw under a tile is invisible. Put labels outside the tile rect.
  - A minimized or virtual-desktop-cloaked source renders nothing. Occluded is
    fine, and so is entirely off-screen -- which is what lets boxes be parked
    clear of every monitor and still show a live tile.
  - fSourceClientAreaOnly does NOT strip browser chrome -- Chromium's toolbar is
    client area. Crop with rcSource if you want page pixels only.
"""

import ctypes
from ctypes import wintypes

dwm = ctypes.windll.dwmapi
user32 = ctypes.windll.user32

DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_RECTSOURCE = 0x00000002
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010

GA_ROOT = 2
S_OK = 0


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("rcDestination", wintypes.RECT),
        ("rcSource", wintypes.RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]


HTHUMBNAIL = wintypes.HANDLE

dwm.DwmRegisterThumbnail.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.POINTER(HTHUMBNAIL)]
dwm.DwmRegisterThumbnail.restype = ctypes.c_long
dwm.DwmUpdateThumbnailProperties.argtypes = [HTHUMBNAIL, ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
dwm.DwmUpdateThumbnailProperties.restype = ctypes.c_long
dwm.DwmUnregisterThumbnail.argtypes = [HTHUMBNAIL]
dwm.DwmUnregisterThumbnail.restype = ctypes.c_long
dwm.DwmQueryThumbnailSourceSize.argtypes = [HTHUMBNAIL, ctypes.POINTER(wintypes.SIZE)]
dwm.DwmQueryThumbnailSourceSize.restype = ctypes.c_long

user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]


def set_dpi_awareness():
    """Must run before the UI toolkit starts, or every rectangle is wrong on a
    scaled display.

    With this on, Tk reports physical pixels, which is the unit DWM client
    coordinates already use -- so under Tk no conversion is needed anywhere. That
    equivalence is a property of Tk and not of this call: a toolkit that lays out
    in logical units still has to convert where it meets rcDestination.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return "per-monitor"
    except Exception:
        user32.SetProcessDPIAware()
        return "system"


def top_level(hwnd):
    """The top-level window above `hwnd` -- the only valid thumbnail destination.

    Toolkits hand out child handles: Tk's winfo_id() is one, and giving it to
    DwmRegisterThumbnail fails with E_INVALIDARG.
    """
    return user32.GetAncestor(hwnd, GA_ROOT)


def client_origin(dest):
    """Screen coordinates of `dest`'s client (0, 0).

    rcDestination is measured from this point, so a caller converts a widget's
    screen position into thumbnail coordinates by subtracting it. Which widget,
    and in what units it reports itself, is the toolkit's business and stays out
    of this module -- see `App.client_offset`.
    """
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(dest, ctypes.byref(origin))
    return origin.x, origin.y


def register(dest, source):
    """Returns a thumbnail handle, or None if the source is gone."""
    handle = HTHUMBNAIL()
    if dwm.DwmRegisterThumbnail(dest, source, ctypes.byref(handle)) != S_OK:
        return None
    return handle


def source_size(handle):
    size = wintypes.SIZE()
    if dwm.DwmQueryThumbnailSourceSize(handle, ctypes.byref(size)) != S_OK:
        return None
    return size.cx, size.cy


def place(handle, rect, visible=True, opacity=255):
    """Move/show/hide a thumbnail. Non-zero return means the source died."""
    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = (
        DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE | DWM_TNP_OPACITY | DWM_TNP_SOURCECLIENTAREAONLY
    )
    props.rcDestination = wintypes.RECT(*rect)
    props.opacity = opacity
    props.fVisible = bool(visible)
    props.fSourceClientAreaOnly = True
    return dwm.DwmUpdateThumbnailProperties(handle, ctypes.byref(props)) == S_OK


def unregister(handle):
    return dwm.DwmUnregisterThumbnail(handle) == S_OK
