"""Focused guards for model-written matter and compact Desk drafts."""
from __future__ import annotations

from ai.client import ModelUnavailable
from ai.composer import compose, correct_matter


class FakeClient:
    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.ai_log: list[dict] = []
        self.calls: list[tuple] = []

    def call(self, *args):
        self.calls.append(args)
        raw = self.replies.pop(0)
        self.ai_log.append({"role": args[0], "raw": raw})
        return raw


def test_semantic_reassurance_is_not_rejected_for_missing_magic_words() -> None:
    text = (
        "To the Sun, Great King, my lord: thus says Ammurapi, your servant.\n"
        "At the feet of my lord, seven times and seven times I fall.\n"
        "I stand firm in loyalty, as the earth stands beneath the sun.\n"
        "My heart is open; your will is heard."
    )
    draft = compose(
        "hatti_king", "reassure", {}, 7, 4, FakeClient([text]))
    assert draft.source == "model"
    assert draft.text == text


def test_matter_correction_uses_model_and_returns_a_small_typed_result() -> None:
    client = FakeClient([
        "Send 200 household troops to Carchemish within 2 fortnights."
    ])
    result = correct_matter(
        "hatti_king",
        "Send 200 household troops to Carchemish in 2 fortnights.",
        7, 4, client,
    )
    assert result.source == "model"
    assert result.text == (
        "Send 200 household troops to Carchemish within 2 fortnights.")
    assert client.calls[0][0] == "matter_corrector"


def test_matter_correction_retries_changed_numbers_then_accepts_exact_terms() -> None:
    client = FakeClient([
        "Send 300 troops to Carchemish within 2 fortnights.",
        "Send 200 troops to Carchemish within 2 fortnights.",
    ])
    result = correct_matter(
        "hatti_king",
        "Send 200 troops to Carchemish within 2 fortnights.",
        7, 4, client,
    )
    assert result.source == "model"
    assert len(client.calls) == 2
    assert client.ai_log[0]["validation_fail"]
    assert "200" in result.text and "300" not in result.text


def test_matter_correction_never_adds_a_promise_during_recovery() -> None:
    original = "The grain did not arrive. Ask why it is late. Record the answer."
    client = FakeClient([
        "The grain did not arrive, but I shall send it tomorrow.",
        "I promise the grain will arrive tomorrow.",
    ])
    result = correct_matter("byblos_king", original, 7, 4, client)
    assert result.source == "fallback"
    assert result.text == (
        "The grain did not arrive. Ask why it is late; Record the answer.")
    assert "shall" not in result.text and "promise" not in result.text


def test_matter_correction_recovers_only_after_true_unavailability() -> None:
    class Unavailable:
        def call(self, *_args):
            raise ModelUnavailable("Ollama is unavailable")

    result = correct_matter(
        "hatti_king", "Refuse the summons.", 7, 4, Unavailable())
    assert result.source == "fallback"
    assert result.text == "Refuse the summons."


def test_matter_correction_can_repair_an_unapostrophized_negation() -> None:
    client = FakeClient([
        "I cannot send 60 men now because the coast is in danger."
    ])
    result = correct_matter(
        "hatti_king",
        "I cant send 60 men now because the coast is in danger",
        7, 4, client,
    )
    assert result.source == "model"
    assert result.text.startswith("I cannot send 60 men")
