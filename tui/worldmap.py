"""The court's known-world tablet: a data-driven operational graph.

This is not an atlas.  It draws only the places and links present in the
projected ``world_graph`` Belief, along with the source, age, certainty, and
seasonal availability that Belief supplies.  In particular, this module has no
list of Late Bronze Age place names and no scenario-specific coordinates.

The graph is rendered as two navigable collections rather than a coastline:
nodes on the left and edges on the right.  That scales to a scenario larger
than one window without silently dropping the tail, and it stays honest about
what a route tablet can say.
"""
from __future__ import annotations

from tui import art, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

MODE_GLYPH = {"land": "·", "sea": "~", "river": "≈"}
MODE_TONE = {"land": "sand", "sea": "lapis", "river": "sky"}
CERTAIN_WORDS = frozenset({"charted", "confirmed", "known", "certain"})

ESTEEM_TONE = {
    "honoured": "gold",
    "warm": "barley",
    "formal": "clay",
    "displeased": "blood",
    "cold": "blood",
    "hostile": "blood",
}


def _spoken(value: object) -> str:
    return str(value).replace("_", " ")


def _certain(item: dict) -> bool:
    """Use the supplied epistemic state; absence is not certainty."""
    if item.get("known") is False:
        return False
    return str(item.get("certainty", "")).lower() in CERTAIN_WORDS


def _age(item: dict) -> tuple[str, str]:
    """Return a visible marker *and* words, so age is never colour-only."""
    age = item.get("age_turns")
    if type(age) is not int or age < 0:
        return "?", "undated"
    if age < 3:
        return "●", "fresh"
    if age <= 8:
        return "○", f"{age}f old"
    return "·", f"stale {age}f"


def _slice(length: int, scroll: int, room: int) -> tuple[int, int]:
    room = max(1, room)
    start = max(0, min(scroll, max(0, length - room)))
    return start, min(length, start + room)


def _number(value: object, default: int = 0) -> int:
    return value if type(value) is int else default


def _source(graph: dict) -> str:
    source = graph.get("source")
    return _spoken(source) if source else "source not recorded"


def _place_rows(
    surface: Surface,
    b: dict,
    places: list[dict],
    start: int,
    end: int,
    selected: str,
    split: int,
    top: int,
) -> None:
    by_place: dict[str, list[dict]] = {}
    for relation in b.get("relations", []):
        place = relation.get("place")
        if place:
            by_place.setdefault(place, []).append(relation)

    seat = b.get("seat", "")
    for offset, place in enumerate(places[start:end]):
        y = top + offset
        place_id = str(place.get("id", ""))
        name = _spoken(place.get("name") or place_id or "(unnamed)")
        active = place_id == selected
        relations = by_place.get(place_id, [])
        unanswered = sum(
            _number(relation.get("unanswered")) for relation in relations)
        esteem = str(relations[0].get("esteem", "")) if relations else ""

        certain = _certain(place)
        mark = "▣" if place_id == seat else ("◇" if certain else "?")
        freshness, age = _age(place)
        epistemic = age if certain else f"uncertain · {age}"
        if unanswered:
            epistemic += f" · mail {unanswered}"

        surface.text(2, y, ">" if active else " ",
                     C["flame"] if active else C["ash"], C["ink"])
        tone_name = (
            "flame" if place_id == seat
            else ESTEEM_TONE.get(esteem, "clay") if relations
            else "ash")
        surface.text(4, y, mark, C[tone_name], C["ink"])
        surface.text(6, y, freshness,
                     C["clay"] if certain else C["ash"], C["ink"])

        state_room = min(18, max(10, split // 3))
        name_room = max(1, split - 9 - state_room)
        surface.text(8, y, name[:name_room],
                     C["bone"] if active else C[tone_name], C["ink"])
        state_x = max(9, split - state_room)
        surface.text(state_x, y, epistemic[:max(0, split - state_x - 1)],
                     C["dim"] if certain else C["ash"], C["ink"])
        surface.link(2, y, max(1, split - 3), 1,
                     f"world:place:{place_id}", enabled=bool(place_id))


def _route_row(
    route: dict,
    names: dict[str, str],
    room: int,
) -> tuple[str, str]:
    first_id = str(route.get("a", ""))
    second_id = str(route.get("b", ""))
    first = names.get(first_id, _spoken(first_id) or "?")
    second = names.get(second_id, _spoken(second_id) or "?")
    mode = str(route.get("mode") or "unknown").lower()
    glyph = MODE_GLYPH.get(mode, "?")
    legs = route.get("legs")
    distance = f"{legs}f" if type(legs) is int and legs >= 0 else "?f"
    availability = str(route.get("availability") or "unknown").lower()
    certainty = "" if _certain(route) else " · uncertain"
    _freshness, age = _age(route)

    name_room = max(3, (room - 6) // 2)
    endpoints = f"{glyph} {first[:name_room]} > {second[:name_room]}"
    details = (
        f"  {mode} · {distance} · {availability}{certainty} · {age}")
    return endpoints[:room], details[:room]


def _route_rows(
    surface: Surface,
    routes: list[dict],
    names: dict[str, str],
    start: int,
    end: int,
    selected: str,
    right: int,
    room: int,
    top: int,
) -> None:
    for offset, route in enumerate(routes[start:end]):
        y = top + offset * 2
        mode = str(route.get("mode") or "unknown").lower()
        incident = selected and selected in {
            str(route.get("a", "")), str(route.get("b", ""))}
        surface.text(right, y, ">" if incident else " ",
                     C["flame"] if incident else C["ash"], C["ink"])
        endpoints, details = _route_row(route, names, max(0, room - 2))
        availability = str(route.get("availability") or "unknown").lower()
        tone = (
            C["ash"] if not _certain(route) or availability == "unknown"
            else C["faint"] if availability == "closed"
            else C[MODE_TONE.get(mode, "clay")])
        surface.text(right + 2, y, endpoints, tone, C["ink"])
        surface.text(right + 2, y + 1, details,
                     C["dim"] if _certain(route) else C["ash"], C["ink"])
        a = str(route.get("a", ""))
        z = str(route.get("b", ""))
        surface.link(right, y, room, 2, f"world:route:{a}:{z}",
                     enabled=bool(a and z))


def compose(
    b: dict,
    width: int = 86,
    height: int = 30,
    place_scroll: int = 0,
    route_scroll: int = 0,
    selected_place: str = "",
    notice: str = "",
) -> InteractiveScreen:
    """Compose a page of the projected graph.

    ``place_scroll`` and ``route_scroll`` are independent because a scenario can
    have many more edges than nodes.  They are offsets, not page numbers, which
    lets an integrating controller move by either one row or one screen.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE KNOWN WORLD",
                note="[esc] close", drop=False)
    style.notice(surface, 2, 1, width - 4, notice)

    graph = b.get("world_graph") or {}
    seat_id = str(b.get("seat", ""))
    places = sorted(
        (dict(place) for place in graph.get("places", [])
         if isinstance(place, dict)),
        key=lambda place: (
            str(place.get("id", "")) != seat_id,
            str(place.get("id", ""))),
    )
    routes = sorted(
        (dict(route) for route in graph.get("routes", [])
         if isinstance(route, dict)),
        key=lambda route: (
            str(route.get("a", "")), str(route.get("b", "")),
            str(route.get("mode", "")), _number(route.get("legs"))),
    )
    place_ids = {str(place.get("id", "")) for place in places}
    if selected_place not in place_ids:
        selected_place = (
            seat_id if seat_id in place_ids
            else str(places[0].get("id", "")) if places else "")
    routes.sort(key=lambda route: (
        selected_place not in {
            str(route.get("a", "")), str(route.get("b", ""))},
        str(route.get("a", "")), str(route.get("b", "")),
        str(route.get("mode", "")), _number(route.get("legs")),
    ))

    split = max(30, min(width - 30, width // 2))
    right = split + 2
    right_room = max(1, width - right - 2)
    top = 7
    collection_room = max(1, height - top - 4)
    route_room = max(1, collection_room // 2)
    place_start, place_end = _slice(
        len(places), place_scroll, collection_room)
    route_start, route_end = _slice(
        len(routes), route_scroll, route_room)

    chart_age = graph.get("age_turns")
    age_words = (
        f"copied {chart_age} fortnights ago"
        if type(chart_age) is int and chart_age >= 0
        else "copy date not recorded")
    surface.text(
        3, 2,
        f"source: {_source(graph)} · {age_words}"[:max(0, width - 6)],
        C["dim"], C["ink"])
    surface.text(
        3, 3,
        "a route tablet: nodes and courier legs, not a surveyed atlas"
        [:max(0, width - 6)],
        C["ash"], C["ink"])

    for y in range(4, max(4, height - 3)):
        surface.put(split, y, "│", C["faint"], C["ink"])

    place_range = (
        f"{place_start + 1}-{place_end}" if places else "0")
    route_range = (
        f"{route_start + 1}-{route_end}" if routes else "0")
    surface.text(
        2, 4, f"PLACES  {place_range} OF {len(places)}"[:max(0, split - 3)],
        C["gold"], C["ink"])
    surface.text(
        right, 4,
        f"ROUTES  {route_range} OF {len(routes)}"[:right_room],
        C["gold"], C["ink"])

    x = 2
    x += style.keycap(
        surface, x, 5, "↑", "earlier", place_start > 0,
        "world:places:previous") + 2
    style.keycap(
        surface, x, 5, "↓", "later", place_end < len(places),
        "world:places:next")
    x = right
    x += style.keycap(
        surface, x, 5, "ctrl-u", "earlier", route_start > 0,
        "world:routes:previous") + 2
    style.keycap(
        surface, x, 5, "ctrl-d", "later", route_end < len(routes),
        "world:routes:next")

    if places:
        _place_rows(
            surface, b, places, place_start, place_end, selected_place,
            split, top)
    else:
        surface.text(3, top, "no places are entered on this court map.",
                     C["ash"], C["ink"])

    names = {
        str(place.get("id", "")): _spoken(
            place.get("name") or place.get("id", ""))
        for place in places
    }
    if routes:
        _route_rows(
            surface, routes, names, route_start, route_end, selected_place,
            right, right_room, top)
    else:
        surface.text(right, top, "no routes are entered on this court map.",
                     C["ash"], C["ink"])

    sea = (
        "~ the sea lanes are open"
        if b.get("sea_open") is True
        else "~ the sea is shut; seasonal lanes are closed"
        if b.get("sea_open") is False
        else "~ seasonal state is not recorded")
    surface.text(3, height - 3, sea[:max(0, width - 6)],
                 C["lapis"] if b.get("sea_open") is True else C["ash"],
                 C["ink"])
    style.footer(surface, (
        style.FooterAction("↑", "places up", place_start > 0,
                           "world:places:previous"),
        style.FooterAction("↓", "places down", place_end < len(places),
                           "world:places:next"),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 4)
    return surface.interactive()


def compose_with_frieze(
    b: dict,
    width: int = 86,
    height: int = 30,
    place_scroll: int = 0,
    route_scroll: int = 0,
    selected_place: str = "",
) -> InteractiveScreen:
    """The same graph under a seal frieze, retaining every hit region."""
    screen = compose(
        b, width, height, place_scroll, route_scroll, selected_place)
    surface = Surface(width, height)
    for y, row in enumerate(screen):
        for x, (glyph, fg, bg) in enumerate(row):
            surface.put(x, y, glyph, fg, bg)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    for hit in screen.hits:
        surface.link(
            hit.x, hit.y, hit.width, hit.height, hit.command, hit.enabled)
    return surface.interactive()
