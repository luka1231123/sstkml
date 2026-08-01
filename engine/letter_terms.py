"""Pure material and legal consequences of structured letter terms.

Dispatch and delivery call these helpers at their respective boundaries.  The
module does not move couriers, marry people, or satisfy promises.  It reserves
physical gifts exactly once and returns immutable records for the parent
integration to persist with the letter that created them.

Both directions land here, and the rule is the same in both (SPEC.md 2.2).
Nothing may enter a store that did not leave a named store somewhere else, on a
recorded turn, carried by something that arrived.  `reserve_terms_at_dispatch`
and `load_court_cargo` are the two places goods leave -- Ugarit's own treasury
and a foreign court's granary; `apply_delivered_terms` and
`apply_incoming_terms` are the two places they land.  A promise leaves nothing
and lands as a dated obligation, because a promise is not a faucet.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from engine import actions as A
from engine import actors
from engine import seat
from engine import obligation as O
from engine.state import GiftRecord, World


@dataclasses.dataclass(frozen=True)
class DispatchTerms:
    world: World
    reservations: tuple[O.GoodsReservation, ...] = ()
    obligations: tuple[O.LetterObligation, ...] = ()


@dataclasses.dataclass(frozen=True)
class DeliveredTerms:
    gifts: tuple[O.GoodsReservation, ...] = ()
    obligations: tuple[O.LetterObligation, ...] = ()
    claims: tuple[O.RequestClaim, ...] = ()
    proposals: tuple[O.MarriageProposal, ...] = ()


def _known_actors(world: World) -> set[str]:
    return (
        {world.court.actor}
        | set(world.relations)
        | {person.id for person in world.court.house.values()}
        | {correspondent.actor for correspondent in world.correspondents}
    )


def _known_goods(world: World) -> set[str]:
    return (
        set(seat.held(world))
        | set(world.gift_values)
        | set(world.works_materials)
        | ({world.revenue_good} if world.revenue_good else set())
    )


def _validate_term(world: World, term: A.LetterTerm, recipient: str,
                   *, check_inventory: bool,
                   promise_after: int,
                   require_living_person: bool = True) -> A.LetterTerm:
    if not isinstance(term, A.LetterTerm):
        raise TypeError("letter terms must be LetterTerm values")
    recipient = actors.canonical(world, recipient)
    if recipient not in _known_actors(world):
        raise ValueError(f"unknown letter recipient: {recipient}")

    if term.kind in {"gift", "request_good", "promise_good"}:
        if term.good not in _known_goods(world):
            raise ValueError(f"unknown good in letter term: {term.good}")
    if term.kind == "gift":
        if term.good not in world.gift_values:
            raise ValueError(f"{term.good} is not a gift good")
        if check_inventory and seat.held(world).get(term.good, 0) < term.quantity:
            raise ValueError(f"not enough {term.good} for that gift")
    elif term.kind == "promise_good":
        if term.due_turn <= promise_after:
            raise ValueError("a promised good needs a future due turn")
    elif term.kind == "service":
        if term.destination not in world.places:
            raise ValueError(
                f"unknown service destination: {term.destination}")
    elif term.kind == "marriage_proposal":
        person = world.court.house.get(term.person_id)
        if person is None or (require_living_person and not person.alive):
            raise ValueError(
                f"marriage proposal needs a living person: {term.person_id}")
    return term


def validate_term(world: World, term: A.LetterTerm,
                  recipient: str) -> A.LetterTerm:
    """Validate one term against current world truth, returning it unchanged."""
    return _validate_term(
        world, term, recipient, check_inventory=True,
        promise_after=world.date.absolute)


def _carrier(world: World, letter_or_action) -> tuple[
        str, str, str, int, tuple[A.LetterTerm, ...]]:
    terms = tuple(getattr(letter_or_action, "terms", ()))
    if not all(isinstance(term, A.LetterTerm) for term in terms):
        raise TypeError("letter terms must be LetterTerm values")
    source = str(
        getattr(letter_or_action, "id", "") or f"L{world.letter_seq + 1}")
    sender = actors.canonical(
        world, str(getattr(letter_or_action, "sender", "") or world.court.actor))
    recipient = actors.canonical(
        world, str(getattr(letter_or_action, "recipient", "")))
    sent_turn = int(
        getattr(letter_or_action, "sent_turn", world.date.absolute))
    return source, sender, recipient, sent_turn, terms


def _term_id(source: str, index: int) -> str:
    return f"{source}:term:{index}"


def _reservation(source: str, index: int, sender: str, recipient: str,
                 sent_turn: int, term: A.LetterTerm) -> O.GoodsReservation:
    return O.GoodsReservation(
        id=_term_id(source, index),
        source_letter=source,
        term_index=index,
        party=sender,
        beneficiary=recipient,
        authority=sender,
        good=term.good,
        quantity=term.quantity,
        created_turn=sent_turn,
        due_turn=term.due_turn,
        history=(f"turn {sent_turn}: reserved at dispatch",),
    )


def _obligation(source: str, index: int, sender: str, recipient: str,
                sent_turn: int, term: A.LetterTerm,
                delivered_turn: int | None = None) -> O.LetterObligation:
    due = term.due_turn
    history = (f"turn {sent_turn}: promised in {source}",)
    status = "promised"
    if delivered_turn is not None:
        history += (
            f"turn {delivered_turn}: delivered to {recipient}",
        )
        status = (
            "overdue"
            if due and delivered_turn > due else "delivered")
    return O.LetterObligation(
        id=_term_id(source, index),
        source_letter=source,
        term_index=index,
        party=sender,
        beneficiary=recipient,
        authority=sender,
        kind=term.kind,
        good=term.good,
        quantity=term.quantity,
        destination=term.destination,
        created_turn=sent_turn,
        due_turn=due,
        status=status,
        history=history,
    )


def _gift_records(records: Iterable[GiftRecord]) -> dict[str, GiftRecord]:
    return {record.id: record for record in records}


def _merge_records(existing: tuple, incoming: Iterable) -> tuple:
    """Replace matching immutable records and append new IDs in stable order."""
    additions = {record.id: record for record in incoming}
    merged = tuple(
        additions.pop(record.id, record)
        for record in existing
    )
    return merged + tuple(
        additions[key] for key in sorted(additions)
    )


def reserve_terms_at_dispatch(
        world: World, letter_or_action) -> DispatchTerms:
    """Atomically reserve gifts and record promises at dispatch.

    Existing reservation IDs make the operation idempotent.  Reapplying the
    same letter returns the same world and records; changing a term beneath an
    existing letter ID is rejected.
    """
    source, sender, recipient, sent_turn, terms = _carrier(
        world, letter_or_action)
    gifts = _gift_records(world.court.treasury_gifts_sent)
    new_gifts: list[tuple[int, A.LetterTerm, O.GoodsReservation]] = []
    reservations: list[O.GoodsReservation] = []
    obligations: list[O.LetterObligation] = []

    for index, term in enumerate(terms):
        marker = _term_id(source, index)
        existing = gifts.get(marker)
        _validate_term(
            world, term, recipient,
            check_inventory=not (term.kind == "gift" and existing is not None),
            promise_after=sent_turn)
        if term.kind == "gift":
            reservation = _reservation(
                source, index, sender, recipient, sent_turn, term)
            if existing is not None:
                identity = (
                    existing.sender, existing.recipient,
                    existing.good, existing.quantity)
                wanted = (sender, recipient, term.good, term.quantity)
                if identity != wanted:
                    raise ValueError(
                        f"{marker} already reserves different goods")
            else:
                new_gifts.append((index, term, reservation))
            reservations.append(reservation)
        elif term.kind in {"promise_good", "service"}:
            obligations.append(_obligation(
                source, index, sender, recipient, sent_turn, term))

    totals: dict[str, int] = {}
    for _index, term, _reservation_record in new_gifts:
        totals[term.good] = totals.get(term.good, 0) + term.quantity
    for good, quantity in totals.items():
        if seat.held(world).get(good, 0) < quantity:
            raise ValueError(f"not enough {good} for all gifts on this letter")

    if new_gifts:
        stores = seat.held(world)
        records = list(world.court.treasury_gifts_sent)
        for _index, term, reservation in new_gifts:
            stores[term.good] -= term.quantity
            records.append(GiftRecord(
                id=reservation.id,
                sender=sender,
                recipient=recipient,
                good=term.good,
                quantity=term.quantity,
                value=term.quantity * world.gift_values[term.good],
                sent_turn=sent_turn,
            ))
        world = seat.put(dataclasses.replace(
            world,
            court=dataclasses.replace(
                world.court,
                treasury_gifts_sent=tuple(records),
            ),
        ), stores, reason_down="expended")
    world = dataclasses.replace(
        world,
        letter_reservations=_merge_records(
            world.letter_reservations, reservations),
        letter_obligations=_merge_records(
            world.letter_obligations, obligations),
    )
    return DispatchTerms(world, tuple(reservations), tuple(obligations))


def _delivered_reservation(
        reservation: O.GoodsReservation, turn: int) -> O.GoodsReservation:
    return dataclasses.replace(
        reservation,
        status="delivered",
        history=reservation.history + (f"turn {turn}: delivered",),
    )


def apply_delivered_terms(
        world: World, letter) -> tuple[World, DeliveredTerms]:
    """Apply terms whose physical tablet has arrived.

    Gifts must already have been reserved, so delivery cannot mint inventory.
    Promises and service become delivered obligations, requests become claims,
    and marriage remains a pending proposal concerning a still-living person.
    """
    source, sender, recipient, sent_turn, terms = _carrier(world, letter)
    turn = world.date.absolute
    gifts = _gift_records(world.court.treasury_gifts_sent)
    delivered_gifts: list[O.GoodsReservation] = []
    obligations: list[O.LetterObligation] = []
    claims: list[O.RequestClaim] = []
    proposals: list[O.MarriageProposal] = []
    gift_updates: dict[str, GiftRecord] = {}
    existing_reservations = {
        record.id: record for record in world.letter_reservations}
    existing_obligations = {
        record.id: record for record in world.letter_obligations}
    existing_claims = {
        record.id: record for record in world.letter_claims}
    existing_proposals = {
        record.id: record for record in world.marriage_proposals}

    for index, term in enumerate(terms):
        _validate_term(
            world, term, recipient, check_inventory=False,
            promise_after=sent_turn, require_living_person=False)
        record_id = _term_id(source, index)
        if term.kind == "gift":
            record = gifts.get(record_id)
            if record is None:
                raise ValueError(
                    f"{record_id} was not reserved at dispatch")
            reservation = existing_reservations.get(record_id)
            if reservation is None:
                reservation = _reservation(
                    source, index, sender, recipient, sent_turn, term)
            delivered_turn = (
                record.arrive_turn if record.arrive_turn is not None else turn)
            delivered_gifts.append(
                reservation
                if reservation.status == "delivered"
                else _delivered_reservation(reservation, delivered_turn))
            if record.arrive_turn is None:
                gift_updates[record_id] = dataclasses.replace(
                    record, arrive_turn=turn)
        elif term.kind in {"promise_good", "service"}:
            existing = existing_obligations.get(record_id)
            obligations.append(
                existing
                if existing is not None
                and existing.status in {"delivered", "overdue"}
                else _obligation(
                    source, index, sender, recipient, sent_turn, term, turn))
        elif term.kind == "request_good":
            existing = existing_claims.get(record_id)
            claims.append(existing or O.RequestClaim(
                id=record_id, source_letter=source, term_index=index,
                party=recipient, beneficiary=sender, authority=sender,
                good=term.good, quantity=term.quantity, created_turn=turn,
                due_turn=term.due_turn or turn,
                history=(f"turn {turn}: claim delivered from {sender}",),
            ))
        elif term.kind == "marriage_proposal":
            existing = existing_proposals.get(record_id)
            if existing is not None:
                proposals.append(existing)
                continue
            person = world.court.house[term.person_id]
            status = "pending" if person.alive else "lapsed"
            note = (
                f"turn {turn}: proposal delivered to {recipient}"
                if person.alive else
                f"turn {turn}: proposal lapsed; {term.person_id} died"
            )
            proposals.append(O.MarriageProposal(
                id=record_id, source_letter=source, term_index=index,
                party=sender, beneficiary=recipient, authority=sender,
                person_id=term.person_id, created_turn=turn,
                due_turn=term.due_turn or turn, status=status,
                history=(note,),
            ))

    if gift_updates:
        records = tuple(
            gift_updates.get(record.id, record)
            for record in world.court.treasury_gifts_sent)
        world = dataclasses.replace(
            world,
            court=dataclasses.replace(
                world.court, treasury_gifts_sent=records),
        )
    world = dataclasses.replace(
        world,
        letter_reservations=_merge_records(
            world.letter_reservations, delivered_gifts),
        letter_obligations=_merge_records(
            world.letter_obligations, obligations),
        letter_claims=_merge_records(world.letter_claims, claims),
        marriage_proposals=_merge_records(
            world.marriage_proposals, proposals),
    )
    return world, DeliveredTerms(
        tuple(delivered_gifts),
        tuple(obligations),
        tuple(claims),
        tuple(proposals),
    )


def spare_in_court(world: World, actor: str, good: str) -> int:
    """What a foreign court could actually hand over today, floor respected.

    World, not belief. `engine/correspondence_policy.py` decides from what the
    court believes and then asks this what is really in the granary, so that a
    tablet states the quantity that was loaded rather than the quantity the
    steward expected to find.
    """
    from engine import foreign_belief

    owner = foreign_belief.actor_of(world, actor)
    settlement = foreign_belief.settlement_of(world, actor)
    if not owner or not settlement:
        return 0
    return sum(lot.free for lot in world.kernel.book.at(settlement)
               if lot.owner == owner and lot.good == good)


def load_court_cargo(world: World, actor: str, letter,
                     *, intercepted: bool = False) -> World:
    """Take the cargo of a court's own reply out of that court's own stores.

    The one place a foreign court parts with anything. Every quantity that will
    later enter Ugarit's stores leaves a named granary here first, on a recorded
    turn, with the tablet that carries it named on the record -- so the arrival
    can be traced back to the place it came out of (SPEC.md 2.2).

    Idempotent on the reservation id: a replayed dispatch of the same reply
    empties the granary once. An intercepted caravan is still gone from the
    granary; it simply never arrives, and the record says which happened.
    """
    from engine import foreign_belief

    source, sender, recipient, sent_turn, terms = _carrier(world, letter)
    owner = foreign_belief.actor_of(world, actor)
    settlement = foreign_belief.settlement_of(world, actor)
    if not owner or not settlement:
        return world
    held = {record.id: record for record in world.letter_reservations}
    book = world.kernel.book.at_phase(sent_turn, "movement")
    recorded: list[O.GoodsReservation] = []
    for index, term in enumerate(terms):
        if term.kind != "gift" or term.quantity <= 0:
            continue
        record_id = _term_id(source, index)
        if record_id in held:
            continue
        # Never more than is there. The policy has already cut the quantity to
        # fit; this is the guard that keeps a bug from minting grain.
        wanted = term.quantity
        moved = 0
        lots = tuple(lot for lot in book.at(settlement)
                     if lot.owner == owner and lot.good == term.good)
        for lot in lots:
            take = min(wanted - moved, lot.free)
            if take:
                book = book.consume(
                    lot.id, take, "lost" if intercepted else "expended",
                    authority=owner)
                moved += take
            if moved >= wanted:
                break
        note = (
            f"turn {sent_turn}: {moved} {term.good} left {settlement} "
            f"with {source} for {recipient}")
        recorded.append(O.GoodsReservation(
            id=record_id, source_letter=source, term_index=index,
            party=sender or actor, beneficiary=recipient,
            authority=sender or actor, good=term.good, quantity=moved,
            created_turn=sent_turn, due_turn=term.due_turn,
            status="intercepted" if intercepted else "reserved",
            history=(note,) + ((
                f"turn {sent_turn}: carrier intercepted; the cargo is lost",)
                if intercepted else ()),
        ))
    if not recorded:
        return world
    kernel = dataclasses.replace(world.kernel, book=book)
    return dataclasses.replace(
        world, kernel=kernel,
        letter_reservations=_merge_records(
            world.letter_reservations, recorded),
    )


def apply_incoming_terms(world: World, letter) -> tuple[World, list]:
    """Apply terms carried by a tablet that has reached the court.

    The receiving counterpart to `apply_delivered_terms`. Two things land here, and the
    difference between them is SPEC.md 2.2 entire.

    A promise becomes a dated obligation the court can hold the sender to. No
    goods move: a promise is not a faucet.

    A cargo enters the court's stores -- but only a cargo that left a named
    granary, which `load_court_cargo` recorded when it was loaded. A gift term
    with no such record is refused rather than honoured, because there is no
    place for it to have come out of and admitting it would create grain.

    Idempotent on the reservation and obligation ids, so a replayed delivery
    records the same promise once and lands the same cargo once.
    """
    source, sender, _recipient, sent_turn, terms = _carrier(world, letter)
    turn = world.date.absolute
    owed = {record.id: record for record in world.letter_obligations}
    shipped = {record.id: record for record in world.letter_reservations}
    recorded: list[O.LetterObligation] = []
    landed: list[O.GoodsReservation] = []
    stores = seat.held(world)
    for index, term in enumerate(terms):
        record_id = _term_id(source, index)
        if term.kind in {"promise_good", "service"}:
            if record_id in owed:
                recorded.append(owed[record_id])
                continue
            recorded.append(O.LetterObligation(
                id=record_id, source_letter=source, term_index=index,
                party=sender, beneficiary=world.court.actor, authority=sender,
                kind=term.kind, good=term.good, quantity=term.quantity,
                destination=term.destination or world.court.seat,
                created_turn=sent_turn, due_turn=term.due_turn or turn,
                status="delivered",
                history=(f"turn {turn}: promised by {sender}",),
            ))
        elif term.kind == "gift":
            cargo = shipped.get(record_id)
            if cargo is None:
                raise ValueError(
                    f"{record_id}: cargo that left nobody's stores")
            if cargo.status == "delivered":
                continue
            stores[cargo.good] = int(
                stores.get(cargo.good, 0)) + cargo.quantity
            landed.append(dataclasses.replace(
                cargo, status="delivered",
                history=cargo.history + (
                    f"turn {turn}: {cargo.quantity} {cargo.good} entered "
                    f"{world.court.seat}",)))
    if not recorded and not landed:
        return world, []
    if landed:
        world = seat.put(world, stores)
    # An increase in the court's stores that no production explains needs an
    # event, or the conservation audit is right to call it grain from nowhere.
    events: list = [
        A.CargoLanded(cargo.id, cargo.party, cargo.good, cargo.quantity)
        for cargo in landed
    ]
    return dataclasses.replace(
        world,
        letter_obligations=_merge_records(world.letter_obligations, recorded),
        letter_reservations=_merge_records(world.letter_reservations, landed),
    ), events


def mark_intercepted_terms(world: World, letter) -> World:
    """Record hidden terminal custody without telling the sending court."""
    source, _sender, _recipient, _sent_turn, _terms = _carrier(world, letter)
    note = f"turn {world.date.absolute}: carrier intercepted"
    reservations = tuple(
        dataclasses.replace(
            record, status="intercepted",
            history=record.history + (note,))
        if record.source_letter == source and record.status == "reserved"
        else record
        for record in world.letter_reservations
    )
    obligations = tuple(
        dataclasses.replace(
            record, status="sealed_undelivered",
            history=record.history + (note,))
        if record.source_letter == source and record.status == "promised"
        else record
        for record in world.letter_obligations
    )
    return dataclasses.replace(
        world,
        letter_reservations=reservations,
        letter_obligations=obligations,
    )


__all__ = [
    "DeliveredTerms",
    "DispatchTerms",
    "apply_delivered_terms",
    "apply_incoming_terms",
    "load_court_cargo",
    "mark_intercepted_terms",
    "reserve_terms_at_dispatch",
    "spare_in_court",
    "validate_term",
]
