"""M13.0 causal invariants for the inherited city simulation."""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import institution, land, metal
from load import load_scenario

SEED = 8814402919


def _world():
    return load_scenario("ugarit", SEED)


def _with_stores(world, **goods):
    stores = dict(world.court.stores)
    stores.update(goods)
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, stores=stores))


def test_institution_upkeep_is_consumed_once_per_step() -> None:
    world = _with_stores(_world(), oil=100)
    after, _ = institution.step(world)

    # Harbour 6 + temple 10. Previously both merely checked the same oil and
    # neither paid it.
    assert world.court.stores["oil"] == 100
    assert after.court.stores["oil"] == 84


def test_institutions_cannot_promise_the_same_upkeep_twice() -> None:
    world = _with_stores(_world(), oil=10)
    court = world.court
    harbour = court.institutions["harbour_mahadu"]
    temple = court.institutions["temple_baal"]

    after, _ = institution.step(world)

    # Stable institution-id order pays the harbour atomically. Four oil remain;
    # the temple cannot spend the harbour's six a second time or make a partial
    # payment that buys no upkeep.
    assert after.court.stores["oil"] == 4
    assert after.court.institutions[harbour.id].condition == (
        harbour.condition
        - institution._decay_for(court, harbour, upkeep_met=True)
    )
    assert after.court.institutions[temple.id].condition == (
        temple.condition
        - institution._decay_for(court, temple, upkeep_met=False)
    )


def test_missing_head_staff_capacity_or_building_is_never_perfect() -> None:
    world = _world()
    court = world.court
    forge = court.institutions["forge_palace"]

    whole = institution.effective(court, forge)
    headless = institution.effective(
        court, dataclasses.replace(forge, head=""))
    unassigned = institution.effective(
        court, dataclasses.replace(forge, group=""))
    assert 0 < headless < whole
    assert 0 < unassigned < whole

    zero_capacity = dict(court.institutions)
    zero_capacity[forge.id] = dataclasses.replace(forge, capacity=0)
    court_without_capacity = dataclasses.replace(
        court, institutions=zero_capacity)
    assert institution.factor(court_without_capacity, "workshop") == 0

    court_without_buildings = dataclasses.replace(court, institutions={})
    assert institution.factor(court_without_buildings, "workshop") == 0


def test_staff_headcount_changes_output() -> None:
    world = _world()
    court = world.court
    forge = court.institutions["forge_palace"]
    full = institution.effective(court, forge)

    groups = dict(court.dependents)
    smiths = groups["smiths_palace"]
    groups[smiths.id] = dataclasses.replace(smiths, size=smiths.size // 2)
    half_staffed = dataclasses.replace(court, dependents=groups)
    reduced = institution.effective(half_staffed, forge)

    assert 0 < reduced < full
    assert reduced * 2 <= full


def test_harvest_workers_do_not_also_run_the_forge() -> None:
    world = _with_stores(_world(), bronze=0, copper=100_000, tin=100_000)
    court = dataclasses.replace(
        world.court, at_harvest=("smiths_palace",))
    world = dataclasses.replace(world, court=court)
    forge = court.institutions["forge_palace"]

    assert institution.effective(court, forge) == 0
    assert institution.factor(court, "workshop") == 0
    after, events = metal.step(world)
    assert after.court.stores["copper"] == court.stores["copper"]
    assert after.court.stores["tin"] == court.stores["tin"]
    assert not any(isinstance(event, A.BronzeSmelted) for event in events)


def test_a_zero_yield_closes_the_season_exactly_once() -> None:
    world = _world()
    estates = {
        key: dataclasses.replace(
            estate,
            seed_sown=0,
            labour_days_supplied=0,
            climate_sum=400,
            climate_turns=4,
            standing_yield=0,
        )
        for key, estate in world.court.estates.items()
    }
    court = dataclasses.replace(
        world.court,
        estates=estates,
        last_harvest=1234,
        previous_harvest=999,
        at_harvest=("smiths_palace",),
        corvee_days=100,
        works_days=20,
    )
    world = dataclasses.replace(
        world,
        date=dataclasses.replace(world.date, fortnight=12),
        court=court,
    )

    closed, events = land.step(world)
    assert any(isinstance(event, A.Threshed) for event in events)
    assert closed.court.previous_harvest == 1234
    assert closed.court.last_harvest == 0
    assert closed.court.last_land_due == 0
    assert closed.court.at_harvest == ()
    assert closed.court.corvee_days == 0
    assert closed.court.works_days == 0
    for estate in closed.court.estates.values():
        assert estate.seed_sown == 0
        assert estate.labour_days_supplied == 0
        assert estate.climate_sum == 0
        assert estate.climate_turns == 0
        assert estate.standing_yield == 0

    second, second_events = land.step(closed)
    assert not any(isinstance(event, A.Threshed) for event in second_events)
    assert second.court.previous_harvest == 1234
    assert second.court.last_harvest == 0
