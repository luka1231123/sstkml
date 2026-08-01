"""Physical dispatch contract for the player's exact outgoing tablet.

The seat->ma_hadu harbour-road cases were archived to
``tests/archive/mail_dispatch_route_graph.py``: no route edge touches
``ma_hadu`` in ``content/world.toml``, so ``_validate_dispatch`` honestly
refuses those paths.
"""
from __future__ import annotations

import dataclasses

import pytest

from engine import actions as A
from engine import mail
from load import load_campaign


SEED = 8_814_402_919


def _world():
    world = load_campaign("seat", SEED)
    from engine.state import with_routes
    return with_routes(world, tuple(
        dataclasses.replace(route, risk=0) for route in world.routes))


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
        ("halab", 2, 0),
    ]
    assert [event.letter_id for event in delivered] == [letter_id]
    copy = next(doc for doc in current.documents if doc.ref == f"L-{letter_id}")
    assert copy.body == action.text
    assert copy.terms == terms


def test_invalid_recipient_or_path_is_transactional():
    cases = [
        _dispatch("sinaranu", ("ma_hadu", "seat")),
        _dispatch("hatti_king", ("seat", "ma_hadu")),
        _dispatch("hatti_king", ("seat", "hattusa")),
        _dispatch("not_a_correspondent", ("seat",)),
    ]
    for action in cases:
        world = _world()

        with pytest.raises(ValueError):
            mail.apply_dispatch(world, action)

        assert world == _world()

