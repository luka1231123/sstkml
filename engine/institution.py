"""Institutions: the city as a machine (spec 6.18, M12).

A dependent group was always an institution. `DependentGroup` (6.3) is not
replaced and not touched -- arrears, loyalty, desertion and the named petitioner
all keep working exactly as they did -- and an `Institution` is a thin layer over
it: a building, a head, a condition, a capacity.

Two multipliers, and neither is announced:

    effective = capacity * condition // 1000 * output_modifier // 1000

`output_modifier` is the staff, and it falls when they go unpaid (6.3, and that
code is unchanged). `condition` is the fabric, and it falls when nobody minds
it. Starving a group used to produce a grudge; starving the harbour stops
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


def _decay_for(court, inst) -> int:
    decay = DECAY.get(inst.kind, 6)
    if not inst.head:
        decay += HEADLESS_DECAY
    if inst.upkeep and not _upkeep_met(court, inst):
        decay += UNPAID_UPKEEP_DECAY
    return decay


def _upkeep_met(court, inst) -> bool:
    return all(court.stores.get(good, 0) >= qty for good, qty in inst.upkeep)


def effective(court, inst) -> int:
    """What it can actually do this fortnight. Derived, never stored."""
    group = court.dependents.get(inst.group)
    staff = group.output_modifier if group is not None else 1000
    return inst.capacity * inst.condition // 1000 * staff // 1000


def reported_condition(court, inst, seed: int, turn: int) -> int:
    """The figure the head puts in his report, which is not the figure.

    A head whose men are in arrears is a head with something to explain, and he
    does not explain it. The overstatement is proportional to what he owes them,
    so the lie grows exactly as the thing being lied about gets worse -- which
    is what makes `inspect` worth an hour precisely when the player can least
    spare one.
    """
    group = court.dependents.get(inst.group)
    if group is None:
        return inst.condition
    owed_per_turn = max(1, group.size * group.entitlement)
    weeks = group.arrears // owed_per_turn
    if weeks < 1:
        return inst.condition
    # Capped: a head who claims a ruin is a palace is a head who gets found out
    # the same fortnight, and nobody in this world is that stupid.
    #
    # Capped below a perfect thousand as well: a head who reports his quay
    # flawless is a head reporting something nobody has ever seen, and the
    # player would learn to read 1000 as a lie. He reports it *nearly* sound.
    flattery = min(300, weeks * 45)
    return min(960, inst.condition + flattery)


def step(world: World) -> tuple[World, list]:
    """A7b: the fabric goes, quietly, whether or not anyone is working."""
    court = world.court
    if not court.institutions:
        return world, []
    events: list = []
    institutions = {}
    history = dict(court.institution_history)
    for key in sorted(court.institutions):
        inst = court.institutions[key]
        condition = max(0, min(1000, inst.condition - _decay_for(court, inst)))
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
            court, institutions=institutions,
            institution_history=history)), events
