"""The furniture: how a window is dressed, in one place (M11, D34).

Every window in the game is drawn with these and nothing else, so that changing
what a panel looks like is one edit rather than nine. The look is a DOS text-mode
program of about 1993 -- Turbo Vision, Norton Commander, the shareware menu you
booted from a floppy:

* a **title bar** that is a filled field, not a word floating in a gap
* a **drop shadow** down and to the right, because the panels overlap
* **key caps** with the letter picked out, so the keyboard is legible at a glance
* a **status bar** along the bottom saying what the keys do here

None of it is decoration for its own sake. The bar tells you which window has
your attention, the shadow tells you the windows stack, the caps tell you what to
press. A screen that reads in `plain_text` is still doing its job; the era is in
the glyphs, and the glyphs are all one column wide (`tui/grid.py`).
"""
from __future__ import annotations

import dataclasses
import re

from tui.grid import INDEX, Surface

C = INDEX

# Shading blocks, lightest to heaviest. The shadow uses the lightest; the lamp
# in the hall uses the heaviest. Ordinary text never uses them.
LIGHT, MEDIUM, HEAVY, FULL = "░", "▒", "▓", "█"


@dataclasses.dataclass(frozen=True)
class FooterAction:
    key: str
    label: str
    enabled: bool = True
    command: str = ""


def key_command(key: str) -> str:
    """Turn a printed key name into the event name used by the Tk backend."""
    return {
        "esc": "Escape",
        "enter": "Return",
        "space": "space",
        "tab": "Tab",
        "backspace": "BackSpace",
        "ctrl-d": "Control-d",
        "ctrl-o": "Control-o",
        "ctrl-s": "Control-s",
        "ctrl-u": "Control-u",
    }.get(key.lower(), key)


def _link_tokens(surface: Surface, x: int, y: int, text: str) -> None:
    """Make ordinary `[key] label` text obey the same mouse contract."""
    matches = list(re.finditer(r"\[([^\]]+)\]", text))
    for index, match in enumerate(matches):
        key = match.group(1)
        if "-" in key or ("/" in key and key != "/"):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        surface.link(x + match.start(), y, max(1, end - match.start()), 1,
                     key_command(key))


def shadow(surface: Surface, x: int, y: int, width: int, height: int) -> None:
    """A drop shadow one cell right and one down, cast onto the ground.

    Drawn with `░` in the shadow colour rather than a solid block: a solid one
    reads as a second panel, and the point is to say *this thing is above the
    ground*, quietly.
    """
    for row in range(y + 1, y + height + 1):
        surface.text(x + width, row, LIGHT, C["shadow"], C["ink"])
    surface.text(x + 1, y + height, LIGHT * max(0, width - 1),
                 C["shadow"], C["ink"])


def panel(surface: Surface, x: int, y: int, width: int, height: int,
          title: str = "", note: str = "", focus: bool = False,
          drop: bool = True) -> None:
    """A framed panel with a filled title bar and, at the foot, a status line.

    `focus` thickens the border, which is how the window with the keyboard says
    so in a game where every window is a real OS window and the toolkit's own
    focus ring is a thin blue line the player will not see.
    """
    style = "thick" if focus else "double"
    edge = C["flame"] if focus else C["faint"]
    if drop:
        shadow(surface, x, y, width, height)
    surface.box(x, y, width, height, style=style, fg=edge)

    if title:
        # Only the title itself is a field, not the whole top edge: a filled
        # edge is handsome in colour and a hole in monochrome, where the rule
        # would simply vanish. This way the border survives `plain_text`.
        label = f" {title} "[: max(0, width - 4)]
        bar(surface, x + 2, y, len(label), label, fg=C["bone"], bg=C["lapis"])
    if note:
        room = width - 4
        note = note[:room]
        surface.text(x + width - 2 - len(note), y + height - 1, note,
                     C["dim"], C["ink"])
        _link_tokens(surface, x + width - 2 - len(note),
                     y + height - 1, note)


def bar(surface: Surface, x: int, y: int, width: int, text: str,
        fg: int = C["bone"], bg: int = C["lapis"]) -> None:
    """A field of colour with text in it. The one place a background is used.

    Reverse video is how text mode made a heading, and it is still the cheapest
    way to say *this row is a different kind of thing* without a second font.
    """
    surface.fill(x, y, width, 1, " ", fg, bg)
    surface.text(x, y, text[:width], fg, bg)
    _link_tokens(surface, x, y, text[:width])


def keycap(surface: Surface, x: int, y: int, key: str, label: str,
           enabled: bool = True, command: str = "",
           bg: int | None = None) -> int:
    """`[S] the stack`, with the key hot and the label plain.

    Returns the width written, so a row of them can be laid out by walking.
    Disabled doors are drawn in ash and marked, never hidden: a door the player
    can see and cannot open is information, and a door that vanishes is a lie
    about the shape of the game.
    """
    bracket = C["dim"] if enabled else C["ash"]
    letter = C["flame"] if enabled else C["ash"]
    word = C["clay"] if enabled else C["ash"]
    field = C["ink"] if bg is None else bg
    surface.text(x, y, "[", bracket, field)
    surface.text(x + 1, y, key, letter, field)
    surface.text(x + 1 + len(key), y, "]", bracket, field)
    gap = x + len(key) + 3
    surface.text(gap, y, label, word, field)
    width = len(key) + 3 + len(label)
    if not enabled:
        surface.text(x + width + 1, y, "·", C["ash"], field)
        width += 2
    surface.link(x, y, width, 1, command or key_command(key), enabled)
    return width


def footer(surface: Surface,
           actions: tuple[FooterAction, ...] | list[FooterAction],
           y: int | None = None, x: int = 0,
           width: int | None = None) -> None:
    """A pinned status bar whose printed controls are also mouse targets."""
    y = surface.height - 1 if y is None else y
    width = surface.width - x if width is None else width
    bar(surface, x, y, width, "", fg=C["clay"], bg=C["lapis"])
    column = x + 1
    right = x + width - 1
    for action in actions:
        needed = len(action.key) + len(action.label) + 4
        if not action.enabled:
            needed += 2
        if column + needed > right:
            break
        column += keycap(
            surface, column, y, action.key, action.label, action.enabled,
            action.command, bg=C["lapis"]) + 3


# What an outcome looks like, in one place (UI/UX spec 8, "feedback"; 21).
#
# Every window that can refuse an order draws the refusal with this, so a
# refusal in the Roll and a refusal in the Muster are the same shape and the
# player learns to read one thing rather than nine. The glyph is the point: the
# specification requires that every colour-coded state also carry a glyph or a
# word, because a player on the monochrome path or with no red vision must
# still be able to tell "it worked" from "it did not".
NOTICE_MARKS = {
    "success": ("✓", "verdigris"),
    "refusal": ("✗", "flame"),
    "preview": ("?", "gold"),
    "cancelled": ("·", "ash"),
    "info": ("·", "bone"),
}


class Notice(str):
    """Feedback text that remembers which kind of outcome it reports.

    A `str` subclass rather than a pair, so that every screen already written
    against a plain `notice: str` keeps working unchanged -- it truncates and
    tests it exactly as before -- while screens that draw it through `notice()`
    below get the right mark and colour for free. The controller sets the kind
    once, where the outcome is known, and no composer has to be told.
    """

    kind: str

    def __new__(cls, text: str = "", kind: str = "info") -> "Notice":
        made = super().__new__(cls, text)
        made.kind = kind
        return made


def notice(surface: Surface, x: int, y: int, width: int,
           text: str, kind: str | None = None) -> None:
    """One line saying what came of the last order, marked by kind.

    Drawn where the order was given rather than only in the Hall: the audit
    found refusals reported into a window the player was not looking at, which
    is indistinguishable from the game ignoring the key.
    """
    if not text or width <= 2:
        return
    if kind is None:
        kind = getattr(text, "kind", "info")
    mark, colour = NOTICE_MARKS.get(kind, NOTICE_MARKS["info"])
    # Clear the span first. Several screens spend this row on a frieze, and a
    # refusal printed through decoration is worse than no decoration: what the
    # player must not miss takes the row for as long as it has something to say.
    surface.fill(x, y, width, 1, " ", C["clay"], C["ink"])
    surface.text(x, y, mark, C[colour], C["ink"])
    room = width - 2
    body = text if len(text) <= room else text[:max(0, room - 1)] + "…"
    surface.text(x + 2, y, body, C[colour], C["ink"])


def rule(surface: Surface, x: int, y: int, width: int,
         fg: int | None = None) -> None:
    surface.text(x, y, "─" * width, C["faint"] if fg is None else fg, C["ink"])


def meter(surface: Surface, x: int, y: int, width: int, filled: int,
          fg: int | None = None) -> None:
    """A bar of blocks. Full cells are `▓`, empty are `░`, and it never lies:
    a meter at one part in twelve shows one cell, not a rounded-up sliver."""
    filled = max(0, min(width, filled))
    surface.text(x, y, HEAVY * filled, C["flame"] if fg is None else fg, C["ink"])
    surface.text(x + filled, y, LIGHT * (width - filled), C["ash"], C["ink"])


def heading(surface: Surface, x: int, y: int, text: str,
            right: str = "", width: int = 0) -> None:
    """A section heading inside a panel: bright, spaced, with a right-hand fact."""
    surface.text(x, y, text, C["bone"], C["ink"])
    if right and width:
        surface.text(x + width - len(right), y, right, C["dim"], C["ink"])
