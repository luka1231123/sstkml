"""M3 tests: the scribe corrupts Belief but never World, inspecting recovers the
truth, and replay survives inspect actions."""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import replay, save
SEED = 8814402919


def test_the_scribe_sometimes_slips_and_reproduces_exactly():
    """Spec 6.7b: the scribe's hand is a pure function of (seed, turn, key).
    With the court's own error rate it must occasionally differ from the truth
    it copies, and the same wrong number must reappear on every look, so a
    slip is a fact about the tablet, not a flicker of the run. (C4: the store
    ledgers no longer move once the crown's fields cross to the kernel, so the
    probe is the pure function itself, not a 60-turn drift through a granary
    that now stands still.)"""
    from belief.distortion import p_error, transcribe

    world = load_campaign("seat", SEED)
    perr = p_error(world.court.scribe_competence, world.court.scribe_fatigue)
    truth = 123_456
    key = "ledger:grain"
    copies = {transcribe(truth, SEED, turn, key, perr, sexagesimal=True)
              for turn in range(40)}
    assert len(copies) > 1, "the scribe must sometimes slip"
    for turn in range(40):
        first = transcribe(truth, SEED, turn, key, perr, sexagesimal=True)
        again = transcribe(truth, SEED, turn, key, perr, sexagesimal=True)
        assert first == again, "the same slip must reproduce exactly"


def test_replay_with_inspect():
    world = load_campaign("seat", SEED)
    log: list[dict] = []
    turns = 0
    for _ in range(25):
        world, _ = advance(world)
        turns += 1
        for act in (A.InspectLedger("granary"), A.InspectLedger("seed")):
            world, _ = apply(world, act)
            log.append({"turn": world.date.absolute, "action": A.to_dict(act)})
    save("/tmp/m3_test.json", SEED, "seat", turns, log, world)
    assert state_hash(replay("/tmp/m3_test.json")) == state_hash(world)
