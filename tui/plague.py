"""The court's sickness record and the routes it can order closed.

The page never turns the engine's disease state into royal knowledge.  It shows
what is observable at the seat, the ruler's own closure orders, and an explicit
``unknown`` when no report about a foreign place has reached the court.
"""
from __future__ import annotations

from tui import render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def place_dossiers(b: dict) -> list[dict]:
    """Return known foreign places without inventing disease observations.

    The World tablet is the authority for which places the court map contains.
    Older/synthetic Belief fixtures may not have ``world_graph`` yet, so the
    relations ledger remains a compatibility fallback.  Correspondents and map
    provenance are useful dossier context; neither is evidence of sickness.
    """
    relations_by_place: dict[str, list[str]] = {}
    for relation in b.get("relations", []):
        place = relation.get("place")
        actor = relation.get("other")
        if place and actor:
            relations_by_place.setdefault(place, []).append(actor)

    graph = b.get("world_graph", {})
    graph_places = list(graph.get("places", []))
    if graph_places:
        source_rows = graph_places
    else:
        source_rows = [
            {
                "id": place,
                "name": place.replace("_", " "),
                "source": "relations ledger",
                "age_turns": 0,
                "certainty": "reported",
            }
            for place in relations_by_place
        ]

    seat = b.get("seat")
    return [
        {
            "id": str(place["id"]),
            "name": str(place.get("name") or place["id"]).replace("_", " "),
            "source": str(place.get("source") or graph.get("source")
                          or "court map"),
            "age_turns": max(
                0, int(place.get("age_turns", graph.get("age_turns", 0)))),
            "certainty": str(place.get("certainty") or "uncertain"),
            "correspondents": tuple(sorted(
                relations_by_place.get(str(place["id"]), ()))),
        }
        for place in sorted(source_rows, key=lambda item: str(item["id"]))
        if str(place["id"]) != seat
    ]


def page_size(height: int, width: int = 78) -> int:
    """Rows available to the place list in either responsive arrangement."""
    if width >= 72 and height >= 28:
        return max(1, height - 15)
    return max(1, height - 18)


def reveal_scroll(length: int, selected_index: int, scroll: int,
                  room: int) -> int:
    """Clamp a list offset and reveal the selected row."""
    scroll = max(0, min(scroll, max(0, length - room)))
    if selected_index < scroll:
        return selected_index
    if selected_index >= scroll + room:
        return min(max(0, length - room), selected_index - room + 1)
    return scroll


def _fit(text: object, width: int) -> str:
    """Fit one semantic line without leaving a chopped word at the frame."""
    if width <= 0:
        return ""
    value = str(text)
    if len(value) <= width:
        return value
    if width == 1:
        return "…"
    head = value[:width - 1].rstrip()
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return (head or value[:width - 1]) + "…"


def _summary(surface: Surface, plague: dict, width: int) -> None:
    """The two directly observable court facts, compact enough for 58 cells."""
    room = max(1, width - 6)
    sickness = plague.get("sickness_at_seat", False)
    condition = (
        "sickness is visible"
        if sickness else "no general sickness is visible"
    )
    surface.text(
        3, 3, _fit(f"ROYAL CITY · {condition}", room),
        C["blood"] if sickness else C["clay"], C["ink"])
    burials = plague.get("burials_at_seat", 0)
    offerings = len(plague.get("offerings_made", []))
    surface.text(
        3, 5,
        _fit(f"burials reported {burials:,} · ritual offerings {offerings}",
             room),
        C["dim"], C["ink"])
    style.rule(surface, 3, 7, width - 6)


def _draw_places(surface: Surface, dossiers: list[dict], closed: set,
                 selected_place: str, scroll: int, room: int,
                 y: int, width: int) -> None:
    """Draw complete place/state rows; state never collides with the name."""
    end = min(len(dossiers), scroll + room)
    position = (
        f"{scroll + 1}–{end} OF {len(dossiers)}" if dossiers else "NONE")
    surface.text(
        3, y, _fit(f"KNOWN PLACES · {position}", width - 6),
        C["gold"], C["ink"])
    state_width = 6
    state_x = width - 3 - state_width
    name_width = max(1, state_x - 6)
    for offset, dossier in enumerate(dossiers[scroll:end]):
        row = y + 2 + offset
        place = dossier["id"]
        active = place == selected_place
        marker = ">" if active else " "
        state = "CLOSED" if place in closed else "open"
        surface.text(
            3, row, marker, C["flame"] if active else C["ash"], C["ink"])
        surface.text(
            5, row, f"{_fit(dossier['name'], name_width):<{name_width}}",
            C["bone"] if active else C["clay"], C["ink"])
        surface.text(
            state_x, row, f"{state:>{state_width}}",
            C["blood"] if place in closed else C["ash"], C["ink"])
        surface.link(
            3, row, max(1, width - 6), 1, f"plague:select:{place}")


def _draw_stacked(surface: Surface, selected: dict | None,
                  selected_place: str, closed: set, b: dict,
                  dossiers: list[dict], scroll: int, room: int,
                  width: int) -> None:
    """Compact ledger: dossier first, then a short scrollable place list."""
    text_width = max(1, width - 6)
    surface.text(
        3, 8, _fit("SELECTED PLACE DOSSIER", text_width),
        C["gold"], C["ink"])
    if selected is None:
        surface.text(
            3, 9, _fit("No foreign place is on the court map.", text_width),
            C["ash"], C["ink"])
    else:
        route = (
            "routes ordered closed"
            if selected_place in closed else "routes remain open"
        )
        surface.text(
            3, 9,
            _fit(f"{selected['name'].upper()} · {route}", text_width),
            C["blood"] if selected_place in closed else C["bone"], C["ink"])
        surface.text(
            3, 10,
            _fit("sickness · no current report is held", text_width),
            C["ash"], C["ink"])
        age = selected["age_turns"]
        age_text = (
            "current this fortnight" if age == 0
            else f"{age} fortnights old"
        )
        surface.text(
            3, 11,
            _fit(
                f"map · {selected['source']} · "
                f"{selected['certainty']} · {age_text}",
                text_width,
            ),
            C["sky"], C["ink"])
        correspondents = selected["correspondents"]
        names = ", ".join(
            render.actor_name(actor, b.get("house"))
            for actor in correspondents) if correspondents else "none recorded"
        prefix = "known hands · "
        suffix = " · not a live view"
        names = _fit(names, max(1, text_width - len(prefix) - len(suffix)))
        surface.text(
            3, 12,
            _fit(f"{prefix}{names}{suffix}", text_width),
            C["clay"], C["ink"])
    _draw_places(
        surface, dossiers, closed, selected_place, scroll, room,
        13, width)


def _draw_split(surface: Surface, selected: dict | None,
                selected_place: str, closed: set, b: dict,
                dossiers: list[dict], scroll: int, room: int,
                width: int, height: int) -> None:
    """Wide ledger: place list and dossier remain visible side by side."""
    divider = max(35, min(39, width // 2))
    list_width = divider - 3
    end = min(len(dossiers), scroll + room)
    position = (
        f"{scroll + 1}–{end} OF {len(dossiers)}" if dossiers else "NONE")
    surface.text(
        3, 9, _fit(f"KNOWN PLACES · {position}", list_width - 3),
        C["gold"], C["ink"])
    for offset, dossier in enumerate(dossiers[scroll:end]):
        y = 11 + offset
        place = dossier["id"]
        active = place == selected_place
        state = "CLOSED" if place in closed else "open"
        surface.text(
            3, y, ">" if active else " ",
            C["flame"] if active else C["ash"], C["ink"])
        surface.text(
            5, y, f"{_fit(dossier['name'], 21):<21}",
            C["bone"] if active else C["clay"], C["ink"])
        surface.text(
            28, y, state,
            C["blood"] if place in closed else C["ash"], C["ink"])
        surface.link(3, y, divider - 4, 1, f"plague:select:{place}")

    for y in range(9, height - 2):
        surface.put(divider, y, "│", C["faint"], C["ink"])
    x = divider + 3
    available = width - x - 3
    surface.text(
        x, 9, _fit("SELECTED PLACE DOSSIER", available),
        C["gold"], C["ink"])
    if selected is None:
        surface.text(
            x, 11, _fit("No foreign place is on the court map.", available),
            C["ash"], C["ink"])
        return

    surface.text(
        x, 11, _fit(selected["name"].upper(), available),
        C["bone"], C["ink"])
    order = (
        "routes ordered closed"
        if selected_place in closed else "routes remain open"
    )
    surface.text(
        x, 13, _fit(order, available),
        C["blood"] if selected_place in closed else C["clay"], C["ink"])
    surface.text(x, 15, _fit("sickness there", available),
                 C["dim"], C["ink"])
    surface.text(x, 16, _fit("no current report is held", available),
                 C["ash"], C["ink"])
    surface.text(x, 18, _fit("map record", available),
                 C["dim"], C["ink"])
    surface.text(x, 19, _fit(selected["source"], available),
                 C["clay"], C["ink"])
    age = selected["age_turns"]
    age_text = (
        "current this fortnight" if age == 0 else f"{age} fortnights old")
    surface.text(
        x, 20, _fit(f"{selected['certainty']} · {age_text}", available),
        C["sky"], C["ink"])
    correspondents = selected["correspondents"]
    surface.text(x, 22, _fit("known hands there", available),
                 C["dim"], C["ink"])
    names = ", ".join(
        render.actor_name(actor, b.get("house"))
        for actor in correspondents) if correspondents else "none recorded"
    surface.text(x, 23, _fit(names, available), C["clay"], C["ink"])
    surface.text(x, 24, _fit("not a live view", available),
                 C["ash"], C["ink"])


def compose(b: dict, selected_place: str = "", width: int = 78,
            height: int = 28, scroll: int = 0,
            notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="SICKNESS AND CLOSURES",
                drop=False)
    plague = b.get("plague", {})
    closed = set(plague.get("quarantined", []))
    dossiers = place_dossiers(b)
    place_ids = [item["id"] for item in dossiers]
    if selected_place not in place_ids:
        selected_place = place_ids[0] if place_ids else ""
    selected_index = (
        place_ids.index(selected_place) if selected_place in place_ids else 0)
    split = width >= 72 and height >= 28
    room = page_size(height, width)
    scroll = reveal_scroll(len(dossiers), selected_index, scroll, room)
    selected = next(
        (item for item in dossiers if item["id"] == selected_place), None)

    _summary(surface, plague, width)
    if split:
        _draw_split(
            surface, selected, selected_place, closed, b,
            dossiers, scroll, room, width, height)
    else:
        _draw_stacked(
            surface, selected, selected_place, closed, b,
            dossiers, scroll, room, width)

    style.notice(surface, 3, height - 3, width - 6, notice)

    route_label = "lift" if selected_place in closed else "close"
    style.footer(surface, (
        style.FooterAction(
            "↑", "prev", enabled=selected_index > 0,
            command="plague:previous"),
        style.FooterAction(
            "↓", "next", enabled=selected_index + 1 < len(dossiers),
            command="plague:next"),
        style.FooterAction("q", route_label,
                           enabled=bool(selected_place)),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 4)
    return surface.interactive()
