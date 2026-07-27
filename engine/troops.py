"""Troops: where they stand, what they are doing, and who has asked for them.

D25, closing the gap the note there describes. Four tasks (spec 11), and every
one of them is the same men:

    garrison   they hold a place, and count for its defence in full
    watch      they hold a place thinly -- a lookout, not a defence, so half
    harvest    they are in the fields, supplying labour-days like anybody else
    campaign   they are away, answering a summons, and defending nothing

There is no combat resolution here, no unit types, no morale and no terrain,
and D25 says explicitly that none of those are deferred-with-it. What M11 needs
from this module is `garrison_strength(place)` for its raid weighting; what the
harvest needs is `harvest_hands`; what the oath audit needs is
`mustered_for`. That is the whole surface.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import Summons, World

TASKS = ("garrison", "harvest", "campaign", "watch")

# A watch is a few men in a tower who can see a sail coming and cannot do
# anything about it. It is worth something against a raid and it is not worth a
# garrison, so it counts half. Spec 7.2's four men in a tower are the whole
# joke, and they should not read as a defence.
_WATCH_SHARE = 500


def garrison_strength(court, place: str) -> int:
    """Spec 6.13's `garrison_strength[place]`, the term M11 raids read.

    Only men standing at the place and tasked to hold it count. Troops sent to
    the harvest or to a muster in the north are not defending anything, and
    that is the point of being able to order them there.
    """
    return sum(
        formation.strength * (_WATCH_SHARE if formation.task == "watch" else 1000)
        // 1000
        for formation in court.formations
        if formation.place == place and formation.task in ("garrison", "watch")
    )


def mustered_for(court, place: str) -> int:
    """Strength on campaign at `place` -- what answers a summons."""
    return sum(f.strength for f in court.formations
               if f.task == "campaign" and f.place == place)


def harvest_hands(court, per_head: int) -> int:
    """Labour-days from formations ordered to the fields (spec 6.4 line 566).

    A soldier reaps like a man, so the same `labour_days_per_head` applies. He
    is not in arrears and has no `output_modifier`: he is fed out of the
    payroll group he belongs to, and starving him shows up as unrest long
    before it shows up as a short harvest.
    """
    return sum(f.strength * per_head for f in court.formations
               if f.task == "harvest")


def note_summons(world: World) -> tuple[World, list]:
    """Turn this turn's arriving demands into standing summonses (D25).

    The clock starts on arrival, not on reading. An unopened tablet is still a
    demand delivered, and the Great King's clerks date it from the day their
    courier handed it over. A king who leaves the summons on the pile has still
    been summoned, which is the entire argument for reading the pile.
    """
    court = world.court
    now = world.date.absolute
    oaths = {oath.id: oath for oath in world.oaths}
    known = {(record.oath_id, record.called_turn) for record in court.summons}
    new: list[Summons] = []
    events: list = []

    for letter in world.inbox:
        if letter.arrive_turn != now or not letter.summons_oath:
            continue
        oath = oaths.get(letter.summons_oath)
        # A lapsed or dissolved oath summons nobody. When the Great King dies,
        # his demand for men dies with him until his son has been sworn to.
        if oath is None or oath.dissolved or oath.lapsed:
            continue
        for clause in oath.clauses:
            if clause.kind != "provide_troops":
                continue
            args = dict(clause.args)
            within = int(args.get("within", 2))
            record = Summons(
                oath_id=oath.id, place=letter.path[0],
                n=int(args["n"]), called_turn=now, due_turn=now + within)
            if (record.oath_id, record.called_turn) in known:
                continue
            new.append(record)
            events.append(A.SummonsReceived(
                oath.id, record.place, record.n, record.due_turn))

    if not new:
        return world, []
    return dataclasses.replace(
        world, court=dataclasses.replace(
            court, summons=court.summons + tuple(new))), events


def assign(world: World, action) -> tuple[World, list]:
    """ASSIGN_TROOPS (spec 11). One line, one order, no negotiation."""
    if action.task not in TASKS:
        raise ValueError(f"troops cannot be set to: {action.task}")
    place = action.place or world.court.seat
    if place not in world.places:
        raise ValueError(f"unknown place: {place}")
    formations = []
    found = False
    for formation in world.court.formations:
        if formation.id == action.formation_id:
            found = True
            formation = dataclasses.replace(
                formation, task=action.task, place=place)
        formations.append(formation)
    if not found:
        raise ValueError(f"unknown formation: {action.formation_id}")
    return (dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, formations=tuple(formations))),
        [A.TroopsAssigned(action.formation_id, action.task, place)])
