"""The turn pipeline (spec Part 5). Written once, reordered never without intent.

advance() runs Phase A (world advance) + the parts of Phase B that don't need
the belief layer. Phase C (player) is driven by the game loop calling
reduce.apply per action. Phase D (dispatch/snapshot) lives in persistence.
"""
from __future__ import annotations

import dataclasses

from engine import systems
from engine.state import World


def drain_schedule(world: World) -> tuple[World, list]:
    """A3: fire everything scheduled for the current absolute turn.

    Fired payloads are returned as events. Their integration into world state
    is per-type and arrives with the systems that create them (letters in M2).
    """
    now = world.date.absolute
    fired = [s.payload for s in world.schedule if s.at == now]
    remaining = tuple(s for s in world.schedule if s.at != now)
    return dataclasses.replace(world, schedule=remaining), list(fired)


def advance(world: World) -> tuple[World, list]:
    """Phase A + B(pre-belief). Returns the events describing this turn's advance."""
    events: list = []

    # A1: date advance. A fresh fortnight: last turn's ledger inspections lapse,
    # so the scribe's count is what the ruler sees again until he inspects anew.
    world = dataclasses.replace(world, date=world.date.advance())
    world = dataclasses.replace(world, court=dataclasses.replace(world.court, inspected=()))
    events.append(_turn_advanced(world))

    # A3: drain the schedule
    world, fired = drain_schedule(world)
    events += fired

    court = world.court
    # A8 spoilage (stock sitting through the fortnight), then A6 deliveries,
    # then rites take their cut, then A8 rations pay from the remainder.
    court, e = systems.spoilage(court); events += e
    court, e = systems.add_income(court); events += e
    court, e = systems.do_rites(court, world.date.fortnight); events += e
    court, e = systems.pay_rations(court); events += e
    # A9 unrest
    court, e = systems.recompute_unrest(court); events += e
    world = dataclasses.replace(world, court=court)

    # Mail: move letters already travelling (delivering arrivals into the Stack),
    # THEN generate this turn's new letters so every one carries at least a leg
    # of latency. Order matters and is fixed.
    from engine import mail
    world, e = mail.step_letters(world); events += e
    world, e = mail.generate_incoming(world); events += e

    return world, events


def _turn_advanced(world: World):
    from engine import actions as A
    return A.TurnAdvanced(world.date.year, world.date.fortnight)
