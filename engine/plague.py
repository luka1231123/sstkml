"""Material disease: explicit import, journey contact, and integer SIR.

The compartment model is deliberately small, but its causal chain is explicit.
An authored boundary event introduces infected travellers at a named place.
After that, another settlement can be seeded only by a modeled exposed journey;
in the current ontology those journeys are courier parties in ``engine.mail``.

Rulers and priests may interpret sickness through vows and offerings.  The
simulation records and pays for those acts, but no hidden oath changes beta,
recovery, mortality, or exposure.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat
from engine.core import stream
from engine.state import Place, World


def living(place: Place) -> int:
    return place.susceptible + place.infected + place.recovered


def infected_places(world: World) -> tuple[str, ...]:
    return tuple(sorted(p.id for p in world.places.values() if p.infected > 0))


def total_load(world: World) -> int:
    """Feeds spec 6.14's collapse index. Never displayed."""
    return sum(p.infected for p in world.places.values())


def effective_beta(world: World) -> int:
    """The pathogen's material transmission parameter.

    Kept as a named function for callers and save-era tests, but M13.0 removes
    every ritual branch from it.
    """
    return world.plague.beta


# --- the compartment model ---------------------------------------------------
def step_place(place: Place, beta: int, gamma: int, mortality: int) -> Place:
    """Spec 6.12's three lines, in that order and with that rounding.

        new_infections = S * I * beta // (pop * 1000)
        recoveries     = I * gamma // 1000
        deaths         = I * mortality // 1000

    Recoveries and deaths are taken from the infected count as it stood at the
    START of the turn, before new infections join it -- otherwise somebody
    infected this fortnight could recover from it in the same fortnight.
    """
    pop = living(place)
    if pop <= 0 or place.infected <= 0:
        return place
    new_infections = place.susceptible * place.infected * beta // (pop * 1000)
    new_infections = min(new_infections, place.susceptible)
    recoveries = place.infected * gamma // 1000
    deaths = place.infected * mortality // 1000
    # Integer floors can, at very small I, remove more than there is.
    if recoveries + deaths > place.infected:
        deaths = min(deaths, place.infected)
        recoveries = place.infected - deaths
    return dataclasses.replace(
        place,
        susceptible=place.susceptible - new_infections,
        infected=place.infected - recoveries - deaths + new_infections,
        recovered=place.recovered + recoveries,
        dead=place.dead + deaths,
    )


# An epidemic seeded with a single case cannot start, and the reason is
# arithmetic rather than epidemiology: with I = 1 and a population of 7,000,
# `S * I * beta // (pop * 1000)` floors to zero, and so do recoveries and
# deaths. The state is a fixed point and the sickness sits there for ever.
#
# The honest fix is to seed the smallest number of cases that is already an
# outbreak rather than a patient. A ship does not deliver one sick man; it
# delivers a crew, and by the time anyone at the palace hears the word for it,
# a street has it. This is also true, which is a convenience.
SEED_DIVISOR = 400          # cases at introduction = population // 400
SEED_FLOOR = 5


def seed_cases(place: Place) -> int:
    return max(SEED_FLOOR, living(place) // SEED_DIVISOR)


def _settlement(world: World, place_id: str) -> str:
    place = world.places.get(place_id)
    if place is None:
        return ""
    return f"settlement:{place_id if place.kind == 'alu' else place.alu}"


def _put(world: World, cohorts: dict) -> World:
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))


def seed_place(world: World, place_id: str, cases: int = 0) -> World:
    """Put the first cases into a settlement. Idempotent in spirit: seeding a
    place that already has the sickness does nothing new."""
    place = world.places.get(place_id)
    if place is None:
        return world
    cases = max(0, cases) or seed_cases(place)
    if place.infected > 0 or place.susceptible < cases:
        return world
    settlement = _settlement(world, place_id)
    cohorts = dict(world.kernel.registry.cohorts)
    left = cases
    for cohort in sorted(
            (c for c in cohorts.values() if c.settlement == settlement),
            key=lambda c: (-c.susceptible, c.id)):
        take = min(left, cohort.susceptible)
        cohorts[cohort.id] = dataclasses.replace(
            cohort, infected=cohort.infected + take)
        left -= take
        if not left:
            break
    return _put(world, cohorts)


def begin(world: World, place_id: str, cases: int = 0) -> tuple[World, list]:
    """Start or spread an epidemic at a settlement through a material caller."""
    if place_id not in world.places:
        raise ValueError(f"no such place: {place_id}")
    before = world.places[place_id]
    world = seed_place(world, place_id, cases)
    if world.places[place_id].infected <= before.infected:
        return world, []
    plague = world.plague
    if plague.began_turn is not None:
        return world, [A.PlagueSpread(place_id)]
    world = dataclasses.replace(world, plague=dataclasses.replace(
        plague, began_turn=world.date.absolute))
    return world, [A.PlagueBegan(place_id, world.date.absolute)]


def expiate(world: World, oath_id: str, offering: int = 0) -> tuple[World, list]:
    """Make a costly ritual interpretation without changing disease physics."""
    offering = max(0, offering)
    plague = world.plague
    court = world.court
    stores = seat.held(world)
    if offering:
        stores["grain"] = max(0, stores.get("grain", 0) - offering)
    plague = dataclasses.replace(
        plague, expiated=plague.expiated + (oath_id,))
    world = dataclasses.replace(world, court=court, plague=plague)
    world = seat.put(world, stores, reason_down="expended")
    return world, [A.OathExpiated(oath_id, offering)]


# --- introduction, quarantine, and the turn step ------------------------------
def route_is_quarantined(court, a: str, b: str) -> bool:
    return a in court.quarantined or b in court.quarantined


def introduce_authored_source(world: World) -> tuple[World, list]:
    """Apply the scenario's explicit external-arrival boundary condition."""
    plague = world.plague
    if (not plague.import_place or plague.import_turn < 0
            or world.date.absolute != plague.import_turn):
        return world, []
    return begin(world, plague.import_place, plague.import_cases)


def _introduction(world: World) -> tuple[World, list]:
    """Resolve exposed courier arrivals recorded by the movement phase.

    The records are consumed even when exposure is zero.  No delivered tablet
    is treated as a magical vector: without the courier having shared a place
    with infected people earlier in this journey, there is no contact record.
    """
    plague = world.plague
    arrivals = tuple(sorted(plague.infectious_arrivals))
    world = dataclasses.replace(
        world, plague=dataclasses.replace(plague, infectious_arrivals=()))
    if not plague.exposure or not arrivals:
        return world, []

    events: list = []
    for courier_id, destination in arrivals:
        place = world.places.get(destination)
        if place is None or place.infected > 0 or place.susceptible <= 0:
            continue
        rng = stream(
            world.seed, world.date.absolute, "plague.transmission",
            f"{courier_id}->{destination}")
        if rng.chance(plague.exposure, 1000):
            world, spread = begin(world, destination)
            events += spread
    return world, events


def step(world: World) -> tuple[World, list]:
    """A4: the plague step per settlement, then mortality.

    Runs before rations and before unrest, because the dead are not fed and the
    grief is not free.
    """
    if not world.places:
        return world, []
    world, events = introduce_authored_source(world)
    world, contacts = _introduction(world)
    events += contacts
    beta = effective_beta(world)
    plague = world.plague
    if not beta:
        return world, events

    places = world.places
    cohorts = dict(world.kernel.registry.cohorts)
    changed = False
    deaths_by_place: dict[str, int] = {}
    progress: list = []
    for place_id in sorted(places):
        before = places[place_id]
        if before.infected <= 0:
            continue
        pop = living(before)
        new_infections = recovered = died = 0
        settlement = _settlement(world, place_id)
        for cohort in sorted(cohorts.values(), key=lambda c: c.id):
            if cohort.settlement != settlement:
                continue
            new = cohort.susceptible * before.infected * beta // (pop * 1000)
            new = min(new, cohort.susceptible)
            rec = cohort.infected * plague.gamma // 1000
            dead = cohort.infected * plague.mortality // 1000
            if rec + dead > cohort.infected:
                dead = min(dead, cohort.infected)
                rec = cohort.infected - dead
            if not (new or rec or dead):
                continue
            people = cohort.people - dead
            cohorts[cohort.id] = dataclasses.replace(
                cohort, people=people,
                households=min(cohort.households, people),
                infected=cohort.infected - rec - dead + new,
                recovered=cohort.recovered + rec, dead=cohort.dead + dead)
            new_infections += new
            recovered += rec
            died += dead
            changed = True
        if new_infections or recovered:
            progress.append(
                A.PlagueProgressed(place_id, new_infections, recovered))
        if died:
            deaths_by_place[place_id] = died
    if not changed:
        return world, events
    world = _put(world, cohorts)
    events += progress
    for place_id in sorted(deaths_by_place):
        events.append(A.PlagueDeaths(place_id, deaths_by_place[place_id]))
    return world, events
