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

from tui import collection, render, style
from tui.grid import INDEX, InteractiveScreen, Screen, Surface

C = INDEX


RESULT_ROOM = 9          # the nine digits that open a result


def result_page(total: int, summary: str = "", width: int = 84,
                height: int = 32, scroll: int = 0, embedded: bool = False,
                selected: int = -1) -> collection.Page:
    top = 4 if embedded else 2
    aside = 24 if width >= 70 else 0
    field = width - aside - 6
    y = top + 4
    if summary:
        y += min(4, len(textwrap.wrap(" ".join(summary.split()), field - 2))) + 2
    room = max(1, min(RESULT_ROOM, (height - 6 - y) // 2))
    return collection.page(total, room, scroll, selected)


def compose(b: dict, query: str = "", hits: list[dict] | None = None,
            summary: str = "", typing: bool = False,
            width: int = 84, height: int = 32,
            notice: str = "", scroll: int = 0,
            embedded: bool = False, selected: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    size = b.get("archive_index", {}).get("size", 0)
    style.panel(
        surface, 0, 0, width, height,
        title=(
            f"SCRIBES' ROOM — {size} RECORDS ON THE SHELVES"
            if embedded else
            f"THE TABLET HOUSE — {size} tablets are shelved here"),
        note="",
        focus=typing, drop=False)
    top = 2
    if embedded:
        # Import locally to keep the archive usable as a standalone pure
        # document while sharing the room's one navigation strip.
        from tui.inbox import draw_views
        draw_views(surface, "records", width)
        top = 4

    # A compact shelf register replaces the large fixed illustration. Its fill
    # changes with the actual index, so the room keeps its physical identity
    # without surrendering half the window to furniture.
    searched = b.get("archive_index", {}).get("searched", [])
    aside = 24 if width >= 70 else 0
    if aside:
        divider = width - aside
        for row in range(2, height - 1):
            surface.put(divider, row, "│", C["faint"], C["ink"])
        shelf_x = divider + 3
        shelf_room = aside - 6
        surface.text(shelf_x, top, "SHELVES", C["bone"], C["ink"])
        capacity = max(1, shelf_room * 4)
        fill = min(capacity, max(0, int(size)))
        for shelf in range(4):
            used = max(0, min(shelf_room, fill - shelf * shelf_room))
            tablets = "▤" * used + "·" * (shelf_room - used)
            surface.text(shelf_x, top + 2 + shelf * 2, tablets,
                         C["sand"] if used else C["faint"], C["ink"])
            surface.text(shelf_x, top + 3 + shelf * 2, "─" * shelf_room,
                         C["faint"], C["ink"])
        if searched:
            surface.text(shelf_x, top + 11, "LAST REQUESTS",
                         C["dim"], C["ink"])
            for offset, past in enumerate(searched[-4:]):
                surface.text(
                    shelf_x, top + 12 + offset,
                    ("· " + str(past))[:shelf_room],
                    C["ash"], C["ink"])

    # --- the query -----------------------------------------------------------
    surface.text(3, top, "LOOK FOR", C["dim"], C["ink"])
    field = width - aside - 6
    style.bar(surface, 3, top + 1, field, " " + query[: field - 2],
              fg=C["bone"], bg=C["faint"])
    if typing:
        surface.put(4 + min(len(query), field - 3), top + 1, "█", C["flame"],
                    C["faint"])
    surface.text(3, top + 2, "─" * field, C["faint"], C["ink"])

    # --- what came back ------------------------------------------------------
    y = top + 4
    hits = hits or []
    if summary:
        surface.text(3, y, "KEEPER'S COLLATION", C["dim"], C["ink"])
        y += 1
        summary_lines = textwrap.wrap(" ".join(summary.split()), field - 2)
        for line in summary_lines[:4]:
            surface.text(3, y, line, C["bone"], C["ink"])
            y += 1
        y += 1
    if query and not hits and not typing:
        surface.text(3, y, "nothing in this house answers to that.",
                     C["ash"], C["ink"])
        y += 1
    # Results page without dropping anything the search found.
    selected_index = next((i for i, hit in enumerate(hits)
                           if str(hit.get("ref", "")) == selected), -1)
    visible = result_page(len(hits), summary, width, height, scroll,
                          embedded, selected_index)
    for index, _absolute, hit in visible.rows(hits):
        if y >= height - 6:
            break
        # The sender, then his own dating, and never a conversion of it: the
        # courts share no epoch (spec 6.17) and a normalised date would hand the
        # player a synchronisation nobody had.
        sender = hit.get("sender", "")
        who = render.actor_name(sender, b.get("house"))
        if who == sender:
            who = sender.replace("_", " ")
        surface.text(2, y, ">" if _absolute == selected_index else " ",
                     C["flame"], C["ink"])
        surface.text(3, y, f"{index}."[:2], C["flame"], C["ink"])
        surface.text(6, y, who[: field - 5], C["clay"], C["ink"])
        dated = str(hit.get("dated_as")
                    or f"turn {hit.get('received_turn', '?')}")
        if len(who) + len(dated) + 7 < field:
            surface.text(3 + field - len(dated) - 1, y, dated, C["sky"],
                         C["ink"])
        surface.link(3, y, field, 2, f"open:{hit.get('ref', '')}")
        y += 1
        snippet = hit.get("snippet", "")
        if snippet:
            surface.text(5, y, ("“" + snippet + "”")[: field - 6],
                         C["dim"], C["ink"])
            y += 1

    style.footer(surface, [
        style.FooterAction("/", "new search"),
        style.FooterAction("↑↓", "choose", enabled=bool(hits),
                           command="archive:next"),
        style.FooterAction("enter", "search · 1h" if typing or not hits else "open"),
        style.FooterAction("esc", "leave"),
    ], y=height - 2, x=2, width=width - 4)
    if visible.partial:
        surface.text(3, height - 3, f"results {visible.label()}"[:field],
                     C["dim"], C["ink"])
    style.notice(surface, 3, height - 4, field, notice)
    return surface.interactive()


def tablet(hit: dict, b: dict, width: int = 72,
           height: int = 24, scroll: int = 0,
           embedded: bool = False) -> Screen:
    """Open one projected archive record.

    The hit carries the complete projected body as well as its short finding
    aid. Long records scroll here, without reaching around the Belief boundary
    for a hidden engine document.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    ref = str(hit.get("ref", "unmarked tablet"))
    style.panel(
        surface, 0, 0, width, height,
        title=(f"SCRIBES' ROOM — RECORD {ref}"
               if embedded else f"TABLET {ref}"),
        note="[esc] back to the shelves" if embedded else "",
        drop=False)

    title = str(hit.get("title") or "untitled record")
    sender = str(hit.get("sender") or "")
    who = render.actor_name(sender, b.get("house")) if sender else "unknown hand"
    if who == sender:
        who = sender.replace("_", " ")
    dated = str(hit.get("dated_as")
                or f"received turn {hit.get('received_turn', '?')}")
    kind = str(hit.get("kind") or "record").replace("_", " ")

    surface.text(3, 2, title[:width - 6], C["bone"], C["ink"])
    surface.text(3, 4, f"hand: {who}"[:width - 6], C["clay"], C["ink"])
    surface.text(3, 5, f"date: {dated}"[:width - 6], C["sky"], C["ink"])
    surface.text(3, 6, f"kind: {kind}"[:width - 6], C["dim"], C["ink"])
    style.rule(surface, 3, 8, width - 6)

    body = str(
        hit.get("body") or hit.get("snippet") or
        "No legible text was indexed.")
    lines: list[str] = []
    for paragraph in body.split("\n\n"):
        if lines:
            lines.append("")
        lines.extend(textwrap.wrap(
            " ".join(paragraph.split()), width - 8) or [""])
    room = max(1, height - 15)
    scroll = max(0, min(scroll, max(0, len(lines) - room)))
    for offset, line in enumerate(lines[scroll:scroll + room]):
        surface.text(4, 10 + offset, line, C["clay"], C["ink"])

    tags = ", ".join(str(tag) for tag in hit.get("tags", []))
    if tags:
        surface.text(3, height - 4, ("marks: " + tags)[:width - 6],
                     C["ash"], C["ink"])
    position = ""
    if len(lines) > room:
        position = f" · lines {scroll + 1}–{min(len(lines), scroll + room)} of {len(lines)}"
    style.bar(
        surface, 2, height - 2, width - 4,
        f" [↑/↓] read{position}  ·  "
        f"[esc] {'back to the shelves' if embedded else 'return to the Tablet House'}",
        fg=C["clay"], bg=C["lapis"])
    return surface.freeze()
