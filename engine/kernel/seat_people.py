"""One population at the seat, counted once (spec 2.2, 5.2; Phase C).

Today the same people are on two payrolls. The court feeds 1,010 heads at Ugarit
as `state.DependentGroup`; the kernel holds 1,300 there as `entity.Cohort`; and
`tools/authority_audit.py` reports both as non-empty because both are true of the
same town. Spec 2.2 says the same person-days cannot be spent twice, and nothing
in either half was in a position to notice that they were.

This module is the seam that ends it, and it is deliberately only a seam. It
converts between the two records without losing a head in either direction, and
it holds the one ledger that says which body of people a meal or a task was
drawn from. It changes no system. `engine/systems.py`, `engine/troops.py` and the
court tick still work exactly as they did; the migration that points them here is
sequenced after this file exists and after the tests below say it is safe.

Four rules, and each one is a test in `tests/test_seat_people.py`:

    people are conserved   every conversion, split and merge preserves heads,
                           and the households inside them
    one meal each          a head fed by the court's ration roll may not also
                           be fed by the kernel's consumption phase
    one task each          a head standing on the wall is not also reaping,
                           which is the garrison-at-harvest case exactly
    persons are not cohorts
                           `Court.house` stays as it is. A `HouseMember` is a
                           named person with an age and an agenda, and there is
                           no arithmetic that turns one into a body of people

The authority table in `docs/PHASE_C_AUTHORITY.md` says the kernel's `Cohort`
owns hunger and grievance after Phase C, and that the court's arrears
bookkeeping is a deletion target. So the translation below reads in the direction
the migration runs -- arrears become hunger -- and the way back exists to prove
that nothing was lost on the way in, not because anything should keep using it.

The one import from the court into the kernel is `state.DependentGroup`, and it
points at the thing being deleted. When `Court.dependents` goes, this module's
`as_group` and `Residue` go with it, and what is left is cohorts.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine.entity import Cohort, EntityId, mint_all
from engine.state import DependentGroup, HouseMember

GroupId = str
PlaceId = str

# The settlement the legacy court is the seat of. Named once, as in the audit.
SEAT = "settlement:ugarit"

# Person-days a head can give in a fortnight. One figure for every function,
# and that is a claim rather than a shortcut: what differs between a smith and a
# field hand is what they are skilled at, not how many days there are in their
# fortnight. `engine/troops.py` says the same thing about a soldier -- "a soldier
# reaps like a man" -- and uses the caller's per-head figure unaltered. 12 is
# `Cohort.labour_per_head`'s own default, so a converted group and an authored
# cohort reckon labour by the same number.
LABOUR_PER_HEAD = 12

# Heads per household. The court counts heads only, so any figure here is
# supplied rather than translated; 5 is the ratio authored in
# content/kernel/world.toml (1,300 people in 260 households at Ugarit, 440 in 90
# at Ma'hadu). It is a stand-in and it is not load-bearing: a `Residue` carries
# the real count once content authors one, and every round trip through this
# module preserves whatever it was given rather than re-deriving it.
HEADS_PER_HOUSEHOLD = 5

# Loyalty and grievance are one scale read from opposite ends, so the map is
# `1000 - x` and nothing else. Any map through a base -- `(700 - loyalty) * 1000
# // 700` and its like -- floors, and a translation that floors is not a
# translation: run it twice and the group has forgiven you. This one is exactly
# its own inverse on 0..1000, which is what "lossless in both directions" has to
# mean if the two fields are ever both live at once.
LOYALTY_SPAN = 1000

# Fortnights of shortfall at which a body of people stops working. The bottom
# band of spec 6.3, and the same figure as the last row of `systems._BANDS`.
# Restated rather than imported: a kernel module reading a court system's table
# would be the second authority this whole phase exists to remove.
REVOLT_FORTNIGHTS = 8

# What a cohort calls the work a group does. Not one-to-one -- a smith and a
# weaver are both `craft` -- which is why `Residue` keeps the court's own word.
KIND_FOR: Mapping[str, str] = {
    "bronze_working": "craft",
    "cult": "cult",
    "field_labour": "field_labour",
    "garrison": "garrison",
    "household": "household",
    "weaving": "craft",
}

# What a draw on a body of people can be for. Closed: a third kind would be a
# third way to spend the same head, and the whole point of the ledger is that
# there are exactly two.
DRAWS = ("food", "work")

# Who is doing the feeding, spelled out, because the double-feed is invisible
# unless both payers are named in the same ledger.
BY_COURT = "court:rations"
BY_KERNEL = "kernel:consumption"


@dataclasses.dataclass(frozen=True)
class Placement:
    """One authored line of the migration map: this group is that cohort."""
    group: GroupId
    cohort: EntityId
    settlement: EntityId


# The map, authored rather than derived. `docs/PHASE_C_AUTHORITY.md` §2 is
# explicit about why: court ids are bare authored strings and kernel ids carry a
# kind prefix, so any rule that turned one into the other would invent an entity
# the first time an authored name did not match the pattern. A group absent from
# this table is a fact nobody owns, and `faults` says so rather than guessing.
#
# `cohort:ugarit_field_hands` is deliberately not `cohort:ugarit_fields`. The
# latter is the placeholder body of 1,300 authored in content/kernel/world.toml
# while the court still owned Ugarit; the two overlap, and `faults` reports the
# overlap rather than quietly adding the two together.
PLACEMENTS: tuple[Placement, ...] = (
    Placement("cult_baal", "cohort:ugarit_temple_servants", SEAT),
    Placement("field_hands", "cohort:ugarit_field_hands", SEAT),
    Placement("garrison_mahadu", "cohort:mahadu_garrison",
              "settlement:mahadu"),
    Placement("household", "cohort:ugarit_household", SEAT),
    Placement("smiths_palace", "cohort:ugarit_smiths", SEAT),
    Placement("weavers", "cohort:ugarit_weavers", SEAT),
)

# Which body of people a formation's men are counted among. Empty, and that is
# the honest state of the content: `content/scenarios/ugarit.toml` authors 390
# men across three formations and no line anywhere says which payroll feeds
# them. `engine/troops.py` asserts in prose that a soldier "is fed out of the
# payroll group he belongs to" and nothing records which group that is.
#
# So this table is empty rather than guessed, `faults` reports every formation
# ordered to the fields that no line accounts for, and a caller who does know
# passes its own map. Filling it in is a content change, not a code one.
STAFFED_BY: Mapping[str, GroupId] = {}


class Unmapped(KeyError):
    """A body of people no line of the migration map accounts for."""


class NotACohort(TypeError):
    """Something that is a person, or is not people at all."""


class DoubleCount(ValueError):
    """A head fed twice, or a person-day spent twice (spec 2.2)."""


@dataclasses.dataclass(frozen=True)
class Residue:
    """What one side of the seam records and the other has no field for.

    Not a cache of the authority and not a second copy of anything: every field
    here is a quantity exactly one side holds. The court has no households and
    no per-head labour; a cohort has no name, no place-word, no `output_modifier`
    and no room for the low-order qa of a debt. Keeping them here is what makes
    the conversion reversible, which is how a migration is checked rather than
    trusted -- and every field dies with `Court.dependents`.
    """
    group: GroupId
    cohort: EntityId
    name: str = ""
    place: PlaceId = ""
    function: str = ""
    households: int = 0
    # Qa of unpaid ration below one whole fortnight of it. `hunger` counts
    # fortnights, `arrears` counts grain, and the low bits of the second are not
    # representable in the first. They are kept rather than dropped because a
    # conversion that loses them is a conversion that forgives a debt.
    arrears_qa: int = 0
    # The court's own note that it is derived and cached (`state.py`). Carried,
    # never recomputed here: recomputing it would need `systems._BANDS`, and a
    # kernel module holding that table is the duplicate authority again.
    output_modifier: int = 1000
    revolting: bool = False
    # The face of a cut (spec 6.3). One of the heads already counted in
    # `people`, not an extra person, and never a `HouseMember`: `load.py` draws
    # this name from the scenario's name list, and the named cast lives in
    # `Court.house` and stays there.
    face: str = ""


def refuse_named(who: object) -> None:
    """Rule four, in one call. A person is not a body of people.

    `Court.house` is a cast (spec 6.10): everyone in it has an age, a location
    that may be a foreign court, a competence, and an agenda of their own. None
    of that survives being averaged, and averaging is all a cohort can do. So a
    `HouseMember` is refused here rather than converted approximately, and the
    refusal is a type error because it is a category error.
    """
    if isinstance(who, HouseMember):
        raise NotACohort(
            f"{getattr(who, 'id', who)!r} is a named person, not a cohort")


def placement(group: GroupId) -> Placement:
    """The authored line for a group, or `Unmapped`."""
    for entry in PLACEMENTS:
        if entry.group == group:
            return entry
    raise Unmapped(f"no kernel cohort is authored for group {group!r}")


def placements_at(settlement: EntityId) -> tuple[Placement, ...]:
    """Every authored line for one settlement, in a stable order."""
    return tuple(sorted(
        (entry for entry in PLACEMENTS if entry.settlement == settlement),
        key=lambda entry: entry.cohort))


# --- the two memories (spec 6.3; the authority table's hunger row) ------------
#
# The court remembers going unpaid as `arrears`, a running total of qa owed, and
# reads a band off it by dividing by one fortnight's full entitlement. The kernel
# remembers going unfed as `hunger`, a count of short fortnights. They are the
# same fact -- how long these people have been hungry because of you -- recorded
# in different units, and `docs/PHASE_C_AUTHORITY.md` says the cohort's is the
# one that survives.
#
# So the division below is not an approximation of the court's figure, it *is*
# the court's figure: `systems.pay_rations` computes `arrears // max(1, size *
# entitlement)` and bands on the result. Everything this seam adds is keeping the
# remainder, so that the trip back is exact.


def hunger_of(arrears: int, size: int, entitlement: int) -> tuple[int, int]:
    """`(fortnights hungry, qa that did not divide)`."""
    owed = max(0, size) * max(0, entitlement)
    arrears = max(0, arrears)
    if owed <= 0:
        # Nobody left, or nothing promised. There is no fortnight's worth to
        # divide by, so the whole debt is remainder and no hunger is claimed.
        return 0, arrears
    return arrears // owed, arrears % owed


def arrears_of(hunger: int, remainder: int, size: int,
               entitlement: int) -> int:
    """The way back. Exact inverse of `hunger_of` for any debt it produced."""
    owed = max(0, size) * max(0, entitlement)
    if owed <= 0:
        return max(0, remainder)
    return max(0, hunger) * owed + max(0, remainder)


def grievance_of(loyalty: int) -> int:
    return _clamp(LOYALTY_SPAN - loyalty)


def loyalty_of(grievance: int) -> int:
    return _clamp(LOYALTY_SPAN - grievance)


def revolting_at(hunger: int) -> bool:
    """What `revolting` becomes once hunger is the authority (spec 6.3)."""
    return hunger >= REVOLT_FORTNIGHTS


def _clamp(x: int, lo: int = 0, hi: int = LOYALTY_SPAN) -> int:
    return lo if x < lo else hi if x > hi else x


# --- conversion ---------------------------------------------------------------

def as_cohort(group: DependentGroup,
              previous: Residue | None = None) -> tuple[Cohort, Residue]:
    """A dependent group as a cohort, plus what a cohort cannot hold.

    `previous` is the residue from an earlier conversion of the same body of
    people. Given one, the fields the court has no room for are restored from it
    rather than supplied again -- which is what makes the cohort -> group ->
    cohort direction lossless, and not merely nearly so.
    """
    refuse_named(group)
    if not isinstance(group, DependentGroup):
        raise NotACohort(f"{group!r} is not a body of dependent people")
    entry = placement(group.id)
    heads = max(0, group.size)
    if previous is not None:
        households = min(heads, max(0, previous.households))
    else:
        households = min(heads, heads // HEADS_PER_HOUSEHOLD) if heads else 0
        if heads and not households:
            households = 1
    hunger, remainder = hunger_of(group.arrears, heads, group.entitlement)
    cohort = Cohort(
        id=entry.cohort,
        settlement=entry.settlement,
        kind=KIND_FOR.get(group.function, group.function),
        households=households,
        people=heads,
        labour_per_head=LABOUR_PER_HEAD,
        ration_per_head=max(0, group.entitlement),
        hunger=hunger,
        grievance=grievance_of(group.loyalty),
    )
    residue = Residue(
        group=group.id, cohort=entry.cohort, name=group.name,
        place=group.place, function=group.function, households=households,
        arrears_qa=remainder, output_modifier=group.output_modifier,
        revolting=group.revolting, face=group.member_name)
    return cohort, residue


def as_group(cohort: Cohort, residue: Residue) -> DependentGroup:
    """A cohort as the dependent group it came from.

    Exists to be checked against, not to be used. Once `Court.dependents` is
    gone there is nothing on the other end of this, and a system that still
    wanted one would be a system that had not been migrated.
    """
    refuse_named(cohort)
    if residue.cohort != cohort.id:
        raise Unmapped(
            f"residue {residue.cohort!r} does not describe {cohort.id!r}")
    return DependentGroup(
        id=residue.group,
        name=residue.name,
        size=max(0, cohort.people),
        entitlement=max(0, cohort.ration_per_head),
        function=residue.function,
        place=residue.place,
        arrears=arrears_of(cohort.hunger, residue.arrears_qa,
                           cohort.people, cohort.ration_per_head),
        loyalty=loyalty_of(cohort.grievance),
        output_modifier=residue.output_modifier,
        member_name=residue.face,
        revolting=residue.revolting,
    )


@dataclasses.dataclass(frozen=True)
class Roster:
    """One settlement's ordinary people, however the two sides record them.

    The whole population of a place and nothing else: no named persons, no
    formations, no institutions. `people()` is the figure the audit's two rows
    are arguing about, and after Phase C it is the only one.
    """
    settlement: EntityId
    cohorts: tuple[Cohort, ...] = ()
    residues: tuple[Residue, ...] = ()

    def cohort(self, cohort_id: EntityId) -> Cohort | None:
        for held in self.cohorts:
            if held.id == cohort_id:
                return held
        return None

    def residue(self, cohort_id: EntityId) -> Residue | None:
        for held in self.residues:
            if held.cohort == cohort_id:
                return held
        return None

    def people(self) -> int:
        return sum(c.people for c in self.cohorts)

    def households(self) -> int:
        return sum(c.households for c in self.cohorts)

    def ration(self) -> int:
        return sum(c.ration() for c in self.cohorts)

    def labour(self) -> int:
        return sum(c.labour() for c in self.cohorts)

    def groups(self) -> tuple[DependentGroup, ...]:
        """Back to the court's record, in a stable order."""
        return tuple(as_group(self.cohorts[i], self.residues[i])
                     for i in range(len(self.cohorts)))


def roster(court, settlement: EntityId = SEAT) -> Roster:
    """Every dependent group at one settlement, as that settlement's people.

    Iterates the authored map rather than the court's mapping, so the result
    does not depend on the order `Court.dependents` happens to be built in
    (spec 2.6). A group the map does not name is left out and reported by
    `faults`: converting it would need an entity id, and inventing one is how a
    migration loses a granary.
    """
    cohorts: list[Cohort] = []
    residues: list[Residue] = []
    for entry in placements_at(settlement):
        group = court.dependents.get(entry.group)
        if group is None:
            continue
        cohort, residue = as_cohort(group)
        cohorts.append(cohort)
        residues.append(residue)
    return Roster(settlement=settlement, cohorts=tuple(cohorts),
                  residues=tuple(residues))


# --- split and merge (spec 5.3's Cohort contract) ------------------------------

def _apportion(total: int, weights: tuple[tuple[str, int], ...],
               caps: Mapping[str, int]) -> dict[str, int]:
    """Divide `total` by weight, exactly, capped, in sorted key order.

    Floor shares first, then the leftover one at a time in sorted order. The
    sort is what makes it replayable: a largest-remainder rule that broke ties
    by iteration order would move a household between two parts depending on
    which of them the caller's loop reached first.
    """
    weight = sum(w for _, w in weights) or 1
    share = {key: min(caps.get(key, w), total * w // weight)
             for key, w in weights}
    left = total - sum(share.values())
    while left > 0:
        moved = False
        for key, _ in sorted(weights):
            if left <= 0:
                break
            if share[key] < caps.get(key, total):
                share[key] += 1
                left -= 1
                moved = True
        if not moved:
            break
    return share


def split(cohort: Cohort, shares: Mapping[str, int],
          turn: int) -> tuple[Cohort, ...]:
    """Send parts of a cohort somewhere, conserving people and households.

    `shares` maps a destination key -- a site, a settlement, a task -- to heads.
    Ids come from `entity.mint_all` over the sorted keys, so the ordinals belong
    to the batch and not to the caller's loop.

    Hunger and grievance are copied unchanged to every part, and that is exact
    rather than convenient: both are per-head intensities, so `people * hunger`
    is conserved by construction. The merge below is where that stops being
    free, and the asymmetry is the reason these are two functions.

    The runtime id domain is `household`, because a split is a body of
    households moving and `entity.ID_DOMAINS` has no `cohort`. Adding one is a
    change to `engine/entity.py` and this module did not make it.
    """
    asked = {key: int(shares[key]) for key in sorted(shares)}
    if any(heads < 0 for heads in asked.values()):
        raise ValueError(f"{cohort.id}: cannot split off negative heads")
    taken = sum(asked.values())
    if taken > cohort.people:
        raise DoubleCount(
            f"{cohort.id}: {taken} heads split from {cohort.people}")
    keys = tuple(key for key in sorted(asked) if asked[key] > 0)
    if not keys:
        return (cohort,)
    ids = mint_all(cohort.id, turn, "household", keys)

    weights = tuple(sorted(
        [(ids[key], asked[key]) for key in keys]
        + [(cohort.id, cohort.people - taken)]))
    caps = {key: heads for key, heads in weights}
    houses = _apportion(cohort.households, weights, caps)

    parts = [dataclasses.replace(
        cohort, id=ids[key], people=asked[key],
        households=houses[ids[key]],
        # Where they are from, once they are no longer only where they live.
        origin=cohort.origin or cohort.settlement) for key in keys]
    parent = dataclasses.replace(
        cohort, people=cohort.people - taken, households=houses[cohort.id])
    return tuple(sorted([parent] + parts, key=lambda c: c.id))


def merge(cohorts: tuple[Cohort, ...], into: EntityId = "") -> Cohort:
    """Two bodies of people becoming one, conserving people and households.

    Refuses cohorts that differ in settlement, kind, ration or per-head labour.
    An average of two ration rates would either invent grain or destroy it every
    fortnight after the merge, and spec 2.2 does not have a rounding allowance.
    Two groups on different rates are two groups; the court's payroll is full of
    them and that is what makes them separate lines.

    Hunger and grievance are people-weighted and floor, so `people * hunger` can
    fall by up to `people - 1`. That is stated rather than hidden: hunger is a
    whole number of fortnights per head, and one body of people cannot carry two
    memories. `split` has no such loss, which is why a split followed by a merge
    is not guaranteed to be the identity and no test here pretends otherwise.
    """
    if not cohorts:
        raise ValueError("nothing to merge")
    ordered = tuple(sorted(cohorts, key=lambda c: c.id))
    first = ordered[0]
    for other in ordered[1:]:
        for field in ("settlement", "kind", "ration_per_head",
                      "labour_per_head"):
            if getattr(other, field) != getattr(first, field):
                raise ValueError(
                    f"{other.id} and {first.id} differ in {field}: "
                    "these are two bodies of people, not one")
    people = sum(c.people for c in ordered)
    households = sum(c.households for c in ordered)
    divisor = max(1, people)
    return dataclasses.replace(
        first,
        id=into or first.id,
        people=people,
        households=min(people, households),
        hunger=sum(c.people * c.hunger for c in ordered) // divisor,
        grievance=sum(c.people * c.grievance for c in ordered) // divisor,
        origin=first.origin if all(
            c.origin == first.origin for c in ordered) else "",
    )


# --- one meal and one task each (spec 2.2) ------------------------------------

@dataclasses.dataclass(frozen=True)
class Draw:
    """A claim on a body of people: a meal, or a task, and how many heads."""
    cohort: EntityId
    kind: str            # one of DRAWS
    by: str              # who feeds them, or what they are doing
    heads: int


@dataclasses.dataclass(frozen=True)
class Muster:
    """Every head at a place, and what each one is already spoken for.

    The invariant is one line long: for either kind of draw, the heads claimed
    from a cohort never exceed the heads in it. That is what makes the
    double-count impossible rather than merely unlikely -- a system cannot feed
    a group the court has already fed, or send the wall's garrison to the
    harvest it is already reaping, without the ledger refusing the draw.

    Person-days are read from the cohort's own `labour()`, applied to the heads
    drawn, so hunger takes the strength before it takes the numbers here exactly
    as it does there and there is no second formula to keep in step.
    """
    roster: Roster
    draws: tuple[Draw, ...] = ()

    def add(self, *draws: Draw) -> Muster:
        held = list(self.draws)
        for draw in draws:
            if draw.kind not in DRAWS:
                raise ValueError(f"a draw is {' or '.join(DRAWS)}: {draw.kind}")
            cohort = self.roster.cohort(draw.cohort)
            if cohort is None:
                raise Unmapped(
                    f"{draw.cohort!r} is not among the people of "
                    f"{self.roster.settlement!r}")
            if draw.heads < 0:
                raise ValueError(f"{draw.cohort}: negative heads drawn")
            taken = sum(d.heads for d in held
                        if d.cohort == draw.cohort and d.kind == draw.kind)
            if taken + draw.heads > cohort.people:
                raise DoubleCount(
                    f"{draw.cohort}: {taken + draw.heads} heads drawn for "
                    f"{draw.kind} from {cohort.people}; "
                    f"{draw.by} is counting people someone else already has")
            held.append(draw)
        return dataclasses.replace(
            self, draws=tuple(sorted(
                held, key=lambda d: (d.cohort, d.kind, d.by, d.heads))))

    def taken(self, cohort_id: EntityId, kind: str) -> int:
        return sum(d.heads for d in self.draws
                   if d.cohort == cohort_id and d.kind == kind)

    def unfed(self) -> int:
        """Heads nobody has undertaken to feed this fortnight."""
        return sum(max(0, c.people - self.taken(c.id, "food"))
                   for c in self.roster.cohorts)

    def days(self, task: str = "") -> int:
        """Person-days drawn, for one task or for all of them."""
        total = 0
        for draw in self.draws:
            if draw.kind != "work" or (task and draw.by != task):
                continue
            cohort = self.roster.cohort(draw.cohort)
            if cohort is None:
                continue
            total += dataclasses.replace(cohort, people=draw.heads).labour()
        return total

    def idle(self) -> int:
        """Person-days standing unclaimed. Never negative, by the invariant."""
        return self.roster.labour() - self.days()

    def faults(self) -> tuple[str, ...]:
        found: list[str] = []
        for cohort in self.roster.cohorts:
            for kind in DRAWS:
                taken = self.taken(cohort.id, kind)
                if taken > cohort.people:
                    found.append(
                        f"{cohort.id}: {taken} heads drawn for {kind} "
                        f"from {cohort.people}")
        if self.days() > self.roster.labour():
            found.append(
                f"{self.roster.settlement}: {self.days()} person-days drawn "
                f"from {self.roster.labour()}")
        return tuple(found)


def kernel_draws(people: Roster) -> tuple[Draw, ...]:
    """The kernel's consumption phase, as claims on heads.

    `world._consume` feeds every cohort of every autonomous settlement, and it
    skips Ugarit today with a comment saying exactly why: the legacy court feeds
    those households and eating their grain twice would model the same mouths
    twice. This turns that comment into a ledger entry, so the next person to
    make Ugarit autonomous finds out from a `DoubleCount` rather than from a
    granary that empties at twice the rate.
    """
    return tuple(Draw(c.id, "food", BY_KERNEL, c.people)
                 for c in people.cohorts)


def court_draws(court, people: Roster,
                staffed_by: Mapping[str, GroupId] = STAFFED_BY,
                ) -> tuple[Draw, ...]:
    """Everything the court already spends these heads on, in one ledger.

    Four sources, and the reason they belong in one place is that no two of them
    can see each other today:

        the ration roll        `systems.pay_rations` feeds every group
        `Court.at_harvest`     groups ordered to the fields instead of their
                               own work, which is all of their heads
        `Court.corvee_sources` days already raised from a group this season
        formations at harvest  `troops.harvest_hands`, which counts a soldier's
                               person-days and knows nothing about the payroll
                               group he eats from

    The last two are the garrison-at-harvest case. A king who puts a group in
    `at_harvest` and also orders the formation his garrison stands in to the
    fields has, today, twice the hands and the same men. Here the second draw
    exceeds the cohort and is refused.

    Formations with no line in `staffed_by` raise nothing and draw nothing:
    nobody has said which people they are, so this cannot say either. `faults`
    reports them.
    """
    draws: list[Draw] = []
    for residue in sorted(people.residues, key=lambda r: r.cohort):
        group = court.dependents.get(residue.group)
        if group is None or group.size <= 0:
            continue
        draws.append(Draw(residue.cohort, "food", BY_COURT, group.size))

    by_group = {r.group: r.cohort for r in people.residues}
    for group_id in sorted(set(court.at_harvest)):
        cohort_id = by_group.get(group_id)
        group = court.dependents.get(group_id)
        if cohort_id is None or group is None or group.size <= 0:
            continue
        draws.append(Draw(cohort_id, "work", "reap", group.size))

    for group_id, days in sorted(court.corvee_sources):
        cohort_id = by_group.get(group_id)
        if cohort_id is None or days <= 0:
            continue
        # Days back into heads, rounding up: a corvée of one day off eleven men
        # still had eleven men standing in the field that morning, and the head
        # is the thing that cannot be in two places.
        heads = -(-int(days) // LABOUR_PER_HEAD)
        draws.append(Draw(cohort_id, "work", "corvee", heads))

    for formation in sorted(court.formations, key=lambda f: f.id):
        if formation.task != "harvest":
            continue
        cohort_id = by_group.get(staffed_by.get(formation.id, ""))
        if cohort_id is None:
            continue
        # `troops.capable`: men who can do the task with serviceable kit.
        heads = max(0, min(formation.strength, formation.ready))
        if heads:
            draws.append(Draw(cohort_id, "work", "reap", heads))
    return tuple(draws)


def muster(court, settlement: EntityId = SEAT,
           staffed_by: Mapping[str, GroupId] = STAFFED_BY) -> Muster:
    """The court's fortnight as one ledger over one population.

    Raises `DoubleCount` on a court that is already spending a head twice, which
    is the point: this is the check the migration runs before it moves a system,
    not a repair it applies afterwards.
    """
    people = roster(court, settlement)
    return Muster(roster=people).add(
        *court_draws(court, people, staffed_by))


# --- faults (spec 11.1's habit, applied to the seam) --------------------------

def faults(court, settlement: EntityId = SEAT, registry=None,
           staffed_by: Mapping[str, GroupId] = STAFFED_BY) -> tuple[str, ...]:
    """Everything wrong at this seam, as sentences. Empty means it is sound.

    Reports rather than raises, because this is an inventory in the same sense
    `tools/authority_audit.py` is one: the two records are allowed to disagree
    during the migration, and what is not allowed is nobody noticing.
    """
    found: list[str] = []
    people = roster(court, settlement)

    for cohort in people.cohorts:
        if cohort.people < 0 or cohort.households < 0:
            found.append(f"{cohort.id}: negative population")
        if cohort.households > cohort.people:
            found.append(
                f"{cohort.id}: {cohort.households} households among "
                f"{cohort.people} people")

    mapped = {entry.group for entry in PLACEMENTS}
    for group_id in sorted(court.dependents):
        if group_id not in mapped:
            found.append(
                f"{group_id}: no kernel cohort is authored for this group")

    # A named person who has ended up in the population. Cannot happen through
    # this module -- `refuse_named` is in the way -- so if it is ever true it was
    # done elsewhere, and rule four of the header is worth checking rather than
    # asserting.
    house = getattr(court, "house", {})
    for member_id in sorted(house):
        for cohort in people.cohorts:
            if cohort.id.split(":")[-1] == member_id:
                found.append(
                    f"{cohort.id}: names {member_id}, who is a person")
        for residue in people.residues:
            if residue.face and residue.face == member_id:
                found.append(
                    f"{residue.cohort}: draws its face from {member_id}, "
                    "who is a named member of the house")

    for formation in sorted(court.formations, key=lambda f: f.id):
        if formation.task == "harvest" and formation.id not in staffed_by:
            found.append(
                f"{formation.id}: reaping, and no line says which people it "
                "is drawn from")

    # The other population. `content/kernel/world.toml` still authors cohorts at
    # the seat from before the court gave it up; both are non-empty, so both are
    # counted, and that is the audit's "ordinary people" row seen from inside.
    if registry is not None:
        ours = {c.id for c in people.cohorts}
        for cohort_id in sorted(registry.cohorts):
            cohort = registry.cohorts[cohort_id]
            if cohort.settlement != settlement or cohort_id in ours:
                continue
            if cohort.people:
                found.append(
                    f"{cohort_id}: {cohort.people} more people at "
                    f"{settlement}, counted by nobody in the court's record")

    try:
        Muster(roster=people).add(*court_draws(court, people, staffed_by))
    except DoubleCount as complaint:
        found.append(str(complaint))
    return tuple(found)
