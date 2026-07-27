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
    world = dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, inspected=(), searched=(), misfortune_weight=0))
    events.append(_turn_advanced(world))

    # A3: drain the schedule
    world, fired = drain_schedule(world)
    from engine import relations
    world, fired = relations.resolve_scheduled(world, fired)
    # Births are scheduled 20 fortnights out at conception (spec 6.10); the
    # child's sex and health are drawn on arrival, not before.
    from engine import actions as A
    from engine import house
    remaining = []
    for payload in fired:
        if isinstance(payload, A.ChildBorn) and not payload.child_id:
            world, born = house.bear_child(world, payload)
            events += born
        else:
            remaining.append(payload)
    events += remaining

    # Letters already in transit arrive in A3. Delivery-time protocol effects
    # must therefore exist before the A10 oath audit and A12 deck draw.
    from engine import mail
    world, e = mail.step_letters(world); events += e
    world = relations.update_unanswered(world)
    # A demand for men becomes a standing summons the moment it is delivered,
    # read or not (D25). Before the A10 audit, so a summons that came due this
    # turn is judged this turn.
    from engine import troops
    world, e = troops.note_summons(world); events += e

    # A4 plague: introduction off this turn's arrivals, then the compartment
    # step and mortality. Before the house, because a member of the household
    # who dies of the sickness should not also age into a mortality check, and
    # before rations, because the dead are not fed.
    from engine import plague
    world, e = plague.step(world); events += e

    # A5 the house: aging, health, conception, and the yearly mortality check
    # that may kill the ruler and hand the seat to somebody else mid-turn.
    from engine import house
    world, e = house.step(world); events += e

    # A6 agriculture, then A7 workshops and metals. Both run before rations,
    # because the threshing floor is what the granary is paid out of.
    from engine import land, metal
    world, e = land.step(world); events += e
    world, e = metal.step(world); events += e
    # A7b: the fabric of the city goes, a little, every fortnight. After the
    # workshops, because what a forge could do this turn is what it could do
    # before the roof leaked another fortnight's worth.
    from engine import institution
    world, e = institution.step(world); events += e

    court = world.court
    # A8 spoilage (stock sitting through the fortnight), then estate deliveries,
    # then rites take their cut, then A8 rations pay from the remainder.
    court, e = systems.spoilage(court); events += e
    court, e = systems.add_income(court); events += e
    court, e = systems.do_rites(court, world.date.fortnight); events += e
    court, e = systems.pay_rations(court); events += e
    # A9 unrest
    court, e = systems.recompute_unrest(court); events += e
    world = dataclasses.replace(world, court=court)

    # A10/A12: audit explicit oath clauses, then let hidden liability weight
    # misfortune. Neither the liability total nor the causing oath enters Belief.
    world, e = relations.audit_oaths(world); events += e
    world, e = relations.draw_misfortune(world); events += e

    # A15: generate new intents after arrivals, so each new travelling letter
    # still carries at least one full turn of latency.
    world, e = mail.generate_incoming(world); events += e

    # 6.17: file the pile. This runs LAST, after A15, because a correspondent
    # who is standing in the same city has no transit to cross -- an estate
    # overseer's letter is generated and delivered inside the same turn, and
    # filing any earlier misses it. Every letter is offered, not only this
    # turn's arrivals: the scenario's opening inbox predates turn 1 and would
    # otherwise leave a hole exactly where the player's first correspondence
    # belongs. `file_letter` dedupes on ref, so this is idempotent and replay-safe.
    from engine import archive
    for letter in world.inbox:
        world = archive.file_letter(world, letter)

    # D4-adjacent: the stock readings the STORES sparkline draws from (9.4).
    world = _record_stores(world)

    return world, events


_HISTORY = 24                      # one full year, one column per fortnight


def _record_stores(world: World) -> World:
    history = dict(world.court.store_history)
    for good in sorted(world.court.stores):
        series = history.get(good, ())
        history[good] = (series + (world.court.stores.get(good, 0),))[-_HISTORY:]
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, store_history=history))


def _turn_advanced(world: World):
    from engine import actions as A
    return A.TurnAdvanced(world.date.year, world.date.fortnight)
