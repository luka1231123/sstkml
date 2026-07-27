"""The bronze chain and the melt ledger (spec 6.5). Graduated from systems.py.

The slow-motion structural failure the player will not notice until it is done.

Tin is the chokepoint. It travels the longest and most fragile route -- the
eastern overland caravan through Mesopotamian middlemen, which in the Ugarit
graph runs Emar -> Mari -> Assur and has the highest risk on the board. Copper
is near, at Alashiya. Losing tin does nothing visible for a long time, because
the workshops go on meeting their demand by melting down what already exists.

The crucial consequence, and the reason this system is in the game:

    **Army strength does not fall. Replacement falls.**

Combat losses stop being replaceable. The player loses the army without ever
losing a battle. The only warning is a monotonically increasing number on a
ledger page nobody reads, labelled `melted to date`.

Nothing here announces anything. No event fires on the threshold crossing, no
warning, no colour. The number sits on the STORES tab among the metals with no
emphasis, and it is the player's job to look.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import Court, MetalState, World


def smelt(copper: int, tin: int, copper_per_tin: int = 9,
          per_batch: int = 10) -> tuple[int, int, int]:
    """Return (bronze, copper_used, tin_used) for spec 6.5's chain:

        bronze_produced = min(copper // 9, tin) * 10

    Nine parts copper to one of tin by weight. The `min` is the whole story: a
    mountain of copper and no tin makes no bronze at all.
    """
    batches = min(copper // max(1, copper_per_tin), tin)
    if batches <= 0:
        return 0, 0, 0
    return batches * per_batch, batches * copper_per_tin, batches


def step(world: World) -> tuple[World, list]:
    """A7: workshops consume inputs, emit outputs, and melt if tin is short."""
    court = world.court
    if not (court.workshops or court.formations):
        return world, []

    rules = world.land_rules
    stores = dict(court.stores)
    events: list = []

    # A workshop crew deep in arrears works less: the bronze chain is not
    # exempt from the payroll, and starving the smiths is another slow way to
    # stop being able to re-equip.
    smith_modifier = 1000
    smith_groups = [court.dependents[w.group_id] for w in court.workshops
                    if w.group_id in court.dependents]
    if smith_groups:
        smith_modifier = min(g.output_modifier for g in smith_groups)
    demand = sum(w.bronze_demand for w in court.workshops) * smith_modifier // 1000
    metals = court.metals

    # 0. Attrition. Bronze in service wears, is lost, is buried with its owner,
    #    goes out as a gift and does not come back. It happens whether or not
    #    anyone is working, and it is the term that makes the workshops worth
    #    paying for.
    #
    #    Without it the system was exactly backwards. Demand is scaled by the
    #    smiths' output_modifier, so starving the smiths -- the obvious low-risk
    #    cut, since smiths do not riot -- collapsed demand to nothing, nothing
    #    was smelted, nothing was melted, and circulation sat at its opening
    #    figure for the whole run. The 32-seed sweep found chariotry ending at a
    #    perfect 1000 on precisely the seeds where the forge went unpaid.
    #    Starving the workshops preserved the army, which is the opposite of 6.5.
    wear = metals.bronze_in_circulation * rules.get(
        "bronze_attrition_per_10000", 0) // 10000
    if wear:
        metals = dataclasses.replace(
            metals, bronze_in_circulation=metals.bronze_in_circulation - wear)

    if demand > 0:
        # 1. Meet demand from finished bronze on hand.
        from_stores = min(demand, stores.get("bronze", 0))
        stores["bronze"] = stores.get("bronze", 0) - from_stores
        shortfall = demand - from_stores

        # 1b. Smelt to cover the rest, but only what is wanted -- smiths make
        #     what the shops need, not everything the metal would allow. The
        #     `min(copper // 9, tin)` is where tin quietly becomes the whole
        #     story: copper sits in the yard and no bronze comes off the fire.
        if shortfall > 0:
            per_batch = rules.get("bronze_per_batch", 10)
            copper_per_tin = rules.get("copper_per_tin", 9)
            wanted_batches = (shortfall + per_batch - 1) // per_batch
            bronze, copper_used, tin_used = smelt(
                min(stores.get("copper", 0), wanted_batches * copper_per_tin),
                min(stores.get("tin", 0), wanted_batches),
                copper_per_tin, per_batch)
            if bronze:
                stores["copper"] = stores.get("copper", 0) - copper_used
                stores["tin"] = stores.get("tin", 0) - tin_used
                used = min(bronze, shortfall)
                stores["bronze"] = stores.get("bronze", 0) + bronze - used
                shortfall -= used
                events.append(A.BronzeSmelted(bronze, copper_used, tin_used))

        # 1c. Whatever the forge actually made goes into service. This is the
        #     only thing that ever puts metal back, and it needs tin, which is
        #     the point of the whole system: new bronze requires the one input
        #     that comes down the longest road.
        # Capped at the ceiling: the forge maintains the kingdom's kit, it does
        # not accumulate a hoard. Growth above what the court has men and uses
        # for would only buy invisible headroom against a collapse that is
        # supposed to arrive on time.
        served = demand - shortfall
        if served:
            ceiling = (metals.in_service_ceiling
                       or metals.bronze_in_circulation + served)
            metals = dataclasses.replace(
                metals, bronze_in_circulation=min(
                    ceiling, metals.bronze_in_circulation + served))

        # 2. Meet whatever remains by melting. This is the quiet part, and the
        #    only thing that ever writes to the melt ledger. Recycled metal
        #    keeps the shops open and adds nothing: what comes off the fire is
        #    what went into it, less the dross, and the ledger is the record of
        #    a court eating its own capital to look busy.
        if shortfall > 0:
            melted = min(shortfall, metals.bronze_in_circulation)
            if melted:
                metals = dataclasses.replace(
                    metals,
                    bronze_in_circulation=metals.bronze_in_circulation - melted,
                    melt_ledger=metals.melt_ledger + melted)
                events.append(A.BronzeMelted(melted, metals.melt_ledger))
        events.append(A.WorkshopDemandMet(demand, from_stores))

    # 3. Formations below their equipment floor cannot re-equip. Strength is
    #    untouched; only the replacement rate moves, and nothing is announced.
    formations = []
    for formation in court.formations:
        if formation.equipment_floor <= 0:
            rate = 1000
        else:
            rate = 1000 * metals.bronze_in_circulation // formation.equipment_floor
            rate = 0 if rate < 0 else 1000 if rate > 1000 else rate
        formations.append(dataclasses.replace(formation, replacement_rate=rate))

    court = dataclasses.replace(
        court, stores=stores, metals=metals, formations=tuple(formations))
    return dataclasses.replace(world, court=court), events
