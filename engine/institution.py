"""Institutions: the city as a machine (spec 6.18, M12).

A dependent group was always an institution. `DependentGroup` (6.3) is not
replaced and not touched -- arrears, loyalty, desertion and the named petitioner
all keep working exactly as they did -- and an `Institution` is a thin layer over
it: a building, a head, a condition, a capacity.

Three multipliers, and none is announced:

    effective = capacity
              * condition
              * staff_available
              * head_factor

`staff_available` combines headcount with the group's `output_modifier`, which
falls when they go unpaid (6.3). A group sent to the harvest is unavailable to
its ordinary institution. `condition` is the fabric, and it falls when nobody
minds it. Starving a group used to produce a grudge; starving the harbour stops
clearing ships, and the tin does not arrive, and no letter explains why.

**The head reports his own condition.** That is where the three layers of number
(D11) reach the city: a harbourmaster six fortnights in arrears writes that the
quay is sound, because the alternative is explaining why it is not. `inspect`
costs an hour and returns the truth. Otherwise the player finds out when a ship
he was counting on does not clear.

Nothing here warns. The condition is on the CITY screen for anyone who looks,
exactly as the melt ledger is on STORES (D19).
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import World

# How fast the fabric goes, per fortnight, by kind. Mudbrick and timber in a wet
# coastal climate: a quay takes the worst of it, a wall the least, and an
# archive is only shelves in a dry room.
#
# The scale is the whole balance of the system and the first pass had it an
# order of magnitude wrong: at 12 a fortnight the walls of Ugarit were rubble
# inside two years and the player could do nothing about it. These are set so
# that a *minded* institution loses roughly a third of its condition over a
# hundred turns -- noticeable, worth repairing, never a countdown -- and a
# vacant one loses about twice that.
DECAY = {
    "harbour": 3, "canal": 3, "workshop": 2, "granary": 2,
    "temple": 2, "road": 2, "walls": 1, "archive": 1, "household": 2,
    "garrison": 2,
}

UNPAID_UPKEEP_DECAY = 2      # the fabric goes first when the goods stop
HEADLESS_DECAY = 3           # nobody is minding it

# An Institution predates an authored `required_staff` field.  Until the world
# schema can carry that number, these are the opening city's staffing norms:
# (heads needed, capacity represented by those heads).  The important invariant
# is not the exact norm; it is that losing ninety of a hundred workers can no
# longer leave output unchanged.
_STAFFING_NORMS = {
    "harbour": (60, 1000),
    "granary": (120, 1000),
    "workshop": (140, 600),
    "temple": (80, 1000),
    "walls": (120, 1000),
    "archive": (30, 1000),
    "canal": (100, 1000),
    "road": (100, 1000),
    "household": (120, 1000),
    "garrison": (60, 1000),
}

# An empty authored post/group represents the residual keepers and casual
# labour that kept a neglected Bronze Age building limping along; it is not a
# free perfect workforce. A named group that has actually fallen to zero still
# contributes zero.
HEADLESS_OUTPUT = 700
UNASSIGNED_STAFF_OUTPUT = 700


def head_person(court, inst):
    return court.house.get(inst.head)


def _head_factor(court, inst) -> int:
    """A mediocre unknown incumbent preserves old scenario balance.

    Bad appointments reduce output; very able ones instead earn their advantage
    by slowing decay, because capacity is what the institution can do whole.
    """
    if not inst.head:
        return HEADLESS_OUTPUT
    person = head_person(court, inst)
    competence = person.competence if person is not None else 500
    return min(1000, 750 + competence // 2)


def _staff_factor(court, inst) -> int:
    """0..1000 labour available to this institution this fortnight.

    A payroll modifier describes willingness and arrears, not how many workers
    remain.  Both matter.  A group ordered to the fields is still present and
    still owed rations, but supplies no labour to its ordinary institution.
    """
    if inst.capacity <= 0:
        return 0
    group = court.dependents.get(inst.group)
    if not inst.group:
        return UNASSIGNED_STAFF_OUTPUT
    if (group is None or group.size <= 0 or group.revolting
            or inst.group in court.at_harvest):
        return 0
    heads, reference_capacity = _STAFFING_NORMS.get(
        inst.kind, (100, 1000))
    required = max(
        1,
        (inst.capacity * heads + reference_capacity - 1)
        // reference_capacity,
    )
    quantity = min(1000, group.size * 1000 // required)
    willingness = max(0, min(1000, group.output_modifier))
    return quantity * willingness // 1000


def _decay_for(court, inst, *, upkeep_met: bool | None = None) -> int:
    decay = DECAY.get(inst.kind, 6)
    if not inst.head:
        decay += HEADLESS_DECAY
    else:
        person = head_person(court, inst)
        competence = person.competence if person is not None else 500
        if competence >= 800:
            decay = max(1, decay // 2)
        elif competence < 300:
            decay *= 2
    if upkeep_met is None:
        upkeep_met = _upkeep_met(court, inst)
    if inst.upkeep and not upkeep_met:
        decay += UNPAID_UPKEEP_DECAY
    return decay


def _upkeep_required(inst) -> dict[str, int]:
    required: dict[str, int] = {}
    for good, qty in inst.upkeep:
        if qty > 0:
            required[good] = required.get(good, 0) + qty
    return required


def _upkeep_met(court, inst) -> bool:
    return all(
        court.stores.get(good, 0) >= qty
        for good, qty in _upkeep_required(inst).items())


def _consume_upkeep(stores: dict[str, int], inst) -> bool:
    """Consume one institution's upkeep atomically.

    Checking without deducting allowed every institution to spend the same jug
    of oil.  Partial payment is no better: it destroys goods while still
    producing the unpaid-upkeep result.  An institution therefore consumes its
    complete requirement once, or consumes nothing.
    """
    required = _upkeep_required(inst)
    if not all(stores.get(good, 0) >= qty
               for good, qty in required.items()):
        return not required
    for good, qty in required.items():
        stores[good] = stores.get(good, 0) - qty
    return True


def effective(court, inst) -> int:
    """What it can actually do this fortnight. Derived, never stored."""
    staff = _staff_factor(court, inst)
    return (inst.capacity * inst.condition // 1000 * staff // 1000
            * _head_factor(court, inst) // 1000)


def factor(court, kind: str) -> int:
    """0..1000: how well the city's institution of this kind is working.

    The multipliers folded into one number, for the systems that consume it.
    No building or capacity means no output. Vacant posts and unassigned crews
    limp along at an explicit degraded factor; they no longer default to a
    perfect 1000. Absence used to make missing infrastructure strictly better
    than a neglected building.
    """
    return factor_at(court, kind)


def factor_at(court, kind: str, place: str | None = None) -> int:
    """Working factor for a kind, optionally at one physical place."""
    matching = sorted((
        inst for inst in court.institutions.values()
        if inst.kind == kind and (place is None or inst.place == place)
    ), key=lambda item: item.id)
    if not matching:
        return 0
    inst = matching[0]
    staff = _staff_factor(court, inst)
    return max(0, min(
        1000, inst.condition * staff // 1000
        * _head_factor(court, inst) // 1000))


def reported_condition(court, inst, seed: int, turn: int) -> int:
    """The figure the head puts in his report, which is not the figure.

    A head whose men are in arrears is a head with something to explain, and he
    does not explain it. The overstatement is proportional to what he owes them,
    so the lie grows exactly as the thing being lied about gets worse -- which
    is what makes `inspect` worth an hour precisely when the player can least
    spare one.
    """
    group = court.dependents.get(inst.group)
    weeks = 0
    if group is not None:
        owed_per_turn = max(1, group.size * group.entitlement)
        weeks = group.arrears // owed_per_turn
    person = head_person(court, inst)
    loyalty = person.loyalty if person is not None else 700
    disloyal_flattery = max(0, 700 - loyalty) // 2
    if weeks < 1 and not disloyal_flattery:
        return inst.condition
    # Capped: a head who claims a ruin is a palace is a head who gets found out
    # the same fortnight, and nobody in this world is that stupid.
    #
    # Capped below a perfect thousand as well: a head who reports his quay
    # flawless is a head reporting something nobody has ever seen, and the
    # player would learn to read 1000 as a lie. He reports it *nearly* sound.
    flattery = min(300, weeks * 45 + disloyal_flattery)
    return min(960, inst.condition + flattery)


def step(world: World) -> tuple[World, list]:
    """A7b: the fabric goes, quietly, whether or not anyone is working."""
    court = world.court
    if not court.institutions:
        return world, []
    events: list = []
    institutions = {}
    history = dict(court.institution_history)
    stores = dict(court.stores)
    for key in sorted(court.institutions):
        inst = court.institutions[key]
        upkeep_met = _consume_upkeep(stores, inst)
        if upkeep_met:
            events.extend(
                A.InstitutionUpkeepConsumed(inst.id, good, qty)
                for good, qty in sorted(_upkeep_required(inst).items())
            )
        condition = max(0, min(
            1000,
            inst.condition - _decay_for(
                court, inst, upkeep_met=upkeep_met),
        ))
        if condition != inst.condition:
            events.append(A.InstitutionDecayed(inst.id, condition))
        inst = dataclasses.replace(inst, condition=condition)
        institutions[key] = inst
        # What he says this fortnight, kept for the shape it makes. A head deep
        # in arrears draws a reassuringly level line over a building that is
        # quietly going, and that line is the tell -- not any number on it.
        said = reported_condition(court, inst, world.seed, world.date.absolute)
        history[key] = (history.get(key, ()) + (said,))[-24:]
    return dataclasses.replace(
        world, court=dataclasses.replace(
            court, stores=stores, institutions=institutions,
            institution_history=history)), events
