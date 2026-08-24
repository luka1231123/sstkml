"""A lost gate creates ration pressure instead of deleting the decision."""

import dataclasses

from engine import actions as A
from engine import defence, seat
from engine.kernel import seat_people as SP
from engine.reduce import apply
from load import load_campaign


SEED = 8814402919
FIELD_FIRST = (
    "field_hands", "palace_dependents", "household", "garrison_mahadu",
    "cult_baal", "smiths_palace", "weavers",
)
PALACE_FIRST = (
    "palace_dependents", "field_hands", "household", "garrison_mahadu",
    "cult_baal", "smiths_palace", "weavers",
)


def _attacker(world, cohort_id: str):
    cohorts = dict(world.kernel.registry.cohorts)
    cohort = cohorts[cohort_id]
    cohorts[cohort_id] = dataclasses.replace(
        cohort, people=10_000, households=min(cohort.households, 10_000),
        status="attacker", armed=True)
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))


def test_a_sack_leaves_a_short_store_for_the_ration_queue():
    world = load_campaign("seat", SEED)
    stores = seat.held(world)
    stores["grain"] = 960_000
    world = seat.put(world, stores)

    after, events = defence._sacked(
        world, SP.SEAT, attack=2_000, defence=1_000,
        stores=seat.held(world))

    assert seat.held(after)["grain"] == 288_000
    assert events == [A.SeatTaken(2_000, 1_000, 672_000, 500)]


def test_consecutive_raids_leave_a_pool_whose_order_changes_who_eats():
    world = load_campaign("seat", SEED)
    stores = seat.held(world)
    stores["grain"] = 960_000
    world = seat.put(world, stores)

    world, first = defence.step(_attacker(world, "cohort:seat_craft"))
    world, second = defence.step(
        _attacker(world, "cohort:seat_field_labour"))

    assert isinstance(first[0], A.SeatTaken)
    assert isinstance(second[0], A.SeatTaken)
    assert 4_000 <= seat.held(world)["grain"] < 96_000

    field_first, _ = apply(world, A.SetPriority(FIELD_FIRST))
    palace_first, _ = apply(world, A.SetPriority(PALACE_FIRST))
    field_first = seat.feed(field_first)
    palace_first = seat.feed(palace_first)
    field_roll = seat.groups(field_first)
    palace_roll = seat.groups(palace_first)

    assert field_roll["field_hands"].arrears == 0
    assert palace_roll["field_hands"].arrears > 0
    assert palace_roll["palace_dependents"].arrears < \
        field_roll["palace_dependents"].arrears
