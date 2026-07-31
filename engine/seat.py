"""What the seat holds, for the court's own systems (Task 2 C2).

`engine.kernel.seat_goods` is the seam; this is the doorway the court walks
through it. The systems that spend the seat's goods -- metal, works, revenue,
institutions, the terms of a letter -- ask `held` for the figures and hand the
result to `put`, and from there the Book is what the answer came out of.

`Court.stores` is still written, as a mirror. It is read by belief projection,
by the interface, and by a long tail of tests, and those move in C5; until they
do, a system that updated only one of the two records would leave the other
saying something false for the rest of the turn. Writing both from one place is
what keeps the overlap honest, and it is one line to delete when the mirror
goes.

A world with no kernel falls back to the flat mapping. Tests build courts
directly, without a scenario behind them, and a system that raised on those
would be untestable in isolation for the sake of a migration.
"""
from __future__ import annotations

import dataclasses

from engine.entity import GoodId
from engine.kernel import seat_goods as SG
from engine.kernel import seat_people as SP
from engine.state import World


def _view(world: World):
    kernel = getattr(world, "kernel", None)
    return kernel.seat_goods if kernel is not None else None


def held(world: World) -> dict[GoodId, int]:
    """The seat's stores, out of the Book. A fresh mapping, safe to mutate."""
    view = _view(world)
    if view is None:
        return dict(world.court.stores)
    return SG.in_hand(world.kernel.book, view)


def put(world: World, stores: dict[GoodId, int], *,
        reason_down: str = "consumed", reason_up: str = "authored",
        authority: str = "") -> World:
    """Record what a system decided about the seat's stores.

    `reason_down` and `reason_up` are why the goods left or entered the world,
    and a caller that knows should say: rations are `consumed`, a smelt is
    `melted` one way and `produced` the other. The defaults are the honest
    answer for a system whose flat arithmetic never said.
    """
    court = dataclasses.replace(world.court, stores=dict(stores))
    view = _view(world)
    if view is None:
        return dataclasses.replace(world, court=court)
    book, view = SG.settle(world.kernel.book, view, stores,
                           reason_down=reason_down, reason_up=reason_up,
                           authority=authority)
    kernel = dataclasses.replace(world.kernel, book=book, seat_goods=view)
    return dataclasses.replace(world, court=court, kernel=kernel)


def record(world: World, court, **why) -> World:
    """Put a court back on the world, and its stores through the seam.

    For the systems that still take and return a bare `Court` -- spoilage,
    rites, rations. They cannot reach the Book from where they stand, so the
    caller carries their figures across, and the Book is in step again before
    anything downstream reads it.
    """
    world = dataclasses.replace(world, court=court)
    return put(world, dict(court.stores), **why)


# --- the seat's people (Task 2 C3) --------------------------------------------
# The same move C2 made for the seat's goods, one record later. The kernel's
# `Cohort` is the authority for the crown's payroll: it holds the heads, the
# hunger and the grievance, and its consumption phase is where those people
# actually eat, out of the palace's lots in the Book. `Court.dependents` is
# written from it as a mirror, because the interface, belief projection, the
# advisors and a long tail of tests read that mapping and they move in C5.
#
# Two fields stay the court's own arithmetic and are recomputed here rather than
# carried: `output_modifier` and `revolting` are consequences of a debt, and the
# table that reads a debt into a consequence is `systems._BANDS` (spec 6.3). A
# kernel module holding a copy of it would be the duplicate authority again.

def enrol(world: World) -> World:
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
        group = world.court.dependents.get(entry.group)
        if group is None:
            continue
        cohort, _ = SP.as_cohort(group)
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


def refresh(world: World) -> World:
    """Read `Court.stores` back off the Book.

    For after something spent the seat's goods without going through `put` --
    the kernel eating a ration is the one case. Without it the next `record`
    would carry a mapping the Book has already moved past, and reconciling the
    two would put the grain back.
    """
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, stores=held(world)))


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
    grain = straw = held_back = 0
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
    if not grain and not held_back:
        return world, out
    out.append(A.Threshed(grain, held_back))
    if not grain:
        # Seed moved aside on a turn with no floor work. It is still a
        # movement the ledger must account for, but it is not a harvest:
        # the year's figure keeps the last threshing's.
        return world, out
    court = dataclasses.replace(world.court, last_land_due=grain)
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


def mirror(world: World) -> tuple[World, list]:
    """Write the payroll back onto the court, and say what changed.

    The events are the ones `systems.pay_rations` used to raise, because they
    are what the log, the advisors and the hall are reading. What raises them
    has moved; what they mean has not.
    """
    from engine import actions as A
    from engine import systems

    kernel = getattr(world, "kernel", None)
    if kernel is None:
        return world, []
    events: list = []
    groups = dict(world.court.dependents)
    for entry in SP.PLACEMENTS:
        was = groups.get(entry.group)
        cohort = kernel.registry.cohorts.get(entry.cohort)
        if was is None or cohort is None:
            continue
        _, residue = SP.as_cohort(was)
        now = SP.as_group(cohort, residue)
        # The debt in qa, off the cohort, not rebuilt out of `hunger`. Hunger
        # counts fortnights and rounds a partial shortfall up to a whole
        # fortnight's ration; the difference is grain the granary still holds
        # and the roll says it paid out, which is spec 2.2 broken by rounding.
        now = dataclasses.replace(now, arrears=cohort.shortfall)
        owed = now.size * now.entitlement
        weeks = now.arrears // max(1, owed)
        # Spec 6.3, unchanged and still the court's: what a ration debt does to
        # the people owed it. The kernel says how much was not delivered; this
        # says what that costs, and then hands the cost back to the kernel,
        # because the heads it takes are the kernel's heads now.
        _, loyalty_delta, out_mod, desertion, revolt = systems._band(weeks)
        revolting = bool(revolt)
        gone = now.size * desertion // 1000 if desertion else 0
        size = now.size - gone
        loyalty = systems._clamp(was.loyalty + loyalty_delta)
        now = dataclasses.replace(
            now, size=size, loyalty=loyalty,
            output_modifier=0 if revolting else out_mod,
            revolting=revolting)
        groups[entry.group] = now
        world = _amend(
            world, cohort.id, people=size,
            households=min(cohort.households, size),
            grievance=SP.grievance_of(loyalty))
        kernel = world.kernel

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
    court = dataclasses.replace(world.court, dependents=groups)
    return dataclasses.replace(world, court=court), events


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
    """Take the dead off the payroll's cohort. The court's copy is the caller's.

    For anything that kills people at the seat outside the ration roll -- the
    plague is the one -- because the cohort is where a head count lives now and
    the mirror would otherwise write the group's size straight back.
    """
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
    for group in sorted(world.court.dependents):
        cohort = _cohort_of(world, group)
        if cohort is not None and cohort.allowance >= 0:
            found[group] = cohort.allowance
    return found


def order_of_payment(world: World) -> tuple[str, ...]:
    """The pay-down order the player set. Highest precedence first."""
    ranked = []
    for group in sorted(world.court.dependents):
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
    for group in sorted(world.court.dependents):
        cohort = _cohort_of(world, group)
        if cohort is not None and cohort.corvee:
            found.append((group, cohort.corvee))
    return tuple(found)


def corvee_days(world: World) -> int:
    """Every day of corvée raised this season, wherever it came from."""
    return sum(days for _group, days in corvee_sources(world))


def to_fields(world: World, group: str, reaping: bool) -> World:
    """Order a group to the harvest, or back to its own work."""
    try:
        entry = SP.placement(group)
    except SP.Unmapped:
        return world
    world = _amend(world, entry.cohort, reaping=bool(reaping))
    return _mirror_fields(world, {group: bool(reaping)})


def _mirror_fields(world: World, wanted: dict) -> World:
    """Carry `reaping` onto the court's groups, which the institutions read."""
    groups = dict(world.court.dependents)
    changed = False
    for group, reaping in wanted.items():
        now = groups.get(group)
        if now is None or now.at_fields == reaping:
            continue
        groups[group] = dataclasses.replace(now, at_fields=reaping)
        changed = True
    if not changed:
        return world
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, dependents=groups))


def at_harvest(world: World) -> tuple[str, ...]:
    """The groups standing in the fields instead of doing their own work."""
    return tuple(
        group for group in sorted(world.court.dependents)
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
    return _mirror_fields(
        world_, {group: False for group in world_.court.dependents})
