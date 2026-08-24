from __future__ import annotations

import dataclasses

from belief.project import project
from engine import actions as A
from engine import institution, seat, systems, troops, works
from engine.core import Date
from engine.kernel import carry, farm
from engine.tick import advance
from load import load_campaign
from tui import render
from tui import works as works_page
from tui.grid import plain_text


SEED = 8814402919


def _finish(world, kind: str):
    world, _ = works.begin_build(world, A.BeginBuild(kind, "seat"))
    work = world.court.projects[f"work{world.court.project_seq}"]
    return works._finish(world, work)[0]


def test_works_names_the_return_wager_and_whole_supply() -> None:
    belief = project(load_campaign("seat", SEED))
    text = plain_text(works_page.compose(
        belief, width=82, height=32, selected_plan="walls"))

    assert "FORTIFICATION" in text
    assert "RETURN" in text and "WAGER" in text
    assert "2,000 copper, 20,000 grain" in text
    assert "36,000 copper" in text
    assert "PRECEDENT" not in text


def test_active_work_does_not_hide_a_plan_upkeep_or_supply() -> None:
    world = load_campaign("seat", SEED)
    world, _ = works.begin_build(world, A.BeginBuild("walls", "seat"))
    text = plain_text(works_page.compose(
        project(world), width=82, height=32, selected_plan="temple"))

    assert "UPKEEP · 10 oil each fortnight" in text
    assert "SUPPLY · 360 copper, 15,000 grain" in text
    assert "IN STORE · 36,000 copper" in text


def test_each_kind_draws_its_own_supplies() -> None:
    plans = {plan["kind"]: plan for plan in project(
        load_campaign("seat", SEED))["plans"]}

    assert plans["archive"]["materials"]["copper"] == 42
    assert plans["walls"]["materials"]["copper"] == 2000
    assert plans["workshop"]["materials"]["copper"] == 600
    assert all(plan["effect"] and plan["tradeoff"]
               for plan in plans.values())


def test_wall_progress_spends_its_fittings_as_well_as_crew_grain() -> None:
    world = load_campaign("seat", SEED)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(
            world.kernel, date=Date(world.date.year, 14, world.date.absolute)))
    days, sources, _incremental = seat.source_corvee(world, 400)
    assert days == 400
    world = seat.levy(world, sources)
    world, _ = works.begin_build(world, A.BeginBuild("walls", "seat"))
    before = seat.held(world)

    world, _ = works.step(world)
    after = seat.held(world)
    wall = world.court.projects["work1"]

    assert wall.days_done == 400
    assert before["grain"] - after["grain"] == 2000
    assert before["copper"] - after["copper"] == 200


def test_corvee_is_shown_as_low_water_capacity_not_a_hidden_field_penalty() -> None:
    world = load_campaign("seat", SEED)
    _days, sources, _incremental = seat.source_corvee(world, 4000)
    world = seat.levy(world, sources)
    belief = project(world)
    land = belief["land"]

    assert land["corvee_days"] == 4000
    assert land["labour_days_committed"] == 0
    assert land["labour_days_idle"] == max(
        0, land["labour_days_this_turn"] - land["labour_days_needed"])
    text = render.land_screen(belief)
    assert "corvée holds" not in text
    assert "works use those days only at low water" in text


def test_finished_works_feed_the_land_routes_and_existing_city_systems() -> None:
    opening = load_campaign("seat", SEED)
    archive_before = institution.factor(opening, "archive")
    workshop_before = institution.factor(opening, "workshop")
    temple_before = institution.factor(opening, "temple")
    defence_before = troops.garrison_strength(opening, "seat")
    roof_before = systems.granary_capacity(opening)

    built = opening
    for kind in ("archive", "canal", "garrison", "granary", "harbour",
                 "road", "temple", "walls", "workshop"):
        built = _finish(built, kind)

    assert institution.factor(built, "archive") > archive_before
    assert institution.factor(built, "workshop") > workshop_before
    assert institution.factor(built, "temple") > temple_before
    assert troops.garrison_strength(built, "seat") > defence_before
    assert systems.granary_capacity(built) > roof_before

    baseline, _ = advance(opening)
    improved, _ = advance(built)
    seat = "settlement:seat"
    field = improved.kernel.field_site(
        seat, improved.kernel.controller(seat))
    assert farm.extent(improved.kernel, field) > farm.extent(
        baseline.kernel, field)

    land_route = next(
        route_id for route_id, route in improved.kernel.registry.routes.items()
        if route.legs and route.legs[0].mode == "land"
        and seat in {carry.settlement_of(improved.kernel, route.origin),
                     carry.settlement_of(improved.kernel, route.destination)})
    sea_route = next(
        route_id for route_id, route in improved.kernel.registry.routes.items()
        if route.legs and route.legs[0].mode == "sea"
        and seat in {carry.settlement_of(improved.kernel, route.origin),
                     carry.settlement_of(improved.kernel, route.destination)})
    assert carry.route_capacity(improved.kernel, land_route) > \
        carry.route_capacity(baseline.kernel, land_route)
    assert carry.route_capacity(improved.kernel, sea_route) > \
        carry.route_capacity(baseline.kernel, sea_route)
