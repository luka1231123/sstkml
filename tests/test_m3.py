"""M3 tests: the scribe corrupts Belief but never World, inspecting recovers the
truth, and replay survives inspect actions."""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from session import replay, save

SEED = 8814402919


def test_scribe_corrupts_belief_not_world_and_inspect_recovers():
    world = load_scenario("ugarit", SEED)
    caught = False
    for _ in range(60):
        world, _ = advance(world)
        b = project(world)
        true_seed = world.court.stores["seed_grain"]
        if b["stores"]["seed_grain"] != true_seed:      # scribe slipped this turn
            caught = True
            after, _ = apply(world, A.InspectLedger("seed"))
            # Inspecting reveals the true count...
            assert project(after)["stores"]["seed_grain"] == true_seed
            # ...and never touched the world (Law 1).
            assert after.court.stores["seed_grain"] == true_seed
    assert caught, "expected at least one transcription slip in 60 turns"


def test_replay_with_inspect():
    world = load_scenario("ugarit", SEED)
    log: list[dict] = []
    turns = 0
    for _ in range(25):
        world, _ = advance(world)
        turns += 1
        for act in (A.InspectLedger("granary"), A.InspectLedger("seed")):
            world, _ = apply(world, act)
            log.append({"turn": world.date.absolute, "action": A.to_dict(act)})
    save("/tmp/m3_test.json", SEED, "ugarit", turns, log, world)
    assert state_hash(replay("/tmp/m3_test.json")) == state_hash(world)
