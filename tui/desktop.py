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
LAYOUT_VERSION = 2

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
    "anchor": WindowClass("anchor", (84, 28), (84, 26)),
    "workbench": WindowClass("workbench", (72, 24), (66, 22)),
    "ledger": WindowClass("ledger", (64, 22), (58, 20)),
    "document": WindowClass("document", (52, 19), (46, 18)),
    "utility": WindowClass("utility", (46, 17), (40, 15)),
    "palette": WindowClass("palette", (62, 14), (48, 11)),
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
    their class default -- Alu wants 96 columns for the skyline, the Inbox 90
    for its columns -- so the class is the rule and the pair is the exception.
    """
    cls = CLASSES[window_class]
    return WindowSpec(key, title, window_class,
                      default or cls.default, minimum or cls.minimum)


# Per-window sizes from UI/UX specification sections 6, 13, 14, 15, 16 and 17.
# Entity windows are keyed by prefix: `institution:tablet_house` is a document.
WINDOWS: dict[str, WindowSpec] = {
    spec.key: spec for spec in (
        # The Hall stops at the narrowest width that preserves its carved
        # palace column. Below 84 columns the room lost its identity and read
        # as another flat dashboard. It no longer shrinks vertically either:
        # twenty-eight rows is what the year wheel needs under the legitimacy
        # block, and below that the calendar was dropped in silence -- the one
        # thing a room may never do with a fact it holds. Refusing to shrink is
        # the house rule for exactly this case.
        _spec("hall", "The Hall", "anchor", (84, 28), (84, 28)),
        _spec("stack", "The Scribes' Room", "workbench", (80, 27), (78, 26)),
        # Four full-size houses, their labels and their matching ledger rows
        # all fit at this floor. A shorter Alu used to cover those labels
        # with the Works band while still advertising the hidden number keys.
        _spec("alu", "The Alu", "workbench", (74, 25), (70, 25)),
        _spec("orders", "Orders", "workbench", (72, 24), (66, 22)),
        # The World is intentionally exempt from the compact desktop pass.
        _spec("world", "The Known World", "workbench", (104, 32), (68, 22)),
        _spec("trade", "Trade", "workbench", (72, 24), (66, 22)),
        _spec("palace", "The Court", "workbench", (74, 25), (68, 24)),
        _spec("works", "Works", "ledger", (66, 23), (62, 21)),
        _spec("plague", "Sickness and Closures", "ledger", (62, 22), (58, 20)),
        _spec("roll", "The Roll", "ledger", (66, 23), (62, 21)),
        # The Land carries the year band and the full estate dossier -- season,
        # hands, gauge, crop, due, ground. Eighty-two by twenty-eight is the
        # measured floor at which none of it is cut, now that the pane lays its
        # facts two to a row; it is wider than the old sixty-four and two rows
        # shorter, because the width is what the dossier was actually short of.
        _spec("land", "The Land", "ledger", (84, 29), (82, 28)),
        _spec("muster", "The Muster", "ledger", (64, 22), (60, 20)),
        _spec("oaths", "The Oaths", "ledger", (62, 22), (58, 20)),
        # The Storehouse hosts the Land page on its third tab, so it cannot be
        # smaller than the Land: the same dossier cut in half is still cut.
        _spec("stores", "The Storehouse", "workbench", (84, 29), (82, 28)),
        # The Shrine keeps enough vertical room for its medium altar vignette
        # above the fixed ritual controls, even at the minimum geometry.
        _spec("altar", "The Shrine", "document", (54, 24), (52, 22)),
        _spec("counsel", "Counsel", "document", (52, 18), (50, 17)),
        _spec("fortnight", "The Fortnight", "document", (54, 18), (50, 17)),
        _spec("help", "Help", "utility"),
        _spec("palette", "Command", "palette"),
        _spec("switcher", "Windows", "utility", (42, 17), (40, 15)),
        _spec("institution:", "Institution", "document", (50, 19), (46, 18)),
        _spec("focus:", "Record", "document", (72, 30), (58, 22)),
        _spec("letter:", "Tablet", "document", (50, 20), (46, 18)),
        _spec("archive:", "Tablet", "document", (50, 20), (46, 18)),
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
    layout_version: int = LAYOUT_VERSION

    @classmethod
    def load(cls, path: str | Path) -> "Preferences":
        try:
            raw = json.loads(Path(path).read_text())
        except Exception:
            return cls()
        if not isinstance(raw, dict):
            return cls()
        geometry = raw.get("geometry")
        if isinstance(geometry, dict) and _int(
                raw.get("layout_version"), 0) < LAYOUT_VERSION:
            geometry = _migrate_geometry(geometry)
        prefs = cls(
            font_size=clamp_font(_int(raw.get("font_size"), FONT_DEFAULT)),
            font_family=str(raw.get("font_family") or ""),
            ascii_only=bool(raw.get("ascii_only", False)),
            restore_placement=bool(raw.get("restore_placement", True)),
            geometry=geometry if isinstance(geometry, dict) else {},
            layout_version=LAYOUT_VERSION,
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

    def forget(self, key: str = "") -> None:
        """Drop a remembered geometry: one window, or every one.

        Without this a window could only ever be resized, never reset: the
        size the player last dragged it to outlived every change to what the
        screen actually needs to show.
        """
        if key:
            self.geometry.pop(key, None)
        else:
            self.geometry.clear()

    def recall(self, key: str) -> dict | None:
        remembered = self.geometry.get(key)
        if not isinstance(remembered, dict):
            return None
        try:
            columns = int(remembered["columns"])
            rows = int(remembered["rows"])
            columns, rows = clamp_size(key, columns, rows)
            return {"x": int(remembered["x"]), "y": int(remembered["y"]),
                    "columns": columns, "rows": rows}
        except (KeyError, TypeError, ValueError):
            return None


def _int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _migrate_geometry(geometry: dict) -> dict:
    """Compact inherited standalone-room sizes once; never resize World."""
    migrated = {}
    for key, raw in geometry.items():
        if not isinstance(raw, dict):
            migrated[key] = raw
            continue
        row = dict(raw)
        if family(key) != "world":
            default_columns, default_rows = default_size(key)
            try:
                row["columns"] = min(int(row["columns"]), default_columns)
                row["rows"] = min(int(row["rows"]), default_rows)
            except (KeyError, TypeError, ValueError):
                pass
        migrated[key] = row
    return migrated
