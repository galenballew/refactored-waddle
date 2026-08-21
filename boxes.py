"""One Playwright browser launch per box, so every box gets its own OS window.

Nothing is shared between boxes -- separate launch, separate page, separate
process tree. Profiles are ephemeral (Playwright's own temp dir); this is a
window manager, not an isolation boundary.

A box is *parked* when its window sits clear of every monitor and out of the
taskbar and Alt-Tab, and *summoned* when the user has clicked its tile and it has
come onto the desktop to be used. At most one box is ever summoned. Parked is not
hidden: the window stays composited, which is the only reason its tile keeps
updating.
"""

import json
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from playwright.sync_api import sync_playwright

import layout
import winfocus

CONFIG_PATH = Path(__file__).with_name("config.json")

# The aviary, in order. Species rather than numbers because a name you can say
# is easier to hold than an index -- "wren is waiting" beats "box 1 is waiting"
# -- and every caption in the app is a name first.
#
# The order is the list's, and that is the whole point of writing it down: the
# birds have no natural sequence, so without a fixed one "which box is third"
# would stop having an answer. Chosen to be short enough for a caption, and no
# two of the first twelve share a first letter, which is as far as `max_boxes`
# reaches by default.
AVIARY = (
    # The first twenty-two have twenty-two different initials, so a name is
    # never one glance away from another one.
    "wren", "finch", "swift", "heron", "robin", "kestrel",
    "plover", "egret", "magpie", "tern", "osprey", "curlew",
    "jay", "ibis", "avocet", "bittern", "godwit", "quail",
    "vireo", "nightjar", "dove", "lark",
    # Past here initials start repeating, which only matters once someone has
    # raised `max_boxes` well beyond its default of twelve.
    "raven", "snipe", "crane", "kite", "hawk", "starling", "dunlin", "merlin",
)


DEFAULTS = {
    "boxes": list(AVIARY[:5]),
    "start_url": "about:blank",
    "window_size": [1440, 900],
    "window_layout": "hidden",
    "max_boxes": 12,
    "dashboard": {"size": [1600, 1000], "columns": "auto", "gap": 10,
                  "refresh_ms": 1000},
}

HIDDEN = "hidden"

# Chromium reads --window-position in DIPs, so this is approximate -- it only has
# to be far enough out that a launching window does not flash on the desktop
# before start() parks it at exact pixels.
LAUNCH_OFFSCREEN = -30000


def load_config(path=CONFIG_PATH):
    config = dict(DEFAULTS)
    if Path(path).exists():
        config.update(json.loads(Path(path).read_text(encoding="utf-8")))
    if not config["boxes"]:
        raise ValueError(f"{path}: 'boxes' is empty, so there is nothing to launch")
    return config


def next_box_name(names, aviary=AVIARY, stem="bird"):
    """The first unused bird, or `bird21` once the aviary is empty.

    Taken rather than counted, so that adding a box after removing one cannot
    hand out a name already in use -- and so that closing `finch` and adding
    another gives you `finch` back rather than shuffling everything along.
    """
    taken = set(names)
    for bird in aviary:
        if bird not in taken:
            return bird
    highest = len(aviary)
    for name in names:
        match = re.fullmatch(rf"{re.escape(stem)}(\d+)", name)
        if match:
            highest = max(highest, int(match.group(1)))
    number = highest + 1
    while f"{stem}{number}" in taken:  # custom names could still collide
        number += 1
    return f"{stem}{number}"


def normalize_url(url):
    """Let the user type 'example.com' and mean it."""
    url = url.strip()
    if not url:
        return ""
    if "://" in url or url.startswith("about:") or url.startswith("data:"):
        return url
    return "https://" + url


def free_port():
    """A port nobody is listening on, for a box's CDP endpoint.

    Racy by nature -- we let the OS pick one, drop it, and hand the number to
    Chromium, which binds it a moment later. Nothing else here is opening ports,
    and the alternative is fishing DevToolsActivePort out of a profile directory
    that Playwright owns and does not tell us about.
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class Box:
    name: str
    browser: object
    page: object
    pids: Set[int] = field(default_factory=set)
    hwnd: Optional[int] = None
    # Where this box's agent reaches its browser. The dashboard never uses it:
    # it exists to be handed to the child process, which is the only thing on
    # this machine allowed to drive the page.
    cdp: Optional[str] = None

    @property
    def url(self):
        try:
            return self.page.url
        except Exception:
            return "(closed)"

    @property
    def alive(self):
        try:
            return not self.page.is_closed()
        except Exception:
            return False

    def ensure_hwnd(self):
        """Re-resolve the window handle if we never got one or it has died."""
        if not winfocus.is_window(self.hwnd):
            self.hwnd = winfocus.top_level_window(self.pids)
        return self.hwnd


class BoxManager:
    """Owns the Playwright driver and every box. Single-threaded by design."""

    def __init__(self, config):
        self.config = config
        self.boxes: List[Box] = []
        self.summoned: Optional[Box] = None
        self._playwright = None

    @property
    def hidden(self):
        """True when boxes live off the desktop and the dashboard is the only window."""
        return self.config.get("window_layout", HIDDEN) == HIDDEN

    @property
    def max_boxes(self):
        return self.config.get("max_boxes", DEFAULTS["max_boxes"])

    def start(self):
        self._playwright = sync_playwright().start()
        for name in self.config["boxes"]:
            self._launch(name)
        return self.boxes

    def add_box(self, name=None):
        """One more box, launched now. Returns it, or None if there is no room.

        Launches are serialized, and that is not a style preference: PID diffing
        attributes every `chrome.exe` that appeared during a launch to the box
        being launched, so two overlapping launches would hand one box's helper
        processes to the other. The caller must not let a second add start while
        this one is running.
        """
        if self._playwright is None or len(self.boxes) >= self.max_boxes:
            return None
        return self._launch(name or next_box_name([box.name for box in self.boxes]))

    def _launch(self, name):
        width, height = self.config["window_size"]
        start_url = self.config["start_url"]
        position = (LAUNCH_OFFSCREEN, LAUNCH_OFFSCREEN) if self.hidden else (0, 0)

        # Each box listens for CDP on its own port, so its agent can attach as an
        # ordinary client. Playwright keeps its own connection either way; a
        # browser is happy to have more than one.
        port = free_port()

        before = winfocus.chrome_pids()
        browser = self._playwright.chromium.launch(
            headless=False,
            args=[
                f"--window-size={width},{height}",
                f"--window-position={position[0]},{position[1]}",
                f"--remote-debugging-port={port}",
            ],
        )
        page = browser.new_page(no_viewport=True)
        # PIDs that appeared during this launch belong to this box, which is how
        # we later find its OS window.
        pids = winfocus.chrome_pids() - before
        box = Box(name=name, browser=browser, page=page, pids=pids,
                  cdp=f"http://127.0.0.1:{port}")
        box.hwnd = winfocus.top_level_window(pids)
        self.boxes.append(box)
        # Park before returning, so at worst a single window is briefly on screen
        # rather than the whole fleet.
        self._place(box, len(self.boxes) - 1)
        if start_url and start_url != "about:blank":
            page.goto(start_url, wait_until="commit")
        return box

    def remove_box(self, box):
        """Close one box for good. Its window, its browser and its slot go away;
        whatever was said to it is gone with them."""
        if box not in self.boxes:
            return False
        if self.summoned is box:
            self.summoned = None
        try:
            box.browser.close()
        except Exception:
            pass
        self.boxes.remove(box)
        # Slots are positional, so everything after the hole moves up one.
        self.reassert_layout()
        return True

    def reassert_layout(self):
        """Push any box that has wandered back where it belongs, leaving the
        summoned one alone.

        Cheap enough to run on every dashboard refresh, and it makes the layout
        self-healing: a display change, or Chromium repositioning its own window,
        corrects itself within a tick instead of leaving a browser on screen.

        Only in hidden mode. The visible layout is a debugging aid, and snapping
        a window back every second while someone is dragging it is not helpful.
        """
        if not self.hidden:
            return
        for index, box in enumerate(self.boxes):
            if box is not self.summoned:
                self._place(box, index)

    def _place(self, box, index):
        """Park a box, or lay it out as a normal desktop window.

        "hidden" is the real mode: dropped from the taskbar and Alt-Tab, moved
        clear of every monitor. Anything else is the escape hatch -- a fleet you
        cannot look at is hard to debug, so one config key brings the windows
        back as ordinary cascaded windows.
        """
        if not box.ensure_hwnd():
            return False
        size = self.config["window_size"]
        if self.hidden:
            if not winfocus.is_tool_window(box.hwnd):
                winfocus.hide_from_shell(box.hwnd)
            rect = layout.park_slot(winfocus.virtual_screen(), index, size)
        else:
            if winfocus.is_tool_window(box.hwnd):
                winfocus.restore_to_shell(box.hwnd)
            rect = layout.cascade_slot(winfocus.work_area(), index, size)
        return winfocus.move_window(
            box.hwnd, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        )

    def navigate_all(self, url):
        """Point every box at one URL. Returns the boxes that refused.

        No UI reaches this any more: the dashboard has no broadcast bar, and a
        box gets its instructions through its own chat. It survives because
        verify.py drives pages through it to prove tiles are live, and because
        an agentless box still has to start somewhere.
        """
        url = normalize_url(url)
        if not url:
            return []
        failed = []
        for box in self.boxes:
            try:
                box.page.goto(url, wait_until="commit", timeout=15000)
            except Exception as exc:
                failed.append((box.name, str(exc).splitlines()[0]))
        return failed

    def summon(self, box):
        """Bring one box onto the desktop and give it the keyboard.

        The previous one goes back to its slot first, so the desktop never
        accumulates browser windows. There is no page.bring_to_front() fallback
        any more: with no HWND we cannot move the window either, so activating it
        would just put focus somewhere the user cannot see.
        """
        if self.summoned is not None and self.summoned is not box:
            self.park(self.summoned)
        if not box.ensure_hwnd():
            return False
        if self.hidden:
            rect = layout.centred_rect(winfocus.work_area(), self.config["window_size"])
            winfocus.move_window(
                box.hwnd, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            )
        self.summoned = box
        return winfocus.focus_window(box.hwnd)

    def park(self, box):
        """Send a box back off the desktop."""
        if self.summoned is box:
            self.summoned = None
        try:
            index = self.boxes.index(box)
        except ValueError:
            return False
        return self._place(box, index)

    def park_summoned(self):
        if self.summoned is not None:
            self.park(self.summoned)

    def holds_foreground(self, box):
        """Is the user still in this box?

        A PID test, not an HWND test, on purpose: Chromium puts <select> popups,
        the print dialog and download bubbles in their own top-level windows, so
        comparing handles would park the box out from under someone mid-click.
        """
        return winfocus.window_pid(winfocus.foreground_window()) in box.pids

    def close(self):
        for box in self.boxes:
            try:
                box.browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
