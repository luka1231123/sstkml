"""Terminal backend: a `Screen` as ANSI on stdout (spec 9.6, M11).

Not the shipped path -- that is Tk -- but not a toy either. This is how the
game is played over ssh, how it is played by someone who would rather have a
terminal, and it is the M15 eighty-column degrade path. It must keep working.

Colour is emitted only where it changes, so a screen of mostly-default text
costs a handful of escapes per row rather than one per cell.
"""
from __future__ import annotations

import os
import sys

from tui.grid import ANSI, Screen, pure_ascii

CLEAR = "\x1b[2J\x1b[H"
HOME = "\x1b[H"
RESET = "\x1b[0m"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"


def supports_colour(stream=None) -> bool:
    """Honour NO_COLOR and a dumb terminal; a pipe gets no escapes either."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") in ("", "dumb"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def to_ansi(screen: Screen, colour: bool = True,
            ascii_only: bool = False) -> str:
    """Render one screen to a string of ANSI. No IO, so it is testable."""
    if ascii_only:
        screen = pure_ascii(screen)
    out: list[str] = []
    for row in screen:
        current: tuple[int, int] | None = None
        for glyph, fg, bg in row:
            if colour and (fg, bg) != current:
                out.append(f"\x1b[38;5;{ANSI[fg]};48;5;{ANSI[bg]}m")
                current = (fg, bg)
            out.append(glyph)
        if colour:
            out.append(RESET)
        out.append("\n")
    return "".join(out).rstrip("\n")


def paint(screen: Screen, stream=None, clear: bool = True,
          colour: bool | None = None, ascii_only: bool = False) -> None:
    stream = stream or sys.stdout
    if colour is None:
        colour = supports_colour(stream)
    stream.write((CLEAR if clear else HOME)
                 + to_ansi(screen, colour, ascii_only) + RESET + "\n")
    stream.flush()


def size(default: tuple[int, int] = (100, 32)) -> tuple[int, int]:
    try:
        columns, lines = os.get_terminal_size()
        return max(80, columns), max(24, lines)
    except OSError:
        return default
