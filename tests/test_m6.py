"""M6 relations: gifts, gossip, protocol, unanswered letters, and oaths."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from ai.composer import fallback_text
from ai.grader import grade_for, profile_for
from ai.parser import preparse
from belief.project import project
from engine import actions as A
from engine.core import Date, canonical_json, lerp_table, state_hash
from engine.reduce import apply
from engine.relations import audit_oaths, deliver_protocol, evaluate_gift
from engine.state import GiftRecord, Letter, ProtocolRecord, Relation
from engine.tick import advance
from load import load_scenario
from session import play, replay, save

SEED = 8814402919


def _relation(esteem: int = 500) -> Relation:
    return Relation(
        other="other", place="seat", status_claim="servant",
        their_status_claim="servant", esteem=esteem, obligation=0,
        last_gift_from_us=0, last_gift_from_them=0,
        best_known_rival_gift=0, known_rival_gift_source=None)


def test_integer_table_and_every_gift_band_boundary():
    table = ((0, 700), (500, 1000), (1000, 1300))
    assert lerp_table(table, 333) == 899
    assert lerp_table(table, 750) == 1150
    assert lerp_table(table, -1) == 700
    assert lerp_table(table, 2000) == 1300

    cases = (
        (69, 690, -150, 0), (70, 700, -40, 0),
        (90, 900, 30, 22), (110, 1100, 70, 36),
        (150, 1500, 90, 50),
    )
    flat = ((0, 1000), (1000, 1000))
    for value, adequacy, delta, obligation in cases:
        relation, got, got_delta = evaluate_gift(
            _relation(), value, flat, {"servant": 100})
        assert (got, got_delta) == (adequacy, delta)
        assert relation.esteem == max(0, min(1000, 500 + delta))
        assert relation.obligation == obligation


def test_gift_arrival_gossip_insult_and_replay():
    world = load_scenario("ugarit", SEED)
    world, events = apply(world, A.SendGift("hatti_king", "copper", 1013))
    assert world.court.stores["copper"] == 36000 - 1013
    assert events[0].arrival_turn == 7
    keys = [(item.at, canonical_json(item.payload)) for item in world.schedule]
    assert keys == sorted(keys)
    for _ in range(7):
        world, _ = advance(world)
    gift = world.court.treasury_gifts_sent[-1]
    assert gift.adequacy == 900
    assert world.relations["hatti_king"].esteem == 550
    assert world.relations["hatti_king"].obligation == -1987
    for _ in range(6):
        world, _ = advance(world)
    alashiya = world.relations["alashiya_gov"]
    assert alashiya.best_known_rival_gift == 4052
    assert alashiya.known_rival_gift_source == "hatti_king"
    assert world.relations["hatti_king"].best_known_rival_gift == 5000

    insult = load_scenario("ugarit", SEED)
    insult, _ = apply(insult, A.SendGift("hatti_king", "oil", 1))
    for _ in range(7):
        insult, _ = advance(insult)
    assert insult.court.treasury_gifts_sent[-1].adequacy < 700
    assert any(letter.topic == "gift_insult"
               for letter in insult.letters_in_transit + insult.inbox)

    script = [[A.SendGift("hatti_king", "copper", 1013)]] + [[] for _ in range(14)]
    final, log, _ = play(SEED, "ugarit", script)
    path = "/tmp/m6_gift_replay.json"
    save(path, SEED, "ugarit", len(script), log, final)
    assert state_hash(replay(path)) == state_hash(final)
    data = json.loads(Path(path).read_text())
    data["version"] = 5
    Path(path).write_text(json.dumps(data))
    try:
        replay(path)
    except ValueError as ex:
        assert "unsupported save version" in str(ex)
    else:
        raise AssertionError("old save version was accepted")

    winter = load_scenario("ugarit", SEED)
    _, events = apply(
        winter, A.SendGift("alashiya_gov", "copper", 1))
    assert events[0].arrival_turn == 7


def _pending_world():
    world = load_scenario("ugarit", SEED)
    letter = Letter(
        id="P1", sender="byblos_king", recipient="ammurapi",
        topic="vassal_plea", facts=(), sent_turn=0,
        path=("byblos", "seat"), edge_index=1, legs_into_edge=0,
        at_node="seat", arrive_turn=0)
    return dataclasses.replace(
        world, correspondents=(), inbox=(letter,), oaths=())


def test_unanswered_decay_reading_reply_and_patron_notice():
    world = _pending_world()
    esteem = []
    for _ in range(7):
        world, _ = advance(world)
        esteem.append(world.relations["byblos_king"].esteem)
    relation = world.relations["byblos_king"]
    assert esteem == [480, 480, 450, 420, 390, 360, 330]
    assert relation.unanswered_letters_from_them == 7
    assert relation.seeking_patron and not relation.patron_notice_received
    notices = [item for item in world.schedule
               if isinstance(item.payload, A.PatronNoticeDue)]
    assert len(notices) == 1 and notices[0].at == 9
    for _ in range(2):
        world, events = advance(world)
    assert world.relations["byblos_king"].patron_notice_received
    assert any(isinstance(event, A.PatronSought) for event in events)

    world = _pending_world()
    for _ in range(2):
        world, _ = advance(world)
    world, _ = apply(world, A.ReadLetter("P1"))
    world, _ = advance(world)
    assert world.relations["byblos_king"].unanswered_letters_from_them == 3
    world, _ = apply(world, A.DictateReply("P1", "answer"))
    assert world.inbox[0].answered_turn == world.date.absolute
    world, _ = advance(world)
    assert world.relations["byblos_king"].unanswered_letters_from_them == 0


def _protocol_world(recipient: str, total: int, violations: tuple[str, ...]):
    world = load_scenario("ugarit", SEED)
    world = dataclasses.replace(
        world, date=Date(1, 10, 10),
        protocol_log=(ProtocolRecord(
            "PX", recipient, "hatti.servant_to_lord",
            total, violations),))
    letter = Letter(
        id="PX", sender="ammurapi", recipient=recipient, topic="reply",
        facts=(), sent_turn=1, path=("seat", "hattusa"),
        edge_index=1, legs_into_edge=0, at_node="hattusa",
        outgoing=True, protocol_profile="hatti.servant_to_lord",
        protocol_total=total, protocol_violations=violations)
    return world, letter


def test_protocol_penalties_wrong_gods_and_delivery_idempotence():
    cases = (
        ("kinship_overreach", 320),
        ("excuse_and_request", 430),
        ("missing_prostration", 400),
    )
    for violation, expected in cases:
        world, letter = _protocol_world("hatti_king", 800, (violation,))
        world, _ = deliver_protocol(world, letter)
        assert world.relations["hatti_king"].esteem == expected
        assert world.protocol_log[0].applied_turn == 10
        again, events = deliver_protocol(world, letter)
        assert again == world and events == []

    world, letter = _protocol_world(
        "hatti_king", 900, ("wrong_oath_gods",))
    before_court = world.court
    world, _ = deliver_protocol(world, letter)
    assert world.relations["hatti_king"].esteem == 520
    assert world.court == before_court
    assert world.relations["hatti_king"].reply_delay_until == 12
    again, _ = deliver_protocol(world, letter)
    assert again == world

    queued, letter = _protocol_world(
        "hatti_king", 900, ("wrong_oath_gods",))
    queued = dataclasses.replace(
        queued, date=Date(1, 7, 7), letters_in_transit=(letter,))
    queued, _events = advance(queued)
    assert queued.relations["hatti_king"].reply_delay_until == 10


def test_status_mismatch_only_bites_when_brotherhood_is_used():
    world = load_scenario("ugarit", SEED)
    inbound = Letter(
        id="B1", sender="byblos_king", recipient="ammurapi",
        topic="vassal_plea", facts=(), sent_turn=0,
        path=("byblos", "seat"), edge_index=1, legs_into_edge=0,
        at_node="seat", arrive_turn=0)
    world = dataclasses.replace(world, inbox=(inbound,))
    profile = profile_for("byblos_king")
    text = fallback_text("byblos_king", "reassure", profile, 1, 1)
    text += "\nMy brother, let friendship stand."
    score = grade_for(text, profile, recipient="byblos_king")
    action = A.DictateReply(
        "B1", "reassure", text, profile, score.total, score.violations)
    world, _ = apply(world, action)
    record = world.protocol_log[-1]
    assert record.violations == ("kinship_overreach",)
    outgoing = dataclasses.replace(
        inbound, id=record.letter_id, sender="ammurapi",
        recipient="byblos_king", outgoing=True,
        protocol_profile=profile, protocol_total=score.total,
        protocol_violations=record.violations)
    world, _ = deliver_protocol(world, outgoing)
    assert world.relations["byblos_king"].esteem == 280
    assert world.relations["byblos_king"].status_mismatch_known


def test_oath_deadline_records_breach_without_causing_random_physics():
    world = load_scenario("ugarit", SEED)
    world = dataclasses.replace(world, date=Date(1, 24, 24))
    audited, events = audit_oaths(world)
    assert audited == world
    assert events == [A.OathViolated("oath_hatti_grain", "provide_goods")]

    fulfilled = load_scenario("ugarit", SEED)
    record = GiftRecord(
        "Gx", "ammurapi", "hatti_king", "grain", 48000, 48000,
        1, arrive_turn=24, adequacy=1000)
    fulfilled = dataclasses.replace(
        fulfilled, date=Date(1, 24, 24),
        court=dataclasses.replace(
            fulfilled.court, treasury_gifts_sent=(record,)))
    audited, events = audit_oaths(fulfilled)
    assert audited == fulfilled
    assert events == []


def test_removed_divine_liability_and_parser_knows_gifts():
    world = load_scenario("ugarit", SEED)
    assert "liability" not in {
        field.name for field in dataclasses.fields(type(world.court))}
    belief = project(world)
    assert "liability" not in json.dumps(belief)
    assert belief["oaths"][0]["id"] == "oath_hatti_grain"
    byblos = next(r for r in belief["relations"]
                  if r["other"] == "byblos_king")
    assert byblos["their_status_claim"] == "uncertain"
    parsed = preparse("gift hatti_king copper 10", belief)
    assert parsed.actions == (A.SendGift("hatti_king", "copper", 10),)
