"""One population at the seat, counted once (spec 2.2, 5.2; Phase C)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine.entity import Cohort, EntityId, mint, mint_all
from engine.state import DependentGroup, HouseMember

GroupId = str

# The settlement the legacy court is the seat of.
SEAT = "settlement:seat"

# Person-days a head can give in a fortnight.
LABOUR_PER_HEAD = 12

# Heads per household.
HEADS_PER_HOUSEHOLD = 5

# Loyalty and grievance are one scale read from opposite ends, so the map is `1000 - x` and nothing.
LOYALTY_SPAN = 1000

# What a cohort calls the work a group does.
KIND_FOR: Mapping[str, str] = {
    "bronze_working": "craft",
    "cult": "cult",
    "field_labour": "field_labour",
    "garrison": "garrison",
    "household": "household",
    "weaving": "craft",
}

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

class Unmapped(KeyError):
    """A body of people no line of the migration map accounts for."""


class NotACohort(TypeError):
    """Something that is a person, or is not people at all."""


class DoubleCount(ValueError):
    """A split tried to create more people than exist."""


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


# --- the two memories (spec 6.3; the authority table's hunger row) ------------


def hunger_of(arrears: int, size: int, entitlement: int) -> tuple[int, int]:
    """`(fortnights hungry, qa that did not divide)`."""
    owed = max(0, size) * max(0, entitlement)
    arrears = max(0, arrears)
    if owed <= 0:
        # Nobody left, or nothing promised.
        return 0, arrears
    return arrears // owed, arrears % owed


def grievance_of(loyalty: int) -> int:
    return _clamp(LOYALTY_SPAN - loyalty)


def loyalty_of(grievance: int) -> int:
    return _clamp(LOYALTY_SPAN - grievance)


def _clamp(x: int, lo: int = 0, hi: int = LOYALTY_SPAN) -> int:
    return lo if x < lo else hi if x > hi else x


# --- conversion ---------------------------------------------------------------

def as_cohort(group: DependentGroup) -> Cohort:
    """Author a dependent group as a cohort."""
    refuse_named(group)
    if not isinstance(group, DependentGroup):
        raise NotACohort(f"{group!r} is not a body of dependent people")
    entry = placement(group.id)
    heads = max(0, group.size)
    households = min(heads, heads // HEADS_PER_HOUSEHOLD) if heads else 0
    if heads and not households:
        households = 1
    hunger, _ = hunger_of(group.arrears, heads, group.entitlement)
    return Cohort(
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
        roll_id=group.id,
        name=group.name,
        representative=group.member_name,
        roll_place=group.place,
        roll_function=group.function,
    )
def as_group(cohort: Cohort) -> DependentGroup:
    """Project a payroll cohort as a court roll entry."""
    refuse_named(cohort)
    group = cohort.roll_id
    if not group:
        raise Unmapped(f"{cohort.id!r} is not on the court roll")
    name = cohort.name
    place = cohort.roll_place
    face = cohort.representative
    function = cohort.roll_function or cohort.kind
    weeks = cohort.shortfall // max(1, cohort.ration())
    _floor, _loyalty, output, _desertion, revolt = band(weeks)
    return DependentGroup(
        id=group,
        name=name,
        size=max(0, cohort.people),
        entitlement=max(0, cohort.ration_per_head),
        function=function,
        place=place,
        arrears=cohort.shortfall,
        loyalty=loyalty_of(cohort.grievance),
        output_modifier=output,
        member_name=face,
        revolting=revolt,
        at_fields=cohort.reaping,
    )


_BANDS = (
    (0, 8, 1000, 0, False),
    (1, -20, 920, 0, False),
    (2, -60, 780, 0, False),
    (4, -140, 520, 30, False),
    (6, -260, 300, 30, False),
    (8, -400, 80, 30, True),
)


def band(weeks: int):
    chosen = _BANDS[0]
    for row in _BANDS:
        if weeks >= row[0]:
            chosen = row
    return chosen


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
    if "/" in cohort.id:
        root = cohort.id.split("/", 1)[0]
        base = int.from_bytes(cohort.id.encode()) * len(keys)
        ids = {key: mint(root, turn, "household", base + i)
               for i, key in enumerate(keys)}
    else:
        ids = mint_all(cohort.id, turn, "household", keys)

    weights = tuple(sorted(
        [(ids[key], asked[key]) for key in keys]
        + [(cohort.id, cohort.people - taken)]))
    caps = {key: heads for key, heads in weights}
    houses = _apportion(cohort.households, weights, caps)
    infected = _apportion(cohort.infected, weights, caps)
    recovered = _apportion(cohort.recovered, weights, caps)
    dead = _apportion(cohort.dead, weights, {})

    parts = [dataclasses.replace(
        cohort, id=ids[key], people=asked[key],
        households=houses[ids[key]],
        infected=infected[ids[key]], recovered=recovered[ids[key]],
        dead=dead[ids[key]],
        # Where they are from, once they are no longer only where they live.
        origin=cohort.origin or cohort.settlement) for key in keys]
    parent = dataclasses.replace(
        cohort, people=cohort.people - taken, households=houses[cohort.id],
        infected=infected[cohort.id], recovered=recovered[cohort.id],
        dead=dead[cohort.id])
    return tuple(sorted([parent] + parts, key=lambda c: c.id))


def merge(cohorts: tuple[Cohort, ...], into: EntityId = "") -> Cohort:
    """Two bodies of people becoming one, conserving people and households."""
    if not cohorts:
        raise ValueError("nothing to merge")
    ordered = tuple(sorted(cohorts, key=lambda c: c.id))
    first = ordered[0]
    for other in ordered[1:]:
        for field in ("settlement", "kind", "ration_per_head",
                      "labour_per_head", "ethnicity", "status",
                      "institution", "armed"):
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
        infected=sum(c.infected for c in ordered),
        recovered=sum(c.recovered for c in ordered),
        dead=sum(c.dead for c in ordered),
        hunger=sum(c.people * c.hunger for c in ordered) // divisor,
        grievance=sum(c.people * c.grievance for c in ordered) // divisor,
        origin=first.origin if all(
            c.origin == first.origin for c in ordered) else "",
    )
