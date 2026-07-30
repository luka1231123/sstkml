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

A row may also be *unmapped* -- a court entity with no kernel counterpart named
in the id map. That is reported too, because an entity nobody owns is how a
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
from load import load_scenario                  # noqa: E402
from load_kernel import load_kernel             # noqa: E402

SEED = 8814402919

# The settlement the legacy court is the seat of. Named once, because the whole
# audit is about which of the two records for this place is the authority.
SEAT = "settlement:ugarit"


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
    return sum(lot.quantity for lot in kernel.book.at(SEAT))


def _court_people(world: World) -> int:
    """Heads the crown feeds. `size` is the court's word for what a cohort calls
    `people`, which is itself one of the things Phase C stops having twice."""
    return sum(group.size for group in world.court.dependents.values())


def _kernel_people(kernel: Kernel) -> int:
    return kernel.people(SEAT)


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
    return kernel.labour(SEAT)


def _court_land(world: World) -> int:
    """Ground under the crown, in the court's unit: iku rather than qa of seed."""
    return sum(estate.area_iku for estate in world.court.estates.values())


def _kernel_land(kernel: Kernel) -> int:
    return sum(
        kernel.registry.sites[site].extent
        for site in sorted(kernel.registry.sites)
        if kernel.registry.sites[site].settlement == SEAT
        and kernel.registry.sites[site].function == "estate")


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
    ("places", lambda w: len(w.places),
     lambda k: len(k.registry.settlements), "World.places"),
    ("routes", lambda w: len(w.routes),
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
    """Court entities with no kernel counterpart under the current id grammar.

    Kernel ids carry a kind prefix and the court's do not, so this cannot be a
    string comparison; it asks whether a kernel settlement exists whose id ends
    in the court's own name. Crude on purpose -- the authored map that replaces
    this guess is C2's deliverable, and until it exists an honest "nobody has
    said" is better than a derived answer that looks authoritative.
    """
    names = {
        settlement.split(":")[-1]
        for settlement in kernel.registry.settlements
    }
    missing = sorted(
        place for place in world.places
        if place.replace("_", "") not in {name.replace("_", "")
                                          for name in names})
    if not missing:
        return []
    return [Finding(
        "court places with no kernel settlement",
        f"{len(missing)}: " + ", ".join(missing[:8])
        + ("..." if len(missing) > 8 else ""),
        f"{len(names)} settlements authored",
        "content/kernel/*.toml must author them, or the id map must say why not",
    )]


def run(seed: int = SEED) -> dict:
    # One fortnight on both sides before counting. Belief, in either half, only
    # exists once somebody has looked at something, so auditing the opening state
    # would report no duplicate beliefs and be wrong about it.
    from engine.kernel.world import advance as advance_kernel
    from engine.tick import advance as advance_court

    world, _ = advance_court(load_scenario("ugarit", seed))
    kernel, _ = advance_kernel(load_kernel("world", seed))
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
