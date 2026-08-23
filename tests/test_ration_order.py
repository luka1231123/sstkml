"""The ration queue is complete, material, and replaceable."""

from belief.project import project
from engine import actions as A
from engine import seat
from engine.kernel import seat_people as SP
from engine.kernel import world as K
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


def test_seven_visible_groups_cover_every_kept_mouth_without_adding_people():
    world = load_campaign("seat", SEED)
    visible = project(world)["groups"]
    mapped = [SP.placement(group["id"]).cohort for group in visible]
    mouths = K.kept_mouths(world.kernel)

    assert len(visible) == len(mapped) == len(set(mapped)) == 7
    assert set(mapped) == {cohort.id for cohort in mouths}
    assert sum(group["size"] for group in visible) == sum(
        cohort.people for cohort in mouths)
    assert world.kernel.people("settlement:seat") == 80_000


def test_ninety_six_thousand_qa_feeds_whichever_large_claim_goes_first():
    base = load_campaign("seat", SEED)
    stores = seat.held(base)
    stores["grain"] = 96_000
    base = seat.put(base, stores)

    field_first, _ = apply(base, A.SetPriority(FIELD_FIRST))
    palace_first, _ = apply(base, A.SetPriority(PALACE_FIRST))
    field_first = seat.feed(field_first)
    palace_first = seat.feed(palace_first)

    field_roll = seat.groups(field_first)
    palace_roll = seat.groups(palace_first)
    assert (field_roll["field_hands"].arrears,
            field_roll["palace_dependents"].arrears) == (0, 4_000)
    assert (palace_roll["field_hands"].arrears,
            palace_roll["palace_dependents"].arrears) == (4_000, 0)
    assert seat.held(field_first)["grain"] == \
        seat.held(palace_first)["grain"] == 0


def test_a_later_full_queue_replaces_the_first_and_duplicates_are_rejected():
    world = load_campaign("seat", SEED)
    world, _ = apply(world, A.SetPriority(FIELD_FIRST))
    world, events = apply(world, A.SetPriority(PALACE_FIRST))

    assert events == [A.PrioritySet(PALACE_FIRST)]
    assert seat.order_of_payment(world) == PALACE_FIRST
    assert project(world)["priority"] == list(PALACE_FIRST)

    try:
        apply(world, A.SetPriority(("field_hands", "field_hands")))
    except ValueError:
        pass
    else:
        raise AssertionError("a ration queue cannot name one group twice")


def test_a_recovered_granary_repays_one_old_ration_automatically():
    world = load_campaign("seat", SEED)
    groups = seat.groups(world)
    owed = {gid: group.size * group.entitlement
            for gid, group in groups.items()}
    palace = owed["palace_dependents"]
    palace_last = tuple(
        gid for gid in seat.order_of_payment(world)
        if gid != "palace_dependents") + ("palace_dependents",)
    world, _ = apply(world, A.SetPriority(palace_last))
    stores = seat.held(world)
    stores["grain"] = sum(owed.values()) - palace
    world = seat.put(world, stores)
    world = seat.feed(world)

    assert seat.groups(world)["palace_dependents"].arrears == palace
    projected = next(group for group in project(world)["groups"]
                     if group["id"] == "palace_dependents")
    assert projected["allocated"] == palace * 2

    stores = seat.held(world)
    stores["grain"] = sum(owed.values()) + palace
    world = seat.put(world, stores)
    world = seat.feed(world)
    assert seat.groups(world)["palace_dependents"].arrears == 0


def test_an_allowance_above_the_claim_does_not_burn_spare_grain():
    world = load_campaign("seat", SEED)
    owed = sum(group.size * group.entitlement
               for group in seat.groups(world).values())
    world, _ = apply(world, A.Allocate("palace_dependents", 500_000))
    stores = seat.held(world)
    stores["grain"] = owed * 3
    world = seat.put(world, stores)

    world = seat.feed(world)

    assert seat.held(world)["grain"] == owed * 2
