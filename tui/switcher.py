"""The Window Switcher: manage the desktop itself (UI/UX spec 13).

A compact list of what is open, in the order the player last touched it, with
a one-line note saying what each window is holding. Enter focuses, X closes an
auxiliary window, T tiles, C cascades.

The Hall is never offered for closing here. Closing it ends the session, and a
list where one row means "quit" and the others mean "tidy up" is a trap; the
Hall's own visible save-and-exit flow is the way out.
"""
from __future__ import annotations

import dataclasses

from tui import style
from tui.grid import INDEX as C, Surface

DEFAULT_WIDTH, DEFAULT_HEIGHT = 42, 17


@dataclasses.dataclass(frozen=True)
class Entry:
    key: str
    title: str
    note: str = ""
    closable: bool = True
    dirty: bool = False


def compose(entries, pick: str = "", width: int = DEFAULT_WIDTH,
            height: int = DEFAULT_HEIGHT, notice: str = ""):
    surface = Surface(width, height)
    listed = list(entries)
    if not listed:
        style.panel(surface, 0, 0, width, height, title="Windows",
                    note="0 open")
        surface.text(3, 2, "No windows are open.", C["dim"], C["ink"])
        style.footer(surface, (style.FooterAction("esc", "close"),))
        return surface.interactive()

    top = 2
    room = height - 5
    # Keep the selected row on screen without moving the list under the
    # player's finger any more than it has to.
    start = 0
    keys = [entry.key for entry in listed]
    if pick in keys and keys.index(pick) >= room:
        start = keys.index(pick) - room + 1
    shown = listed[start:start + room]

    style.panel(surface, 0, 0, width, height, title="Windows")

    # Range and total, on the top edge beside the title. `style.panel` puts its
    # own `note` on the *bottom* edge, where the footer paints over it, and the
    # foot of the list is already taken by the controls row -- writing it there
    # produced "[esc] done0". A list must say how much of itself is showing
    # (spec 8.8), so it goes where there is actually room for it.
    total = (f" {start + 1}-{start + len(shown)} of {len(listed)} "
             if len(listed) > len(shown) else f" {len(listed)} open ")
    if len(total) < width - 14:
        style.bar(surface, width - 2 - len(total), 0, len(total), total,
                  fg=C["bone"], bg=C["lapis"])

    for offset, entry in enumerate(shown):
        y = top + offset
        selected = entry.key == pick
        number = start + offset + 1
        marker = ">" if selected else " "
        fg = C["bone"] if selected else C["clay"]
        background = C["lapis"] if selected else C["ink"]
        if selected:
            surface.fill(1, y, width - 2, 1, " ", fg, background)
        surface.text(1, y, marker, C["flame"] if selected else C["dim"],
                     background)
        label = f"{number} {entry.title}"
        if entry.note:
            label += f" · {entry.note}"
        if entry.dirty:
            label += " *"
        surface.text(3, y, label[: width - 5], fg, background)
        # The whole row is a target, and activating it focuses that window.
        surface.link(1, y, width - 2, 1, f"switch:{entry.key}")

    if notice:
        surface.text(2, height - 3, notice[: width - 4], C["flame"], C["ink"])

    selected_entry = next((e for e in listed if e.key == pick), None)
    # Five controls do not fit on one 42-column footer, and `style.footer`
    # drops the overflow silently -- which would hide tile and cascade at the
    # switcher's own default size. The desktop commands get their own row.
    column = 2
    for key, label in (("t", "tile"), ("c", "cascade"), ("esc", "done")):
        column += style.keycap(surface, column, height - 3, key, label) + 3
    style.footer(surface, (
        style.FooterAction("enter", "focus"),
        style.FooterAction(
            "x", "close",
            enabled=bool(selected_entry and selected_entry.closable)),
    ))
    return surface.interactive()
