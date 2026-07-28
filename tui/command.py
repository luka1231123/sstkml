"""The command palette window (UI/UX spec 10, 6).

A 68 x 15 utility: the line being typed, the form it matches, what each part
resolved to, what it will cost, and the legal completions for whichever part is
not yet understood. Nothing on it can be slow and nothing on it is advice.

The layout follows the specification's sketch. What matters most is the third
band: when the line cannot be understood, this window says *which word* and
*what was allowed instead*, because "guess the verb" is the failure mode a text
interface has to design against (Emily Short's parser note, cited in spec 4).
"""
from __future__ import annotations

import palette
from tui import style
from tui.grid import INDEX, Screen, Surface

C = INDEX

DEFAULT_WIDTH, DEFAULT_HEIGHT = 68, 15


def compose(line: str, result: palette.Parse, hours_left: int,
            width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT,
            history: tuple[str, ...] = (), notice: str = "") -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="COMMAND",
                note="[esc] close", focus=True, drop=False)
    room = width - 6

    # The line, with a block cursor. This window is always typing.
    surface.text(2, 2, ">", C["flame"], C["ink"])
    surface.text(4, 2, line[-room:], C["bone"], C["ink"])
    surface.put(4 + min(len(line), room), 2, "█", C["flame"], C["ink"])

    # The form being matched, so the shape of the order is visible while it is
    # still half typed.
    form = result.form.text if result.form is not None else ""
    surface.text(4, 3, form[:room], C["sky"], C["ink"])

    # What each part resolved to. This is the specification's "explicit current
    # selection": nothing in a typed order may refer to something invisible.
    y = 4
    if result.values:
        parts = "   ".join(f"{name}: {value}"
                           for name, value in result.values.items())
        surface.text(4, y, parts[:room], C["clay"], C["ink"])
        y += 1

    # The verdict. One of three, and never silence.
    if result.status == "ok":
        surface.text(4, y, palette.preview(result)[:room],
                     C["verdigris"], C["ink"])
        if palette.handoff(result):
            surface.text(4, y + 1,
                         f"opens the {palette.handoff(result)}"[:room],
                         C["dim"], C["ink"])
        elif result.cost > hours_left:
            surface.text(4, y + 1,
                         f"✗ {result.cost} hours; {hours_left} remain"[:room],
                         C["flame"], C["ink"])
    elif result.status == "error":
        style.notice(surface, 3, y, room + 1,
                     style.Notice(result.message, "refusal"))
    elif result.status == "incomplete" and result.message:
        style.notice(surface, 3, y, room + 1,
                     style.Notice(result.message, "preview"))
    y += 2

    # What is legal here. Clickable, because the specification asks for
    # suggestions that can be taken with the mouse as well as with Tab.
    offers = result.options or (palette.VERBS if not line else ())
    if offers:
        surface.text(2, y, "try:", C["dim"], C["ink"])
        column = 7
        for offer in offers:
            if column + len(offer) + 2 > width - 3:
                surface.text(column, y, "…", C["dim"], C["ink"])
                break
            surface.text(column, y, offer, C["barley"], C["ink"])
            surface.link(column, y, len(offer), 1, f"complete:{offer}")
            column += len(offer) + 2
    y += 2

    if history and y < height - 3:
        surface.text(2, y, "last:", C["dim"], C["ink"])
        surface.text(8, y, history[-1][:room - 6], C["ash"], C["ink"])

    style.notice(surface, 3, height - 3, room, notice)
    style.footer(surface, (
        style.FooterAction("tab", "complete", enabled=bool(offers)),
        style.FooterAction("up", "history", enabled=bool(history)),
        style.FooterAction("enter", "do it", enabled=result.status == "ok"),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 4)
    return surface.interactive()
