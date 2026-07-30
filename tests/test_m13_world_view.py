"""M13.0 World view: the UI draws Belief's graph, not a second scenario."""
from __future__ import annotations

import dataclasses

from belief.project import project
from load import load_scenario
from tui.grid import InteractiveScreen, plain_text
from tui import atlas, worldmap

SEED = 8814402919

# A little world to draw on: sea on the left, a river down the middle, hills on
# the right. Twelve columns by six rows, which is smaller than any window --
# the map is allowed to be smaller than the screen, and is centred when it is.
GROUND = [
    "~~~~,,.,,^^^",
    "~~~,,,≈,,^^^",
    "~~~,,,≈,,,^^",
    "~~,,,,≈,,,^^",
    "~~,,:,≈,,,,^",
    "~~,,::≈,,,,,",
]


def _place(place_id: str, name: str, age: int = 0,
           certainty: str = "charted", col: int = 0, row: int = 0,
           power: str = "hatti", rank: str = "town", glyph: str = "",
           role: str = "") -> dict:
    return {
        "id": place_id,
        "name": name,
        "col": col,
        "row": row,
        "power": power,
        "rank": rank,
        "glyph": glyph,
        "role": role,
        "source": "test tablet",
        "as_of_turn": 0,
        "age_turns": age,
        "certainty": certainty,
    }


def _route(a: str, b: str, mode: str = "land", age: int = 0,
           certainty: str = "charted", availability: str = "open") -> dict:
    return {
        "a": a,
        "b": b,
        "mode": mode,
        "seasonal": mode == "sea",
        "legs": 2,
        "source": "test tablet",
        "as_of_turn": 0,
        "age_turns": age,
        "certainty": certainty,
        "availability": availability,
        "availability_source": "test calendar",
        "availability_as_of_turn": 0,
    }


def _site(kind: str, alu: str, col: int, row: int) -> dict:
    role = "palace_centre" if kind == "palace" else "capacity"
    capacity = "" if kind == "palace" else ("food" if kind == "grain" else kind)
    return {"kind": kind, "alu": alu, "role": role, "capacity": capacity,
            "col": col, "row": row}


def _belief(places: list[dict], routes: list[dict],
            ground: list[str] | None = None,
            sites: list[dict] | None = None) -> dict:
    return {
        "seat": places[0]["id"] if places else "",
        "sea_open": True,
        "relations": [],
        "world_graph": {
            "source": "test tablet",
            "as_of_turn": 0,
            "age_turns": 0,
            "places": places,
            "routes": routes,
            "sites": sites or [],
            "terrain": {
                "rows": GROUND if ground is None else ground,
                "west": 0, "north": 0, "step_lon": 10, "step_lat": 10,
                "legend": "",
            },
        },
    }


def test_projection_exposes_only_court_map_geography() -> None:
    world = load_scenario("ugarit", SEED)
    graph = project(world)["world_graph"]

    assert {place["id"] for place in graph["places"]} == set(world.places)
    assert {place["name"] for place in graph["places"]} == {
        place.name for place in world.places.values()}
    assert len(graph["routes"]) == len(world.routes)
    assert {
        endpoint
        for route in graph["routes"]
        for endpoint in (route["a"], route["b"])
    }.issubset({place["id"] for place in graph["places"]})
    assert all(place["source"] == "court map" for place in graph["places"])
    assert all(route["source"] == "court map" for route in graph["routes"])

    forbidden = {
        "population", "susceptible", "infected", "recovered", "dead", "risk",
    }
    for place in graph["places"]:
        assert forbidden.isdisjoint(place)
    for route in graph["routes"]:
        assert forbidden.isdisjoint(route)

    for route in graph["routes"]:
        expected = (
            "closed"
            if route["seasonal"] and not project(world)["sea_open"]
            else "open")
        assert route["availability"] == expected
        assert route["availability_as_of_turn"] == world.date.absolute


def test_projected_map_age_advances_but_calendar_state_is_current() -> None:
    world = load_scenario("ugarit", SEED)
    world = dataclasses.replace(
        world, date=dataclasses.replace(
            world.date, fortnight=5, absolute=5))
    graph = project(world)["world_graph"]

    assert graph["age_turns"] == 5
    assert {place["age_turns"] for place in graph["places"]} == {5}
    assert {route["age_turns"] for route in graph["routes"]} == {5}
    assert {
        route["availability_as_of_turn"] for route in graph["routes"]} == {5}


def test_arbitrary_nodes_and_routes_appear_and_old_named_places_do_not() -> None:
    places = [
        _place("ember", "Ember Quay", col=1, row=1),
        _place("glass", "Glass Hill", col=6, row=2),
        _place("reed", "Reed Ford", col=9, row=4),
    ]
    routes = [
        _route("ember", "glass", "land"),
        _route("glass", "reed", "river"),
    ]
    belief = _belief(places, routes)
    belief["relations"] = [{
        "place": "hattusa",
        "esteem": "warm",
        "unanswered": 7,
    }]
    text = plain_text(
        worldmap.compose(belief, 100, 26, all_routes=True))

    assert "Ember Quay" in text
    assert "Glass Hill" in text
    assert "Reed Ford" in text
    assert "land" in text and "river" in text
    assert "Ember Quay > Glass Hill" in text
    assert "Glass Hill > Reed Ford" in text
    assert "Hattusa" not in text
    assert "Alashiya" not in text


def test_uncertainty_staleness_and_missing_knowledge_are_written_out() -> None:
    places = [
        _place("home", "Home", col=2, row=2),
        _place("rumour", "Rumoured Haven", 15, "rumoured", col=8, row=1),
    ]
    route = _route(
        "home", "rumour", "sea", 15, "uncertain", "unknown")
    unknown = {"a": "rumour", "b": "beyond", "mode": "unknown"}
    text = plain_text(
        worldmap.compose(_belief(places, [route, unknown]), 116, 26,
                         selected_place="rumour"))

    assert "uncertain" in text
    assert "stale 15f" in text
    assert "unknown" in text
    assert "undated" in text
    assert "beyond" in text


def test_the_route_tablet_scrolls_and_every_place_stays_clickable() -> None:
    places = [_place(f"p{index:02}", f"Place {index:02}",
                     col=index % 12, row=index % 6)
              for index in range(30)]
    routes = [_route(f"p{index:02}", f"p{index + 1:02}")
              for index in range(29)]
    belief = _belief(places, routes)

    first = worldmap.compose(belief, 92, 18, all_routes=True)
    last = worldmap.compose(
        belief, 92, 18, route_scroll=999, all_routes=True)

    assert isinstance(first, InteractiveScreen)
    assert "Place 28 > Place 29" in plain_text(last)
    assert "Place 28 > Place 29" not in plain_text(first)
    assert "world:routes:next" in {
        hit.command for hit in first.hits if hit.enabled}

    # Thirty places will not fit on twelve columns of ground. Whoever is
    # crowded out is named under the map rather than silently dropped.
    commands = {hit.command for hit in first.hits if hit.enabled}
    assert "elsewhere on the map" in plain_text(first)
    assert "world:routes:scope" in commands


def test_the_route_tablet_opens_locally_and_keeps_the_whole_graph_one_key_away():
    places = [
        _place("home", "Home", col=1, row=1),
        _place("near", "Near", col=3, row=2),
        _place("far", "Far", col=6, row=3),
        _place("beyond", "Beyond", col=9, row=4),
    ]
    belief = _belief(
        places,
        [_route("home", "near"), _route("near", "far"),
         _route("far", "beyond")],
    )

    local = worldmap.compose(belief, 104, 30, selected_place="home")
    complete = worldmap.compose(
        belief, 104, 30, selected_place="home", all_routes=True)

    assert "ROADS HERE" in plain_text(local)
    assert "Home > Near" in plain_text(local)
    assert "Far > Beyond" not in plain_text(local)
    assert "ALL ROADS" in plain_text(complete)
    assert "Far > Beyond" in plain_text(complete)
    assert "world:routes:scope" in {
        hit.command for hit in local.hits if hit.enabled}


def test_the_map_marks_and_names_places_where_the_tablet_locates_them() -> None:
    places = [
        _place("home", "Home", col=4, row=3, rank="royal", glyph="H"),
        _place("north", "North Quay", col=4, row=0, glyph="N"),
        _place("east", "East Ford", col=9, row=3, glyph="E"),
    ]
    screen = worldmap.compose(
        _belief(places, [_route("home", "north"), _route("home", "east")]),
        100, 28)
    text = plain_text(screen)
    commands = {hit.command for hit in screen.hits if hit.enabled}

    for place in places:
        assert f"world:place:{place['id']}" in commands, place["id"]
    assert "North Quay" in text and "East Ford" in text
    assert "{H}" in text, "the seat is not drawn as the seat"

    # North is up and east is right: it is a map, not a list in a box.
    view = atlas.frame_for(GROUND, 40, 12)
    assert view.cell(4, 0)[1] < view.cell(4, 3)[1]
    assert view.cell(9, 3)[0] > view.cell(4, 3)[0]
    assert "world:route:home:north" in commands


def test_a_place_the_tablet_cannot_locate_is_named_rather_than_dropped() -> None:
    """A scenario that authors no coordinates loses no place."""
    places = [_place("home", "Home", col=3, row=3),
              _place("nowhere", "Nowhere")]
    del places[1]["col"]
    del places[1]["row"]
    screen = worldmap.compose(_belief(places, []), 100, 28)

    assert "elsewhere on the map" in plain_text(screen)
    assert "Nowhere" in plain_text(screen)
    assert "world:place:nowhere" in {
        hit.command for hit in screen.hits if hit.enabled}


def test_world_communication_is_an_honest_inert_placeholder() -> None:
    places = [_place("home", "Home", col=3, row=3),
              _place("emar", "Emar", col=8, row=1)]
    belief = _belief(places, [_route("home", "emar")])
    screen = worldmap.compose(belief, 104, 30, selected_place="emar")
    text = plain_text(screen)

    assert "CORRESPONDENCE" in text
    assert "Letter" in text and "Envoy" in text and "Gift" in text
    assert "Marriage" in text and "by letter" in text
    assert "not yet wired" in text
    assert not {
        hit.command for hit in screen.hits
        if hit.command.startswith(("do:", "world:open:"))
    }


def test_frieze_variant_keeps_the_graph_hit_regions() -> None:
    belief = _belief(
        [_place("home", "Home", col=2, row=2),
         _place("away", "Away", col=9, row=4)],
        [_route("home", "away")],
    )
    screen = worldmap.compose_with_frieze(belief)
    commands = {hit.command for hit in screen.hits if hit.enabled}
    assert "world:place:home" in commands
    assert "world:route:home:away" in commands


# --- the ground ---------------------------------------------------------------

def test_the_ground_is_drawn_from_the_scenario_and_from_nowhere_else() -> None:
    """The sea and the hills are authored content, like the place names."""
    places = [_place("home", "Home", col=6, row=2)]
    drawn = plain_text(worldmap.compose(_belief(places, []), 100, 28))
    bare = plain_text(
        worldmap.compose(_belief(places, [], ground=[]), 100, 28))
    assert drawn != bare, "the authored ground changed nothing on the tablet"
    assert "this tablet has no ground drawn on it." in bare

    # And it is scenery: nothing on it can be clicked, so it steals no click
    # from the routes and the marks that can be.
    commands = {hit.command for hit in
                worldmap.compose(_belief(places, []), 100, 28).hits}
    assert not any(command.startswith("world:ground") for command in commands)


def test_the_scenario_authors_ground_that_reaches_the_tablet() -> None:
    world = load_scenario("ugarit", seed=SEED)
    assert world.terrain.rows, "the scenario authors no ground"
    assert world.sites, "the scenario authors no hinterland"
    graph = project(world)["world_graph"]
    assert graph["terrain"]["rows"], "Belief drops the authored ground"

    wide = len(graph["terrain"]["rows"][0])
    for row in graph["terrain"]["rows"]:
        assert len(row) == wide, "the ground is not a rectangle"
    for place in graph["places"]:
        assert 0 <= place["col"] < wide
        assert 0 <= place["row"] < len(graph["terrain"]["rows"])


def test_a_place_and_the_ground_under_it_are_drawn_by_the_same_window() -> None:
    """A port cannot drift off its own shore, whatever the window's shape."""
    for width, height in ((40, 12), (80, 40), (52, 15)):
        view = atlas.frame_for(GROUND, width, height)
        for col, row in ((0, 0), (6, 2), (11, 5)):
            spot = view.cell(col, row)
            assert view.at(spot) == (col, row)


def test_holding_the_tablet_back_shows_more_ground_in_fewer_cells() -> None:
    """The wider setting samples the ground; it never drops the land."""
    rows = ["~~~~", "~,~~", "~~~~", "~~~~"]
    close = atlas.frame_for(rows, 4, 4, wide=1)
    back = atlas.frame_for(rows, 2, 2, wide=2)
    assert atlas.sample(rows, 0, 0, 1) == "~"
    # The island is one cell in four and survives being stood back from: a
    # coastline that thins out as you pull back lies about where the land is.
    assert atlas.sample(rows, 0, 0, 2) == ","
    assert close.wide == 1 and back.wide == 2


def test_the_window_pans_over_a_map_bigger_than_itself() -> None:
    ground = ["".join("," if col % 7 else "~" for col in range(200))
              for _row in range(60)]
    places = [_place("home", "Home", col=5, row=5, glyph="H"),
              _place("far", "Far Away", col=180, row=50, glyph="F")]
    belief = _belief(places, [], ground=ground)

    near = plain_text(worldmap.compose(belief, 104, 30, wide=1,
                                       selected_place="home"))
    away = plain_text(worldmap.compose(belief, 104, 30, wide=1,
                                       selected_place="home",
                                       focus=(180, 50)))
    # Each window holds one of them and says the other is elsewhere. What is
    # off the window is named under it, never dropped.
    assert "1 elsewhere on the map: Far Away" in near
    assert "1 elsewhere on the map: Home" in away


# --- the layers ---------------------------------------------------------------

def test_the_tablet_has_a_tab_for_each_layer_and_says_which_one_you_are_on() -> None:
    places = [_place("home", "Home", col=2, row=2),
              _place("away", "Away", col=8, row=4)]
    screen = worldmap.compose(_belief(places, [_route("home", "away")]),
                              104, 30)
    text = plain_text(screen)
    commands = {hit.command for hit in screen.hits if hit.enabled}

    for layer in worldmap.LAYERS:
        assert worldmap.LAYER_NAME[layer] in text
        assert f"world:layer:{layer}" in commands
    assert "[LAND]" in text, "the tablet does not say which layer it is showing"


def test_each_layer_draws_its_own_question_and_leaves_the_others_alone() -> None:
    """One mark per place on the general map; everything else is a layer."""
    places = [_place("home", "Home", col=1, row=1, glyph="H"),
              _place("court", "Court Town", col=8, row=1, glyph="C"),
              _place("sick", "Sick Port", col=8, row=5, glyph="S")]
    sites = [_site("palace", "home", 3, 3), _site("grain", "home", 4, 4),
             _site("copper", "court", 9, 2)]
    belief = _belief(places, [_route("home", "court", "land"),
                              _route("home", "sick", "sea")], sites=sites)
    belief["relations"] = [{"place": "court", "esteem": "warm",
                            "unanswered": 2}]
    belief["plague"] = {"quarantined": ["sick"]}

    drawn = {layer: plain_text(
                 worldmap.compose(belief, 104, 30, layer=layer, wide=1))
             for layer in worldmap.LAYERS}

    # The general map knows what a place IS, and no more: no esteem diamond
    # and no struck-out road on it.
    assert worldmap.COURT_MARK not in drawn["land"]
    assert worldmap.SHUT_MARK not in drawn["land"]
    assert "{H}" in drawn["land"]

    assert worldmap.COURT_MARK in drawn["courts"]
    assert worldmap.SHUT_MARK not in drawn["courts"]
    assert worldmap.SHUT_MARK in drawn["sickness"]
    assert worldmap.COURT_MARK not in drawn["sickness"]

    # The hinterland belongs to the layer that asks about it and to no other.
    def holdings(layer: str, kind: str) -> int:
        # Counted rather than looked for: the footer under the map has a `x`
        # in it, and a test that cannot tell a keycap from a small palace is
        # a test that passes when the layer is empty.
        return drawn[layer].count(atlas.SITE_GLYPH[kind])

    assert holdings("holds", "palace") > holdings("land", "palace")
    assert holdings("farms", "grain") > 0
    assert holdings("holds", "grain") == 0
    assert holdings("trade", "copper") > 0

    # Roads are drawn on the roads layer, sea lanes on trade, and neither
    # anywhere else. The route tablet beside the map stays clickable on every
    # layer, so what is counted here is the single cells laid along a road.
    def road_cells(layer: str) -> int:
        screen = worldmap.compose(belief, 104, 30, layer=layer, wide=1)
        return sum(1 for hit in screen.hits
                   if hit.command.startswith("world:route:")
                   and (hit.width, hit.height) == (1, 1))

    assert road_cells("roads") > 0
    assert road_cells("trade") > 0
    assert road_cells("land") == 0
    assert road_cells("courts") == 0 and road_cells("sickness") == 0
    assert "─" in drawn["roads"]


def test_the_hinterland_is_counted_beside_the_map_and_never_named() -> None:
    places = [_place("home", "Home", col=1, row=1)]
    sites = [_site("palace", "home", 3, 3), _site("palace", "home", 4, 2),
             _site("grain", "home", 5, 4), _site("copper", "home", 9, 1)]
    text = plain_text(
        worldmap.compose(_belief(places, [], sites=sites), 104, 30))
    assert "2 palace centres" in text
    assert "copper" in text


def test_two_places_in_one_cell_are_both_drawn() -> None:
    """A mark drawn over a mark is a place that has silently vanished."""
    places = [_place("home", "Home", col=5, row=2, glyph="H"),
              _place("twin", "Twin", col=5, row=2, glyph="T")]
    screen = worldmap.compose(_belief(places, []), 104, 30)
    text = plain_text(screen)
    assert "{H}" in text and "T" in text
    assert "elsewhere on the map" not in text


def test_an_unknown_layer_falls_back_to_the_ground() -> None:
    places = [_place("home", "Home", col=3, row=3)]
    text = plain_text(
        worldmap.compose(_belief(places, []), 104, 30, layer="nonsense"))
    assert "[LAND]" in text


# --- the controller -----------------------------------------------------------

class _Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "", state: int = 0) -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = state


def _game():
    import play_gui
    from engine.tick import advance

    world = load_scenario("ugarit", SEED)
    for _ in range(6):
        world, _ = advance(world)
    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = world
    game.hours = project(world)["attention"]
    game.log = []
    game.client = None
    game.repaint = lambda: None
    game.world_place_pick = world.court.seat
    game.world_route_scroll = 0
    game.world_layer = worldmap.LAYERS[0]
    game.world_wide = 3
    game.world_focus = None
    return game


def test_the_brackets_walk_every_place_on_the_map() -> None:
    """The map, the tablet and the keyboard share one order and one selection."""
    game = _game()
    everywhere = [str(place["id"])
                  for place in worldmap.places_in_order(game.belief)]
    seen = {game.world_place_pick}
    for _ in range(len(everywhere) + 2):
        game.on_world_key(_Key(char="]"))
        seen.add(game.world_place_pick)
    assert seen == set(everywhere)


def test_the_arrows_move_the_window_and_choosing_a_place_gives_it_back() -> None:
    game = _game()
    assert game.world_focus is None
    game.on_world_key(_Key(keysym="Right"))
    moved = game.world_focus
    assert moved is not None
    game.on_world_key(_Key(keysym="Down"))
    assert game.world_focus[1] > moved[1]
    assert game.world_focus[0] == moved[0]

    # Choosing a place is going somewhere; the window follows it again.
    game.on_world_key(_Key(command="world:place:hattusa"))
    assert game.world_focus is None


def test_arrows_do_not_bank_invisible_steps_at_the_map_edge() -> None:
    game = _game()
    for _ in range(100):
        game.on_world_key(_Key(keysym="Left"))
    edge = game.world_focus

    game.on_world_key(_Key(keysym="Left"))
    assert game.world_focus == edge

    game.on_world_key(_Key(keysym="Right"))
    assert game.world_focus is not None
    assert game.world_focus[0] > edge[0]


def test_holding_the_tablet_closer_and_wider() -> None:
    game = _game()
    game.on_world_key(_Key(char="+"))
    assert game.world_wide == 2
    for _ in range(9):
        game.on_world_key(_Key(char="-"))
    assert game.world_wide == atlas.MAX_WIDE


def test_clicking_a_mark_or_a_road_selects_a_place() -> None:
    game = _game()
    game.on_world_key(_Key(command="world:place:hattusa"))
    assert game.world_place_pick == "hattusa"

    # Clicking a road selects the far end of it, whichever way it is written.
    game.on_world_key(_Key(command="world:route:hattusa:carchemish"))
    assert game.world_place_pick == "carchemish"
    game.on_world_key(_Key(command="world:route:hattusa:carchemish"))
    assert game.world_place_pick == "hattusa"

    # An onward leg chooses its farther endpoint rather than its authored
    # first endpoint.
    game.on_world_key(
        _Key(command=f"world:place:{game.belief['seat']}"))
    game.on_world_key(_Key(command="world:route:ma_hadu:alashiya"))
    assert game.world_place_pick == "alashiya"


def test_the_route_tablet_turns_between_local_and_complete_views() -> None:
    game = _game()
    assert not getattr(game, "world_all_routes", False)

    game.on_world_key(_Key(char="a"))
    assert game.world_all_routes

    # Choosing a place returns to the useful local leaf.
    game.on_world_key(_Key(command="world:place:hattusa"))
    assert not game.world_all_routes


def test_world_placeholders_do_not_issue_hidden_hotkey_orders() -> None:
    game = _game()
    game.on_world_key(_Key(command="world:place:ma_hadu"))
    game.on_world_key(_Key(char="q"))
    game.on_world_key(_Key(char="m"))
    assert game.log == []
