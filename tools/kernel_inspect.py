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

Nothing here is player-facing. The player's court sees evidence available to
it, dated and sourced and often wrong; this sees the world.

The evidence is collected by re-running the world rather than by keeping a
causal log in the save. That is only legitimate because the run is
deterministic -- the same seed and the same actions reproduce the same history,
so the transfers this replays are the transfers that happened.

    python3 tools/kernel_inspect.py where grain
    python3 tools/kernel_inspect.py why-lot settlement:mahadu/8/lot/0
    python3 tools/kernel_inspect.py why-choice org:mahadu_council --turns 9
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.kernel.world import Kernel, advance_logged  # noqa: E402
from load_kernel import load_kernel                     # noqa: E402


def replay(turns: int) -> tuple[Kernel, list]:
    kernel = load_kernel()
    logs = []
    for _ in range(turns):
        kernel, _events, log = advance_logged(kernel)
        logs.append(log)
    return kernel, logs


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
    print("\n  (M13.1 has no shipments; 'why is this shipment blocked' arrives")
    print("   with movement in M13.3.)")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    turns = 24
    if "--turns" in argv:
        at = argv.index("--turns")
        turns = int(argv[at + 1])
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
    elif command == "short":
        short(kernel, logs)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
