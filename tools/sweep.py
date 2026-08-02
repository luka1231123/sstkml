#!/usr/bin/env python3
"""Balance across many seeds (spec 10.4, closing the known gap before M12).

`tools/balance.py` plays one seed and prints a curve. That was enough while
there was one economy; it is not enough now. Every number in the game has been
tuned against seed 8814402919 and therefore against **one climate series** —
one particular run of good and bad years — and a game balanced for one weather
pattern is not balanced.

This plays the same scripted policies over many seeds and reports the *spread*.
What matters is not the median; it is the tails:

* whether austerity conserves stores, and what it costs the dependent groups
  and connected settlements
* a seed where the passive policy never empties the granary is a seed with no
  game in it at all

The distance between them is the design.

    python3 tools/sweep.py [count] [turns]
    python3 tools/sweep.py 40 96 --csv > sweep.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from balance import run                       # noqa: E402

# Authored, not generated: the sweep has to be the same sweep every time it is
# run, or a change in the tables cannot be told from a change in the seeds.
# Spread across the 32-bit range by hand, with the canonical seed first so its
# row can always be compared against the older single-seed reports.
SEEDS = (
    8814402919, 1, 7, 42, 1009, 65537, 271828, 999331,
    3141592653, 1234567890, 88888888, 40404040, 5150, 2718281828,
    777000777, 123454321, 6021023, 31337, 20250727, 4294967291,
    112358132, 998244353, 1000000007, 525600, 8675309, 1618033988,
    141421356, 173205080, 236067977, 449489742, 645751311, 828427124,
)


def metrics(policy: str, seed: int, turns: int) -> dict:
    rows = run(policy, turns, seed)["rows"]
    last = rows[-1]
    harvests = [row["harvest"] for row in rows if row["harvest"]]
    return {
        "seed": seed,
        "empty": next((r["turn"] for r in rows if r["grain"] == 0), 0),
        "maxed": next((r["turn"] for r in rows if r["unrest"] >= 1000), 0),
        "pinched": next((r["turn"] for r in rows if r["chariotry"] < 1000), 0),
        "grain_end": last["grain"],
        "unrest_end": last["unrest"],
        "unrest_peak": max(r["unrest"] for r in rows),
        "chariotry_end": last["chariotry"],
        "melt_share": (last["melt"] * 1000
                       // max(1, last["melt"] + last["circulation"])),
        "harvest_min": min(harvests) if harvests else 0,
        "harvest_max": max(harvests) if harvests else 0,
        "climate_mean": sum(r["climate"] for r in rows) // max(1, len(rows)),
    }


def spread(values: list[int]) -> tuple[int, int, int]:
    """min, median, max. Integers, because everything in this project is."""
    ordered = sorted(values)
    return ordered[0], ordered[len(ordered) // 2], ordered[-1]


def _column(rows: list[dict], key: str, only_nonzero: bool = False) -> list[int]:
    values = [row[key] for row in rows]
    return [v for v in values if v] if only_nonzero else values


def report(policy: str, rows: list[dict], turns: int) -> list[str]:
    """Return the lines of the report, so tests can read it as well as eyes."""
    out = [f"\n  {policy.upper()}  —  {len(rows)} seeds, {turns} turns each\n"]
    out.append(f"  {'seed':>12}{'empty':>7}{'maxed':>7}{'pinched':>9}"
               f"{'grain end':>11}{'unrest':>8}{'peak':>6}{'chariot':>9}"
               f"{'melt‰':>7}")
    for row in sorted(rows, key=lambda r: (r["empty"] or 9999, r["seed"])):
        out.append(
            f"  {row['seed']:>12}{row['empty'] or '-':>7}"
            f"{row['maxed'] or '-':>7}{row['pinched'] or '-':>9}"
            f"{row['grain_end']:>11,}{row['unrest_end']:>8}"
            f"{row['unrest_peak']:>6}{row['chariotry_end']:>9}"
            f"{row['melt_share']:>7}")

    def line(label: str, key: str, only_nonzero: bool = False) -> str:
        values = _column(rows, key, only_nonzero)
        if not values:
            return f"  {label:<26} never, on any seed"
        low, mid, high = spread(values)
        return f"  {label:<26} {low:>10,}  {mid:>10,}  {high:>10,}"

    out.append(f"\n  {'':<26} {'min':>10}  {'median':>10}  {'max':>10}")
    out.append(line("granary first empty", "empty", True))
    out.append(line("unrest first maxed", "maxed", True))
    out.append(line("chariotry first pinched", "pinched", True))
    out.append(line("grain at the end", "grain_end"))
    out.append(line("unrest peak", "unrest_peak"))
    out.append(line("chariotry at the end", "chariotry_end"))
    out.append(line("melted, per thousand", "melt_share"))
    out.append(line("worst harvest", "harvest_min"))
    out.append(line("best harvest", "harvest_max"))

    never_empty = [r["seed"] for r in rows if not r["empty"]]
    starved = [r["seed"] for r in rows if r["maxed"]]
    out.append(f"\n  seeds where the granary never emptied: {len(never_empty)}"
               f" of {len(rows)}")
    out.append(f"  seeds where unrest reached maximum:    {len(starved)}"
               f" of {len(rows)}")
    return out


def main(argv: list[str]) -> int:
    words = [a for a in argv[1:] if not a.startswith("--")]
    count = int(words[0]) if words else 16
    turns = int(words[1]) if len(words) > 1 else 72
    seeds = SEEDS[:count]

    if "--csv" in argv:
        keys = ("policy",) + tuple(metrics("austerity", seeds[0], 4).keys())
        print(",".join(keys))
        for policy in ("passive", "austerity"):
            for seed in seeds:
                row = metrics(policy, seed, turns)
                print(",".join(str(row.get(key, policy)) for key in keys))
        return 0

    for policy in ("passive", "austerity"):
        rows = [metrics(policy, seed, turns) for seed in seeds]
        print("\n".join(report(policy, rows, turns)))
    print("\n  AUSTERITY should conserve stores, with visible social costs.")
    print("  a seed where PASSIVE never empties is a seed with no game in it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
