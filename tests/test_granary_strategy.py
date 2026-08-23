"""A harder land due buys grain, and storage changes how long it lasts."""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat, systems
from engine.reduce import apply
from engine.state import Institution
from engine.tick import advance
from load import load_campaign


SEED = 8814402919


def _first_harvest(rate: int):
    world = dataclasses.replace(load_campaign("seat", SEED), baseline=True)
    if rate != world.court.land_due_rate:
        world, _ = apply(world, A.SetLandDue(rate))
    for _ in range(13):
        world, _ = advance(world)
    return world


def test_raising_the_land_due_buys_a_real_reserve_at_a_real_cost() -> None:
    customary = _first_harvest(150)
    hard = _first_harvest(250)

    assert hard.court.last_land_due >= customary.court.last_land_due * 3 // 2
    assert seat.held(hard)["grain"] > seat.held(customary)["grain"] + 500_000
    assert hard.court.unrest > customary.court.unrest


def test_a_second_granary_adds_protected_storage() -> None:
    world = load_campaign("seat", SEED)
    before = systems.granary_capacity(world)
    extra = Institution(
        id="granary_second", name="the lower granary", kind="granary",
        place="seat", condition=900, capacity=1000)
    court = dataclasses.replace(
        world.court,
        institutions={**world.court.institutions, extra.id: extra})
    enlarged = dataclasses.replace(world, court=court)

    assert systems.granary_capacity(enlarged) > before
