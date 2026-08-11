"""One Playwright browser launch per box, so every box gets its own OS window.

Nothing is shared between boxes -- separate launch, separate page, separate
process tree. Profiles are ephemeral (Playwright's own temp dir); this is a
window manager, not an isolation boundary.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from playwright.sync_api import sync_playwright

import winfocus

CONFIG_PATH = Path(__file__).with_name("config.json")

DEFAULTS = {
    "boxes": ["box1", "box2", "box3", "box4", "box5"],
    "start_url": "about:blank",
    "window_size": [900, 700],
}

# Windows are cascaded by this many pixels so all of them stay grabbable.
CASCADE = 40


def load_config(path=CONFIG_PATH):
    config = dict(DEFAULTS)
    if Path(path).exists():
        config.update(json.loads(Path(path).read_text(encoding="utf-8")))
    if not config["boxes"]:
        raise ValueError(f"{path}: 'boxes' is empty, so there is nothing to launch")
    return config


def normalize_url(url):
    """Let the user type 'example.com' and mean it."""
    url = url.strip()
    if not url:
        return ""
    if "://" in url or url.startswith("about:") or url.startswith("data:"):
        return url
    return "https://" + url


@dataclass
class Box:
    name: str
    browser: object
    page: object
    pids: Set[int] = field(default_factory=set)
    hwnd: Optional[int] = None

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


class BoxManager:
    """Owns the Playwright driver and every box. Single-threaded by design."""

    def __init__(self, config):
        self.config = config
        self.boxes: List[Box] = []
        self._playwright = None

    def start(self):
        self._playwright = sync_playwright().start()
        width, height = self.config["window_size"]
        start_url = self.config["start_url"]

        for index, name in enumerate(self.config["boxes"]):
            before = winfocus.chrome_pids()
            browser = self._playwright.chromium.launch(
                headless=False,
                args=[
                    f"--window-size={width},{height}",
                    f"--window-position={CASCADE * index},{CASCADE * index}",
                ],
            )
            page = browser.new_page(no_viewport=True)
            # PIDs that appeared during this launch belong to this box, which is
            # how we later find its OS window.
            pids = winfocus.chrome_pids() - before
            box = Box(name=name, browser=browser, page=page, pids=pids)
            box.hwnd = winfocus.top_level_window(pids)
            if start_url and start_url != "about:blank":
                page.goto(start_url, wait_until="commit")
            self.boxes.append(box)

        return self.boxes

    def navigate_all(self, url):
        """Broadcast a navigation. Returns the boxes that refused."""
        url = normalize_url(url)
        if not url:
            return []
        return self._broadcast(lambda box: box.page.goto(url, wait_until="commit", timeout=15000))

    def reload_all(self):
        return self._broadcast(lambda box: box.page.reload(wait_until="commit", timeout=15000))

    def _broadcast(self, action):
        failed = []
        for box in self.boxes:
            try:
                action(box)
            except Exception as exc:
                failed.append((box.name, str(exc).splitlines()[0]))
        return failed

    def focus(self, box):
        """Raise this box's window, re-finding the handle if we never got one."""
        if box.hwnd is None:
            box.hwnd = winfocus.top_level_window(box.pids)
        try:
            box.page.bring_to_front()
        except Exception:
            pass
        return winfocus.focus_window(box.hwnd)

    def close(self):
        for box in self.boxes:
            try:
                box.browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
