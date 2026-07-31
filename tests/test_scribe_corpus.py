"""The historical corpus and the scribe's instructions hold together."""
from __future__ import annotations

import tomllib
from pathlib import Path

from ai import composer
from ai.grader import grade_for, load_formulae, formula

CONTENT = Path(__file__).parent.parent / "content"
LETTERS = tomllib.loads(
    (CONTENT / "corpus" / "historical.toml").read_text())["letters"]
PROMPT = tomllib.loads((CONTENT / "scribe_prompt.toml").read_text())


def test_every_exemplar_obeys_the_register_it_demonstrates():
    for letter in LETTERS:
        score = grade_for(letter["text"], letter["profile"],
                          recipient=letter["recipient"])
        assert score.total == 1000, (letter["id"], score.violations)
        assert 25 <= len(letter["text"].split()) <= 90, letter["id"]


def test_the_corpus_covers_every_register_and_names_its_source():
    directions = {letter["direction"] for letter in LETTERS}
    assert directions == {"up", "level", "down"}
    for letter in LETTERS:
        assert letter["source"] and letter["convention"] and letter["note"]


def test_the_scribe_is_shown_rules_his_rank_and_worked_pairs():
    for recipient, direction in (("hatti_king", "up"),
                                 ("pharaoh", "level"),
                                 ("overseer_royal_lands", "down")):
        messages = composer.scribe_messages(recipient, "send him the grain")
        assert messages[0]["role"] == "system"
        assert PROMPT["rank"][direction]["text"] in messages[0]["content"]
        pairs = [m for m in messages[1:-1]]
        assert pairs and len(pairs) % 2 == 0
        assert messages[-1]["content"].endswith("send him the grain")


def test_the_worked_pairs_never_change_a_number_or_a_name():
    for pair in PROMPT["examples"]:
        rough_numbers = composer._number_multiset(pair["rough"])
        formatted = composer._number_multiset(pair["formatted"])
        # The pairs are written with number words on one side and figures on
        # the other; the guard normalises both, so they must agree.
        assert rough_numbers == formatted, pair["rough"]


def test_a_downward_tablet_carries_no_wish_for_the_officers_health():
    rule = formula(load_formulae(), "ugarit.lord_to_servant")
    assert rule["wellbeing_forbidden"]
    text = composer.fallback_text(
        "overseer_royal_lands", "promise", "ugarit.lord_to_servant", 1, 1)
    score = grade_for(text, "ugarit.lord_to_servant",
                      recipient="overseer_royal_lands")
    assert "wellbeing_downward" not in score.violations
