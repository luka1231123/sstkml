from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat as royal_store
from engine.core import stream
from engine.entity import mint
from engine.kernel import carry, farm
from engine.kernel import politics
from engine.kernel import seat_people as SP
from engine.kernel import travel
from engine import troops
from engine.state import World


# A sack is severe without deleting the next decision. Raiders carry off most
# of the public store; what survives in sealed rooms and household hiding
# places becomes the short ration the player must divide on the following turn.
SACK_LOOT_PER_1000 = 700
REGIONAL_LOOT_PER_1000 = {
    farm.GRAIN: 600,
    carry.TIN: 250,
    carry.COPPER: 250,
}
RAIDED_SEAT_ESTEEM = -120
ALLY_DEFENDED_ESTEEM = 60
VASSAL_ABANDONED_ESTEEM = -60


def _place(settlement: str) -> str:
    return settlement.split(":", 1)[-1]


def _change_esteem(world: World, settlement: str, delta: int,
                   *, vassal_only: bool = False) -> World:
    """Apply a visible military act to correspondents at one place."""
    place = _place(settlement)
    relations = dict(world.relations)
    changed = False
    for actor, relation in relations.items():
        if relation.place != place or (vassal_only and not relation.is_vassal):
            continue
        relations[actor] = dataclasses.replace(
            relation, esteem=max(0, min(1000, relation.esteem + delta)))
        changed = True
    return dataclasses.replace(world, relations=relations) if changed else world


def _home(world: World, cohort) -> str:
    origin = cohort.origin
    if origin in world.kernel.registry.settlements:
        return origin
    org = world.kernel.registry.orgs.get(origin)
    return org.settlement if org is not None else ""


def _road(world: World, origin: str, destination: str) -> tuple[str, ...]:
    return travel.shortest_path(
        world.kernel.registry.routes, origin, destination)


def start_raid(world: World, origin: str, target: str = "",
               heads: int = 0, occupy: bool | None = False
               ) -> tuple[World, list]:
    """Split one hungry local body into a real journey to one neighbour.

    This is deliberately the whole military model for autonomous courts. A
    raid is people already in the registry, on the same routes as everyone
    else, carrying no invented army score.
    """
    if origin not in world.kernel.registry.settlements:
        raise ValueError(f"unknown raid origin: {origin}")
    if world.kernel.registry.settlements[origin].fallen:
        raise ValueError("a fallen Alu cannot send raiders")

    choices = sorted({
        edge.destination
        for edge in travel.adjacency(world.kernel.registry.routes).get(
            origin, ())
        if edge.destination in world.kernel.registry.settlements
        and not world.kernel.registry.settlements[edge.destination].fallen
    })
    if target:
        if target not in choices:
            raise ValueError(f"no direct raid route from {origin} to {target}")
    elif choices:
        # A desperate council strikes where food and metal are actually worth
        # taking. Ties by ID keep replay independent of mapping order.
        target = max(choices, key=lambda place: (
            world.kernel.stores(place, farm.GRAIN)
            + world.kernel.stores(place, carry.TIN) * 4
            + world.kernel.stores(place, carry.COPPER) * 2,
            place))
    else:
        raise ValueError(f"no open neighbour from {origin}")

    # Autonomous strong courts take a smaller neighbour; desperate or evenly
    # matched ones raid and leave. The intent is fixed before anyone departs.
    if occupy is None:
        occupy = world.kernel.people(origin) >= world.kernel.people(target) * 2

    candidates = [
        cohort for cohort in world.kernel.cohorts_of(origin)
        if not cohort.in_transit and cohort.status not in {
            "attacker", "defeated", "petitioning", "displaced", "guest"}
        and not cohort.roll_id and cohort.people >= 200
    ]
    if not candidates:
        raise ValueError(f"no body at {origin} can raid")
    source = max(candidates, key=lambda cohort: (cohort.people, cohort.id))
    # Taking and holding a town needs a larger body than a quick grain raid.
    divisor, ceiling = (8, 12000) if occupy else (20, 4000)
    heads = heads or min(ceiling, max(100, source.people // divisor))
    heads = min(heads, source.people - 20)
    if heads <= 0:
        raise ValueError("a raid needs people")

    path = _road(world, origin, target)
    if not path:
        raise ValueError(f"no route from {origin} to {target}")
    parent, party = SP.split(
        source, {"raid": heads}, world.date.absolute)
    if parent.id != source.id:
        parent, party = party, parent
    travel_time = travel.latency(
        world.kernel.registry.routes, origin, target,
        world.season, world.date.fortnight)
    arrives = world.date.absolute + travel_time
    party = dataclasses.replace(
        party, status="travelling_raider", armed=True, task="raid",
        origin=origin, path=path, arrives=arrives)
    if occupy:
        party = dataclasses.replace(party, task="occupy")
    cohorts = dict(world.kernel.registry.cohorts)
    cohorts[parent.id] = parent
    cohorts[party.id] = party
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, [A.RaidLaunched(
        origin, target, heads, arrives, travel_time, party.task)]


def launch(world: World) -> tuple[World, list]:
    """Rarely turn a sustained foreign famine into one neighbouring raid."""
    if world.baseline or world.ended:
        return world, []
    player = f"settlement:{world.chosen_alu}"
    events: list = []
    for origin in world.kernel.autonomous():
        if origin == player:
            continue
        active = any(
            cohort.status in {"travelling_raider", "attacker"}
            and _home(world, cohort) == origin
            for cohort in world.kernel.registry.cohorts.values())
        if active:
            continue
        hunger = max((cohort.hunger for cohort in world.kernel.cohorts_of(origin)
                      if not cohort.in_transit), default=0)
        if hunger < 5:
            continue
        rng = stream(world.seed, world.date.absolute, "world.raid", origin)
        if not rng.chance(min(18, 3 + hunger), 1000):
            continue
        try:
            world, began = start_raid(world, origin, occupy=None)
        except ValueError:
            continue
        events += began
    return world, events


def step(world: World) -> tuple[World, list]:
    if world.ended:
        return world, []
    seat = f"settlement:{world.chosen_alu}"
    events: list = []
    targets = sorted({
        cohort.settlement for cohort in world.kernel.registry.cohorts.values()
        if cohort.status == "attacker" and cohort.armed})
    for target in targets:
        origins = sorted({
            _home(world, cohort) or target
            for cohort in world.kernel.registry.cohorts.values()
            if cohort.settlement == target
            and cohort.status == "attacker" and cohort.armed})
        for origin in origins:
            attackers = [
                cohort for cohort in world.kernel.registry.cohorts.values()
                if cohort.settlement == target
                and cohort.status == "attacker" and cohort.armed
                and (_home(world, cohort) or target) == origin]
            if target == seat:
                world, produced = _defend_seat(world, seat, attackers)
            else:
                world, produced = _defend_region(
                    world, target, origin, attackers)
            events += produced
    return world, events


def _defend_seat(world: World, seat: str, attackers: list) -> tuple[World, list]:
    attack = sum(c.people for c in attackers)
    if not attack:
        return world, []
    # A court that sends its people against the player's own gate cannot keep
    # the same regard it had before the act, whether the gate holds or not.
    for origin in sorted({_home(world, cohort) for cohort in attackers}):
        if origin:
            world = _change_esteem(world, origin, RAIDED_SEAT_ESTEEM)
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


def _consume_local(world: World, settlement: str,
                   quantity: int) -> World:
    book = world.kernel.book.at_phase(world.date.absolute, "politics")
    left = quantity
    for lot in tuple(book.at(settlement)):
        if left <= 0:
            break
        current = book.lots.get(lot.id)
        if current is None or current.good != farm.GRAIN or current.free <= 0:
            continue
        take = min(left, current.free)
        book = book.consume(current.id, take, "consumed")
        left -= take
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))


def _return_attackers(world: World, attackers: list, dead: int) -> World:
    cohorts = dict(world.kernel.registry.cohorts)
    left = dead
    for before in sorted(attackers, key=lambda cohort: cohort.id):
        cohort = cohorts[before.id]
        lost = min(left, cohort.people)
        people = cohort.people - lost
        left -= lost
        if not people:
            cohorts[cohort.id] = dataclasses.replace(
                cohort, people=0, households=0,
                dead=cohort.dead + lost, status="defeated", armed=False,
                task="", path=(), arrives=-1)
            continue
        home = _home(world, cohort)
        path = _road(world, cohort.settlement, home) if home else ()
        if path:
            cohorts[cohort.id] = dataclasses.replace(
                cohort, people=people,
                households=min(cohort.households, people),
                dead=cohort.dead + lost, status="travelling_return",
                armed=True, task="return", path=path,
                arrives=world.date.absolute + travel.latency(
                    world.kernel.registry.routes, cohort.settlement, home,
                    world.season, world.date.fortnight))
        else:
            cohorts[cohort.id] = dataclasses.replace(
                cohort, people=people,
                households=min(cohort.households, people),
                dead=cohort.dead + lost, status="displaced", armed=False,
                task="", path=(), arrives=-1)
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))


def _occupy(world: World, target: str, origin: str,
            attackers: list) -> tuple[World, A.AluOccupied]:
    """Change the owner and leave the attacking body in place. That is all."""
    registry = world.kernel.registry
    former = registry.settlements[target].owner
    conqueror = registry.settlements[origin].owner
    registry = politics.capture(
        registry, target, conqueror, world.date.absolute)
    cohorts = dict(registry.cohorts)
    for before in attackers:
        cohort = cohorts[before.id]
        cohorts[cohort.id] = dataclasses.replace(
            cohort, settlement=target, status="household", armed=True,
            task="garrison", path=(), arrives=-1)
    registry = dataclasses.replace(registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, A.AluOccupied(
        _place(target), former, conqueror,
        sum(cohort.people for cohort in attackers))


def _next_lot(book, settlement: str, turn: int) -> str:
    ordinal = 9800
    while mint(settlement, turn, "lot", ordinal) in book.lots:
        ordinal += 1
    return mint(settlement, turn, "lot", ordinal)


def _seize(world: World, target: str, origin: str,
           good: str, per_1000: int) -> tuple[World, int]:
    book = world.kernel.book.at_phase(world.date.absolute, "politics")
    winner = world.kernel.controller(origin) or origin
    available = sum(
        lot.free for lot in book.at(target)
        if lot.good == good and lot.owner != winner)
    asked = available * per_1000 // 1000
    left = asked
    for lot in tuple(book.at(target)):
        if left <= 0:
            break
        current = book.lots.get(lot.id)
        if current is None or current.good != good or current.owner == winner \
                or current.free <= 0:
            continue
        take = min(left, current.free)
        moved = current.id
        new_id = None
        if take < current.quantity:
            new_id = _next_lot(book, origin, world.date.absolute)
            moved = new_id
        book = book.give(
            current.id, take, winner, "seized", winner, new_id=new_id)
        carried = book.lots[moved]
        if carried.holder != winner:
            book = book.hand(moved, winner, "seized", winner)
        book = book.relocate(moved, origin, "carried", winner)
        left -= take
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    return world, asked - left


def _damage_site(world: World, target: str) -> tuple[World, str]:
    sites = dict(world.kernel.registry.sites)
    candidates = [site for site in sites.values()
                  if site.settlement == target and site.capacity > 0]
    if not candidates:
        return world, ""
    site = max(candidates, key=lambda item: (item.capacity, item.id))
    sites[site.id] = dataclasses.replace(
        site, capacity=max(0, site.capacity * 900 // 1000))
    registry = dataclasses.replace(world.kernel.registry, sites=sites)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry)), site.id


def _hurt_residents(world: World, target: str,
                    attackers: set[str], dead: int) -> World:
    cohorts = dict(world.kernel.registry.cohorts)
    left = dead
    for cohort in sorted(world.kernel.cohorts_of(target), key=lambda item: item.id):
        if cohort.id in attackers or left <= 0:
            continue
        lost = min(left, max(0, cohort.people - 1))
        people = cohort.people - lost
        cohorts[cohort.id] = dataclasses.replace(
            cohort, people=people, households=min(cohort.households, people),
            dead=cohort.dead + lost,
            grievance=min(1000, cohort.grievance + 80))
        left -= lost
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))


def _defend_region(world: World, target: str, origin: str,
                   attackers: list) -> tuple[World, list]:
    attack = sum(cohort.people for cohort in attackers)
    if not attack:
        return world, []
    residents = [
        cohort for cohort in world.kernel.cohorts_of(target)
        if cohort.id not in {item.id for item in attackers}]
    defence = sum(cohort.people for cohort in residents if cohort.armed)
    defence += sum(cohort.people for cohort in residents if not cohort.armed) // 25
    # A formation sent on campaign is now present in the regional world. It
    # answers the raid at that place instead of merely satisfying an oath bit.
    campaign = troops.mustered_for(world.court, _place(target))
    defence += campaign
    stock = sum(lot.free for lot in world.kernel.book.at(target)
                if lot.good == farm.GRAIN)
    need = max(1, (attack + defence) * 2)
    grain = min(need, stock // 2)
    world = _consume_local(world, target, grain)
    defence = max(defence // 2, defence * grain // need)

    if attack <= defence:
        dead = min(attack, max(1, defence // 2))
        world = _return_attackers(world, attackers, dead)
        if campaign:
            world = _change_esteem(world, target, ALLY_DEFENDED_ESTEEM)
        return world, [A.RaidDefeated(
            origin, target, attack, defence, dead, grain)]

    killed = max(1, (attack - defence) // 3)
    world = _hurt_residents(
        world, target, {cohort.id for cohort in attackers}, killed)
    occupying = any(cohort.task == "occupy" for cohort in attackers)
    if occupying:
        world, _damaged = _damage_site(world, target)
        world, occupied = _occupy(world, target, origin, attackers)
        if not campaign:
            world = _change_esteem(
                world, target, VASSAL_ABANDONED_ESTEEM, vassal_only=True)
        return world, [occupied]

    loot = {}
    for good, rate in REGIONAL_LOOT_PER_1000.items():
        world, loot[good] = _seize(world, target, origin, good, rate)
    world, damaged = _damage_site(world, target)
    world = _return_attackers(world, attackers, 0)
    if not campaign:
        # Only a vassal can fairly treat inaction as abandonment. Other rulers
        # may welcome help, but they were never owed it.
        world = _change_esteem(
            world, target, VASSAL_ABANDONED_ESTEEM, vassal_only=True)
    succeeded = A.RaidSucceeded(
        origin, target, attack, defence,
        loot.get(farm.GRAIN, 0), loot.get(carry.TIN, 0),
        loot.get(carry.COPPER, 0), killed, damaged)
    # Raiders do not become a government by accident. Once they leave, the
    # burned Alu is a ruin and drops out of production and the route map.
    from engine import fall
    world, burned = fall.bring_down(
        world, target, f"burned in a raid from {_place(origin)}")
    return world, [succeeded, burned]


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
