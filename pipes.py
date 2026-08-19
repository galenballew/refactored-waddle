"""Reading a child process's stdout without ever blocking. Windows only.

`select()` does not work on pipes on Windows, and a plain `readline()` blocks the
thread until a line arrives -- which here is the thread running Tk and Playwright.
`PeekNamedPipe` asks how many bytes are already waiting; reading exactly that many
cannot block. So the dashboard drains its children on a timer and stays
single-threaded, which is the rule the whole app is arranged around.

Bytes arrive in whatever chunks the OS feels like, so a read can end mid-line.
The tail is kept until the rest of it turns up.
"""

import ctypes
import msvcrt
import os
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

kernel32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.PeekNamedPipe.restype = wintypes.BOOL


def available(fileobj):
    """Bytes waiting on the pipe. Zero if it is empty, closed or broken."""
    try:
        handle = msvcrt.get_osfhandle(fileobj.fileno())
    except (ValueError, OSError):
        return 0
    count = wintypes.DWORD(0)
    if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(count), None):
        return 0
    return count.value


class LineReader:
    """Complete lines from a pipe, or nothing. Never waits."""

    def __init__(self, fileobj):
        self.fileobj = fileobj
        self._tail = b""

    def lines(self):
        waiting = available(self.fileobj)
        if waiting:
            try:
                self._tail += os.read(self.fileobj.fileno(), waiting)
            except OSError:
                return []
        if b"\n" not in self._tail:
            return []
        *complete, self._tail = self._tail.split(b"\n")
        return [
            line.decode("utf-8", "replace").strip()
            for line in complete
            if line.strip()
        ]
