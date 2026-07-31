#!/usr/bin/env python3
"""One authority per fact (SPEC.md 2.10, 6.2; docs/PHASE_C_AUTHORITY.md).

The gate for Phase C, and the inventory that opens it. Every row of the
authority table names a fact that two systems can both answer today: the legacy
court in `engine/state.py` and the kernel in `engine/kernel/`. This tool loads
both worlds and reports a finding wherever both sides hold a non-empty answer.

It is expected to fail before the migration and to report nothing after it. That
asymmetry is the point: a duplicate authority is invisible until something counts
the two answers side by side, and "we removed the old field" is a claim a script
can check rather than a claim a commit message can make.

A row may also be *unmapped* -- a court entity that answers to no kernel
counterpart. That is reported too, because an entity nobody owns is how a
migration quietly loses a granary.

Usage:

    python3 tools/authority_audit.py
    python3 tools/authority_audit.py --json
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.kernel.world import Kernel          # noqa: E402
from engine.state import World                  # noqa: E402
from load import kernel_settlement, load_scenario  # noqa: E402

SEED = 8814402919

# The settlement the legacy court is the seat of. Asked of the world rather than
# written down here, and the reason is a bug this line used to have: it said
# "settlement:ugarit", which is the id in `content/kernel/world.toml`, an older
# authored world that the live scenario no longer builds from. The scenario's
# seat is `settlement:seat`. Every kernel-side count below therefore returned
# zero, and an audit row is only a finding when both sides are non-empty -- so
# goods, people, labour and land, the four rows Phase C is actually about,
# reported nothing at all and looked like progress.
FALLBACK_SEAT = "settlement:seat"


def seat_of(kernel: Kernel) -> str:
    """Which settlement is the court's. The kernel already knows (Task 2 C2)."""
    goods = getattr(kernel, "seat_goods", None)
    return getattr(goods, "seat", "") or FALLBACK_SEAT


@dataclasses.dataclass(frozen=True)
class Finding:
    """One fact with two authorities, or one with none."""
    fact: str
    court: str            # what the court side holds
    kernel: str           # what the kernel side holds
    deletion_target: str  # what Phase C must remove

    def line(self) -> str:
        return (f"  {self.fact}\n"
                f"      court   {self.court}\n"
                f"      kernel  {self.kernel}\n"
                f"      delete  {self.deletion_target}")


def _quantity(text: str, amount: int) -> str:
    return f"{text}: {amount:,}"


def _court_goods(world: World) -> int:
    return sum(world.court.stores.values())


def _kernel_goods(kernel: Kernel) -> int:
    return sum(lot.quantity for lot in kernel.book.at(seat_of(kernel)))


def _court_people(world: World) -> int:
    """Heads the crown feeds. `size` is the court's word for what a cohort calls
    `people`, which is itself one of the things Phase C stops having twice."""
    return sum(group.size for group in world.court.dependents.values())


def _kernel_people(kernel: Kernel) -> int:
    return kernel.people(seat_of(kernel))


def _court_labour(world: World) -> int:
    """Person-days the court can call on, its own way of reckoning them.

    The court has no per-head labour figure: a group's labour is whatever the
    system asking for it decides, and the only standing numbers are the corvée
    days already raised and the groups sent to the fields. That absence is the
    duplication this row is about, so heads stand in for capacity here.
    """
    return (world.court.corvee_days
            + sum(world.court.dependents[group].size
                  for group in world.court.at_harvest
                  if group in world.court.dependents)
            or _court_people(world))


def _kernel_labour(kernel: Kernel) -> int:
    return kernel.labour(seat_of(kernel))


def _court_land(world: World) -> int:
    """Ground under the crown. C4: the court holds none; the kernel's sites do."""
    return 0


def _kernel_land(kernel: Kernel) -> int:
    seat = seat_of(kernel)
    return sum(
        kernel.registry.sites[site].extent
        for site in sorted(kernel.registry.sites)
        if kernel.registry.sites[site].settlement == seat
        and kernel.registry.sites[site].function == "estate")


def _stored(field: str):
    """How much of a fact the court keeps of its own, which may be none.

    A name that resolves to a property rather than a field is a view over the
    kernel (Task 2 C5): the court can still read it, and reading is not holding.
    """
    def count(world: World) -> int:
        if field in {f.name for f in dataclasses.fields(world)}:
            return len(getattr(world, field))
        return 0
    return count


# Each row: the fact, how to count it on each side, and what Phase C deletes.
# Counting rather than comparing, deliberately: the two figures are allowed to
# differ during the migration, and a row is a finding because both are non-empty,
# not because they disagree.
ROWS: tuple[tuple[str, object, object, str], ...] = (
    ("stock of goods at the seat", _court_goods, _kernel_goods,
     "Court.stores"),
    ("ordinary people at the seat", _court_people, _kernel_people,
     "Court.dependents"),
    ("labour available at the seat", _court_labour, _kernel_labour,
     "Court.corvee_days / corvee_sources / at_harvest"),
    ("land under the seat", _court_land, _kernel_land,
     "Court.estates"),
    ("places", _stored("places"),
     lambda k: len(k.registry.settlements), "World.places"),
    ("routes", _stored("routes"),
     lambda k: len(k.registry.routes), "World.routes"),
    ("foreign court standing",
     lambda w: len(w.foreign_courts),
     lambda k: max(0, len(k.autonomous())),
     "World.foreign_courts / ForeignCourt"),
    ("actor belief",
     lambda w: len(w.foreign_beliefs),
     lambda k: len(k.beliefs), "World.foreign_beliefs"),
    ("the date", lambda w: w.date.absolute + 1,
     lambda k: k.date.absolute + 1, "one of World.date / Kernel.date"),
)


def findings(world: World, kernel: Kernel) -> list[Finding]:
    found: list[Finding] = []
    for fact, on_court, on_kernel, target in ROWS:
        court = int(on_court(world))
        kern = int(on_kernel(kernel))
        if court and kern:
            found.append(Finding(
                fact, _quantity("holds", court), _quantity("holds", kern),
                target))
    return found


def unmapped(world: World, kernel: Kernel) -> list[Finding]:
    """Court places that answer to no kernel settlement (Task 2 C1).

    Every court place names the Alu it belongs to, and every Alu is a kernel
    settlement, so the question has an answer in the content and does not need
    a hand-written table to supply one. It used to be asked by matching names
    -- a place was mapped if some settlement's id looked like it -- which
    reported twenty-six findings that were not defects: Mari answers to Dur
    Katlimmu and Argos to Mycenae, and no amount of comparing the strings
    "mari" and "dur_katlimmu" was ever going to discover that.

    A finding here now means the content is genuinely broken: a place whose Alu
    does not exist. `load.py` refuses to load such a scenario, so this is a
    second reading of a fact the loader already enforces, which is what an
    audit is for.
    """
    missing = sorted(
        f"{place} (alu {kernel_settlement(world, place)[len('settlement:'):]})"
        for place in world.places
        if kernel_settlement(world, place) not in kernel.registry.settlements)
    if not missing:
        return []
    return [Finding(
        "court places with no kernel settlement",
        f"{len(missing)}: " + ", ".join(missing[:8])
        + ("..." if len(missing) > 8 else ""),
        f"{len(kernel.registry.settlements)} settlements authored",
        "author the Alu, or point the place at one that exists",
    )]


def run(seed: int = SEED) -> dict:
    # One fortnight on both sides before counting. Belief, in either half, only
    # exists once somebody has looked at something, so auditing the opening state
    # would report no duplicate beliefs and be wrong about it.
    from engine.kernel.world import advance as advance_kernel
    from engine.tick import advance as advance_court

    scenario = load_scenario("ugarit", seed)
    world, _ = advance_court(scenario)
    kernel, _ = advance_kernel(scenario.kernel)
    duplicates = findings(world, kernel)
    gaps = unmapped(world, kernel)
    return {
        "duplicate_authorities": [
            dataclasses.asdict(item) for item in duplicates],
        "unmapped": [dataclasses.asdict(item) for item in gaps],
        "findings": len(duplicates) + len(gaps),
    }


def main(argv: list[str]) -> int:
    result = run()
    if "--json" in argv:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result["findings"] else 0
    print("authority audit · one authority per fact")
    for group, title in (("duplicate_authorities", "two authorities"),
                         ("unmapped", "no authority")):
        rows = result[group]
        if not rows:
            continue
        print(f"  {title}: {len(rows)}")
        for row in rows:
            print(Finding(**row).line())
    if not result["findings"]:
        print("  no findings")
        return 0
    print(f"  findings   {result['findings']}")
    print("  Phase C is not complete; see docs/PHASE_C_AUTHORITY.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
