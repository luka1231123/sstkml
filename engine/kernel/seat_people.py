"""One population at the seat, counted once (spec 2.2, 5.2; Phase C)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine.entity import Cohort, EntityId, mint_all
from engine.state import DependentGroup, HouseMember

GroupId = str
PlaceId = str

# The settlement the legacy court is the seat of.
SEAT = "settlement:seat"

# Person-days a head can give in a fortnight.
LABOUR_PER_HEAD = 12

# Heads per household.
HEADS_PER_HOUSEHOLD = 5

# Loyalty and grievance are one scale read from opposite ends, so the map is `1000 - x` and nothing.
LOYALTY_SPAN = 1000

# Fortnights of shortfall at which a body of people stops working.
REVOLT_FORTNIGHTS = 8

# What a cohort calls the work a group does.
KIND_FOR: Mapping[str, str] = {
    "bronze_working": "craft",
    "cult": "cult",
    "field_labour": "field_labour",
    "garrison": "garrison",
    "household": "household",
    "weaving": "craft",
}

# What a draw on a body of people can be for.
DRAWS = ("food", "work")

# Who is doing the feeding, spelled out, because the double-feed is invisible unless both payers.
BY_COURT = "court:rations"
BY_KERNEL = "kernel:consumption"


@dataclasses.dataclass(frozen=True)
class Placement:
    """One authored line of the migration map: this group is that cohort."""
    group: GroupId
    cohort: EntityId
    settlement: EntityId


# The map, authored rather than derived.
PLACEMENTS: tuple[Placement, ...] = (
    Placement("cult_baal", "cohort:ugarit_temple_servants", SEAT),
    Placement("field_hands", "cohort:ugarit_field_hands", SEAT),
    Placement("garrison_mahadu", "cohort:mahadu_garrison", SEAT),
    Placement("household", "cohort:ugarit_household", SEAT),
    Placement("smiths_palace", "cohort:ugarit_smiths", SEAT),
    Placement("weavers", "cohort:ugarit_weavers", SEAT),
)

# Which body of people a formation's men are counted among.
STAFFED_BY: Mapping[str, GroupId] = {}


class Unmapped(KeyError):
    """A body of people no line of the migration map accounts for."""


class NotACohort(TypeError):
    """Something that is a person, or is not people at all."""


class DoubleCount(ValueError):
    """A head fed twice, or a person-day spent twice (spec 2.2)."""


@dataclasses.dataclass(frozen=True)
class Residue:
    """What one side of the seam records and the other has no field for."""
    group: GroupId
    cohort: EntityId
    name: str = ""
    place: PlaceId = ""
    function: str = ""
    households: int = 0
    # Qa of unpaid ration below one whole fortnight of it.
    arrears_qa: int = 0
    # The court's own note that it is derived and cached (`state.py`).
    output_modifier: int = 1000
    revolting: bool = False
    # The face of a cut (spec 6.3).
    face: str = ""


def refuse_named(who: object) -> None:
    """Rule four, in one call."""
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


def hunger_of(arrears: int, size: int, entitlement: int) -> tuple[int, int]:
    """`(fortnights hungry, qa that did not divide)`."""
    owed = max(0, size) * max(0, entitlement)
    arrears = max(0, arrears)
    if owed <= 0:
        # Nobody left, or nothing promised.
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


def _clamp(x: int, lo: int = 0, hi: int = LOYALTY_SPAN) -> int:
    return lo if x < lo else hi if x > hi else x


# --- conversion ---------------------------------------------------------------

def as_cohort(group: DependentGroup,
              previous: Residue | None = None) -> tuple[Cohort, Residue]:
    """A dependent group as a cohort, plus what a cohort cannot hold."""
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
        # A dependent group owns no grain; it is fed by the body above it.
        tenure="redistributive",
    )
    residue = Residue(
        group=group.id, cohort=entry.cohort, name=group.name,
        place=group.place, function=group.function, households=households,
        arrears_qa=remainder, output_modifier=group.output_modifier,
        revolting=group.revolting, face=group.member_name)
    return cohort, residue


def as_group(cohort: Cohort, residue: Residue) -> DependentGroup:
    """A cohort as the dependent group it came from."""
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
    """One settlement's ordinary people, however the two sides record them."""
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
    """Every dependent group at one settlement, as that settlement's people."""
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
    """Divide `total` by weight, exactly, capped, in sorted key order."""
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
    """Send parts of a cohort somewhere, conserving people and households."""
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
    """Two bodies of people becoming one, conserving people and households."""
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
    """Every head at a place, and what each one is already spoken for."""
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


def _corvee_of(people: Roster) -> tuple[tuple[GroupId, int], ...]:
    """This season's corvée, per group, off the cohorts that owe it."""
    found = []
    for residue in people.residues:
        cohort = people.cohort(residue.cohort)
        if cohort is not None and cohort.corvee:
            found.append((residue.group, cohort.corvee))
    return tuple(sorted(found))


def court_draws(court, people: Roster,
                staffed_by: Mapping[str, GroupId] = STAFFED_BY,
                ) -> tuple[Draw, ...]:
    """Everything the court already spends these heads on, in one ledger."""
    draws: list[Draw] = []
    for residue in sorted(people.residues, key=lambda r: r.cohort):
        group = court.dependents.get(residue.group)
        if group is None or group.size <= 0:
            continue
        draws.append(Draw(residue.cohort, "food", BY_COURT, group.size))

    by_group = {r.group: r.cohort for r in people.residues}
    for group_id in sorted(court.dependents):
        group = court.dependents[group_id]
        cohort_id = by_group.get(group_id)
        if cohort_id is None or not group.at_fields or group.size <= 0:
            continue
        draws.append(Draw(cohort_id, "work", "reap", group.size))

    for group_id, days in sorted(_corvee_of(people)):
        cohort_id = by_group.get(group_id)
        if cohort_id is None or days <= 0:
            continue
        # Days back into heads, rounding up: a corvée of one day off eleven men still had eleven.
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
    """The court's fortnight as one ledger over one population."""
    people = roster(court, settlement)
    return Muster(roster=people).add(
        *court_draws(court, people, staffed_by))


# --- faults (spec 11.1's habit, applied to the seam) --------------------------

def faults(court, settlement: EntityId = SEAT, registry=None,
           staffed_by: Mapping[str, GroupId] = STAFFED_BY) -> tuple[str, ...]:
    """Everything wrong at this seam, as sentences."""
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

    # A named person who has ended up in the population.
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

    # The other population.
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
