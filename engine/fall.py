from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import World

POPULATION_FLOOR = 400


def unrest(world: World, settlement: str) -> int:
    cohorts = tuple(c for c in world.kernel.cohorts_of(settlement)
                    if not c.in_transit and c.people)
    people = sum(c.people for c in cohorts)
    return sum(c.people * c.grievance for c in cohorts) // max(1, people)


def bring_down(world: World, settlement: str, cause: str) -> tuple[World, A.AluFell]:
    registry = world.kernel.registry
    row = registry.settlements[settlement]
    now = world.date.absolute
    polity = registry.polities[row.owner]
    persons = dict(registry.persons)
    elites = []
    ruler = persons.get(polity.ruler)
    # An occupied polity can hold several Alus. Losing an outlying town does
    # not kill a ruler who sits somewhere else.
    if settlement == polity.seat and ruler and ruler.alive:
        persons[ruler.id] = dataclasses.replace(ruler, alive=False, died_turn=now)
        elites.append(ruler.id)
    settlements = dict(registry.settlements)
    settlements[settlement] = dataclasses.replace(
        row, autonomous=False, fell_turn=now, fall_cause=cause)
    court = world.court
    if settlement == f"settlement:{world.chosen_alu}":
        house = {pid: (dataclasses.replace(p, alive=False, died_turn=now)
                       if p.alive else p) for pid, p in court.house.items()}
        elites += [pid for pid, p in court.house.items() if p.alive]
        court = dataclasses.replace(court, house=house)
    registry = dataclasses.replace(registry, settlements=settlements, persons=persons)
    world = dataclasses.replace(
        world, court=court,
        kernel=dataclasses.replace(world.kernel, registry=registry))
    if settlement == f"settlement:{world.chosen_alu}":
        world = dataclasses.replace(
            world, ended=True, end_reason=f"the Alu fell through {cause}",
            ended_turn=now)
    return world, A.AluFell(
        settlement.split(":", 1)[1], cause, world.kernel.people(settlement),
        unrest(world, settlement), tuple(sorted(set(elites))))


def step(world: World) -> tuple[World, list]:
    events = []
    for sid in sorted(world.kernel.registry.settlements):
        row = world.kernel.registry.settlements[sid]
        if row.fallen:
            continue
        people = world.kernel.people(sid)
        unrest_now = unrest(world, sid)
        cause = ("population collapse"
                 if row.population and people * 1000 <= row.population * POPULATION_FLOOR
                 else "maximum unrest" if unrest_now >= 1000 else "")
        if cause:
            world, event = bring_down(world, sid, cause)
            events.append(event)
    return world, events
