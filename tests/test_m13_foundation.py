"""M13.0 causal invariants for the inherited city simulation."""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import institution, metal, seat
from load import load_scenario

SEED = 8814402919


def _world():
    return load_scenario("ugarit", SEED)


def _with_stores(world, **goods):
    """Set the seat's stores through the seam, not on the court.

    `Court.stores` is a mirror since Task 2 C2 -- the systems read the Book --
    so a fixture that writes only the court sets a figure nothing consults.
    """
    stores = seat.held(world)
    stores.update(goods)
    return seat.put(world, stores)


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
    world = seat.to_fields(world, "smiths_palace", True)
    court = world.court
    forge = court.institutions["forge_palace"]

    assert institution.effective(court, forge) == 0
    assert institution.factor(court, "workshop") == 0
    after, events = metal.step(world)
    assert after.court.stores["copper"] == court.stores["copper"]
    assert after.court.stores["tin"] == court.stores["tin"]
    assert not any(isinstance(event, A.BronzeSmelted) for event in events)
