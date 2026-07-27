"""Plague, and the archive puzzle bolted on top of it (spec 6.12).

Two systems in one file, because they are one mechanic.

The first is an integer SIR model per settlement. It is completely ordinary and
that is deliberate: the epidemic is not the interesting part, it is the clock
that makes the interesting part urgent.

The second is the theological layer. When an epidemic begins the engine picks a
`cause_oath_id` -- a genuinely violated oath, very often one the player's
PREDECESSOR swore, which has been sitting in the archive since before turn one.
The gods are angry about a specific thing. The player must find out which, by
reading, and `expiate` it.

    Correct oath:  beta drops by 40 percent and legitimacy rises.
    Wrong oath:    the offering is gone, the attention is gone, nothing happens.

There is no feedback that distinguishes "wrong oath" from "correct oath, slow
effect". The epidemic curve is the only signal, and an epidemic that is about to
burn out on its own looks exactly like one that has been successfully expiated.
This is the honest version of the historical situation and it must not be
softened with a confirmation message.

Everything here is stdlib and integers. `cause_oath_id` is in FORBIDDEN_KEYS and
is never projected into Belief.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import stream
from engine.state import Place, PlagueState, World

# Spec 6.12: correct expiation drops beta by 40 percent "for the duration".
EXPIATION_BETA_RELIEF = 400        # per mille off beta
EXPIATION_LEGITIMACY = 60


def living(place: Place) -> int:
    return place.susceptible + place.infected + place.recovered


def infected_places(world: World) -> tuple[str, ...]:
    return tuple(sorted(p.id for p in world.places.values() if p.infected > 0))


def total_load(world: World) -> int:
    """Feeds spec 6.14's collapse index. Never displayed."""
    return sum(p.infected for p in world.places.values())


def effective_beta(world: World) -> int:
    """Beta after any correct expiation. Note there is no other caller-visible
    difference between having expiated correctly and having expiated wrongly."""
    plague = world.plague
    if plague.expiated_correctly_turn is None:
        return plague.beta
    return plague.beta * (1000 - EXPIATION_BETA_RELIEF) // 1000


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
    cases = cases or seed_cases(place)
    if place.infected > 0 or place.susceptible < cases:
        return world
    places = dict(world.places)
    places[place_id] = dataclasses.replace(
        place, susceptible=place.susceptible - cases, infected=place.infected + cases)
    return dataclasses.replace(world, places=places)


# --- the theological layer ---------------------------------------------------
def designate_cause(world: World) -> str:
    """Pick the oath the gods are angry about (spec 6.12).

    It must be a *genuinely* violated oath -- one carrying real liability -- so
    that a player who reads carefully can narrow the field rather than guess
    blind. If none qualifies the epidemic has no cause and no expiation will
    ever work, which is a legitimate and quietly horrible state.

    The draw among the qualifying oaths is UNIFORM, deliberately, though an
    earlier version weighted it by liability on the reasoning that the more
    badly broken oath is the likelier grievance. That reasoning is fine and the
    result was bad: Ugarit's Hatti grain oath carries an order of magnitude more
    liability than the old vows, so it was the answer in about three runs in
    four, and a puzzle with a modal answer is a puzzle you solve once and then
    remember. Liability is invisible to the player either way (6.9), so
    weighting bought no fairness -- it only made the game repeat itself.
    """
    liability = world.court.liability
    candidates = sorted(oath.id for oath in world.oaths
                        if liability.get(oath.id, 0) > 0)
    if not candidates:
        return ""
    rng = stream(world.seed, world.date.absolute, "plague.cause", "designate")
    return candidates[rng.int(len(candidates))]


def begin(world: World, place_id: str) -> tuple[World, list]:
    """An epidemic starts. Designates the cause and records the turn."""
    world = seed_place(world, place_id)
    if world.places[place_id].infected <= 0:
        return world, []
    plague = world.plague
    if plague.began_turn is not None:
        return world, [A.PlagueSpread(place_id)]
    cause = designate_cause(world)
    world = dataclasses.replace(world, plague=dataclasses.replace(
        plague, began_turn=world.date.absolute, cause_oath_id=cause))
    return world, [A.PlagueBegan(place_id, world.date.absolute)]


def expiate(world: World, oath_id: str, offering: int = 0) -> tuple[World, list]:
    """Spend an offering on an oath and find out nothing (spec 6.12).

    The returned event names the oath and the offering and says NOTHING about
    whether it was right, because the court does not know. `belief/project.py`
    shows the same. Only the curve tells, and only later.
    """
    plague = world.plague
    court = world.court
    stores = dict(court.stores)
    if offering:
        stores["grain"] = max(0, stores.get("grain", 0) - offering)
    correct = bool(plague.cause_oath_id) and oath_id == plague.cause_oath_id
    legitimacy = court.legitimacy
    if correct and plague.expiated_correctly_turn is None:
        legitimacy = min(1000, legitimacy + EXPIATION_LEGITIMACY)
    court = dataclasses.replace(court, stores=stores, legitimacy=legitimacy)
    plague = dataclasses.replace(
        plague,
        expiated=plague.expiated + (oath_id,),
        expiated_correctly_turn=(
            world.date.absolute
            if correct and plague.expiated_correctly_turn is None
            else plague.expiated_correctly_turn))
    world = dataclasses.replace(world, court=court, plague=plague)
    return world, [A.OathExpiated(oath_id, offering)]


# --- introduction, quarantine, and the turn step ------------------------------
def route_is_quarantined(court, a: str, b: str) -> bool:
    return a in court.quarantined or b in court.quarantined


def _introduction(world: World) -> tuple[World, list]:
    """Spec 6.12: any arrival from a node with I > 0 may seed the destination.

    Arrivals are letters landing this turn. A quarantined place sends nothing,
    which is why quarantine works -- and why it costs, since the same closure
    stops the letters the ruler needs to know anything at all.
    """
    plague = world.plague
    if not plague.exposure:
        return world, []
    seat = world.court.seat
    seat_place = world.places.get(seat)
    if seat_place is None or seat_place.infected > 0 or seat_place.susceptible <= 0:
        return world, []
    sources = sorted(
        {L.path[0] for L in world.inbox
         if L.arrive_turn == world.date.absolute and L.path and not L.outgoing})
    events: list = []
    for origin in sources:
        source = world.places.get(origin)
        if source is None or source.infected <= 0:
            continue
        if route_is_quarantined(world.court, origin, seat):
            continue
        rng = stream(world.seed, world.date.absolute,
                     "plague.transmission", f"{origin}->{seat}")
        if rng.chance(plague.exposure, 1000):
            world, e = begin(world, seat)
            return world, events + e
    return world, events


def step(world: World) -> tuple[World, list]:
    """A4: the plague step per settlement, then mortality.

    Runs before rations and before unrest, because the dead are not fed and the
    grief is not free.
    """
    if not world.places:
        return world, []
    world, events = _introduction(world)
    beta = effective_beta(world)
    plague = world.plague
    if not beta:
        return world, events

    places = dict(world.places)
    deaths_by_place: dict[str, int] = {}
    for place_id in sorted(places):
        before = places[place_id]
        if before.infected <= 0:
            continue
        after = step_place(before, beta, plague.gamma, plague.mortality)
        places[place_id] = after
        died = after.dead - before.dead
        if died:
            deaths_by_place[place_id] = died
    if not deaths_by_place and places == dict(world.places):
        return world, events
    world = dataclasses.replace(world, places=places)

    # The dead at the seat are the ruler's own dependents, and they come off the
    # ration lists. This is the only channel by which the epidemic touches the
    # economy directly, and it is the one the player feels first.
    seat_deaths = deaths_by_place.get(world.court.seat, 0)
    if seat_deaths:
        world = _kill_dependents(world, seat_deaths)
    for place_id in sorted(deaths_by_place):
        events.append(A.PlagueDeaths(place_id, deaths_by_place[place_id]))
    return world, events


def _kill_dependents(world: World, deaths: int) -> World:
    """Spread seat deaths across the groups at the seat, largest first.

    Deliberately not weighted by anything the player controls. A plague is not a
    punishment for bad payroll management, and making it one would turn 6.12
    into another arrears mechanic instead of the theological problem it is.
    """
    court = world.court
    groups = sorted((g for g in court.dependents.values() if g.place == court.seat),
                    key=lambda g: (-g.size, g.id))
    if not groups:
        return world
    total = sum(g.size for g in groups)
    if total <= 0:
        return world
    dependents = dict(court.dependents)
    remaining = min(deaths, total - 1)
    for group in groups:
        if remaining <= 0:
            break
        share = min(remaining, max(1, deaths * group.size // total))
        share = min(share, group.size - 1 if group.size > 1 else 0)
        if share <= 0:
            continue
        dependents[group.id] = dataclasses.replace(
            dependents[group.id], size=group.size - share)
        remaining -= share
    return dataclasses.replace(
        world, court=dataclasses.replace(court, dependents=dependents))
