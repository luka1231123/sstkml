"""M13.0 World view: the UI draws Belief's graph, not a second scenario."""
from __future__ import annotations

import dataclasses

from belief.project import project
from load import load_scenario
from tui.grid import InteractiveScreen, plain_text
from tui import chart, worldmap

SEED = 8814402919


def _place(place_id: str, name: str, age: int = 0,
           certainty: str = "charted", lat: int = 0, lon: int = 0) -> dict:
    return {
        "id": place_id,
        "name": name,
        "lat": lat,
        "lon": lon,
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


def _belief(places: list[dict], routes: list[dict]) -> dict:
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
        _place("ember", "Ember Quay"),
        _place("glass", "Glass Hill"),
        _place("reed", "Reed Ford"),
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
        _place("home", "Home", lat=3500, lon=3500),
        _place("rumour", "Rumoured Haven", 15, "rumoured", 3400, 3600),
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
                     lat=3000 + index * 30, lon=3000 + (index % 7) * 40)
              for index in range(30)]
    routes = [_route(f"p{index:02}", f"p{index + 1:02}")
              for index in range(29)]
    belief = _belief(places, routes)

    first = worldmap.compose(belief, 92, 18)
    last = worldmap.compose(
        belief, 92, 18, route_scroll=999, all_routes=True)

    assert isinstance(first, InteractiveScreen)
    assert "Place 28 > Place 29" in plain_text(last)
    assert "Place 28 > Place 29" not in plain_text(first)

    # A name that will not fit on the chart is dropped; the place never is.
    commands = {hit.command for hit in first.hits if hit.enabled}
    for place in places:
        assert f"world:place:{place['id']}" in commands, place["id"]
    assert "world:routes:scope" in commands


def test_the_route_tablet_opens_locally_and_keeps_the_whole_graph_one_key_away():
    places = [
        _place("home", "Home", lat=3500, lon=3500),
        _place("near", "Near", lat=3600, lon=3600),
        _place("far", "Far", lat=3700, lon=3700),
        _place("beyond", "Beyond", lat=3800, lon=3800),
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


def test_the_chart_marks_and_names_places_where_the_tablet_locates_them() -> None:
    places = [
        _place("home", "Home", lat=3500, lon=3500),
        _place("north", "North Quay", lat=3900, lon=3500),
        _place("east", "East Ford", lat=3500, lon=4000),
    ]
    screen = worldmap.compose(
        _belief(places, [_route("home", "north"), _route("home", "east")]),
        100, 28)
    text = plain_text(screen)
    commands = {hit.command for hit in screen.hits if hit.enabled}

    for place in places:
        assert f"world:place:{place['id']}" in commands, place["id"]
    assert "North Quay" in text and "East Ford" in text
    assert worldmap.SEAT_MARK in text

    # North is up and east is right: it is a map, not a list in a box.
    at = chart.project(places, 40, 12)
    assert at["north"][1] < at["home"][1]
    assert at["east"][0] > at["home"][0]
    assert "world:route:home:north" in commands


def test_the_crowded_chart_keeps_place_marks_visually_separate() -> None:
    places = [
        _place(f"port-{index}", f"Port {index}",
               lat=3500 + index, lon=3500 + index)
        for index in range(8)
    ]
    at = chart.project(places, 32, 12, spacing=1)

    for place, cell in at.items():
        assert all(
            max(abs(cell[0] - other[0]), abs(cell[1] - other[1])) > 1
            for other_place, other in at.items()
            if other_place != place
        )


def test_a_place_the_tablet_cannot_locate_is_named_rather_than_dropped() -> None:
    """A scenario that authors no coordinates loses no place."""
    places = [_place("home", "Home", lat=3500, lon=3500),
              _place("nowhere", "Nowhere")]
    del places[1]["lat"]
    del places[1]["lon"]
    screen = worldmap.compose(_belief(places, []), 100, 28)

    assert "not located on this tablet" in plain_text(screen)
    assert "Nowhere" in plain_text(screen)
    assert "world:place:nowhere" in {
        hit.command for hit in screen.hits if hit.enabled}


def test_world_communication_is_an_honest_inert_placeholder() -> None:
    places = [_place("home", "Home", lat=3500, lon=3500),
              _place("emar", "Emar", lat=3600, lon=3800)]
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


def test_selection_does_not_rearrange_the_map_ink_or_labels() -> None:
    places = [
        _place("home", "Home", lat=3500, lon=3500),
        _place("near", "Near", lat=3600, lon=3600),
        _place("far", "Far", lat=3700, lon=3500),
    ]
    belief = _belief(
        places, [_route("home", "near"), _route("near", "far", "river")])

    def chart_text(selected: str) -> str:
        surface = worldmap.Surface(40, 14)
        at = worldmap._draw_chart(
            surface, belief, 0, 0, 40, 14, selected)
        rows = [list(row) for row in plain_text(surface.freeze()).splitlines()]
        for x, y in at.values():
            rows[y][x] = " "
        return "\n".join("".join(row) for row in rows)

    assert chart_text("home") == chart_text("far")


def test_frieze_variant_keeps_the_graph_hit_regions() -> None:
    belief = _belief(
        [_place("home", "Home"), _place("away", "Away")],
        [_route("home", "away")],
    )
    screen = worldmap.compose_with_frieze(belief)
    commands = {hit.command for hit in screen.hits if hit.enabled}
    assert "world:place:home" in commands
    assert "world:route:home:away" in commands


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
    return game


def test_the_arrows_walk_every_place_on_the_chart() -> None:
    """The map, the tablet and the keyboard share one order and one selection."""
    game = _game()
    everywhere = [str(place["id"])
                  for place in worldmap.places_in_order(game.belief)]
    seen = {game.world_place_pick}
    for _ in range(len(everywhere) + 2):
        game.on_world_key(_Key(keysym="Down"))
        seen.add(game.world_place_pick)
    assert seen == set(everywhere)


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
    game.on_world_key(_Key(command="world:place:seat"))
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
