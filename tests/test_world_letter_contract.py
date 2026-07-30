"""Phase A contract tests for physical, structured outgoing tablets."""
from __future__ import annotations

import dataclasses
import json

import pytest

from engine import actions as A
from engine import letter_terms
from engine import mail
from engine.core import state_hash
from engine.state import Letter
from belief.project import project
from engine.reduce import apply
from load import load_scenario
from session import load_session, play, save
from tools import m13_audit


def _dispatch() -> A.DispatchLetter:
    return A.DispatchLetter(
        recipient="hatti_king",
        reply_to="L7",
        text="My lord, the grain will be sent after the threshing.",
        profile="hatti.servant_to_lord",
        terms=(
            A.LetterTerm(
                "promise_good", good="grain", quantity=30, due_turn=9),
            A.LetterTerm(
                "service", quantity=12, destination="carchemish"),
        ),
        scribe_id="yabninu",
        seal="royal",
        courier_id="iliya",
        path=("ugarit", "carchemish", "hattusa"),
    )


def test_dispatch_round_trips_nested_terms_through_json() -> None:
    action = _dispatch()
    encoded = A.to_dict(action)
    wire = json.loads(json.dumps(encoded))
    decoded = A.from_dict(wire)

    assert decoded == action
    assert all(isinstance(term, A.LetterTerm) for term in decoded.terms)
    assert encoded["text"] == action.text
    assert encoded["terms"][0]["_t"] == "LetterTerm"


def test_legacy_flat_action_still_decodes_with_defaults() -> None:
    old = A.from_dict({
        "_t": "DictateReply",
        "letter_id": "L1",
        "intent": "warn",
    })
    assert old == A.DictateReply("L1", "warn")
    assert A.from_dict(json.loads(json.dumps(A.to_dict(old)))) == old


@pytest.mark.parametrize(
    "term",
    [
        lambda: A.LetterTerm("unknown"),
        lambda: A.LetterTerm("gift", good="grain", quantity=0),
        lambda: A.LetterTerm("request_good", quantity=2),
        lambda: A.LetterTerm("service", quantity=2),
        lambda: A.LetterTerm("marriage_proposal"),
        lambda: A.LetterTerm("promise_good", good="grain", quantity=-1),
        lambda: A.LetterTerm("promise_good", good="grain", quantity=1,
                             due_turn=-1),
    ],
)
def test_letter_term_rejects_structurally_invalid_values(term) -> None:
    with pytest.raises(ValueError):
        term()


def test_dispatch_requires_exact_text_route_and_material_provenance() -> None:
    values = {
        "recipient": "hatti_king",
        "reply_to": "",
        "text": "I have heard your words.",
        "profile": "hatti.servant_to_lord",
        "terms": (),
        "scribe_id": "yabninu",
        "seal": "royal",
        "courier_id": "iliya",
        "path": ("ugarit", "hattusa"),
    }
    for field in (
        "recipient", "text", "profile", "scribe_id", "seal", "courier_id",
    ):
        broken = dict(values)
        broken[field] = ""
        with pytest.raises(ValueError, match=field):
            A.DispatchLetter(**broken)
    with pytest.raises(ValueError, match="route"):
        A.DispatchLetter(**{**values, "path": ()})
    with pytest.raises(TypeError, match="LetterTerm"):
        A.DispatchLetter(**{**values, "terms": (object(),)})


def test_existing_letter_construction_gets_empty_outgoing_contract_fields() -> None:
    letter = Letter(
        id="L1",
        sender="alashiya_gov",
        recipient="ugarit_king",
        topic="copper",
        facts=(("copper", 20),),
        sent_turn=1,
        path=("alashiya", "ugarit"),
        edge_index=0,
        legs_into_edge=0,
        at_node="alashiya",
    )
    assert letter.text == ""
    assert letter.terms == ()
    assert letter.reply_to == ""
    assert letter.scribe_id == letter.seal == letter.courier_id == ""


def test_dispatch_and_delivery_persist_term_records() -> None:
    world = load_scenario("ugarit", 8814402919)
    world = dataclasses.replace(
        world,
        routes=tuple(dataclasses.replace(route, risk=0)
                     for route in world.routes),
    )
    action = A.DispatchLetter(
        recipient="sinaranu",
        reply_to="",
        text="Receive this oil; send grain; hear the proposed union.",
        profile="ugarit.ruler_to_other",
        terms=(
            A.LetterTerm("gift", good="oil", quantity=3),
            A.LetterTerm("request_good", good="grain", quantity=20),
            A.LetterTerm("marriage_proposal", person_id="pidray"),
        ),
        scribe_id="yabninu",
        seal="royal",
        courier_id="iliya",
        path=("seat", "ma_hadu"),
    )
    opening = world.court.stores["oil"]

    sent, _ = mail.apply_dispatch(world, action)
    assert sent.court.stores["oil"] == opening - 3
    assert len(sent.letter_reservations) == 1
    assert not sent.letter_claims
    assert not sent.marriage_proposals

    delivered, _ = mail.step_letters(sent)
    assert delivered.letter_reservations[0].status == "delivered"
    assert delivered.letter_claims[0].source_letter == "L1"
    assert delivered.marriage_proposals[0].person_id == "pidray"
    assert delivered.court.house["pidray"].spouse is None


def test_dispatch_action_replays_without_a_model(tmp_path) -> None:
    from ai.grader import profile_for

    action = A.DispatchLetter(
        recipient="sinaranu",
        reply_to="",
        text="To Sinaranu: receive these words exactly.",
        profile=profile_for("sinaranu"),
        terms=(A.LetterTerm("gift", good="oil", quantity=2),),
        scribe_id="yabninu",
        seal="royal",
        courier_id="iliya",
        path=("seat", "ma_hadu"),
    )
    world, log, _hashes = play(8814402919, "ugarit", [[action]])
    path = tmp_path / "dispatch.json"
    save(path, 8814402919, "ugarit", 1, log, world)

    replayed, data = load_session(path)
    assert state_hash(replayed) == state_hash(world)
    assert data["log"][0]["action"]["terms"][0]["_t"] == "LetterTerm"


def test_death_in_transit_lapses_proposal_without_stopping_delivery() -> None:
    world = load_scenario("ugarit", 8814402919)
    world = dataclasses.replace(
        world,
        routes=tuple(dataclasses.replace(route, risk=0)
                     for route in world.routes),
    )
    action = A.DispatchLetter(
        "sinaranu", "", "I propose this union.",
        "ugarit.ruler_to_other",
        (A.LetterTerm("marriage_proposal", person_id="pidray"),),
        "yabninu", "royal", "iliya", ("seat", "ma_hadu"),
    )
    sent, _ = mail.apply_dispatch(world, action)
    person = sent.court.house["pidray"]
    sent = dataclasses.replace(
        sent,
        court=dataclasses.replace(
            sent.court,
            house={
                **sent.court.house,
                "pidray": dataclasses.replace(
                    person, alive=False, died_turn=sent.date.absolute),
            },
        ),
    )

    delivered, events = mail.step_letters(sent)
    assert any(isinstance(event, A.LetterDelivered) for event in events)
    assert delivered.marriage_proposals[0].status == "lapsed"
    assert delivered.court.house["pidray"].spouse is None


def test_delivery_records_are_idempotent_across_later_turns() -> None:
    world = load_scenario("ugarit", 8814402919)
    letter = Letter(
        id="L-repeat",
        sender=world.court.actor,
        recipient="sinaranu",
        topic="terms",
        facts=(),
        sent_turn=world.date.absolute,
        path=("seat", "ma_hadu"),
        edge_index=1,
        legs_into_edge=0,
        at_node="ma_hadu",
        outgoing=True,
        terms=(
            A.LetterTerm("request_good", good="grain", quantity=7),
            A.LetterTerm(
                "promise_good", good="oil", quantity=3, due_turn=9),
            A.LetterTerm("marriage_proposal", person_id="pidray"),
        ),
    )
    reserved = letter_terms.reserve_terms_at_dispatch(world, letter).world
    once, _ = letter_terms.apply_delivered_terms(reserved, letter)
    later = dataclasses.replace(once, date=once.date.advance())
    twice, _ = letter_terms.apply_delivered_terms(later, letter)

    assert twice.letter_obligations == once.letter_obligations
    assert twice.letter_claims == once.letter_claims
    assert twice.marriage_proposals == once.marriage_proposals


def test_unread_tablet_contents_do_not_cross_the_belief_boundary() -> None:
    world = load_scenario("ugarit", 8814402919)
    letter = Letter(
        id="L-sealed",
        sender="sinaranu",
        recipient=world.court.actor,
        topic="request",
        facts=(("hidden_amount", 777),),
        sent_turn=0,
        path=("ma_hadu", "seat"),
        edge_index=1,
        legs_into_edge=0,
        at_node="seat",
        arrive_turn=0,
        text="Send seven hundred and seventy-seven measures.",
        terms=(A.LetterTerm(
            "request_good", good="grain", quantity=777),),
    )
    world = dataclasses.replace(world, inbox=world.inbox + (letter,))

    sealed = next(item for item in project(world)["stack"]
                  if item["id"] == letter.id)
    assert sealed["facts"] == {}
    assert sealed["terms"] == []
    assert sealed["body"] == ""

    opened, _ = apply(world, A.ReadLetter(letter.id))
    read = next(item for item in project(opened)["stack"]
                if item["id"] == letter.id)
    assert read["facts"]["hidden_amount"]
    assert read["terms"][0]["quantity"] == 777
    assert read["body"] == letter.text


def test_structured_gift_has_material_evidence_and_hidden_interception() -> None:
    world = load_scenario("ugarit", 8814402919)
    routes = tuple(
        dataclasses.replace(
            route,
            risk=(1000 if {route.a, route.b} == {"seat", "ma_hadu"} else 0),
        )
        for route in world.routes
    )
    world = dataclasses.replace(world, routes=routes)
    action = A.DispatchLetter(
        "sinaranu", "", "Receive this oil.", "ugarit.ruler_to_other",
        (A.LetterTerm("gift", good="oil", quantity=3),),
        "yabninu", "royal", "iliya", ("seat", "ma_hadu"),
    )

    after, events = mail.apply_dispatch(world, action)
    findings = m13_audit.audit_transition(world, after, events)
    assert not [item for item in findings if item.path == "stores.oil"]
    assert any(isinstance(event, A.GiftSent) for event in events)
    assert any(isinstance(event, A.LetterIntercepted) for event in events)
    assert after.letter_reservations[0].status == "intercepted"
    assert not after.letters_in_transit
    sent_copy = next(item for item in project(after)["outbox"]
                     if item["recipient"] == "sinaranu")
    assert sent_copy["status"] == "sent — no receipt"
