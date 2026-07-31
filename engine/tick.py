"""The turn pipeline (spec Part 5). Written once, reordered never without intent.

advance() runs Phase A (world advance) + the parts of Phase B that don't need
the belief layer. Phase C (player) is driven by the game loop calling
reduce.apply per action. Phase D (dispatch/snapshot) lives in persistence.
"""
from __future__ import annotations

import dataclasses

from engine import seat, systems
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


def step_kernel(world: World) -> tuple[World, list]:
    """A2: advance the autonomous world one fortnight (Task 2 C1).

    Kernel events are tuples, not `engine.actions` records, and they describe
    settlements the player has no standing to see. They are returned in the
    turn's event list because dropping them would make the world's turn
    unobservable to `tools/kernel_inspect.py`; every reader downstream
    isinstance-filters on the action types, so they are inert until C6 gives
    the belief layer somewhere to put them.
    """
    from engine.kernel import world as K
    kernel, events = K.advance(world.kernel)
    return dataclasses.replace(world, kernel=kernel), events


def advance(world: World) -> tuple[World, list]:
    """Phase A + B(pre-belief). Returns the events describing this turn's advance."""
    events: list = []

    # A1: date advance. A fresh fortnight: last turn's ledger inspections lapse,
    # so the scribe's count is what the ruler sees again until he inspects anew.
    world = dataclasses.replace(world, date=world.date.advance())
    world = dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, inspected=(), searched=()))
    events.append(_turn_advanced(world))

    # A2: the world outside the seat. Every other settlement crosses the same
    # fortnight -- sows, tends, reaps, eats, and settles what it owes -- on its
    # own region's weather. Kept here, immediately after A1, because the court
    # phases below are the seat's own turn and the world does not wait on them.
    #
    # The kernel keeps its own date and steps it itself, so this is one advance
    # per world advance and the two dates stay level. Nothing in the court reads
    # kernel state yet (Task 2 C2 onward moves the readers over), so the seat's
    # numbers are unchanged by this call.
    world, e = step_kernel(world); events += e
    # The crown's grain year, said in the court's own vocabulary (C4/C5).
    world, e = seat.harvest(world, e); events += e
    # The year closes: this season's labour figures belong to the season.
    world = seat.close_year(world)

    # A3: drain the schedule
    world, fired = drain_schedule(world)
    from engine import relations
    world, fired = relations.resolve_scheduled(world, fired)
    from engine import justice
    world, fired = justice.resolve_scheduled(world, fired)
    from engine import revenue
    world, fired = revenue.resolve_scheduled(world, fired)
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
    # must therefore exist before the A10 oath audit.
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

    # A7 workshops and metals.
    from engine import metal
    world, e = metal.step(world); events += e
    # A7b: the fabric of the city goes, a little, every fortnight. After the
    # workshops, because what a forge could do this turn is what it could do
    # before the roof leaked another fortnight's worth.
    from engine import institution
    world, e = institution.step(world); events += e
    # Cargo is assessed against what the harbour can actually clear after this
    # fortnight's decay. Merchant withdrawals arrived in A3 and already reduce
    # the traffic presented to it.
    world, e = revenue.collect_harbour(world); events += e

    # A7c: the men on the building site work, or the season is wrong, or the
    # storehouse cannot feed them, and nothing distinguishes the three (6.21).
    # After A7b, so a fortnight's decay is never cancelled by the same
    # fortnight's repair -- the fabric goes first and the men catch up.
    from engine import works
    world, e = works.step(world); events += e

    court = world.court
    # A8 spoilage (stock sitting through the fortnight), then rites take their
    # cut, then rations pay from the remainder. Grain enters only at threshing.
    court, e = systems.spoilage(court); events += e
    # Spoilage crosses on its own, because it is the one sink here that is not
    # somebody eating: spec 2.2 counts spoiled apart from consumed, and a
    # single crossing for the whole block would file rot as a meal.
    world = seat.record(world, court, reason_down="spoiled")
    court = world.court
    court, e = systems.do_rites(court, world.date.fortnight); events += e
    # A8 rations. The payroll is a body of cohorts now and it eats in the
    # kernel, out of the palace's lots (Task 2 C3); `seat.feed` is only the
    # moment, kept where `systems.pay_rations` used to stand so the fortnight's
    # grain still leaves after the rot and after the gods. `seat.mirror` writes
    # the result back onto `Court.dependents` and raises the events the log,
    # the hall and the advisors read. The retired system is in
    # `engine/legacy/rations.py`.
    world = seat.record(world, court, reason_down="consumed")
    world = seat.feed(world)
    world, e = seat.mirror(world); events += e
    # The kernel spent lots directly, so the court's mapping is read back off
    # the Book rather than written to it. Recording it instead would reconcile
    # the Book to a figure taken before the meal, and put the ration back.
    world = seat.refresh(world)
    # A9 unrest
    court, e = systems.recompute_unrest(world.court); events += e
    world = dataclasses.replace(world, court=court)
    # High land dues are an additional pressure, not part of ration arrears,
    # and flight is permanent even if the next order lowers the rate.
    world, e = revenue.pressure(world); events += e
    # A9b: the queue in the hall ages after ordinary unrest is recomputed.
    # Cases arriving today start at zero; old cases add their own pressure once
    # they have stood six fortnights.
    world, e = justice.step(world); events += e

    # A10: audit explicit oath clauses for the human/archive record.
    world, e = relations.audit_oaths(world); events += e

    # A14: the far side of the correspondence. Each foreign court counts its own
    # place, then answers the tablets that have reached it. Observation before
    # decision, and both after arrivals: a court answering today decides from
    # what it can see today, and from a tablet delivered no later than this turn.
    from engine import correspondence_policy, foreign_belief
    world, e = foreign_belief.step(world); events += e
    world, e = correspondence_policy.step(world); events += e

    # A15: generate new intents after arrivals, so each new travelling letter
    # still carries at least one full turn of latency.
    world, e = mail.generate_incoming(world); events += e

    # 6.17: file the pile. This runs LAST, after A15, because a correspondent
    # who is standing in the same city has no transit to cross -- a letter from
    # the same settlement is generated and delivered inside the same turn, and
    # filing any earlier misses it. Every letter is offered, not only this
    # turn's arrivals: the scenario's opening inbox predates turn 1 and would
    # otherwise leave a hole exactly where the player's first correspondence
    # belongs. `file_letter` dedupes on ref, so this is idempotent and replay-safe.
    from engine import archive
    world = archive.file_letters(world, world.inbox)

    # D4-adjacent: the stock readings the STORES sparkline draws from (9.4).
    world = _record_stores(world)

    return world, events


_HISTORY = 24                      # one full year, one column per fortnight


def _record_stores(world: World) -> World:
    """A year of readings, off the Book (Task 2 C2).

    A projection and nothing else: the sparkline the player reads is a picture
    of the seat's lots at the close of each fortnight, not a second record that
    could disagree with them.
    """
    from engine import seat
    stores = seat.held(world)
    history = dict(world.court.store_history)
    for good in sorted(stores):
        series = history.get(good, ())
        history[good] = (series + (stores.get(good, 0),))[-_HISTORY:]
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, store_history=history))


def _turn_advanced(world: World):
    from engine import actions as A
    return A.TurnAdvanced(world.date.year, world.date.fortnight)
