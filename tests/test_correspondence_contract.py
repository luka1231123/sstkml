"""The frozen contract for a foreign court's answer (SPEC.md 6.1 phase B).

These tests belong to the boundary rather than to any one system: they say what
a case is, who may decide, what a decision may contain, and that the whole chain
replays. The behaviour behind the boundary -- which court refuses, what the
refusal costs, how the reply reads -- is tested beside the modules that own it.
"""
from __future__ import annotations

import inspect

import pytest

from engine import actions as A
from engine import correspondence_policy as P
from engine import foreign_belief, mail, tick
from engine.state import CorrespondenceCase
from load import load_scenario
from session import play


def _world(turns: int = 1):
    world = load_scenario("ugarit", 1)
    for _ in range(turns):
        world, _ = tick.advance(world)
    return world


def _dispatch(world, recipient: str = "pharaoh", quantity: int = 50000):
    place = world.foreign_courts[recipient].place
    path = mail.shortest_path(world.routes, world.court.seat, place)
    from ai.grader import profile_for
    return A.DispatchLetter(
        recipient=recipient, reply_to="", text="Send grain, my brother.",
        profile=profile_for(recipient),
        terms=(A.LetterTerm(kind="request_good", good="grain",
                            quantity=quantity, due_turn=40),),
        scribe_id="yabninu", seal="royal", courier_id="courier_1", path=path)


def _run(world, turns: int):
    for _ in range(turns):
        world, _ = tick.advance(world)
    return world


# --- the case ----------------------------------------------------------------

def test_authored_foreign_courts_stand_where_they_write():
    world = _world()
    assert world.foreign_courts, "the scenario authors no foreign court"
    for actor, court in world.foreign_courts.items():
        assert court.place in world.places
        assert world.relations[actor].place == court.place


def test_delivery_opens_exactly_one_case_with_dated_claims():
    world = _world()
    world, _ = mail.apply_dispatch(world, _dispatch(world))
    world = _run(world, 12)
    cases = [case for case in world.correspondence
             if case.actor == "pharaoh"]
    assert len(cases) == 1
    case = cases[0]
    assert case.terms and case.terms[0].kind == "request_good"
    belief = foreign_belief.belief_of(world, "pharaoh")
    about = belief.about(case.letter_id)
    assert about, "the delivered terms left no claim behind"
    for claim in about:
        assert claim.source == "reported"
        assert claim.chain, "a reported claim names who carried it"
        assert claim.observed_turn <= case.received_turn


def test_a_replayed_delivery_opens_no_second_case():
    world = _world()
    world, _ = mail.apply_dispatch(world, _dispatch(world))
    world = _run(world, 12)
    letter = next(case.letter_id for case in world.correspondence)
    before = len(world.correspondence)
    delivered = next(
        (item for item in world.documents if item.ref == f"L-{letter}"), None)
    assert delivered is not None, "the sealed copy was never filed"
    again, _ = foreign_belief.receive(
        world, type("L", (), {"id": letter, "recipient": "pharaoh",
                              "terms": (), "sent_turn": 0,
                              "courier_id": ""})())
    assert len(again.correspondence) == before


# --- the decision ------------------------------------------------------------

def test_a_policy_is_handed_no_world():
    parameters = set(inspect.signature(P.decide).parameters)
    assert parameters == {"actor", "belief", "case", "turn"}
    body = inspect.getsource(P.decide).split('"""')[-1]
    assert "world" not in body, "a decision may not read World"


def test_an_unregistered_decision_is_refused():
    with pytest.raises(ValueError):
        CorrespondenceCase(
            id="C1", letter_id="L1", actor="pharaoh", place="egypt",
            received_turn=1, decision="perhaps", decided_turn=1)


def test_counter_terms_belong_only_to_a_counter():
    with pytest.raises(ValueError):
        CorrespondenceCase(
            id="C1", letter_id="L1", actor="pharaoh", place="egypt",
            received_turn=1, decision="refuse", decided_turn=1,
            counter_terms=(A.LetterTerm(
                kind="promise_good", good="grain", quantity=10, due_turn=9),))


def test_a_decision_happens_on_a_turn():
    with pytest.raises(ValueError):
        CorrespondenceCase(
            id="C1", letter_id="L1", actor="pharaoh", place="egypt",
            received_turn=1, decision="accept")


def test_a_court_that_can_spare_nothing_refuses():
    world = _world()
    world, _ = mail.apply_dispatch(
        world, _dispatch(world, "alashiya_gov", 39000))
    world = _run(world, 14)
    case = next(case for case in world.correspondence
                if case.actor == "alashiya_gov")
    assert case.decision in {"refuse", "counter"}
    assert case.basis, "a refusal names the claims behind it"


# --- the reply ---------------------------------------------------------------

def test_an_answered_case_puts_a_tablet_on_the_road_home():
    world = _world()
    world, _ = mail.apply_dispatch(world, _dispatch(world))
    world = _run(world, 12)
    case = next(case for case in world.correspondence)
    assert case.decision, "no answer after the tablet arrived"
    assert case.reply_letter_id
    world = _run(world, 10)
    reply = next(
        (letter for letter in world.inbox
         if letter.id == case.reply_letter_id), None)
    assert reply is not None
    assert reply.sender == case.actor
    assert reply.reply_to == case.letter_id
    assert not reply.outgoing


def test_the_engine_writes_facts_and_never_prose():
    world = _world()
    world, _ = mail.apply_dispatch(world, _dispatch(world))
    world = _run(world, 22)
    replies = [letter for letter in world.inbox
               if letter.topic.startswith("reply_")]
    assert replies
    for letter in replies:
        assert letter.text == "", "engine composed prose for a foreign court"
        assert dict(letter.facts).get("decision") in {
            "accept", "refuse", "counter"}


# --- replay ------------------------------------------------------------------

def test_an_accepted_reading_is_kept_and_never_rewritten():
    from engine.reduce import apply

    world = _world()
    world, _ = mail.apply_dispatch(world, _dispatch(world))
    world = _run(world, 22)
    case = next(case for case in world.correspondence if case.reply_letter_id)
    assert case.reply_text == "", "prose existed before anyone read it out"

    world, _ = apply(world, A.RecordReplyText(
        case.reply_letter_id, "Thus says Pharaoh: the grain will go."))
    kept = next(item for item in world.correspondence if item.id == case.id)
    assert kept.reply_text.startswith("Thus says Pharaoh")

    # A second reading does not overwrite the tablet the king already holds.
    world, _ = apply(world, A.RecordReplyText(
        case.reply_letter_id, "Thus says Pharaoh: no grain will go."))
    again = next(item for item in world.correspondence if item.id == case.id)
    assert again.reply_text == kept.reply_text


def _answered_script(turns: int = 26):
    """A script whose one dispatch survived its road, and the case it opened.

    Every road out of Ugarit carries interception risk, and which fortnight a
    courier is taken on is a property of the seed and the turn. So the sealing
    turn is searched rather than assumed -- deterministically, first tablet that
    arrives wins -- because a test about stored words should not also be a test
    about a lucky crossing.
    """
    reference = load_scenario("ugarit", 1)
    reference, _ = tick.advance(reference)
    dispatch = _dispatch(reference)
    for sealed in range(1, 8):
        script: list[list] = [[] for _ in range(turns)]
        script[sealed] = [dispatch]
        played, _log, _hashes = play(1, "ugarit", script)
        case = next((item for item in played.correspondence
                     if item.reply_letter_id), None)
        if case is not None:
            return script, case
    raise AssertionError("no tablet reached Egypt in the first eight fortnights")


