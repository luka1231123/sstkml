"""Sending court dependents to harvest buys field labour."""

from engine import actions as A
from engine import seat
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign


SEED = 8814402919
PALACE = "palace_dependents"
SEAT = "settlement:seat"


def _harvest(events) -> int:
    return sum(event.qa for event in events
               if isinstance(event, A.Harvested))


def test_a_non_field_group_only_adds_labour_while_assigned():
    world = load_campaign("seat", SEED)
    for _ in range(7):
        world, _ = advance(world)
    cohort = world.kernel.registry.cohorts["cohort:seat_palace"]
    people = world.kernel.people(SEAT)
    ordinary = world.kernel.labour(SEAT)

    sent, _ = apply(world, A.SendToHarvest(PALACE, True))
    recalled, _ = apply(sent, A.SendToHarvest(PALACE, False))

    assert sent.kernel.labour(SEAT) == ordinary + cohort.labour()
    assert recalled.kernel.labour(SEAT) == ordinary
    assert sent.kernel.people(SEAT) == recalled.kernel.people(SEAT) == people


def test_harvest_assignment_bites_and_lasts_through_the_window():
    world = load_campaign("seat", SEED)
    for _ in range(7):
        world, _ = advance(world)
    sent, _ = apply(world, A.SendToHarvest(PALACE, True))

    passive, passive_events = advance(world)
    sent, sent_events = advance(sent)

    assert _harvest(sent_events) > _harvest(passive_events)
    assert seat.groups(sent)[PALACE].at_fields
    assert sent.kernel.people(SEAT) == passive.kernel.people(SEAT)

    for _ in range(5):
        sent, _ = advance(sent)
    assert sent.date.fortnight == 13
    assert not seat.groups(sent)[PALACE].at_fields


def test_hands_cannot_be_parked_in_the_fields_after_harvest():
    world = load_campaign("seat", SEED)
    for _ in range(13):
        world, _ = advance(world)

    try:
        apply(world, A.SendToHarvest(PALACE, True))
    except ValueError as error:
        assert "harvest" in str(error)
    else:
        raise AssertionError("an off-season harvest order was accepted")
