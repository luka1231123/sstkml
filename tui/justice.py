"""The court of justice: two men, two claims, and no mark for the honest one.

This is a room rather than a ledger because judging is face-to-face work.  The
picture carries no answer: both litigants are given the same visual weight,
and hearing them reveals two stories rather than a truth value.
"""
from __future__ import annotations

import textwrap

from tui import art, render, style
from tui.grid import INDEX, Screen, Surface

C = INDEX


def _name(actor: str, b: dict) -> str:
    return render.actor_name(actor, b.get("house"))


def _wrap(surface: Surface, x: int, y: int, text: str, width: int,
          rows: int, colour: int) -> int:
    lines = textwrap.wrap(text, width)[:rows]
    for line in lines:
        surface.text(x, y, line, colour, C["ink"])
        y += 1
    return y


def compose(b: dict, selected: str = "", width: int = 90,
            height: int = 34, notice: str = "") -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height,
                title="THE COURT OF JUSTICE", drop=False)
    petitions = b.get("justice", {}).get("petitions", [])
    petition = next(
        (item for item in petitions if item["id"] == selected),
        petitions[0] if petitions else None)

    # The court: two equal figures on one floor, with the king's dais between.
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    style.notice(surface, 2, 1, width - 4, notice)
    left_x, right_x = 8, width - 23
    art.draw(surface, left_x, 2, art.LITIGANT_LEFT,
             lit=C["bone"], mid=C["clay"], dark=C["faint"])
    art.draw(surface, right_x, 2, art.LITIGANT_RIGHT,
             lit=C["bone"], mid=C["clay"], dark=C["faint"])
    centre = width // 2
    surface.text(centre - 10, 3, ".------------------.",
                 C["faint"], C["ink"])
    surface.text(centre - 10, 4, "| BEFORE THE KING  |",
                 C["sand"], C["ink"])
    surface.text(centre - 10, 5, "'--------+---------'", C["faint"], C["ink"])
    surface.text(centre - 1, 6, "||", C["faint"], C["ink"])
    surface.text(centre - 5, 7, "____||____", C["faint"], C["ink"])
    surface.text(centre - 8, 11, "-" * 17, C["faint"], C["ink"])

    if petition is not None:
        left_name = _name(petition["petitioner"], b)
        right_name = _name(petition["against"], b)
        surface.text(2, 12, left_name[:30], C["barley"], C["ink"])
        surface.text(width - 2 - min(30, len(right_name)), 12,
                     right_name[:30], C["wine"], C["ink"])
    else:
        surface.text(centre - 15, 9, "the king's floor is empty.",
                     C["ash"], C["ink"])

    top = 14
    style.bar(surface, 2, top, width - 4, " THE PETITIONS",
              fg=C["bone"], bg=C["faint"])
    list_width = 27
    if not petitions:
        surface.text(4, top + 2, "no one waits for a judgement.",
                     C["ash"], C["ink"])
    for index, item in enumerate(petitions[:8]):
        row = top + 2 + index
        mark = ">" if petition is item else " "
        surface.text(3, row, mark, C["flame"], C["ink"])
        style.keycap(surface, 5, row, str(index + 1),
                     item["kind"][:12])
        waited = f"{item['waiting']} fn"
        surface.text(list_width - len(waited), row, waited,
                     C["dim"], C["ink"])

    divider = list_width + 2
    for row in range(top + 1, height - 2):
        surface.put(divider, row, "|", C["faint"], C["ink"])

    x, room = divider + 3, width - divider - 5
    if petition is not None:
        y = top + 2
        matter = f"{petition['kind']} · waiting {petition['waiting']} fortnights"
        surface.text(x, y, matter[:room], C["bone"], C["ink"])
        y += 2
        precedent = petition.get("precedent")
        if precedent:
            cited = (
                f"They cite {precedent['document_ref']}: in another "
                f"{precedent['kind']} case you ruled {precedent['verdict']}.")
            y = _wrap(surface, x, y, cited, room, 2, C["sand"]) + 1
        if not petition["heard"]:
            y = _wrap(
                surface, x, y,
                "You know their names and the nature of the quarrel. "
                "Neither man has yet been heard.",
                room, 3, C["ash"])
        else:
            surface.text(x, y, f"{_name(petition['petitioner'], b)} says:",
                         C["barley"], C["ink"])
            y = _wrap(surface, x + 2, y + 1, petition["claim_text"],
                      room - 2, 3, C["clay"]) + 1
            if y < height - 6:
                surface.text(x, y, f"{_name(petition['against'], b)} answers:",
                             C["wine"], C["ink"])
                _wrap(surface, x + 2, y + 1, petition["counter_text"],
                      room - 2, 3, C["clay"])

    style.bar(
        surface, 2, height - 2, width - 4,
        " [h] hear — one hour   [f] for   [a] against   [s] split   [d] defer",
        fg=C["clay"], bg=C["lapis"])
    return surface.interactive()
