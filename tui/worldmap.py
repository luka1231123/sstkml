"""The court's known-world tablet: the map, and what can be done on it.

This is still not an atlas. It draws only the places and links present in the
projected ``world_graph`` Belief, with the source, age, certainty and seasonal
availability Belief supplies -- and it holds no list of Late Bronze Age place
names and no coordinates of its own. What changed is where the coordinates come
from: `content/` authors them, Belief carries them, and `tui/chart.py` turns
them into cells. A scenario set on a different sea draws a different map from
the same code, and a scenario that authors no coordinates still loses nothing,
because a place the tablet cannot locate is listed beside the map rather than
dropped from it.

Three things are on the screen at once, because they are three views of one
question -- who can I reach, how, and what can I do about it:

* the chart, with every known place and a stable, quiet copy of every road
* the route tablet, which opens on the roads from that place but can still be
  turned over to read every known road
* the communication instruments intended for the selected court

The restraint is deliberate. Thirty-four places joined by forty-three solid
lines is not a map in a character grid; it is a knot. The complete network is
there in sparse marks and does not redraw itself when a place is chosen.
"""
from __future__ import annotations

import heapq

from tui import art, chart, style
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

# How often the stable chart lays down a glyph. Sparse tracks keep the complete
# network present without letting forty-three routes turn into a black knot.
CLOSED_STRIDE = 3
MAP_STRIDE = {"land": 3, "river": 3, "sea": 4, "unknown": 5}

# What a place is, in one glyph. The seat is a walled city, a court you write
# to is a diamond, anywhere else is a ring, and a place you have shut the road
# to is struck out.
SEAT_MARK = "▣"
COURT_MARK = "◇"
PLACE_MARK = "○"
CHOSEN_MARK = "◆"
SHUT_MARK = "✗"


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


def places_in_order(b: dict) -> list[dict]:
    """Every place on the tablet, seat first and the rest by name.

    The one order the whole window agrees on: what the arrow keys walk, what a
    number means, and what the map claims to hold. A screen with two ideas
    about which place is next is the bug this exists to prevent.
    """
    graph = b.get("world_graph") or {}
    seat = str(b.get("seat", ""))
    places = [dict(place) for place in graph.get("places", [])
              if isinstance(place, dict)]
    return sorted(places, key=lambda place: (
        str(place.get("id", "")) != seat,
        _spoken(place.get("name") or place.get("id", "")).lower(),
        str(place.get("id", "")),
    ))


def routes_of(b: dict, place: str = "") -> list[dict]:
    """Every route, the ones touching `place` first."""
    graph = b.get("world_graph") or {}
    routes = [dict(route) for route in graph.get("routes", [])
              if isinstance(route, dict)]
    return sorted(routes, key=lambda route: (
        not (place and place in {str(route.get("a", "")),
                                 str(route.get("b", ""))}),
        str(route.get("a", "")), str(route.get("b", "")),
        str(route.get("mode", "")), _number(route.get("legs")),
    ))


def routes_from(b: dict, place: str) -> list[dict]:
    """The roads that actually touch the chosen place."""
    return [
        route for route in routes_of(b, place)
        if place in {str(route.get("a", "")), str(route.get("b", ""))}
    ]


def tablet_routes(b: dict, place: str, all_routes: bool = False) -> list[dict]:
    """The focused leaf of the route tablet, or its complete reverse."""
    return routes_of(b, place) if all_routes else routes_from(b, place)


def _relations_by_place(b: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for relation in b.get("relations", []):
        place = relation.get("place")
        if place and place not in found:
            found[str(place)] = relation
    return found


def court_at(b: dict, place: str) -> str:
    """The correspondent known at a place, if the map names one."""
    relation = _relations_by_place(b).get(place) or {}
    return str(relation.get("other") or "")


def route_path(b: dict, origin: str, destination: str) -> tuple[str, ...]:
    """The shortest known courier path, weighted by projected route legs."""
    if not origin or not destination:
        return ()
    if origin == destination:
        return (origin,)
    adjacent: dict[str, list[tuple[int, str]]] = {}
    for route in routes_of(b):
        a, z = str(route.get("a", "")), str(route.get("b", ""))
        if not a or not z:
            continue
        legs = max(1, _number(route.get("legs"), 1))
        adjacent.setdefault(a, []).append((legs, z))
        adjacent.setdefault(z, []).append((legs, a))
    queue: list[tuple[int, tuple[str, ...], str]] = [(0, (origin,), origin)]
    best: dict[str, int] = {}
    while queue:
        distance, path, here = heapq.heappop(queue)
        if distance >= best.get(here, distance + 1):
            continue
        best[here] = distance
        if here == destination:
            return path
        for legs, there in sorted(adjacent.get(here, ())):
            heapq.heappush(
                queue, (distance + legs, path + (there,), there))
    return ()


def path_legs(b: dict, path: tuple[str, ...]) -> int:
    """Known travel time along a path; zero means no complete known route."""
    if len(path) < 2:
        return 0
    edges = {
        frozenset((str(route.get("a", "")), str(route.get("b", "")))):
        max(1, _number(route.get("legs"), 1))
        for route in routes_of(b)
    }
    total = 0
    for a, z in zip(path, path[1:]):
        legs = edges.get(frozenset((a, z)))
        if legs is None:
            return 0
        total += legs
    return total


def _shut(b: dict) -> set[str]:
    plague = b.get("plague") or {}
    quarantined = plague.get("quarantined")
    return {str(place) for place in quarantined} if quarantined else set()


def _mark_of(place_id: str, b: dict, courts: dict[str, dict],
             selected: str) -> tuple[str, str]:
    """The glyph for a place and the palette name to draw it in."""
    if place_id in _shut(b):
        return SHUT_MARK, "blood"
    if place_id == str(b.get("seat", "")):
        return SEAT_MARK, "flame"
    if place_id == selected:
        return CHOSEN_MARK, "bone"
    if place_id in courts:
        esteem = str(courts[place_id].get("esteem", ""))
        return COURT_MARK, ESTEEM_TONE.get(esteem, "clay")
    return PLACE_MARK, "ash"


# --- the chart ----------------------------------------------------------------

def _near(cell: tuple[int, int], other: tuple[int, int]) -> bool:
    return max(abs(cell[0] - other[0]), abs(cell[1] - other[1])) <= 1


def _draw_chart(surface: Surface, b: dict, x: int, y: int,
                width: int, height: int, selected: str) -> dict[str, tuple[int, int]]:
    """Stable sparse routes, then marks, then a useful number of names.

    Drawn in that order because each layer may be written over by the next: a
    road runs behind a city rather than through its name, which is the same
    order a scribe would have drawn it in. Selection never changes route ink
    or label placement: a map that rearranges when touched cannot be learned.
    """
    places = places_in_order(b)
    at = chart.project(places, width, height, spacing=1)
    if not at:
        surface.text(x, y, "this tablet locates no place it names.",
                     C["ash"], C["ink"])
        return {}

    courts = _relations_by_place(b)
    seat = str(b.get("seat", ""))
    routes = routes_of(b)
    marks = set(at.values())
    # Names may not touch another city's mark. This small breathing space is
    # what stops strings such as "○Alalakh" and "◇▣Ugarit" reading as one
    # invented symbol when several ports project onto neighbouring cells.
    used: set[tuple[int, int]] = {
        (px + dx, py + dy)
        for px, py in marks
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if 0 <= px + dx < width and 0 <= py + dy < height
    }

    for route in routes:
        a, z = str(route.get("a", "")), str(route.get("b", ""))
        if a not in at or z not in at:
            continue          # a road to a place the tablet cannot locate
        mode = str(route.get("mode") or "unknown").lower()
        closed = str(route.get("availability") or "").lower() == "closed"
        glyph = (
            "·" if closed else
            "~" if mode == "sea" else
            "≈" if mode == "river" else
            chart.slope_glyph(at[a], at[z])
        )
        stride = CLOSED_STRIDE if closed else MAP_STRIDE.get(mode, 5)
        cells = chart.line(at[a], at[z])
        for step, (cx, cy) in enumerate(cells):
            if (cx, cy) in at.values():
                continue      # a city is not a milestone on its own road
            if step % stride:
                continue
            # A route may meet its own ends. It may not run through the halo of
            # an unrelated city and visually weld that city's mark to a road.
            if ((cx, cy) in used
                    and not _near((cx, cy), at[a])
                    and not _near((cx, cy), at[z])):
                continue
            surface.put(x + cx, y + cy, glyph, C["faint"], C["ink"])

    for place in places:
        place_id = str(place.get("id", ""))
        if place_id not in at:
            continue
        cx, cy = at[place_id]
        glyph, tone = _mark_of(place_id, b, courts, selected)
        if place_id == selected and place_id != seat:
            tone = "bone"
        surface.put(x + cx, y + cy, glyph, C[tone], C["ink"])
        surface.link(x + cx, y + cy, 1, 1,
                     f"world:place:{place_id}")

    # The label set is stable. Selection changes a mark and the inspector, not
    # which other names happen to survive collision placement.
    anchor_ids: set[str] = set()
    if at:
        anchor_ids.update((
            min(at, key=lambda place_id: at[place_id][0]),
            max(at, key=lambda place_id: at[place_id][0]),
            min(at, key=lambda place_id: at[place_id][1]),
            max(at, key=lambda place_id: at[place_id][1]),
        ))

    def label_rank(place: dict) -> tuple[int, str]:
        place_id = str(place.get("id", ""))
        rank = (
            0 if place_id == seat else
            1 if place_id in anchor_ids else
            2 if place_id in courts else
            3
        )
        return rank, _spoken(place.get("name") or "").lower()

    order = sorted(
        (place for place in places if str(place.get("id", "")) in at),
        key=label_rank)
    label_limit = (
        len(order) if len(order) <= 12
        else max(5, min(12, (width * height) // 80))
    )
    labels_drawn = 0
    for place in order:
        if labels_drawn >= label_limit:
            break
        place_id = str(place.get("id", ""))
        name = _spoken(place.get("name") or place_id)[:13]
        cell = at[place_id]
        spot = _label_spot(cell, len(name), width, height, used)
        chosen = place_id == selected
        if spot is None:
            continue
        lx, ly = spot
        surface.text(x + lx, y + ly, name,
                     C["bone"] if chosen else
                     C["gold"] if place_id == seat else C["dim"], C["ink"])
        # One blank cell between labels makes short port names read as
        # separate annotations rather than a single long place name.
        for step in range(-1, len(name) + 1):
            if 0 <= lx + step < width:
                used.add((lx + step, ly))
        surface.link(x + lx, y + ly, len(name), 1,
                     f"world:place:{place_id}")
        labels_drawn += 1
    return at


def _label_spot(cell: tuple[int, int], length: int, width: int, height: int,
                used: set[tuple[int, int]]) -> tuple[int, int] | None:
    """Somewhere clear to write a name, near the mark it belongs to.

    Tried to the right first, then left, then the rows above and below, which
    is the order that keeps a name on the same latitude as its city whenever
    the map has room for it.
    """
    cx, cy = cell
    candidates = []
    for distance in range(0, 4):
        rows = (0,) if distance == 0 else (-distance, distance)
        for dy in rows:
            candidates.extend((
                (cx + 2, cy + dy),
                (cx - length - 1, cy + dy),
            ))
        if distance:
            candidates.extend((
                (cx - length // 2, cy - distance),
                (cx - length // 2, cy + distance),
            ))
    for lx, ly in candidates:
        if lx < 0 or ly < 0 or ly >= height or lx + length > width:
            continue
        if any((lx + step, ly) in used for step in range(length)):
            continue
        return (lx, ly)
    return None


# --- the tablet beside it -----------------------------------------------------

def _route_row(route: dict, names: dict[str, str], room: int) -> tuple[str, str]:
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

    # How old the record is goes at the end of the first line rather than the
    # end of the second, because the second line is the one that runs out of
    # column first and staleness is the last thing that should fall off it.
    name_room = max(3, (room - len(age) - 8) // 2)
    endpoints = f"{glyph} {first[:name_room]} > {second[:name_room]}"
    endpoints = f"{endpoints:<{max(0, room - len(age) - 1)}} {age}"
    details = f"  {mode} · {distance} · {availability}{certainty}"
    return endpoints[:room], details[:room]


def _route_rows(surface: Surface, routes: list[dict], names: dict[str, str],
                start: int, end: int, selected: str, right: int, room: int,
                top: int) -> None:
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


def orders_for(b: dict, place: str) -> list[tuple[str, str, str, bool, str]]:
    """Communication leaves this map as writing, not immediate world mutation."""
    recipient = court_at(b, place)
    can_write = bool(recipient and place != str(b.get("seat", "")))
    stem = f"world:letter:{recipient}:" if can_write else ""
    return [
        ("w", "Letter", "at the Scribe's Desk", can_write,
         stem + "letter" if can_write else ""),
        ("e", "Envoy", "not yet wired", False, ""),
        ("g", "Gift", "by letter", can_write,
         stem + "gift" if can_write else ""),
        ("m", "Marriage", "by letter", can_write,
         stem + "marriage_proposal" if can_write else ""),
    ]


def _name_of(b: dict, place: str) -> str:
    for item in places_in_order(b):
        if str(item.get("id", "")) == place:
            return _spoken(item.get("name") or place)
    return ""


def _describe(b: dict, place: str, room: int) -> list[tuple[str, str]]:
    """The selected place written out: what it is, and how well it is known."""
    if not place:
        return [("nothing is selected on the tablet.", "ash")]
    entry = next((item for item in places_in_order(b)
                  if str(item.get("id", "")) == place), {})
    lines: list[tuple[str, str]] = []
    name = _spoken(entry.get("name") or place)
    lines.append((name[:room], "bone"))

    seat = str(b.get("seat", ""))
    courts = _relations_by_place(b)
    if place == seat:
        lines.append(("your own seat", "flame"))
    elif place in courts:
        relation = courts[place]
        esteem = _spoken(relation.get("esteem", "")) or "no regard recorded"
        unanswered = _number(relation.get("unanswered"))
        lines.append((f"a court in correspondence · {esteem}",
                      ESTEEM_TONE.get(str(relation.get("esteem", "")), "clay")))
        if unanswered:
            lines.append((f"{unanswered} letters unanswered", "blood"))
    else:
        lines.append(("no court of yours writes from there", "ash"))
    if place in _shut(b):
        lines.append(("the road to it is closed by your order", "blood"))

    certain = _certain(entry)
    _freshness, age = _age(entry)
    lines.append((f"{'charted' if certain else 'uncertain'} · {age}",
                  "dim" if certain else "ash"))
    legs = routes_from(b, place)
    open_legs = sum(1 for route in legs
                    if str(route.get("availability", "")).lower() != "closed")
    lines.append((f"{len(legs)} roads, {open_legs} open this season", "dim"))
    return [(text[:room], tone) for text, tone in lines]


# --- the window ---------------------------------------------------------------

def _right_layout(b: dict, place: str, height: int,
                  right_room: int) -> tuple[list[tuple[str, str]], int, int, int]:
    """Description and row budgets shared by drawing and key handling."""
    described = _describe(b, place, right_room)
    orders_top = height - 2 - len(orders_for(b, place))
    while len(described) > 2 and (orders_top - 7 - len(described)) // 2 < 1:
        described.pop()
    routes_top = 6 + len(described)
    route_room = max(0, (orders_top - 1 - routes_top) // 2)
    return described, orders_top, routes_top, route_room


def route_page_size(b: dict, place: str, height: int) -> int:
    """How many two-row route entries the current window can really show."""
    return max(1, _right_layout(b, place, height, 40)[3])


def compose(b: dict, width: int = 90, height: int = 30,
            route_scroll: int = 0, selected_place: str = "",
            notice: str = "", all_routes: bool = False) -> InteractiveScreen:
    """Compose the tablet: chart on the left, routes and orders on the right."""
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE KNOWN WORLD",
                note="[esc] close", drop=False)
    style.notice(surface, 2, 1, width - 4, notice)

    graph = b.get("world_graph") or {}
    places = places_in_order(b)
    place_ids = [str(place.get("id", "")) for place in places]
    seat_id = str(b.get("seat", ""))
    if selected_place not in place_ids:
        selected_place = (seat_id if seat_id in place_ids
                          else place_ids[0] if place_ids else "")
    routes = tablet_routes(b, selected_place, all_routes)

    split = max(30, min(width - 34, (width * 3) // 5))
    right = split + 2
    right_room = max(1, width - right - 2)

    chart_age = graph.get("age_turns")
    age_words = (f"copied {chart_age} fortnights ago"
                 if type(chart_age) is int and chart_age >= 0
                 else "copy date not recorded")
    surface.text(3, 2, f"source: {_source(graph)} · {age_words}"
                 [:max(0, width - 6)], C["dim"], C["ink"])

    for y in range(4, max(4, height - 2)):
        surface.put(split, y, "│", C["faint"], C["ink"])

    # The chart. It keeps the rows between the source line and the legend; the
    # projection uses as much of that as its own proportions allow and centres
    # what it uses, so a wider window shows a bigger map and not a stretched one.
    chart_top = 4
    chart_bottom = height - 6
    chart_height = max(1, chart_bottom - chart_top)
    chart_width = max(1, split - 3)
    at = _draw_chart(surface, b, 2, chart_top, chart_width, chart_height,
                     selected_place)

    unplaced = [place for place in places
                if str(place.get("id", "")) not in at]
    if unplaced:
        missing = ", ".join(
            _spoken(place.get("name") or place.get("id", ""))
            for place in unplaced)
        surface.text(2, chart_bottom,
                     f"not located on this tablet: {missing}"
                     [:max(0, chart_width)], C["ash"], C["ink"])
        for index, place in enumerate(unplaced[:6]):
            surface.link(2 + index, chart_bottom, 1, 1,
                         f"world:place:{place.get('id', '')}")

    legend = "─ land  ~ sea  ≈ river  · shut"
    surface.text(2, chart_bottom + 1, legend[:max(0, chart_width)],
                 C["faint"], C["ink"])
    sea = ("the sea lanes are open" if b.get("sea_open") is True
           else "the sea is shut; seasonal lanes are closed"
           if b.get("sea_open") is False
           else "seasonal state is not recorded")
    surface.text(2, chart_bottom + 2,
                 f"~ {sea} · ▣ seat  ◇ court  ○ place"
                 [:max(0, chart_width)],
                 C["lapis"] if b.get("sea_open") is True else C["ash"],
                 C["ink"])

    # The right column holds three blocks in a fixed order of importance: what
    # is selected, the roads from it, and what can be ordered. The orders are
    # pinned to the bottom and never given up -- a window that hides an order
    # because it ran out of rows is the fault this whole layout exists to
    # avoid -- so a short window spends what is left on the description, then
    # on the routes, and drops the route list last of all.
    orders = orders_for(b, selected_place)
    described, orders_top, routes_top, route_room = _right_layout(
        b, selected_place, height, right_room)

    surface.text(right, 4, "CHOSEN PLACE"[:right_room], C["gold"], C["ink"])
    for offset, (text, tone) in enumerate(described):
        if 5 + offset < orders_top - 1:
            surface.text(right, 5 + offset, text, C[tone], C["ink"])

    route_start, route_end = _slice(len(routes), route_scroll, route_room)
    names = {str(place.get("id", "")): _spoken(
        place.get("name") or place.get("id", "")) for place in places}
    if route_room:
        route_range = f"{route_start + 1}-{route_end}" if routes else "0"
        scope_label = "[a] here" if all_routes else "[a] all"
        heading = (
            f"ALL ROADS {route_range}/{len(routes)}"
            if all_routes else
            f"ROADS HERE {route_range}/{len(routes)}"
        )
        heading_room = max(0, right_room - len(scope_label) - 1)
        surface.text(right, routes_top - 1, heading[:heading_room],
                     C["gold"], C["ink"])
        if len(scope_label) <= right_room:
            scope_x = right + right_room - len(scope_label)
            surface.text(scope_x, routes_top - 1, scope_label,
                         C["flame"], C["ink"])
            surface.link(scope_x, routes_top - 1, len(scope_label), 1,
                         "world:routes:scope")
        if routes:
            _route_rows(surface, routes, names, route_start, route_end,
                        selected_place, right, right_room, routes_top)
        else:
            surface.text(right, routes_top,
                         "no routes are entered on this court map."
                         [:right_room], C["ash"], C["ink"])
    else:
        route_start, route_end = 0, 0

    surface.text(right, orders_top - 1, "CORRESPONDENCE"[:right_room],
                 C["gold"], C["ink"])
    for offset, (key, label, note, enabled, command) in enumerate(orders):
        y = orders_top + offset
        written = style.keycap(surface, right, y, key, label, enabled, command)
        surface.text(right + written + 1, y,
                     note[:max(0, right_room - written - 1)],
                     C["dim"] if enabled else C["ash"], C["ink"])

    actions = [
        style.FooterAction("↑", "previous", bool(places),
                           "world:place:previous"),
        style.FooterAction("↓", "next", bool(places), "world:place:next"),
    ]
    if route_start:
        actions.append(style.FooterAction(
            "ctrl-u", "earlier", True, "world:routes:previous"))
    if route_end < len(routes):
        actions.append(style.FooterAction(
            "ctrl-d", "more", True, "world:routes:next"))
    actions.append(style.FooterAction("esc", "close"))
    style.footer(surface, actions, y=height - 2, x=2, width=width - 4)
    return surface.interactive()


def compose_with_frieze(b: dict, width: int = 90, height: int = 30,
                        route_scroll: int = 0,
                        selected_place: str = "",
                        all_routes: bool = False) -> InteractiveScreen:
    """The same tablet under a seal frieze, retaining every hit region."""
    screen = compose(
        b, width, height, route_scroll, selected_place,
        all_routes=all_routes)
    surface = Surface(width, height)
    for y, row in enumerate(screen):
        for x, (glyph, fg, bg) in enumerate(row):
            surface.put(x, y, glyph, fg, bg)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    for hit in screen.hits:
        surface.link(
            hit.x, hit.y, hit.width, hit.height, hit.command, hit.enabled)
    return surface.interactive()
