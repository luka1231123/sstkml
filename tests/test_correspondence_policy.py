"""Why a foreign court answers as it does, and what its answer costs it.

Two halves. The first hands `decide` a belief and a case and nothing else, and
checks that every one of the five answers is reachable with a cause a reader can
print. The second follows the material: a promise moves nothing, an accepted
request empties a named granary by exactly what later enters Ugarit's, and a
delivery replayed twice lands once (SPEC.md 2.2).
"""
from __future__ import annotations

import dataclasses

import pytest

from engine import actions as A
from engine import correspondence_policy as P
from engine import foreign_belief as FB
from engine import letter_terms as LT
from engine import mail, observe as OB, tick
from engine.believe import Belief
from engine.state import CorrespondenceCase, ForeignCourt, Letter
from load import load_scenario
from session import play

KING = "ammurapi"


def _world(turns: int = 1):
    world = load_scenario("ugarit", 1)
    for _ in range(turns):
        world, _ = tick.advance(world)
    return world


def _counted(world, actor: str, turn: int) -> Belief:
    """What that court counted at home on that turn, and nothing else."""
    court = world.foreign_courts[actor]
    return OB.project(
        Belief(holder=actor), FB.observations(court, turn), turn)


def _tablet(world, actor: str, terms: tuple, letter_id: str = "L1",
            sent_turn: int = 1) -> Letter:
    """A sealed tablet of ours, addressed to that court, already at its door."""
    return Letter(
        id=letter_id, sender=KING, recipient=actor, topic="letter", facts=(),
        sent_turn=sent_turn,
        path=(world.court.seat, world.foreign_courts[actor].place),
        edge_index=0, legs_into_edge=0, at_node=world.court.seat,
        outgoing=True, terms=terms, courier_id="courier_1")


def _case(world, actor: str, terms: tuple, letter_id: str = "L1",
          received_turn: int = 1) -> CorrespondenceCase:
    return CorrespondenceCase(
        id="C1", letter_id=letter_id, actor=actor,
        place=world.foreign_courts[actor].place,
        received_turn=received_turn, terms=tuple(terms))


def _asking(good: str = "grain", quantity: int = 50000,
            due_turn: int = 0) -> tuple:
    return (A.LetterTerm(kind="request_good", good=good, quantity=quantity,
                         due_turn=due_turn),)


def _reply(world, actor: str, terms: tuple, letter_id: str = "R1",
           sent_turn: int = 1) -> Letter:
    """That court's answer, on the road home with whatever it is carrying."""
    place = world.foreign_courts[actor].place
    return Letter(
        id=letter_id, sender=actor, recipient=world.court.actor,
        topic="reply_accept", facts=(("decision", "accept"),),
        sent_turn=sent_turn, path=(place, world.court.seat),
        edge_index=0, legs_into_edge=0, at_node=place,
        outgoing=False, terms=tuple(terms), courier_id="courier_2")


# --- the five answers, each with its cause ------------------------------------

def test_a_court_with_plenty_accepts_and_says_what_it_will_send():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    case = _case(world, "pharaoh", _asking(), received_turn=4)
    answer = P.decide("pharaoh", belief, case, 4)
    assert answer.kind == "accept"
    assert answer.reason and "spare" in answer.reason
    assert [(term.kind, term.good, term.quantity) for term in answer.terms] \
        == [("gift", "grain", 50000)]
    assert answer.basis, "an acceptance names the claims behind it"


def test_a_far_off_date_is_promised_rather_than_loaded():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    case = _case(world, "pharaoh", _asking(due_turn=40), received_turn=4)
    answer = P.decide("pharaoh", belief, case, 4)
    assert answer.kind == "accept"
    assert [term.kind for term in answer.terms] == ["promise_good"]
    assert answer.terms[0].due_turn == 40


def test_a_court_offers_exactly_what_it_can_spare():
    world = _world()
    belief = _counted(world, "ura_merchant", 4)
    case = _case(world, "ura_merchant", _asking(quantity=8000),
                 received_turn=4)
    answer = P.decide("ura_merchant", belief, case, 4)
    court = world.foreign_courts["ura_merchant"]
    spare = (court.stores["grain"] - court.floor.get("grain", 0)
             - court.need["grain"] * P.RESERVE_TURNS)
    assert answer.kind == "counter"
    assert answer.terms[0].quantity == spare
    assert "spare" in answer.reason and "8000" in answer.reason


def test_a_court_that_can_spare_nothing_refuses_and_shows_its_figures():
    world = _world()
    belief = _counted(world, "alashiya_gov", 4)
    case = _case(world, "alashiya_gov", _asking(quantity=39000),
                 received_turn=4)
    answer = P.decide("alashiya_gov", belief, case, 4)
    assert answer.kind == "refuse"
    assert not answer.terms
    assert "39000 asked" in answer.reason
    assert answer.basis


def test_a_household_is_given_time_to_talk_about_a_match():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    terms = (A.LetterTerm(kind="marriage_proposal", person_id="pidray"),)
    case = _case(world, "pharaoh", terms, received_turn=4)
    waiting = P.decide("pharaoh", belief, case, 4)
    assert waiting.kind == "delay"
    assert waiting.delay_until == 4 + P.PROPOSAL_DELAY
    assert "talking" in waiting.reason
    answered = P.decide("pharaoh", belief, case, 4 + P.PROPOSAL_DELAY)
    assert answered.kind == "accept"


def test_a_court_that_has_not_counted_its_own_stores_waits():
    world = _world()
    case = _case(world, "pharaoh", _asking(), received_turn=4)
    answer = P.decide("pharaoh", Belief(holder="pharaoh"), case, 4)
    assert answer.kind == "delay"
    assert answer.delay_until == 5
    assert "counted" in answer.reason


def test_a_tablet_that_asks_nothing_is_not_answered():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    answer = P.decide("pharaoh", belief, _case(world, "pharaoh", ()), 4)
    assert answer.kind == "ignore"
    assert "asks nothing" in answer.reason


def test_a_court_says_nothing_about_a_good_it_keeps_no_count_of():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    case = _case(world, "pharaoh", _asking(good="tin", quantity=40),
                 received_turn=4)
    answer = P.decide("pharaoh", belief, case, 4)
    assert answer.kind == "ignore"
    assert "no count of tin" in answer.reason


def test_asking_a_third_time_for_what_it_cannot_send_earns_silence():
    world = _world()
    belief = _counted(world, "alashiya_gov", 6)
    for index in range(P.SILENCE_AFTER):
        belief = FB.learn(
            belief,
            _tablet(world, "alashiya_gov", _asking(quantity=39000),
                    letter_id=f"L{index + 1}", sent_turn=index + 1),
            6)
    case = _case(world, "alashiya_gov", _asking(quantity=39000),
                 letter_id=f"L{P.SILENCE_AFTER}", received_turn=6)
    answer = P.decide("alashiya_gov", belief, case, 6)
    assert answer.kind == "ignore"
    assert f"asked on {P.SILENCE_AFTER} separate days" in answer.reason
    assert answer.basis, "silence still names what it was silent about"


def test_person_days_are_answered_out_of_the_people_it_counts():
    world = _world()
    belief = _counted(world, "byblos_king", 4)
    people = world.foreign_courts["byblos_king"].people
    small = (A.LetterTerm(kind="service", quantity=40,
                          destination=world.court.seat, due_turn=9),)
    assert P.decide("byblos_king", belief, _case(world, "byblos_king", small),
                    4).kind == "accept"
    large = (A.LetterTerm(kind="service", quantity=people * 10,
                          destination=world.court.seat, due_turn=9),)
    answer = P.decide(
        "byblos_king", belief, _case(world, "byblos_king", large), 4)
    assert answer.kind == "counter"
    assert answer.terms[0].kind == "service"
    assert answer.terms[0].quantity == people * P.DAYS_PER_HEAD


def test_a_house_believed_short_of_grain_is_not_married_into():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    belief = FB.learn(belief, _tablet(world, "pharaoh", _asking()), 4)
    terms = (A.LetterTerm(kind="marriage_proposal", person_id="pidray"),)
    case = _case(world, "pharaoh", terms, letter_id="L2", received_turn=4)
    answer = P.decide("pharaoh", belief, case, 4 + P.PROPOSAL_DELAY)
    assert answer.kind == "refuse"
    assert "50000" in answer.reason
    assert answer.basis, "the refusal cites the tablet that taught it"


def test_a_gift_is_received_and_acknowledged():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    terms = (A.LetterTerm(kind="gift", good="oil", quantity=20),)
    answer = P.decide(
        "pharaoh", belief, _case(world, "pharaoh", terms), 4)
    assert answer.kind == "accept" and not answer.terms


# --- old news is not current news (spec 2.4) ---------------------------------

def test_a_granary_counted_long_ago_is_reckoned_smaller_than_it_was_written():
    world = _world()
    belief = _counted(world, "pharaoh", 4)
    case = _case(world, "pharaoh", _asking(quantity=600000), received_turn=4)
    assert P.decide("pharaoh", belief, case, 4).kind == "accept"
    # The same figures, twenty fortnights old. Twenty fortnights of eating have
    # been done against them, and the court will not promise from them.
    later = dataclasses.replace(case, received_turn=24)
    stale = P.decide("pharaoh", belief, later, 24)
    assert stale.kind == "refuse"
    assert "counted 20 fortnights ago" in stale.reason
    assert belief.stale(now=24, older_than=10), "nothing was recognised as old"


# --- the material side -------------------------------------------------------

def test_a_promise_moves_nothing():
    world = _world()
    letter = _reply(
        world, "pharaoh",
        (A.LetterTerm(kind="promise_good", good="grain", quantity=50000,
                      due_turn=40),))
    before = dict(world.court.stores)
    after, _ = LT.apply_incoming_terms(world, letter)
    assert dict(after.court.stores) == before, "a promise filled the granary"
    assert not after.letter_reservations
    owed = after.letter_obligations[-1]
    assert owed.party == "pharaoh" and owed.quantity == 50000
    assert owed.due_turn == 40 and owed.history


def test_what_leaves_the_court_is_what_arrives_and_it_arrives_once():
    world = _world()
    letter = _reply(
        world, "pharaoh",
        (A.LetterTerm(kind="gift", good="grain", quantity=50000),))
    court_before = world.foreign_courts["pharaoh"].stores["grain"]
    seat_before = world.court.stores.get("grain", 0)

    loaded = LT.load_court_cargo(world, "pharaoh", letter)
    left = court_before - loaded.foreign_courts["pharaoh"].stores["grain"]
    assert left == 50000
    assert loaded.court.stores.get("grain", 0) == seat_before, \
        "the grain was at Ugarit before anything carried it there"

    arrived, _ = LT.apply_incoming_terms(loaded, letter)
    gained = arrived.court.stores.get("grain", 0) - seat_before
    assert gained == left, "what arrived is not what left"
    record = next(item for item in arrived.letter_reservations
                  if item.source_letter == "R1")
    assert record.status == "delivered"
    assert record.party == "pharaoh" and record.beneficiary == "ammurapi"
    assert len(record.history) == 2, "the cargo lost its history"

    replayed, _ = LT.apply_incoming_terms(arrived, letter)
    assert replayed.court.stores == arrived.court.stores
    assert replayed.letter_reservations == arrived.letter_reservations


def test_a_granary_is_emptied_once_however_often_the_reply_is_applied():
    world = _world()
    letter = _reply(
        world, "pharaoh",
        (A.LetterTerm(kind="gift", good="grain", quantity=50000),))
    once = LT.load_court_cargo(world, "pharaoh", letter)
    twice = LT.load_court_cargo(once, "pharaoh", letter)
    assert twice.foreign_courts["pharaoh"].stores == \
        once.foreign_courts["pharaoh"].stores
    assert len(twice.letter_reservations) == 1


def test_cargo_that_left_no_granary_is_refused_rather_than_created():
    world = _world()
    letter = _reply(
        world, "pharaoh",
        (A.LetterTerm(kind="gift", good="grain", quantity=50000),))
    with pytest.raises(ValueError):
        LT.apply_incoming_terms(world, letter)


def test_an_intercepted_cargo_is_gone_from_the_granary_and_never_arrives():
    world = _world()
    letter = _reply(
        world, "pharaoh",
        (A.LetterTerm(kind="gift", good="grain", quantity=50000),))
    before = world.foreign_courts["pharaoh"].stores["grain"]
    lost = LT.load_court_cargo(world, "pharaoh", letter, intercepted=True)
    assert lost.foreign_courts["pharaoh"].stores["grain"] == before - 50000
    record = lost.letter_reservations[-1]
    assert record.status == "intercepted"
    assert any("intercepted" in note for note in record.history)


def test_a_court_loads_what_is_there_rather_than_what_it_believed():
    world = _world()
    court = world.foreign_courts["pharaoh"]
    # The steward's count says plenty; the granary has been emptied since.
    thin = dict(world.foreign_courts)
    thin["pharaoh"] = ForeignCourt(
        actor=court.actor, place=court.place,
        stores={"grain": court.floor.get("grain", 0)},
        need=dict(court.need), floor=dict(court.floor), people=court.people)
    world = dataclasses.replace(world, foreign_courts=thin)
    plenty = P.Decision(
        "accept",
        terms=(A.LetterTerm(kind="gift", good="grain", quantity=50000),),
        basis=("c1",), reason="it can spare what was asked")
    cut = P._affordable(world, "pharaoh", plenty)
    assert cut.kind == "refuse" and not cut.terms
    assert "granary held less" in cut.reason


# --- the whole chain ---------------------------------------------------------

def _dispatch(world, recipient: str = "pharaoh", quantity: int = 50000,
              due_turn: int = 0):
    from ai.grader import profile_for
    place = world.foreign_courts[recipient].place
    return A.DispatchLetter(
        recipient=recipient, reply_to="", text="Send grain, my brother.",
        profile=profile_for(recipient),
        terms=_asking(quantity=quantity, due_turn=due_turn),
        scribe_id="yabninu", seal="royal", courier_id="courier_1",
        path=mail.shortest_path(world.routes, world.court.seat, place))


def test_an_accepted_request_empties_a_named_granary_and_fills_ours():
    world = _world()
    world, _ = mail.apply_dispatch(world, _dispatch(world))
    stores = [world.foreign_courts["pharaoh"].stores["grain"]]
    for _ in range(30):
        world, _ = tick.advance(world)
        stores.append(world.foreign_courts["pharaoh"].stores["grain"])
    case = next(item for item in world.correspondence
                if item.actor == "pharaoh")
    assert case.decision == "accept"
    assert case.basis, "the acceptance kept no record of what it read"
    cargo = next(item for item in world.letter_reservations
                 if item.party == "pharaoh")
    assert cargo.quantity == 50000
    assert cargo.status == "delivered", "the cargo never reached the seat"
    # It left the granary on exactly one turn, and only that much left.
    fell = [before - after
            for before, after in zip(stores, stores[1:]) if after != before]
    assert fell == [50000]
    assert any(world.court.seat in note for note in cargo.history)


def test_the_whole_chain_replays_to_the_same_hash():
    script: list[list] = [[] for _ in range(30)]
    reference = load_scenario("ugarit", 1)
    reference, _ = tick.advance(reference)
    script[1] = [_dispatch(reference)]
    _first, _log, first_hashes = play(1, "ugarit", script)
    _second, _second_log, second_hashes = play(1, "ugarit", script)
    assert first_hashes == second_hashes
