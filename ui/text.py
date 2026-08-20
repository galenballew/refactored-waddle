"""Turning URLs into captions. Shared by both views."""


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


def clip(font, text, max_px):
    """Truncate to fit, or a caption bleeds into the next tile."""
    if max_px <= 0 or font.measure(text) <= max_px:
        return text
    while text and font.measure(text + "…") > max_px:
        text = text[:-1]
    return text + "…"
