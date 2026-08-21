"""Drive the real dashboard through a fixed demo, for recording.

    .venv\\Scripts\\python.exe demo.py                 # the whole thing, ~4 minutes
    .venv\\Scripts\\python.exe demo.py --no-claude      # same, minus the paid act
    .venv\\Scripts\\python.exe demo.py --pace 1.4       # hold every shot 40% longer

This is `main.py` with a director attached: the same `App`, the same boxes, the
same agent children. Nothing here is a mock. Every beat goes through the seam a
user's click would -- `detail.send()`, `overview.go_to_waiting()`,
`overview.add_box()` -- so what is recorded is the app working, not a
re-enactment of it.

Why a script rather than a live take: a person can only type into one box at a
time, which forces a demo of a parallel fleet to be narrated serially. The
director gives seven boxes a task inside fifteen seconds and then lets the grid
diverge on camera. That shot is the product, and it cannot be performed by hand.

`storyboard.md` is what this file implements, beat for beat, and `transcript.md`
is read against it. Change the film there first.

**The fleet changes size three times.** Three boxes at the start, because a tile
you can read a page in is what makes "this is a live window" land; eight in the
middle, which is the shot that shows a fleet rather than an app; five at the end,
which is the shipped default and the size the model act is legible at. The
starting three come from this file, not from `config.json` -- that file still
says five, because `verify.py` is choreographed against it.

**Half the pages are invented and half are real, and both halves matter.** The
real ones -- NPR, CNN, the first website ever published at CERN, the RFC editor,
Wikipedia, Hacker News, the Python docs -- are the point: these are ordinary
Chromium windows on the ordinary internet, and nothing here logs in, submits a
form or changes anything. The invented ones are Pinion Ops, served from `sites/`
over local HTTP by this file, and they buy two things the real internet cannot.
Their content does not move between takes, so the narration can name an answer
out loud -- "the top story on Hacker News" is a different story by the time the
take is cut. And one of their URLs answers 404 on purpose, which is where the
red tile in the churn act comes from: a real HTTP response, not a staged state.

Three pieces of stagecraft, all of them cosmetic:

  * the mouse pointer is glided onto a control with `SetCursorPos` a beat before
    the control is invoked, so actions look caused rather than spontaneous;
  * text is typed into the chat box a character at a time;
  * the take-control beat presses Ctrl+F in the summoned window and types into
    Chromium's own find bar -- browser chrome that cannot be mistaken for a
    picture of a browser.

Recording notes:

  * Capture the **display**, not the window. Tiles are DWM thumbnails and live
    only in the compositor's visual tree; a PrintWindow-based recorder gets empty
    rectangles where the tiles should be.
  * Do not touch the machine while it runs. The take-control beat summons a real
    window and hands it the keyboard, and a stray click parks it early.
  * Beat timings are printed to the console as they happen, and again as a
    summary at the end, for lining up narration. See `transcript.md`.

The paid act is the last one, and it is **five tasks on five boxes**: the fleet
runs on the free demo agent, and those boxes' children are swapped for Claude
ones through the ordinary constructor. `--no-claude` skips the swap and sends the
same five prompts to the demo agents instead, which still opens all five pages
for real -- that is what rehearsals should use, because a demo script gets run a
dozen times before the take that gets kept.
"""

import ctypes
import os
import sys
import time
import traceback

import session as session_model
import sites
import thumbs
from agents import Agent
from boxes import AVIARY, BoxManager, load_config
from ui.app import App

user32 = ctypes.windll.user32

# -- stagecraft ------------------------------------------------------------

GLIDE_MS = 22          # one hop of the pointer on its way to a control
GLIDE_HOPS = 14
KEY_MS = 38            # per character in the chat box
PAGE_KEY_S = 0.045     # per character into a real browser window
CLAUDE_CAP_S = 150     # give up waiting on the models rather than record a hang

# The fleet arc. Three shapes on camera, and the grid reflows between each.
OPENING_BOXES = 3
ADDS = 5               # 3 -> 8, one press of the add tile at a time
CLOSES = 3             # 8 -> 5, back to the shipped default

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_F = 0x46
KEYEVENTF_KEYUP = 0x0002


# -- the web ---------------------------------------------------------------

# Real sites, picked for being stable, readable without an account, plain enough
# to stay legible in a tile, and content nobody minds a browser reading a few
# times per take.
REAL = {
    "npr": "https://text.npr.org",
    "cnn": "https://lite.cnn.com",
    "cern": "https://info.cern.ch/hypertext/WWW/TheProject.html",
    "rfc": "https://www.rfc-editor.org/rfc/rfc1149.html",
    "hypervisor": "https://en.wikipedia.org/wiki/Hypervisor",
    "hn": "https://news.ycombinator.com",
    "pathlib": "https://docs.python.org/3/library/pathlib.html",
}

# Pinion Ops, this repo's own. Filled in against the local server's port once it
# is listening, because the port is picked at run time.
PINION = {
    "status": "/pinion/",
    "tickets": "/pinion/tickets",
    "changelog": "/pinion/changelog",
    "inventory": "/pinion/inventory",
    "runbook": "/pinion/runbook",
    # Not a page. The churn act sends a box here so one tile really fails.
    "deploy": "/pinion/deploys/482",
}


def pages(base):
    """Every URL this film uses, with the local ones pointed at `base`."""
    return {**REAL, **{key: base + path for key, path in PINION.items()}}


# A word that is certainly on the page the take-control beat is looking at, and
# certainly ours: the runbook is called "Runbook: payments-api Degraded" and says
# it another five times. A find that matches nothing reads as a broken browser,
# and a real site can drop a word between takes.
FIND_TERM = "Degraded"

# The opening: one box given a page, two given tasks with no page in them.
#
# **A box only asks when it has nothing at all to work with**, and that is the
# single constraint this whole script is arranged around. An agent given a task
# with no URL uses the page the box already has, and only comes back to ask if
# there is no such page -- blank, or still on the start page. So every beat that
# wants `needs input` on camera has to spend a box that has never navigated, and
# once a box has been somewhere it can never produce that state again.
#
# Getting this wrong is silent: the box reports `done` about the wrong page
# instead of asking, and the beat is simply missing from the take.
OPENING = [
    ("Wren", "status", "open {url} and tell me what is there"),
]
ASKS = [
    ("Finch", "what does the on-call rota say for this week?"),
    ("Swift", "read the second paragraph and summarise it"),
]

# The churn act, in two waves so the grid is never all one colour. Half of these
# pages are ours and half are the real internet, and every box is driven the same
# way. Plover is the asker here because it is a box added minutes ago that has
# never been given anything -- see the note above.
WAVE_ONE = [
    ("Heron", "changelog", "open {url} and tell me what is there"),
    ("Robin", "npr", "take a look at {url}"),
    ("Kestrel", "runbook", "open {url} and read it"),
    ("Swift", "cnn", "check {url}"),
]
WAVE_TWO = [
    ("Wren", "cern", "open {url}"),
    ("Finch", "deploy", "check {url}"),        # 404s, and the box says so
]
WAVE_TWO_ASKS = ("Plover", "summarise whatever it says about the outage")

# The model act: five real questions, on five pages. Two of them are ours, and
# their answers are the same in every take -- so the narration can say what the
# answer is. The other three are the real internet, which is the opposite point.
MODEL_TASKS = [
    ("Wren", "status",
     "go to {url} - which service is degraded, and how long has it been?"),
    ("Finch", "tickets",
     "go to {url} - what is the oldest unassigned P1, and who owns the service "
     "it is filed against? the owner is on the status board"),
    ("Swift", "hypervisor",
     "go to {url} - what is the difference between a type 1 and a type 2 "
     "hypervisor, in one sentence, and name an example of each from the page"),
    ("Heron", "hn",
     "go to {url} - which story on the front page has the most points right "
     "now, and how many comments does it have?"),
    ("Robin", "pathlib",
     "go to {url} - which method writes text to a file, and what does it do if "
     "the file is already there?"),
]

# Which boxes go away in the wind-down, and why these three: they are the ones
# the two beats before it have just used, so closing them reads as tidying up
# rather than as picking on a box at random.
CLOSING = ("Kestrel", "Plover", "Egret")


# Where things are on screen is the views' business: `tile_centre` and
# `control_centre` on each of them, answering in physical pixels because that is
# what SetCursorPos wants. This file does not know what the dashboard is built
# out of, which is the only reason a toolkit change did not rewrite it.


# -- the real keyboard -----------------------------------------------------
#
# Only ever used with a box summoned and holding the foreground -- every caller
# checks first -- because keystrokes go wherever the keyboard is, and being wrong
# about that means typing into someone else's window.

def tap(vk, ctrl=False):
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def type_into_page(text):
    for char in text:
        code = user32.VkKeyScanW(ord(char))
        if code == -1:
            continue
        vk, shift = code & 0xFF, bool(code >> 8 & 1)
        if shift:
            user32.keybd_event(VK_SHIFT, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        if shift:
            user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(PAGE_KEY_S)


# -- the director ----------------------------------------------------------

class Wait:
    """Hold here until something the app decides has happened."""

    def __init__(self, predicate, timeout, label=""):
        self.predicate = predicate
        self.deadline = time.monotonic() + timeout
        self.label = label

    def done(self):
        return self.predicate()

    def expired(self):
        return time.monotonic() > self.deadline


class Director:
    """Runs a generator of beats on the UI thread.

    The script yields either a number of seconds to hold, or a `Wait`. Everything
    else it does is an ordinary call into the app, which is the point: if a beat
    can be performed from here it could be performed by a user, and if it cannot
    it does not belong in the demo.

    On the UI thread and never off it, like everything else in this app -- the
    beats are `app.schedule` callbacks, so the layout tick and the pump keep
    running between them and the tiles never stop being live.
    """

    def __init__(self, app, pace=1.0):
        self.app = app
        self.pace = pace
        self.started = 0.0
        self.marks = []
        self._gen = None

    # -- clock ------------------------------------------------------------

    @property
    def elapsed(self):
        return time.monotonic() - self.started

    def stamp(self):
        return f"{int(self.elapsed) // 60}:{int(self.elapsed) % 60:02d}"

    @staticmethod
    def _console(text):
        """This console is cp1252 and the app is full of arrows and bullets.

        Anything quoted back from the UI -- the jump button's own text, a state
        word, a page title -- would otherwise raise `UnicodeEncodeError` from
        `print`, and an exception in a beat ends the film. Flattened rather than
        avoided, because quoting the UI back is how a take is lined up against
        what was on screen.
        """
        return str(text).encode("ascii", "replace").decode("ascii")

    def beat(self, name):
        self.marks.append((self.stamp(), name))
        print(f"  [{self.stamp():>5}]  {self._console(name)}", flush=True)

    def note(self, text):
        print(f"           . {self._console(text)}", flush=True)

    # -- stagecraft -------------------------------------------------------

    def point(self, target):
        """Glide the pointer onto a control, so the next action has a cause."""
        self.app.flush()
        if target is None:
            return
        origin = (ctypes.c_long * 2)()
        user32.GetCursorPos(ctypes.byref(origin))
        x0, y0 = origin[0], origin[1]
        for hop in range(1, GLIDE_HOPS + 1):
            fraction = hop / GLIDE_HOPS
            fraction = 1 - (1 - fraction) ** 3   # ease out: it arrives, not stops
            user32.SetCursorPos(int(x0 + (target[0] - x0) * fraction),
                                int(y0 + (target[1] - y0) * fraction))
            yield GLIDE_MS / 1000.0

    def type(self, text):
        """Into the detail view's chat box, one character at a time."""
        for char in text:
            self.app.detail.type_char(char)
            yield KEY_MS / 1000.0

    # -- the seam ---------------------------------------------------------

    def box(self, name):
        """A box by name. Indices stop meaning anything once the fleet grows."""
        for box in self.app.manager.boxes:
            if box.name == name:
                return box
        return None

    def session(self, box):
        return self.app.sessions[box.name]

    def state(self, box):
        return self.session(box).state

    def send(self, name, text):
        """What the chat box does, for a box we are not looking at."""
        box = self.box(name) if isinstance(name, str) else name
        if box is None:
            self.note(f"no box called {name}; skipped")
            return None
        self.app.send(box, text)
        if self.app.view is not None:
            self.app.view.sync()
        return box

    def say(self, text):
        """Type it and press Send, in the detail view, like a person would.

        Through `control_centre`, which answers in the physical pixels
        `SetCursorPos` wants. Handing `point` the widget itself is a crash --
        which is what was here, and what the port left behind: `entry` and
        `send_button` were coordinates under Tk and are QWidgets now.
        """
        yield from self.point(self.app.detail.control_centre("input"))
        yield from self.type(text)
        yield 0.35
        yield from self.point(self.app.detail.control_centre("send"))
        yield 0.2
        self.app.detail.send()

    def open_box(self, name):
        """Point at a box's tile and double-click it open."""
        box = self.box(name)
        if box is None:
            return None
        index = self.app.manager.boxes.index(box)
        yield from self.point(self.app.overview.tile_centre(index))
        yield 0.5
        self.app.enter_detail(box)
        return box

    def until(self, predicate, timeout=30.0, label=""):
        return Wait(predicate, timeout, label)

    def settled(self, names, timeout=30.0):
        """Every one of them has stopped working."""
        boxes = [self.box(name) for name in names]
        boxes = [box for box in boxes if box is not None]
        return self.until(
            lambda: all(self.state(box) != session_model.WORKING for box in boxes),
            timeout, "boxes finish")

    # -- running ----------------------------------------------------------

    def run(self, script):
        self.started = time.monotonic()
        self._gen = script(self)
        self.app.schedule(400, self._advance)

    def _advance(self):
        try:
            item = next(self._gen)
        except StopIteration:
            self._finish()
            return
        except Exception:
            traceback.print_exc()
            self._finish()
            return
        if isinstance(item, Wait):
            self._hold(item)
        else:
            self.app.schedule(max(1, int(float(item) * 1000 * self.pace)),
                              self._advance)

    def _hold(self, wait):
        if wait.done():
            self.app.schedule(1, self._advance)
        elif wait.expired():
            if wait.label:
                self.note(f"gave up waiting: {wait.label}")
            self.app.schedule(1, self._advance)
        else:
            self.app.schedule(50, self._hold, wait)

    def _finish(self):
        print("\n  beat sheet (actual):", flush=True)
        for stamp, name in self.marks:
            print(f"    {stamp:>5}  {self._console(name)}", flush=True)
        print(f"\n  total {self.stamp()}", flush=True)
        self.app.quit()


# -- the demo --------------------------------------------------------------

def swap_to_claude(app, box):
    """Give one box a Claude child in place of its scripted one.

    Through the ordinary constructor, and onto the same Session, so the chat keeps
    everything said before it: the seam does not change shape for the paid path,
    which is the thing worth showing.
    """
    old = app.agents.get(box.name)
    if old is not None:
        old.close()
    app.agents[box.name] = Agent(app.sessions[box.name], box.cdp, "claude")


def build_script(base, claude=True):
    url = pages(base)

    def script(d):
        app = d.app

        # -- 1. three boxes, doing nothing at all --------------------------
        d.beat("overview - three live tiles, each on its own start page")
        yield 7.0
        # A tile lifting under the pointer, before anything is happening in one.
        yield from d.point(app.overview.tile_centre(1))
        yield 3.0

        # -- 2. one box works, two come back and ask ------------------------
        d.beat("one box gets a page; two get tasks with no page in them")
        for name, key, prompt in OPENING:
            d.send(name, prompt.format(url=url[key]))
            yield 0.6
        # Neither of these names a URL, and neither box has been anywhere, so
        # both have to come back and ask. This is the only moment in the film
        # where two boxes are fresh at once, which is why both asks happen here.
        for name, prompt in ASKS:
            d.send(name, prompt)
            yield 0.6
        yield d.until(lambda: len(app.waiting()) >= 2, 40.0, "two boxes waiting")
        yield d.settled(["Wren"], timeout=60.0)
        yield 5.0

        # -- 4. the button that counts them --------------------------------
        d.beat("two boxes need you, and the button says so")
        yield from d.point(app.overview.control_centre("jump"))
        yield 1.2
        d.note(f"the button reads: {app.overview.jump_text()}")
        app.overview.go_to_waiting()
        yield 2.0
        first = app.box
        yield from d.say(url["tickets"])
        yield d.until(lambda: d.state(first) == session_model.DONE, 60.0,
                      f"{first.name} finishes")
        yield 2.5

        d.beat("answer one, and the button is still lit for the other")
        app.show_overview()
        yield 1.5
        yield from d.point(app.overview.control_centre("jump"))
        yield 1.0
        d.note(f"the button now reads: {app.overview.jump_text()}")
        app.overview.go_to_waiting()
        yield 1.8
        second = app.box
        yield from d.say(url["inventory"])
        yield d.until(lambda: d.state(second) == session_model.DONE, 60.0,
                      f"{second.name} finishes")
        yield 3.0

        # -- 5. the fleet grows, on camera ---------------------------------
        d.beat("+ Add box, five times, live")
        app.show_overview()
        yield 1.5
        for press in range(ADDS):
            before = len(app.manager.boxes)
            yield from d.point(app.overview.tile_centre(-1))
            yield 0.4
            app.overview.add_box()
            # A launch blocks this thread, so by the time we are back the box is
            # either there or was refused. Waiting on the count rather than on a
            # sleep is also what keeps the adds serialized, which PID
            # attribution depends on.
            yield d.until(lambda n=before: len(app.manager.boxes) > n, 25.0,
                          "the box to launch")
            yield 1.4
        d.note(f"{len(app.manager.boxes)} boxes now: "
               + ", ".join(box.name for box in app.manager.boxes))
        yield 2.5

        # -- 6. eight boxes, every state ------------------------------------
        # Egret is deliberately left out of both waves: the stop beat needs a box
        # whose child has not started Playwright yet. See beat 8.
        d.beat("four boxes go to work at once")
        for name, key, prompt in WAVE_ONE:
            d.send(name, prompt.format(url=url[key]))
            yield 0.7
        yield 9.0
        d.beat("a second wave, while the first is still going")
        for name, key, prompt in WAVE_TWO:
            d.send(name, prompt.format(url=url[key]))
            yield 0.7
        d.send(WAVE_TWO_ASKS[0], WAVE_TWO_ASKS[1])
        yield 6.0
        d.note("counts: " + ", ".join(f"{n} {s}" for s, n
                                      in app.state_counts().items() if n))
        yield d.settled([name for name, _, _ in WAVE_ONE + WAVE_TWO], timeout=90.0)
        yield 5.0
        d.note("ended: " + ", ".join(
            f"{box.name} {d.state(box)}" for box in app.manager.boxes))

        # -- 7. one box up close ---------------------------------------------
        d.beat("detail view: live mirror, trajectory, chat")
        yield from d.open_box("Robin")
        yield 12.0

        # -- 8. stop ----------------------------------------------------------
        # Egret, the one left out of the waves, and left out for this. Its child
        # has never run a task, so its first one spends a second or two importing
        # Playwright and attaching over CDP -- and that is the window Stop lands
        # in. On a warm child the cancel would arrive after the run was over. The
        # URL is one the script could finish, so a stop that misses records a
        # tidy run rather than a failure.
        d.beat("stop a run mid-flight")
        app.show_overview()
        yield 1.2
        yield from d.open_box("Egret")
        yield 1.2
        yield from d.say(f"open {url['rfc']} and read it")
        yield d.until(lambda: d.state(d.box("Egret")) == session_model.WORKING,
                      6.0, "Egret starts")
        yield 1.0
        yield from d.point(app.detail.control_centre("stop"))
        d.note(f"stop pressed while Egret was {d.state(d.box('Egret'))}")
        app.detail.stop()
        yield 4.0

        # -- 9. take control ---------------------------------------------------
        # Kestrel, because its page is one of ours: the runbook is called
        # "Runbook: payments-api Degraded" and says the word another five times,
        # so the find bar will certainly match.
        d.beat("take control: the real window, on the desktop, with the keyboard")
        app.show_overview()
        yield 1.2
        yield from d.open_box("Kestrel")
        yield 1.0
        yield from d.point(app.detail.control_centre("take control"))
        yield 0.5
        app.detail.take_control()
        yield 1.8
        # Chromium's own find bar: browser chrome, on a real page, answering a
        # real keyboard. Nothing about it can be mistaken for a picture of a
        # browser. The foreground is checked first -- keystrokes go wherever the
        # keyboard is, and being wrong means typing into someone else's window.
        if app.manager.holds_foreground(d.box("Kestrel")):
            tap(VK_F, ctrl=True)
            yield 0.8
            type_into_page(FIND_TERM)
            d.note(f'searched the summoned window for "{FIND_TERM}"')
            yield 2.5
            tap(VK_ESCAPE)
            yield 0.8
        else:
            d.note("Kestrel did not hold the foreground; skipped the keyboard")
            yield 2.0
        d.beat("look back at the dashboard and it parks itself")
        app.focus_window()   # what clicking the dashboard does
        yield 5.0

        # -- 10. the fleet comes back down --------------------------------------
        d.beat("close three; the grid comes back down")
        app.show_overview()
        yield 1.4
        for name in CLOSING:
            if d.box(name) is None:
                continue
            yield from d.open_box(name)
            yield 1.0
            yield from d.point(app.detail.control_centre("close box"))
            yield 0.4
            app.detail.close_box()
            yield 1.6
        d.note(f"{len(app.manager.boxes)} boxes left: "
               + ", ".join(box.name for box in app.manager.boxes))
        yield 2.5

        # -- 11. five real questions, five model loops ---------------------------
        staying = [name for name, _, _ in MODEL_TASKS if d.box(name) is not None]
        if claude:
            d.beat("same seam, different driver: Claude takes five boxes")
            for name in staying:
                swap_to_claude(app, d.box(name))
                d.note(f"{name}'s child is a Claude loop now")
                yield 0.3
            d.note("five model tasks - this is the part that costs money")
        else:
            d.beat("the same five questions, with the script still driving")
        yield 8.0

        d.beat("five boxes, five questions, at once")
        for name, key, prompt in MODEL_TASKS:
            d.send(name, prompt.format(url=url[key]))
            yield 0.6
        yield 13.0

        # One of them up close while the other four carry on behind it. Finch,
        # because its question needs two pages -- so its trajectory fills with
        # tool calls nobody scripted rather than one goto and an answer.
        d.beat("watch one of them think")
        yield from d.open_box("Finch")
        yield 12.0

        d.beat("the answers, and what they cost")
        yield d.settled(staying, timeout=CLAUDE_CAP_S)
        for name in staying:
            d.note(f"{name} ended {d.state(d.box(name))}")
        yield 7.0
        app.show_overview()
        yield 5.0

        # -- 12. out --------------------------------------------------------------
        d.beat("close the dashboard; every window goes with it")
        yield 8.5

    return script


# -- entry point -----------------------------------------------------------

USAGE = """usage: demo.py [--no-claude] [--pace X] [--agent script|demo|claude]

Drives the real dashboard through a scripted demo, for recording. Serves this
repo's own pages over local HTTP, and needs a network connection for the rest:
half of them are real websites.

  --no-claude   skip the model swap, the only thing here that spends money. The
                same five pages are still opened, by the demo agent. Rehearse
                with this.
  --pace X      multiply every hold by X (default 1.0). 1.3 is a calmer take.
  --agent KIND  what the fleet's children run (default demo). The model act
                swaps five boxes either way.
"""


def option(argv, flag, fallback):
    if flag not in argv:
        return fallback
    index = argv.index(flag)
    return argv[index + 1] if index + 1 < len(argv) else fallback


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(USAGE)
        return 0
    claude = "--no-claude" not in sys.argv
    pace = float(option(sys.argv, "--pace", "1.0"))
    kind = option(sys.argv, "--agent", "demo")

    if claude:
        # Fail here, rather than three minutes in with the camera running.
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("demo.py: the model act needs ANTHROPIC_API_KEY in this "
                  "terminal.\n         Set it, or run with --no-claude.")
            return 2
        try:
            import anthropic  # noqa: F401
        except ImportError:
            print("demo.py: the model act needs the anthropic package.\n"
                  "         pip install anthropic, or run with --no-claude.")
            return 2
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        if base_url and "api.anthropic.com" not in base_url:
            print(f"demo.py: warning - ANTHROPIC_BASE_URL is {base_url}, so the "
                  "boxes will not\n         be talking to the Anthropic API.")

    base, stop_serving = sites.serve()
    print(f"demo: serving this repo's pages at {base}")

    print("demo: checking the real sites are reachable...")
    probes = [REAL[key] for key in ("npr", "cnn", "cern", "rfc")]
    if claude:
        probes += [REAL[key] for key in ("hypervisor", "hn", "pathlib")]
    unreachable = [address for address in probes if not sites.reachable(address)]
    if unreachable:
        print("demo: warning - cannot reach " + ", ".join(unreachable)
              + "\n      half the pages here are real websites; without a "
                "network this records failures.")

    thumbs.set_dpi_awareness()
    config = load_config()
    config["agent"] = kind
    # The film opens on three boxes and grows to eight on camera. `config.json`
    # still says five, because `verify.py` is choreographed against it.
    config["boxes"] = list(AVIARY[:OPENING_BOXES])
    # Over HTTP rather than file://, because the address bar is on camera.
    #
    # One page for the whole fleet rather than a list, even though `start_url`
    # takes a list now: every box that has to ask something on camera must be one
    # that has never navigated, and giving boxes different landing pages would
    # mean tracking which index is still blank. The variety in this film comes
    # from the tasks, which is where it belongs.
    config["start_urls"] = [base + "/start.html"]

    manager = BoxManager(config)
    print(f"demo: launching {len(config['boxes'])} boxes, {kind} agent"
          f"{'' if claude else ', no paid act'}...")
    manager.start()
    if len(manager.boxes) < OPENING_BOXES:
        print(f"demo: this is choreographed for {OPENING_BOXES} boxes to start.")
        stop_serving()
        return 2
    if manager.max_boxes < OPENING_BOXES + ADDS:
        print(f"demo: max_boxes is {manager.max_boxes}; this film grows to "
              f"{OPENING_BOXES + ADDS}.")
        stop_serving()
        return 2

    app = App(manager)
    print("demo: recording can start now.\n")
    try:
        Director(app, pace).run(build_script(base, claude))
        app.run()
    finally:
        print("demo: closing boxes...")
        manager.close()
        stop_serving()
    return 0


if __name__ == "__main__":
    sys.exit(main())
