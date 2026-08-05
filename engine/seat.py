"""The player's stores in the shared Book."""
from __future__ import annotations

import dataclasses

from engine.entity import GoodId
from engine.core import in_range
from engine.kernel import seat_goods as SG
from engine.kernel import seat_people as SP
from engine.state import World


def held(world: World) -> dict[GoodId, int]:
    """The seat's stores, out of the Book. A fresh mapping, safe to mutate."""
    return SG.in_hand(world.kernel.book, world.kernel.seat_goods)


def put(world: World, stores: dict[GoodId, int], *,
        reason_down: str = "consumed", reason_up: str = "authored",
        authority: str = "") -> World:
    """Record what a system decided about the seat's stores.

    `reason_down` and `reason_up` are why the goods left or entered the world,
    and a caller that knows should say: rations are `consumed`, a smelt is
    `melted` one way and `produced` the other. The defaults are the honest
    answer for a system whose flat arithmetic never said.
    """
    view = world.kernel.seat_goods
    book, view = SG.settle(world.kernel.book, view, stores,
                           reason_down=reason_down, reason_up=reason_up,
                           authority=authority)
    kernel = dataclasses.replace(world.kernel, book=book, seat_goods=view)
    return dataclasses.replace(world, kernel=kernel)


# --- the seat's people --------------------------------------------------------

def enrol(world: World, groups) -> World:
    """Put the court's dependent groups into the registry, once, at load.

    After this the 1,010 heads on the crown's payroll are cohorts standing at
    the seat like anybody else's people, marked `redistributive` because that is
    what a body owed a ration and owning no grain is. They come out of the
    seat's own cohorts rather than on top of them (`_make_room`): the crown's
    people already lived in that town, and naming them is not the same as
    arriving. What is left of the 80,000 still eats nothing here; their fields
    are the court's until C4, and `kernel.world._mouths` says why at length.
    """
    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return world
    cohorts = dict(kernel.registry.cohorts)
    crown = kernel.controller(SP.SEAT)
    moved: dict[str, int] = {}
    for entry in SP.PLACEMENTS:
        group = groups.get(entry.group)
        if group is None:
            continue
        cohort = SP.as_cohort(group)
        cohort = dataclasses.replace(cohort, shortfall=max(0, group.arrears))
        if entry.settlement not in kernel.registry.settlements:
            # The map has no such place. `PLACEMENTS` names `settlement:mahadu`
            # and the scenario the live world is built from has one settlement
            # of the crown's, the seat -- the same stale id as the `SEAT`
            # constant was, from the retired `content/kernel/world.toml`.
            #
            # So the garrison stands with the rest of the crown's people rather
            # than at a port that does not exist. It is the crown that feeds it
            # either way, which is the fact the ledger is about; where it sleeps
            # becomes a real question when the map has a Ma'hadu, and `prebendal`
            # plus `world._within_reach` is what will answer it then.
            cohort = dataclasses.replace(cohort, settlement=SP.SEAT)
        elif entry.settlement != SP.SEAT:
            # Lives there, fed from here. Not redistributive -- that word says
            # "whoever controls the place I stand in", and the place it stands
            # in is not the one that owes it dinner. `prebendal` is a body kept
            # by the house it serves, and the crown is the house.
            cohort = dataclasses.replace(
                cohort, tenure="prebendal", origin=crown)
        settlement = kernel.registry.settlements[cohort.settlement]
        cohort = dataclasses.replace(
            cohort, ethnicity=settlement.region, status="dependent",
            institution=crown, armed=group.function == "garrison")
        cohorts[cohort.id] = cohort
        moved[cohort.settlement] = moved.get(cohort.settlement, 0) + cohort.people
    cohorts = _make_room(kernel, cohorts, moved)
    registry = dataclasses.replace(kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(kernel, registry=registry))


def _make_room(kernel, cohorts: dict, moved: dict[str, int]) -> dict:
    """Take the payroll's heads out of the town it was already living in.

    The scenario authors a settlement's whole population and the generator
    splits it into craft, field labour and palace. The crown's 1,010 are not a
    thousand people who have just arrived -- they are a thousand of the eighty
    thousand, named. Adding them without subtracting them counts them twice,
    which is spec 2.2 for people and is what `test_registry_mint` asks.

    Which of the three loses them is by weight, so the split stays in
    proportion, and `_apportion` does it exactly rather than by rounding each
    share on its own: floors first, then the remainder one head at a time in
    sorted order, so a replay puts the same person in the same place.
    """
    payroll = {entry.cohort for entry in SP.PLACEMENTS}
    for settlement, heads in sorted(moved.items()):
        hosts = [c for c in cohorts.values()
                 if c.settlement == settlement and c.id not in payroll
                 and c.people > 0]
        if not hosts or heads <= 0:
            continue
        weights = tuple((c.id, c.people) for c in hosts)
        caps = {c.id: c.people for c in hosts}
        for cohort_id, take in SP._apportion(heads, weights, caps).items():
            if take <= 0:
                continue
            host = cohorts[cohort_id]
            people = host.people - take
            cohorts[cohort_id] = dataclasses.replace(
                host, people=people,
                households=min(host.households, people))
    return cohorts


def feed(world: World) -> World:
    """Pay the crown's ration, at A8, out of the Book.

    The kernel does the eating -- one rule for hunger, one for who owns what --
    and this only says when. `engine.kernel.world.feed` is the same code the
    autonomous settlements run in phase 7.
    """
    from engine.kernel import world as K

    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return world
    kernel, _ = K.feed(kernel, K.kept_mouths(kernel), starve=False)
    return dataclasses.replace(world, kernel=kernel)


def harvest(world: World, events: list) -> tuple[World, list]:
    """Court records for the grain year the kernel ran on the crown's fields.

    The kernel is the authority (Task 2 C4/C5); this only says what happened in
    the vocabulary the log, the hall and the archive read. `last_land_due` keeps
    its meaning -- what the land gave the crown last year -- and is what
    `tools/balance.py` budgets against.
    """
    from engine import actions as A

    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return world, []
    seat_id = SP.SEAT
    out: list = []
    grain = straw = held_back = shared = 0
    for event in events:
        if not isinstance(event, tuple) or len(event) < 2:
            continue
        if event[0] == "reaped" and event[2] == seat_id:
            out.append(A.Harvested(event[1], event[3]))
        elif event[0] == "threshed" and event[2] == seat_id:
            grain += event[3]
            straw += event[4]
        elif event[0] == "set_aside" and _at_seat(kernel, event[1]):
            held_back += event[2]
        elif (event[0] == "shared_out" and event[2] == seat_id
              and event[3] == "grain"):
            shared += event[4]
    if not grain and not held_back:
        return world, out
    out.append(A.Threshed(grain, held_back))
    if not grain:
        # Seed moved aside on a turn with no floor work. It is still a
        # movement the ledger must account for, but it is not a harvest:
        # the year's figure keeps the last threshing's.
        return world, out
    # The due is what the crown kept, not what the floor made: the villages took
    # their share and next year's seed came off the top before either.
    took = max(0, grain - shared - held_back)
    court = dataclasses.replace(world.court, last_land_due=took)
    return dataclasses.replace(world, court=court), out


def close_year(world: World) -> World:
    """Close the court's labour season at the threshing fortnight (spec 6.4).

    The seasonal reset used to live in the court's own land module, which C4
    retired when the harvest moved to the kernel. The crown's fields close on
    the kernel's calendar now, so the reset runs here, where `harvest` already
    stands. The corvée, the groups in the fields and `works_days` are all "this
    season" figures; the first threshing fortnight is the new year. The first
    two are the cohorts' now, so the reset reaches through to them.
    """
    span = world.season.get("threshing") or (12, 13)
    if world.date.fortnight != span[0]:
        return world
    world = close_season(world)
    if not world.court.works_days:
        return world
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, works_days=0))


def _at_seat(kernel, actor: str) -> bool:
    org = kernel.registry.orgs.get(actor)
    return bool(org) and org.settlement == SP.SEAT


def groups(world: World) -> dict:
    """The court roll projected from its cohorts."""
    found = {}
    for entry in SP.PLACEMENTS:
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        if cohort is not None:
            found[entry.group] = SP.as_group(cohort)
    return found


def settle_payroll(world: World) -> tuple[World, list]:
    """Apply payroll consequences and report them."""
    from engine import actions as A
    events: list = []
    for entry in SP.PLACEMENTS:
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        if cohort is None:
            continue
        was = SP.as_group(cohort)
        now = was
        owed = now.size * now.entitlement
        weeks = now.arrears // max(1, owed)
        _, loyalty_delta, _output, desertion, revolt = SP.band(weeks)
        revolting = bool(revolt)
        gone = now.size * desertion // 1000 if desertion else 0
        size = now.size - gone
        loyalty = max(0, min(1000, was.loyalty + loyalty_delta))
        world = _amend(
            world, cohort.id, people=size,
            households=min(cohort.households, size),
            grievance=SP.grievance_of(loyalty))

        # What the fortnight cost, read off the debt rather than off a payment:
        # the kernel took grain out of a lot and never formed the figure.
        paid = max(0, owed - (now.arrears - was.arrears))
        events.append(A.RationsPaid(entry.group, owed, paid, now.arrears, weeks))
        if gone:
            events.append(A.DependentsDeparted(
                entry.group, now.place, gone, "ration arrears"))
        if revolting != was.revolting:
            events.append(A.GroupRevoltChanged(
                entry.group, now.place, revolting, now.size))
        if weeks >= 2 and now.member_name:
            events.append(A.Grumbling(entry.group, now.member_name, weeks))
    return world, events


def _amend(world: World, cohort_id: str, **fields) -> World:
    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return world
    cohort = kernel.registry.cohorts.get(cohort_id)
    if cohort is None:
        return world
    cohorts = dict(kernel.registry.cohorts)
    cohorts[cohort_id] = dataclasses.replace(cohort, **fields)
    registry = dataclasses.replace(kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(kernel, registry=registry))


def bury(world: World, group: str, dead: int) -> World:
    """Take the dead off the payroll's cohort."""
    kernel = getattr(world, "kernel", None)
    if kernel is None or dead <= 0:
        return world
    try:
        entry = SP.placement(group)
    except SP.Unmapped:
        return world
    cohort = kernel.registry.cohorts.get(entry.cohort)
    if cohort is None:
        return world
    people = max(0, cohort.people - dead)
    return _amend(world, cohort.id, people=people,
                  households=min(cohort.households, people))


def allow(world: World, group: str, qa: int) -> World:
    """What the crown will hand this group per fortnight, said to the kernel.

    The order the player gives is a ration order, and the store it binds is the
    palace's lots in the Book. Writing it on the cohort is what makes it bite:
    before Task 2 C3 it was read by `systems.pay_rations`, and once that retired
    an allocation of nothing was a lever attached to nothing.
    """
    try:
        entry = SP.placement(group)
    except SP.Unmapped:
        return world
    return _amend(world, entry.cohort, allowance=max(0, qa))


def rank(world: World, order: tuple[str, ...]) -> World:
    """Who eats first when the store will not stretch. Highest served first."""
    world_ = world
    for place, group in enumerate(order):
        try:
            entry = SP.placement(group)
        except SP.Unmapped:
            continue
        world_ = _amend(world_, entry.cohort, precedence=len(order) - place)
    return world_


# --- allocations, precedence, corvée and the fields --------------------------
#
# Five facts the court used to keep in mappings of its own: `allocations`,
# `priority`, `corvee_days`, `corvee_sources` and `at_harvest`. They are all
# facts about a body of people -- what it is allowed, when it is served, how
# many of its days the crown has taken, and whether it is standing in a field
# -- so they live on the cohort, and these are how the court reads them back.

def _cohort_of(world: World, group: str):
    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return None
    try:
        entry = SP.placement(group)
    except SP.Unmapped:
        return None
    return kernel.registry.cohorts.get(entry.cohort)


def allowances(world: World) -> dict:
    """Group -> qa the crown will hand it, for groups where an order stands."""
    found = {}
    for group in sorted(groups(world)):
        cohort = _cohort_of(world, group)
        if cohort is not None and cohort.allowance >= 0:
            found[group] = cohort.allowance
    return found


def order_of_payment(world: World) -> tuple[str, ...]:
    """The pay-down order the player set. Highest precedence first."""
    ranked = []
    for group in sorted(groups(world)):
        cohort = _cohort_of(world, group)
        if cohort is not None and cohort.precedence:
            ranked.append((-cohort.precedence, group))
    return tuple(group for _rank, group in sorted(ranked))


def levy(world: World, sources: tuple[tuple[str, int], ...]) -> World:
    """Write this season's corvée onto the people it is taken from."""
    world_ = world
    for group, days in sources:
        try:
            entry = SP.placement(group)
        except SP.Unmapped:
            continue
        world_ = _amend(world_, entry.cohort, corvee=max(0, int(days)))
    return world_


def corvee_sources(world: World) -> tuple[tuple[str, int], ...]:
    """Days raised this season, per group, in a stable order."""
    found = []
    for group in sorted(groups(world)):
        cohort = _cohort_of(world, group)
        if cohort is not None and cohort.corvee:
            found.append((group, cohort.corvee))
    return tuple(found)


def corvee_days(world: World) -> int:
    """Every day of corvée raised this season, wherever it came from."""
    return sum(c.corvee for c in world.kernel.registry.cohorts.values())


def detach(world: World, cohort_id: str, heads: int, destination: str,
           duration: int, task: str = "work", ration_source: str = "",
           official: str = "") -> tuple[World, object]:
    from engine import actions as A

    cohort = world.kernel.registry.cohorts.get(cohort_id)
    if cohort is None or cohort.parent:
        raise ValueError(f"unknown cohort: {cohort_id}")
    if heads <= 0 or heads >= cohort.people:
        raise ValueError("levy must leave someone in the parent cohort")
    place = world.places.get(destination)
    if place is None:
        raise ValueError(f"unknown destination: {destination}")
    alu = destination if place.kind == "alu" else place.alu
    settlement = f"settlement:{alu}"
    from engine.kernel import travel

    path = travel.shortest_path(
        world.kernel.registry.routes, cohort.settlement, settlement)
    if not path:
        raise ValueError(f"no route to {destination}")
    journey = travel.latency(
        world.kernel.registry.routes, cohort.settlement, settlement,
        world.season, world.date.fortnight)
    duration = max(1, duration)
    arrives = world.date.absolute + journey
    parts = SP.split(cohort, {"detachment": heads}, world.date.absolute)
    parent = next(c for c in parts if c.id == cohort.id)
    party = next(c for c in parts if c.id != cohort.id)
    party = dataclasses.replace(
        party, parent=parent.id, status="travelling", task=task, path=path,
        arrives=arrives, until=arrives + duration,
        ration_source=ration_source or world.kernel.controller(SP.SEAT),
        official=official, corvee=heads * cohort.labour_per_head * duration,
        tenure="prebendal")
    cohorts = dict(world.kernel.registry.cohorts)
    cohorts[parent.id] = parent
    cohorts[party.id] = party
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, A.CohortDetached(
        parent.id, party.id, heads, destination, party.until)


def release(world: World, detachment_id: str) -> tuple[World, object]:
    from engine import actions as A

    cohorts = dict(world.kernel.registry.cohorts)
    party = cohorts.get(detachment_id)
    if party is None or not party.parent:
        raise ValueError(f"unknown detachment: {detachment_id}")
    parent = cohorts.get(party.parent)
    if parent is None:
        raise ValueError(f"missing parent cohort: {party.parent}")
    party = dataclasses.replace(
        party, settlement=parent.settlement, kind=parent.kind,
        status=parent.status, institution=parent.institution,
        armed=parent.armed, parent="", task="", path=(), arrives=-1, until=-1,
        ration_source="", official="", corvee=0, tenure=parent.tenure)
    joined = SP.merge((parent, party), into=parent.id)
    del cohorts[detachment_id]
    cohorts[parent.id] = joined
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, A.CohortReturned(detachment_id, parent.id, party.people)


def return_due(world: World) -> tuple[World, list]:
    events = []
    due = tuple(sorted(
        c.id for c in world.kernel.registry.cohorts.values()
        if c.parent and c.until <= world.date.absolute))
    for cohort_id in due:
        world, event = release(world, cohort_id)
        events.append(event)
    return world, events


def arrive_detachments(world: World) -> World:
    cohorts = dict(world.kernel.registry.cohorts)
    changed = False
    for cohort_id in sorted(cohorts):
        cohort = cohorts[cohort_id]
        if not cohort.parent or cohort.status != "travelling":
            continue
        if cohort.arrives > world.date.absolute:
            continue
        cohorts[cohort_id] = dataclasses.replace(
            cohort, settlement=cohort.path[-1], status="detachment")
        changed = True
    if not changed:
        return world
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))


def source_corvee(world: World, requested: int):
    span = world.season.get("growing")
    turns = max(1, sum(
        1 for fortnight in range(1, 25)
        if span and in_range(fortnight, tuple(span))))
    per_head = world.land_rules.get("labour_days_per_head", 12)
    capacity = {
        group.id: group.size * per_head * turns * group.output_modifier // 1000
        for group in groups(world).values()
        if group.function == "field_labour" and not group.revolting
    }
    existing = dict(corvee_sources(world))
    incremental = {}
    remaining = max(0, requested)
    for group_id, total in sorted(capacity.items()):
        take = min(remaining, max(0, total - existing.get(group_id, 0)))
        if take:
            existing[group_id] = existing.get(group_id, 0) + take
            incremental[group_id] = take
            remaining -= take
        if not remaining:
            break
    return (requested - remaining, tuple(sorted(existing.items())),
            tuple(sorted(incremental.items())))


def to_fields(world: World, group: str, reaping: bool) -> World:
    """Order a group to the harvest, or back to its own work."""
    try:
        entry = SP.placement(group)
    except SP.Unmapped:
        return world
    return _amend(world, entry.cohort, reaping=bool(reaping))


def at_harvest(world: World) -> tuple[str, ...]:
    """The groups standing in the fields instead of doing their own work."""
    return tuple(
        group for group in sorted(groups(world))
        if getattr(_cohort_of(world, group), "reaping", False))


def close_season(world: World) -> World:
    """Clear every cohort's season figures. `close_year` is the caller."""
    world_ = world
    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return world
    for cohort_id in sorted(kernel.registry.cohorts):
        cohort = world_.kernel.registry.cohorts[cohort_id]
        if cohort.corvee or cohort.reaping:
            world_ = _amend(world_, cohort_id, corvee=0, reaping=False)
    return world_
