"""Window classes, typography, placement, and preferences (UI/UX spec 6, 21).

Everything here is integers. No Tk, no display, no window: the point is that
the desktop's awkward parts -- what size a window may be, whether restored
geometry is still on a monitor that exists, how six windows tile without
overlapping -- can be asserted in the headless suite instead of by opening
rectangles on a developer's screen and looking at them. `tui/grid.py` does the
same thing for rendering, and for the same reason.

The sizes are the specification's, not invented here. A window has a class
(anchor, workbench, ledger, document, utility) that gives it a default and a
minimum, and it is never allowed below the minimum: the rule is to refuse to
shrink rather than to clip, because a clipped window silently hides actions and
a window that stops shrinking is merely awkward.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

FONT_MIN = 9
FONT_MAX = 20
FONT_DEFAULT = 11

# Width tiers (spec 6). A composer asks which tier it is in and decides how
# many panes to show; it never hardcodes a column count.
WIDE, STANDARD, COMPACT, MINIMUM = "wide", "standard", "compact", "minimum"

# Height bands. Art is the first thing to go, then history length.
FULL, REDUCED, BARE = "full", "reduced", "bare"


@dataclasses.dataclass(frozen=True)
class WindowClass:
    name: str
    default: tuple[int, int]
    minimum: tuple[int, int]


CLASSES = {
    "anchor": WindowClass("anchor", (92, 34), (72, 26)),
    "workbench": WindowClass("workbench", (88, 30), (66, 22)),
    "ledger": WindowClass("ledger", (78, 27), (58, 20)),
    "document": WindowClass("document", (62, 25), (46, 18)),
    "utility": WindowClass("utility", (52, 20), (40, 15)),
    "palette": WindowClass("palette", (68, 15), (48, 11)),
}


@dataclasses.dataclass(frozen=True)
class WindowSpec:
    key: str
    title: str
    window_class: str
    default: tuple[int, int]
    minimum: tuple[int, int]


def _spec(key, title, window_class, default=None, minimum=None) -> WindowSpec:
    """A window's size, defaulting to its class but free to state its own.

    Several screens in specification section 15 name a size that is not exactly
    their class default -- City wants 96 columns for the skyline, the Inbox 90
    for its columns -- so the class is the rule and the pair is the exception.
    """
    cls = CLASSES[window_class]
    return WindowSpec(key, title, window_class,
                      default or cls.default, minimum or cls.minimum)


# Per-window sizes from UI/UX specification sections 6, 13, 14, 15, 16 and 17.
# Entity windows are keyed by prefix: `institution:tablet_house` is a document.
WINDOWS: dict[str, WindowSpec] = {
    spec.key: spec for spec in (
        _spec("hall", "The Hall", "anchor"),
        _spec("stack", "The Inbox", "workbench", (90, 30), (66, 22)),
        _spec("city", "The City", "workbench", (96, 34), (70, 24)),
        _spec("world", "The Known World", "workbench", (90, 30), (68, 22)),
        _spec("justice", "The Court of Justice", "workbench", (84, 29), (64, 22)),
        _spec("house", "The House", "workbench", (82, 29), (62, 22)),
        _spec("relations", "Relations", "ledger", (82, 28), (62, 21)),
        _spec("archive", "The Tablet House", "ledger", (78, 28), (58, 20)),
        _spec("works", "Works", "ledger", (82, 28), (62, 21)),
        _spec("plague", "Sickness and Closures", "ledger", (78, 27), (58, 20)),
        _spec("roll", "The Roll", "ledger", (82, 28), (62, 21)),
        _spec("land", "The Land", "ledger", (80, 28), (60, 21)),
        _spec("muster", "The Muster", "ledger", (80, 27), (60, 20)),
        _spec("oaths", "The Oaths", "ledger", (78, 28), (58, 20)),
        _spec("stores", "The Stores", "ledger", (76, 26), (58, 20)),
        _spec("desk", "The Desk", "document", (66, 28), (52, 20)),
        _spec("altar", "The Altar", "document", (68, 24), (52, 18)),
        _spec("counsel", "Counsel", "document", (64, 22), (50, 17)),
        _spec("fortnight", "The Fortnight", "document", (66, 22), (50, 17)),
        _spec("help", "Help", "utility"),
        _spec("switcher", "Windows", "utility", (42, 17), (40, 15)),
        _spec("institution:", "Institution", "document", (62, 24), (46, 18)),
        _spec("letter:", "Tablet", "document", (60, 25), (46, 18)),
        _spec("archive:", "Tablet", "document", (60, 25), (46, 18)),
    )
}


def family(key: str) -> str:
    """Collapse an entity key onto the kind it belongs to.

    `letter:tablet_12` and `letter:tablet_13` are two windows of one kind, so
    they share a size but not a geometry: each remembers where the player put
    it (spec 6, "entity windows are keyed by ID").
    """
    prefix, separator, _rest = key.partition(":")
    return prefix + ":" if separator else key


def spec_for(key: str) -> WindowSpec:
    """The spec for a window key, falling back to a document."""
    return WINDOWS.get(family(key), WINDOWS["letter:"])


def default_size(key: str) -> tuple[int, int]:
    return spec_for(key).default


def minimum_size(key: str) -> tuple[int, int]:
    return spec_for(key).minimum


def clamp_size(key: str, width: int, height: int) -> tuple[int, int]:
    """Never below the class minimum. Refuse to shrink; do not clip."""
    least_width, least_height = minimum_size(key)
    return max(least_width, int(width)), max(least_height, int(height))


def tier(width: int) -> str:
    if width >= 88:
        return WIDE
    if width >= 68:
        return STANDARD
    if width >= 52:
        return COMPACT
    return MINIMUM


def band(height: int) -> str:
    if height >= 28:
        return FULL
    if height >= 20:
        return REDUCED
    return BARE


def capacity(pixel_width: int, pixel_height: int,
             cell_width: int, cell_height: int) -> tuple[int, int]:
    """How many cells fit in a pixel rectangle.

    This is what makes font scaling a recomposition rather than a magnifying
    glass: the window keeps its rectangle, the glyphs get bigger, fewer of them
    fit, and the screen is composed again at the smaller size (spec 6).
    """
    if cell_width <= 0 or cell_height <= 0:
        return 0, 0
    return max(0, pixel_width // cell_width), max(0, pixel_height // cell_height)


def clamp_font(size: int) -> int:
    return max(FONT_MIN, min(FONT_MAX, int(size)))


# --- placement ---------------------------------------------------------------

Rect = tuple[int, int, int, int]        # x, y, width, height, in pixels


def clamp_to_area(rect: Rect, area: Rect) -> Rect:
    """Bring a window rectangle back inside the usable area.

    A geometry saved on a second monitor that is no longer attached would
    otherwise restore to coordinates no display covers, and the window would be
    invisible with no way to reach it but deleting the settings file.
    """
    x, y, width, height = rect
    ax, ay, aw, ah = area
    width = max(1, min(width, aw))
    height = max(1, min(height, ah))
    x = max(ax, min(int(x), ax + aw - width))
    y = max(ay, min(int(y), ay + ah - height))
    return x, y, width, height


def fits(rect: Rect, area: Rect) -> bool:
    x, y, width, height = rect
    ax, ay, aw, ah = area
    return x >= ax and y >= ay and x + width <= ax + aw and y + height <= ay + ah


def _splits(total: int, parts: int) -> list[int]:
    """Boundaries dividing `total` into `parts` as evenly as integers allow."""
    return [total * index // parts for index in range(parts + 1)]


def tiled(count: int, area: Rect) -> list[Rect]:
    """Rectangles that exactly cover the area without overlapping.

    Rows first, then a share of the width per row, so a count that is not a
    perfect grid leaves a wider window in the last row rather than a gap. Exact
    cover matters more than equal size: a gap in a tiling reads as a bug.
    """
    if count <= 0:
        return []
    ax, ay, aw, ah = area
    rows = 1
    while rows * rows < count:
        rows += 1
    rows = min(rows, count)
    base, extra = divmod(count, rows)
    row_bounds = _splits(ah, rows)
    out: list[Rect] = []
    for row in range(rows):
        in_row = base + (1 if row < extra else 0)
        column_bounds = _splits(aw, in_row)
        top = ay + row_bounds[row]
        height = row_bounds[row + 1] - row_bounds[row]
        for column in range(in_row):
            left = ax + column_bounds[column]
            width = column_bounds[column + 1] - column_bounds[column]
            out.append((left, top, width, height))
    return out


def cascaded(count: int, area: Rect, size: tuple[int, int],
             step: int = 28) -> list[Rect]:
    """Overlapping rectangles stepped down and right, wrapping at the edge."""
    if count <= 0:
        return []
    ax, ay, aw, ah = area
    width, height = min(size[0], aw), min(size[1], ah)
    out: list[Rect] = []
    offset = 0
    for index in range(count):
        x, y = ax + offset, ay + offset
        if x + width > ax + aw or y + height > ay + ah:
            offset = 0
            x, y = ax, ay
        out.append((x, y, width, height))
        offset += step
    return out


# --- preferences -------------------------------------------------------------

@dataclasses.dataclass
class Preferences:
    """What the desktop remembers between runs (spec 6, 18).

    Deliberately forgiving: a settings file that is missing, unreadable, or
    full of nonsense yields defaults and is rewritten on the next save. Nothing
    about presentation is worth refusing to start the game over.
    """
    font_size: int = FONT_DEFAULT
    font_family: str = ""
    ascii_only: bool = False
    restore_placement: bool = True
    geometry: dict[str, dict] = dataclasses.field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Preferences":
        try:
            raw = json.loads(Path(path).read_text())
        except Exception:
            return cls()
        if not isinstance(raw, dict):
            return cls()
        geometry = raw.get("geometry")
        prefs = cls(
            font_size=clamp_font(_int(raw.get("font_size"), FONT_DEFAULT)),
            font_family=str(raw.get("font_family") or ""),
            ascii_only=bool(raw.get("ascii_only", False)),
            restore_placement=bool(raw.get("restore_placement", True)),
            geometry=geometry if isinstance(geometry, dict) else {},
        )
        return prefs

    def save(self, path: str | Path) -> bool:
        """Write atomically. A failed save must not interrupt play."""
        try:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(dataclasses.asdict(self), indent=2,
                                 sort_keys=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(payload)
            temporary.replace(destination)
            return True
        except Exception:
            return False

    def remember(self, key: str, x: int, y: int,
                 columns: int, rows: int) -> None:
        self.geometry[key] = {"x": int(x), "y": int(y),
                              "columns": int(columns), "rows": int(rows)}

    def recall(self, key: str) -> dict | None:
        remembered = self.geometry.get(key)
        if not isinstance(remembered, dict):
            return None
        try:
            columns, rows = clamp_size(
                key, remembered["columns"], remembered["rows"])
            return {"x": int(remembered["x"]), "y": int(remembered["y"]),
                    "columns": columns, "rows": rows}
        except (KeyError, TypeError, ValueError):
            return None


def _int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
