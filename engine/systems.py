"""Simulation systems, merged (spec Part 6). Integer arithmetic only.

Each function is pure: (world/court, ...) -> (new court, [events]). The tick
pipeline (engine/tick.py) sequences them in the one canonical order. Splitting
this into 20 files as the spec's tree suggests buys nothing while the systems
are small; the boundaries that matter (engine vs belief vs ai) are enforced
elsewhere. Systems get promoted to their own module when they earn it.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import in_range
from engine.state import Court, DependentGroup, World

# --- Arrears effect bands (spec 6.3) -----------------------------------------
# (debt_weeks_threshold, loyalty_delta, output_modifier, desertion_per_mille, revolt)
_BANDS = (
    (0,   +8, 1000,   0, False),
    (1,  -20,  920,   0, False),
    (2,  -60,  780,   0, False),
    (4, -140,  520,  30, False),   # desertion begins, 3%/turn
    (6, -260,  300,  30, False),   # function begins to fail
    (8, -400,   80,  30, True),    # flight or revolt
)


def _band(debt_weeks: int):
    chosen = _BANDS[0]
    for band in _BANDS:
        if debt_weeks >= band[0]:
            chosen = band
    return chosen


def _clamp(x: int, lo: int = 0, hi: int = 1000) -> int:
    return lo if x < lo else hi if x > hi else x


# --- A2/A6 (placeholder): estate deliveries ----------------------------------
def add_income(court: Court) -> tuple[Court, list]:
    """Flat estate deliveries. Agriculture (M8) replaces this with real yields."""
    if court.grain_income <= 0:
        return court, []
    stores = dict(court.stores)
    stores["grain"] = stores.get("grain", 0) + court.grain_income
    return dataclasses.replace(court, stores=stores), [A.GrainReceived(court.grain_income)]


# --- A8: rations paid, arrears updated ---------------------------------------
def pay_rations(court: Court) -> tuple[Court, list]:
    events: list = []
    stores = dict(court.stores)
    available = stores.get("grain", 0)
    groups = dict(court.dependents)

    order = list(court.priority)
    order += sorted(g for g in groups if g not in court.priority)

    for gid in order:
        g = groups.get(gid)
        if g is None or g.size <= 0:
            continue
        owed = g.size * g.entitlement
        target = court.allocations.get(gid, owed)   # default: pay the full entitlement
        paid = min(max(0, target), available)
        available -= paid
        arrears = max(0, g.arrears + owed - paid)
        debt_weeks = arrears // max(1, g.size * g.entitlement)
        _, loyalty_delta, out_mod, desertion, revolt = _band(debt_weeks)

        size = g.size
        if desertion:
            size -= size * desertion // 1000
        loyalty = _clamp(g.loyalty + loyalty_delta)

        groups[gid] = dataclasses.replace(
            g, arrears=arrears, loyalty=loyalty,
            output_modifier=out_mod, size=size,
        )
        events.append(A.RationsPaid(gid, owed, paid, arrears, debt_weeks))
        if debt_weeks >= 2 and g.member_name:
            events.append(A.Grumbling(gid, g.member_name, debt_weeks))

    stores["grain"] = available
    return dataclasses.replace(court, stores=stores, dependents=groups), events


# --- A8: spoilage -------------------------------------------------------------
_SPOILAGE_PER_1000 = {"grain": 4, "seed_grain": 4, "oil": 6, "wine": 3}


def spoilage(court: Court) -> tuple[Court, list]:
    events: list = []
    stores = dict(court.stores)
    for good, rate in _SPOILAGE_PER_1000.items():
        stock = stores.get(good, 0)
        loss = stock * rate // 1000     # floor: small stocks never spoil, and that's true
        if loss:
            stores[good] = stock - loss
            events.append(A.Spoiled(good, loss))
    return dataclasses.replace(court, stores=stores), events


# --- A-phase: rites -----------------------------------------------------------
def do_rites(court: Court, fortnight: int) -> tuple[Court, list]:
    events: list = []
    stores = dict(court.stores)
    legitimacy = court.legitimacy
    unrest = court.unrest
    for rite in court.rites:
        if rite.fortnight != fortnight:
            continue
        if all(stores.get(good, 0) >= qty for good, qty in rite.requires):
            for good, qty in rite.requires:
                stores[good] -= qty
            events.append(A.RitePerformed(rite.id, rite.hours, True))
        else:
            legitimacy = _clamp(legitimacy + rite.skip_legitimacy)
            unrest = _clamp(unrest + rite.skip_unrest)
            events.append(A.RiteSkipped(rite.id))
    return dataclasses.replace(court, stores=stores, legitimacy=legitimacy,
                               unrest=unrest), events


# --- A9: unrest recompute -----------------------------------------------------
def recompute_unrest(court: Court) -> tuple[Court, list]:
    """Unrest pulls toward a target set by aggregate arrears, and decays down."""
    total_debt_weeks = 0
    for g in court.dependents.values():
        total_debt_weeks += g.arrears // max(1, g.size * g.entitlement)
    target = _clamp(total_debt_weeks * 60)
    # Move a third of the way toward target each turn: momentum, not a step.
    unrest = court.unrest + (target - court.unrest) // 3
    unrest = _clamp(unrest)
    delta = unrest - court.unrest
    events = [A.UnrestChanged(delta, "arrears")] if delta else []
    return dataclasses.replace(court, unrest=unrest), events


# --- 6.1: the attention budget ------------------------------------------------
def obligatory_rite_hours(court: Court, fortnight: int) -> int:
    return sum(r.hours for r in court.rites if r.fortnight == fortnight)


def attention_available(court: Court, fortnight: int) -> int:
    unrest_tax = min(3, court.unrest // 250)
    hours = court.attention_base - obligatory_rite_hours(court, fortnight) - unrest_tax
    return max(0, hours)


# --- Seasonal flags (spec 3.2) -----------------------------------------------
def sea_open(seasons: dict, fortnight: int) -> bool:
    span = seasons.get("sailing_open")
    return True if span is None else in_range(fortnight, tuple(span))
