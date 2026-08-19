"""Grid geometry for the dashboard. Pure functions -- no Tk, no Win32.

Kept dependency-free on purpose so verify.py can assert on the tile map without
opening a window.
"""

from collections import namedtuple

Rect = namedtuple("Rect", "left top right bottom")
Tile = namedtuple("Tile", "index cell thumb label")

MIN_TILE = 60

# How far past the last monitor a parked window sits, and how much each box is
# offset from the one before it.
PARK_GAP = 200
PARK_STAGGER = 200

# Stagger for the visible debug layout, so every window stays grabbable.
CASCADE = 40


def tile_rects(width, height, count, aspect=4 / 3, columns="auto", gap=10, label_h=20,
               max_thumb=None):
    """Lay `count` tiles into a width x height area.

    `columns="auto"` picks whichever column count makes the tiles biggest, which
    matters a lot in a tall narrow window: two columns of small tiles can waste
    most of the panel where one column of large ones fills it.

    `max_thumb` is the source window's own size, and tiles are never scaled past
    it. Upscaling invents no detail, and more importantly DWM will not reliably
    paint a thumbnail bigger than its source: it fails by quietly leaving the far
    edge of the later tiles unpainted. Total area is not the constraint — five
    1200x930 tiles are fine from 1200x930 windows — only the ratio to the source.
    """
    if columns == "auto":
        columns = _best_columns(width, height, count, aspect, gap, label_h, max_thumb)
    return _lay(width, height, count, aspect, columns, gap, label_h, max_thumb)


def _best_columns(width, height, count, aspect, gap, label_h, max_thumb=None):
    best, best_area = 1, -1
    for columns in range(1, max(1, count) + 1):
        tiles = _lay(width, height, count, aspect, columns, gap, label_h, max_thumb)
        if not tiles:
            continue
        thumb = tiles[0].thumb
        area = (thumb.right - thumb.left) * (thumb.bottom - thumb.top)
        if area > best_area:
            best, best_area = columns, area
    return best


def _lay(width, height, count, aspect, columns, gap, label_h, max_thumb=None):
    """Cells are sized to the source aspect rather than dividing the area evenly,
    so a tile is exactly its image plus a caption strip and no dead space.

    The cell is the click target; the thumb is what DWM composites into.
    """
    if count <= 0 or width <= 0 or height <= 0:
        return []
    columns = max(1, min(int(columns), count))
    rows = -(-count // columns)
    aspect = aspect if aspect > 0 else 4 / 3

    cell_w = (width - gap * (columns + 1)) // columns
    thumb_h = int(cell_w / aspect)

    max_cell_h = (height - gap * (rows + 1)) // rows
    if thumb_h + label_h > max_cell_h:
        thumb_h = max_cell_h - label_h
        cell_w = min(cell_w, int(thumb_h * aspect))
    if max_thumb:
        source_w, source_h = max_thumb
        if source_w > 0 and cell_w > source_w:
            cell_w, thumb_h = source_w, int(source_w / aspect)
        if source_h > 0 and thumb_h > source_h:
            thumb_h, cell_w = source_h, min(cell_w, int(source_h * aspect))
    cell_h = thumb_h + label_h

    if cell_w < MIN_TILE or thumb_h < MIN_TILE:
        return []

    span = columns * cell_w + gap * (columns - 1)
    origin_x = max(gap, (width - span) // 2)
    # Centred vertically too, or a capped grid sits jammed against the top of a
    # tall window with all the dead space below it.
    span_y = rows * cell_h + gap * (rows - 1)
    origin_y = max(gap, (height - span_y) // 2)

    tiles = []
    for index in range(count):
        row, col = divmod(index, columns)
        left = origin_x + col * (cell_w + gap)
        top = origin_y + row * (cell_h + gap)
        tiles.append(Tile(
            index,
            Rect(left, top, left + cell_w, top + cell_h),
            Rect(left, top, left + cell_w, top + thumb_h),
            Rect(left, top + thumb_h, left + cell_w, top + cell_h),
        ))
    return tiles


def viewport_rect(width, height, aspect=4 / 3, max_thumb=None):
    """The detail view's single live view: as large as the space allows, centred.

    Same constraint as `tile_rects`' `max_thumb` and for the same reason -- DWM
    will not reliably paint a thumbnail larger than its source, and it fails by
    quietly leaving the far edge unpainted rather than by erroring. One tile
    instead of five changes nothing about that, so a viewport bigger than the box
    window is letterboxed rather than stretched.
    """
    if width <= 0 or height <= 0:
        return Rect(0, 0, 0, 0)
    aspect = aspect if aspect > 0 else 4 / 3

    view_w = width
    view_h = int(view_w / aspect)
    if view_h > height:
        view_h = height
        view_w = int(view_h * aspect)
    if max_thumb:
        source_w, source_h = max_thumb
        if source_w > 0 and view_w > source_w:
            view_w, view_h = source_w, int(source_w / aspect)
        if source_h > 0 and view_h > source_h:
            view_h, view_w = source_h, int(source_h * aspect)

    left = (width - view_w) // 2
    top = (height - view_h) // 2
    return Rect(left, top, left + view_w, top + view_h)


def bounds_rect(x, y, width, height):
    """A Rect from the (x, y, w, h) tuples the Win32 screen metrics come back as."""
    return Rect(x, y, x + width, y + height)


def intersects(a, b):
    """Do two rects share any pixel? Used to ask whether a window is on a screen."""
    return a.left < b.right and b.left < a.right and a.top < b.bottom and b.top < a.bottom


def park_slot(virtual, index, size):
    """Where box `index` waits while nobody is using it.

    Clear of every monitor, so the window is still composited -- and therefore
    still mirrorable into a tile -- but nowhere the user can see. Every box gets
    its own origin rather than sharing one, so a window that ends up somewhere
    unexpected is traceable to a single box instead of a pile of five.
    """
    screen = bounds_rect(*virtual)
    width, height = size
    left = screen.right + PARK_GAP + PARK_STAGGER * index
    return Rect(left, screen.top, left + width, screen.top + height)


def centred_rect(work, size):
    """`size`, centred in the work area, clamped to fit.

    Where a summoned box lands, and where the dashboard opens. A summoned box is
    deliberately not maximised: the tile grid takes its aspect ratio from a live
    source window, so a box that changed shape would reflow every tile.
    """
    area = bounds_rect(*work)
    width = min(size[0], area.right - area.left)
    height = min(size[1], area.bottom - area.top)
    left = area.left + (area.right - area.left - width) // 2
    top = area.top + (area.bottom - area.top - height) // 2
    return Rect(left, top, left + width, top + height)


def cascade_slot(work, index, size, step=CASCADE):
    """The visible debug layout: boxes as ordinary staggered desktop windows."""
    area = bounds_rect(*work)
    width = min(size[0], area.right - area.left)
    height = min(size[1], area.bottom - area.top)
    left = min(area.left + step * index, area.right - width)
    top = min(area.top + step * index, area.bottom - height)
    return Rect(left, top, left + width, top + height)


def hit_test(tiles, x, y):
    """Index of the tile containing the point, or None. Whole cell is clickable."""
    for tile in tiles:
        if tile.cell.left <= x < tile.cell.right and tile.cell.top <= y < tile.cell.bottom:
            return tile.index
    return None
