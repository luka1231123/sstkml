#!/usr/bin/env python3
"""Walk the simulated world and move it. Development only.

`tools/look.py` reads a run as tables. This holds one world open, lets you ask
it anything and step it forward, so a question and its answer are one session
rather than one process each.

    world.py                       open a session on seed 42
    world.py --seed 7 --baseline   open one with the abnormal policies frozen
    world.py step 24 stocks        run the commands and exit

Inside, `help` lists the commands. Nothing here is generic over the model on
purpose except the parts that must be: goods, entities and events are read off
the Book and the Registry by name, so a good that stops existing stops being
printed rather than raising.
"""
from __future__ import annotations

import dataclasses
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import seat                                 # noqa: E402
from engine.kernel import arms as AR                    # noqa: E402
from engine.kernel import carry as C                    # noqa: E402
from engine.kernel import farm as F                     # noqa: E402
from engine.tick import advance                         # noqa: E402
from load import load_campaign                          # noqa: E402


def num(value) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def rows(pairs, width: int = 22) -> None:
    for label, value in pairs:
        print(f"  {label:<{width}} {num(value)}")


class Session:
    """One world, held open, with the last turn's events beside it."""

    def __init__(self, seed: int, baseline: bool) -> None:
        self.world = load_campaign("seat", seed)
        if baseline:
            self.world = dataclasses.replace(self.world, baseline=True)
        self.events: list = []
        self.seed = seed

    # --- moving it -------------------------------------------------------

    def step(self, count: str = "1") -> None:
        """step [n] -- advance n fortnights, default one."""
        for _ in range(max(1, int(count))):
            self.world, self.events = advance(self.world)
            if self.world.ended:
                print(f"ENDED turn {self.world.date.absolute}: "
                      f"{self.world.end_reason}")
                return
        self.where()

    def goto(self, turn: str) -> None:
        """goto <turn> -- advance until the absolute turn is reached."""
        want = int(turn)
        while self.world.date.absolute < want and not self.world.ended:
            self.world, self.events = advance(self.world)
        self.where()

    # --- reading it ------------------------------------------------------

    def where(self, *_) -> None:
        """where -- the date, the season, and the court's dials."""
        w, k = self.world, self.world.kernel
        season = F.code_for(k.seasons, w.date.fortnight)
        name = next((n for n, code, _ in F.SEASON_CODES if code == season),
                    "low water")
        rows([("turn", w.date.absolute),
              ("date", f"year {w.date.year}, fortnight {w.date.fortnight}"),
              ("season", name),
              ("baseline", "on -- shocks, plague, displacement frozen"
               if w.baseline else "off"),
              ("legitimacy", w.court.legitimacy),
              ("unrest", w.court.unrest),
              ("ruler", w.court.ruler),
              ("world people", sum(c.people for c in k.registry.cohorts.values())),
              ("events last turn", len(self.events))])

    def stocks(self, place: str = "") -> None:
        """stocks [place] -- every good in the world, or at one place."""
        k = self.world.kernel
        held: Counter = Counter()
        for lot in k.book.lots.values():
            if place and place not in lot.location:
                continue
            held[lot.good] += lot.free
        if not held:
            print("  nothing held there")
            return
        rows(sorted(held.items()))

    def places(self, pattern: str = "") -> None:
        """places [pattern] -- every settlement: people, grain, fortnights of cover."""
        k = self.world.kernel
        print(f"  {'settlement':<28} {'people':>10} {'grain':>14} {'cover':>6}")
        for sid in sorted(k.registry.settlements):
            if pattern and pattern not in sid:
                continue
            people = k.people(sid)
            if not people:
                continue
            need = sum(c.ration() for c in k.cohorts_of(sid))
            grain = k.stores(sid, F.GRAIN)
            flag = " fallen" if k.registry.settlements[sid].fallen else ""
            print(f"  {sid.replace('settlement:', ''):<28} {people:>10,} "
                  f"{grain:>14,} {grain // max(1, need):>6}{flag}")

    def place(self, sid: str) -> None:
        """place <id> -- everything one settlement is and holds."""
        k = self.world.kernel
        sid = sid if sid.startswith("settlement:") else f"settlement:{sid}"
        found = k.registry.settlements.get(sid)
        if found is None:
            print(f"  no settlement {sid!r}")
            return
        need = sum(c.ration() for c in k.cohorts_of(sid))
        rows([("region", found.region), ("owner", found.owner),
              ("autonomous", found.autonomous), ("fallen", found.fallen),
              ("controller", k.controller(sid)),
              ("people", k.people(sid)), ("labour a fortnight", k.labour(sid)),
              ("eats a fortnight", need),
              ("bronze kit wanted", AR.kit(k, sid))])
        print("  cohorts")
        for c in k.cohorts_of(sid):
            print(f"    {c.id:<34} {c.people:>9,} {c.kind:<14} "
                  f"hunger {c.hunger}  {k.tenure_of(c)}")
        print("  ground")
        for site_id in sorted(k.registry.sites):
            site = k.registry.sites[site_id]
            if site.settlement != sid:
                continue
            print(f"    {site_id:<34} {site.function:<14} "
                  f"capacity {site.capacity:,}  extent {site.extent:,}")
        print("  stores")
        self.stocks(sid)
        reach = C.reachable(k, sid)
        if reach:
            print(f"  routes reach  {', '.join(r.replace('settlement:', '') for r in reach)}")

    def court(self, *_) -> None:
        """court -- the crown's stores, dials and institutions."""
        w = self.world
        rows([("legitimacy", w.court.legitimacy), ("unrest", w.court.unrest),
              ("land due /1000", w.court.land_due_rate),
              ("harbour due /1000", w.court.harbour_due_rate),
              ("harbour traffic", w.court.harbour_traffic),
              ("granary holds", __import__(
                  "engine.systems", fromlist=["x"]).granary_capacity(w))])
        print("  stores")
        rows(sorted(seat.held(w).items()))
        print("  institutions")
        for key in sorted(w.court.institutions):
            inst = w.court.institutions[key]
            print(f"    {inst.id:<24} {inst.kind:<10} condition "
                  f"{inst.condition:>4}  head {inst.head or '--'}")
        print("  relations")
        for actor in sorted(w.relations):
            print(f"    {actor:<28} esteem {w.relations[actor].esteem:>4}")

    def who(self, pattern: str = "") -> None:
        """who [pattern] -- cohorts, orgs and people whose id matches."""
        k = self.world.kernel
        for label, table in (("cohort", k.registry.cohorts),
                             ("org", k.registry.orgs),
                             ("person", k.registry.persons)):
            for key in sorted(table):
                if pattern and pattern not in key:
                    continue
                item = table[key]
                extra = (f"{item.people:,} people" if label == "cohort"
                         else getattr(item, "name", "") or getattr(item, "kind", ""))
                print(f"  {label:<8} {key:<38} {extra}")

    def sites(self, pattern: str = "") -> None:
        """sites [pattern] -- the ground, and what each piece of it yields."""
        k = self.world.kernel
        for site_id in sorted(k.registry.sites):
            site = k.registry.sites[site_id]
            if pattern and pattern not in site_id and pattern != site.function:
                continue
            print(f"  {site_id:<34} {site.function:<14} "
                  f"capacity {site.capacity:>8,}  extent {site.extent:>12,}")

    def events_(self, limit: str = "40") -> None:
        """events [n] -- what the last turn produced, commonest first."""
        tally: Counter = Counter()
        for event in self.events:
            kind = event[0] if isinstance(event, tuple) else type(event).__name__
            tally[kind] += 1
        for kind, count in tally.most_common(int(limit)):
            print(f"  {count:>6,} x {kind}")

    def find(self, text: str = "") -> None:
        """find <text> -- any entity in the registry whose id contains it."""
        k = self.world.kernel
        for name in ("settlements", "orgs", "cohorts", "sites", "persons",
                     "polities", "routes", "regions"):
            table = getattr(k.registry, name, {})
            hits = [key for key in sorted(table) if text in key]
            if hits:
                print(f"  {name}: {', '.join(hits[:12])}"
                      + (f" ... and {len(hits) - 12} more" if len(hits) > 12 else ""))

    def help(self, *_) -> None:
        """help -- this list."""
        for name, method in sorted(COMMANDS.items()):
            doc = (method.__doc__ or "").split("\n")[0]
            print(f"  {doc}" if doc else f"  {name}")
        print("  quit -- leave")


COMMANDS = {
    "step": Session.step, "goto": Session.goto, "where": Session.where,
    "stocks": Session.stocks, "places": Session.places, "place": Session.place,
    "court": Session.court, "who": Session.who, "sites": Session.sites,
    "events": Session.events_, "find": Session.find, "help": Session.help,
}


def run(session: Session, line: str) -> bool:
    """One command. False to stop."""
    parts = line.split()
    if not parts:
        return True
    if parts[0] in ("quit", "exit", "q"):
        return False
    method = COMMANDS.get(parts[0])
    if method is None:
        print(f"  no command {parts[0]!r}. `help` lists them.")
        return True
    try:
        method(session, *parts[1:])
    except TypeError as error:
        print(f"  {parts[0]}: {error}")
    return True


def main(argv: list[str]) -> int:
    seed, baseline, rest = 42, False, []
    i = 0
    while i < len(argv):
        if argv[i] == "--seed":
            i += 1
            seed = int(argv[i])
        elif argv[i] == "--baseline":
            baseline = True
        else:
            rest.append(argv[i])
        i += 1

    session = Session(seed, baseline)
    if rest:
        for line in " ".join(rest).split(","):
            print(f"> {line.strip()}")
            run(session, line.strip())
        return 0

    print(f"seed {seed}"
          + (", baseline" if baseline else "")
          + ". `help` lists the commands, `quit` leaves.")
    session.where()
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not run(session, line):
            return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
