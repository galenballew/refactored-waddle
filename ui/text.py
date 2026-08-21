"""The words the dashboard says for itself: captions, and the greeting.

`clip` is handed a measuring function rather than a font, so nothing in here
knows which toolkit is drawing.
"""

import os
from datetime import datetime


def who():
    """Whoever is logged in, or None. Best effort and never fatal -- a dashboard
    that will not start because it could not read an environment variable would
    be a poor trade for a friendlier heading."""
    name = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()
    return name.split("@")[0].capitalize() or None


def greeting(now=None):
    """What the overview leads with, instead of repeating the app's own name.

    The title bar already says Aviary; saying it twice spends the largest piece
    of type on screen on something you have already read. This is the one place
    the app talks to the person using it rather than about the boxes, so it
    follows the clock -- and at three in the morning it says something truer
    than "good evening".
    """
    now = now or datetime.now()
    if now.hour < 5:
        opener = "Still up"
    elif now.hour < 12:
        opener = "Good morning"
    elif now.hour < 18:
        opener = "Good afternoon"
    else:
        opener = "Good evening"
    name = who()
    return f"{opener}, {name}" if name else opener


def short_url(url):
    """Shorten for a caption.

    Local files show just their filename -- captions are clipped from the right,
    and every local path shares a long identical prefix, so keeping the head
    would make every tile read the same.
    """
    if not url:
        return "(blank)"
    if url.startswith("file:///"):
        return url.rsplit("/", 1)[-1] or url
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            return url[len(prefix):]
    return url


def clip(measure, text, max_px):
    """Truncate to fit, or a caption bleeds into the next tile.

    `measure` turns a string into its width. Tk spells that `font.measure` and
    Qt spells it `QFontMetrics.horizontalAdvance`; this module does not care.
    """
    if max_px <= 0 or measure(text) <= max_px:
        return text
    while text and measure(text + "…") > max_px:
        text = text[:-1]
    return text + "…"
