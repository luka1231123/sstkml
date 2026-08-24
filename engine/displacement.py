from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.kernel import seat_people as SP
from engine.kernel import travel
from engine.state import World


def _destination(world: World, origin: str, exclude: str = "") -> str:
    edges = travel.adjacency(world.kernel.registry.routes).get(origin, ())
    choices = sorted({edge.destination for edge in edges
                      if edge.destination != exclude
                      and not world.kernel.registry.settlements[
                          edge.destination].fallen})
    if not choices:
        return ""

    def distress(settlement: str):
        cohorts = world.kernel.cohorts_of(settlement)
        return (sum(c.hunger for c in cohorts) // max(1, len(cohorts)),
                settlement)

    return min(choices, key=distress)


def _send(world: World, cohort, destination: str, status: str):
    path = travel.shortest_path(
        world.kernel.registry.routes, cohort.settlement, destination)
    if not path:
        raise ValueError(f"no route from {cohort.settlement} to {destination}")
    delay = travel.latency(
        world.kernel.registry.routes, cohort.settlement, destination,
        world.season, world.date.fortnight)
    return dataclasses.replace(
        cohort, status=status, path=path,
        arrives=world.date.absolute + delay, task="migration")


def arrivals(world: World) -> tuple[World, list]:
    cohorts = dict(world.kernel.registry.cohorts)
    changed = False
    for cohort_id in sorted(cohorts):
        cohort = cohorts[cohort_id]
        if cohort.status not in {"travelling_displaced", "travelling_raider"}:
            continue
        if cohort.arrives > world.date.absolute:
            continue
        destination = cohort.path[-1]
        status = "attacker" if cohort.status == "travelling_raider" else (
            "petitioning" if destination == f"settlement:{world.chosen_alu}"
            else "displaced")
        cohorts[cohort_id] = dataclasses.replace(
            cohort, settlement=destination, status=status, path=(),
            arrives=world.date.absolute,
            task="")
        changed = True
    if not changed:
        return world, []
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry)), []


def _settle(cohorts: dict, cohort, **fields):
    """A body of people that stops being displaced rejoins its house.

    Every displacement splits one record into two and nothing used to put them
    back, so a long reign accumulated thousands of one-family cohorts: the turn
    cost grew with them, and the Roll listed the same people many times over.
    """
    settled = dataclasses.replace(cohort, status="household", **fields)
    for other in sorted(cohorts.values(), key=lambda c: c.id):
        if other.id == settled.id or other.parent:
            continue
        try:
            joined = SP.merge((other, settled), into=other.id)
        except ValueError:
            continue
        cohorts.pop(settled.id, None)
        cohorts[other.id] = joined
        return
    cohorts[settled.id] = settled


def step(world: World) -> tuple[World, list]:
    cohorts = dict(world.kernel.registry.cohorts)
    events = []
    for cohort_id in sorted(tuple(cohorts)):
        cohort = cohorts.get(cohort_id)
        if cohort is None:
            continue
        if cohort.status == "displaced" and cohort.hunger < 3:
            _settle(cohorts, cohort, arrives=-1)
            continue
        if (cohort.status == "petitioning" and cohort.arrives >= 0
                and world.date.absolute - cohort.arrives >= 6
                and cohort.hunger >= 7):
            cohorts[cohort_id] = dataclasses.replace(
                cohort, status="attacker", armed=True,
                grievance=max(700, cohort.grievance))
            continue
        if cohort.status == "distressed" and cohort.hunger < 3:
            _settle(cohorts, cohort)
            continue
        if cohort.parent or cohort.status in {
                "distressed", "travelling", "travelling_displaced",
                "travelling_raider", "petitioning", "attacker", "displaced",
                "guest", "raider", "defeated"}:
            continue
        if cohort.hunger < 4 or cohort.people < 20:
            continue
        destination = _destination(world, cohort.settlement)
        if not destination:
            continue
        heads = max(1, cohort.people * min(450, cohort.hunger * 55) // 1000)
        if heads >= cohort.people:
            continue
        parent, party = SP.split(
            cohort, {"displaced": heads}, world.date.absolute)
        if parent.id != cohort.id:
            parent, party = party, parent
        parent = dataclasses.replace(parent, status="distressed")
        hostile = cohort.grievance >= 500 and cohort.hunger >= 6
        party = _send(
            world, party, destination,
            "travelling_raider" if hostile else "travelling_displaced")
        party = dataclasses.replace(
            party, parent="", armed=hostile,
            status=party.status, origin=cohort.origin or cohort.settlement)
        cohorts[parent.id] = parent
        cohorts[party.id] = party
        events.append(A.CohortDisplaced(
            party.id, party.people, cohort.settlement, destination))
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, events


def receive(world: World, cohort_id: str, decision: str,
            destination: str = "") -> tuple[World, object]:
    cohorts = dict(world.kernel.registry.cohorts)
    cohort = cohorts.get(cohort_id)
    seat = f"settlement:{world.chosen_alu}"
    if cohort is None or cohort.status != "petitioning" or cohort.settlement != seat:
        raise ValueError(f"no displaced petition from {cohort_id}")
    if decision == "accept":
        cohort = dataclasses.replace(cohort, status="guest")
    elif decision == "settle":
        cohort = dataclasses.replace(
            cohort, status="household", institution=world.kernel.controller(seat))
    elif decision in {"redirect", "refuse"}:
        target = (f"settlement:{destination}"
                  if destination and not destination.startswith("settlement:")
                  else destination)
        target = target or _destination(world, seat, seat)
        if not target:
            raise ValueError("no open destination")
        hostile = decision == "refuse" and cohort.grievance >= 700
        cohort = _send(
            world, cohort, target,
            "travelling_raider" if hostile else "travelling_displaced")
        cohort = dataclasses.replace(cohort, armed=cohort.armed or hostile)
    else:
        raise ValueError(f"unknown reception {decision!r}")
    cohorts[cohort_id] = cohort
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, A.CohortReceived(cohort_id, decision, destination)
