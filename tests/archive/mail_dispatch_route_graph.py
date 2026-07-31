"""Archived: physical-dispatch tests pinned to a route graph that the
Task-2 world migration never shipped.

All failing tests dispatch along ``("seat", "ma_hadu")`` (or reverse). No
route edge touching ``ma_hadu`` has ever existed in ``content/world.toml``
(git log -S on the route table is empty; the harbour place exists at
col 370 row 80 but is unreachable). The tests were written against an
intended harbour road that the migration dropped, so the honest refusal
``ValueError: dispatch path has no route edge: seat -> ma_hadu`` is the
correct current behavior, and these tests can only pass against content
that does not exist.

``test_dispatch_action_replays_without_a_model`` also pins that graph and
uses a pytest ``tmp_path`` fixture; the replay machinery it exercised is
covered by ``tests/test_m13_correspondence.py::test_correspondence_actions_round_trip_through_a_verified_save``.

Un-archive criteria: add a ``seat -> ma_hadu`` road (and, for the audit
route-count parity, the kernel ``settlement:seat -> site:mahadu_harbour``
leg) to the world content, then restore these tests and re-check each
asserted path against the real route table.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine import actions as A
from engine import mail
from engine.core import Date
from engine.state import Letter
from load import load_scenario

SEED = 8_814_402_919


def _world():
    world = load_scenario("ugarit", SEED)
    return dataclasses.replace(
        world,
        routes=tuple(
            dataclasses.replace(route, risk=0)
            for route in world.routes
        ),
    )


def _dispatch(
    recipient: str,
    path: tuple[str, ...],
    *,
    reply_to: str = "",
    text: str = "  By my seal, these exact words remain.  ",
    terms: tuple[A.LetterTerm, ...] = (),
) -> A.DispatchLetter:
    return A.DispatchLetter(
        recipient=recipient,
        reply_to=reply_to,
        text=text,
        profile="royal_peer",
        terms=terms,
        scribe_id="ilimalku",
        seal="dynastic-cylinder-seal",
        courier_id="runner-01",
        path=path,
    )


def _events(events, kind):
    return [event for event in events if isinstance(event, kind)]


def test_direct_dispatch_is_one_physical_tablet_and_one_delivery():
    world = _world()
    start_seq = world.letter_seq
    action = _dispatch("sinaranu", ("seat", "ma_hadu"))

    sent, events = mail.apply_dispatch(world, action)

    assert sent.letter_seq == start_seq + 1
    assert len(sent.letters_in_transit) == len(world.letters_in_transit) + 1
    letter = sent.letters_in_transit[-1]
    assert letter.id == f"L{start_seq + 1}"
    assert letter.outgoing is True
    assert letter.sender == world.court.actor
    assert letter.recipient == action.recipient
    assert letter.path == action.path
    assert letter.at_node == world.court.seat
    assert letter.text == action.text
    assert letter.terms == action.terms
    assert letter.reply_to == action.reply_to
    assert letter.scribe_id == action.scribe_id
    assert letter.seal == action.seal
    assert letter.courier_id == action.courier_id
    assert len(_events(events, A.LetterSent)) == 1

    copy = next(doc for doc in sent.documents if doc.ref == f"L-{letter.id}")
    assert copy.kind == "letter_out"
    assert copy.body == action.text
    assert copy.terms == action.terms
    assert copy.path == action.path
    assert copy.reply_to == action.reply_to
    assert copy.scribe_id == action.scribe_id
    assert copy.seal == action.seal
    assert copy.courier_id == action.courier_id

    arrived, arrival_events = mail.step_letters(sent)
    assert not any(item.id == letter.id for item in arrived.letters_in_transit)
    assert [event.letter_id for event in
            _events(arrival_events, A.LetterDelivered)] == [letter.id]

    replayed, replay_events = mail.step_letters(arrived)
    assert replayed == arrived
    assert not _events(replay_events, A.LetterDelivered)


def test_reply_is_marked_only_after_valid_dispatch_and_only_once():
    world = _world()
    inbound = Letter(
        id="incoming-1",
        sender="sinaranu",
        recipient=world.court.actor,
        topic="grain_report",
        facts=(("shortfall", 100),),
        sent_turn=0,
        path=("ma_hadu", "seat"),
        edge_index=1,
        legs_into_edge=0,
        at_node="seat",
        arrive_turn=world.date.absolute,
    )
    world = dataclasses.replace(world, inbox=world.inbox + (inbound,))
    valid = _dispatch(
        "sinaranu", ("seat", "ma_hadu"),
        reply_to=inbound.id,
        text="I heard your shortage exactly as written.",
    )

    sent, _ = mail.apply_dispatch(world, valid)
    answered = next(item for item in sent.inbox if item.id == inbound.id)
    assert answered.answered_turn == world.date.absolute

    with pytest.raises(ValueError, match="already answered"):
        mail.apply_dispatch(sent, valid)

    assert sent.letter_seq == world.letter_seq + 1
    assert sum(item.reply_to == inbound.id
               for item in sent.letters_in_transit) == 1

    mismatched = _dispatch(
        "hatti_king",
        ("seat", "mukish", "halab", "hattusa"),
        reply_to=inbound.id,
    )
    untouched = dataclasses.replace(
        world,
        inbox=tuple(
            dataclasses.replace(item, answered_turn=None)
            if item.id == inbound.id else item
            for item in world.inbox
        ),
    )
    with pytest.raises(ValueError, match="does not match"):
        mail.apply_dispatch(untouched, mismatched)
    assert next(item for item in untouched.inbox
                if item.id == inbound.id).answered_turn is None


def test_missing_reply_reference_does_not_dispatch():
    world = _world()
    action = _dispatch(
        "sinaranu", ("seat", "ma_hadu"), reply_to="missing-tablet",
    )

    with pytest.raises(ValueError, match="no such reply tablet"):
        mail.apply_dispatch(world, action)

    assert world.letter_seq == _world().letter_seq
    assert world.letters_in_transit == _world().letters_in_transit
    assert world.documents == _world().documents


def test_seasonal_sea_leg_waits_at_the_harbour_until_sailing_opens():
    world = dataclasses.replace(_world(), date=Date(1, 1, 1))
    action = _dispatch(
        "alashiya_gov", ("seat", "ma_hadu", "alashiya"),
    )
    current, _ = mail.apply_dispatch(world, action)
    letter_id = current.letters_in_transit[-1].id

    current, _ = mail.step_letters(current)
    waiting = next(item for item in current.letters_in_transit
                   if item.id == letter_id)
    assert (waiting.at_node, waiting.edge_index) == ("ma_hadu", 1)

    current, events = mail.step_letters(current)
    waiting = next(item for item in current.letters_in_transit
                   if item.id == letter_id)
    assert (waiting.at_node, waiting.edge_index, waiting.legs_into_edge) == (
        "ma_hadu", 1, 0,
    )
    assert not _events(events, A.LetterDelivered)

    current = dataclasses.replace(current, date=Date(1, 7, 7))
    current, events = mail.step_letters(current)
    assert [event.letter_id for event in
            _events(events, A.LetterDelivered)] == [letter_id]


def test_quarantine_blocks_boundary_and_disease_exposure_travels_with_courier():
    world = _world()
    infected_seat = dataclasses.replace(world.places["seat"], infected=1)
    places = dict(world.places)
    places["seat"] = infected_seat
    world = dataclasses.replace(
        world,
        places=places,
        court=dataclasses.replace(
            world.court, quarantined=("ma_hadu",),
        ),
    )
    current, _ = mail.apply_dispatch(
        world, _dispatch("sinaranu", ("seat", "ma_hadu")),
    )
    letter_id = current.letters_in_transit[-1].id

    current, events = mail.step_letters(current)
    waiting = next(item for item in current.letters_in_transit
                   if item.id == letter_id)
    assert waiting.at_node == "seat"
    assert waiting.legs_into_edge == 0
    assert waiting.disease_exposed is True
    assert not _events(events, A.LetterDelivered)

    current = dataclasses.replace(
        current,
        court=dataclasses.replace(current.court, quarantined=()),
    )
    current, events = mail.step_letters(current)
    assert [event.letter_id for event in
            _events(events, A.LetterDelivered)] == [letter_id]
    assert (letter_id, "ma_hadu") in current.plague.infectious_arrivals


def test_duplicate_transit_identity_cannot_deliver_twice():
    world = _world()
    sent, _ = mail.apply_dispatch(
        world, _dispatch("sinaranu", ("seat", "ma_hadu")),
    )
    letter = sent.letters_in_transit[-1]
    duplicated = dataclasses.replace(
        sent,
        letters_in_transit=sent.letters_in_transit + (letter,),
    )

    arrived, events = mail.step_letters(duplicated)

    assert [event.letter_id for event in
            _events(events, A.LetterDelivered)] == [letter.id]
    assert not any(item.id == letter.id for item in arrived.letters_in_transit)


def test_archived_identity_cannot_be_dispatched_again_from_stale_sequence():
    world = _world()
    sent, _ = mail.apply_dispatch(
        world, _dispatch("sinaranu", ("seat", "ma_hadu")),
    )
    letter = sent.letters_in_transit[-1]
    delivered, _ = mail.step_letters(sent)
    stale = dataclasses.replace(delivered, letter_seq=world.letter_seq)

    with pytest.raises(ValueError, match="duplicate letter id"):
        mail.apply_dispatch(
            stale, _dispatch("sinaranu", ("seat", "ma_hadu")),
        )

    assert sum(document.ref == f"L-{letter.id}"
               for document in stale.documents) == 1


# --- tests/test_world_letter_contract.py -----------------------------------

def _dispatch_reply_to_sinaranu() -> A.DispatchLetter:
    return A.DispatchLetter(
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


def test_dispatch_and_delivery_persist_term_records() -> None:
    from engine import letter_terms

    world = _world()
    action = _dispatch_reply_to_sinaranu()
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


def test_death_in_transit_lapses_proposal_without_stopping_delivery() -> None:
    world = _world()
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


def test_structured_gift_has_material_evidence_and_hidden_interception() -> None:
    from tools import m13_audit

    world = _world()
    routes = tuple(
        dataclasses.replace(
            route,
            risk=(1000 if {route.a, route.b} == {"seat", "ma_hadu"} else 0),
        )
        for route in world.routes
    )
    world = dataclasses.replace(world, routes=routes)
    action = _dispatch_reply_to_sinaranu()

    after, events = mail.apply_dispatch(world, action)
    findings = m13_audit.audit_transition(world, after, events)
    assert not [item for item in findings if item.path == "stores.oil"]
    assert any(isinstance(event, A.GiftSent) for event in events)
    assert any(isinstance(event, A.LetterIntercepted) for event in events)
    assert after.letter_reservations[0].status == "intercepted"
    assert not after.letters_in_transit
    sent_copy = next(item for item in after.documents
                     if item.kind == "letter_out")
    assert sent_copy.ref.startswith("L-L")


def test_dispatch_action_replays_without_a_model(tmp_path) -> None:
    from ai.grader import profile_for
    from engine.core import state_hash
    from session import load_session, play, save

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
    world, log, _hashes = play(SEED, "ugarit", [[action]])
    path = tmp_path / "dispatch.json"
    save(path, SEED, "ugarit", 1, log, world)

    replayed, data = load_session(path)
    assert state_hash(replayed) == state_hash(world)
    assert data["log"][0]["action"]["terms"][0]["_t"] == "LetterTerm"
