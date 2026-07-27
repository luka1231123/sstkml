"""A few M1 tests. Determinism is trusted; these guard the two invariants that
fail silently: grain conservation and arrears monotonicity (spec 10.2)."""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from session import play, replay, save

SEED = 8814402919


def _rite_grain(court, rite_id: str) -> int:
    for r in court.rites:
        if r.id == rite_id:
            return dict(r.requires).get("grain", 0)
    return 0


def test_replay_matches():
    script = [[] for _ in range(80)]
    world, log, _ = play(SEED, "ugarit", script)
    save("/tmp/st_test.json", SEED, "ugarit", 80, log, world)
    assert state_hash(replay("/tmp/st_test.json")) == state_hash(world)


def test_grain_is_conserved():
    """in - consumed - spoiled == delta_stock, exactly, every turn.

    M8 added the threshing floor as a second inflow: what comes off it, less
    what is held back as next year's seed, which moves to the other stock
    rather than leaving the world.
    """
    world = load_scenario("ugarit", SEED)
    for _ in range(60):
        before = world.court.stores["grain"]
        world, events = advance(world)
        after = world.court.stores["grain"]
        threshed = sum(e.taken for e in events
                       if isinstance(e, A.LandDueTaken))
        paid = sum(e.paid for e in events if isinstance(e, A.RationsPaid))
        spoiled = sum(e.amount for e in events
                      if isinstance(e, A.Spoiled) and e.good == "grain")
        rite = sum(_rite_grain(world.court, e.rite_id) for e in events
                   if isinstance(e, A.RitePerformed))
        assert after == before - spoiled + threshed - rite - paid


def test_arrears_monotone_under_zero_allocation():
    world = load_scenario("ugarit", SEED)
    gids = list(world.court.dependents)
    world, _ = apply(world, A.SetPriority(tuple(gids)))
    for gid in gids:
        world, _ = apply(world, A.Allocate(gid, 0))
    prev = {gid: 0 for gid in gids}
    for _ in range(20):
        world, _ = advance(world)
        for gid in gids:
            arr = world.court.dependents[gid].arrears
            assert arr >= prev[gid]
            prev[gid] = arr
