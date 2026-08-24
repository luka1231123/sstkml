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


def advance(world: World) -> tuple[World, list]:
    """Advance the shared world through one declared phase sequence."""
    if world.ended:
        return world, []
    from engine.kernel import turn as T
    from engine.kernel import world as K

    held = [world]
    phase_events: dict[str, list] = {}

    def step(phase: str, name: str, run) -> T.Step:
        def invoke(kernel):
            current = dataclasses.replace(held[0], kernel=kernel)
            current, produced = run(current)
            held[0] = current
            return current.kernel, produced
        return T.Step(phase, name, invoke)

    extra = (
        step("calendar", "court calendar", _calendar),
        step("arrivals", "court arrivals", _arrivals),
        step("production", "court production",
             lambda w: _production(w, phase_events.get("production", []))),
        step("consumption", "court consumption", _consumption),
        step("health", "court health", _health),
        step("politics", "court politics", _politics),
        step("reports", "court reports", _reports),
        step("project", "court projection", _project),
    )
    kernel, events, _log = K.advance_logged(
        world.kernel, extra_steps=extra, phase_events=phase_events)
    return dataclasses.replace(held[0], kernel=kernel), events


def _calendar(world: World) -> tuple[World, list]:
    from engine import institution
    from engine.kernel import carry

    kernel = world.kernel
    seat_id = getattr(kernel.seat_goods, "seat", "")

    def at_seat(item) -> bool:
        place = world.places.get(item.place)
        alu = (item.place if place is not None and place.kind == "alu"
               else place.alu if place is not None else "")
        return alu == world.chosen_alu

    by_kind = {
        kind: sum(institution.effective(world, item)
                  for item in world.court.institutions.values()
                  if item.kind == kind and at_seat(item))
        for kind in ("canal", "harbour", "road")
    }
    field = kernel.field_site(seat_id, kernel.controller(seat_id))
    site_bonus = ({field: by_kind["canal"]}
                  if field and by_kind["canal"] else {})
    route_bonus = {}
    for route_id, route in kernel.registry.routes.items():
        if not route.legs:
            continue
        ends = {carry.settlement_of(kernel, route.origin),
                carry.settlement_of(kernel, route.destination)}
        if seat_id not in ends:
            continue
        mode = route.legs[0].mode
        bonus = (by_kind["harbour"] if mode == "sea" else
                 by_kind["road"] if mode in {"land", "road"} else 0)
        if bonus:
            route_bonus[route_id] = bonus
    world = dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, inspected=(), searched=()),
        # The court's due is the share its own harvest renders.
        kernel=dataclasses.replace(
            kernel, land_due_per_1000=world.court.land_due_rate,
            baseline=world.baseline, site_extent_bonus=site_bonus,
            route_capacity_bonus=route_bonus))
    return world, [_turn_advanced(world)]


def _arrivals(world: World) -> tuple[World, list]:
    from engine import actions as A
    from engine import displacement, house, justice, mail, relations, revenue, troops

    events: list = []
    if not world.baseline:
        world, arrived = displacement.arrivals(world)
        events += arrived
    world, fired = drain_schedule(world)
    world, fired = relations.resolve_scheduled(world, fired)
    world, fired = revenue.resolve_scheduled(world, fired)
    remaining = []
    for payload in fired:
        if isinstance(payload, A.ChildBorn) and not payload.child_id:
            world, born = house.bear_child(world, payload)
            events += born
        else:
            remaining.append(payload)
    events += remaining
    world, produced = mail.step_letters(world); events += produced
    world = relations.update_unanswered(world)
    world, produced = troops.note_summons(world); events += produced
    return world, events


def _production(world: World, kernel_events: list) -> tuple[World, list]:
    from engine import institution, metal, revenue, works

    events: list = []
    world, produced = seat.harvest(world, kernel_events); events += produced
    world = seat.close_year(world)
    world, produced = metal.step(world); events += produced
    world, produced = institution.step(world); events += produced
    world, produced = revenue.land_cargo(world); events += produced
    world, produced = revenue.collect_harbour(world); events += produced
    world, produced = works.step(world); events += produced
    return world, events


def _consumption(world: World) -> tuple[World, list]:
    events: list = []
    world, produced = systems.spoilage(world); events += produced
    world, produced = systems.do_rites(
        world, world.date.fortnight); events += produced
    before = seat.groups(world)
    world = seat.feed(world)
    world, produced = seat.settle_payroll(world, before); events += produced
    return world, events


def _health(world: World) -> tuple[World, list]:
    from engine import house, plague, shocks

    events: list = []
    if not world.baseline:
        world, produced = shocks.step(world); events += produced
        world, produced = plague.step(world); events += produced
    # Births and deaths are the normal state of existence; always run.
    world, produced = house.step(world); events += produced
    return world, events


def _politics(world: World) -> tuple[World, list]:
    from engine import correspondence_policy, defence, displacement, fall, justice
    from engine import relations, revenue

    events: list = []
    world, produced = systems.recompute_unrest(world); events += produced
    world, produced = revenue.pressure(world); events += produced
    world, produced = justice.step(world); events += produced
    world, produced = relations.audit_oaths(world); events += produced
    world, produced = correspondence_policy.step(world); events += produced
    if not world.baseline:
        world, produced = displacement.step(world); events += produced
        world, produced = fall.step(world); events += produced
        world, produced = defence.step(world); events += produced
    return world, events


def _reports(world: World) -> tuple[World, list]:
    from engine import archive, mail

    world, events = mail.generate_incoming(world)
    world = archive.file_letters(world, world.inbox)
    return world, events


def _project(world: World) -> tuple[World, list]:
    world = _record_stores(world)
    seat_id = f"settlement:{world.chosen_alu}"
    population = world.kernel.people(seat_id)
    return dataclasses.replace(
        world, population_history=world.population_history + (population,)), []


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
