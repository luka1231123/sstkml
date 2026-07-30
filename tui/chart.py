"""Authored coordinates turned into character cells, and nothing else.

The World tablet is drawn in the shape of the real coast, which needs two
things this module supplies and no more: where a place falls on a grid of
cells, and which cells a line between two places passes through.

It knows no place names, no scenario, and no palette. Everything it is given
comes out of Belief, having been authored in `content/`, so the map can be
wrong only in the way the scenario is wrong -- there is no second, hardcoded
geography living in the UI, which is what got the previous map deleted.

Two distortions are deliberate:

* a character cell is about twice as tall as it is wide, so a degree of
  longitude is given twice as many columns as a degree of latitude is given
  rows. Without this the eastern Mediterranean comes out looking like a
  vertical smear of the Levant.
* longitude is squeezed by the cosine of the middle latitude, the plate
  carree correction. Over ten degrees of latitude that is the difference
  between a coastline and a fan.

Both are integer arithmetic on hundredths of a degree, because a map that
moved a place by a cell between two runs of the same seed would be a map you
could not point at.
"""
from __future__ import annotations

import math

# One degree of longitude is drawn this many times wider than one degree of
# latitude is drawn tall, to undo the shape of a character cell.
CELL_ASPECT = 2

def _nudge_order(limit: int = 6) -> tuple[tuple[int, int], ...]:
    """A stable nearest-first search, preferring sideways movement.

    Character maps have much more horizontal than vertical resolution. Moving
    a crowded port sideways first therefore preserves its apparent latitude
    better than stacking a column of fused marks.
    """
    cells = [
        (dx, dy)
        for dx in range(-limit, limit + 1)
        for dy in range(-limit, limit + 1)
        if dx or dy
    ]
    return tuple(sorted(cells, key=lambda cell: (
        max(abs(cell[0]), abs(cell[1])),
        abs(cell[1]),
        abs(cell[0]),
        cell[0] < 0,
        cell[1] < 0,
    )))


_NUDGE = _nudge_order()


def _coordinate(place: dict, key: str) -> int | None:
    value = place.get(key)
    return value if type(value) is int else None


def placed(places: list[dict]) -> list[dict]:
    """Only the places the tablet actually locates.

    A place with no coordinate is not drawn rather than drawn at the origin,
    which would put it in the sea off Africa and look like knowledge.
    """
    return [place for place in places
            if _coordinate(place, "lat") is not None
            and _coordinate(place, "lon") is not None]


def project(places: list[dict], width: int, height: int,
            spacing: int = 0) -> dict[str, tuple[int, int]]:
    """Where each place falls on a `width` x `height` grid of cells.

    North is up and east is right. The whole set is scaled to fit and centred;
    the scale is shared between the axes, so the map keeps its proportions when
    the window is a different shape and simply uses less of it.
    """
    located = placed(places)
    if not located or width < 1 or height < 1:
        return {}

    lats = [place["lat"] for place in located]
    lons = [place["lon"] for place in located]
    middle = (min(lats) + max(lats)) / 2 / 100
    squeeze = max(0.1, math.cos(math.radians(middle)))

    def east(place: dict) -> float:
        return place["lon"] * squeeze * CELL_ASPECT

    span_x = max(east(p) for p in located) - min(east(p) for p in located)
    span_y = max(lats) - min(lats)
    # A single place, or a set all on one line, still has to land somewhere.
    scale = min((width - 1) / span_x if span_x > 0 else float("inf"),
                (height - 1) / span_y if span_y > 0 else float("inf"))
    if scale == float("inf"):
        scale = 0.0

    left = min(east(p) for p in located)
    top = max(lats)
    used_x = span_x * scale
    used_y = span_y * scale
    margin_x = int((width - 1 - used_x) / 2)
    margin_y = int((height - 1 - used_y) / 2)

    taken: dict[tuple[int, int], str] = {}
    at: dict[str, tuple[int, int]] = {}
    # Sorted by id so the order marks claim their cells -- and therefore which
    # of two neighbours is the one that gets nudged -- does not depend on the
    # order Belief happened to list them in.
    for place in sorted(located, key=lambda item: str(item.get("id", ""))):
        x = margin_x + int(round((east(place) - left) * scale))
        y = margin_y + int(round((top - place["lat"]) * scale))
        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))
        cell = _free(x, y, width, height, taken, max(0, spacing))
        taken[cell] = str(place.get("id", ""))
        at[str(place.get("id", ""))] = cell
    return at


def _clear(cell: tuple[int, int], taken: dict[tuple[int, int], str],
           spacing: int) -> bool:
    return all(
        max(abs(cell[0] - other[0]), abs(cell[1] - other[1])) > spacing
        for other in taken
    )


def _free(x: int, y: int, width: int, height: int,
          taken: dict[tuple[int, int], str],
          spacing: int = 0) -> tuple[int, int]:
    """The wanted cell, or the nearest free one, or the wanted cell anyway.

    Two marks in one cell is one place hidden with no sign that it is missing,
    so a mark walks a short way to be seen. It gives up rather than walking far
    enough to lie about where it is.
    """
    if _clear((x, y), taken, spacing):
        return (x, y)
    for dx, dy in _NUDGE:
        cell = (x + dx, y + dy)
        if (0 <= cell[0] < width and 0 <= cell[1] < height
                and _clear(cell, taken, spacing)):
            return cell
    return (x, y)


def line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Every cell a straight route passes through, endpoints included.

    Bresenham, in integers. Used both to draw a road and to decide whether the
    player clicked on one, so the line you can see and the line you can hit are
    the same list of cells.
    """
    (x0, y0), (x1, y1) = start, end
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    step_x = 1 if x1 >= x0 else -1
    step_y = 1 if y1 >= y0 else -1
    error = dx - dy
    cells = []
    while True:
        cells.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return cells
        doubled = 2 * error
        if doubled > -dy:
            error -= dy
            x0 += step_x
        if doubled < dx:
            error += dx
            y0 += step_y


def slope_glyph(start: tuple[int, int], end: tuple[int, int]) -> str:
    """The line-drawing character that lies along a route's bearing.

    Four directions, because a terminal has four: level, steep, and the two
    diagonals. A road drawn with the glyph of its own slope reads as a road
    rather than as a row of dots.
    """
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    if dy * CELL_ASPECT <= dx:
        return "─"
    if dx * CELL_ASPECT <= dy:
        return "│"
    rising = (end[0] - start[0]) * (end[1] - start[1]) < 0
    return "╱" if rising else "╲"
