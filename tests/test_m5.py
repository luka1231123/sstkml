"""M5: deterministic protocol, guarded composition, and replayable sent text."""
from __future__ import annotations

import json

from ai.composer import compose, fallback_text, raw_draft, split_draft
from ai.grader import formula, grade, grade_for, load_formulae, profile_for
from ai.numeric_guard import guard
from engine import actions as A
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from session import replay, save
from tools.corpus_lint import lint


def test_good_and_bad_hatti_protocol():
    data = load_formulae()
    rule = formula(data, "hatti.servant_to_lord")
    good = fallback_text("hatti_king", "promise", "hatti.servant_to_lord", 1, 1)
    score = grade(good.replace("\n", "\r\n"), rule, data["weights"])
    assert score.total == 1000
    assert score.address_ok and score.prostration_ok and score.self_designation_ok

    bad = ("To my brother. Because the sea closed, I ask you to send me grain "
           "under my oath.")
    score = grade(bad, rule, data["weights"])
    assert score.total == 0
    assert score.violations == (
        "wrong_address", "missing_prostration", "missing_self_designation",
        "kinship_overreach", "multi_topic", "excuse_and_request",
        "wrong_oath_gods",
    )


def test_address_is_bound_to_the_actual_recipient():
    text = fallback_text(
        "alashiya_gov", "reassure", "ugarit.ruler_to_other", 1, 1)
    assert grade_for(
        text, "ugarit.ruler_to_other", recipient="alashiya_gov").address_ok
    assert not grade_for(
        text, "ugarit.ruler_to_other", recipient="sinaranu").address_ok


def test_outgoing_corpus_is_clean():
    assert lint() == []


class _GuardFailClient:
    def __init__(self):
        self.calls = 0
        self.ai_log = []

    def call(self, *args):
        self.calls += 1
        self.messages = args[1]
        raw = "To the king: I have ninety-nine ships."
        self.ai_log.append({"raw": raw})
        return raw


def test_composer_retries_numeric_failure_then_falls_back():
    client = _GuardFailClient()
    draft = compose("hatti_king", "promise", {"ships": 4}, 1, 1, client)
    assert client.calls == 2
    assert all(entry["guard_fail"] for entry in client.ai_log)
    assert draft.source == "fallback"
    assert guard(draft.text, {"seven"})[0]
    assert draft.score.total == 1000

    # Free-form intent is not an engine fact and cannot license a quantity.
    client = _GuardFailClient()
    safe = compose("hatti_king", "promise ninety-nine ships", {}, 1, 1, client)
    assert client.calls == 2
    assert guard(safe.text, {"seven"})[0]

    peer = _GuardFailClient()
    compose("pharaoh", "reassure", {}, 1, 1, peer)
    prompt = peer.messages[1]["content"]
    assert "{recipient}" not in prompt and "Pharaoh, the Sun" in prompt


def test_player_text_is_exact_and_can_outperform_scribe():
    omitted = fallback_text(
        "hatti_king", "promise", "hatti.servant_to_lord", seed=5, turn=0)
    assert grade_for(omitted, "hatti.servant_to_lord").total < 1000
    correct = fallback_text(
        "hatti_king", "promise", "hatti.servant_to_lord", seed=1, turn=1)
    raw = raw_draft(correct + "\n", "hatti_king")
    assert raw.text == correct + "\n"
    assert raw.score.total == 1000
    assert 10 <= len(omitted.splitlines()) <= 18


def test_multi_topic_draft_can_split_into_two_tablets():
    text = fallback_text(
        "hatti_king", "warn", "hatti.servant_to_lord", 1, 1)
    text += "\nI ask my lord to send me grain."
    draft = raw_draft(text, "hatti_king")
    assert draft.score.topic_count == 2
    parts = split_draft(draft, "hatti_king")
    assert len(parts) == 2
    assert all(part.text.startswith("To the Sun") for part in parts)


def test_reply_text_round_trips_and_replays_without_model():
    seed = 8814402919
    world = load_scenario("ugarit", seed)
    turns = 0
    while not world.inbox:
        world, _ = advance(world)
        turns += 1
    letter = world.inbox[0]
    profile = profile_for(letter.sender)
    text = fallback_text(letter.sender, "promise", profile, seed, world.date.absolute)
    score = grade_for(text, profile, recipient=letter.sender)
    action = A.DictateReply(
        letter.id, "promise", text, profile, score.total, score.violations)
    before = world
    world, _ = apply(world, action)
    log = [{"turn": world.date.absolute, "action": A.to_dict(action)}]
    path = "/tmp/m5_replay.json"
    save(path, seed, "ugarit", turns, log, world)

    encoded = json.loads(open(path).read())["log"][0]["action"]
    assert encoded["text"] == text and encoded["profile"] == profile
    assert "score" not in encoded
    assert encoded["protocol_total"] == score.total
    assert state_hash(replay(path)) == state_hash(world)
    assert world.protocol_log[-1].total == score.total

    bad_text = "To the wrong king. I ask for aid because the sea is closed."
    bad_score = grade_for(bad_text, profile, recipient=letter.sender)
    bad_action = A.DictateReply(
        letter.id, "promise", bad_text, profile,
        bad_score.total, bad_score.violations)
    bad_world, _ = apply(before, bad_action)
    assert state_hash(bad_world) != state_hash(world)

    tampered = json.loads(open(path).read())
    tampered["log"][0]["action"]["text"] = bad_text
    tampered_path = "/tmp/m5_tampered.json"
    open(tampered_path, "w").write(json.dumps(tampered))
    try:
        replay(tampered_path)
    except ValueError as exc:
        assert "protocol grade divergence" in str(exc)
    else:
        raise AssertionError("tampered protocol text should fail replay")

    # Saves made before M5 still decode through the new default fields.
    old = A.from_dict({"_t": "DictateReply", "letter_id": "L1", "intent": "warn"})
    assert old.text == old.profile == ""
