"""Physical dispatch contract for the player's exact outgoing tablet."""
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


def test_multileg_dispatch_preserves_exact_text_and_terms_until_delivery():
    world = _world()
    terms = (
        A.LetterTerm(
            kind="gift", good="copper", quantity=30,
            destination="carchemish",
        ),
        A.LetterTerm(
            kind="service", quantity=40, destination="carchemish",
            due_turn=18,
        ),
    )
    action = _dispatch(
        "carchemish_viceroy",
        ("seat", "mukish", "halab", "carchemish"),
        text="Brother: copper now; forty days of carts after harvest.",
        terms=terms,
    )

    current, _ = mail.apply_dispatch(world, action)
    letter_id = current.letters_in_transit[-1].id
    positions = []
    delivered = []
    for _ in range(5):
        current, events = mail.step_letters(current)
        delivered.extend(_events(events, A.LetterDelivered))
        travelling = next(
            (item for item in current.letters_in_transit
             if item.id == letter_id),
            None,
        )
        if travelling is not None:
            positions.append((
                travelling.at_node,
                travelling.edge_index,
                travelling.legs_into_edge,
            ))
            assert travelling.text == action.text
            assert travelling.terms == terms

    assert positions == [
        ("mukish", 1, 0),
        ("mukish", 1, 1),
        ("halab", 2, 0),
        ("halab", 2, 1),
    ]
    assert [event.letter_id for event in delivered] == [letter_id]
    copy = next(doc for doc in current.documents if doc.ref == f"L-{letter_id}")
    assert copy.body == action.text
    assert copy.terms == terms


@pytest.mark.parametrize(
    "action",
    [
        _dispatch("sinaranu", ("ma_hadu", "seat")),
        _dispatch("hatti_king", ("seat", "ma_hadu")),
        _dispatch("hatti_king", ("seat", "hattusa")),
        _dispatch("not_a_correspondent", ("seat",)),
    ],
)
def test_invalid_recipient_or_path_is_transactional(action):
    world = _world()

    with pytest.raises(ValueError):
        mail.apply_dispatch(world, action)

    assert world == _world()


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
