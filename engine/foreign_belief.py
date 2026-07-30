"""What a foreign court knows: its own place, and the tablets that reach it.

The mirror of `engine/observe.py`, pointed outward (spec 2.4, 3.2). A foreign
court counts its own granary because it is standing next to it, and learns
everything about Ugarit from tablets that arrived late, through a named courier,
saying what the king chose to have written. Nothing here reads Ugarit's stores
on the foreign court's behalf, and nothing here decides: this module only mints
claims, and `engine/correspondence_policy.py` is handed those claims and no
world at all.

Two entry points, and the boundary between them is the whole point.

`step` is the fortnightly look around the courtyard: stores, mouths, the draw
against them, and the quantity the court will not part with. First-hand,
`observed`, confidence 1000.

`receive` is a tablet finishing its journey, and it leaves three kinds of trace.

First, one dated `reported` claim per delivered term, held under the tablet as
subject, so that "what did this tablet say" has an answer that survives the
tablet being answered.

Second, the same terms held under the *sender* as subject, because a request is
also an assertion about the man making it: he says he wants two thousand qa of
grain. That is where two tablets on one matter meet and disagree, and both are
kept -- `engine/believe.py` does not resolve contradictions and neither does
this file.

Third, an inference: a king who asks for grain is short of grain. It is minted
through `believe.infer`, so it names the claims it came from and does not
overwrite them.

Every one of those carries `observed_turn` = the turn the king sealed the
tablet, not the turn it arrived. A request for two thousand qa of grain written
five fortnights ago is five fortnights old on the day it is read, and the
deciding court is entitled to weigh it as such. `age_of` and `ages` are how
another module asks how old a court's knowledge of a matter is; nothing here
throws a stale claim away, because a court deciding on old news is the ordinary
case and deleting the news would hide it (spec 2.4).
"""
from __future__ import annotations

import dataclasses

from engine.believe import Belief, Claim, Observation, infer
from engine import observe as OB
from engine.state import CorrespondenceCase, ForeignCourt, World

# What a foreign court counts at home each fortnight. Same test as
# `engine.observe.LOCAL`: could this actor learn it by walking round its own
# place? Its own granary, its own mouths, the fortnightly draw against the
# granary, and the quantity its steward will not release, yes. Ugarit's, never.
#
# The names are grain-shaped because `ForeignCourt` is grain-shaped and both are
# deletion targets: SPEC.md 6.2 puts the foreign settlements on the kernel's
# stores and cohorts, and these four readings go when that lands.
FOREIGN_LOCAL = ("stores_grain", "need_grain", "floor_grain", "people")

# What a tablet is worth as evidence, scaled 1000.
#
# The tablet's own assertion is certain: it says what it says, and the court can
# read it. What the tablet says about the *sender* is not, because the sender is
# describing himself and had a motive to write it. Interested testimony stays
# visible as interested (spec 2.4), and since `believe.infer` takes the least
# confident of its inputs, the conclusion drawn from a request is no surer than
# the request was.
TABLET_ASSERTS = 1000
SENDER_ON_HIMSELF = 800


def readings(court: ForeignCourt) -> dict[str, int]:
    """The figures a court can count where it stands, keyed as in FOREIGN_LOCAL."""
    return {
        "stores_grain": int(court.stores.get("grain", 0)),
        "need_grain": int(court.need.get("grain", 0)),
        "floor_grain": int(court.floor.get("grain", 0)),
        "people": int(court.people),
    }


def belief_of(world: World, actor: str) -> Belief:
    """That court's belief, or an empty one. Never None, so policies stay simple."""
    held = world.foreign_beliefs.get(actor)
    return held if isinstance(held, Belief) else Belief(holder=actor)


def _with_belief(world: World, actor: str, belief: Belief) -> World:
    beliefs = dict(world.foreign_beliefs)
    beliefs[actor] = belief
    return dataclasses.replace(world, foreign_beliefs=beliefs)


def observations(court: ForeignCourt, turn: int) -> tuple[Observation, ...]:
    """What this court counted at home this fortnight.

    Minted here rather than through `engine.observe.observe_local` because
    FOREIGN_LOCAL is a different list: the court's own fortnightly draw against
    its own granary is something its steward knows and Ugarit's does not, and
    adding it to the shared LOCAL list would hand it to every actor in the game.
    """
    figures = readings(court)
    return tuple(
        Observation(
            id=f"{court.actor}|{turn}|{court.place}|{attribute}",
            observer=court.actor, subject=court.place, attribute=attribute,
            value=figures[attribute], turn=turn, method="counted",
            place=court.place)
        for attribute in FOREIGN_LOCAL if attribute in figures)


def _recounted(belief: Belief, fresh: tuple[Claim, ...]) -> Belief:
    """This fortnight's count of its own place, replacing last fortnight's.

    The one place a claim is dropped rather than kept, and the reason is that it
    is not testimony. `engine/believe.py` keeps contradictions because two people
    disagreeing is a fact about the world; a steward who counted the granary this
    morning is not in disagreement with the steward who counted it a fortnight
    ago, he has simply counted it again. Keeping every reading would grow the
    saved state without end -- a hundred years of Ma'hadu counting its own barley
    -- and would tell a policy nothing that `best` does not already give it.

    Only the holder's own `observed` claims about its own place are replaced.
    Everything reported, inferred, or held about anyone else stays exactly where
    it was (spec 2.4).
    """
    superseded = {(claim.subject, claim.attribute) for claim in fresh}
    kept = tuple(
        claim for claim in belief.claims
        if claim.source != "observed"
        or (claim.subject, claim.attribute) not in superseded)
    return dataclasses.replace(belief, claims=kept).add(*fresh)


def step(world: World) -> tuple[World, list]:
    """Every foreign court counts its own place (phase 3, from the far side)."""
    now = world.date.absolute
    beliefs = dict(world.foreign_beliefs)
    for actor in sorted(world.foreign_courts):
        court = world.foreign_courts[actor]
        belief = belief_of(world, actor)
        beliefs[actor] = _recounted(
            belief, OB.as_claims(observations(court, now), now))
    return dataclasses.replace(world, foreign_beliefs=beliefs), []


def term_attribute(term) -> str:
    """The claim attribute one delivered term is held under.

    `kind:good` for material terms, `kind:person` for a proposal, `kind` alone
    for service, which names a destination rather than a thing.
    """
    if term.kind in {"gift", "request_good", "promise_good"}:
        return f"{term.kind}:{term.good}"
    if term.kind == "marriage_proposal":
        return f"{term.kind}:{term.person_id}"
    return term.kind


def _courier(letter) -> str:
    """Who carried it. Named even when unnamed: a chain may not be empty."""
    return letter.courier_id or "courier"


def tablet_claims(letter, turn: int) -> tuple[Claim, ...]:
    """One dated, sourced claim per delivered term, subject the tablet itself.

    Subject is the letter id, so the case can be read back years later --
    "these were the terms as delivered" -- without the terms of a second tablet
    on the same matter being taken for the terms of this one.
    """
    return tuple(
        Claim(
            id=f"{letter.id}:term:{index}@{turn}",
            holder=letter.recipient,
            subject=letter.id,
            attribute=term_attribute(term),
            value=int(term.quantity),
            source="reported",
            observed_turn=int(letter.sent_turn),
            received_turn=turn,
            chain=(_courier(letter),),
            confidence=TABLET_ASSERTS,
        )
        for index, term in enumerate(letter.terms))


def sender_claims(letter, turn: int) -> tuple[Claim, ...]:
    """The same terms held as belief about the man who wrote them.

    A request is an assertion about the sender: on the turn he sealed this, he
    wanted this much of this good. Held under the sender rather than the tablet
    so that a second tablet asking for a different quantity lands on the same
    subject and attribute, disagrees with the first, and stays. The court now
    holds two accounts of what Ugarit wants, which is what a court would hold.
    """
    return tuple(
        Claim(
            id=f"{letter.id}:sender:{index}@{turn}",
            holder=letter.recipient,
            subject=letter.sender,
            attribute=term_attribute(term),
            value=int(term.quantity),
            source="reported",
            observed_turn=int(letter.sent_turn),
            received_turn=turn,
            chain=(_courier(letter),),
            confidence=SENDER_ON_HIMSELF,
        )
        for index, term in enumerate(letter.terms))


def claims_for(letter, turn: int) -> tuple[Claim, ...]:
    """Everything one delivered tablet is direct evidence of."""
    return tablet_claims(letter, turn) + sender_claims(letter, turn)


def _requests_by_good(claims: tuple[Claim, ...]) -> dict[str, list[Claim]]:
    """The request claims among these, grouped by the good asked for."""
    grouped: dict[str, list[Claim]] = {}
    for claim in claims:
        kind, _, good = claim.attribute.partition(":")
        if kind == "request_good" and good:
            grouped.setdefault(good, []).append(claim)
    return grouped


def learn(belief: Belief, letter, turn: int) -> Belief:
    """Fold one delivered tablet into the recipient's belief.

    Pure: no World, so the whole of what a tablet teaches can be tested against
    a belief and a letter. Direct claims first, then the conclusions drawn from
    them, because an inference must be able to name inputs that exist.
    """
    minted = claims_for(letter, turn)
    belief = belief.add(*minted)
    # A king who asks for grain is short of grain. That is the one thing about
    # Ugarit a foreign court may conclude from a tablet without having been
    # there, and the size of the ask is all it has to go on: the value here is
    # what he asked for, not a count of his granary, which nobody at this court
    # has seen. sorted() so two goods asked for in one tablet are always
    # concluded in the same order.
    requested = _requests_by_good(sender_claims(letter, turn))
    for good in sorted(requested):
        inputs = tuple(requested[good])
        belief = infer(
            belief, f"{letter.id}:short:{good}@{turn}",
            letter.sender, f"short:{good}",
            sum(claim.value for claim in inputs), inputs, turn)
    return belief


# --- how old is what this court knows (spec 2.4) ------------------------------

def age_of(belief: Belief, subject: str, attribute: str,
           now: int) -> int | None:
    """Fortnights since the fact behind the claim this court would act on.

    None means the court has never heard of the matter, which is a different
    answer from "heard of it long ago" and must not be flattened into a zero.
    """
    claim = belief.best(subject, attribute)
    return None if claim is None else claim.age(now)


def ages(belief: Belief, now: int) -> tuple[tuple[str, str, int], ...]:
    """The age of this court's knowledge of every matter it holds any of.

    One row per subject and attribute, sorted, so an inspector prints the same
    table on every machine. Nothing is dropped for being old: staleness is
    reported and left for the reader (or the policy) to weigh.
    """
    matters = sorted({(claim.subject, claim.attribute)
                      for claim in belief.claims})
    aged = ((subject, attribute, age_of(belief, subject, attribute, now))
            for subject, attribute in matters)
    return tuple((subject, attribute, age)
                 for subject, attribute, age in aged if age is not None)


def receive(world: World, letter) -> tuple[World, list]:
    """A sealed tablet has reached its addressee: mint claims, open a case.

    Idempotent on letter id. A replayed or duplicated delivery must not open a
    second case or double the claims behind a decision.
    """
    if any(case.letter_id == letter.id for case in world.correspondence):
        return world, []
    court = world.foreign_courts.get(letter.recipient)
    if court is None:
        # Not an autonomous court in this scenario: the tablet still arrives and
        # its terms still take material effect, but nobody there decides.
        return world, []

    now = world.date.absolute
    belief = learn(belief_of(world, letter.recipient), letter, now)
    world = _with_belief(world, letter.recipient, belief)

    seq = world.case_seq + 1
    case = CorrespondenceCase(
        id=f"C{seq}",
        letter_id=letter.id,
        actor=letter.recipient,
        place=court.place,
        received_turn=now,
        terms=tuple(letter.terms),
    )
    return dataclasses.replace(
        world,
        correspondence=world.correspondence + (case,),
        case_seq=seq,
    ), []
