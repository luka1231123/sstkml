"""Relations, gifts, gossip, oaths, and hidden misfortune (spec 6.8-6.9)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine import actions as A
from engine.core import canonical_json, lerp_table, stream
from engine.state import GiftRecord, Relation, Scheduled, World


def _clamp(value: int, low: int = 0, high: int = 1000) -> int:
    return low if value < low else high if value > high else value


def schedule(world: World, at: int, payload: object) -> World:
    items = world.schedule + (Scheduled(at, payload),)
    return dataclasses.replace(
        world, schedule=tuple(sorted(
            items, key=lambda item: (item.at, canonical_json(item.payload)))))


def evaluate_gift(relation: Relation, value: int,
                  reciprocity: tuple[tuple[int, int], ...],
                  status_floors: Mapping[str, int]) -> tuple[Relation, int, int]:
    expected = max(
        relation.last_gift_from_them
        * lerp_table(reciprocity, relation.esteem) // 1000,
        relation.best_known_rival_gift * 900 // 1000,
        status_floors.get(relation.their_status_claim, 0),
    )
    adequacy = 1000 * value // max(1, expected)
    obligation = relation.obligation
    if adequacy < 700:
        delta = -150
    elif adequacy < 900:
        delta = -40
    elif adequacy < 1100:
        delta = 30
        obligation += value // 4
    elif adequacy < 1500:
        delta = 70
        obligation += value // 3
    else:
        delta = 90
        obligation += value // 3
    return dataclasses.replace(
        relation, esteem=_clamp(relation.esteem + delta),
        obligation=obligation, last_gift_from_us=value,
    ), adequacy, delta


def send_gift(world: World, action: A.SendGift) -> tuple[World, list]:
    relation = world.relations.get(action.recipient)
    if relation is None:
        raise ValueError(f"unknown correspondent: {action.recipient}")
    if action.quantity <= 0:
        raise ValueError("gift quantity must be positive")
    unit_value = world.gift_values.get(action.good)
    if unit_value is None:
        raise ValueError(f"{action.good} is not a gift good")
    stores = dict(world.court.stores)
    if stores.get(action.good, 0) < action.quantity:
        raise ValueError(f"not enough {action.good} for that gift")

    from engine.mail import route_latency
    gift_id = f"G{world.gift_seq + 1}"
    value = action.quantity * unit_value
    arrival = world.date.absolute + route_latency(
        world.routes, world.court.seat, relation.place,
        world.season, world.date.fortnight)
    record = GiftRecord(
        gift_id, world.court.actor, action.recipient, action.good,
        action.quantity, value, world.date.absolute)
    stores[action.good] -= action.quantity
    court = dataclasses.replace(
        world.court, stores=stores,
        treasury_gifts_sent=world.court.treasury_gifts_sent + (record,))
    world = dataclasses.replace(
        world, court=court, gift_seq=world.gift_seq + 1)
    world = schedule(world, arrival, A.GiftArrived(gift_id))
    return world, [A.GiftSent(
        gift_id, action.recipient, action.good, action.quantity, value, arrival)]


def _receive_gift(world: World, gift_id: str) -> tuple[World, list]:
    record = next(
        (gift for gift in world.court.treasury_gifts_sent if gift.id == gift_id),
        None)
    if record is None:
        raise ValueError(f"scheduled unknown gift: {gift_id}")
    relation = world.relations[record.recipient]
    relation, adequacy, delta = evaluate_gift(
        relation, record.value, world.reciprocity_table,
        world.gift_status_floors)
    relations = dict(world.relations)
    relations[relation.other] = relation
    gifts = tuple(
        dataclasses.replace(
            gift, arrive_turn=world.date.absolute, adequacy=adequacy)
        if gift.id == gift_id else gift
        for gift in world.court.treasury_gifts_sent
    )
    world = dataclasses.replace(
        world, relations=relations,
        court=dataclasses.replace(world.court, treasury_gifts_sent=gifts))

    from engine import mail
    for observer, other in sorted(world.relations.items()):
        if observer == record.recipient:
            continue
        delay = mail.route_latency(
            world.routes, relation.place, other.place,
            world.season, world.date.fortnight)
        world = schedule(
            world, world.date.absolute + delay,
            A.RumourArrived(observer, record.recipient, record.value))
    if adequacy < 700:
        world = mail.inject_incoming(
            world, record.recipient, relation.place, "gift_insult",
            (("good", record.good), ("quantity", record.quantity)))
    return world, [A.GiftJudged(gift_id, record.recipient, adequacy, delta)]


def _learn_rumour(world: World, event: A.RumourArrived) -> World:
    relation = world.relations.get(event.observer)
    if relation is None or event.gift_value <= relation.best_known_rival_gift:
        return world
    relations = dict(world.relations)
    relations[event.observer] = dataclasses.replace(
        relation, best_known_rival_gift=event.gift_value,
        known_rival_gift_source=event.subject)
    return dataclasses.replace(world, relations=relations)


def resolve_scheduled(world: World, payloads: list) -> tuple[World, list]:
    events = []
    for payload in payloads:
        if isinstance(payload, A.GiftArrived):
            world, resolved = _receive_gift(world, payload.gift_id)
            events += resolved
        elif isinstance(payload, A.RumourArrived):
            world = _learn_rumour(world, payload)
            events.append(payload)
        elif isinstance(payload, A.PatronNoticeDue):
            relation = world.relations.get(payload.actor)
            if relation is not None and not relation.patron_notice_received:
                relations = dict(world.relations)
                relations[payload.actor] = dataclasses.replace(
                    relation, patron_notice_received=True)
                world = dataclasses.replace(world, relations=relations)
                events.append(A.PatronSought(payload.actor))
        else:
            events.append(payload)
    return world, events


def update_unanswered(world: World) -> World:
    relations = dict(world.relations)
    now = world.date.absolute
    for actor, relation in sorted(relations.items()):
        pending = any(
            not letter.outgoing and letter.sender == actor
            and letter.answered_turn is None
            for letter in world.inbox
        )
        count = relation.unanswered_letters_from_them + 1 if pending else 0
        esteem = relation.esteem - 30 if count >= 3 else relation.esteem
        seeking = relation.seeking_patron
        if count >= 6 and relation.is_vassal and not seeking:
            seeking = True
            delay = 2 + stream(
                world.seed, now, "relations.patron_notice", actor).int(3)
            world = schedule(world, now + delay, A.PatronNoticeDue(actor))
        relations[actor] = dataclasses.replace(
            relation, unanswered_letters_from_them=count,
            esteem=_clamp(esteem), seeking_patron=seeking)
    return dataclasses.replace(world, relations=relations)


def deliver_protocol(world: World, letter) -> tuple[World, list]:
    if not letter.protocol_profile or letter.recipient not in world.relations:
        return world, []
    record = next(
        (item for item in world.protocol_log if item.letter_id == letter.id),
        None)
    if record is not None and record.applied_turn is not None:
        return world, []
    relation = world.relations[letter.recipient]
    rules = world.protocol_rules
    violations = tuple(letter.protocol_violations)
    delta = 0
    if not violations:
        if letter.protocol_total >= rules.get("good_floor", 900):
            delta = rules.get("good_delta", 0)
        elif letter.protocol_total < rules.get("poor_floor", 700):
            delta = rules.get("poor_delta", 0)
    else:
        known = {
            "kinship_overreach": rules.get("kinship_overreach", -200),
            "excuse_and_request": rules.get("excuse_and_request", -90),
            "missing_prostration": rules.get("missing_prostration", -120),
        }
        for violation in violations:
            if violation != "wrong_oath_gods":
                delta += known.get(
                    violation, rules.get("other_violation", -40))

    court = world.court
    delay_until = relation.reply_delay_until
    if "wrong_oath_gods" in violations:
        matching = [
            oath for oath in world.oaths
            if not oath.dissolved and letter.recipient in oath.parties
        ]
        if len(matching) == 1:
            oath = matching[0]
            liability = dict(court.liability)
            liability[oath.id] = liability.get(oath.id, 0) + max(
                1, sum(world.god_ranks.get(god, 1) for god in oath.gods))
            court = dataclasses.replace(court, liability=liability)
        delay_until = max(
            delay_until, world.date.absolute
            + rules.get("wrong_god_reply_delay", 2))

    relations = dict(world.relations)
    relations[letter.recipient] = dataclasses.replace(
        relation, esteem=_clamp(relation.esteem + delta),
        reply_delay_until=delay_until,
        status_mismatch_known=(
            relation.status_mismatch_known
            or (relation.status_claim != relation.their_status_claim
                and ("kinship_overreach" in violations
                     or "wrong_address" in violations))))
    records = tuple(
        dataclasses.replace(record, applied_turn=world.date.absolute)
        if record.letter_id == letter.id and record.applied_turn is None
        else record
        for record in world.protocol_log
    )
    return dataclasses.replace(
        world, court=court, relations=relations,
        protocol_log=records), [
            A.ProtocolApplied(letter.recipient, delta, violations)]


def _clause_violated(world: World, oath, clause) -> bool:
    args = dict(clause.args)
    if clause.kind == "provide_goods":
        if not args.get("per_year") or world.date.fortnight != 24:
            return False
        other = next(actor for actor in oath.parties
                     if actor != world.court.actor)
        year_start = world.date.absolute - 23
        delivered = sum(
            gift.quantity for gift in world.court.treasury_gifts_sent
            if gift.recipient == other and gift.good == args["good"]
            and gift.arrive_turn is not None
            and year_start <= gift.arrive_turn <= world.date.absolute
        )
        return delivered < int(args["qty"])
    if clause.kind == "maintain_rite":
        # A vow that a named festival will be kept, every year, for ever
        # (spec 6.12's "quietly violable"). It is checked once a year, on the
        # fortnight it names, and it is violated if that rite is simply not on
        # the court's calendar any more -- which is the ordinary fate of a
        # festival nobody alive remembers being told to keep. The player is
        # never notified, because nobody at court knows either. It is in the
        # archive, and only in the archive.
        if world.date.fortnight != int(args["fortnight"]):
            return False
        return not any(rite.id == args["rite"] for rite in world.court.rites)
    if clause.kind == "no_contact_with":
        actor = args["actor"]
        return any(
            record.recipient == actor
            for record in world.protocol_log
        )
    raise ValueError(f"unsupported oath clause: {clause.kind}")


def audit_oaths(world: World) -> tuple[World, list]:
    liability = dict(world.court.liability)
    events = []
    for oath in sorted(world.oaths, key=lambda value: value.id):
        # A lapsed oath binds nobody (spec 6.9, M9): the man who swore it is
        # dead, and until a living man swears again there is no relationship to
        # violate and no god to offend. This is not a loophole -- it is why
        # every succession anywhere is a diplomatic emergency.
        if oath.dissolved or oath.lapsed:
            continue
        weight = max(
            1, sum(world.god_ranks.get(god, 1) for god in oath.gods))
        for clause in oath.clauses:
            if _clause_violated(world, oath, clause):
                liability[oath.id] = liability.get(oath.id, 0) + weight
                events.append(A.OathViolated(oath.id, clause.kind))
    return dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, liability=liability)), events


def draw_misfortune(world: World) -> tuple[World, list]:
    total_liability = sum(world.court.liability.values())
    pressure = total_liability + world.court.misfortune_weight
    if pressure <= 0 or not world.misfortune_deck:
        return world, []
    rng = stream(world.seed, world.date.absolute, "deck", "misfortune")
    if not rng.chance(min(900, pressure), 1000):
        return world, []
    card = rng.weighted(tuple(
        (item, item.weight
         + pressure * item.liability_weight // 100)
        for item in world.misfortune_deck
    ))
    stores = dict(world.court.stores)
    material_loss = 0
    if card.good:
        before = stores.get(card.good, 0)
        stores[card.good] = max(0, before - card.loss)
        material_loss = before - stores[card.good]
    court = dataclasses.replace(
        world.court, stores=stores,
        legitimacy=_clamp(
            world.court.legitimacy + card.legitimacy_delta),
        unrest=_clamp(world.court.unrest + card.unrest_delta))
    return dataclasses.replace(world, court=court), [
        A.MisfortuneOccurred(card.id, card.good, material_loss)]
