"""How a foreign court answers a tablet, decided from its belief alone.

`decide` takes `(actor, belief, case, turn)`. It is handed no world, and that is
the contract, not a convenience: a policy that could reach World would be able
to read Ugarit's granary before answering Ugarit's request for grain, and
nothing in the answer would show that it had. The kernel's policies pass the
same test (`engine/kernel/world.py`), and the same test is inspected here.

What the court weighs is what it can count at home -- its stores, its mouths,
the fortnightly draw against them, the quantity its steward will not release --
and what the tablet asserts. Both arrive as dated claims from
`engine/foreign_belief.py`, and age is weighed rather than ignored: a count
taken five fortnights ago has had five fortnights of eating done against it, so
a court reckons a stale granary smaller than it was written down. That is why a
court can refuse from figures that would have let it accept when they were
fresh, and the refusal names the claim it read (spec 2.4).

Five answers, and each has a cause a reader can print:

    accept   it can do what was asked, and says so;
    counter  it can do part of it, and says exactly how much;
    refuse   it can spare nothing, or the match is not one it wants;
    delay    the household has not finished talking, or it has not yet counted;
    ignore   there is nothing to say, or the sender has asked once too often.

Nothing here draws on chance. Every answer follows from claims and arithmetic,
so `decide` can be run again years later against the stored case and print the
same reason -- which is how the inspector explains a refusal (spec 2.6).

`step` is the only part that touches World: it walks the open cases, asks the
policy, records the answer, hands a reply to the mail, and asks
`engine/letter_terms.py` to take any cargo out of the answering court's own
stores. What a court believes it can spare and what is actually in its granary
are two different figures; the reply carries the second one.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.believe import Belief
from engine.state import CorrespondenceCase, World

# How many fortnights of its own draw a court keeps back, on top of its floor,
# before calling anything spare. Not a difficulty knob: it is the reason a court
# with a full granary still says no to a large request in a thin year.
RESERVE_TURNS = 4

# A proposal of marriage is not answered by return of courier. It waits while
# the household talks, and then it is answered.
PROPOSAL_DELAY = 2

# Goods wanted further off than this are undertaken rather than loaded. A court
# does not send grain five fortnights before it is wanted; it promises it, and
# the promise is a dated obligation (SPEC.md 2.2).
PROMISE_HORIZON = 4

# How many separate days a sender may ask for the same good it cannot have
# before the court stops answering. Silence is an answer, and it is the one a
# court gives to a correspondent it has come to hold beneath a reply (spec 3.2).
SILENCE_AFTER = 3

# Person-days a court reckons it could raise per head in a fortnight. One: the
# rest of them are eating, sowing, or too old to walk to Ugarit.
DAYS_PER_HEAD = 1


@dataclasses.dataclass(frozen=True)
class Decision:
    """One court's answer, the claims it rested on, and why it gave it."""
    kind: str
    terms: tuple[A.LetterTerm, ...] = ()
    basis: tuple[str, ...] = ()
    delay_until: int = 0
    # A sentence, written from the figures the court read. Stored nowhere,
    # because `decide` is pure and can be asked again for it.
    reason: str = ""


@dataclasses.dataclass(frozen=True)
class Reckoning:
    """What one court makes of one good it has been asked for."""
    good: str
    wanted: int
    due: int
    spare: int
    age: int
    counted: bool
    basis: tuple[str, ...] = ()


# --- reading a tablet and a belief (no World, deliberately) -------------------

def _asks(case: CorrespondenceCase) -> tuple[tuple[str, int, int], ...]:
    """Every good this tablet asks for: good, quantity, the turn it is wanted.

    Two terms naming one good are one ask of the sum, because the granary does
    not care that it was written on two lines. Sorted, so a tablet asking for
    grain and oil is always reckoned in the same order.
    """
    wanted: dict[str, int] = {}
    due: dict[str, int] = {}
    for term in case.terms:
        if term.kind != "request_good" or not term.good:
            continue
        wanted[term.good] = wanted.get(term.good, 0) + term.quantity
        known = due.get(term.good, 0)
        due[term.good] = term.due_turn if not known else min(
            known, term.due_turn or known)
    return tuple((good, wanted[good], due.get(good, 0))
                 for good in sorted(wanted))


def _services(case: CorrespondenceCase) -> tuple[int, str]:
    """Person-days this tablet asks for, and where it wants them spent.

    One destination, the first named on the tablet: a court answering for its
    own people answers about one journey, and two places on one tablet are two
    matters the sender should have written twice.
    """
    asked = tuple(term for term in case.terms if term.kind == "service")
    days = sum(term.quantity for term in asked)
    return days, (asked[0].destination if asked else "")


def _tablet_basis(belief: Belief, case: CorrespondenceCase) -> tuple[str, ...]:
    """The claims this tablet itself left behind, sorted for a stable record."""
    return tuple(sorted(claim.id for claim in belief.about(case.letter_id)))


def _reckon(belief: Belief, home: str, good: str, wanted: int, due: int,
            turn: int) -> Reckoning:
    """What this court believes it could part with, and how old that belief is.

    The floor is subtracted whole -- a granary emptied for a friend is a granary
    emptied -- and the draw is subtracted once for each fortnight the court
    means to keep eating, plus once more for every fortnight since it counted.
    Old news is not treated as current news (spec 2.4).
    """
    stores = belief.best(home, f"stores_{good}")
    if stores is None:
        return Reckoning(good, wanted, due, 0, 0, counted=False)
    draw = belief.best(home, f"need_{good}")
    floor = belief.best(home, f"floor_{good}")
    read = tuple(claim for claim in (stores, draw, floor) if claim is not None)
    age = stores.age(turn)
    held_back = (floor.value if floor is not None else 0)
    held_back += (draw.value if draw is not None else 0) * (RESERVE_TURNS + age)
    return Reckoning(
        good, wanted, due, max(0, stores.value - held_back), age,
        counted=True, basis=tuple(sorted(claim.id for claim in read)))


def _times_asked(belief: Belief, good: str) -> tuple[int, tuple[str, ...]]:
    """On how many separate days this court has been asked for this good.

    A delivered request leaves claims dated to the day the sender sealed the
    tablet (`engine/foreign_belief.py`), so counting distinct `observed_turn`
    counts tablets rather than claims, and does it without this module knowing
    how another module builds a claim id. Two tablets sealed on one day are one
    asking, which is what they were.
    """
    held = tuple(claim for claim in belief.claims
                 if claim.attribute == f"request_good:{good}")
    days = {claim.observed_turn for claim in held}
    return len(days), tuple(sorted(claim.id for claim in held))


def _shortage(belief: Belief) -> tuple[int, str, tuple[str, ...]]:
    """What this court believes the sender is short of, and from which claim.

    Only a tablet can teach a court that somebody far off is short of grain, and
    the subject of such a claim is always the man who sealed the tablet, so the
    court's own place never appears here. Interested testimony, and it stays
    marked as interested: it is the sender's own account of his want.
    """
    claimed = tuple(claim for claim in belief.claims
                    if claim.attribute.startswith("short:"))
    if not claimed:
        return 0, "", ()
    worst = max(claimed, key=lambda claim: (claim.value, claim.id))
    return worst.value, worst.attribute.partition(":")[2], (worst.id,)


# --- the answers -------------------------------------------------------------

def _offer(good: str, quantity: int, due: int, turn: int) -> A.LetterTerm:
    """The term a court writes when it means to part with something.

    Near enough to load now, and the cargo travels with the tablet. Far enough
    off to undertake, and the tablet carries a dated promise and no goods at all
    (SPEC.md 2.2: a promise is not a faucet).
    """
    if due > turn + PROMISE_HORIZON:
        return A.LetterTerm(
            kind="promise_good", good=good, quantity=quantity, due_turn=due)
    return A.LetterTerm(kind="gift", good=good, quantity=quantity)


def _answer_goods(belief: Belief, home: str, case: CorrespondenceCase,
                  asks: tuple[tuple[str, int, int], ...], turn: int,
                  basis: tuple[str, ...]) -> Decision:
    """Answer a tablet that asks for goods, from what the court can count."""
    reckoned = tuple(
        _reckon(belief, home, good, wanted, due, turn)
        for good, wanted, due in asks)
    read = tuple(sorted(set(
        basis + tuple(claim for one in reckoned for claim in one.basis))))

    uncounted = tuple(one.good for one in reckoned if not one.counted)
    if uncounted:
        # It keeps no account of the thing it has been asked for. That is not a
        # refusal, which would be a statement about a granary it has never
        # counted; there is simply nothing it can say.
        return Decision(
            "ignore", basis=read,
            reason=(f"{home} keeps no count of "
                    + ", ".join(uncounted)
                    + ": it has nothing to say about it"))

    offers: list[A.LetterTerm] = []
    short: list[str] = []
    for one in reckoned:
        can = min(one.wanted, one.spare)
        if can > 0:
            offers.append(_offer(one.good, can, one.due, turn))
        if can < one.wanted:
            short.append(
                f"{one.good}: {one.wanted} asked, {one.spare} spare"
                + (f", counted {one.age} fortnights ago" if one.age else ""))

    if not offers:
        asked, asked_ids = 0, ()
        for one in reckoned:
            times, ids = _times_asked(belief, one.good)
            asked = max(asked, times)
            asked_ids += ids
        if asked >= SILENCE_AFTER:
            # Asked again for what it has already been unable to send. It stops
            # answering, and the king cannot tell that from a drowned courier.
            return Decision(
                "ignore", basis=tuple(sorted(set(read + asked_ids))),
                reason=(f"asked on {asked} separate days for "
                        + "; ".join(short) + ": no further answer"))
        return Decision(
            "refuse", basis=read,
            reason="it can spare none of what was asked -- " + "; ".join(short))

    if not short:
        return Decision(
            "accept", terms=tuple(offers), basis=read,
            reason="it can spare what was asked and undertakes to send it")
    return Decision(
        "counter", terms=tuple(offers), basis=read,
        reason="it offers what it can actually spare -- " + "; ".join(short))


def _answer_service(belief: Belief, home: str, days: int, where: str,
                    turn: int, basis: tuple[str, ...]) -> Decision:
    """Answer an ask for person-days out of the people this court counts."""
    people = belief.best(home, "people")
    if people is None:
        return Decision(
            "delay", delay_until=turn + 1, basis=basis,
            reason=f"{home} has not counted its people; the answer waits")
    read = basis + (people.id,)
    can = people.value * DAYS_PER_HEAD
    if can <= 0:
        return Decision(
            "refuse", basis=read,
            reason=f"{home} has nobody to send for {days} days of work")
    if can >= days:
        return Decision(
            "accept", basis=read,
            reason=f"{days} days of work from {people.value} people")
    return Decision(
        "counter",
        terms=(A.LetterTerm(
            kind="service", quantity=can, destination=where or home,
            due_turn=turn + 1),),
        basis=read,
        reason=(f"{days} days asked; {people.value} people can raise {can}"))


def _answer_proposal(belief: Belief, case: CorrespondenceCase, turn: int,
                     basis: tuple[str, ...]) -> Decision:
    """Answer a proposal of marriage once the household has talked.

    What the household talks about is whether the other house can keep a
    daughter, and the only thing this court knows about that is what the
    sender's own tablets have said. A house that has written asking for grain
    has said it is short of grain, and a court that has been told so weighs it
    (spec 2.4: interested testimony stays visible as interested).
    """
    if case.received_turn + PROPOSAL_DELAY > turn:
        return Decision(
            "delay", delay_until=case.received_turn + PROPOSAL_DELAY,
            basis=basis,
            reason="the household has not finished talking about the match")
    want, good, cited = _shortage(belief)
    if want > 0:
        return Decision(
            "refuse", basis=basis + cited,
            reason=(f"the house that proposes has asked for {want} {good}: "
                    "not a house to marry into"))
    return Decision(
        "accept", basis=basis,
        reason="the match is agreeable and the household has said so")


def decide(actor: str, belief: Belief, case: CorrespondenceCase,
           turn: int) -> Decision:
    """The court's answer to one tablet. Reads belief; reads nothing else.

    The matters of a tablet are weighed in order of gravity. A tablet that asks
    for goods is answered on the goods, because that is what the reply has to
    carry; labour next; a proposal of marriage only when it stands alone, since
    a tablet that begs for grain and offers a daughter in the same breath is
    answered on the grain. A gift or a promise is received and acknowledged.
    """
    home = case.place
    basis = _tablet_basis(belief, case)
    if not case.terms:
        # Nothing was asked and nothing offered. There is no answer to write.
        return Decision(
            "ignore", basis=basis,
            reason="the tablet asks nothing and offers nothing")
    if not belief.about(home):
        # It has not yet looked round its own courtyard. It will not answer for
        # a granary it has never counted.
        return Decision(
            "delay", delay_until=turn + 1, basis=basis,
            reason=f"{home} has not counted its own stores yet")

    asks = _asks(case)
    if asks:
        return _answer_goods(belief, home, case, asks, turn, basis)
    days, where = _services(case)
    if days > 0:
        return _answer_service(belief, home, days, where, turn, basis)
    if any(term.kind == "marriage_proposal" for term in case.terms):
        return _answer_proposal(belief, case, turn, basis)
    return Decision(
        "accept", basis=basis,
        reason="a gift or a promise, received and acknowledged")


# --- the World side: recording, replying, and parting with goods -------------

def _decided(case: CorrespondenceCase, decision: Decision,
             turn: int) -> CorrespondenceCase:
    return dataclasses.replace(
        case,
        decision=decision.kind,
        decided_turn=turn,
        counter_terms=decision.terms if decision.kind == "counter" else (),
        basis=decision.basis,
        delay_until=decision.delay_until if decision.kind == "delay" else 0,
    )


def _affordable(world: World, actor: str, decision: Decision) -> Decision:
    """Cut the cargo down to what is actually in that court's granary.

    The decision was made from belief, and belief can be wrong or old. What
    leaves is limited by World, so the tablet states the quantity that was
    really loaded rather than the quantity the steward expected to find. A court
    that opens the granary and finds nothing above its floor writes a refusal
    instead, and that is the divergence being modelled, not a rounding error.
    """
    cargo = tuple(term for term in decision.terms if term.kind == "gift")
    if not cargo:
        return decision
    from engine import letter_terms

    loaded: list[A.LetterTerm] = []
    cut: list[str] = []
    for term in decision.terms:
        if term.kind != "gift":
            loaded.append(term)
            continue
        have = letter_terms.spare_in_court(world, actor, term.good)
        if have >= term.quantity:
            loaded.append(term)
            continue
        cut.append(f"{term.good}: {term.quantity} meant, {have} found")
        if have > 0:
            loaded.append(dataclasses.replace(term, quantity=have))
    if not cut:
        return decision
    if not any(term.kind == "gift" for term in loaded):
        return dataclasses.replace(
            decision, kind="refuse", terms=(),
            reason=(decision.reason + " -- but the granary held less than the "
                    "count said: " + "; ".join(cut)))
    return dataclasses.replace(
        decision, kind="counter", terms=tuple(loaded),
        reason=(decision.reason + " -- loaded short: " + "; ".join(cut)))


def step(world: World) -> tuple[World, list]:
    """Answer every case whose turn to be answered has come."""
    from engine import foreign_belief, letter_terms, mail

    now = world.date.absolute
    events: list = []
    cases = list(world.correspondence)
    for index, case in enumerate(cases):
        if not case.open() or case.delay_until > now:
            continue
        belief = foreign_belief.belief_of(world, case.actor)
        decision = decide(case.actor, belief, case, now)
        decision = _affordable(world, case.actor, decision)
        decided = _decided(case, decision, now)
        if decision.kind in {"accept", "refuse", "counter"}:
            world, reply, sent = mail.foreign_reply(world, decided, decision)
            events += sent
            # The cargo leaves the granary now, whether or not it ever arrives:
            # a hijacked caravan is a loss, not an absence (SPEC.md 2.2).
            stolen = any(
                isinstance(event, A.LetterIntercepted) and
                event.letter_id == reply.id for event in sent)
            world = letter_terms.load_court_cargo(
                world, case.actor, reply, intercepted=stolen)
            decided = dataclasses.replace(decided, reply_letter_id=reply.id)
        cases[index] = decided
        world = dataclasses.replace(world, correspondence=tuple(cases))
        cases = list(world.correspondence)
    return dataclasses.replace(world, correspondence=tuple(cases)), events
