"""Structured tablet terms have explicit, conservative world consequences."""
from __future__ import annotations

import dataclasses

import pytest

from engine import actions as A
from engine import letter_terms, seat
from engine.state import Letter
from load import load_campaign


SEED = 8814402919


def _world():
    return load_campaign("seat", SEED)


def _letter(world, *terms: A.LetterTerm, letter_id: str = "L-terms") -> Letter:
    return Letter(
        id=letter_id,
        sender=world.court.actor,
        recipient="hatti_king",
        topic="terms",
        facts=(),
        sent_turn=world.date.absolute,
        path=("seat", "carchemish", "hattusa"),
        edge_index=0,
        legs_into_edge=0,
        at_node="seat",
        outgoing=True,
        text="These are the words on the tablet.",
        terms=tuple(terms),
    )


def test_world_validation_rejects_unknown_or_impossible_terms() -> None:
    world = _world()
    with pytest.raises(ValueError, match="recipient"):
        letter_terms.validate_term(
            world, A.LetterTerm("gift", good="oil", quantity=1),
            "nobody")
    with pytest.raises(ValueError, match="not enough"):
        letter_terms.validate_term(
            world,
            A.LetterTerm(
                "gift", good="oil",
                quantity=seat.held(world)["oil"] + 1),
            "hatti_king")
    with pytest.raises(ValueError, match="future due turn"):
        letter_terms.validate_term(
            world,
            A.LetterTerm("promise_good", good="grain", quantity=1),
            "hatti_king")
    with pytest.raises(ValueError, match="destination"):
        letter_terms.validate_term(
            world,
            A.LetterTerm("service", quantity=20, destination="nowhere"),
            "hatti_king")

    person = world.court.house["pidray"]
    dead = dataclasses.replace(person, alive=False, died_turn=0)
    dead_world = dataclasses.replace(
        world,
        court=dataclasses.replace(
            world.court,
            house={**world.court.house, person.id: dead},
        ),
    )
    with pytest.raises(ValueError, match="living person"):
        letter_terms.validate_term(
            dead_world,
            A.LetterTerm("marriage_proposal", person_id=person.id),
            "hatti_king")


def test_gift_is_reserved_once_and_delivery_never_mints_goods() -> None:
    world = _world()
    letter = _letter(
        world, A.LetterTerm("gift", good="oil", quantity=20))
    opening = seat.held(world)["oil"]

    first = letter_terms.reserve_terms_at_dispatch(world, letter)
    second = letter_terms.reserve_terms_at_dispatch(first.world, letter)

    assert seat.held(first.world)["oil"] == opening - 20
    assert second.world == first.world
    assert second.reservations == first.reservations
    assert sum(
        gift.quantity for gift in second.world.court.treasury_gifts_sent
        if gift.id == "L-terms:term:0") == 20

    delivered_world, delivered = letter_terms.apply_delivered_terms(
        first.world, letter)
    again_world, again = letter_terms.apply_delivered_terms(
        delivered_world, letter)
    assert seat.held(delivered_world)["oil"] == opening - 20
    assert again_world == delivered_world
    assert again == delivered
    assert delivered.gifts[0].status == "delivered"


def test_all_gifts_are_checked_as_one_atomic_reservation() -> None:
    world = _world()
    half = seat.held(world)["wine"] // 2 + 1
    letter = _letter(
        world,
        A.LetterTerm("gift", good="wine", quantity=half),
        A.LetterTerm("gift", good="wine", quantity=half),
    )
    with pytest.raises(ValueError, match="all gifts"):
        letter_terms.reserve_terms_at_dispatch(world, letter)
    assert seat.held(world)["wine"] == 3000
    assert not world.court.treasury_gifts_sent


def test_promise_and_service_create_records_without_a_goods_faucet() -> None:
    world = _world()
    letter = _letter(
        world,
        A.LetterTerm(
            "promise_good", good="grain", quantity=30, due_turn=9),
        A.LetterTerm(
            "service", quantity=12, destination="carchemish", due_turn=7),
    )
    opening = seat.held(world)

    dispatched = letter_terms.reserve_terms_at_dispatch(world, letter)
    assert seat.held(dispatched.world) == opening
    assert [item.kind for item in dispatched.obligations] == [
        "promise_good", "service"]
    assert dispatched.obligations[0].due_turn == 9
    assert dispatched.obligations[1].destination == "carchemish"

    delivered_world, delivered = letter_terms.apply_delivered_terms(
        dispatched.world, letter)
    assert seat.held(delivered_world) == opening
    assert all(item.status == "delivered"
               for item in delivered.obligations)
    assert all(item.source_letter == letter.id
               for item in delivered.obligations)
    assert all(item.authority == letter.sender
               and item.beneficiary == letter.recipient
               for item in delivered.obligations)


def test_request_becomes_a_dated_claim_only_on_delivery() -> None:
    world = _world()
    letter = _letter(
        world,
        A.LetterTerm("request_good", good="grain", quantity=70))

    dispatched = letter_terms.reserve_terms_at_dispatch(world, letter)
    assert not dispatched.reservations
    assert not dispatched.obligations

    _after, delivered = letter_terms.apply_delivered_terms(
        dispatched.world, letter)
    claim = delivered.claims[0]
    assert claim.source_letter == letter.id
    assert claim.created_turn == world.date.absolute
    assert claim.due_turn == world.date.absolute
    assert claim.party == letter.recipient
    assert claim.beneficiary == letter.sender
    assert claim.history


def test_marriage_delivery_stays_a_pending_proposal() -> None:
    world = _world()
    person = world.court.house["pidray"]
    letter = _letter(
        world,
        A.LetterTerm("marriage_proposal", person_id=person.id))

    dispatched = letter_terms.reserve_terms_at_dispatch(world, letter)
    after, delivered = letter_terms.apply_delivered_terms(
        dispatched.world, letter)

    assert after.court.house[person.id] == person
    proposal = delivered.proposals[0]
    assert proposal.status == "pending"
    assert proposal.person_id == person.id
    assert proposal.source_letter == letter.id
    assert proposal.authority == letter.sender
    assert proposal.beneficiary == letter.recipient
    with pytest.raises(dataclasses.FrozenInstanceError):
        proposal.status = "accepted"


def test_term_results_are_deterministically_equal() -> None:
    world = _world()
    letter = _letter(
        world,
        A.LetterTerm("gift", good="copper", quantity=13),
        A.LetterTerm(
            "promise_good", good="grain", quantity=21, due_turn=11),
        A.LetterTerm("request_good", good="wine", quantity=8),
    )
    left = letter_terms.reserve_terms_at_dispatch(world, letter)
    right = letter_terms.reserve_terms_at_dispatch(world, letter)
    assert left == right
    assert letter_terms.apply_delivered_terms(
        left.world, letter) == letter_terms.apply_delivered_terms(
            right.world, letter)


def test_dispatch_action_uses_the_id_of_the_letter_it_will_create() -> None:
    world = _world()
    action = A.DispatchLetter(
        recipient="hatti_king",
        reply_to="",
        text="Oil travels with this tablet.",
        profile="hatti.servant_to_lord",
        terms=(A.LetterTerm("gift", good="oil", quantity=4),),
        scribe_id="yabninu",
        seal="royal",
        courier_id="iliya",
        path=("seat", "carchemish", "hattusa"),
    )

    result = letter_terms.reserve_terms_at_dispatch(world, action)
    assert result.reservations[0].source_letter == (
        f"L{world.letter_seq + 1}")
    assert result.reservations[0].authority == world.court.actor
