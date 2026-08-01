#!/usr/bin/env python3
"""The causal inspector (spec 7.5). Omniscient, and for developers only.

Spec 7.5 lists the questions a development build must be able to answer. This
answers them from the record rather than from a reading of the code:

    why-lot LOT          Why does this lot exist?
    where GOOD           Where did this quantity go?
    why-choice ACTOR     Why did this actor choose this?
    belief ACTOR         Which observation supported that belief?
    authority ID         Which order or obligation authorized this act?
    short                Who asked for something and did not get it?
    chain PLACE|LOT      Where did this household's food come from?
    weather              What did the climate do, and to whom?

Nothing here is player-facing. The player's court sees evidence available to
it, dated and sourced and often wrong; this sees the world.

The evidence is collected by re-running the world rather than by keeping a
causal log in the save. That is only legitimate because the run is
deterministic -- the same seed and the same actions reproduce the same history,
so the transfers this replays are the transfers that happened.

    python3 tools/kernel_inspect.py where grain
    python3 tools/kernel_inspect.py why-lot settlement:mahadu/8/lot/0
    python3 tools/kernel_inspect.py why-choice org:mahadu_council --turns 9
    python3 tools/kernel_inspect.py chain settlement:alashiya_port --turns 60
    python3 tools/kernel_inspect.py weather --turns 72
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.kernel.world import Kernel, advance_logged  # noqa: E402
from load import load_campaign                          # noqa: E402

SCENARIO, SEED = "ugarit", 1


def opening() -> Kernel:
    """The world every query below replays from."""
    return load_campaign(SCENARIO, SEED).kernel


def replay(turns: int) -> tuple[Kernel, list]:
    kernel = opening()
    logs = []
    for _ in range(turns):
        kernel, _events, log = advance_logged(kernel)
        logs.append(log)
    return kernel, logs


def _lot_history(turns: int) -> dict:
    """Every lot the run ever held, as it last stood.

    Replayed separately from `replay` and kept out of it deliberately: a lot
    that is emptied leaves the book, so a question about where a household's
    bread came from is a question about lots that mostly no longer exist. This
    is the only query that needs them, and it pays for them itself.
    """
    kernel = opening()
    seen = dict(kernel.book.lots)
    for _ in range(turns):
        kernel, _events, _log = advance_logged(kernel)
        seen.update(kernel.book.lots)
    return seen


def _rule(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def why_lot(kernel: Kernel, logs: list, lot_id: str) -> None:
    _rule(f"why does {lot_id} exist")
    lot = kernel.book.lots.get(lot_id)
    if lot:
        print(f"  it still exists: {lot.quantity} {lot.good} at {lot.location}")
        print(f"  owned by {lot.owner}, held by {lot.holder}")
        print(f"  provenance: {', '.join(lot.provenance) or 'none recorded'}")
    else:
        print("  it does not exist now; the ledger below is its whole life")
    for log in logs:
        for t in log.transfers:
            if t.lot != lot_id:
                continue
            authority = f" under {t.authority}" if t.authority else ""
            print(f"  t{t.turn:>3} {t.phase:<12} {t.reason:<10} {t.quantity:>8} "
                  f"{t.from_owner} -> {t.to_owner}{authority}")


def where(kernel: Kernel, logs: list, good: str) -> None:
    from engine.ownership import SINKS, SOURCES

    _rule(f"where did the {good} go")
    into: dict[str, int] = {}
    out: dict[str, int] = {}
    moved: dict[str, int] = {}
    for log in logs:
        for t in log.transfers:
            if t.good != good:
                continue
            if t.reason in SOURCES:
                into[t.reason] = into.get(t.reason, 0) + t.quantity
            elif t.reason in SINKS:
                out[t.reason] = out.get(t.reason, 0) + t.quantity
            else:
                moved[t.reason] = moved.get(t.reason, 0) + t.quantity

    for title, table in (("in", into), ("out", out), ("moved", moved)):
        body = ", ".join(f"{k} {v:,}" for k, v in sorted(table.items()))
        print(f"  {title:<6} {body or 'nothing'}")
    print(f"  standing  {kernel.book.total(good):,}")
    for settlement in sorted(kernel.registry.settlements):
        print(f"    {settlement:<28} {kernel.stores(settlement, good):>9,}")


def why_choice(kernel: Kernel, logs: list, actor: str, turn: int | None) -> None:
    _rule(f"why did {actor} choose what it chose")
    for log in logs:
        if turn is not None and log.turn != turn:
            continue
        for intent in log.intents:
            if intent.actor != actor:
                continue
            grant = log.allocation.for_intent(intent.id)
            got = "not allocated" if grant is None else (
                f"got {grant.granted:,} of {grant.asked:,}")
            print(f"  t{log.turn:>3} {intent.kind:<8} {intent.subject:<26} "
                  f"asked {intent.quantity:>8,}  {got}")
            for basis in intent.basis:
                claim = next((c for c in kernel.beliefs[actor].claims
                              if c.id == basis), None)
                if claim:
                    print(f"        because it held: {claim.attribute}="
                          f"{claim.value:,} ({claim.source}, seen t{claim.observed_turn})")


def belief(kernel: Kernel, actor: str) -> None:
    _rule(f"what {actor} believes, and on what evidence")
    held = kernel.beliefs.get(actor)
    if held is None:
        print("  it holds nothing; it may not be an actor that decides")
        return
    subjects = sorted({c.subject for c in held.claims})
    for subject in subjects:
        attributes = sorted({c.attribute for c in held.about(subject)})
        for attribute in attributes:
            best = held.best(subject, attribute)
            claims = held.about(subject, attribute)
            flag = "  (conflicting)" if held.conflicts(subject, attribute) else ""
            print(f"  {subject} {attribute:<14} {best.value:>9,}  "
                  f"{best.source}, seen t{best.observed_turn}, "
                  f"{len(claims)} claim(s){flag}")
            if best.basis:
                print(f"      from {', '.join(best.basis)}")


def authority(kernel: Kernel, logs: list, wanted: str) -> None:
    _rule(f"what {wanted} authorized")
    found = False
    for log in logs:
        for t in log.transfers:
            if t.authority != wanted:
                continue
            found = True
            print(f"  t{t.turn:>3} {t.reason:<10} {t.quantity:>8,} {t.good:<8} "
                  f"{t.from_owner} -> {t.to_owner}")
    for obligation in kernel.obligations:
        if obligation.id == wanted:
            print(f"  the clause: {obligation.clause}, {obligation.quantity:,} "
                  f"{obligation.good}, now {obligation.status}")
            print(f"  believed consequence: {obligation.consequence or 'none stated'}")
            print(f"  history: {' | '.join(obligation.history[-6:])}")
            found = True
    if not found:
        print("  nothing was done under it")


def _parents(lot) -> tuple[str, ...]:
    """The lots this one came out of, newest link first.

    Three kinds of link and one meaning. `from:` is a conversion -- sheaves
    drawn down, grain created. `split:` is the same goods in two lots, because
    part of a store was sold or sailed. `merged:` is the reverse: another lot
    folded into this one, which is how a cargo becomes part of a granary. All
    three say "to explain this, go and look at that".

    Conversions and handovers are interleaved rather than listed in turn, and
    that ordering is the difference between a tree that reaches a field and one
    that does not. The walk narrows as it goes back, so whatever is at the
    front of this list is what survives the narrowing. A granary lot has one
    `from:` parent and dozens of `merged:` ones: take the conversions first and
    the trail skips the bargains, take the handovers first and it walks
    sideways through a year of bookkeeping without ever leaving the store. One
    of each, alternating, keeps both threads alive.
    """
    kinds: dict[str, list[str]] = {"from:": [], "split:": [], "merged:": []}
    for mark in reversed(lot.provenance):
        for prefix, found in kinds.items():
            if mark.startswith(prefix):
                found.append(mark[len(prefix):].split("@")[0])
    made = kinds["from:"]
    passed = kinds["split:"] + kinds["merged:"]

    seen, unique = {lot.id}, []
    for step in range(max(len(made), len(passed))):
        for queue in (made, passed):
            lot_id = queue[step] if step < len(queue) else None
            if lot_id and lot_id not in seen:
                seen.add(lot_id)
                unique.append(lot_id)
    return tuple(unique)


# The transfers worth printing when a lot's whole life would drown the tree.
# A source, a sink, and anything that changed whose it was or where it was --
# which is exactly the set a "how did this get here" question is asking about.
TELLING = frozenset({"harvested", "produced", "authored", "mined", "sold",
                     "paid", "levied", "carried", "unloaded", "loaded",
                     "sown", "lost", "seized", "gifted"})

# How many parents to follow at the top of the tree; one fewer at each step down.
BRANCH = 4


def ancestry(seen: dict, lot_id: str, depth: int = 12) -> tuple[str, ...]:
    """Every lot this one came out of, as far back as the record goes.

    Unbounded in width where `chain` below is bounded, because this answers
    "is that in here at all" rather than "read me the story". Depth-bounded and
    cycle-safe: provenance only ever points backwards, but a walk that trusted
    that and was wrong would not stop.
    """
    found: list[str] = []
    frontier = [(lot_id, 0)]
    while frontier:
        current, step = frontier.pop(0)
        if current in found or step > depth:
            continue
        found.append(current)
        lot = seen.get(current)
        if lot is not None:
            frontier.extend((parent, step + 1) for parent in _parents(lot))
    return tuple(found)


def eaten_at(logs: list, seen: dict, place: str) -> tuple[str, ...]:
    """The lots households at a place drew their rations out of, newest first."""
    found: list[str] = []
    for log in reversed(logs):
        for transfer in log.transfers:
            if (transfer.reason == "consumed" and transfer.lot in seen
                    and seen[transfer.lot].location == place
                    and transfer.lot not in found):
                found.append(transfer.lot)
    return tuple(found)


def chain(kernel: Kernel, logs: list, seen: dict, target: str,
          depth: int = 6) -> None:
    """Walk a household's food back to the ground it grew in (spec 7.5, M13.2).

    The milestone's exit gate is not that the chain exists -- conservation
    already says that much -- but that it can be *explained*, link by link, out
    of records rather than out of a reading of the code. Every line below is a
    transfer or a provenance mark, and where the trail runs past the replayed
    window it says so rather than interpolating.

    It branches, because a granary is a mixture and saying otherwise would be a
    lie told for tidiness. A fortnight's bread on Alashiya came partly off the
    estate outside the wall and partly out of a cargo that crossed from Ma'hadu,
    which came off a road from Ari; the tree is what that sentence looks like
    when every clause of it has to be a record.
    """
    moves: dict[str, list] = {}
    for log in logs:
        for transfer in log.transfers:
            moves.setdefault(transfer.lot, []).append(transfer)

    roots = [target]
    if target not in seen:
        # Every distinct lot the households there ate out of, newest first. Not
        # only the last one: a place that eats out of two granaries in the same
        # fortnight has two answers, and one of them may be the imported one.
        eaten = eaten_at(logs, seen, target)
        if not eaten:
            _rule(f"where the food at {target} came from")
            print("  nothing was eaten there in this window")
            return
        roots = eaten[:3]

    _rule(f"where the food at {target} came from")
    walked: set[str] = set()

    def ledger(lot_id: str, pad: str) -> None:
        for transfer in moves.get(lot_id, []):
            if transfer.reason not in TELLING:
                continue
            under = f" under {transfer.authority}" if transfer.authority else ""
            print(f"  {pad}    t{transfer.turn:>3} {transfer.reason:<10}"
                  f" {transfer.quantity:>8,}  {transfer.from_owner}"
                  f" -> {transfer.to_owner}{under}")

    def walk(lot_id: str, step: int) -> None:
        pad = "  " * step
        lot = seen.get(lot_id)
        if lot is None:
            # Created and emptied inside one turn, so it never appears in a
            # between-turn snapshot: a sheaf lot threshed the fortnight it was
            # cut, most often. Its ledger survives; its ancestry is reachable
            # down the branch that outlived it.
            print(f"  {pad}{lot_id}: emptied within a turn, ledger only")
            ledger(lot_id, pad)
            return
        if lot_id in walked:
            print(f"  {pad}{lot.good} · {lot_id} (already followed above)")
            return
        walked.add(lot_id)
        print(f"  {pad}{lot.good} · {lot_id}")
        ledger(lot_id, pad)

        parents = _parents(lot)
        if not parents:
            origin = next((m for m in lot.provenance if not m.startswith(
                ("from:", "split:", "merged:"))), "unknown")
            print(f"  {pad}    and before that: {origin}")
            return
        if step + 1 >= depth:
            print(f"  {pad}    out of {len(parents)} earlier lot(s); "
                  f"pass --depth to follow them")
            return
        # Widest at the root and narrower as it goes back, because a granary
        # holds dozens of merged lots and following every one of them prints a
        # year of bookkeeping rather than an explanation. What is dropped is
        # counted out loud: a truncated tree that looks complete is worse than
        # no tree.
        width = max(1, BRANCH - step)
        for parent in parents[:width]:
            walk(parent, step + 1)
        if len(parents) > width:
            print(f"  {pad}    ({len(parents) - width} further lot(s) went into "
                  f"this one, not followed)")

    for root in roots:
        walk(root, 0)


def weather(kernel: Kernel, logs: list) -> None:
    """What the climate did, and which estate paid for it (spec 6.2).

    The other half of the exit gate. A drought is not a scripted event here: it
    is one integer per turn, the same for every settlement in the region, and
    what it costs each of them depends on how much ground they had and what
    they decided to do with their hands.
    """
    _rule("what the weather did")
    years: dict[int, dict] = {}
    for log in logs:
        year = years.setdefault((log.turn - 1) // 24 + 1,
                                {"climate": [], "withered": {}, "reaped": {},
                                 "neglect": 0})
        for event in log.events:
            if event[0] == "withered":
                _, actor, gone, neglect, climate = event
                year["climate"].append(climate)
                year["withered"][actor] = year["withered"].get(actor, 0) + gone
                year["neglect"] = max(year["neglect"], neglect)
            elif event[0] == "reaped":
                _, actor, _place, cut = event
                year["reaped"][actor] = year["reaped"].get(actor, 0) + cut

    if not years:
        print("  no growing season fell inside this window")
        return
    for number in sorted(years):
        year = years[number]
        climate = min(year["climate"]) if year["climate"] else 100
        neglect = (f", worst neglect {year['neglect']}/1000"
                   if year["neglect"] else "")
        print(f"\n  year {number} · climate {climate}{neglect}")
        actors = sorted(set(year["withered"]) | set(year["reaped"]))
        for actor in actors:
            lost = year["withered"].get(actor, 0)
            cut = year["reaped"].get(actor, 0)
            print(f"    {actor:<24} withered {lost:>9,}   reaped {cut:>9,}")


def short(kernel: Kernel, logs: list) -> None:
    _rule("who asked for something and did not get it")
    any_short = False
    for log in logs:
        for grant in log.allocation.unmet():
            any_short = True
            print(f"  t{log.turn:>3} {grant.actor:<24} {grant.resource:<32} "
                  f"short {grant.short:,} of {grant.asked:,}")
    if not any_short:
        print("  nobody: every claim on every pool was met in full")
    print("\n  (A `#cargo` pool short here is 'why is this shipment blocked':")
    print("   the crossing's hold ran out and somebody's grain stayed ashore.")
    print("   Named vessels, so the answer can be a particular hull, are M13.3's.)")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    turns, depth = 24, 6
    for flag in ("--turns", "--depth"):
        if flag in argv:
            at = argv.index(flag)
            value = int(argv[at + 1])
            turns, depth = (value, depth) if flag == "--turns" else (turns, value)
            argv = argv[:at] + argv[at + 2:]

    command, *rest = argv
    kernel, logs = replay(turns)
    print(f"replayed {turns} fortnights of {len(kernel.registry.settlements)} "
          f"settlements")

    if command == "why-lot" and rest:
        why_lot(kernel, logs, rest[0])
    elif command == "where" and rest:
        where(kernel, logs, rest[0])
    elif command == "why-choice" and rest:
        why_choice(kernel, logs, rest[0], None)
    elif command == "belief" and rest:
        belief(kernel, rest[0])
    elif command == "authority" and rest:
        authority(kernel, logs, rest[0])
    elif command == "chain" and rest:
        chain(kernel, logs, _lot_history(turns), rest[0], depth)
    elif command == "weather":
        weather(kernel, logs)
    elif command == "short":
        short(kernel, logs)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
