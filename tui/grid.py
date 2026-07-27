"""The cell grid (spec 9.6, M11). The renderer's only output type.

A `Screen` is a rectangle of `(glyph, fg, bg)` and nothing above it knows what
draws it. The terminal backend and the window backend are both consumers and
neither is privileged.

The rule that makes this worth doing: **a screen is asserted, never a
screenshot.** Tests index cells and check glyphs and colours, in the same
headless run as the engine, with no GUI started and nothing compared by eye.

Two invariants are enforced here rather than trusted:

* every cell is exactly one column wide -- no combining marks, no East Asian
  wide forms, no control characters. A grid that silently desynchronises is
  worse than one that raises.
* nothing is drawn outside the surface. Writes clip; they never wrap onto the
  next line, because a wrapped ledger row is a misread number.
"""
from __future__ import annotations

import tomllib
import unicodedata
from pathlib import Path

Cell = tuple[str, int, int]                   # glyph, fg index, bg index
Screen = tuple[tuple[Cell, ...], ...]

_PALETTE_PATH = Path(__file__).parent.parent / "content" / "palette.toml"
_RAW = tomllib.loads(_PALETTE_PATH.read_text())

# Name -> index, and the reverse. Code and content name colours; only the
# backends ever see the number.
INDEX: dict[str, int] = {name: entry["index"] for name, entry in _RAW.items()}
NAMES: tuple[str, ...] = tuple(
    sorted(INDEX, key=lambda name: INDEX[name]))
RGB: tuple[str, ...] = tuple(_RAW[name]["rgb"] for name in NAMES)
ANSI: tuple[int, ...] = tuple(_RAW[name]["ansi"] for name in NAMES)

INK = INDEX["ink"]
CLAY = INDEX["clay"]


class BadGlyph(ValueError):
    """Something that is not one column wide was written to a cell."""


def _check(glyph: str) -> str:
    if len(glyph) != 1:
        raise BadGlyph(f"a cell holds exactly one character, got {glyph!r}")
    if unicodedata.category(glyph) in ("Cc", "Cf", "Mn", "Me"):
        raise BadGlyph(f"control or combining character in a cell: {glyph!r}")
    if unicodedata.east_asian_width(glyph) in ("W", "F"):
        raise BadGlyph(f"double-width character in a cell: {glyph!r}")
    return glyph


# Box furniture. `single` is a tablet, `double` a room worth being in, `thick`
# the window that has focus. Named rather than spelled at call sites so the
# pure-ASCII path has one place to translate.
BOXES = {
    "single": "┌┐└┘─│",
    "double": "╔╗╚╝═║",
    "thick":  "┏┓┗┛━┃",
    "ascii":  "++++-|",
}

# Spec 9.4: the sparkline, and its degrade.
BLOCKS = " ▁▂▃▄▅▆▇█"
BLOCKS_ASCII = " .:-=+*#@"

_ASCII_FOLD = {
    **{fancy: plain
       for style in ("single", "double", "thick")
       for fancy, plain in zip(BOXES[style], BOXES["ascii"])},
    **{block: plain for block, plain in zip(BLOCKS, BLOCKS_ASCII)},
    "·": ".", "—": "-", "–": "-", "…": ".", "▓": "#", "░": ".", "▒": "+",
    "•": "*", "→": ">", "←": "<", "↑": "^", "↓": "v", "×": "x",
}


class Surface:
    """A mutable rectangle you paint into, frozen to a `Screen` when done.

    Coordinates are (x, y) from the top left. Every write clips to the surface,
    so composing a panel never has to know whether it fits.
    """

    __slots__ = ("width", "height", "_rows")

    def __init__(self, width: int, height: int,
                 fg: int = CLAY, bg: int = INK, fill: str = " ") -> None:
        if width < 0 or height < 0:
            raise ValueError("a surface cannot have negative extent")
        _check(fill)
        self.width = width
        self.height = height
        self._rows: list[list[Cell]] = [
            [(fill, fg, bg) for _ in range(width)] for _ in range(height)]

    # --- painting ------------------------------------------------------------

    def put(self, x: int, y: int, glyph: str,
            fg: int = CLAY, bg: int = INK) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._rows[y][x] = (_check(glyph), fg, bg)

    def text(self, x: int, y: int, s: str,
             fg: int = CLAY, bg: int = INK) -> int:
        """Write a string on one line. Clips at the right edge, never wraps.

        Returns the number of glyphs actually placed, so a caller laying out a
        row can tell that it ran out of room instead of finding out later.
        """
        if not 0 <= y < self.height:
            return 0
        placed = 0
        for offset, glyph in enumerate(s):
            column = x + offset
            if column >= self.width:
                break
            if column < 0:
                continue
            self._rows[y][column] = (_check(glyph), fg, bg)
            placed += 1
        return placed

    def fill(self, x: int, y: int, width: int, height: int,
             glyph: str = " ", fg: int = CLAY, bg: int = INK) -> None:
        _check(glyph)
        for row in range(y, min(y + height, self.height)):
            if row < 0:
                continue
            for column in range(max(x, 0), min(x + width, self.width)):
                self._rows[row][column] = (glyph, fg, bg)

    def box(self, x: int, y: int, width: int, height: int,
            style: str = "single", fg: int = INDEX["faint"], bg: int = INK,
            title: str = "", title_fg: int | None = None) -> None:
        """A bordered frame, optionally titled on the top rule.

        The title is written into the border itself with a space either side,
        the way a label is scratched into a frame rather than floated above it.
        """
        if width < 2 or height < 2:
            return
        tl, tr, bl, br, horizontal, vertical = BOXES[style]
        right, bottom = x + width - 1, y + height - 1
        for column in range(x + 1, right):
            self.put(column, y, horizontal, fg, bg)
            self.put(column, bottom, horizontal, fg, bg)
        for row in range(y + 1, bottom):
            self.put(x, row, vertical, fg, bg)
            self.put(right, row, vertical, fg, bg)
        self.put(x, y, tl, fg, bg)
        self.put(right, y, tr, fg, bg)
        self.put(x, bottom, bl, fg, bg)
        self.put(right, bottom, br, fg, bg)
        if title and width >= len(title) + 6:
            self.text(x + 2, y, f" {title} ",
                      title_fg if title_fg is not None else fg, bg)

    def blit(self, other: "Surface", x: int, y: int) -> None:
        """Paint another surface into this one at (x, y), clipped."""
        for row_offset, row in enumerate(other._rows):
            target_row = y + row_offset
            if not 0 <= target_row < self.height:
                continue
            for column_offset, cell in enumerate(row):
                column = x + column_offset
                if 0 <= column < self.width:
                    self._rows[target_row][column] = cell

    # --- reading -------------------------------------------------------------

    def at(self, x: int, y: int) -> Cell:
        return self._rows[y][x]

    def freeze(self) -> Screen:
        return tuple(tuple(row) for row in self._rows)


# --- whole-screen transforms -------------------------------------------------

def plain_text(screen: Screen) -> str:
    """The screen with every colour dropped, one line per row.

    This is the monochrome path and it is also how most tests read a screen:
    if a distinction survives here it was never carried by colour alone, which
    is the rule (spec 9.6).
    """
    return "\n".join(
        "".join(cell[0] for cell in row).rstrip() for row in screen)


def pure_ascii(screen: Screen) -> Screen:
    """Fold box-drawing, blocks and typographic glyphs down to plain ASCII.

    The `--pure-ascii` flag and the M15 degrade path are this function, not a
    second renderer.
    """
    return tuple(
        tuple((_ASCII_FOLD.get(glyph, glyph), fg, bg) for glyph, fg, bg in row)
        for row in screen)


def sparkline(values: list[int], width: int = 24, ascii_only: bool = False) -> str:
    """Spec 9.4. One column per fortnight, scaled to the series' own maximum.

    Deliberately unlabelled and deliberately small: it shows a shape, and the
    player who wants a number has to go and count.
    """
    blocks = BLOCKS_ASCII if ascii_only else BLOCKS
    series = values[-width:]
    if not series:
        return ""
    ceiling = max(series)
    if ceiling <= 0:
        return blocks[0] * len(series)
    top = len(blocks) - 1
    return "".join(blocks[max(0, value) * top // ceiling] for value in series)
