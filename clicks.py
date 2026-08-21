"""The real mouse and the real keyboard, for the demo.

The film is a recording of a cursor. Video editors track that cursor -- it is
how a cut follows the action -- so a demo that changes the app by calling its
methods produces footage where things happen and nothing moves. Every control
the film presses is therefore pressed: the pointer travels to it, the left
button goes down and up, and Windows delivers the click to whatever is under
the cursor, which is the dashboard's own widget with its own handler.

That last sentence is also the danger. A synthetic click is not addressed to
anything; it lands wherever the pointer happens to be, on whatever window
happens to be in front. `demo.py` checks `App.holds_foreground()` before every
one of them, and never clicks while a browser is summoned onto the desktop.

`mouse_event` and `keybd_event` rather than `SendInput`: they are two lines of
ctypes each, this module has no other job, and `demo.py` was already driving
Chromium's find bar with `keybd_event`. There is nothing here that a hand at the
keyboard could not do, which is the whole point -- if a beat cannot be performed
from this module, it does not belong in the film.

Movement is eased rather than teleported. A pointer that jumps between controls
reads as a script; one that arrives reads as a hand, and gives a tracker
something continuous to follow.
"""

import ctypes
import time

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_F = 0x46
KEYEVENTF_KEYUP = 0x0002

# How long the button is held. Long enough for Qt to paint the pressed state --
# which is the visible reward for clicking for real rather than calling the
# handler -- and short enough to read as a click rather than a drag.
PRESS_S = 0.09

# Two clicks inside this are a double-click. Windows' own setting is usually
# 500ms; well under it, because the beat that opens a box depends on Qt agreeing
# that this was one gesture.
DOUBLE_GAP_S = 0.12

KEY_S = 0.045   # per character, typing into a real window


def where():
    """The pointer, now."""
    point = (ctypes.c_long * 2)()
    user32.GetCursorPos(ctypes.byref(point))
    return point[0], point[1]


def move(x, y):
    user32.SetCursorPos(int(x), int(y))


def glide(target, hops=14, ease=3):
    """Yield the pointer's way to `target`, a hop at a time.

    A generator, because the director's beats are `app.schedule` callbacks and
    nothing in this app is allowed to sleep on the UI thread: the caller yields
    between hops and the layout tick and the agent pump keep running. Eased out,
    so the pointer arrives rather than stops.
    """
    if target is None:
        return
    x0, y0 = where()
    for hop in range(1, hops + 1):
        fraction = hop / hops
        move(x0 + (target[0] - x0) * (1 - (1 - fraction) ** ease),
             y0 + (target[1] - y0) * (1 - (1 - fraction) ** ease))
        yield


def press():
    """One left click, wherever the pointer is."""
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(PRESS_S)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def double_press():
    press()
    time.sleep(DOUBLE_GAP_S)
    press()


def tap(vk, ctrl=False):
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def send_char(char):
    """One character to whatever holds the keyboard, and no waiting.

    Separate from `type_text` because the director types into the dashboard's
    own chat box one character per beat: sleeping between them would block the
    UI thread, and a dashboard that cannot repaint while someone types is a
    dashboard that looks broken on camera.
    """
    code = user32.VkKeyScanW(ord(char))
    if code == -1:
        return
    vk, shift = code & 0xFF, bool(code >> 8 & 1)
    if shift:
        user32.keybd_event(VK_SHIFT, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    if shift:
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)


def type_text(text, per_key=KEY_S):
    """Into whatever holds the keyboard, blocking. For the summoned browser,
    where the dashboard is behind the window anyway."""
    for char in text:
        send_char(char)
        time.sleep(per_key)
