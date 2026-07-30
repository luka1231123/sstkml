"""Focused contract for the compact, model-first Bronze Age writing desk."""
from __future__ import annotations

import tomllib
from pathlib import Path

from ai.composer import compose as model_compose
from ai.composer import fallback_text
from ai.grader import grade_for
from tui import composer
from tui.grid import plain_text


INTENTS = ("reassure", "refuse", "promise", "warn", "excuse", "request")
PROFILES = (
    ("hatti_king", "hatti.servant_to_lord"),
    ("pharaoh", "peer.equal_to_equal"),
    ("sinaranu", "ugarit.ruler_to_other"),
)


def test_recovery_tablets_are_compact_formulae_not_generic_padding() -> None:
    old_padding = (
        "Nothing in the message has been hidden",
        "My house remembers the hand",
        "Let this writing make my purpose plain",
        "without addition or omission",
        "Thus I have spoken; thus it is written",
    )
    for recipient, profile in PROFILES:
        for intent in INTENTS:
            text = fallback_text(recipient, intent, profile, seed=1, turn=1)
            assert 25 <= len(text.split()) <= 90
            assert 3 <= len(text.splitlines()) <= 6
            assert not any(filler in text for filler in old_padding)
            score = grade_for(text, profile, recipient=recipient)
            assert score.total == 1000
            assert score.topic_count == 1


class _LocalScribe:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def call(self, *_args):
        self.calls += 1
        return self.text


def test_local_scribe_is_the_normal_compose_result_when_guardrails_pass() -> None:
    text = fallback_text(
        "hatti_king", "refuse", "hatti.servant_to_lord", 1, 1)
    client = _LocalScribe(text)
    draft = model_compose(
        "hatti_king", "refuse", {}, seed=1, turn=1, client=client)
    assert draft.source == "model"
    assert draft.text == text
    assert client.calls == 1


def test_small_model_draft_must_keep_recipient_intent_and_physical_size() -> None:
    wrong_intent = fallback_text(
        "hatti_king", "promise", "hatti.servant_to_lord", 1, 1)
    client = _LocalScribe(wrong_intent)
    draft = model_compose(
        "hatti_king", "refuse", {}, seed=1, turn=1, client=client)
    assert client.calls == 2
    assert draft.source == "fallback"
    assert draft.text.startswith("To the Sun, Great King, my lord")
    assert "cannot perform" in draft.text


def test_desk_leads_with_scribes_reading_not_a_numeric_oracle() -> None:
    item = {"sender": "hatti_king", "persona": ""}
    matter = "I cannot grant this demand."
    blocks = composer.default_blocks()
    draft = composer.assemble("hatti_king", blocks, matter)
    text = plain_text(composer.compose(
        item, draft, blocks=blocks, matter=matter))
    assert "YABNINU'S READING" in text
    assert "receive these words as your answer" in text
    assert "Sun above Ugarit" in text
    assert "score" not in text.casefold()
    assert "1000" not in text


def test_desk_exposes_compact_letter_anatomy_and_arrow_controls() -> None:
    item = {
        "sender": "hatti_king",
        "facts": {"troops": 60},
        "topic": "summons",
    }
    matter = "I cannot grant this demand."
    blocks = composer.default_blocks()
    draft = composer.assemble("hatti_king", blocks, matter)
    text = plain_text(composer.compose(
        item, draft, blocks=blocks, matter=matter))

    for part in ("ADDRESS", "RECOGNITION", "MATTER", "SEAL"):
        assert part in text
    assert "POSTURE" not in text
    assert "[↑] block" in text and "[←] choice" in text
    assert "[e] write matter" in text
    assert "[y] Yabninu correct" in text
    assert "PgUp" not in text and "PgDn" not in text


def test_scribes_reading_explains_a_deliberate_breach_in_plain_language() -> None:
    item = {"sender": "hatti_king", "persona": ""}
    draft = composer.dictated("My brother, send grain.", "hatti_king")
    reading = composer.scribe_expects(draft, "request")
    assert "The chosen address may be rejected." in reading
    assert "No bow reaches the feet of the Sun." in reading
    assert "\"Brother\" claims equal rank." in reading

    text = plain_text(composer.compose(item, draft, "request"))
    assert "FORM BREAK ·" in text
    assert "address" in text
    assert "prostration" in text
    assert "of 1000" not in text


def test_letter_blocks_change_forms_without_replacing_the_kings_matter() -> None:
    matter = "I will send the grain already promised."
    blocks = composer.default_blocks()
    court = composer.assemble("hatti_king", blocks, matter)
    blocks["address"] = 2
    blocks["recognition"] = 2
    blocks["seal"] = 1
    brother = composer.assemble("hatti_king", blocks, matter)

    assert matter in court.text and matter in brother.text
    assert "seven times and seven times" in court.text
    assert "my brother" in brother.text
    assert "Your words were heard" not in brother.text
    assert "word of Ammurapi" in brother.text


def test_writing_clay_has_a_wedge_impression_band_not_texture_in_words() -> None:
    item = {"sender": "hatti_king", "topic": "summons"}
    matter = "I cannot grant this demand."
    draft = composer.assemble("hatti_king", None, matter)
    text = plain_text(composer.compose(item, draft, matter=matter))
    assert "╲·╱" in text
    assert matter in text


def test_a_scribe_correction_is_visibly_reversible() -> None:
    item = {"sender": "hatti_king", "topic": "summons"}
    matter = "I cannot grant this demand."
    draft = composer.assemble("hatti_king", None, matter, source="model")
    text = plain_text(composer.compose(
        item, draft, matter=matter, advisor_undo=True))
    assert "WORDS SMOOTHED" in text
    assert "[u] restore my words" in text


def test_the_matter_envelope_is_one_or_two_sentences() -> None:
    assert composer.sentence_count("") == 0
    assert composer.sentence_count("Send grain.") == 1
    assert composer.sentence_count("Send grain. Keep sixty men.") == 2
    assert composer.sentence_count("One. Two. Three.") == 3


def test_outgoing_exemplars_fit_the_same_compact_clay_envelope() -> None:
    path = Path(__file__).parent.parent / "content" / "corpus" / "outgoing.toml"
    letters = tomllib.loads(path.read_text())["letters"]
    assert letters
    assert all(25 <= len(letter["text"].split()) <= 90 for letter in letters)
