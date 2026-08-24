"""Land and harbour dues (spec 6.20).

The two levers deliberately have different clocks. Land dues bite at harvest
and high rates drive hands away every fortnight. Harbour dues
are collected now, but merchants decide to shift their business only after a
seeded three-to-six-turn delay.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat
from engine.core import stream
from engine.state import HarbourCargoLot, Scheduled, World, replace_court


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


def land_cargo(world: World) -> tuple[World, list]:
    """The merchants come back. Once a season, with what traffic and esteem buy.

    Without this the harbour is a drain: two authored cargoes, cleared once, and
    then nothing lands at Ma'hadu ever again. The court's oil is spent on the
    temple lamps and the harbour's own upkeep, so it runs out in about seven
    years and every rite after that is skipped for want of it.

    A merchant's cargo is his own decision, and he makes it on what the court is
    worth to him: `harbour_traffic` for the port, his esteem for the man who
    keeps it. Drive either down and the jars stop coming, which is the lever the
    harbour due was always supposed to have.
    """
    rules = world.revenue_rules
    if world.date.fortnight % rules.get("cargo_fortnights", 6):
        return world, []
    harbour = next((
        inst for inst in sorted(
            world.court.institutions.values(), key=lambda item: item.id)
        if inst.kind == "harbour"), None)
    if harbour is None:
        return world, []
    base = rules.get("cargo_per_merchant", 900)
    cargo = dict(world.harbour_cargo)
    events = []
    good = world.revenue_good
    for actor in sorted(world.revenue_merchants):
        relation = world.relations.get(actor)
        if relation is None:
            continue
        quantity = (base * world.court.harbour_traffic // 1000
                    * relation.esteem // 1000)
        if quantity <= 0:
            continue
        lot_id = f"{actor}_{good}_{world.date.absolute}"
        cargo[lot_id] = HarbourCargoLot(
            id=lot_id, owner=actor, place=harbour.place,
            good=good, quantity=quantity)
        events.append(A.HarbourCargoLanded(lot_id, actor, good, quantity))
    return dataclasses.replace(world, harbour_cargo=cargo), events


def _harbour(world: World):
    return next((
        inst for inst in sorted(
            world.court.institutions.values(), key=lambda item: item.id)
        if inst.kind == "harbour"), None)


def harbour_assessment(
        world: World, effective_capacity: int | None = None,
        ) -> tuple[tuple[str, int], ...]:
    """The cargo lots the next clearance can assess, in ledger order.

    Projection may pass the harbour master's reported capacity. The engine
    omits it and uses the institution's actual output. Keeping the lot split is
    important: the due is rounded on each merchant's lot, not on one invented
    heap.
    """
    from engine.institution import effective

    harbour = _harbour(world)
    if harbour is None:
        return ()
    output = (effective(world, harbour) if effective_capacity is None
              else max(0, effective_capacity))
    remaining = (
        output
        * world.court.harbour_traffic
        * world.revenue_rules.get("clearance_units_per_1000", 100)
        // 1_000_000
    )
    assessed = []
    for lot_id in sorted(world.harbour_cargo):
        lot = world.harbour_cargo[lot_id]
        if lot.place != harbour.place or lot.quantity <= 0 or remaining <= 0:
            continue
        cleared = min(remaining, lot.quantity)
        assessed.append((lot_id, cleared))
        remaining -= cleared
    return tuple(assessed)


def harbour_take(assessment: tuple[tuple[str, int], ...], rate: int) -> int:
    """The due on a clearance assessment, preserving per-lot rounding."""
    rate = max(0, min(1000, rate))
    return sum(max(0, quantity) * rate // 1000
               for _lot_id, quantity in assessment)


def harbour_waiting(world: World) -> int:
    """Cargo physically waiting at the court's harbour."""
    harbour = _harbour(world)
    if harbour is None:
        return 0
    return sum(max(0, lot.quantity) for lot in world.harbour_cargo.values()
               if lot.place == harbour.place)


def collect_harbour(world: World) -> tuple[World, list]:
    """Clear finite owned lots and transfer the assessed share to the crown."""
    harbour = _harbour(world)
    if harbour is None:
        return world, []
    court = world.court
    assessment = harbour_assessment(world)
    stores = seat.held(world)
    cargo = dict(world.harbour_cargo)
    events = []
    total_taken = 0
    for lot_id, cleared in assessment:
        lot = cargo[lot_id]
        taken = cleared * court.harbour_due_rate // 1000
        if taken:
            stores[lot.good] = stores.get(lot.good, 0) + taken
        left = lot.quantity - cleared
        if left:
            cargo[lot_id] = dataclasses.replace(lot, quantity=left)
        else:
            del cargo[lot_id]
        total_taken += taken
        events.append(A.HarbourDueTaken(
            lot.good, cleared, court.harbour_due_rate, taken,
            lot.id, lot.owner, cleared))
    if not events:
        events.append(A.HarbourDueTaken(
            world.revenue_good, 0, court.harbour_due_rate, 0))
    court = dataclasses.replace(court, last_harbour_due=total_taken)
    world = dataclasses.replace(world, court=court, harbour_cargo=cargo)
    # The due is levied off a cargo already in the Book, so what enters the
    # granary here is a move and not a source. `settle` cannot say that yet --
    # it mints -- so the reason is the honest one for a figure the flat
    # arithmetic produced.
    return seat.put(world, stores), events


def pressure(world: World) -> tuple[World, list]:
    """Apply the fortnightly social cost of a land due above custom."""
    court = world.court
    excess = max(0, court.land_due_rate - court.land_due_base)
    if not excess:
        return world, []
    unrest_delta = excess // world.revenue_rules.get("unrest_divisor", 4)
    unrest = min(1000, court.unrest + unrest_delta)
    # C4: the estate hands that used to flee a heavy due are the kernel's
    # ground now; the unrest stands, the flight goes with the estates.
    court = dataclasses.replace(court, unrest=unrest)
    events = []
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
