from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat as royal_store
from engine import troops
from engine.state import World


def step(world: World) -> tuple[World, list]:
    if world.ended:
        return world, []
    seat = f"settlement:{world.chosen_alu}"
    attackers = [c for c in world.kernel.registry.cohorts.values()
                 if c.settlement == seat and c.status == "attacker" and c.armed]
    attack = sum(c.people for c in attackers)
    if not attack:
        return world, []
    defence = troops.garrison_strength(world, world.court.seat)
    defence += sum(c.people for c in world.kernel.registry.cohorts.values()
                   if c.settlement == seat and c.armed
                   and c.status != "attacker")
    stores = royal_store.held(world)
    need = max(1, (attack + defence) * 2)
    grain = min(stores.get("grain", 0), need)
    defence = defence * grain // need
    stores["grain"] = stores.get("grain", 0) - grain
    world = royal_store.put(world, stores, reason_down="consumed")
    if attack > defence:
        world = dataclasses.replace(
            world, ended=True, end_reason="the Seat fell to a displaced force",
            ended_turn=world.date.absolute)
        return world, [A.SeatFell(attack, defence, world.end_reason, grain)]

    dead = min(attack, max(1, defence // 2))
    left = dead
    cohorts = dict(world.kernel.registry.cohorts)
    for cohort in sorted(attackers, key=lambda item: item.id):
        lost = min(left, cohort.people)
        people = cohort.people - lost
        cohorts[cohort.id] = dataclasses.replace(
            cohort, people=people, households=min(cohort.households, people),
            dead=cohort.dead + lost, status="displaced" if people else "defeated",
            armed=bool(people))
        left -= lost
        if not left:
            break
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, [A.SeatDefended(attack, defence, dead, grain)]
