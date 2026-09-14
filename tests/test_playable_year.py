"""The first-year decisions cross the controller, records and replay boundary."""

import tempfile
from pathlib import Path

from belief import harvest
from belief.project import project
from belief.rations import repayment
from engine import actions as A, seat
from engine.core import state_hash
from engine.tick import advance
from session import save, load_session
from tests.test_ledgers import _game, _Key
from tui import aftermath, document, relief, trade, render
from tui.grid import plain_text


def test_arrears_draft_cancels_then_pays_once_and_replays():
    game = _game(turns=1)
    group = "palace_dependents"
    game.do(A.Allocate(group, 0), window="roll")
    game.world, _ = advance(game.world)
    game.hours = 8
    game.ledger_state["roll"]["pick"] = group
    before = game.world
    game.on_roll_key(_Key("r"))
    assert game.world is before
    assert "PAYMENT DRAFT" in plain_text(game.compose_ledger("roll", game.belief, 82, 28, ""))
    game.on_roll_key(_Key(keysym="Escape"))
    assert game.world is before
    game.on_roll_key(_Key("r"))
    amount = game.ledger_state["roll"]["arrears_draft"]
    assert amount > 0
    grain = seat.held(game.world)["grain"]
    game.on_roll_key(_Key(keysym="Return"))
    assert seat.held(game.world)["grain"] == grain - amount
    assert game.log[-1]["action"]["_t"] == "PayArrears"
    assert game.log[-1]["receipt"]
    report = ["A saved court report."]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "year.json"
        save(path, game.seed, "seat", game.world.date.absolute, game.log,
             game.world, hours_left=game.hours, court_report=report)
        loaded, data = load_session(path)
        assert state_hash(loaded) == state_hash(game.world)
        assert data["court_report"] == report


def test_repayment_preview_excludes_reserved_grain():
    b = {"stores": {"grain": 100}, "ration_reserved": 80,
         "groups": [{"id": "g", "size": 1, "entitlement": 10,
                     "allocated": 10, "arrears_qa": 100}]}
    assert repayment(b, "g", 21)["refusal"] == "only 20 qa unreserved"
    p = repayment(b, "g", 20)
    assert not p["refusal"] and p["remaining_grain"] == 0
    assert p["queue"]["groups"][0]["next_short"] == 10


def test_harvest_review_counts_only_future_work_and_does_not_spend_on_cancel():
    game = _game(turns=7)
    game.ledger_state["roll"]["pick"] = "palace_dependents"
    before = game.world
    game.on_roll_key(_Key("h"))
    screen = plain_text(game.compose_ledger("roll", game.belief, 82, 28, ""))
    assert "Deadline shortfall" in screen and "ordinary duties" in screen
    assert game.world is before and not game.log
    game.cancel_pending()
    assert game.world is before
    game.on_roll_key(_Key("h"))
    game.confirm_pending()
    assert game.log[-1]["receipt"]
    closing = next(s["to"] for s in game.belief["calendar"]["spans"] if s["name"] == "harvest")
    while game.world.date.fortnight < closing:
        game.world, _ = advance(game.world)
    assert harvest.plan(game.belief)["remaining"] == 0
    assert harvest.plan(game.belief, "weavers")["refusal"]


def test_relief_draft_dispatches_exact_request_and_preserves_an_existing_draft():
    game = _game(turns=7)
    game.desk = None
    game.desk_drafts = {}
    game.trade_view = "relief"
    game.trade_pick = relief.courts(game.belief)[0]["id"]
    game.on_trade_key(_Key(keysym="Return"))
    assert not game.log
    request = game._desk_commitments()
    assert len(request) == 1 and request[0].kind == "request_good"
    assert request[0].good == "grain" and request[0].quantity == relief.ration(game.belief)
    original = game.desk["matter"]
    game.relief_quantity = 1
    game.on_trade_key(_Key(keysym="Return"))
    assert game.desk["matter"] == original
    game.on_desk_key(_Key("s"))
    assert game.pending_action is not None
    game.confirm_pending()
    assert game.log[-1]["action"]["_t"] == "DispatchLetter"
    assert game.belief["outbox"][0]["terms"][0]["quantity"] == request[0].quantity
    request_id = game.belief["outbox"][0]["id"]
    arrived = []
    for _ in range(8):
        game.world, events = advance(game.world)
        arrived += [e for e in events if isinstance(e, A.CargoLanded)]
    sent = next(item for item in game.belief["outbox"] if item["id"] == request_id)
    assert sent["answered"] and not sent["decision"], "unread answer must not leak its decision"
    assert arrived and sum(e.quantity for e in arrived) == request[0].quantity
    assert "Cargo received" in " ".join(render.events_lines(arrived, game.world.court))
    assert any(r.source_letter == sent["reply_id"] and r.status == "delivered"
               for r in game.world.letter_reservations)


def test_aftermath_has_no_unread_reply_decision_and_last_line_is_reachable():
    before = project(_game(turns=7).world)
    after = {**before, "turn": 8,
             "outbox": [{"id": "L1", "status": "answer come — seal unbroken",
                         "expected_reply_turn": 8}]}
    lines = aftermath.lines(before, after) + ["Final report line."]
    assert "seal unbroken" in " ".join(lines)
    assert "accept" not in " ".join(lines)
    rows = document.fortnight_rows(lines, 66)
    screen = document.fortnight(after, lines, 66, 18, scroll=len(rows))
    assert "Final report line." in plain_text(screen)


def test_relief_minimum_screen_keeps_cost_and_commit_controls_visible():
    b = _game(turns=7).belief
    screen = plain_text(trade.compose(b, 66, 22, view="relief", hours=8))
    assert "sealing:" in screen and "draft grain request" in screen
    assert "no payment is attached" in screen


def test_conflicting_attached_and_written_terms_cannot_be_sealed():
    game = _game(turns=7)
    game.desk = None
    game.desk_drafts = {}
    game.trade_view = "relief"
    game.on_trade_key(_Key(keysym="Return"))
    game.desk["terms"] = (A.LetterTerm("request_good", good="grain", quantity=1),)
    game.on_desk_key(_Key("s"))
    assert not game.log and getattr(game, "pending_action", None) is None
    assert "conflicts" in str(game.notices["stack"])
