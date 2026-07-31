#!/usr/bin/env python3
"""M13.0 material and causal audit for the current one-city world.

The audit is intentionally independent of the renderer and Belief.  It advances
World, compares material snapshots, and reconciles each changed stock with the
structured events emitted by the engine.  It is a foundation harness, not the
M13.1 multi-settlement conservation ledger.

Usage:

    python3 tools/m13_audit.py
    python3 tools/m13_audit.py --turns 96 --json
"""
from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import actions as A  # noqa: E402
from engine.tick import advance  # noqa: E402
from load import load_scenario    # noqa: E402

SEED = 8814402919
DEFAULT_TURNS = 96


@dataclasses.dataclass(frozen=True)
class Snapshot:
    stores: dict[str, int]
    bronze_service: int
    bronze_melted: int
    populations: dict[str, tuple[int, int, int, int, int]]
    dependents: dict[str, tuple[str, int, bool]]
    formations: dict[str, tuple[int, int, int]]
    cargo: dict[str, tuple[str, str, str, int]]
    corvee_days: int
    works_days: int
    corvee_sources: dict[str, int]


@dataclasses.dataclass(frozen=True)
class Finding:
    turn: int
    path: str
    actual: int
    explained: int
    evidence: tuple[str, ...]


def snapshot(world) -> Snapshot:
    return Snapshot(
        stores=dict(world.court.stores),
        bronze_service=world.court.metals.bronze_in_circulation,
        bronze_melted=world.court.metals.melt_ledger,
        populations={
            place_id: (
                place.population, place.susceptible, place.infected,
                place.recovered, place.dead)
            for place_id, place in sorted(world.places.items())
        },
        dependents={
            group_id: (group.place, group.size, group.revolting)
            for group_id, group in sorted(world.court.dependents.items())
        },
        formations={
            formation.id: (
                formation.strength, formation.ready, formation.replacement_rate)
            for formation in world.court.formations
        },
        cargo={
            lot_id: (lot.owner, lot.place, lot.good, lot.quantity)
            for lot_id, lot in sorted(world.harbour_cargo.items())
        },
        corvee_days=world.court.corvee_days,
        works_days=world.court.works_days,
        corvee_sources=dict(world.court.corvee_sources),
    )


def _delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {
        key: after.get(key, 0) - before.get(key, 0)
        for key in sorted(set(before) | set(after))
        if after.get(key, 0) != before.get(key, 0)
    }


def _store_explanation(before_world, before: Snapshot, after: Snapshot,
                       events: list) -> tuple[Counter, dict[str, list[str]]]:
    expected: Counter[str] = Counter()
    evidence: dict[str, list[str]] = {}

    def add(good: str, amount: int, reason: str) -> None:
        if not amount:
            return
        expected[good] += amount
        evidence.setdefault(good, []).append(reason)

    smelted = 0
    workshop_demand = 0
    workshop_from_stores = 0
    for event in events:
        name = type(event).__name__
        if isinstance(event, A.Spoiled):
            add(event.good, -event.amount, name)
        elif isinstance(event, A.RationsPaid):
            add("grain", -event.paid, name)
        elif isinstance(event, A.HarbourDueTaken):
            if event.taken and event.lot_id and event.owner and event.cleared:
                add(event.good, event.taken, f"{name}:{event.lot_id}")
        elif isinstance(event, A.GiftSent):
            add(event.good, -event.quantity, name)
        elif isinstance(event, A.CargoLanded):
            # It left a foreign granary on a recorded turn; the reservation it
            # settles is the other half of the entry.
            add(event.good, event.quantity, f"{name}:{event.record_id}")
        elif isinstance(event, A.SeedEaten):
            add("seed_grain", -event.amount, name)
            add("grain", event.amount, name)
        elif isinstance(event, A.OathExpiated):
            add("grain", -event.offering, name)
        elif isinstance(event, A.OfferingConsumed):
            add(event.good, -event.amount, name)
        elif isinstance(event, A.InstitutionUpkeepConsumed):
            add(event.good, -event.amount, name)
        elif isinstance(event, A.WorkMaterialConsumed):
            add(event.good, -event.amount, name)
        elif isinstance(event, A.BronzeSmelted):
            smelted += event.bronze
            add("copper", -event.copper_used, name)
            add("tin", -event.tin_used, name)
        elif isinstance(event, A.WorkshopDemandMet):
            workshop_demand += event.demand
            workshop_from_stores += event.from_stores
        elif isinstance(event, A.RitePerformed):
            rite = next(
                (rite for rite in before_world.court.rites
                 if rite.id == event.rite_id), None)
            if rite is not None:
                for good, quantity in rite.requires:
                    add(good, -quantity, f"{name}:{event.rite_id}")

    if workshop_from_stores:
        add("bronze", -workshop_from_stores, "WorkshopDemandMet")
    if smelted:
        used_new = min(
            smelted, max(0, workshop_demand - workshop_from_stores))
        add("bronze", smelted - used_new, "BronzeSmelted:surplus")
    return expected, evidence


def audit_transition(before_world, after_world, events: list) -> list[Finding]:
    """Return every unexplained or invalid material change."""
    turn = after_world.date.absolute
    before, after = snapshot(before_world), snapshot(after_world)
    findings: list[Finding] = []

    for key, value in after.stores.items():
        if value < 0:
            findings.append(Finding(
                turn, f"stores.{key}", value, 0, ("non-negative stock",)))

    expected, evidence = _store_explanation(
        before_world, before, after, events)
    actual = _delta(before.stores, after.stores)
    for good in sorted(set(actual) | set(expected)):
        got, explained = actual.get(good, 0), expected.get(good, 0)
        if got != explained:
            findings.append(Finding(
                turn, f"stores.{good}", got, explained,
                tuple(evidence.get(good, ())) or ("no material event",)))

    worn = sum(event.amount for event in events
               if isinstance(event, A.BronzeWorn))
    melted = sum(event.amount for event in events
                 if isinstance(event, A.BronzeMelted))
    produced = sum(event.bronze for event in events
                   if isinstance(event, A.BronzeSmelted))
    demands = [event for event in events
               if isinstance(event, A.WorkshopDemandMet)]
    served = sum(
        event.from_stores + min(
            produced, max(0, event.demand - event.from_stores))
        for event in demands)
    service_after_wear = before.bronze_service - worn
    ceiling = (before_world.court.metals.in_service_ceiling
               or service_after_wear + served)
    expected_service = min(
        ceiling, service_after_wear + served) - melted
    service_actual = after.bronze_service - before.bronze_service
    service_explained = expected_service - before.bronze_service
    if service_actual != service_explained:
        findings.append(Finding(
            turn, "metal.bronze_in_service", service_actual,
            service_explained,
            tuple(type(event).__name__ for event in events
                  if isinstance(event, (
                      A.BronzeWorn, A.BronzeMelted, A.BronzeSmelted,
                      A.WorkshopDemandMet))) or ("no bronze event",)))
    melt_actual = after.bronze_melted - before.bronze_melted
    if melt_actual != melted:
        findings.append(Finding(
            turn, "metal.melt_ledger", melt_actual, melted,
            ("BronzeMelted",)))

    cargo_expected: Counter[str] = Counter()
    for event in events:
        if isinstance(event, A.HarbourDueTaken) and event.cleared:
            cargo_expected[event.lot_id] -= event.cleared
            source = before.cargo.get(event.lot_id)
            if (source is None or source[0] != event.owner
                    or source[2] != event.good
                    or source[3] < event.cleared):
                findings.append(Finding(
                    turn, f"cargo.{event.lot_id}.source", 0, event.cleared,
                    ("missing or mismatched owned lot",)))
        elif isinstance(event, A.HarbourCargoWithdrawn):
            cargo_expected[event.lot_id] -= event.quantity
    for lot_id in sorted(set(before.cargo) | set(after.cargo) | set(cargo_expected)):
        before_row = before.cargo.get(lot_id)
        after_row = after.cargo.get(lot_id)
        before_qty = before_row[3] if before_row else 0
        after_qty = after_row[3] if after_row else 0
        actual_delta = after_qty - before_qty
        explained = cargo_expected.get(lot_id, 0)
        if actual_delta != explained:
            findings.append(Finding(
                turn, f"cargo.{lot_id}.quantity", actual_delta, explained,
                ("HarbourDueTaken/HarbourCargoWithdrawn",)))
        if before_row and after_row and before_row[:3] != after_row[:3]:
            findings.append(Finding(
                turn, f"cargo.{lot_id}.identity", 1, 0,
                ("owner/place/good changed",)))

    departed: Counter[str] = Counter()
    revolt_events = {}
    for event in events:
        if isinstance(event, (A.DependentsDeparted, A.DependentsDied)):
            departed[event.group_id] -= event.heads
        elif isinstance(event, A.GroupRevoltChanged):
            revolt_events[event.group_id] = event.revolting
    for group_id in sorted(set(before.dependents) | set(after.dependents)):
        old = before.dependents.get(group_id)
        new = after.dependents.get(group_id)
        if old is None or new is None:
            findings.append(Finding(
                turn, f"dependents.{group_id}.identity", int(new is not None),
                int(old is not None), ("group appeared/disappeared",)))
            continue
        size_delta = new[1] - old[1]
        if size_delta != departed.get(group_id, 0):
            findings.append(Finding(
                turn, f"dependents.{group_id}.size", size_delta,
                departed.get(group_id, 0),
                ("DependentsDeparted/DependentsDied",)))
        if new[2] != old[2] and revolt_events.get(group_id) != new[2]:
            findings.append(Finding(
                turn, f"dependents.{group_id}.revolt", int(new[2]),
                int(old[2]), ("no GroupRevoltChanged",)))

    capability = {
        event.formation_id: event.after - event.before
        for event in events if isinstance(event, A.FormationCapabilityChanged)
    }
    for formation_id in sorted(set(before.formations) | set(after.formations)):
        old = before.formations.get(formation_id)
        new = after.formations.get(formation_id)
        if old is None or new is None:
            findings.append(Finding(
                turn, f"formations.{formation_id}.identity",
                int(new is not None), int(old is not None),
                ("formation appeared/disappeared",)))
            continue
        if new[0] != old[0]:
            findings.append(Finding(
                turn, f"formations.{formation_id}.people",
                new[0] - old[0], 0, ("no personnel event",)))
        ready_delta = new[1] - old[1]
        if ready_delta != capability.get(formation_id, 0):
            findings.append(Finding(
                turn, f"formations.{formation_id}.ready", ready_delta,
                capability.get(formation_id, 0),
                ("FormationCapabilityChanged",)))
        if not 0 <= new[1] <= new[0]:
            findings.append(Finding(
                turn, f"formations.{formation_id}.range", new[1], new[0],
                ("0 <= ready <= strength",)))

    if sum(after.corvee_sources.values()) != after.corvee_days:
        findings.append(Finding(
            turn, "labour.corvee_sources",
            sum(after.corvee_sources.values()), after.corvee_days,
            ("named source days",)))
    if not 0 <= after.works_days <= after.corvee_days:
        findings.append(Finding(
            turn, "labour.public_works", after.works_days,
            after.corvee_days, ("works cannot exceed sourced corvee",)))
    for group_id in after.corvee_sources:
        group = after_world.court.dependents.get(group_id)
        if group is None or group.function != "field_labour":
            findings.append(Finding(
                turn, f"labour.corvee_source.{group_id}", 1, 0,
                ("source must be a field-labour cohort",)))

    population_events = {
        getattr(event, "place_id")
        for event in events
        if type(event).__name__ in {
            "PlagueBegan", "PlagueSpread", "PlagueProgressed", "PlagueDeaths"
        } and getattr(event, "place_id", "")
    }
    for place_id, row in after.populations.items():
        population, susceptible, infected, recovered, dead = row
        if min(susceptible, infected, recovered, dead) < 0:
            findings.append(Finding(
                turn, f"population.{place_id}.negative",
                min(susceptible, infected, recovered, dead), 0,
                ("non-negative compartments",)))
        accounted = susceptible + infected + recovered + dead
        if accounted != population:
            findings.append(Finding(
                turn, f"population.{place_id}.accounting",
                accounted, population, ("S+I+R+dead",)))
        if row != before.populations.get(place_id) and (
                place_id not in population_events):
            findings.append(Finding(
                turn, f"population.{place_id}.causality", 1, 0,
                ("no plague progress/import/death event",)))
    return findings


def run(turns: int = DEFAULT_TURNS, seed: int = SEED,
        scenario: str = "ugarit") -> dict:
    world = load_scenario(scenario, seed)
    findings: list[Finding] = []
    event_counts: Counter[str] = Counter()
    source_totals: Counter[str] = Counter()
    sink_totals: Counter[str] = Counter()
    for _ in range(turns):
        before = world
        world, events = advance(world)
        event_counts.update(type(event).__name__ for event in events)
        old, new = snapshot(before), snapshot(world)
        for good, amount in _delta(old.stores, new.stores).items():
            (source_totals if amount > 0 else sink_totals)[good] += abs(amount)
        findings.extend(audit_transition(before, world, events))
    return {
        "turns": turns,
        "findings": findings,
        "event_counts": dict(sorted(event_counts.items())),
        "sources": dict(sorted(source_totals.items())),
        "sinks": dict(sorted(sink_totals.items())),
    }


def _parse_turns(argv: list[str]) -> int:
    for index, argument in enumerate(argv[1:], 1):
        if argument == "--turns" and index + 1 < len(argv):
            return int(argv[index + 1])
        if argument.startswith("--turns="):
            return int(argument.split("=", 1)[1])
    return DEFAULT_TURNS


def main(argv: list[str]) -> int:
    result = run(_parse_turns(argv))
    findings = result["findings"]
    if "--json" in argv:
        print(json.dumps({
            **result,
            "findings": [dataclasses.asdict(item) for item in findings],
        }, sort_keys=True))
    else:
        print(f"M13 causal audit · {result['turns']} turns")
        print("  material sources  " + (
            ", ".join(f"{good} +{amount:,}"
                      for good, amount in result["sources"].items()) or "none"))
        print("  material sinks    " + (
            ", ".join(f"{good} -{amount:,}"
                      for good, amount in result["sinks"].items()) or "none"))
        print(f"  causal findings   {len(findings)}")
        for finding in findings[:20]:
            print(
                f"    turn {finding.turn}: {finding.path} "
                f"{finding.actual:+} != {finding.explained:+} "
                f"({', '.join(finding.evidence)})")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
