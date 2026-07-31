"""A8, as the court did it before the kernel fed the seat (Task 2 C3).

Archived, not called. `engine/seat.py::mirror` is what happens now: the payroll
is a body of cohorts, it eats in `engine.kernel.world._consume` out of the
palace's lots in the Book, and its hunger and grievance are the arrears and the
loyalty below. The band table stayed in `engine/systems.py`, because reading a
debt into an output modifier is still the court's arithmetic and moving a copy
of it into the kernel would be the second authority all over again.

What changed in crossing, and it is not nothing: `allocations` and `priority`
chose who went short first, and the kernel has no such order -- every cohort
reaches for the same store in a fixed sequence and the store runs out where it
runs out. Restoring the choice is a kernel decision, not a court one, and it is
not built. Kept here so the loss is a diff rather than a memory.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import Court
from engine.systems import _band, _clamp


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
            departed = size * desertion // 1000
            size -= departed
            if departed:
                events.append(A.DependentsDeparted(
                    gid, g.place, departed, "ration arrears"))
        loyalty = _clamp(g.loyalty + loyalty_delta)
        revolting = bool(revolt)

        groups[gid] = dataclasses.replace(
            g, arrears=arrears, loyalty=loyalty,
            output_modifier=0 if revolting else out_mod, size=size,
            revolting=revolting,
        )
        events.append(A.RationsPaid(gid, owed, paid, arrears, debt_weeks))
        if revolting != g.revolting:
            events.append(A.GroupRevoltChanged(
                gid, g.place, revolting, size))
        if debt_weeks >= 2 and g.member_name:
            events.append(A.Grumbling(gid, g.member_name, debt_weeks))

    stores["grain"] = available
    return dataclasses.replace(court, stores=stores, dependents=groups), events
