"""Drive the real dashboard through the demo reel, for recording.

    .venv\\Scripts\\python.exe demo.py                 # the whole thing, ~2.5 minutes
    .venv\\Scripts\\python.exe demo.py --no-claude      # same, minus the paid act
    .venv\\Scripts\\python.exe demo.py --pace 1.3       # hold every shot 30% longer

This is `main.py` with a director attached: the same `App`, the same boxes, the
same agent children. Nothing here is a mock.

**It is a reel, not a walkthrough.** Two and a half minutes, six beats, and the
only things in it are the ones that say what this is for: a fleet working at
once, a box that stops and asks you something, the real window when a mirror is
not enough, and a model driving the same seam a script was driving a minute
earlier. Everything else the app can do -- stopping a run, closing a box, the
grid reflowing three times -- is true, useful, and cut. `storyboard.md` says what
was cut and why; `transcript.md` is what is said over it.

**The cursor is real, because the film is a recording of a cursor.** Every
control the reel presses is pressed: the pointer travels to it and the left
button goes down and up, through `clicks.py`, and Windows delivers it to the
dashboard's own widget. Editors track that cursor, and a demo that changes the
app by calling its methods produces footage where things happen and nothing
moves. Between beats the pointer drifts across the grid rather than parking, so
there is always something to follow.

The one thing that is not a click is **the fan-out**, and it cannot be. Six boxes
get a task inside three seconds; a person can only type into one box at a time,
which is exactly why a fleet is worth having and exactly why that shot cannot be
performed by hand. It goes through `App.send`, the same call the chat box makes.
Nothing else in the film is cast that way.

**Half the pages are invented and half are real.** The real ones -- NPR, CNN, the
first website ever published at CERN, Wikipedia, Hacker News, the Python docs --
are the point: ordinary Chromium windows on the ordinary internet, and nothing
here logs in, submits a form or changes anything. The invented ones are Pinion
Ops, served from `sites/` over local HTTP by this file, and they buy two things
the real internet cannot: content that does not move between takes, so the
narration can name an answer out loud, and a URL that answers 404 on purpose,
which is where the failed tile comes from -- a real HTTP response, not a staged
state.

Recording notes:

  * Capture the **display**, not the window. Tiles are DWM thumbnails and live
    only in the compositor's visual tree; a PrintWindow-based recorder gets empty
    rectangles where the tiles should be.
  * Do not touch the machine while it runs. Synthetic clicks land wherever the
    pointer is, on whatever window is in front -- the director checks
    `App.holds_foreground()` before every one of them, but a hand on the mouse
    beats any check.
  * Beat timings are printed to the console as they happen, and again as a
    summary at the end, for lining up narration.

The paid act is the last one, and it is three boxes swapped for Claude children
through the ordinary constructor. `--no-claude` skips the swap and sends the same
three questions to the demo agents instead, which still opens all three pages for
real -- that is what rehearsals should use, because a demo script gets run a dozen
times before the take that gets kept.
"""

import os
import sys
import time
import traceback

import clicks
import session as session_model
import sites
import thumbs
from agents import Agent
from boxes import AVIARY, BoxManager, load_config
from ui.app import App

# -- stagecraft ------------------------------------------------------------

GLIDE_MS = 20          # one hop of the pointer on its way to a control
GLIDE_HOPS = 14
DRIFT_MS = 34          # one hop of an idle pointer wandering the grid
KEY_MS = 40            # per character in the chat box
CLAUDE_CAP_S = 120     # give up waiting on the models rather than record a hang

FLEET = 5              # what config.json launches; one more is added on camera


# -- the web ---------------------------------------------------------------

REAL = {
    "npr": "https://text.npr.org",
    "cnn": "https://lite.cnn.com",
    "cern": "https://info.cern.ch/hypertext/WWW/TheProject.html",
    "hypervisor": "https://en.wikipedia.org/wiki/Hypervisor",
    "hn": "https://news.ycombinator.com",
    "pathlib": "https://docs.python.org/3/library/pathlib.html",
}

PINION = {
    "status": "/pinion/",
    "tickets": "/pinion/tickets",
    "changelog": "/pinion/changelog",
    "inventory": "/pinion/inventory",
    "runbook": "/pinion/runbook",
    # Not a page. One box is sent here so one tile really fails.
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

# The fan-out: six boxes, six tasks, three seconds. Three of these pages are
# ours and two are the real internet, and the sixth names no page at all.
#
# **A box only asks when it has nothing at all to work with.** A task naming no
# URL uses the page the box already has; only a box that has never navigated --
# still on its start page -- comes back and asks. Kestrel was added forty seconds
# ago and has been nowhere, which is what makes it the one that can ask.
FAN_OUT = [
    ("Wren", "status", "open {url} and tell me what is there"),
    ("Finch", "tickets", "take a look at {url}"),
    ("Swift", "npr", "check {url}"),
    ("Heron", "cnn", "open {url} and tell me what is there"),
    ("Robin", "deploy", "check {url}"),          # 404s, and the box says so
]
ASKS = ("Kestrel", "pull up the runbook for the payments incident")

# What the waiting box is answered with, typed into its chat a character at a
# time. Also the page the take-control beat then works on.
ANSWER = "runbook"

# The model act: three real questions on three pages. One of them is ours, so its
# answer is the same in every take and the narration can say what it is; the
# other two are the real internet, which is the opposite point.
MODEL_TASKS = [
    ("Wren", "tickets",
     "go to {url} - what is the oldest unassigned P1, and which service is it "
     "filed against?"),
    ("Finch", "hypervisor",
     "go to {url} - what is the difference between a type 1 and a type 2 "
     "hypervisor, in one sentence, with an example of each from the page"),
    ("Swift", "pathlib",
     "go to {url} - which method writes text to a file, and what does it do if "
     "the file is already there?"),
]


# Where things are on screen is the views' business: `tile_centre` and
# `control_centre` on each of them, answering in physical pixels because that is
# what the mouse wants. This file does not know what the dashboard is built out
# of, which is the only reason a toolkit change did not rewrite it.


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
    else it does is a click, a keystroke, or one call into the app -- and the
    rule is that the first two are preferred: if a beat can be performed with the
    mouse it is, and the exceptions are named where they happen.

    On the UI thread and never off it, like everything else in this app -- the
    beats are `app.schedule` callbacks, so the layout tick and the pump keep
    running between them and the tiles never stop being live.
    """

    def __init__(self, app, pace=1.0):
        self.app = app
        self.pace = pace
        self.started = 0.0
        self.marks = []
        self.missed = 0
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

        Anything quoted back from the UI would otherwise raise from `print`, and
        an exception in a beat ends the film.
        """
        return str(text).encode("ascii", "replace").decode("ascii")

    def beat(self, name):
        self.marks.append((self.stamp(), name))
        print(f"  [{self.stamp():>5}]  {self._console(name)}", flush=True)

    def note(self, text):
        print(f"           . {self._console(text)}", flush=True)

    # -- the mouse --------------------------------------------------------

    def point(self, target):
        """Glide the pointer onto a control, so the next thing has a cause."""
        self.app.flush()
        for _ in clicks.glide(target, GLIDE_HOPS):
            yield GLIDE_MS / 1000.0

    def click(self, target, label=""):
        """Travel there and press it, for real.

        Checked first, because a synthetic click is not addressed to anything:
        it lands on whatever window is under the pointer. If the dashboard is not
        in front the click is skipped and said out loud rather than fired into
        somebody else's window.
        """
        yield from self.point(target)
        yield 0.18
        if target is None:
            self.note(f"no control to click: {label or 'unnamed'}")
            return
        if not self.app.holds_foreground():
            self.missed += 1
            self.note(f"dashboard was not in front; did not click {label}")
            return
        clicks.press()
        yield 0.25

    def double_click(self, target, label=""):
        yield from self.point(target)
        yield 0.18
        if target is None or not self.app.holds_foreground():
            self.missed += 1
            self.note(f"dashboard was not in front; did not open {label}")
            return
        clicks.double_press()
        yield 0.3

    def drift(self, targets, seconds):
        """Wander the pointer across the grid while the fleet works.

        Scaled by `pace` like every other hold: this one is bounded by the clock
        rather than by a yielded number, so it would otherwise be the one part of
        a slower take that did not slow down.

        The alternative is a cursor parked in a corner for forty seconds, which
        is dead footage for anything tracking it -- and drifting over tiles lifts
        their frames on the way past, which is the app's own hover state doing
        the work.
        """
        deadline = time.monotonic() + seconds * self.pace
        index = 0
        while time.monotonic() < deadline and targets:
            target = targets[index % len(targets)]
            index += 1
            for _ in clicks.glide(target, hops=26, ease=2):
                if time.monotonic() >= deadline:
                    return
                yield DRIFT_MS / 1000.0
            yield 0.4

    def type(self, text):
        """Into the chat box, one character a beat, on the real keyboard.

        The input was clicked a moment ago so it holds the keyboard. Verified
        afterwards rather than assumed: if the characters went somewhere else the
        beat falls back to the view's own `type_char`, because a chat box that
        stays empty while the narration says a URL was typed is worse than a
        keystroke nobody saw.
        """
        for char in text:
            clicks.send_char(char)
            yield KEY_MS / 1000.0
        if self.app.detail.entry_text() != text:
            self.note("the keyboard did not land in the chat box; typing it in")
            self.app.detail.clear_entry()
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

    def tile(self, name):
        box = self.box(name)
        if box is None:
            return None
        return self.app.overview.tile_centre(self.app.manager.boxes.index(box))

    def state(self, box):
        return self.app.sessions[box.name].state

    def send(self, name, text):
        """The one thing here that is not a click. See the module docstring."""
        box = self.box(name)
        if box is None:
            self.note(f"no box called {name}; skipped")
            return None
        self.app.send(box, text)
        if self.app.view is not None:
            self.app.view.sync()
        return box

    def open_box(self, name):
        """Double-click a tile open, like a person would."""
        yield from self.double_click(self.tile(name), label=name)
        yield 0.4
        if self.app.box is None or self.app.box.name != name:
            # The click missed, or landed while another window was in front.
            # Say so and get there anyway: a reel that stops halfway is worse
            # than one beat that did not photograph well.
            self.note(f"opening {name} directly")
            box = self.box(name)
            if box is not None:
                self.app.enter_detail(box)

    def until(self, predicate, timeout=30.0, label=""):
        return Wait(predicate, timeout, label)

    def settled(self, names, timeout=30.0):
        """Every one of them has stopped working."""
        boxes = [b for b in (self.box(n) for n in names) if b is not None]
        return self.until(
            lambda: all(self.state(b) != session_model.WORKING for b in boxes),
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
        if self.missed:
            print(f"  {self.missed} click(s) skipped - the dashboard was not in "
                  "front. Do not use this take.", flush=True)
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
        working = [name for name, _, _ in FAN_OUT]

        # -- 1. what it is -------------------------------------------------
        d.beat("five live windows, one dashboard")
        yield 3.0
        yield from d.drift([d.tile("Finch"), d.tile("Heron")], 6.0)

        # -- 2. the fleet is not a fixed size ------------------------------
        d.beat("one more, on camera")
        yield from d.click(app.overview.tile_centre(-1), label="add box")
        yield d.until(lambda: len(app.manager.boxes) > FLEET, 25.0, "the box to launch")
        d.note(f"{len(app.manager.boxes)} boxes: "
               + ", ".join(b.name for b in app.manager.boxes))
        yield 3.5

        # -- 3. six at once ------------------------------------------------
        d.beat("six tasks, three seconds")
        for name, key, prompt in FAN_OUT:
            d.send(name, prompt.format(url=url[key]))
            yield 0.45
        d.send(ASKS[0], ASKS[1])
        yield 1.5
        # The pointer keeps moving while nobody is driving. Forty seconds of a
        # parked cursor is dead footage for anything tracking it.
        yield from d.drift([d.tile(n) for n in ("Swift", "Robin", "Wren", "Heron")], 12.0)
        yield d.settled(working, timeout=75.0)
        d.note("counts: " + ", ".join(f"{n} {s}" for s, n
                                      in app.state_counts().items() if n))
        yield from d.drift([d.tile("Kestrel"), d.tile("Robin")], 5.0)

        # -- 4. one of them wants you --------------------------------------
        d.beat("the one that needs you, and answering it")
        yield from d.click(app.overview.control_centre("jump"), label="jump")
        yield 1.6
        if app.box is None:
            d.note("the jump button did not take; opening Kestrel directly")
            app.enter_detail(d.box("Kestrel"))
            yield 1.0
        yield from d.click(app.detail.control_centre("input"), label="the chat box")
        yield from d.type(url[ANSWER])
        yield 0.4
        yield from d.click(app.detail.control_centre("send"), label="send")
        yield d.until(lambda: d.state(d.box("Kestrel")) == session_model.DONE,
                      60.0, "Kestrel finishes")
        yield 3.0

        # -- 5. the real window --------------------------------------------
        # Kestrel is on the runbook now, because that is what it was answered
        # with -- and the runbook says FIND_TERM six times, so the find bar will
        # certainly match. A find that matches nothing reads as a broken browser.
        d.beat("take control: the real window, with the keyboard")
        yield from d.click(app.detail.control_centre("take control"),
                           label="take control")
        yield 1.8
        if app.manager.holds_foreground(d.box("Kestrel")):
            clicks.tap(clicks.VK_F, ctrl=True)
            yield 0.8
            clicks.type_text(FIND_TERM)
            d.note(f'searched the summoned window for "{FIND_TERM}"')
            yield 2.2
            clicks.tap(clicks.VK_ESCAPE)
            yield 0.7
        else:
            d.note("Kestrel did not hold the foreground; skipped the keyboard")
            yield 2.0
        # Not a click: the dashboard is behind a browser window, so a click here
        # would land on the page. This is what clicking the dashboard does.
        app.focus_window()
        yield 2.2
        # Back to the grid before anything else is clicked. Tile coordinates only
        # mean something while the overview is showing -- pressing one from the
        # detail view lands on whatever widget happens to be there, which is a
        # click that does nothing and still looks about right.
        yield from d.click(app.detail.control_centre("back"), label="back")
        yield 1.2

        # -- 6. and when a script is not enough ----------------------------
        staying = [name for name, _, _ in MODEL_TASKS if d.box(name) is not None]
        if claude:
            d.beat(f"same seam, different driver: Claude takes {len(staying)} boxes")
            for name in staying:
                swap_to_claude(app, d.box(name))
            d.note("three model tasks - this is the part that costs money")
        else:
            d.beat("the same three questions, with the script still driving")
        yield 1.0

        d.beat("three questions no script could answer")
        for name, key, prompt in MODEL_TASKS:
            d.send(name, prompt.format(url=url[key]))
            yield 0.5
        yield 3.0
        yield from d.drift([d.tile("Finch"), d.tile("Swift")], 5.0)
        # One of them up close while the other two work behind it.
        yield from d.open_box("Wren")
        yield 9.0
        yield d.settled(staying, timeout=CLAUDE_CAP_S)
        for name in staying:
            d.note(f"{name} ended {d.state(d.box(name))}")
        yield 5.0

        # -- 7. out ---------------------------------------------------------
        d.beat("close the dashboard; every window goes with it")
        yield from d.click(app.detail.control_centre("back"), label="back")
        yield 5.0

    return script


# -- entry point -----------------------------------------------------------

USAGE = """usage: demo.py [--no-claude] [--pace X] [--agent script|demo|claude]

Drives the real dashboard through the demo reel, for recording. Serves this
repo's own pages over local HTTP, and needs a network connection for the rest:
half of them are real websites.

  --no-claude   skip the model swap, the only thing here that spends money. The
                same three pages are still opened, by the demo agent. Rehearse
                with this.
  --pace X      multiply every hold by X (default 1.0). 1.3 is a calmer take.
  --agent KIND  what the fleet's children run (default demo). The model act
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
    kind = option(sys.argv, "--agent", "demo")

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
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        if base_url and "api.anthropic.com" not in base_url:
            print(f"demo.py: warning - ANTHROPIC_BASE_URL is {base_url}, so the "
                  "boxes will not\n         be talking to the Anthropic API.")

    base, stop_serving = sites.serve()
    print(f"demo: serving this repo's pages at {base}")

    print("demo: checking the real sites are reachable...")
    probes = [REAL[key] for key in ("npr", "cnn")]
    if claude:
        probes += [REAL[key] for key in ("hypervisor", "pathlib")]
    unreachable = [address for address in probes if not sites.reachable(address)]
    if unreachable:
        print("demo: warning - cannot reach " + ", ".join(unreachable)
              + "\n      half the pages here are real websites; without a "
                "network this records failures.")

    thumbs.set_dpi_awareness()
    config = load_config()
    config["agent"] = kind
    config["boxes"] = list(AVIARY[:FLEET])
    # Over HTTP rather than file://, because the address bar is on camera.
    #
    # One page for the whole fleet rather than a list, even though `start_url`
    # takes a list now: the box that asks for a URL on camera has to be one that
    # has never navigated, and giving boxes different landing pages would mean
    # tracking which of them is still blank.
    config["start_urls"] = [base + "/start.html"]

    manager = BoxManager(config)
    print(f"demo: launching {len(config['boxes'])} boxes, {kind} agent"
          f"{'' if claude else ', no paid act'}...")
    manager.start()
    if len(manager.boxes) < FLEET:
        print(f"demo: this reel is choreographed for {FLEET} boxes to start.")
        stop_serving()
        return 2
    if manager.max_boxes <= FLEET:
        print(f"demo: max_boxes is {manager.max_boxes}; the reel adds one more.")
        stop_serving()
        return 2

    app = App(manager)
    print("demo: recording can start now. Do not touch the mouse.\n")
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
