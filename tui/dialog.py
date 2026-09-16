"""Small grid dialogs, drawn like every other screen: confirm, choose, write."""
from __future__ import annotations

import textwrap

from tui import style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def compose(title: str, body, options=(), *, typed: str | None = None,
            footer=(), width: int = 64, height: int = 16,
            notice: str = "") -> InteractiveScreen:
    """`body` is prose, `options` are (command, label) rows, `typed` is a pad."""
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title=title, drop=False)
    room, y = width - 6, 2
    for line in body:
        for wrapped in textwrap.wrap(line, room) or [""]:
            if y < height - 3:
                surface.text(3, y, wrapped, C["bone"], C["ink"])
                y += 1
    y += 1
    for index, (command, label) in enumerate(options, 1):
        if y >= height - 3:
            break
        text = f"[{index}] {label}"[:room]
        surface.text(3, y, text, C["bone"], C["ink"])
        surface.link(3, y, len(text), 1, command)
        y += 1
    if typed is not None:
        lines = typed.split("\n")
        top = max(y + 1, 4)
        for offset, line in enumerate(lines[-(height - top - 3):]):
            surface.text(3, top + offset, line[:room], C["sky"], C["ink"])
        last = lines[-1] if lines else ""
        surface.put(min(width - 4, 3 + len(last)),
                    top + min(len(lines), height - top - 3) - 1, "█",
                    C["flame"], C["ink"])
    style.notice(surface, 3, height - 3, room, notice)
    style.footer(surface, list(footer))
    return surface.interactive()
