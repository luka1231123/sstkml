"""State-driven correspondence does not turn cadence into duplicate tablets."""
from __future__ import annotations

from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario

SEED = 8814402919


def _advance(world, turns: int):
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _matter(world, sender: str, topic: str):
    return [
        letter for letter in world.inbox + world.letters_in_transit
        if not letter.outgoing and letter.sender == sender
        and letter.topic == topic
    ]


def test_an_unchanged_unanswered_matter_has_one_active_tablet() -> None:
    world = _advance(load_scenario("ugarit", SEED), 30)
    tablets = _matter(world, "alashiya_gov", "ships_sighted")
    assert len(tablets) == 1
    assert tablets[0].answered_turn is None


def test_answering_allows_the_sender_to_raise_the_matter_again() -> None:
    world = load_scenario("ugarit", SEED)
    while not any(
        letter.sender == "alashiya_gov" and letter.topic == "ships_sighted"
        for letter in world.inbox
    ):
        world, _ = advance(world)
    first = next(
        letter for letter in world.inbox
        if letter.sender == "alashiya_gov"
        and letter.topic == "ships_sighted"
    )
    world, _ = apply(world, A.ReadLetter(first.id))
    world, _ = apply(world, A.DictateReply(first.id, "refuse"))
    world = _advance(world, 8)
    assert len(_matter(world, "alashiya_gov", "ships_sighted")) >= 2
    assert any(letter.id != first.id for letter in _matter(
        world, "alashiya_gov", "ships_sighted"))


def test_a_long_unattended_court_stays_a_pile_not_a_landfill() -> None:
    world = _advance(load_scenario("ugarit", SEED), 96)
    active = [letter for letter in world.inbox if not letter.archived]
    assert len(active) <= 80
