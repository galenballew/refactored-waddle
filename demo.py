"""Drive the real dashboard through a fixed demo, for recording.

    .venv\\Scripts\\python.exe demo.py                 # the whole thing, ~2.5 minutes
    .venv\\Scripts\\python.exe demo.py --no-claude      # same, minus the paid act
    .venv\\Scripts\\python.exe demo.py --pace 1.4       # hold every shot 40% longer

This is `main.py` with a director attached: the same `App`, the same boxes, the
same agent children. Nothing here is a mock. Every beat goes through the seam a
user's click would -- `detail.send()`, `overview.go_to_waiting()`,
`overview.add_box()` -- so what is recorded is the app working, not a re-enactment
of it.

Why a script rather than a live take: a person can only type into one box at a
time, which forces a demo of a parallel fleet to be narrated serially. The
director gives three boxes a task inside two seconds and then lets the grid
diverge on camera. That shot is the product, and it cannot be performed by hand.

**The pages are real websites, and that is the point.** These are ordinary
Chromium windows on the ordinary internet: Wikipedia, Hacker News, the Python
docs, MDN. Nothing here logs in, submits a form, or changes anything -- the demo
reads pages and clicks links, which is all the agents can do. It needs a working
network connection, and `main()` says so before it launches anything rather than
recording five boxes failing to load.

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

The paid act is the last one, and it is **three tasks on three boxes**: the fleet
runs on the free scripted agent, and those boxes' children are swapped for Claude
ones through the ordinary constructor. `--no-claude` skips the swap and sends the
same three prompts to the scripted agents instead, which still opens all three
sites for real -- that is what rehearsals should use, because a demo script gets
run a dozen times before the take that gets kept.
"""

import ctypes
import os
import socket
import sys
import time
import traceback
from urllib.parse import urlparse

import session as session_model
import thumbs
from agents import Agent
from boxes import BoxManager, load_config
from ui.app import App

user32 = ctypes.windll.user32

# -- stagecraft ------------------------------------------------------------

GLIDE_MS = 22          # one hop of the pointer on its way to a control
GLIDE_HOPS = 14
KEY_MS = 38            # per character in the chat box
PAGE_KEY_S = 0.045     # per character into a real browser window
CLAUDE_CAP_S = 120     # give up waiting on the models rather than record a hang

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_F = 0x46
KEYEVENTF_KEYUP = 0x0002


# -- the web ---------------------------------------------------------------

# Real sites, picked for being stable, readable without an account, plain enough
# to stay legible in a tile, and content nobody minds a browser reading a few
# times per take. Nothing in this demo signs in, fills in a form, or writes
# anything anywhere.
#
# They are in two groups, and the split is not cosmetic. `BrowserAgent` clicks
# `a[href]` *first*, and on most modern sites the first anchor in the DOM is a
# visually hidden "Skip to content" link -- Wikipedia, MDN and the Python docs
# all have one. Playwright waits for a hidden element to become actionable,
# times out, and the box ends `failed`. So the boxes driven by the script get
# pages whose first link is really on the page, and the ones driven by the model
# can have anything: it clicks by visible text and never touches a skip link.
SCRIPTED_PAGES = {
    "npr": "https://text.npr.org",          # first link goes to the full site
    "cnn": "https://lite.cnn.com",          # first link is the CNN wordmark
    "cern": "https://info.cern.ch/hypertext/WWW/TheProject.html",
    "example": "https://example.com",       # first link goes to iana.org
    "rfc": "https://www.rfc-editor.org/rfc/rfc1149.html",
}

MODEL_PAGES = {
    "hypervisor": "https://en.wikipedia.org/wiki/Hypervisor",
    "hn": "https://news.ycombinator.com",
    "pathlib": "https://docs.python.org/3/library/pathlib.html",
}

PAGES = {**SCRIPTED_PAGES, **MODEL_PAGES}

# The opening fan-out: three real sites, three boxes, one script each. The
# scripted agent can do this much -- find the URL, open it, look at it, click the
# first link -- and doing it on the real internet is the point of the shot. NPR
# is first because its first link leads to the full site, so that tile turns from
# a page of text into an ordinary news homepage while you watch.
OPENING = [
    ("npr", "open {url} and tell me what is there"),
    ("cnn", "take a look at {url}"),
    ("cern", "check {url}"),
]

# A word that is certainly rendered on lite.cnn.com, because the scripted agent
# clicked a link whose label was exactly this. The take-control beat types it
# into Chromium's find bar, and a find that matches nothing would read as a
# broken browser rather than a real one.
FIND_TERM = "CNN"

# The model act: three real sites again, but questions the fixed script cannot
# answer. Each one needs the page read and a judgement about what it says, and
# each answer is checkable by anyone watching the recording.
MODEL_TASKS = [
    ("hypervisor",
     "go to {url} - what is the difference between a type 1 and a type 2 "
     "hypervisor, in one sentence, and name an example of each from the page"),
    ("hn",
     "go to {url} - which story on the front page has the most points right "
     "now, and how many comments does it have?"),
    ("pathlib",
     "go to {url} - which method writes text to a file, and what does it do if "
     "the file is already there?"),
]


def reachable(url, timeout=4.0):
    """Can this machine open a socket to that host at all?

    A demo about web browsers with no network is not a demo with one broken beat,
    it is a recording of five boxes failing. Worth four seconds up front.
    """
    parts = urlparse(url)
    port = 443 if parts.scheme == "https" else 80
    try:
        with socket.create_connection((parts.hostname, port), timeout):
            return True
    except OSError:
        return False


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
    """Runs a generator of beats on the Tk thread.

    The script yields either a number of seconds to hold, or a `Wait`. Everything
    else it does is an ordinary call into the app, which is the point: if a beat
    can be performed from here it could be performed by a user, and if it cannot
    it does not belong in the demo.

    On the Tk thread and never off it, like everything else in this app -- the
    beats are `root.after` callbacks, so the layout tick and the pump keep running
    between them and the tiles never stop being live.
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

    def beat(self, name):
        self.marks.append((self.stamp(), name))
        print(f"  [{self.stamp():>5}]  {name}", flush=True)

    def note(self, text):
        print(f"           . {text}", flush=True)

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

    def session(self, box):
        return self.app.sessions[box.name]

    def state(self, box):
        return self.session(box).state

    def send(self, box, text):
        """What the chat box does, for a box we are not looking at."""
        self.app.send(box, text)
        if self.app.view is not None:
            self.app.view.sync()

    def say(self, text):
        """Type it and press Send, in the detail view, like a person would."""
        yield from self.point(self.app.detail.entry)
        yield from self.type(text)
        yield 0.35
        yield from self.point(self.app.detail.send_button)
        yield 0.2
        self.app.detail.send()

    def until(self, predicate, timeout=30.0, label=""):
        return Wait(predicate, timeout, label)

    def settled(self, boxes, timeout=30.0):
        """Every one of them has stopped working."""
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
            print(f"    {stamp:>5}  {name}", flush=True)
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


def build_script(claude=True):
    def script(d):
        app = d.app
        box1, box2, box3, box4, box5 = app.manager.boxes[:5]
        working = [box1, box2, box3]
        known = {box.name for box in app.manager.boxes}

        # -- 1. the fleet, doing nothing at all ---------------------------
        d.beat("overview - five live tiles, nothing needs you")
        yield 5.0

        # -- 2. three real websites, at once -------------------------------
        # box4 is deliberately left alone: the stop beat needs a box whose child
        # has not started Playwright yet. See beat 7.
        d.beat("three boxes open three real websites at once")
        for box, (key, prompt) in zip(working, OPENING):
            d.send(box, prompt.format(url=PAGES[key]))
            yield 0.5
        # No URL anywhere in this one, and box5 is still on about:blank -- so it
        # has nothing to work with and has to come back and ask.
        d.send(box5, "tell me what the first paragraph says")

        # -- 3. the grid diverges on its own -------------------------------
        # Long enough that every child has answered with `working` before the
        # wait below asks -- otherwise "nobody is working" is briefly true for
        # the wrong reason and the beat ends before it starts.
        yield 0.8
        d.beat("states diverge: working to done, and one stops to ask")
        yield d.settled(working, timeout=60.0)
        yield 5.0

        # -- 4. the box that is waiting on you -----------------------------
        d.beat("jump straight to the box that needs you")
        yield from d.point(app.overview.control_centre("jump"))
        yield 0.6
        app.overview.go_to_waiting()
        yield 2.0
        d.beat("answer its question; it carries on from there")
        yield from d.say(PAGES["example"])
        yield d.until(lambda: d.state(box5) == session_model.DONE, 60.0,
                      "box5 finishes")
        yield 4.0

        # -- 5. one box up close -------------------------------------------
        d.beat("detail view: live mirror, trajectory, chat")
        app.show_overview()
        yield 1.5
        yield from d.point(app.overview.tile_centre(0))
        yield 0.6
        app.enter_detail(box1)
        yield 5.5

        # -- 6. stop --------------------------------------------------------
        # box4, the one left out of beat 2, and left out for this. Its child has
        # never run a task, so its first one spends a second or two importing
        # Playwright and attaching over CDP -- and that is the window Stop lands
        # in. On a warm child the cancel would arrive after the run was over.
        # The URL is one the script could finish, so a stop that misses records a
        # tidy run rather than a failure.
        d.beat("stop a run mid-flight")
        app.show_overview()
        yield 1.2
        yield from d.point(app.overview.tile_centre(3))
        yield 0.5
        app.enter_detail(box4)
        yield 1.2
        yield from d.say(f"open {PAGES['rfc']} and read it")
        yield d.until(lambda: d.state(box4) == session_model.WORKING, 5.0,
                      "box4 starts")
        yield 1.0
        yield from d.point(app.detail.control_centre("stop"))
        d.note(f"stop pressed while box4 was {d.state(box4)}")
        app.detail.stop()
        yield 4.0

        # -- 7. take control -------------------------------------------------
        # box2, because its page is the one whose text is known: the script
        # clicked a link there labelled FIND_TERM, so the find bar will match.
        d.beat("take control: the real window, on the desktop, with the keyboard")
        app.show_overview()
        yield 1.2
        yield from d.point(app.overview.tile_centre(1))
        yield 0.5
        app.enter_detail(box2)
        yield 1.0
        yield from d.point(app.detail.control_centre("take control"))
        yield 0.5
        app.detail.take_control()
        yield 1.8
        # Chromium's own find bar: browser chrome, on a real page, answering a
        # real keyboard. Nothing about it can be mistaken for a picture of a
        # browser. The foreground is checked first -- keystrokes go wherever the
        # keyboard is, and being wrong means typing into someone else's window.
        if app.manager.holds_foreground(box2):
            tap(VK_F, ctrl=True)
            yield 0.8
            type_into_page(FIND_TERM)
            d.note(f'searched the summoned window for "{FIND_TERM}"')
            yield 2.5
            tap(VK_ESCAPE)
            yield 0.8
        else:
            d.note("box2 did not hold the foreground; skipped the keyboard")
            yield 2.0
        d.beat("look back at the dashboard and it parks itself")
        app.focus_window()   # what clicking the dashboard does
        yield 3.0

        # -- 8. the fleet changes size ---------------------------------------
        d.beat("+ Add box, live")
        app.show_overview()
        yield 1.2
        yield from d.point(app.overview.tile_centre(-1))
        yield 0.6
        app.overview.add_box()
        yield 1.8
        added = app.manager.boxes[-1]
        if added.name not in known:
            d.send(added, f"open {PAGES['rfc']}")
            yield d.settled([added], timeout=60.0)
            yield 3.0
            d.beat("close box: window, agent and conversation, gone")
            yield from d.point(
                app.overview.tile_centre(len(app.manager.boxes) - 1))
            yield 0.5
            app.enter_detail(added)
            yield 1.5
            yield from d.point(app.detail.control_centre("close box"))
            yield 0.5
            app.detail.close_box()
            yield 3.0
        else:
            d.note("no box was added; skipped the close-box beat")

        # -- 9. three real sites, three hard questions -------------------------
        if claude:
            d.beat("same seam, different driver: Claude takes three boxes")
            for box in working:
                swap_to_claude(app, box)
                d.note(f"{box.name}'s child is a Claude loop now")
                yield 0.4
            d.note("three model tasks - this is the part that costs money")
        else:
            d.beat("the same three questions, with the script still driving")
        yield 1.0

        d.beat("three boxes, three real sites, three questions at once")
        for box, (key, prompt) in zip(working, MODEL_TASKS):
            d.send(box, prompt.format(url=PAGES[key]))
            yield 0.6
        yield 8.0

        # One of them up close while the other two carry on behind it.
        d.beat("watch one of them think")
        yield from d.point(app.overview.tile_centre(1))
        yield 0.5
        app.enter_detail(box2)
        yield 10.0

        d.beat("the answers, and what they cost")
        yield d.settled(working, timeout=CLAUDE_CAP_S)
        for box in working:
            d.note(f"{box.name} ended {d.state(box)}")
        yield 7.0
        app.show_overview()
        yield 5.0

        # -- 10. out ------------------------------------------------------------
        d.beat("close the dashboard; every window goes with it")
        yield 2.5

    return script


# -- entry point -----------------------------------------------------------

USAGE = """usage: demo.py [--no-claude] [--pace X] [--agent script|claude]

Drives the real dashboard through a scripted demo, for recording. Needs a
network connection: the pages are real websites.

  --no-claude   skip the model swap, the only thing here that spends money. The
                three real sites are still opened, by the script. Rehearse with
                this.
  --pace X      multiply every hold by X (default 1.0). 1.3 is a calmer take.
  --agent KIND  what the fleet's children run (default script). The model act
                swaps three boxes either way.
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
    kind = option(sys.argv, "--agent", "script")

    if claude:
        # Fail here, rather than two minutes in with the camera running.
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
        base = os.environ.get("ANTHROPIC_BASE_URL")
        if base and "api.anthropic.com" not in base:
            print(f"demo.py: warning - ANTHROPIC_BASE_URL is {base}, so the "
                  "boxes will not\n         be talking to the Anthropic API.")

    print("demo: checking the sites are reachable...")
    probes = [PAGES["npr"], PAGES["cnn"], PAGES["cern"]]
    if claude:
        probes += [PAGES["hypervisor"], PAGES["hn"], PAGES["pathlib"]]
    unreachable = [url for url in probes if not reachable(url)]
    if unreachable:
        print("demo: warning - cannot reach " + ", ".join(unreachable)
              + "\n      the pages are real websites; without a network this "
                "records five failures.")

    thumbs.set_dpi_awareness()
    config = load_config()
    config["agent"] = kind
    manager = BoxManager(config)
    print(f"demo: launching {len(config['boxes'])} boxes, {kind} agent"
          f"{'' if claude else ', no paid act'}...")
    manager.start()
    if len(manager.boxes) < 5:
        print("demo: this is choreographed for the five boxes in config.json.")
        return 2
    app = App(manager)
    print("demo: recording can start now.\n")
    try:
        Director(app, pace).run(build_script(claude))
        app.run()
    finally:
        print("demo: closing boxes...")
        manager.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
