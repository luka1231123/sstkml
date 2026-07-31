"""Divination as a situated, fallible human forecast.

The diviner reads observations, court records, seasonal tradition, and visible
health.  He never reads ahead in the climate series or asks the mortality RNG
what will happen.  Competence controls how faithfully he interprets evidence;
loyalty controls how often his institutional interest shades the report.

The result remains politically real.  It can be published, suppressed, leaked,
or defied, but later history is not forced to obey it and World stores no
privileged correctness verdict.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import lerp_table, stream
from engine.state import Omen, World

# Harvest bands, worst to best. Neighbouring means adjacent in this list.
HARVEST_BANDS = ("failure", "poor", "middling", "good", "abundant")
QUESTIONS = ("harvest", "death", "route")


def _table(world: World, name: str, x: int, default: int = 0) -> int:
    points = world.house_tables.get(name)
    return default if not points else lerp_table(points, x)


# --- evidence available at the time -----------------------------------------
def _band(value: int, ceilings: tuple[int, ...]) -> int:
    for index, ceiling in enumerate(ceilings):
        if value < ceiling:
            return index
    return len(ceilings)


def _harvest_evidence(world: World) -> str:
    """A coarse reading of today's gauge and completed harvest records only."""
    from engine.legacy.land import gauge_reading

    # The well/gauge is a present observation.  These coarse bands deliberately
    # throw away the exact climate index from which the proxy was produced.
    water = _band(gauge_reading(world), (18, 24, 33, 39))

    # C4: the harvest record was the court's (`last_harvest`) and is deleted;
    # the kernel keeps no completed record for the seat while the court still
    # owns Ugarit. No record means the year is unknowable, which is the truth.
    record = 2

    # Recent water carries twice the weight of a year-old floor record.  Both
    # are available evidence; neither says what next fortnight's weather is.
    index = max(0, min(4, (water * 2 + record) // 3))
    return HARVEST_BANDS[index]


def _death_evidence(world: World, subject: str) -> str:
    """Traditional risk applied to age and visible health, never a death roll."""
    person = world.court.house[subject]
    annual = _table(world, "mortality_by_age", person.age_turns)
    annual = annual * _table(
        world, "mortality_by_health", person.health, 1000) // 1000
    # A forecast of death in the coming season should be rare but not reserved
    # for knowledge of an already-drawn outcome.
    return "yes" if annual >= 120 else "no"


def _route_evidence(world: World, place: str) -> str:
    """Known route topology plus the court's seasonal sailing tradition."""
    from engine.mail import shortest_path
    from engine.systems import sea_open

    path = shortest_path(world.routes, world.court.seat, place) if place else ()
    if place and not path:
        return "shut"

    edges = set(zip(path, path[1:])) | set(
        (b, a) for a, b in zip(path, path[1:]))
    seasonal_sea = (
        not place
        or any((route.a, route.b) in edges
               and route.seasonal and route.mode == "sea"
               for route in world.routes)
    )
    if not seasonal_sea:
        return "open"

    # Three fortnights is the traditional planning horizon used by the old
    # consultation.  Calendar knowledge is not a privileged future value.
    for ahead in range(4):
        fortnight = (world.date.fortnight + ahead - 1) % 24 + 1
        if not sea_open(world.season, fortnight):
            return "shut"
    return "open"


def evidence_forecast(world: World, question: str, subject: str) -> str:
    """The forecast implied by present/past evidence before human distortion."""
    if question == "harvest":
        return _harvest_evidence(world)
    if question == "death":
        if subject not in world.court.house:
            raise ValueError(f"no such person in the house: {subject}")
        return _death_evidence(world, subject)
    if question == "route":
        return _route_evidence(world, subject)
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
    """Shade evidence toward the diviner's institutional interest."""
    bias = _table(world, "diviner_bias", world.court.diviner_loyalty)
    if not rng.chance(bias, 1000):
        return value
    faction = world.court.diviner_faction
    if faction == "temple":
        if question == "harvest":
            index = max(0, HARVEST_BANDS.index(value) - 1)
            return HARVEST_BANDS[index]
        return "yes" if question == "death" else "shut"
    if faction in ("harbour", "merchant"):
        if question == "harvest":
            index = min(len(HARVEST_BANDS) - 1,
                        HARVEST_BANDS.index(value) + 1)
            return HARVEST_BANDS[index]
        return "no" if question == "death" else "open"
    return value


def consult(world: World, question: str, subject: str,
            offering_value: int = 0) -> tuple[World, list]:
    """Take and record a fallible forecast from available evidence."""
    if question not in QUESTIONS:
        raise ValueError(f"the diviner does not read that: {question!r}")
    if question == "death" and subject not in world.court.house:
        raise ValueError(f"no such person in the house: {subject}")

    seq = world.omen_seq + 1
    omen_id = f"O{seq}"
    evidence = evidence_forecast(world, question, subject)

    competence = _table(
        world, "divination_accuracy", world.court.diviner_competence, 500)

    rng = stream(world.seed, world.date.absolute, "divination", omen_id)
    reported = evidence if rng.chance(competence, 1000) else _neighbour(
        question, evidence, rng)
    reported = _faction_shift(world, question, reported, rng)

    # The material offering was already removed by reduce.apply.  It purchases
    # the rite and its public meaning, not access to tomorrow's state.
    _ = offering_value

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
