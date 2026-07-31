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


def seed_place(world: World, place_id: str, cases: int = 0) -> World:
    """Put the first cases into a settlement. Idempotent in spirit: seeding a
    place that already has the sickness does nothing new."""
    place = world.places.get(place_id)
    if place is None:
        return world
    cases = max(0, cases) or seed_cases(place)
    if place.infected > 0 or place.susceptible < cases:
        return world
    places = dict(world.places)
    places[place_id] = dataclasses.replace(
        place, susceptible=place.susceptible - cases, infected=place.infected + cases)
    return dataclasses.replace(world, places=places)


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

    places = dict(world.places)
    deaths_by_place: dict[str, int] = {}
    progress: list = []
    for place_id in sorted(places):
        before = places[place_id]
        if before.infected <= 0:
            continue
        after = step_place(before, beta, plague.gamma, plague.mortality)
        places[place_id] = after
        new_infections = before.susceptible - after.susceptible
        recovered = after.recovered - before.recovered
        if new_infections or recovered:
            progress.append(
                A.PlagueProgressed(place_id, new_infections, recovered))
        died = after.dead - before.dead
        if died:
            deaths_by_place[place_id] = died
    if not deaths_by_place and places == dict(world.places):
        return world, events
    world = dataclasses.replace(world, places=places)
    events += progress

    # The dead at the seat are the ruler's own dependents, and they come off the
    # ration lists. This is the only channel by which the epidemic touches the
    # economy directly, and it is the one the player feels first.
    seat_deaths = deaths_by_place.get(world.court.seat, 0)
    if seat_deaths:
        world, dependent_events = _kill_dependents(world, seat_deaths)
        events += dependent_events
    for place_id in sorted(deaths_by_place):
        events.append(A.PlagueDeaths(place_id, deaths_by_place[place_id]))
    return world, events


def _kill_dependents(world: World, deaths: int) -> tuple[World, list]:
    """Apply the court-dependent share of city deaths, largest group first.

    Deliberately not weighted by payroll or ritual choices. Infection is not a
    punishment mechanic.  Court dependents are only part of the settlement, so
    assigning every city burial to the ration lists would erase the palace
    while most of the city's SIR population was still alive.
    """
    court = world.court
    groups = sorted((g for g in court.dependents.values() if g.place == court.seat),
                    key=lambda g: (-g.size, g.id))
    if not groups:
        return world, []
    total = sum(g.size for g in groups)
    if total <= 0:
        return world, []
    seat = world.places.get(court.seat)
    city_before_deaths = living(seat) + deaths if seat is not None else total
    dependent_deaths = deaths * total // max(1, city_before_deaths)
    if dependent_deaths <= 0:
        return world, []
    dependents = dict(court.dependents)
    events = []
    remaining = min(dependent_deaths, total - 1)
    for group in groups:
        if remaining <= 0:
            break
        share = min(
            remaining, max(1, dependent_deaths * group.size // total))
        share = min(share, group.size - 1 if group.size > 1 else 0)
        if share <= 0:
            continue
        dependents[group.id] = dataclasses.replace(
            dependents[group.id], size=group.size - share)
        events.append(A.DependentsDied(
            group.id, group.place, share, "plague"))
        remaining -= share
    return (
        dataclasses.replace(
            world, court=dataclasses.replace(court, dependents=dependents)),
        events,
    )
