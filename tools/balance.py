#!/usr/bin/env python3
"""Balance harness (spec 10.4). Plays scripted policies and prints the curves.

Two policies, because they answer different questions:

  `passive`  pays every group its full entitlement and never adjusts. This is
             the deficit made visible: how many turns before the granary is
             empty, and what the collapse looks like on the way down.
  `prudent`  cuts the payroll from the bottom of the priority list to fit the
             grain actually coming in. This is the game played competently, and
             it is the run the metal story has to be legible in -- because a
             court in ruins has stopped commissioning bronze, and the point of
             6.5 is that the chain fails while everything looks fine.

Usage:  python3 tools/balance.py [passive|prudent] [turns] [seed]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import actions as A            # noqa: E402
from engine.reduce import apply            # noqa: E402
from engine.tick import advance            # noqa: E402
from load import load_scenario             # noqa: E402


def _prudent_allocations(world, budget: int) -> list:
    """Pay down the priority list until the budget is gone; cut the rest."""
    from engine import seat

    court = world.court
    order = list(seat.order_of_payment(world))
    order += sorted(g for g in court.dependents if g not in order)
    allowances = seat.allowances(world)
    actions, left = [], budget
    for gid in order:
        group = court.dependents[gid]
        owed = group.size * group.entitlement
        give = min(owed, max(0, left))
        left -= give
        if allowances.get(gid, owed) != give:
            actions.append(A.Allocate(gid, give))
    return actions


def run(policy: str = "prudent", turns: int = 72,
        seed: int = 8814402919, scenario: str = "ugarit") -> dict:
    world = load_scenario(scenario, seed)
    rows = []
    for turn in range(1, turns + 1):
        world, events = advance(world)
        court = world.court
        if policy == "prudent":
            # Spend against what the land actually returned last year, not
            # against the entitlement. One-turn lag applies (D3).
            annual = court.last_land_due
            budget = annual // 24
            # A cushion: never spend the granary below one year of seed.
            for action in _prudent_allocations(world, budget):
                world, _ = apply(world, action)
            # Hands to the fields when the granary is thin and the crop is standing.
            if court.stores.get("grain", 0) < annual // 4:
                for gid in ("weavers", "garrison_mahadu"):
                    if gid in court.dependents and not court.dependents[gid].at_fields:
                        world, _ = apply(world, A.SendToHarvest(gid, True))
        court = world.court
        rows.append({
            "turn": turn, "fortnight": world.date.fortnight,
            "climate": world.climate[world.date.absolute],
            "grain": court.stores.get("grain", 0),
            "seed": court.stores.get("seed_grain", 0),
            "tin": court.stores.get("tin", 0),
            "circulation": court.metals.bronze_in_circulation,
            "melt": court.metals.melt_ledger,
            "unrest": court.unrest,
            "chariotry": next(
                (f.replacement_rate for f in court.formations
                 if f.id == "chariotry"), 1000),
            "events": sorted({type(e).__name__ for e in events}
                             & {"Sown", "Harvested", "Threshed", "BronzeMelted"}),
        })
    return {"policy": policy, "rows": rows, "world": world}


def report(result: dict) -> None:
    rows = result["rows"]
    print(f"  policy: {result['policy']}\n")
    print(f"{'t':>4}{'fn':>4}{'clim':>6}{'grain':>10}{'seed':>8}"
          f"{'tin':>6}{'circ':>8}{'melted':>8}{'unrest':>7}{'chariot':>8}  events")
    for row in rows:
        if row["turn"] % 4 and not row["events"]:
            continue
        print(f"{row['turn']:>4}{row['fortnight']:>4}{row['climate']:>6}"
              f"{row['grain']:>10}{row['seed']:>8}"
              f"{row['tin']:>6}{row['circulation']:>8}{row['melt']:>8}"
              f"{row['unrest']:>7}{row['chariotry']:>8}  {','.join(row['events'])}")

    empty = next((r["turn"] for r in rows if r["grain"] == 0), None)
    starved = next((r["turn"] for r in rows if r["unrest"] >= 1000), None)
    pinched = next((r["turn"] for r in rows if r["chariotry"] < 1000), None)
    last = rows[-1]
    print(f"\n  granary first empty:      {empty or 'never'}")
    print(f"  unrest first at maximum:  {starved or 'never'}")
    print(f"  chariotry first pinched:  {pinched or 'never'}")
    print(f"  melted to date at end:    {last['melt']:,} of "
          f"{last['melt'] + last['circulation']:,} ever in circulation")
    print(f"  chariotry replacement:    {last['chariotry']} / 1000")


if __name__ == "__main__":
    policy = sys.argv[1] if len(sys.argv) > 1 else "prudent"
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 72
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 8814402919
    report(run(policy, turns, seed))
