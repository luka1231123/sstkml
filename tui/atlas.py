"""The ground the world is drawn on, and the window that looks at it.

The tablet is a grid of characters authored in `content/`: one cell of ground
per character, three hundred columns by a hundred and nineteen rows of the
eastern Mediterranean, drawn from the real relief and the real rivers. That is
far more ground than any window holds, which is the point -- the map is bigger
than the screen and the screen moves over it, so a king looking at Ugarit is
looking at Ugarit and not at a smear of the whole sea.

This module knows three things and no more:

* which character stands for which ground, and in what colour
* where a window sits on the grid, and how a grid cell maps to a screen cell
* how to walk a straight line between two cells, for a road

It knows no place names, no scenario and no rules. Everything it draws comes
out of Belief, having been authored in `content/`, so the map can be wrong only
in the way the scenario is wrong: there is no second, hardcoded geography
living in the UI.

Held wider than one cell per character, the window samples rather than
averages, and it samples in favour of the land: given a block holding both
shore and sea it draws the shore. A coastline that thins out and vanishes as
you pull back is a coastline that lies about where the islands are.
"""
from __future__ import annotations

# How far back the tablet can be held: cells of ground per character. One is
# the true grid; five puts the whole authored world inside an ordinary window.
MAX_WIDE = 5

SEA = "~"
RIVER = "≈"
UPLAND = "^"
SOWN = ","
DRY = "."
DESERT = ":"
MARSH = ";"

# What survives when one character has to stand for several cells. Land beats
# water and the sharp things beat the flat ones, because those are what tell
# you where you are: a river, a ridge and a shoreline are landmarks, and a
# stretch of dry plain is not.
PRIORITY = (UPLAND, RIVER, MARSH, SOWN, DRY, DESERT, SEA)

GROUND_TONE = {
    SEA: "lapis",
    RIVER: "sky",
    UPLAND: "clay",
    SOWN: "verdigris",
    DRY: "sand",
    DESERT: "dim",
    MARSH: "barley",
}

# What a place is drawn as. The brackets are the rank -- a king can see at a
# glance which marks are the great seats -- and the letter inside is authored,
# so a scenario decides what stands for Hattusa and not this module.
BRACKET = {
    "seat": ("{", "}"),
    "imperial": ("[", "]"),
    "royal": ("(", ")"),
    "town": ("", ""),
}

# Whose empire answers for the place. Colour only ever repeats what the tablet
# beside the map says in words, because colour alone is not a legend.
POWER_TONE = {
    "egypt": "gold",
    "hatti": "flame",
    "ahhiyawa": "lapis",
    "free": "verdigris",
}

# The hinterland, which has no names: a holding, an estate, a source of metal.
# One glyph per kind of thing rather than per commodity -- the tablet beside
# the map says which metal, and the map says only that there is one.
SITE_GLYPH = {
    "palace": "x",
    "grain": "%",
    "copper": "*",
    "tin": "*",
    "gold": "*",
    "silver": "*",
    "lapis": "*",
    "cedar": "Y",
    "horses": "n",
}
SITE_TONE = {
    "palace": "bone",
    "grain": "barley",
    "cedar": "verdigris",
    "horses": "sand",
}
METAL_TONE = "gold"

SITE_WORD = {
    "palace": "small palaces",
    "grain": "grain estates",
    "copper": "copper",
    "tin": "tin",
    "gold": "gold",
    "silver": "silver",
    "lapis": "lapis",
    "cedar": "cedar",
    "horses": "horse pasture",
}


def terrain_of(b: dict) -> dict:
    """The authored ground, if this scenario drew any."""
    graph = b.get("world_graph") or {}
    ground = graph.get("terrain")
    return dict(ground) if isinstance(ground, dict) else {}


def ground_rows(b: dict) -> list[str]:
    rows = terrain_of(b).get("rows") or []
    return [str(row) for row in rows]


def sites_of(b: dict) -> list[dict]:
    """Every holding in every hinterland, as plain dicts."""
    graph = b.get("world_graph") or {}
    return [dict(site) for site in graph.get("sites", [])
            if isinstance(site, dict)]


def site_tone(kind: str) -> str:
    return SITE_TONE.get(kind, METAL_TONE)


def sample(rows: list[str], col: int, row: int, wide: int) -> str:
    """The one character standing for the block of ground at (col, row)."""
    if wide <= 1:
        if 0 <= row < len(rows) and 0 <= col < len(rows[row]):
            return rows[row][col]
        return " "
    best = ""
    rank = len(PRIORITY)
    for dy in range(wide):
        line = rows[row + dy] if 0 <= row + dy < len(rows) else ""
        for dx in range(wide):
            if not (0 <= col + dx < len(line)):
                continue
            glyph = line[col + dx]
            here = PRIORITY.index(glyph) if glyph in PRIORITY else len(PRIORITY)
            if here < rank:
                rank, best = here, glyph
    return best or " "


class View:
    """Which part of the authored grid a panel of characters is showing.

    One object shared by everything drawn, because the alternative -- each
    layer working out its own offset -- is a road that starts at one city and
    ends a column away from another. Cells outside the panel are returned
    rather than clamped: a road running off the edge should be cut off there,
    not folded back along it.
    """

    def __init__(self, cols: int, rows: int, width: int, height: int,
                 focus: tuple[int, int] | None = None, wide: int = 1,
                 corner: tuple[int, int] | None = None) -> None:
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self.width = max(1, width)
        self.height = max(1, height)
        self.wide = max(1, min(MAX_WIDE, wide))

        # How much ground the panel holds at this magnification, and therefore
        # how far the corner can travel before the window runs off the map.
        span_x = self.width * self.wide
        span_y = self.height * self.wide
        self.span = (span_x, span_y)

        if corner is None:
            spot = focus or (self.cols // 2, self.rows // 2)
            corner = (spot[0] - span_x // 2, spot[1] - span_y // 2)
        self.corner = (self._hold(corner[0], span_x, self.cols),
                       self._hold(corner[1], span_y, self.rows))

    @staticmethod
    def _hold(start: int, span: int, total: int) -> int:
        """Keep the window on the map, and centred on it when it is smaller."""
        if span >= total:
            return (total - span) // 2
        return max(0, min(start, total - span))

    def cell(self, col: int, row: int) -> tuple[int, int]:
        """Where a grid cell falls in the panel. May be off it."""
        return ((col - self.corner[0]) // self.wide,
                (row - self.corner[1]) // self.wide)

    def at(self, spot: tuple[int, int]) -> tuple[int, int]:
        """Which grid cell a panel cell holds: `cell` run backwards."""
        return (self.corner[0] + spot[0] * self.wide,
                self.corner[1] + spot[1] * self.wide)

    def inside(self, spot: tuple[int, int]) -> bool:
        return 0 <= spot[0] < self.width and 0 <= spot[1] < self.height

    def holds(self, col: int, row: int) -> bool:
        return self.inside(self.cell(col, row))

    def moved(self, across: int = 0, down: int = 0,
              wide: int | None = None) -> "View":
        """The same window, shifted, or held closer. In grid cells."""
        step = self.wide
        return View(self.cols, self.rows, self.width, self.height,
                    wide=self.wide if wide is None else wide,
                    corner=(self.corner[0] + across * step,
                            self.corner[1] + down * step))


def frame_for(rows: list[str], width: int, height: int,
              focus: tuple[int, int] | None = None, wide: int = 1,
              corner: tuple[int, int] | None = None) -> View:
    """A window onto the authored rows, sized to the panel it is drawn in."""
    return View(max((len(row) for row in rows), default=1), len(rows) or 1,
                width, height, focus=focus, wide=wide, corner=corner)


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
    diagonals. A character cell is about twice as tall as it is wide, so the
    thresholds are not at forty-five degrees -- a road drawn with the glyph of
    its own slope reads as a road rather than as a row of dots.
    """
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    if dy * 2 <= dx:
        return "─"
    if dx * 2 <= dy:
        return "│"
    rising = (end[0] - start[0]) * (end[1] - start[1]) < 0
    return "╱" if rising else "╲"


def free(spot: tuple[int, int], width: int, height: int,
         taken: set[tuple[int, int]]) -> tuple[int, int]:
    """The wanted cell, or the nearest free one, or the wanted cell anyway.

    Two marks in one cell is one place hidden with no sign that it is missing,
    so a mark walks a short way to be seen. It gives up rather than walking far
    enough to lie about where it is.
    """
    if spot not in taken:
        return spot
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0),
                   (1, 1), (-1, -1), (1, -1), (-1, 1), (0, 2), (0, -2)):
        cell = (spot[0] + dx, spot[1] + dy)
        if 0 <= cell[0] < width and 0 <= cell[1] < height and cell not in taken:
            return cell
    return spot
