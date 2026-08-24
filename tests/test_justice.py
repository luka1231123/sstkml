"""Court rulings are one visible resource decision."""
from __future__ import annotations

import pytest

from belief.project import project
from engine import actions as A
from engine import seat
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import play, replay, save

SEED = 8814402919


def _world():
    world = load_campaign("seat", SEED)
    return advance(world)[0]


def _petition(world):
    return next(iter(world.court.petitions.values()))


def test_the_docket_shows_both_arguments_and_every_price() -> None:
    shown = project(_world())["justice"]["petitions"][0]
    assert shown["claim_text"] and shown["counter_text"]
    assert set(shown["outcomes"]) == {"for", "against", "split"}
    assert shown["outcomes"]["for"]["amount"] == 9_000
    assert shown["outcomes"]["against"]["amount"] == 3_000
    assert shown["outcomes"]["split"]["amount"] == 6_000
    assert shown["outcomes"]["for"]["unrest"] == -12
    assert not {"heard", "truth", "correct", "precedent"} & shown.keys()


def test_a_ruling_pays_the_named_good_and_changes_unrest_now() -> None:
    world = _world()
    petition = _petition(world)
    copper = seat.held(world)["copper"]
    unrest = world.court.unrest
    world, events = apply(world, A.RulePetition(petition.id, "for"))
    assert seat.held(world)["copper"] == copper - 9_000
    awarded = [lot for lot in world.kernel.book.lots.values()
               if lot.good == "copper" and lot.owner == petition.petitioner]
    assert sum(lot.quantity for lot in awarded) == 9_000
    assert all(lot.holder == petition.petitioner for lot in awarded)
    assert world.court.unrest == max(0, unrest - 12)
    assert petition.id not in world.court.petitions
    ruled = next(event for event in events if isinstance(event, A.PetitionRuled))
    assert (ruled.beneficiary, ruled.good, ruled.amount) == (
        petition.petitioner, "copper", 9_000)


def test_an_unaffordable_ruling_refuses_without_mutating() -> None:
    world = _world()
    stores = seat.held(world)
    stores["copper"] = 0
    world = seat.put(world, stores, reason_down="expended")
    before = state_hash(world)
    with pytest.raises(ValueError, match="does not hold"):
        apply(world, A.RulePetition(_petition(world).id, "for"))
    assert state_hash(world) == before


def test_an_unresolved_petition_carries_a_visible_burden() -> None:
    world = _world()
    assert world.court.unrest == 12
    assert _petition(world).id == "debt_shipwright"


def test_a_ruling_save_replays_exactly(tmp_path) -> None:
    script = [[A.RulePetition("debt_shipwright", "split")]]
    world, log, _ = play(SEED, "seat", script)
    path = tmp_path / "justice.json"
    save(path, SEED, "seat", len(script), log, world)
    assert state_hash(replay(path)) == state_hash(world)
