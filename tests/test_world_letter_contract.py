"""Phase A contract tests for physical, structured outgoing tablets.

The dispatch cases that pin the seat->ma_hadu harbour road (term records,
death-in-transit, structured gift interception, model-less replay) were
archived to ``tests/archive/mail_dispatch_route_graph.py`` — no route edge
touches ``ma_hadu`` in ``content/world.toml``.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from engine import actions as A
from engine import letter_terms
from engine.state import Letter
from belief.project import project
from engine.reduce import apply
from load import load_campaign


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


def test_letter_term_rejects_structurally_invalid_values() -> None:
    invalid = [
        lambda: A.LetterTerm("unknown"),
        lambda: A.LetterTerm("gift", good="grain", quantity=0),
        lambda: A.LetterTerm("request_good", quantity=2),
        lambda: A.LetterTerm("service", quantity=2),
        lambda: A.LetterTerm("marriage_proposal"),
        lambda: A.LetterTerm("promise_good", good="grain", quantity=-1),
        lambda: A.LetterTerm("promise_good", good="grain", quantity=1,
                             due_turn=-1),
    ]
    for term in invalid:
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


def test_delivery_records_are_idempotent_across_later_turns() -> None:
    world = load_campaign("seat", 8814402919)
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
    later = dataclasses.replace(once, kernel=dataclasses.replace(
        once.kernel, date=once.date.advance()))
    twice, _ = letter_terms.apply_delivered_terms(later, letter)

    assert twice.letter_obligations == once.letter_obligations
    assert twice.letter_claims == once.letter_claims
    assert twice.marriage_proposals == once.marriage_proposals


def test_unread_tablet_contents_do_not_cross_the_belief_boundary() -> None:
    world = load_campaign("seat", 8814402919)
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
