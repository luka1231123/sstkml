from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat as royal_store
from engine import troops
from engine.state import World


# A sack is severe without deleting the next decision. Raiders carry off most
# of the public store; what survives in sealed rooms and household hiding
# places becomes the short ration the player must divide on the following turn.
SACK_LOOT_PER_1000 = 700


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
    resident = 0
    for cohort in world.kernel.registry.cohorts.values():
        if cohort.settlement != seat or cohort.status == "attacker":
            continue
        if cohort.armed:
            defence += cohort.people
        else:
            resident += cohort.people
    # A city is not defended by its garrison alone. When the gate is threatened
    # the households come out with what they have: one in twenty-five, and worth less
    # than a soldier, which is what the garrison is for.
    defence += resident // 25
    stores = royal_store.held(world)
    need = max(1, (attack + defence) * 2)
    stock = stores.get("grain", 0)
    # The wall may consume a great deal, but never the entire strategic store.
    # If defeat and provisioning both zero the granary, the ration order cannot
    # affect the aftermath. Holding half back leaves that decision to the king.
    grain = min(need, stock // 2)
    # Rations decide how well the wall is held, not whether it is held at all.
    # Without the floor an emptied granary left the next band unopposed, so one
    # sack guaranteed the next.
    defence = max(defence // 2, defence * grain // need)
    stores["grain"] = stores.get("grain", 0) - grain
    world = royal_store.put(world, stores, reason_down="consumed")
    if attack > defence:
        return _sacked(world, seat, attack, defence, stores)

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


def _sacked(world: World, seat: str, attack: int, defence: int,
            stores: dict) -> tuple[World, list]:
    """The gate goes. Most grain is taken, people are killed, the city
    remembers, and the raiders settle in it.

    This used to end the campaign outright, which made two thousand hungry
    farmers a terminal event and read as a scripted death. Spec 6.4 puts the
    fall in the ordinary population and unrest rules; a sack feeds them.
    """
    grain = stores.get("grain", 0)
    taken = grain * SACK_LOOT_PER_1000 // 1000
    stores["grain"] = grain - taken
    world = royal_store.put(world, stores, reason_down="lost")

    killed = max(1, (attack - defence) // 2)
    left = killed
    cohorts = dict(world.kernel.registry.cohorts)
    for cohort in sorted(world.kernel.cohorts_of(seat), key=lambda c: c.id):
        if cohort.status == "attacker":
            # The raiders stop raiding: they are in the city now.
            cohorts[cohort.id] = dataclasses.replace(
                cohort, status="displaced", armed=False)
            continue
        lost = min(left, max(0, cohort.people - 1))
        people = cohort.people - lost
        cohorts[cohort.id] = dataclasses.replace(
            cohort, people=people, households=min(cohort.households, people),
            dead=cohort.dead + lost, grievance=min(1000, cohort.grievance + 80))
        left -= lost
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    court = dataclasses.replace(
        world.court, unrest=min(1000, world.court.unrest + 60),
        legitimacy=max(0, world.court.legitimacy - 100))
    world = dataclasses.replace(
        world, court=court,
        kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, [A.SeatTaken(attack, defence, taken, killed)]
