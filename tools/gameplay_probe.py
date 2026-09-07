#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from belief.project import project
from engine import actions as A, fall, seat
from engine.core import in_range
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tools.balance import _austerity_allocations

SEEDS = (1, 7, 42, 1009, 65537, 271828, 8814402919, 4294967291)
POLICIES = {
    "passive": "leaves authored rations and labour untouched",
    "austerity": "cuts rations to last land revenue and sends hands to harvest when grain is thin",
    "stewardship": "rations against the fortnights the granary can feed, banking a good year to spend through a bad one",
}


def event_name(event) -> str:
    return f"kernel:{event[0]}" if isinstance(event, tuple) and event else type(event).__name__


def _act(policy: str, world) -> tuple:
    """What a court that is paying attention does with its granary.

    `austerity` only reacts once the grain is nearly gone, which is why it
    stopped differing from doing nothing as soon as the seat had reserves: the
    trigger never fired. `stewardship` reads the same figure the Hall now shows
    the player -- how many fortnights the granary feeds the roll -- and rations
    against it, so a good year is banked and a bad one is spent through.
    """
    made: list = []
    roll = seat.groups(world)
    owed = sum(g.size * g.entitlement for g in roll.values())
    if owed <= 0:
        return world, made
    kept = seat.held(world).get("grain", 0) // owed

    if policy == "austerity":
        budget = (world.court.last_land_due // 24
                  if world.court.last_land_due else owed)
        thin = kept < 6
    else:
        # Full rations while a year is banked; three quarters while half a year
        # stands; half when the floor is in sight. Never nothing: a court that
        # feeds nobody is not economising, it is abdicating.
        share = 1000 if kept >= 24 else 750 if kept >= 12 else 500
        budget = owed * share // 1000
        thin = kept < 12

    for action in _austerity_allocations(world, budget):
        world, got = apply(world, action)
        made += got
    harvest = tuple(world.season.get("harvest") or ())
    may_send = bool(harvest) and in_range(
        world.date.advance().fortnight, harvest)
    if thin and may_send:
        for gid in ("weavers", "garrison_mahadu"):
            group = roll.get(gid)
            if group and not group.at_fields:
                world, got = apply(world, A.SendToHarvest(gid, True))
                made += got
    return world, made


def run(policy: str, seed: int, turns: int = 120, *, baseline: bool = False) -> dict:
    world = dataclasses.replace(load_campaign("seat", seed), baseline=baseline)
    opening = {sid: max(1, s.population or world.kernel.people(sid))
               for sid, s in world.kernel.registry.settlements.items()}
    low = dict(opening)
    high_unrest = {sid: 0 for sid in opening}
    events = Counter()
    falls = []
    invalid_cohorts = {}

    for _ in range(turns):
        world, made = advance(world)
        events.update(event_name(event) for event in made)
        falls += [(world.date.absolute, event.alu, event.cause,
                   event.population, event.unrest)
                  for event in made if isinstance(event, A.AluFell)]
        if policy in {"austerity", "stewardship"} and not world.ended:
            world, made = _act(policy, world)
            events.update(event_name(event) for event in made)
        for cohort in world.kernel.registry.cohorts.values():
            if (min(cohort.people, cohort.households, cohort.infected,
                    cohort.recovered, cohort.dead) < 0
                    or cohort.households > cohort.people
                    or cohort.infected + cohort.recovered > cohort.people):
                invalid_cohorts.setdefault(cohort.id, world.date.absolute)
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
    outcomes = set()
    errors = [f"{cid}: invalid population/health at turn {turn}"
              for cid, turn in sorted(invalid_cohorts.items())]
    for sid, start in opening.items():
        alu = sid.split(":", 1)[1]
        row = settlements[sid]
        ratio = low[sid] * 1000 // start
        fallen = getattr(row, "fallen", False)
        if fallen:
            outcomes.add("fall:" + getattr(row, "fall_cause", "unknown"))
            if alu in mapped:
                errors.append(f"{alu}: fallen but still mapped")
            if (world.kernel.owner(sid).seat == sid
                    and world.kernel.king(sid) is not None):
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
    player = settlements[seat_id]
    if world.ended != player.fallen:
        errors.append("player fall and terminal state disagree")
    if player.fallen and (world.ended_turn != player.fell_turn
                          or world.end_reason != f"the Alu fell through {player.fall_cause}"):
        errors.append("player fall and terminal cause/date disagree")
    if world.ended:
        outcomes.add("game over")
    outcomes.update("shock:" + shock.kind for shock in world.shocks)
    return {
        "policy": policy, "seed": seed, "baseline": baseline,
        "turn": world.date.absolute,
        "ended": world.ended, "cause": world.end_reason,
        "outcomes": sorted(outcomes), "errors": errors,
        "events": dict(sorted(events.items())),
        "falls": falls,
        "population_ratio_min": min(
            low[sid] * 1000 // opening[sid] for sid in opening),
        "population": sum(world.kernel.people(sid) for sid in opening),
        "population_opening": sum(opening.values()),
        "seat_population_ratio": world.kernel.people(seat_id) * 1000
        // opening[seat_id],
        "seat_unrest": fall.unrest(world, seat_id),
        "seat_grain": seat.held(world).get("grain", 0),
        "unrest_peak": max(high_unrest.values()),
        "active_alus": sum(not getattr(s, "fallen", False)
                           for s in settlements.values()),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("count", nargs="?", type=int, default=4)
    parser.add_argument("turns", nargs="?", type=int, default=120)
    parser.add_argument("--baseline", action="store_true",
                        help="ordinary climate, no shocks, plague, raids or displacement; falls still resolve")
    parser.add_argument("--policy", choices=POLICIES, action="append")
    args = parser.parse_args(argv[1:])
    if not 1 <= args.count <= len(SEEDS) or args.turns < 1:
        parser.error(f"count must be 1..{len(SEEDS)} and turns must be positive")
    policies = args.policy or tuple(POLICIES)
    for policy in policies:
        print(f"{policy}: {POLICIES[policy]}", flush=True)
    print("baseline: ordinary climate, abnormal shocks disabled, falls enabled"
          if args.baseline else "campaign: authored climate and shocks enabled", flush=True)
    all_events = Counter()
    failed = False
    for policy, seed in ((p, s) for p in policies for s in SEEDS[:args.count]):
        row = run(policy, seed, args.turns, baseline=args.baseline)
        failed |= bool(row["errors"])
        all_events.update(row["events"])
        print(f"{row['policy']:>7} {row['seed']:>10} t={row['turn']:>3} "
              f"pop={row['population_ratio_min']:>4}‰ "
              f"seat={row['seat_population_ratio']:>4}‰/{row['seat_unrest']:>4} "
              f"grain={row['seat_grain']:>7} unrest={row['unrest_peak']:>4} "
              f"alus={row['active_alus']:>2} "
              f"{' | '.join(row['outcomes'])}", flush=True)
        print(f"  world population {row['population_opening']:,} -> {row['population']:,}",
              flush=True)
        if row["falls"]:
            print("  falls", ", ".join(
                f"t{turn}:{alu}:{cause}" for turn, alu, cause, _, _ in row["falls"]))
        for error in row["errors"]:
            print("  ERROR", error)
    print("\nevents:", ", ".join(
        f"{name}={count}" for name, count in sorted(all_events.items())))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
