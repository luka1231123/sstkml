"""M13.0 World view: the UI draws Belief's graph, not a second scenario."""
from __future__ import annotations

import dataclasses

from belief.project import project
from load import load_scenario
from tui.grid import InteractiveScreen, plain_text
from tui import worldmap

SEED = 8814402919


def _place(place_id: str, name: str, age: int = 0,
           certainty: str = "charted") -> dict:
    return {
        "id": place_id,
        "name": name,
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
    text = plain_text(worldmap.compose(belief, 100, 26))

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
        _place("home", "Home"),
        _place("rumour", "Rumoured Haven", 15, "rumoured"),
    ]
    route = _route(
        "home", "rumour", "sea", 15, "uncertain", "unknown")
    unknown = {"a": "rumour", "b": "beyond", "mode": "unknown"}
    text = plain_text(
        worldmap.compose(_belief(places, [route, unknown]), 116, 26))

    assert "uncertain" in text
    assert "stale 15f" in text
    assert "unknown" in text
    assert "undated" in text
    assert "beyond" in text


def test_both_collections_scroll_and_publish_navigation_hits() -> None:
    places = [_place(f"p{index:02}", f"Place {index:02}")
              for index in range(30)]
    routes = [_route(f"p{index:02}", f"p{index + 1:02}")
              for index in range(29)]
    belief = _belief(places, routes)

    first = worldmap.compose(belief, 92, 18)
    last = worldmap.compose(
        belief, 92, 18, place_scroll=999, route_scroll=999)
    first_text = plain_text(first)
    last_text = plain_text(last)

    assert isinstance(first, InteractiveScreen)
    assert "Place 29" not in first_text
    assert "Place 29" in last_text
    assert "Place 28 > Place 29" in last_text

    first_commands = {hit.command for hit in first.hits if hit.enabled}
    last_commands = {hit.command for hit in last.hits if hit.enabled}
    assert "world:places:next" in first_commands
    assert "world:routes:next" in first_commands
    assert "world:places:previous" in last_commands
    assert "world:routes:previous" in last_commands


def test_frieze_variant_keeps_the_graph_hit_regions() -> None:
    belief = _belief(
        [_place("home", "Home"), _place("away", "Away")],
        [_route("home", "away")],
    )
    screen = worldmap.compose_with_frieze(belief)
    commands = {hit.command for hit in screen.hits if hit.enabled}
    assert "world:place:home" in commands
    assert "world:route:home:away" in commands
