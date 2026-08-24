"""The player's stores in the shared Book."""
from __future__ import annotations

import dataclasses

from engine.entity import EntityId, GoodId, mint
from engine.core import in_range
from engine.kernel import seat_goods as SG
from engine.kernel import seat_people as SP
from engine.state import World


def held(world: World) -> dict[GoodId, int]:
    """The seat's stores, out of the Book. A fresh mapping, safe to mutate."""
    return SG.in_hand(world.kernel.book, world.kernel.seat_goods)


def available(world: World) -> dict[GoodId, int]:
    """The part of the stores not already promised elsewhere."""
    return SG.in_hand(
        world.kernel.book, world.kernel.seat_goods, free_only=True)


def pay(world: World, good: GoodId, amount: int, beneficiary: EntityId,
        *, authority: EntityId = "") -> World:
    """Move a court good to a named beneficiary, atomically."""
    if amount < 0:
        raise ValueError("a payment cannot be negative")
    if amount == 0:
        return world
    view = world.kernel.seat_goods
    lots = SG.lots(world.kernel.book, view, good)
    if sum(lot.free for lot in lots) < amount:
        raise ValueError(f"the crown does not hold {amount:,} {good}")
    book = world.kernel.book
    owed = amount
    ordinal = 12_000
    for lot in lots:
        if owed <= 0:
            break
        current = book.lots[lot.id]
        quantity = min(owed, current.free)
        if quantity <= 0:
            continue
        new_id = None
        if quantity < current.quantity:
            while mint(view.seat, book.turn, "lot", ordinal) in book.lots:
                ordinal += 1
            new_id = mint(view.seat, book.turn, "lot", ordinal)
            ordinal += 1
        book = book.give(
            current.id, quantity, beneficiary, "paid",
            authority=authority, new_id=new_id)
        moved = new_id or current.id
        if book.lots[moved].holder != beneficiary:
            book = book.hand(moved, beneficiary, "paid", authority)
        owed -= quantity
    kernel = dataclasses.replace(world.kernel, book=book)
    return dataclasses.replace(world, kernel=kernel)


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
    """Put the court's ration groups into the registry, once, at load."""
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
        existing = cohorts.get(entry.cohort)
        cohort = SP.as_cohort(group)
        if existing is not None:
            cohort = dataclasses.replace(
                existing, labour_per_head=cohort.labour_per_head,
                ration_per_head=cohort.ration_per_head,
                hunger=cohort.hunger, grievance=cohort.grievance,
                tenure=cohort.tenure, roll_id=cohort.roll_id,
                name=cohort.name, representative=cohort.representative,
                roll_place=cohort.roll_place,
                roll_function=cohort.roll_function,
                shortfall=max(0, group.arrears))
        else:
            cohort = dataclasses.replace(
                cohort, shortfall=max(0, group.arrears))
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
        if existing is None:
            moved[cohort.settlement] = (
                moved.get(cohort.settlement, 0) + cohort.people)
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
    span = tuple(world.season.get("harvest") or (8, 11))
    opening = world.date.fortnight == span[0]
    closing = world.date.fortnight == span[-1]
    running = 0 if opening else world.court.land_due_in_progress
    out: list = []
    grain = held_back = shared = 0
    for event in events:
        if not isinstance(event, tuple) or len(event) < 2:
            continue
        if event[0] == "reaped" and event[2] == seat_id:
            out.append(A.Harvested(event[1], event[3]))
            grain += event[3]
        elif event[0] == "set_aside" and _at_seat(kernel, event[1]):
            held_back += event[2]
        elif (event[0] == "shared_out" and event[2] == seat_id
              and event[3] == "grain"):
            shared += event[4]
    if grain or held_back:
        # Compatibility event: older saves and reports know this shape even
        # though grain now comes straight in from reaping.
        out.append(A.Threshed(grain, held_back))
    if grain:
        # The due is what the crown kept, not what the harvest made: the
        # villages took their share and next year's seed came off the top.
        running += max(0, grain - shared - held_back)
    if not (opening or closing or grain):
        return world, out
    court = dataclasses.replace(world.court, land_due_in_progress=running)
    if closing:
        court = dataclasses.replace(
            court, last_land_due=running, land_due_in_progress=0)
    return dataclasses.replace(world, court=court), out


def close_year(world: World) -> World:
    """Close the court's labour season after the harvest (spec 6.4).

    The seasonal reset used to live in the court's own land module, which C4
    retired when the harvest moved to the kernel. The crown's fields close on
    the kernel's calendar now, so the reset runs here, where `harvest` already
    stands. The corvée, the groups in the fields and `works_days` are all "this
    season" figures; the last harvest fortnight closes them. The first two are
    the cohorts' now, so the reset reaches through to them.
    """
    span = world.season.get("harvest") or (8, 11)
    if world.date.fortnight != span[-1]:
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


def settle_payroll(world: World, before=None) -> tuple[World, list]:
    """Apply payroll consequences and report them."""
    from engine import actions as A
    before = before or groups(world)
    events: list = []
    for entry in SP.PLACEMENTS:
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        if cohort is None:
            continue
        now = SP.as_group(cohort)
        was = before.get(entry.group, now)
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
    known = tuple(sorted(groups(world)))
    current = order_of_payment(world)
    ordered = tuple(dict.fromkeys(group for group in order if group in known))
    full = ordered + tuple(group for group in current if group not in ordered)
    full += tuple(group for group in known if group not in full)
    world_ = world
    for group in known:
        cohort = _cohort_of(world_, group)
        if cohort is not None:
            world_ = _amend(world_, cohort.id, precedence=0)
    for place, group in enumerate(full):
        cohort = _cohort_of(world_, group)
        if cohort is not None:
            world_ = _amend(
                world_, cohort.id, precedence=len(full) - place)
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
    """The complete pay-down order. Highest precedence first."""
    ranked = []
    for group in sorted(groups(world)):
        cohort = _cohort_of(world, group)
        if cohort is not None:
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
