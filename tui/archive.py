"""The tablet house: a setting, because the room makes the hour feel spent (D34).

The third and last drawn place. Searching the archive costs an hour per query
(spec 6.17) and the whole difficulty of M10 rests on the player being willing to
spend several of them on a hunch. A search box on a grey panel makes that feel
like an interface being slow. A room with shelves in it makes it feel like
walking in and reading, which is what it is.

The librarian summarises what was found and is bounded to the figures actually
in the hits (`ai/librarian.py` — and its fallback, which is what ships). He does
not tell the player which document matters. Two of Ugarit's three vows have been
in breach since before turn 1 and nothing in this room will ever say so (D31).
"""
from __future__ import annotations

import textwrap

from tui import art, render, style
from tui.grid import INDEX, Screen, Surface

C = INDEX


def compose(b: dict, query: str = "", hits: list[dict] | None = None,
            summary: str = "", typing: bool = False,
            width: int = 84, height: int = 32) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE TABLET HOUSE",
                focus=typing, drop=False)

    # The shelves, and how much is on them.
    art.draw(surface, width - 36, 2, art.SHELVES,
             lit=C["sand"], mid=C["dim"], dark=C["faint"], edge=C["faint"])
    size = b.get("archive_index", {}).get("size", 0)
    surface.text(width - 36, 13, f"{size} tablets are shelved here",
                 C["ash"], C["ink"])
    searched = b.get("archive_index", {}).get("searched", [])
    if searched:
        surface.text(width - 36, 14, "you have asked for:", C["dim"], C["ink"])
        for offset, past in enumerate(searched[-6:]):
            surface.text(width - 34, 15 + offset, f"· {past}"[:32],
                         C["ash"], C["ink"])

    # --- the query -----------------------------------------------------------
    surface.text(3, 2, "you are looking for", C["dim"], C["ink"])
    field = width - 42
    style.bar(surface, 3, 3, field, " " + query[: field - 2],
              fg=C["bone"], bg=C["faint"])
    if typing:
        surface.put(4 + min(len(query), field - 3), 3, "█", C["flame"],
                    C["faint"])
    surface.text(3, 4, "─" * field, C["faint"], C["ink"])

    # --- what came back ------------------------------------------------------
    y = 6
    hits = hits or []
    if summary:
        for line in textwrap.wrap(summary, field - 2):
            if y >= height - 8:
                break
            surface.text(3, y, line, C["bone"], C["ink"])
            y += 1
        y += 1
    if query and not hits and not typing:
        surface.text(3, y, "nothing in this house answers to that.",
                     C["ash"], C["ink"])
        y += 1
    for hit in hits[:10]:
        if y >= height - 6:
            break
        # The sender, then his own dating, and never a conversion of it: the
        # courts share no epoch (spec 6.17) and a normalised date would hand the
        # player a synchronisation nobody had.
        who = render.actor_name(hit.get("sender", ""), b.get("house"))
        surface.text(3, y, who[: field - 2], C["clay"], C["ink"])
        dated = str(hit.get("dated_as")
                    or f"turn {hit.get('received_turn', '?')}")
        if len(who) + len(dated) + 4 < field:
            surface.text(3 + field - len(dated) - 1, y, dated, C["sky"],
                         C["ink"])
        y += 1
        snippet = hit.get("snippet", "")
        if snippet:
            surface.text(5, y, ("“" + snippet + "”")[: field - 6],
                         C["dim"], C["ink"])
            y += 1

    style.bar(surface, 2, height - 2, width - 4,
              " [/] ask for a word   [enter] search — one hour   [esc] leave",
              fg=C["clay"], bg=C["lapis"])
    return surface.freeze()
