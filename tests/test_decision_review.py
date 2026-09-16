"""Costs, cancellation and readable receipts across the player boundary."""
from types import SimpleNamespace
import json

import pytest

from belief.project import project
from belief import muster, trade
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import save, load_session
from tui import counsel, desktop, dialog, ledgers, orders, aftermath, style
from tui.grid import plain_text, Surface


def campaign():
    world = load_campaign("seat", 8814402919)
    for _ in range(6):
        world, _ = advance(world)
    return world


def controller(world):
    from play_gui import Game
    game = Game.__new__(Game)
    game.world, game.seed, game.log = world, 8814402919, []
    game.hours, game.client = 10, None
    game.repaint = lambda: None
    return game


@pytest.mark.parametrize("size", [(60, 20), (72, 26)])
def test_muster_controls_and_every_preview_line_remain_reachable(size):
    b = project(campaign())
    formation = b["troops"]["formations"][0]
    texts = []
    for page in range(20):
        text = plain_text(ledgers.muster(b, formation["id"], *size,
                          task="watch", place="seat", hours=10, detail_page=page))
        assert "[t] task" in text and "[l] place" in text
        assert "review assignment" in text
        texts.append(text)
    visible = " ".join(" ".join(texts).replace("║", " ").split())
    assert "90 → 45" in visible
    assert "Muster roll · turn 6" in visible
    assert "no new levy or immediate goods payment" in visible


def test_assignment_cancel_commit_and_replay_keep_the_receipt(tmp_path):
    game = controller(campaign())
    before = game.world
    formation = game.belief["troops"]["formations"][0]
    action = A.AssignTroops(formation["id"], "watch", "seat")
    game.do(action, window="muster")
    assert game.world is before and game.hours == 10 and not game.log
    game.cancel_pending()
    assert game.world is before and game.hours == 10 and not game.log
    game.do(action, window="muster")
    game.confirm_pending()
    assert game.hours == 9 and len(game.log) == 1
    assert "assigned to watch" in game.log[0]["receipt"][0]
    path = tmp_path / "save.json"
    save(path, game.seed, "seat", 6, game.log, game.world)
    restored, data = load_session(path)
    assert restored == game.world
    assert data["log"] == game.log
    later, _ = advance(game.world)
    report = aftermath.lines(game.belief, project(later), game.log)
    assert any("New muster roll" in line for line in report)
    assert not any("New muster roll" in line for line in
                   aftermath.follow_through(project(later), project(later), game.log))


@pytest.mark.parametrize("purse", [1, 100, 3000])
def test_quay_estimate_matches_actual_rounded_payment(purse):
    world = campaign()
    estimate = trade.purchase(project(world), purse)
    _, events = apply(world, A.FinanceTrade("copper", purse))
    result = next(e for e in events if isinstance(e, A.TradeFinanced))
    assert estimate["grain"] == result.received_quantity
    assert estimate["paid"] == result.quantity
    assert result.quantity <= purse


def test_local_purchase_receipt_survives_orders_pagination():
    game = controller(campaign())
    game.do(A.FinanceTrade("copper", 3000), window="trade")
    game.confirm_pending()
    assert "Received 50,000 qa" in game.log[0]["receipt"][0]
    text = " ".join(plain_text(orders.compose(game.belief, game.log, 6,
                    view="all", width=66, height=22, detail_page=page))
                    for page in range(20))
    assert "Received 50,000 qa" in text
    assert "copper shekels" in text


def test_long_reviews_and_old_conversation_are_readable_at_minimum_size():
    said = [("scribe", f"record{n}: " + "The counted goods are here. " * 8)
            for n in range(12)]
    width, height = desktop.minimum_size("counsel")
    pages = counsel.page_count(said, width, height)
    text = " ".join(plain_text(counsel.compose({}, said, 8, width=width,
                    height=height, page=page)) for page in range(pages))
    assert all(f"record{n}:" in text for n in range(12))
    pending = ["First order. " * 20, "Second order. " * 20 + " FINAL_RECEIPT"]
    pages = counsel.page_count([], width, height, pending)
    text = " ".join(plain_text(counsel.compose({}, [], 8, width=width,
                    height=height, pending=pending, pending_cost=2, page=page))
                    for page in range(pages))
    assert "FINAL_RECEIPT" in text and "2h" in text
    text = " ".join(plain_text(dialog.compose("REVIEW", pending, width=48,
                    height=12, page=page)) for page in range(20))
    assert "FINAL_RECEIPT" in text


def test_note_captures_origin_instead_of_the_note_window(tmp_path):
    game = controller(campaign())
    game.save_path = tmp_path / "autosave.json"
    active = ["muster"]
    game.active_window = lambda: active[0]
    surface = Surface(40, 5)
    surface.text(1, 1, "The order I was reviewing")
    game.compose = lambda key: surface.interactive()
    def window(*args, **kwargs):
        active[0] = "note"
        return SimpleNamespace(focus=lambda: None)
    game.app = SimpleNamespace(window=window, close=lambda key: None, live=lambda: [active[0]])
    game.playtest_note()
    game.note_typed = "I expected fewer defenders."
    game.save_note()
    note = json.loads((tmp_path / "notes.jsonl").read_text())
    assert note["window"] == "muster"
    assert "The order I was reviewing" in note["screen"]
    assert note["turn"] == 6


def test_multiline_order_can_also_be_shown_in_a_one_line_notice():
    surface = Surface(80, 4)
    style.notice(surface, 2, 1, 76, style.Notice("Order: watch\nCost: 1h", "preview"))
    assert "Order: watch Cost: 1h" in plain_text(surface.freeze())


def test_notes_keep_colons_and_question_marks_in_the_editor():
    game = controller(campaign())
    game.app = SimpleNamespace(live=lambda: ["note", "muster"])
    def unexpected():
        pytest.fail("Typing punctuation opened another window")
    game.open_palette = game.open_help = unexpected
    bindings = game._desktop_bindings()
    assert bindings["<colon>"]() is None
    assert bindings["<question>"]() is None


def test_hall_opens_order_receipts_without_spending_attention():
    game = controller(campaign())
    game.home_view = "hall"
    opened = []
    game.open_orders = lambda: opened.append("orders")
    game.on_audience_key(SimpleNamespace(keysym="o", char="o", command=""))
    assert opened == ["orders"] and game.hours == 10 and not game.log
