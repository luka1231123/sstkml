"""Divination (spec 6.11). The only legitimate way to reduce uncertainty.

The engine reads a fact that is *already true* out of the precomputed future --
the climate series fixed at load (6.4), a mortality roll that is a pure function
of (seed, turn, person) -- and then decides how faithfully the diviner reports
it. Nothing is decided here and then retro-fitted as fate. That distinction is
the whole reason this system is honest, and it is why M8 had to precompute the
climate before M9 could ask about it.

Three things degrade the answer, in this order:

  1. accuracy, from the diviner's competence plus what was offered
  2. on failure, a *plausible neighbouring* value -- one band off, or a negated
     boolean. Never noise. A wrong omen must look exactly like a right one.
  3. faction bias, which shades a correct answer toward what the temple already
     wanted, with a probability set by how loyal the diviner is to YOU

The player is never told the accuracy, and there is no field anywhere that says
whether an omen was right. Acting against a published omen costs legitimacy
whether or not it was correct, which is the political part: you are not being
punished for being wrong, you are being punished for being seen to defy the
gods, and those are different things.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import lerp_table, stream
from engine.state import Omen, World

# Harvest bands, worst to best. Neighbouring means adjacent in this list, which
# is what makes a wrong answer plausible rather than absurd.
HARVEST_BANDS = ("failure", "poor", "middling", "good", "abundant")
QUESTIONS = ("harvest", "death", "route")


def _table(world: World, name: str, x: int, default: int = 0) -> int:
    points = world.house_tables.get(name)
    return default if not points else lerp_table(points, x)


# --- the true future ---------------------------------------------------------
def _true_harvest_band(world: World) -> str:
    """What the coming harvest will actually be, read from the fixed series.

    A band, not a number: the gods do not do arithmetic, and a figure would
    make the omen worth more than the whole information economy around it.
    """
    from engine.land import climate_at
    season = world.season.get("growing", ())
    if not season:
        return "middling"
    from engine.core import in_range
    now = world.date.absolute
    values = [climate_at(world, now + ahead) for ahead in range(1, 25)
              if in_range((world.date.fortnight + ahead - 1) % 24 + 1,
                          tuple(season))]
    if not values:
        return "middling"
    mean = sum(values) // len(values)
    for ceiling, band in ((70, "failure"), (88, "poor"),
                          (105, "middling"), (125, "good")):
        if mean < ceiling:
            return band
    return "abundant"


def _true_death(world: World, subject: str) -> str:
    from engine import house
    return "yes" if house.dies_within(world, subject, 8) else "no"


def _true_route(world: World, place: str) -> str:
    """Whether the sea to a place will be shut when it next matters."""
    from engine.systems import sea_open
    ahead = (world.date.fortnight + 3 - 1) % 24 + 1
    return "open" if sea_open(world.season, ahead) else "shut"


def true_answer(world: World, question: str, subject: str) -> str:
    if question == "harvest":
        return _true_harvest_band(world)
    if question == "death":
        return _true_death(world, subject)
    if question == "route":
        return _true_route(world, subject)
    raise ValueError(f"the diviner does not read that: {question!r}")


def _neighbour(question: str, value: str, rng) -> str:
    """A plausible wrong answer: one band off, or the boolean negated."""
    if question == "harvest":
        index = HARVEST_BANDS.index(value)
        options = [i for i in (index - 1, index + 1)
                   if 0 <= i < len(HARVEST_BANDS)]
        return HARVEST_BANDS[rng.pick(tuple(options))]
    if question == "death":
        return "no" if value == "yes" else "yes"
    return "shut" if value == "open" else "open"


def _faction_shift(world: World, question: str, value: str, rng) -> str:
    """The temple would rather the king stayed home and kept the rites, so it
    shades toward the answer that argues for caution: a worse harvest, a death
    to prepare for, a sea that is shut. A loyal diviner does this less. He is
    not more honest; he is loyal to you rather than to them."""
    bias = _table(world, "diviner_bias", world.court.diviner_loyalty)
    if not rng.chance(bias, 1000):
        return value
    if question == "harvest":
        index = max(0, HARVEST_BANDS.index(value) - 1)
        return HARVEST_BANDS[index]
    return "yes" if question == "death" else "shut"


def consult(world: World, question: str, subject: str,
            offering_value: int = 0) -> tuple[World, list]:
    """Take an omen. Returns the world with the omen recorded and the event
    carrying what the diviner said -- which may be wrong, and the player will
    never be told which."""
    if question not in QUESTIONS:
        raise ValueError(f"the diviner does not read that: {question!r}")
    if question == "death" and subject not in world.court.house:
        raise ValueError(f"no such person in the house: {subject}")

    seq = world.omen_seq + 1
    omen_id = f"O{seq}"
    truth = true_answer(world, question, subject)

    accuracy = _table(world, "divination_accuracy",
                      world.court.diviner_competence, 500)
    accuracy += _table(world, "offering_bonus", offering_value)
    accuracy = max(0, min(1000, accuracy))

    rng = stream(world.seed, world.date.absolute, "divination", omen_id)
    reported = truth if rng.chance(accuracy, 1000) else _neighbour(
        question, truth, rng)
    reported = _faction_shift(world, question, reported, rng)

    omen = Omen(id=omen_id, turn=world.date.absolute, question=question,
                subject=subject, reported=reported, published=True)
    world = dataclasses.replace(
        world, omens=world.omens + (omen,), omen_seq=seq)
    return world, [A.OmenTaken(omen_id, question, subject, reported)]


def suppress(world: World, omen_id: str) -> tuple[World, list]:
    """Keep an omen off the record. Costs attention at the call site; the risk
    is that it leaks anyway, and a suppressed omen that leaks is worse than a
    bad one published."""
    omens = []
    found = None
    for omen in world.omens:
        if omen.id == omen_id:
            found = omen
            omen = dataclasses.replace(omen, published=False)
        omens.append(omen)
    if found is None:
        raise ValueError(f"no such omen: {omen_id}")

    events: list = [A.OmenSuppressed(omen_id)]
    court = world.court
    leak = world.house_rules.get("suppression_leak_permille", 220)
    if stream(world.seed, world.date.absolute, "divination",
              f"leak:{omen_id}").chance(leak, 1000):
        delta = world.house_rules.get("suppressed_leak_legitimacy", -140)
        court = dataclasses.replace(
            court, legitimacy=max(0, min(1000, court.legitimacy + delta)))
        events.append(A.OmenLeaked(omen_id, delta))
    return dataclasses.replace(
        world, omens=tuple(omens), court=court), events


def defy(world: World, omen_id: str) -> tuple[World, list]:
    """Act against a published omen. Costs legitimacy whether or not the omen
    was correct -- you are not being punished for being wrong."""
    omens = []
    found = None
    for omen in world.omens:
        if omen.id == omen_id:
            found = omen
            omen = dataclasses.replace(omen, defied_turn=world.date.absolute)
        omens.append(omen)
    if found is None:
        raise ValueError(f"no such omen: {omen_id}")
    if not found.published:
        raise ValueError("an omen nobody heard cannot be defied")
    delta = world.house_rules.get("defied_omen_legitimacy", -80)
    court = dataclasses.replace(
        world.court,
        legitimacy=max(0, min(1000, world.court.legitimacy + delta)))
    return (dataclasses.replace(world, omens=tuple(omens), court=court),
            [A.OmenDefied(omen_id, delta)])
