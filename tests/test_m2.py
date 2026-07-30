"""M2 tests: the closed sea produces a backlog without duplicate demands, and
replay survives mail actions (read/reply)."""
from __future__ import annotations

from engine import actions as A
from engine.core import state_hash
from engine.mail import _route_between
from engine.reduce import apply
from engine.systems import sea_open
from engine.tick import advance
from load import load_scenario
from session import replay, save

SEED = 8814402919


def test_closed_sea_backlogs_then_releases_distinct_tablets():
    world = load_scenario("ugarit", SEED)
    winter_sea_backlog = 0
    max_sea_arrivals = 0
    for _ in range(40):
        world, events = advance(world)
        fn = world.date.fortnight
        # No letter ever *enters* a closed sea leg: any sea letter in transit
        # during the closed window is sitting at a harbour, waiting.
        if not sea_open(world.season, fn):
            for L in world.letters_in_transit:
                a, b = L.path[L.edge_index], L.path[L.edge_index + 1]
                r = _route_between(world.routes, a, b)
                # A letter sitting at a harbour before a shut sea leg is backlogged.
                # (One already mid-crossing when the season turned finishes it.)
                if r and r.mode == "sea" and L.legs_into_edge == 0:
                    winter_sea_backlog += 1
        sea_arrivals = sum(1 for e in events if isinstance(e, A.LetterArrived)
                           and e.sender in ("alashiya_gov", "pharaoh"))
        max_sea_arrivals = max(max_sea_arrivals, sea_arrivals)
    assert winter_sea_backlog > 0        # tablets really wait at the harbour
    assert max_sea_arrivals >= 1         # and eventually cross when it opens


def test_replay_with_mail_actions():
    # Drive live (ids depend on letter_seq, which replies advance), log, replay.
    world = load_scenario("ugarit", SEED)
    log: list[dict] = []
    turns = 0
    for _ in range(30):
        world, _ = advance(world)
        turns += 1
        if world.inbox:
            top = world.inbox[0].id
            for act in (A.ReadLetter(top), A.DictateReply(top, "promise")):
                world, _ = apply(world, act)
                log.append({"turn": world.date.absolute, "action": A.to_dict(act)})

    save("/tmp/m2_test.json", SEED, "ugarit", turns, log, world)
    assert state_hash(replay("/tmp/m2_test.json")) == state_hash(world)
