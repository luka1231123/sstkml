"""Session driver + save/load/replay (spec 2.1).

A save is a chosen Alu, seed, and action log.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from engine.actions import from_dict, to_dict
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign

def new_seed() -> int:
    """A seed for a game nobody has played yet.

    The engine is deterministic on purpose and must stay that way -- a save is
    a seed plus an action log. That is a statement
    about *reproducing* a run, not about every run being the same one, and
    pinning the default seed quietly turned the second into the first. Drawn
    here, outside the engine, and printed so any run can be replayed on demand.
    """
    return secrets.randbits(48)


SAVE_VERSION = 23


def play(seed: int, chosen_alu: str, script: list[list]) -> tuple[object, list, list]:
    """Run a headless game. `script` is one list of actions per turn.

    Returns (final world, action log, empty compatibility list). No model, no IO.
    """
    world = load_campaign(chosen_alu, seed)
    log: list[dict] = []
    hashes: list[str] = []
    for turn_actions in script:
        world, _ = advance(world)
        turn = world.date.absolute
        for act in turn_actions:
            world, _ = apply(world, act)
            log.append({"turn": turn, "action": to_dict(act)})
    return world, log, hashes


def save(path: str | Path, seed: int, chosen_alu: str, turns: int,
         log: list, world, ai_log: list | None = None,
         hours_left: int | None = None) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "version": SAVE_VERSION,
        "seed": seed,
        "chosen_alu": chosen_alu,
        "turns": turns,
        "log": log,
        "ai_log": ai_log or [],
        # Questions and other information work can spend attention without
        # changing World, so a GUI save must carry the remainder explicitly.
        "hours_left": hours_left,
    }, indent=2)
    # A campaign save should never be a half-written JSON file after an
    # interrupted process.  Replace a sibling temporary file atomically.
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(payload)
    temporary.replace(destination)


def load_session(path: str | Path):
    """Rebuild a save, returning both world and session metadata."""
    data = json.loads(Path(path).read_text())
    if data.get("version") != SAVE_VERSION:
        raise ValueError(
            "This save predates the current shared-world format and cannot be loaded. "
            f"Start a new campaign (save {data.get('version')!r}, "
            f"current {SAVE_VERSION}).")
    world = load_campaign(data["chosen_alu"], data["seed"])
    by_turn: dict[int, list] = {}
    for entry in data["log"]:
        action = from_dict(entry["action"])
        by_turn.setdefault(entry["turn"], []).append(action)

    for _ in range(data["turns"]):
        world, _ = advance(world)
        turn = world.date.absolute
        for act in by_turn.get(turn, []):
            world, _ = apply(world, act)

    return world, data


def replay(path: str | Path):
    """Compatibility entry point returning only the rebuilt world."""
    world, _data = load_session(path)
    return world
