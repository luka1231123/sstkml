"""The court's known-world tablet: the map, and what can be done on it.

This is still not an atlas. It draws only the places, roads, ground and
holdings present in the projected ``world_graph`` Belief, with the source, age,
certainty and seasonal availability Belief supplies -- it holds no list of Late
Bronze Age place names and no geography of its own. `content/` authors the
ground as a grid of characters, Belief carries it, and `tui/atlas.py` decides
which part of it a window is looking at. A scenario set on a different sea
draws a different map from the same code.

The map is bigger than the window on purpose. Three hundred columns of ground
do not fit beside a route list, so the window moves over the map: the arrows
pan it, `+` and `-` change how much ground a character stands for, and the
selected place pulls the window to itself. A map that fits entirely on the
screen is a map with nothing on it worth walking to.

Three things are on the screen at once, because they are three views of one
question -- who can I reach, how, and what can I do about it:

* the map, with a mark per place and a line per road, both clickable
* the route tablet, which is the same edges written out with their legs,
  their season and how old the record is
* the orders that apply to whatever is selected, including the ones that
  belong to another window, which say so and open it
"""
from __future__ import annotations

from tui import art, atlas, style
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

POWER_WORD = {
    "egypt": "under Egypt",
    "hatti": "under Hatti",
    "ahhiyawa": "of the Ahhiyawa",
    "free": "under no overlord",
}
RANK_WORD = {
    "seat": "your own seat",
    "imperial": "an imperial capital",
    "royal": "a royal seat",
    "town": "a town",
}

# How often a route lays down a glyph. A road is solid, a sea lane is a dashed
# track, a lane the season has shut is a few dots -- so the three read apart in
# a monochrome terminal, where the mode colours are not there to help.
STRIDE = {"land": 1, "river": 1, "sea": 2, "unknown": 2}
CLOSED_STRIDE = 3

# What a place is, beyond its own mark, on the layers that ask. The rank
# brackets in `atlas` say what a place IS; these say what it is TO YOU, and
# they are only ever drawn on the layer that is about them.
COURT_MARK = "◇"
SHUT_MARK = "✗"

# The layers, and the order the tabs are written in.
#
# One tablet cannot answer seven questions at once. Drawn together, the ground,
# the roads, the sea lanes, the sown land, the holdings, who writes to you and
# where the sickness is come out as one wash of marks in which nothing can be
# found -- so each is a tab, the ground is the one you land on, and every other
# layer draws the ground faintly underneath itself to say where you are.
LAYERS = ("land", "roads", "trade", "farms", "holds", "courts", "sickness")
LAYER_NAME = {
    "land": "LAND",
    "roads": "ROADS",
    "trade": "TRADE",
    "farms": "FARMS",
    "holds": "HOLDS",
    "courts": "COURTS",
    "sickness": "PLAGUE",
}
LAYER_LEGEND = {
    "land": "{ } seat  [ ] imperial  ( ) royal  ~ sea  ^ upland  , sown",
    "roads": "─ road  ≈ river  Nf fortnights by courier  · shut this season",
    "trade": "╌ sea lane  Nf fortnights  * metal  Y cedar  n horses",
    "farms": ", sown ground  % a grain estate  : desert",
    "holds": "x a small palace, counted and not named",
    "courts": "◇ a court that writes to you  · silence from there",
    "sickness": "✗ the road is shut by your order  ○ nothing reported",
}
LAYER_UNDER = {
    "land": "the ground itself; the tabs above put things on it",
    "roads": "the roads and the rivers, in fortnights of courier time",
    "trade": "what crosses the sea, and where the metal comes from",
    "farms": "the sown ground, and the estates that work it",
    "holds": "the small palaces: your hinterland, and everyone else's",
    "courts": "the courts that write to you, and how they hold you",
    "sickness": "the roads you have shut, and the ones you have not",
}

# Which routes are the subject of which layer. A road is on Roads, a sea lane
# is on Trade, and neither is drawn anywhere else: roads over the ground layer
# were the wash of lines this window was split up to stop.
LAYER_MODES = {
    "roads": ("land", "river", "unknown"),
    "trade": ("sea",),
}

# Which holdings are the subject of which layer.
LAYER_SITES = {
    "holds": ("palace",),
    "farms": ("grain",),
    "trade": ("copper", "tin", "gold", "silver", "lapis", "cedar", "horses"),
}

# How far one press of an arrow moves the window, in characters of panel.
PAN_ACROSS = 10
PAN_DOWN = 5


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


def _relations_by_place(b: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for relation in b.get("relations", []):
        place = relation.get("place")
        if place and place not in found:
            found[str(place)] = relation
    return found


def _shut(b: dict) -> set[str]:
    plague = b.get("plague") or {}
    quarantined = plague.get("quarantined")
    return {str(place) for place in quarantined} if quarantined else set()


def _layer_of(layer: str) -> str:
    """The asked-for layer, or the ground itself if it is not one."""
    return layer if layer in LAYERS else LAYERS[0]


def _second_claim(place_id: str, b: dict, courts: dict[str, dict],
                  layer: str) -> bool:
    """Whether this place has no claim on a name beyond being on the map.

    After the selected place and the seat, the names that fit go to whoever the
    layer is about: the courts on Courts, the shut roads on Sickness. False
    sorts first, so a place with a claim is written before one without.
    """
    if layer == "courts":
        return place_id not in courts
    if layer == "sickness":
        return place_id not in _shut(b)
    return False


def _mark_of(place: dict, b: dict, courts: dict[str, dict],
             selected: str, layer: str = "land") -> tuple[str, str]:
    """The glyph for a place and the palette name to draw it in.

    A place's mark is what it is -- an imperial capital, a royal seat, a town,
    your own seat -- in brackets authored by the scenario, and its colour is
    whose empire answers for it. What a place is *to you* is a layer of its
    own: a court with an opinion, a road you have shut. Five meanings on one
    mark is a legend the player has to learn before he can read anything.
    """
    place_id = str(place.get("id", ""))
    letter = (str(place.get("glyph", "")) or
              _spoken(place.get("name") or place_id)[:1].upper() or "?")
    rank = str(place.get("rank", "town"))
    if place_id == str(b.get("seat", "")):
        rank = "seat"
    open_mark, close_mark = atlas.BRACKET.get(rank, ("", ""))

    tone = atlas.POWER_TONE.get(str(place.get("power", "")), "ash")
    if place_id == str(b.get("seat", "")):
        tone = "flame"
    elif place_id == selected:
        tone = "bone"
    if layer == "sickness":
        if place_id in _shut(b):
            return f"{open_mark}{SHUT_MARK}{close_mark}", "blood"
        tone = "ash" if place_id != selected else "bone"
    elif layer == "courts":
        if place_id in courts:
            esteem = str(courts[place_id].get("esteem", ""))
            return (f"{open_mark}{COURT_MARK}{close_mark}",
                    ESTEEM_TONE.get(esteem, "clay"))
        if place_id not in (selected, str(b.get("seat", ""))):
            tone = "ash"
    return f"{open_mark}{letter}{close_mark}", tone


# --- the map ------------------------------------------------------------------

def cell_of(place: dict) -> tuple[int, int] | None:
    """Where a place stands on the authored grid, if the tablet locates it."""
    col, row = place.get("col"), place.get("row")
    if type(col) is int and type(row) is int:
        return (col, row)
    return None


def focus_of(b: dict, place_id: str) -> tuple[int, int] | None:
    """The grid cell the window centres on when nothing has been panned."""
    for place in places_in_order(b):
        if str(place.get("id", "")) == place_id:
            return cell_of(place)
    return None


def _draw_ground(surface: Surface, rows: list[str], view: atlas.View,
                 x: int, y: int, layer: str) -> None:
    """The ground, before anything that matters is drawn on it.

    Under everything, and clickable by nothing: a stretch of dry plain cannot
    be ordered, sailed or written to, so putting a hit region on it would only
    steal clicks from the roads crossing it.

    On its own layer it is the subject and is drawn in its own colours. Under
    any other layer it is dimmed, where it does the one job left to it: saying
    which part of the world you are looking at. Farms is the exception, and
    dims everything except the ground it is about.
    """
    for down in range(view.height):
        for across in range(view.width):
            col, row = view.at((across, down))
            glyph = atlas.sample(rows, col, row, view.wide)
            if glyph == " ":
                continue
            tone = atlas.GROUND_TONE.get(glyph, "dim")
            if layer == "farms":
                tone = tone if glyph in (atlas.SOWN, atlas.RIVER) else "faint"
            elif layer != "land":
                tone = "faint" if glyph != atlas.SEA else "shadow"
            surface.put(x + across, y + down, glyph, C[tone], C["ink"])


def _draw_sites(surface: Surface, b: dict, view: atlas.View,
                x: int, y: int, layer: str,
                used: set[tuple[int, int]]) -> int:
    """The hinterland: holdings, estates and sources, none of them named.

    They are drawn only on the layer that asks about them, and they are never
    clickable -- there is no order in this game that names one, and a hit
    region on a thing you cannot act on is a lie about the shape of the game.
    """
    kinds = LAYER_SITES.get(layer, ())
    if not kinds:
        return 0
    drawn = 0
    for site in atlas.sites_of(b):
        kind = str(site.get("kind", ""))
        if kind not in kinds:
            continue
        spot = cell_of(site)
        if spot is None:
            continue
        cell = view.cell(*spot)
        if not view.inside(cell) or cell in used:
            continue
        surface.put(x + cell[0], y + cell[1],
                    atlas.SITE_GLYPH.get(kind, "x"),
                    C[atlas.site_tone(kind)], C["ink"])
        used.add(cell)
        drawn += 1
    return drawn


def _draw_routes(surface: Surface, b: dict, view: atlas.View, x: int, y: int,
                 layer: str, selected: str, marks: set[tuple[int, int]],
                 used: set[tuple[int, int]]) -> None:
    """The roads, and how many fortnights each of them is.

    The number is on the road rather than in the legend because that is the
    question the layer exists to answer: not where Carchemish is, which the
    ground already says, but how long a letter to it takes.
    """
    modes = LAYER_MODES.get(layer, ())
    if not modes:
        return
    ends: dict[str, tuple[int, int]] = {}
    for place in places_in_order(b):
        spot = cell_of(place)
        if spot is not None:
            ends[str(place.get("id", ""))] = view.cell(*spot)

    for route in routes_of(b):
        a, z = str(route.get("a", "")), str(route.get("b", ""))
        if a not in ends or z not in ends:
            continue          # a road to a place the tablet cannot locate
        mode = str(route.get("mode") or "unknown").lower()
        if mode not in modes:
            continue
        closed = str(route.get("availability") or "").lower() == "closed"
        incident = selected in (a, z)
        # In winter most of the sea is shut, and a dotted line for every lane
        # that is not there covers the map in debris the player cannot act on.
        # A shut lane is drawn when it is one of the selected place's own --
        # where it answers a question he is asking -- and is otherwise left to
        # the route tablet, which lists all of them and says which are closed.
        if closed and not incident:
            continue
        glyph = "·" if closed else atlas.slope_glyph(ends[a], ends[z])
        stride = CLOSED_STRIDE if closed else STRIDE.get(mode, 2)
        tone = ("faint" if closed
                else "bone" if incident
                else MODE_TONE.get(mode, "clay"))
        road = atlas.line(ends[a], ends[z])
        for step, cell in enumerate(road):
            if cell in marks or not view.inside(cell):
                continue      # a city is not a milestone on its own road
            surface.link(x + cell[0], y + cell[1], 1, 1,
                         f"world:route:{a}:{z}")
            if step % stride:
                continue
            surface.put(x + cell[0], y + cell[1], glyph, C[tone], C["ink"])
            used.add(cell)

        legs = _number(route.get("legs"), 0)
        if not legs or len(road) < 5:
            continue
        label = f"{legs}f"
        middle = road[len(road) // 2]
        spot = (middle[0] - 1, middle[1])
        if any((spot[0] + step, spot[1]) in marks or
               not view.inside((spot[0] + step, spot[1]))
               for step in range(len(label))):
            continue
        surface.text(x + spot[0], y + spot[1], label,
                     C["bone"] if incident else C["dim"], C["ink"])
        for step in range(len(label)):
            used.add((spot[0] + step, spot[1]))


def _draw_map(surface: Surface, b: dict, x: int, y: int,
              width: int, height: int, selected: str, layer: str = "land",
              wide: int = 1, focus: tuple[int, int] | None = None
              ) -> tuple[dict[str, tuple[int, int]], atlas.View | None]:
    """Ground, then holdings, then roads, then marks, then names.

    Drawn in that order because each is written over by the next: the ground
    runs behind a road, and a road runs behind a city rather than through its
    name, which is the same order a scribe would have drawn it in.
    """
    layer = _layer_of(layer)
    places = places_in_order(b)
    rows = atlas.ground_rows(b)
    if not rows:
        surface.text(x, y, "this tablet has no ground drawn on it.",
                     C["ash"], C["ink"])
        return {}, None

    view = atlas.frame_for(rows, width, height, focus=focus, wide=wide)
    _draw_ground(surface, rows, view, x, y, layer)

    courts = _relations_by_place(b)
    seat = str(b.get("seat", ""))
    used: set[tuple[int, int]] = set()

    # Where every mark goes, worked out before anything is drawn. Two hubs an
    # hour apart share a cell once the tablet is held back far enough, and a
    # mark drawn over another mark is a place that has silently vanished --
    # so the marks are laid out first, and one of the two steps aside.
    at, marks = _lay_marks(places, b, courts, selected, layer, view,
                           width, height)

    _draw_sites(surface, b, view, x, y, layer, used | marks)
    _draw_routes(surface, b, view, x, y, layer, selected, marks, used)

    for place in places:
        place_id = str(place.get("id", ""))
        if place_id not in at:
            continue
        cx, cy = at[place_id]
        glyph, tone = _mark_of(place, b, courts, selected, layer)
        # The brackets sit either side of the cell the place is actually in, so
        # the letter is on the spot and the rank is around it. A mark at the
        # edge of the window loses its brackets rather than its place.
        start = cx - (len(glyph) // 2)
        for step, mark in enumerate(glyph):
            if 0 <= start + step < width:
                surface.put(x + start + step, y + cy, mark, C[tone], C["ink"])
                used.add((start + step, cy))
        surface.link(x + max(0, start), y + cy,
                     min(len(glyph), width - max(0, start)), 1,
                     f"world:place:{place_id}")

    # Names, in the order of who most needs one. Whoever is left over keeps his
    # mark and his place in the tablet beside the map: a name that will not fit
    # is dropped, never the place.
    order = sorted(
        (place for place in places if str(place.get("id", "")) in at),
        key=lambda place: (
            str(place.get("id", "")) != selected,
            str(place.get("id", "")) != seat,
            _second_claim(str(place.get("id", "")), b, courts, layer),
            _spoken(place.get("name") or "").lower(),
        ))
    for place in order:
        place_id = str(place.get("id", ""))
        name = _spoken(place.get("name") or place_id)[:14]
        cell = at[place_id]
        spot = _label_spot(cell, len(name), width, height, used)
        if spot is None:
            continue
        lx, ly = spot
        surface.text(x + lx, y + ly, name,
                     C["bone"] if place_id == selected else
                     C["gold"] if place_id == seat else C["dim"], C["ink"])
        for step in range(len(name)):
            used.add((lx + step, ly))
        surface.link(x + lx, y + ly, len(name), 1, f"world:place:{place_id}")
    return at, view


def _span(cell: tuple[int, int], length: int) -> list[tuple[int, int]]:
    """The cells a mark of this length occupies, centred on its own cell."""
    start = cell[0] - (length // 2)
    return [(start + step, cell[1]) for step in range(length)]


def _lay_marks(places: list[dict], b: dict, courts: dict[str, dict],
               selected: str, layer: str, view: atlas.View,
               width: int, height: int
               ) -> tuple[dict[str, tuple[int, int]], set[tuple[int, int]]]:
    """Which cell each mark ends up in, and every cell the marks cover.

    The seat and the chosen place are laid first and never moved: those two
    are the ones the player is reading the map to find. Everything else takes
    the nearest free cell, and gives up rather than walking far enough to lie
    about where it is -- a place whose mark will not fit keeps its line in the
    tablet beside the map, which is where the whole list is anyway.
    """
    seat = str(b.get("seat", ""))
    order = sorted(places, key=lambda place: (
        str(place.get("id", "")) != seat,
        str(place.get("id", "")) != selected,
        _spoken(place.get("name") or "").lower()))

    at: dict[str, tuple[int, int]] = {}
    taken: set[tuple[int, int]] = set()
    for place in order:
        spot = cell_of(place)
        if spot is None:
            continue
        wanted = view.cell(*spot)
        glyph, _tone = _mark_of(place, b, courts, selected, layer)
        room = len(glyph)
        for dx, dy in ((0, 0), (0, -1), (0, 1), (room, 0), (-room, 0),
                       (room, -1), (-room, 1), (0, -2), (0, 2)):
            cell = (wanted[0] + dx, wanted[1] + dy)
            span = _span(cell, room)
            if not view.inside(cell) or any(
                    not view.inside(mark) for mark in span):
                continue
            if any(mark in taken for mark in span):
                continue
            at[str(place.get("id", ""))] = cell
            taken.update(span)
            # A mark needs air either side or two of them read as one word.
            taken.add((span[0][0] - 1, cell[1]))
            taken.add((span[-1][0] + 1, cell[1]))
            break
    return at, {cell for cell in taken if view.inside(cell)}


def _label_spot(cell: tuple[int, int], length: int, width: int, height: int,
                used: set[tuple[int, int]]) -> tuple[int, int] | None:
    """Somewhere clear to write a name, near the mark it belongs to.

    Tried to the right first, then left, then the rows above and below, which
    is the order that keeps a name on the same line as its city whenever the
    map has room for it. A name is written over the ground without hesitation:
    the ground is scenery, and a city with no name on it is not.
    """
    cx, cy = cell
    candidates = (
        (cx + 3, cy), (cx - length - 2, cy),
        (cx + 3, cy - 1), (cx + 3, cy + 1),
        (cx - length - 2, cy - 1), (cx - length - 2, cy + 1),
        (cx - length // 2, cy - 1), (cx - length // 2, cy + 1),
    )
    for lx, ly in candidates:
        if lx < 0 or ly < 0 or ly >= height or lx + length > width:
            continue
        # One clear cell either side, so two names never run together into a
        # third word that is on no map anywhere.
        if any((lx + step, ly) in used for step in range(-1, length + 1)):
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
    """What can be done about the selected place, and where it is done.

    Every order that names a place anywhere in the registry appears here,
    whichever window owns it, because the question "what can I do about Emar"
    is asked while looking at Emar. The ones this window does not own say which
    window does and open it; the ones that do not apply stay on the list,
    greyed, with the reason -- a door that vanishes is a lie about the shape of
    the game (spec 9.5).

    Returns (key, label, note, enabled, command).
    """
    import registry

    shut = place in _shut(b)
    courts = _relations_by_place(b)
    seat = str(b.get("seat", ""))

    close = registry.BY_ID["quarantine"]
    if not place or place == seat:
        orders = [(close.mnemonic or "q", close.label,
                   "your own seat", False, "")]
    elif shut:
        orders = [(close.mnemonic or "q", "Open",
                   "the road is shut", True, f"do:quarantine:{place}")]
    else:
        orders = [(close.mnemonic or "q", close.label,
                   "shut the road", True, f"do:quarantine:{place}")]

    # Orders this window does not own. They are listed because the question
    # "what can I do about Emar" is asked while looking at Emar, and they name
    # the window that takes them rather than pretending to take them here.
    elsewhere = (
        ("t", "assign_troops", "muster", "in the Muster", True),
        ("b", "begin_build", "works", "in the Works", True),
        ("m", "marry_abroad", "relations", "in Relations", place in courts),
    )
    for key, action_id, room, where, applies in elsewhere:
        descriptor = registry.BY_ID[action_id]
        if not applies:
            orders.append((key, descriptor.label, "no court there", False, ""))
            continue
        orders.append((key, descriptor.label, where,
                       bool(place), f"world:open:{room}"))
    orders.append(("p", "The sickness", "in Sickness", bool(place),
                   "world:open:plague"))
    return orders


def _name_of(b: dict, place: str) -> str:
    for item in places_in_order(b):
        if str(item.get("id", "")) == place:
            return _spoken(item.get("name") or place)
    return ""


def _wrap(text: str, room: int, lines: int = 2) -> list[str]:
    """Break a line of prose to the column, and no further than `lines`."""
    out: list[str] = []
    words = text.split()
    while words and len(out) < lines:
        row = words.pop(0)
        while words and len(row) + 1 + len(words[0]) <= room:
            row += " " + words.pop(0)
        out.append(row[:room])
    return out


def _hinterland(b: dict, place: str, room: int) -> list[tuple[str, str]]:
    """What lies behind a hub, counted by kind. Never named."""
    counted: dict[str, int] = {}
    for site in atlas.sites_of(b):
        if str(site.get("hub", "")) != place:
            continue
        kind = str(site.get("kind", ""))
        counted[kind] = counted.get(kind, 0) + 1
    if not counted:
        return []
    parts = []
    for kind, count in sorted(counted.items()):
        word = atlas.SITE_WORD.get(kind, kind)
        parts.append(f"{count} {word}" if count > 1 or kind in
                     ("palace", "grain") else word)
    return [(line, "dim") for line in
            _wrap("hinterland: " + " · ".join(parts), room, 2)]


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
    rank = "seat" if place == seat else str(entry.get("rank", "town"))
    power = str(entry.get("power", ""))
    standing = RANK_WORD.get(rank, "a town")
    if power and rank != "seat":
        standing = f"{standing} {POWER_WORD.get(power, '')}".strip()
    lines.append((standing[:room],
                  "flame" if place == seat
                  else atlas.POWER_TONE.get(power, "clay")))
    role = _spoken(entry.get("role", ""))
    for line in _wrap(role, room, 2) if role else []:
        lines.append((line, "dim"))

    if place in courts:
        relation = courts[place]
        esteem = _spoken(relation.get("esteem", "")) or "no regard recorded"
        unanswered = _number(relation.get("unanswered"))
        lines.append((f"a court in correspondence · {esteem}"[:room],
                      ESTEEM_TONE.get(str(relation.get("esteem", "")), "clay")))
        if unanswered:
            lines.append((f"{unanswered} letters unanswered", "blood"))
    elif place != seat:
        lines.append(("no court of yours writes from there", "ash"))
    if place in _shut(b):
        lines.append(("the road to it is closed by your order", "blood"))

    lines.extend(_hinterland(b, place, room))

    certain = _certain(entry)
    _freshness, age = _age(entry)
    lines.append((f"{'charted' if certain else 'uncertain'} · {age}",
                  "dim" if certain else "ash"))
    legs = [route for route in routes_of(b, place)
            if place in {str(route.get("a", "")), str(route.get("b", ""))}]
    open_legs = sum(1 for route in legs
                    if str(route.get("availability", "")).lower() != "closed")
    lines.append((f"{len(legs)} roads, {open_legs} open this season", "dim"))
    return [(text[:room], tone) for text, tone in lines]


# --- the window ---------------------------------------------------------------

def _draw_tabs(surface: Surface, x: int, y: int, room: int,
               layer: str) -> int:
    """The layers, named, with the one you are on marked. Returns rows used.

    Written out rather than hidden behind a key, because a layer the player
    cannot see is a layer he does not know he is missing. They wrap onto a
    second row rather than running off the edge: a tab you cannot see is the
    same as a tab that is not there.
    """
    left, rows = x, 1
    for name in LAYERS:
        label = LAYER_NAME[name]
        here = name == layer
        text = f"[{label}]" if here else f" {label} "
        if left + len(text) > x + room and left > x:
            left, rows = x, rows + 1
            if rows > 2:
                return 2
        surface.text(left, y + rows - 1, text,
                     C["gold"] if here else C["dim"], C["ink"])
        surface.link(left, y + rows - 1, len(text), 1, f"world:layer:{name}")
        left += len(text) + 1
    return rows


def compose(b: dict, width: int = 90, height: int = 30,
            route_scroll: int = 0, selected_place: str = "",
            notice: str = "", wide: int = 3,
            layer: str = "land",
            focus: tuple[int, int] | None = None) -> InteractiveScreen:
    """Compose the tablet: the map on the left, routes and orders on the right."""
    layer = _layer_of(layer)
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
    routes = routes_of(b, selected_place)

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

    map_width = max(1, split - 3)
    tab_rows = _draw_tabs(surface, 2, 3, map_width, layer)
    map_top = 3 + tab_rows
    map_bottom = height - 6
    map_height = max(1, map_bottom - map_top)
    wide = max(1, min(atlas.MAX_WIDE, wide))
    if focus is None:
        focus = focus_of(b, selected_place)
    at, view = _draw_map(surface, b, 2, map_top, map_width, map_height,
                         selected_place, layer, wide, focus)

    offscreen = [place for place in places
                 if str(place.get("id", "")) not in at]
    if offscreen:
        # Not "missing": they are on the map, the window is elsewhere. The
        # count comes first so the number is readable even when the names run
        # off the end of the row.
        missing = ", ".join(
            _spoken(place.get("name") or place.get("id", ""))
            for place in offscreen)
        told = f"{len(offscreen)} elsewhere on the map: {missing}"
        surface.text(2, map_bottom, told[:max(0, map_width)],
                     C["ash"], C["ink"])
        for index, place in enumerate(offscreen[:6]):
            surface.link(2 + index, map_bottom, 1, 1,
                         f"world:place:{place.get('id', '')}")

    legend = LAYER_LEGEND[layer]
    scale = ("cell by cell" if wide == 1 else f"{wide} cells to a mark")
    surface.text(2, map_bottom + 1, legend[:max(0, map_width)],
                 C["faint"], C["ink"])
    # How far back the tablet is held, at the far end of the legend row when
    # the window is wide enough to hold both, and never written over the
    # legend: it is in the footer too, so a narrow window loses nothing.
    if map_width >= len(legend) + len(scale) + 2:
        surface.text(2 + map_width - len(scale), map_bottom + 1, scale,
                     C["dim"], C["ink"])
    sea = ("the sea lanes are open" if b.get("sea_open") is True
           else "the sea is shut; seasonal lanes are closed"
           if b.get("sea_open") is False
           else "seasonal state is not recorded")
    under = (f"~ {sea}" if layer == "trade" else LAYER_UNDER[layer])
    surface.text(2, map_bottom + 2, under[:max(0, map_width)],
                 C["lapis"] if layer == "trade" and b.get("sea_open") is True
                 else C["ash"], C["ink"])

    # The right column holds three blocks in a fixed order of importance: what
    # is selected, the roads from it, and what can be ordered. The orders are
    # pinned to the bottom and never given up -- a window that hides an order
    # because it ran out of rows is the fault this whole layout exists to
    # avoid -- so a short window spends what is left on the description, then
    # on the routes, and drops the route list last of all.
    described = _describe(b, selected_place, right_room)
    orders = orders_for(b, selected_place)
    orders_top = height - 3 - len(orders) + 1
    while len(described) > 2 and (orders_top - 7 - len(described)) // 2 < 1:
        described.pop()
    routes_top = 6 + len(described)
    route_room = max(0, (orders_top - 1 - routes_top) // 2)

    surface.text(right, 4, "THIS PLACE"[:right_room], C["gold"], C["ink"])
    for offset, (text, tone) in enumerate(described):
        if 5 + offset < orders_top - 1:
            surface.text(right, 5 + offset, text, C[tone], C["ink"])

    route_start, route_end = _slice(len(routes), route_scroll, route_room)
    names = {str(place.get("id", "")): _spoken(
        place.get("name") or place.get("id", "")) for place in places}
    if route_room:
        route_range = f"{route_start + 1}-{route_end}" if routes else "0"
        surface.text(right, routes_top - 1,
                     f"ROUTES  {route_range} OF {len(routes)}"[:right_room],
                     C["gold"], C["ink"])
        if routes:
            _route_rows(surface, routes, names, route_start, route_end,
                        selected_place, right, right_room, routes_top)
        else:
            surface.text(right, routes_top,
                         "no routes are entered on this court map."
                         [:right_room], C["ash"], C["ink"])
    else:
        route_start, route_end = 0, 0

    surface.text(right, orders_top - 1, "ORDERS"[:right_room],
                 C["gold"], C["ink"])
    for offset, (key, label, note, enabled, command) in enumerate(orders):
        y = orders_top + offset
        written = style.keycap(surface, right, y, key, label, enabled, command)
        surface.text(right + written + 1, y,
                     note[:max(0, right_room - written - 1)],
                     C["dim"] if enabled else C["ash"], C["ink"])

    style.footer(surface, (
        style.FooterAction("↑↓←→", "pan", bool(view), "world:pan:north"),
        style.FooterAction("]", "next place", bool(places),
                           "world:place:next"),
        style.FooterAction("ctrl-d", "more routes", route_end < len(routes),
                           "world:routes:next"),
        style.FooterAction("tab", "layer", True, "world:layer:next"),
        style.FooterAction("+", "closer", wide > 1, "world:zoom:in"),
        style.FooterAction("-", "wider", wide < atlas.MAX_WIDE,
                           "world:zoom:out"),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 4)
    return surface.interactive()


def compose_with_frieze(b: dict, width: int = 90, height: int = 30,
                        route_scroll: int = 0, selected_place: str = "",
                        wide: int = 3, layer: str = "land",
                        focus: tuple[int, int] | None = None
                        ) -> InteractiveScreen:
    """The same tablet under a seal frieze, retaining every hit region."""
    screen = compose(b, width, height, route_scroll, selected_place,
                     wide=wide, layer=layer, focus=focus)
    surface = Surface(width, height)
    for y, row in enumerate(screen):
        for x, (glyph, fg, bg) in enumerate(row):
            surface.put(x, y, glyph, fg, bg)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    for hit in screen.hits:
        surface.link(
            hit.x, hit.y, hit.width, hit.height, hit.command, hit.enabled)
    return surface.interactive()
