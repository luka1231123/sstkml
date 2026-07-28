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


def page_size(height: int) -> int:
    return max(1, height - 15)


def reveal_scroll(length: int, selected_index: int, scroll: int,
                  room: int) -> int:
    """Clamp a list offset and reveal the selected row."""
    scroll = max(0, min(scroll, max(0, length - room)))
    if selected_index < scroll:
        return selected_index
    if selected_index >= scroll + room:
        return min(max(0, length - room), selected_index - room + 1)
    return scroll


def compose(b: dict, selected_place: str = "", width: int = 78,
            height: int = 28, scroll: int = 0,
            notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="SICKNESS AND CLOSURES",
                note="[esc] close", drop=False)
    plague = b.get("plague", {})
    closed = set(plague.get("quarantined", []))
    dossiers = place_dossiers(b)
    place_ids = [item["id"] for item in dossiers]
    if selected_place not in place_ids:
        selected_place = place_ids[0] if place_ids else ""
    selected_index = (
        place_ids.index(selected_place) if selected_place in place_ids else 0)
    room = page_size(height)
    scroll = reveal_scroll(len(dossiers), selected_index, scroll, room)
    selected = next(
        (item for item in dossiers if item["id"] == selected_place), None)

    surface.text(3, 3, "at the royal city", C["gold"], C["ink"])
    sickness = plague.get("sickness_at_seat", False)
    surface.text(
        24, 3,
        "sickness is visible" if sickness else "no general sickness is visible",
        C["blood"] if sickness else C["clay"], C["ink"])
    surface.text(3, 5, "burials reported", C["dim"], C["ink"])
    surface.text(24, 5, f"{plague.get('burials_at_seat', 0):,}",
                 C["bone"], C["ink"])
    offerings = plague.get("offerings_made", [])
    surface.text(
        47, 5, f"{len(offerings)} ritual offerings recorded"[:width - 50],
        C["dim"], C["ink"])
    style.rule(surface, 3, 7, width - 6)

    end = min(len(dossiers), scroll + room)
    position = (
        f"{scroll + 1}–{end} OF {len(dossiers)}" if dossiers else "NONE")
    surface.text(3, 9, f"KNOWN PLACES · {position}", C["gold"], C["ink"])
    for offset, dossier in enumerate(dossiers[scroll:end]):
        y = 11 + offset
        place = dossier["id"]
        active = place == selected_place
        marker = ">" if active else " "
        state = "CLOSED" if place in closed else "open"
        surface.text(3, y, marker, C["flame"] if active else C["ash"], C["ink"])
        surface.text(5, y, f"{dossier['name'][:21]:<21}",
                     C["bone"] if active else C["clay"], C["ink"])
        surface.text(28, y, state,
                     C["blood"] if place in closed else C["ash"], C["ink"])
        surface.link(3, y, 35, 1, f"plague:select:{place}")

    divider = 39
    for y in range(9, height - 2):
        surface.put(divider, y, "│", C["faint"], C["ink"])
    x = divider + 3
    available = width - x - 3
    surface.text(x, 9, "SELECTED PLACE DOSSIER", C["gold"], C["ink"])
    if selected is None:
        surface.text(x, 11, "No foreign place is on the court map.",
                     C["ash"], C["ink"])
    else:
        surface.text(x, 11, selected["name"].upper()[:available],
                     C["bone"], C["ink"])
        order = "routes ordered closed" if selected_place in closed else \
            "routes remain open"
        surface.text(x, 13, order[:available],
                     C["blood"] if selected_place in closed else C["clay"],
                     C["ink"])
        surface.text(x, 15, "sickness there", C["dim"], C["ink"])
        # No foreign infection flag crosses Belief. A future report projection
        # may replace this line; until then, absence of evidence is stated.
        surface.text(x, 16, "no current report is held"[:available],
                     C["ash"], C["ink"])
        surface.text(x, 18, "map record", C["dim"], C["ink"])
        surface.text(x, 19, selected["source"][:available],
                     C["clay"], C["ink"])
        age = selected["age_turns"]
        age_text = (
            "current this fortnight" if age == 0 else
            f"{age} fortnights old")
        surface.text(
            x, 20, f"{selected['certainty']} · {age_text}"[:available],
            C["sky"], C["ink"])
        correspondents = selected["correspondents"]
        surface.text(x, 22, "known hands there", C["dim"], C["ink"])
        names = ", ".join(
            render.actor_name(actor, b.get("house"))
            for actor in correspondents) if correspondents else "none recorded"
        surface.text(x, 23, names[:available], C["clay"], C["ink"])
        surface.text(x, 24, "not a live view"[:available],
                     C["ash"], C["ink"])

    style.notice(surface, 3, height - 3, width - 6, notice)

    style.footer(surface, (
        style.FooterAction(
            "↑", "previous", enabled=selected_index > 0,
            command="plague:previous"),
        style.FooterAction(
            "↓", "next", enabled=selected_index + 1 < len(dossiers),
            command="plague:next"),
        style.FooterAction("q", "close/lift selected",
                           enabled=bool(selected_place)),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 4)
    return surface.interactive()
