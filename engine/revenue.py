"""Land and harbour dues (spec 6.20).

The two levers deliberately have different clocks. Land dues bite at the
threshing floor and high rates drive hands away every fortnight. Harbour dues
are collected now, but merchants decide to shift their business only after a
seeded three-to-six-turn delay.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import stream
from engine.state import Scheduled, World, replace_court


def set_land_due(world: World, rate: int) -> tuple[World, list]:
    if not 0 <= rate <= 1000:
        raise ValueError("a land due must be between 0 and 1000")
    if rate == world.court.land_due_rate:
        raise ValueError("that is already the land due")
    return replace_court(world, land_due_rate=rate), [A.LandDueSet(rate)]


def set_harbour_due(world: World, rate: int) -> tuple[World, list]:
    if not 0 <= rate <= 1000:
        raise ValueError("a harbour due must be between 0 and 1000")
    court = world.court
    if rate == court.harbour_due_rate:
        raise ValueError("that is already the harbour due")

    scheduled = list(world.schedule)
    old_excess = max(0, court.harbour_due_rate
                     - court.harbour_due_customary)
    excess = max(0, rate - court.harbour_due_customary)
    # A second small raise is a second small offence, not a replay of the
    # entire customs policy. A reduction schedules no miraculous return.
    esteem_loss = max(0, excess // 20 - old_excess // 20)
    if esteem_loss:
        low = world.revenue_rules.get("response_min_turns", 3)
        high = world.revenue_rules.get("response_max_turns", 6)
        traffic_each = esteem_loss * world.revenue_rules.get(
            "traffic_loss_per_esteem", 3)
        for actor in sorted(world.revenue_merchants):
            if actor not in world.relations:
                continue
            delay = low + stream(
                world.seed, world.date.absolute, "revenue.merchant",
                f"{actor}|{rate}").int(max(1, high - low + 1))
            scheduled.append(Scheduled(
                world.date.absolute + delay,
                A.MerchantResponseDue(actor, -esteem_loss, -traffic_each)))
    scheduled.sort(key=lambda item: (
        item.at, type(item.payload).__name__, repr(item.payload)))
    world = dataclasses.replace(
        world, court=dataclasses.replace(court, harbour_due_rate=rate),
        schedule=tuple(scheduled))
    return world, [A.HarbourDueSet(rate)]


def land_take(world: World, gross: int) -> int:
    """The crown's share of one gross harvest."""
    return max(0, gross) * world.court.land_due_rate // 1000


def collect_harbour(world: World) -> tuple[World, list]:
    """Clear finite owned lots and transfer the assessed share to the crown."""
    from engine.institution import effective

    harbour = next((
        inst for inst in sorted(
            world.court.institutions.values(), key=lambda item: item.id)
        if inst.kind == "harbour"), None)
    if harbour is None:
        return world, []
    court = world.court
    capacity = (
        effective(court, harbour)
        * court.harbour_traffic
        * world.revenue_rules.get("clearance_units_per_1000", 100)
        // 1_000_000
    )
    stores = dict(court.stores)
    cargo = dict(world.harbour_cargo)
    events = []
    total_taken = 0
    remaining = capacity
    for lot_id in sorted(cargo):
        lot = cargo[lot_id]
        if lot.place != harbour.place or lot.quantity <= 0 or remaining <= 0:
            continue
        cleared = min(remaining, lot.quantity)
        taken = cleared * court.harbour_due_rate // 1000
        if taken:
            stores[lot.good] = stores.get(lot.good, 0) + taken
        left = lot.quantity - cleared
        if left:
            cargo[lot_id] = dataclasses.replace(lot, quantity=left)
        else:
            del cargo[lot_id]
        total_taken += taken
        remaining -= cleared
        events.append(A.HarbourDueTaken(
            lot.good, cleared, court.harbour_due_rate, taken,
            lot.id, lot.owner, cleared))
    if not events:
        events.append(A.HarbourDueTaken(
            world.revenue_good, 0, court.harbour_due_rate, 0))
    court = dataclasses.replace(
        court, stores=stores, last_harbour_due=total_taken)
    return dataclasses.replace(
        world, court=court, harbour_cargo=cargo), events


def pressure(world: World) -> tuple[World, list]:
    """Apply the fortnightly social cost of a land due above custom."""
    court = world.court
    excess = max(0, court.land_due_rate - court.land_due_base)
    if not excess:
        return world, []
    unrest_delta = excess // world.revenue_rules.get("unrest_divisor", 4)
    unrest = min(1000, court.unrest + unrest_delta)
    flight = (excess // 100
              * world.revenue_rules.get("flight_per_100", 20))
    estates = {}
    flight_events = []
    for key, estate in sorted(court.estates.items()):
        hands = max(0, estate.hands * (1000 - flight) // 1000)
        estates[key] = dataclasses.replace(estate, hands=hands)
        if hands != estate.hands:
            flight_events.append(A.EstateLabourFled(
                estate.id, estate.place, estate.hands, hands))
    court = dataclasses.replace(court, unrest=unrest, estates=estates)
    events = list(flight_events)
    if unrest != world.court.unrest:
        events.append(A.UnrestChanged(
            unrest - world.court.unrest, "the raised land due"))
    return dataclasses.replace(world, court=court), events


def resolve_scheduled(world: World, fired: list) -> tuple[World, list]:
    """Resolve delayed merchant decisions; leave other payloads untouched."""
    remaining = []
    events = []
    for payload in fired:
        if not isinstance(payload, A.MerchantResponseDue):
            remaining.append(payload)
            continue
        relation = world.relations.get(payload.actor)
        if relation is None:
            continue
        relations = dict(world.relations)
        relations[payload.actor] = dataclasses.replace(
            relation, esteem=max(0, min(
                1000, relation.esteem + payload.esteem_delta)))
        court = dataclasses.replace(
            world.court, harbour_traffic=max(
                0, min(1000,
                       world.court.harbour_traffic + payload.traffic_delta)))
        cargo = dict(world.harbour_cargo)
        withdrawal = max(0, -payload.traffic_delta)
        cargo_events = []
        if withdrawal:
            for lot_id in sorted(cargo):
                lot = cargo[lot_id]
                if lot.owner != payload.actor:
                    continue
                quantity = lot.quantity * withdrawal // 1000
                if quantity <= 0 and lot.quantity:
                    quantity = 1
                quantity = min(quantity, lot.quantity)
                left = lot.quantity - quantity
                if left:
                    cargo[lot_id] = dataclasses.replace(lot, quantity=left)
                else:
                    del cargo[lot_id]
                cargo_events.append(A.HarbourCargoWithdrawn(
                    lot.id, lot.owner, lot.good, quantity))
        world = dataclasses.replace(
            world, court=court, relations=relations, harbour_cargo=cargo)
        events.append(A.MerchantWithdrew(
            payload.actor, payload.esteem_delta, payload.traffic_delta))
        events.extend(cargo_events)
    return world, remaining + events
