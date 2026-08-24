#!/usr/bin/env python3
"""Read a run without reading a screen. Development only.

`tools/screens.py` shows what the player sees. This shows what happened and
what the game now holds, in the shape a person or an agent can scan:

    look.py figures [--turns 60] [--every 4]     the numbers, one row a turn
    look.py events  [--turns 40] [--each]        events by domain, not 767 lines
    look.py belief  [path] [--turns 6] [--diff]  what any screen could show

Every screen is a pure function of Belief, so `belief` answers "can the player
see this?" without composing a rectangle. `--diff` answers the harder one:
what changed this fortnight, and where.
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from belief.project import project                    # noqa: E402
from engine import seat, systems                      # noqa: E402
from engine.kernel import seat_people as SP           # noqa: E402
from engine.tick import advance                       # noqa: E402
from load import load_campaign                        # noqa: E402

# Which part of the world an event belongs to. The stream is one flat list of
# tuples and dataclasses, and reading it raw is why nobody reads it.
DOMAINS = {
    "farm": ("sown", "reaped", "threshed", "set_aside", "shared_out",
             "unreaped", "withered", "spoiled", "mined", "Harvested",
             "Threshed", "Spoiled"),
    "food": ("hungry", "ate_the_seed", "consumed", "AllocationSet",
             "RationPaid", "Grumbling"),
    "people": ("born", "died", "CohortDisplaced", "CohortReceived",
               "PlagueBegan", "PlagueProgressed", "PlagueDeaths",
               "PlagueSpread", "Born", "Died"),
    "trade": ("sold", "bought", "sailed", "landed", "caravan_departed",
              "lost_at_sea", "lost_on_road", "no_word", "HarbourDueTaken"),
    "letters": ("LetterArrived", "LetterSent", "LetterRead", "LetterArchived",
                "LetterDelegated", "LetterIntercepted", "ReplyDue"),
    "obligation": ("due", "rendered", "defaulted", "ObligationDue",
                   "ObligationDelivered"),
    "war": ("SeatDefended", "SeatTaken", "SeatFell", "AluFell", "Raid"),
    "court": ("UnrestChanged", "LegitimacyChanged", "RitePerformed",
              "RiteSkipped", "PetitionHeard", "PetitionRuled", "LandDueSet",
              "HarbourDueSet", "PersonPlaced", "PersonDismissed"),
    "world": ("news", "ShockLanded", "consolidated", "observed"),
}
DOMAIN_OF = {kind: domain for domain, kinds in DOMAINS.items() for kind in kinds}

# What a name begins with, where the table does not name it. Anything neither
# names lands in `other`, which is on purpose: an unclassified event is a new
# event, and it should be visible rather than filed under something plausible.
PREFIXES = (
    ("Plague", "people"), ("House", "people"), ("Ruler", "people"),
    ("Conceived", "people"), ("Born", "people"), ("Died", "people"),
    ("Letter", "letters"), ("Reply", "letters"), ("Courier", "letters"),
    ("Bronze", "metal"), ("Workshop", "metal"), ("Metal", "metal"),
    ("Institution", "court"), ("Petition", "court"), ("Verdict", "court"),
    ("Oath", "court"), ("Rite", "court"), ("Omen", "court"),
    ("Person", "court"), ("Post", "court"), ("Heir", "court"),
    ("Rations", "food"), ("Allocation", "food"), ("Priority", "food"),
    ("Harbour", "trade"), ("Cargo", "trade"), ("Trade", "trade"),
    ("Obligation", "obligation"), ("Summons", "war"), ("Troop", "war"),
    ("Levy", "war"), ("Corvee", "war"), ("Turn", "world"), ("Shock", "world"),
)


def domain_of(kind: str) -> str:
    if kind in DOMAIN_OF:
        return DOMAIN_OF[kind]
    for prefix, domain in PREFIXES:
        if kind.startswith(prefix):
            return domain
    return "other"


def kind_of(event) -> str:
    if isinstance(event, tuple) and event:
        return str(event[0])
    return type(event).__name__


def quantity_of(event) -> int:
    """The number an event carries, where it carries one obvious number."""
    if isinstance(event, tuple):
        numbers = [x for x in event[1:] if isinstance(x, int)]
        return numbers[-1] if numbers else 0
    for field in dataclasses.fields(event) if dataclasses.is_dataclass(event) else ():
        value = getattr(event, field.name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0


def actor_of(event) -> str:
    if isinstance(event, tuple) and len(event) > 1 and isinstance(event[1], str):
        return event[1]
    return ""


def run(seed: int, turns: int, baseline: bool = False):
    """The world, turn by turn, with the events each turn produced."""
    world = load_campaign("seat", seed)
    if baseline:
        world = dataclasses.replace(world, baseline=True)
    for _ in range(turns):
        world, events = advance(world)
        yield world, events
        if world.ended:
            return


# --- figures ------------------------------------------------------------------

def figures(args) -> int:
    print(f"seed {args.seed}, {args.turns} turns"
          + (" (baseline: abnormal policies frozen)" if args.baseline else ""))
    print("turn  date     seatpop  granary  cover  village  unrest  legit  "
          "hungry  events")
    for world, events in run(args.seed, args.turns, args.baseline):
        turn = world.date.absolute
        if turn % args.every and turn != args.turns:
            continue
        kernel = world.kernel
        cohorts = [c for c in kernel.registry.cohorts.values()
                   if c.settlement == SP.SEAT]
        theirs = {c.id for c in cohorts}
        village = sum(lot.free for lot in kernel.book.at(SP.SEAT)
                      if lot.good == "grain" and lot.owner in theirs)
        granary = seat.held(world).get("grain", 0)
        owed = sum(g.size * g.entitlement for g in seat.groups(world).values())
        owed += sum(c.ration() for c in kernel.registry.cohorts.values()
                    if c.settlement == SP.SEAT
                    and kernel.tenure_of(c) == "redistributive")
        hungry = sum(1 for e in events
                     if kind_of(e) == "hungry" and e[1] in theirs)
        print(f"{turn:5d} y{world.date.year}f{world.date.fortnight:<3d} "
              f"{sum(c.people for c in cohorts):8,} {granary:8,} "
              f"{granary // max(1, owed):5d}  {village:8,} "
              f"{world.court.unrest:6d} {world.court.legitimacy:6d} "
              f"{hungry:6d}  {len(events):6d}")
    print(f"granary holds {systems.granary_capacity(world):,} qa")
    if world.ended:
        print(f"ENDED turn {world.date.absolute}: {world.end_reason}")
    return 0


# --- events -------------------------------------------------------------------

def _tally(events, into: dict) -> None:
    for event in events:
        kind = kind_of(event)
        if args_filter(kind, actor_of(event)):
            row = into.setdefault(domain_of(kind), {}).setdefault(
                kind, [0, 0, Counter()])
            row[0] += 1
            row[1] += quantity_of(event)
            if actor_of(event):
                row[2][actor_of(event).split("/")[0]] += 1


_FILTER = {"kind": "", "who": ""}


def args_filter(kind: str, actor: str) -> bool:
    if _FILTER["kind"] and _FILTER["kind"] not in kind:
        return False
    return not _FILTER["who"] or _FILTER["who"] in actor


def _print_tally(tally: dict, indent: str = "") -> None:
    for domain in sorted(tally, key=lambda d: -sum(
            row[0] for row in tally[d].values())):
        total = sum(row[0] for row in tally[domain].values())
        print(f"{indent}{domain.upper()}  {total:,} events")
        for kind, (count, quantity, actors) in sorted(
                tally[domain].items(), key=lambda item: -item[1][0]):
            who = ", ".join(name for name, _ in actors.most_common(3))
            amount = f"{quantity:>14,}" if quantity else " " * 14
            print(f"{indent}  {count:6,} × {kind:<22}{amount}  {who[:46]}")


def events(args) -> int:
    _FILTER["kind"], _FILTER["who"] = args.kind, args.who
    whole: dict = {}
    for world, produced in run(args.seed, args.turns, args.baseline):
        if args.each:
            turn_tally: dict = {}
            _tally(produced, turn_tally)
            if turn_tally:
                print(f"── turn {world.date.absolute} "
                      f"(y{world.date.year}f{world.date.fortnight}) "
                      f"· {len(produced):,} events")
                _print_tally(turn_tally, "  ")
        _tally(produced, whole)
    if not args.each:
        print(f"seed {args.seed}, {args.turns} turns")
        _print_tally(whole)
    if not whole:
        print("nothing matched. A filter that matches nothing and a world "
              "that did nothing look the same, so this line says which.")
    return 0


# --- belief -------------------------------------------------------------------

def _walk(value, path: str):
    for step in (p for p in path.replace("[", ".").replace("]", "").split(".") if p):
        value = value[int(step)] if step.isdigit() else value[step]
    return value


def _lines(value, prefix: str = "") -> list[str]:
    """A readable projection of any Belief subtree. Lists become numbered rows."""
    if isinstance(value, dict):
        out = []
        for key in value:
            child = value[key]
            if isinstance(child, (dict, list, tuple)) and child:
                out.append(f"{prefix}{key}:")
                out += _lines(child, prefix + "  ")
            else:
                out.append(f"{prefix}{key} = {child!r}")
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for index, child in enumerate(value):
            if isinstance(child, dict):
                head = child.get("name") or child.get("id") or ""
                out.append(f"{prefix}[{index}] {head}")
                out += _lines(child, prefix + "  ")
            else:
                out.append(f"{prefix}[{index}] {child!r}")
        return out
    return [f"{prefix}{value!r}"]


def _flat(value, path: str = "") -> dict:
    if isinstance(value, dict):
        return {k: v for key in value
                for k, v in _flat(value[key], f"{path}.{key}").items()}
    if isinstance(value, (list, tuple)):
        return {k: v for i, item in enumerate(value)
                for k, v in _flat(item, f"{path}[{i}]").items()}
    return {path: value}


def belief(args) -> int:
    world = load_campaign("seat", args.seed)
    if args.baseline:
        world = dataclasses.replace(world, baseline=True)
    before = {}
    for _ in range(args.turns):
        before = project(world) if args.diff else before
        world, _ = advance(world)
    now = project(world)
    if not args.diff:
        print(f"seed {args.seed}, turn {world.date.absolute}, "
              f"belief.{args.path or '*'}")
        print("\n".join(_lines(_walk(now, args.path) if args.path else now)))
        return 0
    old, new = _flat(_walk(before, args.path) if args.path else before), \
        _flat(_walk(now, args.path) if args.path else now)
    print(f"seed {args.seed}, turn {world.date.absolute - 1} → "
          f"{world.date.absolute}, belief.{args.path or '*'}")
    for key in sorted(set(old) | set(new)):
        was, is_ = old.get(key, "—"), new.get(key, "—")
        if was != is_:
            print(f"  {key.lstrip('.'):<52} {was!r} → {is_!r}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="look.py", description=__doc__)
    sub = parser.add_subparsers(dest="what", required=True)

    def common(child):
        child.add_argument("--seed", type=int, default=42)
        child.add_argument("--turns", type=int, default=24)
        child.add_argument("--baseline", action="store_true",
                           help="freeze shocks, plague, displacement, siege")
        return child

    table = common(sub.add_parser("figures", help="the numbers, one row a turn"))
    table.add_argument("--every", type=int, default=1)
    table.set_defaults(run=figures)

    stream = common(sub.add_parser("events", help="events by domain"))
    stream.add_argument("--each", action="store_true", help="one block a turn")
    stream.add_argument("--kind", default="", help="only kinds containing this")
    stream.add_argument("--who", default="", help="only this actor")
    stream.set_defaults(run=events)

    view = common(sub.add_parser("belief", help="what any screen could show"))
    view.add_argument("path", nargs="?", default="",
                      help="e.g. justice.petitions, cohorts[0], trade.movements")
    view.add_argument("--diff", action="store_true", help="what the last turn changed")
    view.set_defaults(run=belief)

    args = parser.parse_args(argv[1:])
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
