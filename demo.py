"""Drive the real dashboard through a fixed demo, for recording.

    .venv\\Scripts\\python.exe demo.py                 # the whole thing, ~2 minutes
    .venv\\Scripts\\python.exe demo.py --no-claude      # same, minus the paid finale
    .venv\\Scripts\\python.exe demo.py --pace 1.4       # hold every shot 40% longer

This is `main.py` with a director attached: the same `App`, the same boxes, the
same agent children. Nothing here is a mock. Every beat goes through the seam a
user's click would -- `detail.send()`, `overview.go_to_waiting()`,
`overview.add_box()` -- so what is recorded is the app working, not a re-enactment
of it.

Why a script rather than a live take: a person can only type into one box at a
time, which forces a demo of a parallel fleet to be narrated serially. The
director gives every box a task inside two seconds and then lets the grid diverge
on camera. That shot is the product, and it cannot be performed by hand.

Three pieces of stagecraft, all of them cosmetic:

  * the mouse pointer is glided onto a control with `SetCursorPos` a beat before
    the control is invoked, so actions look caused rather than spontaneous;
  * text is typed into the chat box a character at a time;
  * the pages are local `file://` fixtures written to the temp folder, so the
    trajectory says the same thing on every take. Chrome blocks top-frame
    navigation to `data:` URLs -- hence files.

Recording notes:

  * Capture the **display**, not the window. Tiles are DWM thumbnails and live
    only in the compositor's visual tree; a PrintWindow-based recorder gets empty
    rectangles where the tiles should be.
  * Do not touch the machine while it runs. The take-control beat summons a real
    window and hands it the keyboard, and a stray click parks it early.
  * Beat timings are printed to the console as they happen, and again as a
    summary at the end, for lining up narration. See `transcript.md`.

The paid beat is the last one, and it is one task on one box: the fleet runs on
the free scripted agent, and that box's child is swapped for a Claude one through
the ordinary constructor. `--no-claude` skips it, which is what rehearsals should
use -- a demo script gets run a dozen times before the take that gets kept.
"""

import ctypes
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

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
CLAUDE_CAP_S = 75      # give up waiting on the model rather than record a hang

VK_SHIFT = 0x10
KEYEVENTF_KEYUP = 0x0002


# -- the fixtures ----------------------------------------------------------

# name -> (title, accent, the label of the link the script will click)
SITES = {
    "docs": ("Acme - Docs", "#1f6f4e", "Getting started"),
    "changelog": ("Acme - Changelog", "#6b4f9c", "Release 4.2"),
    "status": ("Acme - Status", "#2b6ca3", "Incident history"),
    "blog": ("Acme - Blog", "#a35b2b", "How we park windows"),
    "pricing": ("Acme - Pricing", "#8a2f52", "Team plan details"),
}

OTHER_LINKS = ["Support", "Security", "Contact"]

PLANS = """
<table>
  <tr><th>Plan</th><th>Price</th><th>SSO</th><th>Audit log</th></tr>
  <tr><td>Starter</td><td>free</td><td>no</td><td>no</td></tr>
  <tr><td>Team</td><td>$20 per user / month</td><td><b>yes</b></td><td>no</td></tr>
  <tr><td>Business</td><td>$45 per user / month</td><td><b>yes</b></td><td>yes</td></tr>
  <tr><td>Enterprise</td><td>talk to us</td><td><b>yes</b></td><td>yes</td></tr>
</table>
<p>SSO is included from the Team plan upwards. Starter has no SSO.</p>
"""

STYLE = """
body {{ margin:0; font:16px/1.6 system-ui,sans-serif; color:#1b1b1b; }}
header {{ background:{accent}; color:#fff; padding:28px 40px; }}
header h1 {{ margin:0; font-size:34px; }}
main {{ padding:28px 40px; max-width:900px; }}
nav a {{ display:inline-block; margin-right:22px; font-size:18px; color:{accent}; }}
table {{ border-collapse:collapse; margin-top:18px; }}
td,th {{ border:1px solid #ccc; padding:8px 16px; text-align:left; }}
input {{ font-size:20px; padding:10px 14px; width:420px; margin-top:20px; }}
"""


def _page(accent, heading, body):
    return (
        "<!doctype html><meta charset='utf-8'>"
        + f"<title>{heading}</title>"
        + f"<style>{STYLE.format(accent=accent)}</style>"
        + f"<header><h1>{heading}</h1></header><main>{body}</main>"
    )


def fixtures():
    """Write the demo's pages and return {name: file:// uri}.

    Two pages per site: an index whose *first* link is the one the scripted agent
    will click, and the page that link leads to. The second page carries an
    autofocused text field, which is what the take-control beat types into -- a
    summoned window arrives with the page's focus where it left it, so nothing
    has to click into the page first.
    """
    folder = Path(tempfile.gettempdir()) / "multibox-demo"
    folder.mkdir(exist_ok=True)
    uris = {}
    for name, (title, accent, first) in SITES.items():
        labels = [first] + OTHER_LINKS
        links = "".join(
            f"<a href='{name}-2.html'>{label}</a>" if i == 0
            else f"<a href='{name}.html'>{label}</a>"
            for i, label in enumerate(labels)
        )
        body = f"<nav>{links}</nav>"
        subject = title.split("-")[-1].strip().lower()
        body += PLANS if name == "pricing" else f"<p>Everything about {subject}.</p>"
        (folder / f"{name}.html").write_text(
            _page(accent, title, body), encoding="utf-8"
        )
        detail = ("<p>Team is $20 per user / month and includes SSO.</p>"
                  if name == "pricing" else f"<p>{first}, in detail.</p>")
        (folder / f"{name}-2.html").write_text(
            _page(accent, first,
                  detail
                  + "<input autofocus placeholder='type here'>"
                  + f"<p><a href='{name}.html'>back</a></p>"),
            encoding="utf-8",
        )
        uris[name] = (folder / f"{name}.html").as_uri()
    return uris


# -- finding things on screen ----------------------------------------------

def find_button(widget, text):
    """A button by its label. The header buttons are packed inline and never
    kept, so going looking for one is the only way to point at it."""
    for child in widget.winfo_children():
        try:
            if str(child.cget("text")) == text:
                return child
        except Exception:
            pass
        found = find_button(child, text)
        if found is not None:
            return found
    return None


def widget_centre(widget):
    return (widget.winfo_rootx() + widget.winfo_width() // 2,
            widget.winfo_rooty() + widget.winfo_height() // 2)


def tile_centre(overview, index):
    """Screen centre of tile `index`; -1 is the add tile."""
    if not overview.tiles:
        return None
    tile = overview.tiles[index]
    return (overview.canvas.winfo_rootx() + (tile.thumb.left + tile.thumb.right) // 2,
            overview.canvas.winfo_rooty() + (tile.thumb.top + tile.thumb.bottom) // 2)


def type_into_page(text):
    """Real keystrokes into whatever holds the foreground.

    Only ever called with a box summoned and holding it -- the caller checks --
    because keystrokes go wherever the keyboard is, and being wrong about that
    means typing into someone else's window.
    """
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
        time.sleep(0.045)


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
        self.app.root.update_idletasks()
        if hasattr(target, "winfo_rootx"):
            target = widget_centre(target)
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
        entry = self.app.detail.entry
        entry.configure(state="normal")
        entry.focus_set()
        for char in text:
            entry.insert("end", char)
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
        self.app.root.after(400, self._advance)

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
            self.app.root.after(max(1, int(float(item) * 1000 * self.pace)),
                                self._advance)

    def _hold(self, wait):
        if wait.done():
            self.app.root.after(1, self._advance)
        elif wait.expired():
            if wait.label:
                self.note(f"gave up waiting: {wait.label}")
            self.app.root.after(1, self._advance)
        else:
            self.app.root.after(50, self._hold, wait)

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


def build_script(pages, claude=True):
    def script(d):
        app = d.app
        box1, box2, box3, box4, box5 = app.manager.boxes[:5]
        known = {box.name for box in app.manager.boxes}

        # -- 1. the fleet, doing nothing at all ---------------------------
        d.beat("overview - five live tiles, nothing needs you")
        yield 5.0

        # -- 2. four boxes at once ----------------------------------------
        # box4 is deliberately left alone: the stop beat needs a box whose child
        # has not started Playwright yet. See beat 6.
        d.beat("four boxes get a task inside two seconds")
        d.send(box1, f"open {pages['docs']} and tell me what is there")
        yield 0.45
        d.send(box2, f"take a look at {pages['changelog']}")
        yield 0.45
        d.send(box3, f"check {pages['status']}")
        yield 0.45
        # No URL anywhere in this one, and box5 is still on about:blank -- so it
        # has nothing to work with and has to come back and ask.
        d.send(box5, "compare the pricing tiers for me")

        # -- 3. the grid diverges on its own -------------------------------
        # Long enough that every child has answered with `working` before the
        # wait below asks -- otherwise "nobody is working" is briefly true for
        # the wrong reason and the beat ends before it starts.
        yield 0.8
        d.beat("states diverge: working to done, and one stops to ask")
        yield d.settled([box1, box2, box3], timeout=40.0)
        yield 4.0

        # -- 4. the box that is waiting on you -----------------------------
        d.beat("jump straight to the box that needs you")
        yield from d.point(app.overview.jump)
        yield 0.6
        app.overview.go_to_waiting()
        yield 2.0
        d.beat("answer its question; it carries on from there")
        yield from d.say(pages["pricing"])
        yield d.until(lambda: d.state(box5) == session_model.DONE, 40.0,
                      "box5 finishes")
        yield 4.0

        # -- 5. one box up close -------------------------------------------
        d.beat("detail view: live mirror, trajectory, chat")
        app.show_overview()
        yield 1.5
        yield from d.point(tile_centre(app.overview, 0))
        yield 0.6
        app.enter_detail(box1)
        yield 5.0

        # -- 6. stop --------------------------------------------------------
        # box4, the one left out of beat 2, and left out for this. Its child has
        # never run a task, so its first one spends a second or two importing
        # Playwright and attaching over CDP -- and that is the window Stop lands
        # in. On a warm child a local page is done in a few hundred milliseconds,
        # which is not something a demo can reliably catch, or a viewer see.
        d.beat("stop a run mid-flight")
        app.show_overview()
        yield 1.2
        yield from d.point(tile_centre(app.overview, 3))
        yield 0.5
        app.enter_detail(box4)
        yield 1.2
        yield from d.say(f"open {pages['blog']} and read it")
        yield d.until(lambda: d.state(box4) == session_model.WORKING, 5.0,
                      "box4 starts")
        yield 1.0
        yield from d.point(app.detail.stop_button)
        d.note(f"stop pressed while box4 was {d.state(box4)}")
        app.detail.stop()
        yield 4.0

        # -- 7. take control -------------------------------------------------
        d.beat("take control: the real window, on the desktop, with the keyboard")
        app.show_overview()
        yield 1.2
        yield from d.point(tile_centre(app.overview, 0))
        yield 0.5
        app.enter_detail(box1)
        yield 1.0
        yield from d.point(find_button(app.detail.frame, "Take control"))
        yield 0.5
        app.detail.take_control()
        yield 1.6
        if app.manager.holds_foreground(box1):
            type_into_page("typed into the real window")
        else:
            d.note("box1 did not hold the foreground; skipped typing")
        yield 2.2
        d.beat("look back at the dashboard and it parks itself")
        app.root.focus_force()   # what clicking the dashboard does
        yield 3.0

        # -- 8. the fleet changes size ---------------------------------------
        d.beat("+ Add box, live")
        app.show_overview()
        yield 1.2
        yield from d.point(tile_centre(app.overview, -1))
        yield 0.6
        app.overview.add_box()
        yield 1.8
        added = app.manager.boxes[-1]
        if added.name not in known:
            d.send(added, f"open {pages['status']}")
            yield d.settled([added], timeout=40.0)
            yield 3.0
            d.beat("close box: window, agent and conversation, gone")
            yield from d.point(tile_centre(app.overview,
                                           len(app.manager.boxes) - 1))
            yield 0.5
            app.enter_detail(added)
            yield 1.5
            yield from d.point(find_button(app.detail.frame, "Close box"))
            yield 0.5
            app.detail.close_box()
            yield 3.0
        else:
            d.note("no box was added; skipped the close-box beat")

        # -- 9. the paid finale ------------------------------------------------
        if claude:
            d.beat("same seam, different driver: Claude takes box2")
            yield from d.point(tile_centre(app.overview, 1))
            yield 0.5
            app.enter_detail(box2)
            yield 1.2
            swap_to_claude(app, box2)
            d.note("box2's child is a Claude loop now - this task costs money")
            yield 0.8
            # Something the fixed script cannot do: the answer is in the page, and
            # which plan qualifies is a judgement about what the page says.
            yield from d.say(
                f"go to {pages['pricing']} - which is the cheapest plan that "
                "includes SSO, and what does it cost?"
            )
            yield 2.0
            d.beat("the model picks its own tools, and reports what it cost")
            yield d.until(
                lambda: d.state(box2) in (session_model.DONE, session_model.FAILED,
                                          session_model.NEEDS_INPUT),
                CLAUDE_CAP_S, "box2's model turns")
            d.note(f"box2 ended {d.state(box2)}")
            yield 6.0

        # -- 10. out ------------------------------------------------------------
        d.beat("close the dashboard; every window goes with it")
        app.show_overview()
        yield 2.5

    return script


# -- entry point -----------------------------------------------------------

USAGE = """usage: demo.py [--no-claude] [--pace X] [--agent script|claude]

Drives the real dashboard through a scripted demo, for recording.

  --no-claude   skip the last beat, the only one that spends money. Rehearse
                with this.
  --pace X      multiply every hold by X (default 1.0). 1.3 is a calmer take.
  --agent KIND  what the fleet's children run (default script). The Claude beat
                swaps one box either way.
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
            print("demo.py: the Claude beat needs ANTHROPIC_API_KEY in this "
                  "terminal.\n         Set it, or run with --no-claude.")
            return 2
        try:
            import anthropic  # noqa: F401
        except ImportError:
            print("demo.py: the Claude beat needs the anthropic package.\n"
                  "         pip install anthropic, or run with --no-claude.")
            return 2

    pages = fixtures()
    thumbs.set_dpi_awareness()
    config = load_config()
    config["agent"] = kind
    manager = BoxManager(config)
    print(f"demo: launching {len(config['boxes'])} boxes, {kind} agent"
          f"{'' if claude else ', no paid beat'}...")
    manager.start()
    if len(manager.boxes) < 5:
        print("demo: this is choreographed for the five boxes in config.json.")
        return 2
    app = App(manager)
    print("demo: recording can start now.\n")
    try:
        Director(app, pace).run(build_script(pages, claude))
        app.run()
    finally:
        print("demo: closing boxes...")
        manager.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
