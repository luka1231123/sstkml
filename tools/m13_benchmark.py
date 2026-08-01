#!/usr/bin/env python3
"""Pinned M13 foundation benchmark.

This is a diagnostic budget, not a microbenchmark contest.  It runs the same
unattended campaign every time and reports cumulative turn time, canonical
state size, archive growth, and hash cost.  M13 features must keep this report
visible rather than discovering quadratic history handling after the world has
already been multiplied by forty settlements.

    python3 tools/m13_benchmark.py
    python3 tools/m13_benchmark.py --turns 240 --json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.core import canonical_json, state_hash  # noqa: E402
from engine.tick import advance                     # noqa: E402
from load import load_campaign                       # noqa: E402

SEED = 8814402919
DEFAULT_TURNS = 240
FOUNDATION_BUDGET = {
    # Deliberately generous across development machines.  These are tripwires
    # for accidental superlinear work, not claims about final M13 scale.
    # Re-pinned after the kernel belief ledger (73 orgs, ~19 claims each per
    # turn) landed: measured at 240 turns is ~25 s advance, ~2.1 s hash,
    # ~112 MB canonical.  The 2.5x headroom keeps superlinear regressions
    # visible without tripping on the linear journal.
    "advance_ns": 60_000_000_000,
    "hash_ns": 5_000_000_000,
    "canonical_bytes": 300_000_000,
    "documents": 1_100,
}


def measure(turns: int = DEFAULT_TURNS, seed: int = SEED,
            chosen_alu: str = "seat") -> dict[str, int]:
    world = load_campaign(chosen_alu, seed)
    started = time.perf_counter_ns()
    for _ in range(turns):
        world, _events = advance(world)
    advance_ns = time.perf_counter_ns() - started

    encoded = canonical_json(world).encode()
    hash_started = time.perf_counter_ns()
    state_hash(world)
    hash_ns = time.perf_counter_ns() - hash_started
    return {
        "turns": turns,
        "advance_ns": advance_ns,
        "advance_ns_per_turn": advance_ns // max(1, turns),
        "hash_ns": hash_ns,
        "canonical_bytes": len(encoded),
        "inbox_letters": len(world.inbox),
        "documents": len(world.documents),
        "scheduled": len(world.schedule),
    }


def over_budget(result: dict[str, int]) -> dict[str, tuple[int, int]]:
    return {
        key: (result[key], limit)
        for key, limit in FOUNDATION_BUDGET.items()
        if result[key] > limit
    }


def main(argv: list[str]) -> int:
    turns = DEFAULT_TURNS
    for index, arg in enumerate(argv[1:]):
        if arg == "--turns" and index + 2 < len(argv):
            turns = int(argv[index + 2])
        elif arg.startswith("--turns="):
            turns = int(arg.split("=", 1)[1])
    result = measure(turns)
    excess = over_budget(result) if turns == DEFAULT_TURNS else {}
    if "--json" in argv:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"M13 foundation · {result['turns']} turns")
        print(f"  advance/turn      {result['advance_ns_per_turn'] / 1e6:8.3f} ms")
        print(f"  one state hash    {result['hash_ns'] / 1e6:8.3f} ms")
        print(f"  canonical state   {result['canonical_bytes'] / 1024:8.1f} KiB")
        print(f"  inbox/documents   {result['inbox_letters']} / "
              f"{result['documents']}")
        print(f"  scheduled         {result['scheduled']}")
        if excess:
            for key, (actual, limit) in excess.items():
                print(f"  OVER BUDGET       {key}: {actual} > {limit}")
    return 1 if excess else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
