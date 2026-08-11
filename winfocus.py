"""Win32 helpers: find each Chromium window and force it to the foreground.

Playwright gives us no OS window handle, so we match windows to the processes
that a given browser launch created. Everything here is ctypes against user32 --
no third-party dependency.
"""

import csv
import ctypes
import subprocess
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
GW_OWNER = 4
CHROME_WINDOW_CLASS = "Chrome_WidgetWin_1"

# 64-bit handles are truncated without explicit restypes.
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
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


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
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if (
            pid.value in pids
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
    clicked the control window *is* foreground, so this normally just works; the
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
