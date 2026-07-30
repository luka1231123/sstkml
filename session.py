"""Session driver + save/load/replay (spec 2.1).

A save is a seed, a scenario, and a log of actions. Loading replays the log and
refuses if the resulting hash differs from the one stored -- this catches every
determinism regression in the field, not just in tests.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from engine.actions import DispatchLetter, EndTurn, from_dict, to_dict
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario

def new_seed() -> int:
    """A seed for a game nobody has played yet.

    The engine is deterministic on purpose and must stay that way -- a save is
    a seed plus an action log, replayed and hash-verified. That is a statement
    about *reproducing* a run, not about every run being the same one, and
    pinning the default seed quietly turned the second into the first. Drawn
    here, outside the engine, and printed so any run can be replayed on demand.
    """
    return secrets.randbits(48)


SAVE_VERSION = 13     # M13.0: causal-foundation and GUI workflow boundary


def _verify_protocol(world, action):
    """Bind a logged grade to its real recipient and recompute it from prose."""
    if not (getattr(action, "text", "") and getattr(action, "profile", "")):
        return
    from ai.grader import grade_for, profile_for
    if isinstance(action, DispatchLetter):
        expected = profile_for(action.recipient)
        if action.profile != expected:
            raise ValueError(
                f"protocol profile mismatch: got {action.profile}, "
                f"expected {expected}")
        # DispatchLetter stores exact text and its formula profile. Its
        # structured terms are the authority for mechanics; replay never asks
        # a model to reconstruct or reinterpret them.
        grade_for(action.text, action.profile, recipient=action.recipient)
        return
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
         log: list, world, ai_log: list | None = None,
         hours_left: int | None = None) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "version": SAVE_VERSION,
        "seed": seed,
        "scenario": scenario,
        "turns": turns,
        "log": log,
        "ai_log": ai_log or [],
        # Questions and other information work can spend attention without
        # changing World, so a GUI save must carry the remainder explicitly.
        "hours_left": hours_left,
        "state_hash_at_save": state_hash(world),
    }, indent=2)
    # A campaign save should never be a half-written JSON file after an
    # interrupted process.  Replace a sibling temporary file atomically.
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(payload)
    temporary.replace(destination)


def load_session(path: str | Path):
    """Rebuild and verify a save, returning both world and session metadata.

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
    return world, data


def replay(path: str | Path):
    """Compatibility entry point returning only the verified world."""
    world, _data = load_session(path)
    return world
