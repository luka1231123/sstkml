"""Gifts and marriages enter new play only as terms on physical letters."""
from __future__ import annotations

import inspect

import pytest

import play_cli
import registry
from ai import parser
from belief.project import project
from engine import actions as A
from engine import house, relations
from engine.reduce import apply
from load import load_scenario


SEED = 8_814_402_919
LEGACY_TYPES = (A.SendGift, A.MarryAbroad)


def _belief() -> dict:
    return project(load_scenario("ugarit", SEED))


def test_legacy_descriptors_keep_compatibility_but_leave_player_contexts():
    gift = registry.BY_ID["send_gift"]
    marriage = registry.BY_ID["marry_abroad"]

    assert gift.action_type is A.SendGift
    assert marriage.action_type is A.MarryAbroad
    assert gift.player_accessible is False
    assert marriage.player_accessible is False
    assert registry.describe(A.SendGift("hatti_king", "oil", 1)) is gift
    assert registry.describe(A.MarryAbroad("pidray", "hatti_king")) is marriage
    assert registry.cost_of(A.SendGift("hatti_king", "oil", 1)) == gift.cost
    assert registry.cost_of(
        A.MarryAbroad("pidray", "hatti_king")) == marriage.cost

    player_types = {
        descriptor.action_type
        for descriptor in registry.player_descriptors()
    }
    assert not player_types.intersection(LEGACY_TYPES)
    assert all(
        descriptor.action_type not in LEGACY_TYPES
        for context in registry.contexts()
        for descriptor in registry.in_context(context)
    )


def test_legacy_diplomacy_phrases_redirect_to_world_and_desk():
    phrases = (
        "gift hatti_king copper 10",
        "send 10 copper to hatti_king",
        "marry pidray to hatti_king",
        "send pidray into the court of hatti_king",
    )
    for words in phrases:
        belief = _belief()

        quick = parser.preparse(words, belief)
        assert quick is not None
        assert quick.actions == ()
        assert quick.question == parser.LETTER_ONLY_DIPLOMACY
        assert "World" in quick.question
        assert "Desk" in quick.question

        class ModelMustNotBeCalled:
            def call(self, *_args, **_kwargs):
                raise AssertionError(
                    "legacy diplomacy should be caught locally")

        parsed = parser.parse(
            words, belief, hours_left=8, seed=SEED, turn=0,
            client=ModelMustNotBeCalled(),
        )
        assert parsed.actions == ()
        assert parsed.question == parser.LETTER_ONLY_DIPLOMACY


def test_model_action_decoder_has_no_legacy_diplomacy_verb():
    for verb in ("SEND_GIFT", "MARRY_ABROAD"):
        assert verb not in parser.VERBS
        with pytest.raises(ValueError, match="unknown action"):
            parser._action({"verb": verb, "args": {}}, _belief())


def test_terminal_mutation_funnel_refuses_legacy_diplomacy():
    actions = (
        A.SendGift("hatti_king", "oil", 1),
        A.MarryAbroad("pidray", "hatti_king"),
    )
    for action in actions:
        with pytest.raises(ValueError) as refused:
            play_cli._guard_player_action(action)

        assert str(refused.value) == parser.LETTER_ONLY_DIPLOMACY
        assert "World" in play_cli.HELP
        assert "Desk" in play_cli.HELP

    # The exact colon-command branches may explain the replacement workflow,
    # but must not retain a hidden direct commit around the central guard.
    source = inspect.getsource(play_cli.run)
    assert "commit(A.SendGift" not in source
    assert "commit(A.MarryAbroad" not in source


def test_legacy_log_records_still_decode_and_reach_reduce():
    marker = object()
    seen = []
    real_send_gift = relations.send_gift
    real_marry_abroad = house.marry_abroad

    def replay_gift(world, action):
        seen.append((world, action))
        return world, ["gift replayed"]

    def replay_marriage(world, person_id, actor):
        seen.append((world, person_id, actor))
        return world, ["marriage replayed"]

    relations.send_gift = replay_gift
    house.marry_abroad = replay_marriage
    try:
        gift = A.from_dict({
            "_t": "SendGift",
            "recipient": "hatti_king",
            "good": "oil",
            "quantity": 10,
        })
        marriage = A.from_dict({
            "_t": "MarryAbroad",
            "person_id": "pidray",
            "actor": "hatti_king",
        })

        assert apply(marker, gift) == (marker, ["gift replayed"])
        assert apply(marker, marriage) == (marker, ["marriage replayed"])
        assert seen == [
            (marker, gift),
            (marker, "pidray", "hatti_king"),
        ]
    finally:
        relations.send_gift = real_send_gift
        house.marry_abroad = real_marry_abroad
