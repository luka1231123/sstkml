"""Compare one year of waiting with a policy using only the king's records."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import registry
from ai import commitments
from belief import harvest
from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import save
from tui import aftermath, composer, relief, render


def choices(b: dict, requested: bool) -> list:
    actions = []
    need = relief.ration(b)
    for letter in b.get("outbox", ()):
        if letter.get("reply_id") and "seal unbroken" in letter.get("status", ""):
            actions.append(A.ReadLetter(letter["reply_id"]))
    if harvest.plan(b)["remaining"]:
        group = next((g for g in b["groups"] if g["id"] == "palace_dependents"), {})
        if group and not group["at_fields"]:
            actions.append(A.SendToHarvest(group["id"], True))
    grain = max(0, b["stores"].get("grain", 0) - b.get("ration_reserved", 0))
    spare = max(0, grain - 2 * need)
    for group in b["groups"]:
        amount = min(spare, group["arrears_qa"])
        if amount:
            actions.append(A.PayArrears(group["id"], amount))
            spare -= amount
    if not requested and need and grain <= relief.horizon(b) * need:
        court = next((c for c in relief.courts(b) if c["path"]), None)
        if court:
            matter = f"Send me {need} qa of grain."
            draft = composer.assemble(court["id"], composer.default_blocks(), matter)
            actions.append(A.DispatchLetter(
                recipient=court["id"], reply_to="", text=draft.text,
                profile=draft.profile, terms=commitments.as_terms(commitments.read(matter, b)),
                scribe_id="yabninu", seal="royal", courier_id="iliya", path=court["path"]))
    for case in b.get("justice", {}).get("petitions", ()):
        if case["outcomes"]["for"]["affordable"]:
            actions.append(A.RulePetition(case["id"], "for"))
    return actions


def run(seed: int, active: bool, directory: Path) -> dict:
    world = load_campaign("seat", seed)
    log, reports, failures = [], [], []
    requested = False
    hours = 0
    peak_arrears = 0
    shortage_turns = []
    for _ in range(24):
        before = project(world)
        world, events = advance(world)
        b = project(world)
        debt = sum(g["arrears_qa"] for g in b["groups"])
        peak_arrears = max(peak_arrears, debt)
        if debt:
            shortage_turns.append(b["turn"])
        last_report = aftermath.lines(before, b) + render.events_lines(events, world.court)
        reports += last_report
        if world.ended:
            break
        hours = b["attention"]
        for action in choices(b, requested) if active else ():
            cost = registry.cost_of(action)
            if cost > hours:
                continue
            try:
                world, _ = apply(world, action)
            except (ValueError, TypeError, KeyError) as error:
                failures.append(f"turn {b['turn']}: {type(action).__name__}: {error}")
                continue
            hours -= cost
            log.append({"turn": b["turn"], "action": A.to_dict(action)})
            requested |= isinstance(action, A.DispatchLetter)
    b = project(world)
    name = "recovery" if active else "waiting"
    directory.mkdir(parents=True, exist_ok=True)
    save(directory / f"{name}.json", seed, "seat", b["turn"], log, world,
         hours_left=hours, court_report=last_report)
    (directory / f"{name}.txt").write_text("\n".join(reports) + "\n")
    return {"policy": name, "turn": b["turn"], "grain_report_qa": b["stores"].get("grain", 0),
            "arrears_qa": sum(g["arrears_qa"] for g in b["groups"]),
            "peak_arrears_qa": peak_arrears, "shortage_turns": shortage_turns,
            "court_unrest": world.court.unrest,
            "rulings": len(b["justice"]["rulings"]),
            "waiting_claims": len(b["justice"]["petitions"]),
            "orders": len(log), "replies": [l["status"] for l in b.get("outbox", ())],
            "refusals": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=8814402919)
    parser.add_argument("--output", type=Path, default=Path("output/first-year"))
    args = parser.parse_args()
    result = [run(args.seed, active, args.output) for active in (False, True)]
    print(json.dumps(result, indent=2))
