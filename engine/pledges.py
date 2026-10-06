"""Optional public undertakings, measured against the local court's accounts.

A vow creates no goods and grants no authority. Six fortnightly accounts show
whether the king kept his word; the household remembers the public result.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A, seat

KINDS = frozenset({"bread", "wages", "justice"})


def _rule(world, name: str, default: int) -> int:
    return int(world.protocol_rules.get(f"pledge_{name}", default))


def cooldown(world) -> int:
    """Fortnights before another vow can be declared; active vows block one."""
    current = getattr(world.court, "royal_pledge", None)
    history = getattr(world.court, "pledge_history", ())
    starts = [record.start_turn for record in history]
    if current is not None:
        starts.append(current.start_turn)
    if not starts:
        return 0
    return max(0, max(starts) + _rule(world, "cooldown", 12)
               - world.date.absolute)


def measure(world, kind: str) -> dict:
    """A counted local condition, suitable for the player's own account view."""
    if kind == "bread":
        payroll = sum(group.size * group.entitlement
                      for group in seat.groups(world).values())
        required = payroll * _rule(world, "bread_payrolls", 2)
        observed = seat.available(world).get("grain", 0)
        return {"kept": observed >= required, "observed": observed,
                "required": required,
                "detail": f"{observed:,} qa unreserved; {required:,} qa for two full payrolls"}
    if kind == "wages":
        observed = sum(group.arrears for group in seat.groups(world).values())
        return {"kept": observed == 0, "observed": observed, "required": 0,
                "detail": f"{observed:,} qa ration arrears on the local payroll"}
    if kind == "justice":
        late = sum(petition.waiting > petition.grace
                   for petition in world.court.petitions.values())
        return {"kept": late == 0, "observed": late, "required": 0,
                "detail": f"{late} waiting claims beyond their stated grace"}
    raise ValueError("choose bread, wages, or justice")


def declare(world, action):
    """Record a reviewed vow; it is checked on the next six closing accounts."""
    from engine.state import RoyalPledge

    if not isinstance(action.kind, str) or action.kind not in KINDS:
        raise ValueError("choose bread, wages, or justice")
    if getattr(world.court, "royal_pledge", None) is not None:
        raise ValueError("the current royal pledge must finish first")
    remaining = cooldown(world)
    if remaining:
        raise ValueError(f"another royal pledge may be declared in {remaining} fortnights")
    start = world.date.absolute
    duration = max(1, _rule(world, "duration", 6))
    pledge = RoyalPledge(
        id=f"pledge:{start}:{action.kind}", kind=action.kind,
        start_turn=start, due_turn=start + duration)
    court = dataclasses.replace(world.court, royal_pledge=pledge)
    return dataclasses.replace(world, court=court), [
        A.RoyalPledgeDeclared(pledge.kind, pledge.due_turn)]


def step(world):
    """Check once per closing fortnight; resolve once at the deadline.

    A failed account cannot be erased by a later surplus. The vow remains in
    force until its public deadline, allowing the king to complete the term
    honourably even after losing the promised reward.
    """
    pledge = getattr(world.court, "royal_pledge", None)
    if pledge is None or pledge.status != "active":
        return world, []
    now = world.date.absolute
    if now <= pledge.start_turn + pledge.checked:
        return world, []
    duration = max(1, pledge.due_turn - pledge.start_turn)
    checked = min(duration, now - pledge.start_turn)
    kept = pledge.kept + int(measure(world, pledge.kind)["kept"])
    pledge = dataclasses.replace(pledge, checked=checked, kept=kept)
    if now < pledge.due_turn:
        return dataclasses.replace(
            world, court=dataclasses.replace(world.court, royal_pledge=pledge)), []

    success = pledge.checked == duration and pledge.kept == duration
    pledge = dataclasses.replace(pledge, status="kept" if success else "broken")
    prefix = "success" if success else "failure"
    old = world.court
    legitimacy = max(0, min(1000, old.legitimacy + _rule(
        world, f"{prefix}_legitimacy", 10 if success else -15)))
    unrest = max(0, min(1000, old.unrest + _rule(
        world, f"{prefix}_unrest", -10 if success else 10)))
    history = (getattr(old, "pledge_history", ()) + (pledge,))[
        -max(1, _rule(world, "history_limit", 8)):]
    court = dataclasses.replace(
        old, royal_pledge=None, pledge_history=history,
        legitimacy=legitimacy, unrest=unrest)
    return dataclasses.replace(world, court=court), [A.RoyalPledgeResolved(
        pledge.kind, success, legitimacy - old.legitimacy, unrest - old.unrest)]
