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

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_F = 0x46
KEYEVENTF_KEYUP = 0x0002

# How long the button is held. Long enough for Qt to paint the pressed state --
# which is the visible reward for clicking for real rather than calling the
# handler -- and short enough to read as a click rather than a drag.
PRESS_S = 0.09

# How a move is paced, and this is the part that has to look human rather than
# merely be real.
#
# Screen recorders smooth the pointer. They sample it and run the samples through
# a filter tuned for a hand, and a hand does not cross nine hundred pixels in
# half a second -- so a move that fast leaves the filter still catching up
# seconds after the real cursor has stopped, which plays back as a slow straight
# crawl that arrives about when the next click happens. Live it looks perfect,
# because live it is; the crawl is the recorder's, drawn from our numbers.
#
# So travel time grows with distance, the way aimed movement does: a fixed cost
# to start and stop, plus about a millisecond per pixel. Nine hundred pixels
# takes roughly 1.1 seconds and peaks near 1200 px/s, which is inside what a hand
# does. Steps are small and frequent so a sampler sees a path rather than a jump.
HOP_S = 0.016            # ~60 positions a second
TRAVEL_FIXED_S = 0.26    # getting going and stopping again
TRAVEL_PER_PX = 1 / 1100  # and the distance in between

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
    """Put the pointer at `x, y` by *injecting input*, not by setting it.

    This is the whole difference between a recording that shows the cursor moving
    and one that does not, and it took a strange symptom to find.

    `SetCursorPos` moves the pointer, and everything on screen agrees it moved --
    Qt gets its enter and leave events, hover states light up, a person watching
    sees a mouse move. What it does *not* do is go through the input queue. A
    low-level mouse hook (`WH_MOUSE_LL`) is fed from that queue, and a hook is how
    screen recorders track the cursor, so a `SetCursorPos` move is invisible to
    them: no samples, no path.

    What they do see is our clicks, because `mouse_event` posts real input. So a
    recorder watching the old code got exactly one cursor sample per click and
    drew the pointer sliding in a straight line from one click to the next across
    the whole gap between them -- a crawl that was never on screen. Run the same
    code with no clicks in it at all and the recorded cursor never moves once,
    which is the observation that gave this away.

    `mouse_event` with `MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE` posts a move the
    hook can see. Absolute rather than relative, so the pointer lands where it was
    asked rather than somewhere pointer acceleration decided, and `VIRTUALDESK`
    so the coordinate space is every monitor rather than the primary one.
    Coordinates are normalised to 0-65535 across that space, which is finer than
    a pixel on any display this will ever run on.
    """
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = max(1, user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) - 1)
    height = max(1, user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) - 1)
    user32.mouse_event(
        MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
        int(round((int(x) - left) * 65535 / width)),
        int(round((int(y) - top) * 65535 / height)),
        0, 0)


def travel_time(distance):
    """How long a hand would take to move that far, in seconds."""
    return TRAVEL_FIXED_S + abs(distance) * TRAVEL_PER_PX


def glide(target, hop_s=HOP_S):
    """Yield the pointer's way to `target`, a hop at a time.

    A generator, because the director's beats are `app.schedule` callbacks and
    nothing in this app is allowed to sleep on the UI thread: the caller yields
    between hops, and the layout tick and the agent pump keep running.

    Eased in *and* out -- smoothstep, so the pointer is stationary at both ends
    and quickest in the middle. Easing only out means starting at full speed,
    which is the shape of a teleport with a tail on it and exactly what a cursor
    smoother renders badly.
    """
    if target is None:
        return
    x0, y0 = where()
    span = ((target[0] - x0) ** 2 + (target[1] - y0) ** 2) ** 0.5
    steps = max(2, round(travel_time(span) / hop_s))
    for step in range(1, steps + 1):
        fraction = step / steps
        eased = fraction * fraction * (3 - 2 * fraction)   # smoothstep
        move(x0 + (target[0] - x0) * eased, y0 + (target[1] - y0) * eased)
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
