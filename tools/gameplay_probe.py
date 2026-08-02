#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from belief.project import project
from engine import actions as A, fall, seat
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tools.balance import _austerity_allocations

SEEDS = (1, 7, 42, 1009, 65537, 271828, 8814402919, 4294967291)
POLICIES = {
    "passive": "leaves authored rations and labour untouched",
    "austerity": "cuts rations to last land revenue and sends hands to harvest when grain is thin",
}


def event_name(event) -> str:
    return f"kernel:{event[0]}" if isinstance(event, tuple) and event else type(event).__name__


def run(policy: str, seed: int, turns: int = 120) -> dict:
    world = load_campaign("seat", seed)
    opening = {sid: max(1, s.population or world.kernel.people(sid))
               for sid, s in world.kernel.registry.settlements.items()}
    low = dict(opening)
    high_unrest = {sid: 0 for sid in opening}
    events = Counter()
    falls = []

    for _ in range(turns):
        world, made = advance(world)
        events.update(event_name(event) for event in made)
        falls += [(world.date.absolute, event.alu, event.cause,
                   event.population, event.unrest)
                  for event in made if isinstance(event, A.AluFell)]
        if policy == "austerity" and not world.ended:
            budget = (world.court.last_land_due // 24
                      if world.court.last_land_due else sum(
                          g.size * g.entitlement for g in seat.groups(world).values()))
            for action in _austerity_allocations(world, budget):
                world, made = apply(world, action)
                events.update(event_name(event) for event in made)
            if seat.held(world).get("grain", 0) < world.court.last_land_due // 4:
                for gid in ("weavers", "garrison_mahadu"):
                    group = seat.groups(world).get(gid)
                    if group and not group.at_fields:
                        world, made = apply(world, A.SendToHarvest(gid, True))
                        events.update(event_name(event) for event in made)
        for sid in opening:
            low[sid] = min(low[sid], world.kernel.people(sid))
            cohorts = tuple(c for c in world.kernel.cohorts_of(sid)
                            if not c.in_transit)
            people = sum(c.people for c in cohorts)
            high_unrest[sid] = max(
                high_unrest[sid],
                sum(c.people * c.grievance for c in cohorts) // max(1, people))
        if world.ended:
            break

    settlements = world.kernel.registry.settlements
    seat_id = "settlement:seat"
    mapped = {row["id"] for row in project(world)["world_graph"]["places"]}
    outcomes, errors = set(), []
    for sid, start in opening.items():
        alu = sid.split(":", 1)[1]
        row = settlements[sid]
        ratio = low[sid] * 1000 // start
        fallen = getattr(row, "fallen", False)
        if fallen:
            outcomes.add("fall:" + getattr(row, "fall_cause", "unknown"))
            if alu in mapped:
                errors.append(f"{alu}: fallen but still mapped")
            if world.kernel.king(sid) is not None:
                errors.append(f"{alu}: fallen with a living ruler")
        elif ratio <= fall.POPULATION_FLOOR:
            outcomes.add("unresolved population collapse")
            errors.append(f"{alu}: active below the population floor")
        elif high_unrest[sid] >= 1000:
            outcomes.add("unresolved maximum unrest")
        elif ratio <= 600:
            outcomes.add("population crisis")
        else:
            outcomes.add("survived")
        if world.kernel.people(sid) < 0:
            errors.append(f"{alu}: negative population")
    if world.ended:
        outcomes.add("game over")
    outcomes.update("shock:" + shock.kind for shock in world.shocks)
    return {
        "policy": policy, "seed": seed, "turn": world.date.absolute,
        "ended": world.ended, "cause": world.end_reason,
        "outcomes": sorted(outcomes), "errors": errors,
        "events": dict(sorted(events.items())),
        "falls": falls,
        "population_ratio_min": min(
            low[sid] * 1000 // opening[sid] for sid in opening),
        "seat_population_ratio": world.kernel.people(seat_id) * 1000
        // opening[seat_id],
        "seat_unrest": fall.unrest(world, seat_id),
        "seat_grain": seat.held(world).get("grain", 0),
        "unrest_peak": max(high_unrest.values()),
        "active_alus": sum(not getattr(s, "fallen", False)
                           for s in settlements.values()),
    }


def main(argv: list[str]) -> int:
    count = int(argv[1]) if len(argv) > 1 else 4
    turns = int(argv[2]) if len(argv) > 2 else 120
    rows = [run(policy, seed, turns)
            for policy in ("passive", "austerity") for seed in SEEDS[:count]]
    for policy, meaning in POLICIES.items():
        print(f"{policy}: {meaning}")
    all_events = Counter()
    for row in rows:
        all_events.update(row["events"])
        print(f"{row['policy']:>7} {row['seed']:>10} t={row['turn']:>3} "
              f"pop={row['population_ratio_min']:>4}‰ "
              f"seat={row['seat_population_ratio']:>4}‰/{row['seat_unrest']:>4} "
              f"grain={row['seat_grain']:>7} unrest={row['unrest_peak']:>4} "
              f"alus={row['active_alus']:>2} "
              f"{' | '.join(row['outcomes'])}")
        if row["falls"]:
            print("  falls", ", ".join(
                f"t{turn}:{alu}:{cause}" for turn, alu, cause, _, _ in row["falls"]))
        for error in row["errors"]:
            print("  ERROR", error)
    print("\nevents:", ", ".join(
        f"{name}={count}" for name, count in sorted(all_events.items())))
    return int(any(row["errors"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
