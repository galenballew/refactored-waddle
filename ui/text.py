"""Turning URLs into captions. Shared by both views.

Same as `ui/text.py` except that `clip` is handed a measuring function rather
than a Tk font, so nothing here knows which toolkit is drawing.
"""


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
