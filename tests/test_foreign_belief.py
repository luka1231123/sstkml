"""What a foreign court is allowed to know, and how old it is (spec 2.4, 3.2).

Two halves, and the seam between them is the rule this module exists to hold.
A court counts its own place: those claims are `observed` and certain. A court
reads a tablet: those claims are `reported`, dated to the day the king sealed
it, carried by a named courier, and kept even when the next tablet contradicts
them. Nothing lets a court read Ugarit's granary, and nothing throws old news
away.
"""
from __future__ import annotations

from engine import foreign_belief as FB
from engine import mail, tick
from engine import actions as A
from engine.believe import Belief
from engine.state import Letter
from load import load_scenario

# The king who seals the tablets in this scenario. Claims about the sender are
# held under his actor id, not under the name of his city.
KING = "ammurapi"


def _world(turns: int = 1):
    world = load_scenario("ugarit", 1)
    for _ in range(turns):
        world, _ = tick.advance(world)
    return world


def _letter(letter_id: str = "L1", sent_turn: int = 3,
            quantity: int = 20000, courier: str = "courier_1",
            terms: tuple = ()) -> Letter:
    """A sealed outgoing tablet, without the mail having to carry it anywhere."""
    if not terms:
        terms = (A.LetterTerm(kind="request_good", good="grain",
                              quantity=quantity, due_turn=40),)
    return Letter(
        id=letter_id, sender=KING, recipient="pharaoh", topic="reply",
        facts=(), sent_turn=sent_turn, path=("ugarit", "egypt"),
        edge_index=0, legs_into_edge=0, at_node="ugarit", outgoing=True,
        terms=terms, courier_id=courier)


# --- counting its own courtyard ----------------------------------------------

def test_a_reading_carries_everything_a_court_decides_from():
    world = _world()
    court = world.foreign_courts["pharaoh"]
    figures = FB.readings(court)
    assert set(figures) == set(FB.FOREIGN_LOCAL)
    assert figures["stores_grain"] == court.stores["grain"]
    assert figures["need_grain"] == court.need["grain"]
    assert figures["floor_grain"] == court.floor["grain"]
    assert figures["people"] == court.people


def test_a_court_counts_its_own_place_each_fortnight():
    """A recount replaces the last count rather than standing beside it.

    Two readings of one's own granary are not two testimonies in conflict; they
    are one steward counting twice. The claim that survives is this fortnight's,
    dated to this fortnight, so staleness still means what it says.
    """
    world = _world(2)
    belief = FB.belief_of(world, "pharaoh")
    home = world.foreign_courts["pharaoh"].place
    for attribute in FB.FOREIGN_LOCAL:
        claims = belief.about(home, attribute)
        assert len(claims) == 1, f"{attribute} was kept twice over"
        for claim in claims:
            assert claim.source == "observed"
            assert claim.confidence == 1000
            assert claim.chain == ()
            assert claim.observed_turn == world.date.absolute
    assert belief.value(home, "stores_grain") == \
        world.foreign_courts["pharaoh"].stores["grain"]


def test_no_court_counts_ugarit():
    world = _world(3)
    seat = world.court.seat
    for actor in sorted(world.foreign_courts):
        belief = FB.belief_of(world, actor)
        assert not belief.about(seat), f"{actor} read Ugarit's own stores"
        for claim in belief.claims:
            if claim.source == "observed":
                assert claim.subject == world.foreign_courts[actor].place


# --- what a tablet teaches ---------------------------------------------------

def test_a_delivered_term_is_dated_to_the_day_it_was_sealed():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(sent_turn=3), 9)
    claim = belief.best("L1", "request_good:grain")
    assert claim is not None
    assert claim.source == "reported"
    assert claim.observed_turn == 3, "dated to the delivery, not the seal"
    assert claim.received_turn == 9
    assert claim.chain == ("courier_1",), "the carrier is not named"
    assert claim.value == 20000


def test_a_courier_is_named_even_when_he_is_not():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(courier=""), 9)
    claim = belief.best("L1", "request_good:grain")
    assert claim is not None and claim.chain and all(claim.chain)


def test_a_tablet_is_also_belief_about_the_man_who_sealed_it():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(), 9)
    claim = belief.best(KING, "request_good:grain")
    assert claim is not None
    assert claim.value == 20000
    assert claim.source == "reported"
    # He is describing his own want, and is not disinterested about it.
    assert claim.confidence == FB.SENDER_ON_HIMSELF < FB.TABLET_ASSERTS


def test_a_second_tablet_on_one_matter_leaves_both_accounts_standing():
    belief = Belief(holder="pharaoh")
    belief = FB.learn(belief, _letter("L1", sent_turn=3, quantity=20000), 9)
    belief = FB.learn(belief, _letter("L2", sent_turn=6, quantity=90000), 11)
    held = belief.about(KING, "request_good:grain")
    assert len(held) == 2, "the earlier account was overwritten"
    assert {claim.value for claim in held} == {20000, 90000}
    assert belief.conflicts(KING, "request_good:grain")
    # The court acts on the newer word without forgetting the older one.
    assert belief.value(KING, "request_good:grain") == 90000
    assert len(belief.about("L1")) == 1 and len(belief.about("L2")) == 1


def test_a_king_who_asks_for_grain_is_believed_short_of_grain():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(), 9)
    short = belief.best(KING, "short:grain")
    assert short is not None
    assert short.source == "inferred"
    assert short.value == 20000
    inputs = belief.about(KING, "request_good:grain")
    assert short.basis == tuple(claim.id for claim in inputs)
    assert short.observed_turn == 3, "the conclusion is as old as its inputs"
    assert short.confidence == FB.SENDER_ON_HIMSELF


def test_a_gift_teaches_nothing_about_a_shortage():
    gift = (A.LetterTerm(kind="gift", good="copper", quantity=40,
                         due_turn=0),)
    belief = FB.learn(Belief(holder="pharaoh"), _letter(terms=gift), 9)
    assert belief.about(KING, "gift:copper")
    assert not belief.about(KING, "short:copper")


def test_the_claims_behind_a_conclusion_are_still_there_afterwards():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(), 9)
    short = belief.best(KING, "short:grain")
    assert short is not None
    held = {claim.id for claim in belief.claims}
    assert set(short.basis) <= held, "an inference ate its own inputs"


# --- how old the knowledge is ------------------------------------------------

def test_the_age_of_a_matter_is_measured_from_the_seal():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(sent_turn=3), 9)
    assert FB.age_of(belief, KING, "request_good:grain", 9) == 6
    assert FB.age_of(belief, KING, "request_good:grain", 20) == 17


def test_a_matter_never_heard_of_is_not_a_matter_aged_nothing():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(), 9)
    assert FB.age_of(belief, KING, "request_good:copper", 9) is None
    assert FB.age_of(belief, "hatti_king", "stores_grain", 9) is None


def test_stale_knowledge_is_reported_and_not_discarded():
    belief = FB.learn(Belief(holder="pharaoh"), _letter(sent_turn=1), 2)
    before = len(belief.claims)
    old = belief.stale(now=40, older_than=10)
    assert old, "nothing was recognised as stale"
    assert len(belief.claims) == before, "a stale claim was thrown away"
    matters = FB.ages(belief, 40)
    assert (KING, "request_good:grain", 39) in matters
    assert matters == tuple(sorted(matters)), "the table is not in one order"


def test_ages_covers_every_matter_the_court_holds():
    world = _world(2)
    belief = FB.belief_of(world, "pharaoh")
    now = world.date.absolute
    matters = FB.ages(belief, now)
    held = {(claim.subject, claim.attribute) for claim in belief.claims}
    assert {(row[0], row[1]) for row in matters} == held
    assert all(row[2] >= 0 for row in matters)


# --- through the mail --------------------------------------------------------

def test_a_delivered_tablet_teaches_the_court_the_same_thing():
    world = _world()
    place = world.foreign_courts["pharaoh"].place
    path = mail.shortest_path(world.routes, world.court.seat, place)
    from ai.grader import profile_for
    world, _ = mail.apply_dispatch(world, A.DispatchLetter(
        recipient="pharaoh", reply_to="", text="Send grain, my brother.",
        profile=profile_for("pharaoh"),
        terms=(A.LetterTerm(kind="request_good", good="grain",
                            quantity=50000, due_turn=40),),
        scribe_id="yabninu", seal="royal", courier_id="courier_1", path=path))
    sealed = world.date.absolute
    for _ in range(12):
        world, _ = tick.advance(world)
    belief = FB.belief_of(world, "pharaoh")
    asked = belief.best(KING, "request_good:grain")
    assert asked is not None
    assert asked.observed_turn == sealed
    assert asked.received_turn > sealed, "it arrived the turn it was written"
    assert belief.best(KING, "short:grain") is not None
    assert FB.age_of(belief, KING, "request_good:grain",
                     world.date.absolute) > 0


def test_the_same_delivery_teaches_it_only_once():
    world = _world()
    letter = _letter(sent_turn=world.date.absolute)
    world, _ = FB.receive(world, letter)
    first = FB.belief_of(world, "pharaoh").claims
    again, _ = FB.receive(world, letter)
    assert FB.belief_of(again, "pharaoh").claims == first
    assert len(again.correspondence) == len(world.correspondence) == 1
