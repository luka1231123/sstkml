"""The minimum state an Alu needs to take an autonomous turn."""
from __future__ import annotations

from engine.kernel import world as K


def faults(kernel: K.Kernel) -> tuple[str, ...]:
    found: list[str] = []
    for settlement_id in sorted(kernel.registry.settlements):
        if kernel.registry.settlements[settlement_id].fallen:
            continue
        if kernel.king(settlement_id) is None:
            found.append(f"{settlement_id}: no king")
        if not kernel.controller(settlement_id):
            found.append(f"{settlement_id}: no governing organization")
        if not kernel.cohorts_of(settlement_id):
            found.append(f"{settlement_id}: no population cohort")
        ground = tuple(
            site for site in kernel.registry.sites.values()
            if site.settlement == settlement_id
            and site.function in K.FIELD and site.extent > 0)
        if not ground:
            found.append(f"{settlement_id}: no rule-bearing food ground")
    return tuple(found)
