"""Session driver + save/load/replay (spec 2.1).

A save is a seed, a scenario, and a log of actions. Loading replays the log and
refuses if the resulting hash differs from the one stored -- this catches every
determinism regression in the field, not just in tests.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.actions import EndTurn, from_dict, to_dict
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario

SAVE_VERSION = 10     # M10: plague, the archive, vows that bind the house


def _verify_protocol(world, action):
    """Bind a logged grade to its real recipient and recompute it from prose."""
    if not (getattr(action, "text", "") and getattr(action, "profile", "")):
        return
    from ai.grader import grade_for, profile_for
    letter = next((item for item in world.inbox
                   if item.id == action.letter_id), None)
    if letter is None:
        raise ValueError(f"protocol reply names unknown letter: {action.letter_id}")
    expected = profile_for(letter.sender)
    if action.profile != expected:
        raise ValueError(
            f"protocol profile mismatch: got {action.profile}, expected {expected}")
    score = grade_for(
        action.text, action.profile, recipient=letter.sender)
    if (action.protocol_total != score.total
            or tuple(action.protocol_violations) != score.violations):
        raise ValueError("protocol grade divergence in logged reply")


def play(seed: int, scenario: str, script: list[list]) -> tuple[object, list, list]:
    """Run a headless game. `script` is one list of actions per turn.

    Returns (final world, action log, per-turn hash list). No model, no IO.
    """
    world = load_scenario(scenario, seed)
    log: list[dict] = []
    hashes: list[str] = []
    for turn_actions in script:
        world, _ = advance(world)
        turn = world.date.absolute
        for act in turn_actions:
            _verify_protocol(world, act)
            world, _ = apply(world, act)
            log.append({"turn": turn, "action": to_dict(act)})
        hashes.append(state_hash(world))          # Phase D: snapshot
    return world, log, hashes


def save(path: str | Path, seed: int, scenario: str, turns: int,
         log: list, world, ai_log: list | None = None) -> None:
    Path(path).write_text(json.dumps({
        "version": SAVE_VERSION,
        "seed": seed,
        "scenario": scenario,
        "turns": turns,
        "log": log,
        "ai_log": ai_log or [],
        "state_hash_at_save": state_hash(world),
    }, indent=2))


def replay(path: str | Path):
    """Rebuild from seed + scenario, replay the log, verify the hash.

    Never invokes the model. Raises on divergence, naming the turn.
    """
    data = json.loads(Path(path).read_text())
    if data.get("version") != SAVE_VERSION:
        raise ValueError(
            f"unsupported save version: {data.get('version')!r}; "
            f"expected {SAVE_VERSION}")
    world = load_scenario(data["scenario"], data["seed"])
    by_turn: dict[int, list] = {}
    for entry in data["log"]:
        action = from_dict(entry["action"])
        by_turn.setdefault(entry["turn"], []).append(action)

    for _ in range(data["turns"]):
        world, _ = advance(world)
        turn = world.date.absolute
        for act in by_turn.get(turn, []):
            _verify_protocol(world, act)
            world, _ = apply(world, act)

    got = state_hash(world)
    want = data["state_hash_at_save"]
    if got != want:
        raise ValueError(f"replay divergence: got {got}, saved {want}")
    return world
