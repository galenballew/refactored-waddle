"""Win32 helpers: find each Chromium window, place it, and force it to the foreground.

Playwright gives us no OS window handle, so we match windows to the processes
that a given browser launch created. Everything here is ctypes against user32 --
no third-party dependency.

This is also where a box stops being a desktop window: `hide_from_shell` drops it
from the taskbar and Alt-Tab, and `move_window` parks it clear of every monitor.
Neither of those hides the window in the Win32 sense, which is the point -- a
hidden, minimized or cloaked window is not composited and its tile goes blank.
"""

import csv
import ctypes
import subprocess
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SW_RESTORE = 9
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SPI_GETWORKAREA = 0x0030
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
CHROME_WINDOW_CLASS = "Chrome_WidgetWin_1"
# The renderer's own child window: the page, without the tab strip or toolbar.
CHROME_RENDER_WIDGET_CLASS = "Chrome_RenderWidgetHostHWND"

# 64-bit handles are truncated without explicit restypes.
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND,
                                 wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

# The Ptr forms only exist on 64-bit; the plain ones are the whole API on 32-bit.
_get_style = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
_set_style = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
_get_style.argtypes = [wintypes.HWND, ctypes.c_int]
_get_style.restype = ctypes.c_ssize_t
_set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_set_style.restype = ctypes.c_ssize_t

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def work_area():
    """Desktop minus the taskbar, in physical pixels. Call after DPI awareness is set."""
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def virtual_screen():
    """Union of every monitor, in physical pixels.

    A parked window has to clear this, not just the primary monitor, or plugging
    in a second screen would put five browser windows on it.
    """
    return (
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def window_rect(hwnd):
    """(left, top, right, bottom) in physical pixels, or None if the window is gone."""
    rect = wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def window_pid(hwnd):
    """The process owning a window, or 0. Beware: every Chromium window of one box
    shares a PID, which is exactly why the foreground test uses this and not HWNDs."""
    if not hwnd:
        return 0
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def is_tool_window(hwnd):
    return bool(hwnd) and bool(_get_style(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW)


def hide_from_shell(hwnd):
    """Drop a window from the taskbar and Alt-Tab, without hiding it from DWM.

    The shell only re-reads WS_EX_TOOLWINDOW across a hide/show cycle, hence the
    ShowWindow pair. The window is genuinely hidden between those two calls and
    has no thumbnail while it is, so this has to run before the dashboard
    registers one. Chromium is another process; the style edit is allowed because
    we launched it at our own integrity level, but it is not a contract -- callers
    should be able to re-apply it.
    """
    if not hwnd:
        return False
    style = _get_style(hwnd, GWL_EXSTYLE)
    user32.ShowWindow(hwnd, SW_HIDE)
    _set_style(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    return is_tool_window(hwnd)


def restore_to_shell(hwnd):
    """Give a window its taskbar button and Alt-Tab entry back."""
    if not hwnd:
        return False
    style = _get_style(hwnd, GWL_EXSTYLE)
    user32.ShowWindow(hwnd, SW_HIDE)
    _set_style(hwnd, GWL_EXSTYLE, (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW)
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    return not is_tool_window(hwnd)


def alt_tab_windows():
    """Every HWND the shell would offer in Alt-Tab: visible, unowned, not a tool
    window. Verification asks whether a box is in here; nothing else should be."""
    found = []

    def callback(hwnd, _lparam):
        if (
            user32.IsWindowVisible(hwnd)
            and not user32.GetWindow(hwnd, GW_OWNER)
            and not is_tool_window(hwnd)
            and user32.GetWindowTextLengthW(hwnd) > 0
        ):
            found.append(hwnd)
        return True

    user32.EnumWindows(_WNDENUMPROC(callback), 0)
    return found


def move_window(hwnd, x, y, width, height):
    """Place a window in physical pixels.

    Used instead of Chromium's --window-position because that flag is in DIPs,
    which would need DPI conversion; HWND coordinates are already physical.
    """
    if not hwnd:
        return False
    return bool(
        user32.SetWindowPos(hwnd, None, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE)
    )


def page_rect(hwnd):
    """Where the page itself is inside a Chromium window, in client coordinates.

    The tab strip and the toolbar are client area, so DWM's
    `fSourceClientAreaOnly` does not strip them -- a tile mirrors the whole
    browser, chrome included. The renderer, though, lives in its own child
    window, and its bounds are exactly the region worth showing.

    Measured rather than assumed: the chrome is 130px tall on this machine at
    150% scaling, and would be a different number at another zoom, with a
    bookmarks bar, or on another Chromium build.

    Returns None if the child window is not there -- a browser still starting
    up, or some future Chromium that arranges itself differently -- and the
    caller shows the whole window, which is merely the old behaviour.
    """
    if not hwnd:
        return None
    child = user32.FindWindowExW(hwnd, None, CHROME_RENDER_WIDGET_CLASS, None)
    if not child:
        return None
    bounds = wintypes.RECT()
    if not user32.GetWindowRect(child, ctypes.byref(bounds)):
        return None
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return (bounds.left - origin.x, bounds.top - origin.y,
            bounds.right - origin.x, bounds.bottom - origin.y)


def set_topmost(hwnd, on):
    """Float a window above the others, or stop.

    Done on the HWND rather than through the toolkit on purpose: Qt recreates
    the native window when a window flag changes, which would silently
    invalidate every DWM thumbnail registered against it. SetWindowPos only
    changes the z-order.
    """
    if not hwnd:
        return False
    return bool(user32.SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                                    0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))


def is_window(hwnd):
    return bool(hwnd) and bool(user32.IsWindow(hwnd))


def describe(hwnd):
    """Identify a window, for diagnosing who stole the foreground."""
    if not hwnd:
        return "none"
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return f"hwnd={hwnd} pid={window_pid(hwnd)} class={_class_name(hwnd)} title={buf.value[:44]!r}"


def chrome_pids():
    """Every running chrome.exe PID, as a set of ints."""
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
    ).stdout
    pids = set()
    for row in csv.reader(out.splitlines()):
        if len(row) >= 2 and row[1].strip().isdigit():
            pids.add(int(row[1].strip()))
    return pids


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def top_level_window(pids):
    """The visible top-level Chromium window owned by any PID in `pids`, or None."""
    found = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if (
            window_pid(hwnd) in pids
            and _class_name(hwnd) == CHROME_WINDOW_CLASS
            and not user32.GetWindow(hwnd, GW_OWNER)
            and user32.GetWindowTextLengthW(hwnd) > 0
        ):
            found.append(hwnd)
        return True

    user32.EnumWindows(_WNDENUMPROC(callback), 0)
    return found[0] if found else None


def foreground_window():
    return user32.GetForegroundWindow()


def focus_window(hwnd):
    """Raise `hwnd` and make it the foreground window. Returns True if Windows agreed.

    Windows only lets the current foreground process hand off focus. When a row is
    clicked the dashboard *is* foreground, so this normally just works; the
    AttachThreadInput dance is the fallback for when it is not (e.g. verify.py
    driving this from a console).
    """
    if not hwnd:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    current = kernel32.GetCurrentThreadId()
    fg = user32.GetForegroundWindow()
    other = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(other and other != current and user32.AttachThreadInput(current, other, True))
    try:
        user32.BringWindowToTop(hwnd)
        return bool(user32.SetForegroundWindow(hwnd))
    finally:
        if attached:
            user32.AttachThreadInput(current, other, False)
