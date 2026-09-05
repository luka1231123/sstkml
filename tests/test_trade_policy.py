"""Court trade orders return cargo and conserve the goods in the Book."""
from __future__ import annotations

import dataclasses

import pytest

from belief.project import project
from engine import actions as A
from engine import seat, trade_policy, works
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
import palette
from tui import trade
from tui.grid import plain_text


SEED = 8814402919


def _total(world, good: str) -> int:
    return sum(lot.quantity for lot in world.kernel.book.lots.values()
               if lot.good == good)


def test_financing_copper_buys_counted_grain_instead_of_giving_money_away() -> None:
    world = load_campaign("seat", SEED)
    before = seat.held(world)
    grain_total = _total(world, "grain")
    copper_total = _total(world, "copper")

    world, events = apply(world, A.FinanceTrade("copper", 100))

    assert seat.held(world)["copper"] == before["copper"] - 100
    assert seat.held(world)["grain"] == before["grain"] + 2500
    assert events == [A.TradeFinanced("copper", 100, "grain", 2500)]
    assert _total(world, "grain") == grain_total
    assert _total(world, "copper") == copper_total


def test_financing_refuses_before_spending_when_the_order_names_no_copper() -> None:
    world = load_campaign("seat", SEED)
    before = world.kernel.book

    with pytest.raises(ValueError, match="financed with copper"):
        apply(world, A.FinanceTrade("grain", 100))

    assert world.kernel.book == before


def test_finance_palette_defaults_to_copper_without_extra_typing() -> None:
    belief = {"stores": {"copper": 100}, "relations": [], "stack": [],
              "groups": [], "institutions": [], "seat": "seat"}
    result = palette.parse("finance 100", belief)

    assert result.ok
    assert palette.build(result) == A.FinanceTrade("copper", 100)


def test_trade_screen_names_the_return_and_requisition_cost() -> None:
    belief = project(load_campaign("seat", SEED))
    text = plain_text(trade.compose(belief, width=66, height=22))

    assert "buys up to" in text and "counted grain" in text
    assert "tin price" in text
    assert "requisition: take cargo now" in text
    assert "unrest rises with value" in text
    assert "buy grain · 1 talent" in text

    cargo = plain_text(trade.compose(
        belief, width=66, height=22, view="cargo"))
    assert "grain · craft" in cargo
    assert "grain · field labour" in cargo
    assert "finance" not in cargo

    routes = plain_text(trade.compose(
        belief, width=66, height=22, view="routes"))
    assert "cap 6,000" in routes and "loss 75/1000" in routes
    assert "close route" not in routes

    movements = plain_text(trade.compose(
        belief, width=66, height=22, view="movements"))
    assert "none reported" in movements
    assert "choose" not in movements and "Enter" not in movements
    assert "escort" not in movements and "close route" not in movements


def test_trade_finances_one_talent_without_opening_a_typed_command() -> None:
    game = _game(load_campaign("seat", SEED))
    game.trade_view = "exchange"
    game.trade_pick = ""

    game.on_trade_key(_Key("f"))

    action, _cost, window = game.pending_action
    assert action == A.FinanceTrade("copper", 3000)
    assert window == "trade"
    assert "buy up to 75,000 grain" in str(game.notices["trade"])
    assert "Enter confirms" in str(game.notices["trade"])
    assert not game.log


def test_requisition_takes_the_visible_cargo_and_charges_unrest() -> None:
    world = load_campaign("seat", SEED)
    grain = seat.held(world)["grain"]
    unrest = world.court.unrest

    world, events = apply(world, A.RequisitionTrade("grain", 10_000))

    assert seat.held(world)["grain"] == grain + 10_000
    assert world.court.unrest > unrest
    assert events[0] == A.TradeRequisitioned("grain", 10_000)
    assert events[1] == A.UnrestChanged(
        world.court.unrest - unrest, "the requisitioned cargo")


def _trade_world():
    world = load_campaign("seat", SEED)
    for _ in range(8):
        world, _ = advance(world)
    return world


class _Key:
    def __init__(self, char: str = "", keysym: str = "") -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = ""
        self.state = 0


def _game(world):
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.world = world
    game.hours = project(world)["attention"]
    game.log = []
    game.client = None
    game.repaint = lambda: None
    game.trade_view = "cargo"
    game.trade_scroll = 0
    return game


def test_requisition_uses_the_selected_lot_without_retyping_it() -> None:
    world = _trade_world()
    cargo = [item for item in project(world)["trade"]["cargo"]
             if item["good"] == "grain"]
    first, selected = cargo[:2]
    assert first["owner"] != selected["owner"]
    before_first = world.kernel.book.lots[first["id"]]
    before_grain = seat.held(world)["grain"]
    expected_unrest = trade_policy.requisition_unrest(
        world, selected["good"], selected["available"])
    game = _game(world)
    game.trade_pick = selected["id"]

    game.on_trade_key(_Key("r"))

    action, _cost, _window = game.pending_action
    assert action == A.RequisitionTrade(
        selected["good"], selected["available"], selected["id"])
    preview = str(game.notices["trade"])
    assert selected["owner_name"] in preview
    assert f"unrest +{expected_unrest}" in preview
    assert "Enter confirms" in preview
    assert not game.log

    game.confirm_pending()
    assert game.log[-1]["action"]["lot_id"] == selected["id"]
    assert game.world.kernel.book.lots[first["id"]] == before_first
    assert seat.held(game.world)["grain"] == before_grain + selected["available"]
    crown = game.world.kernel.controller("settlement:seat")
    assert game.world.kernel.book.lots[selected["id"]].owner == crown


def test_selected_lot_requisition_takes_only_its_free_quantity() -> None:
    world = _trade_world()
    selected = [item for item in project(world)["trade"]["cargo"]
                if item["good"] == "grain"][1]
    book = world.kernel.book.reserve(selected["id"], 100, "letter:test")
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    item = next(c for c in project(world)["trade"]["cargo"]
                if c["id"] == selected["id"])
    before = seat.held(world)["grain"]

    changed, _ = apply(world, A.RequisitionTrade(
        item["good"], item["available"], item["id"]))

    assert seat.held(changed)["grain"] == before + item["available"]
    left = changed.kernel.book.lots[item["id"]]
    assert left.quantity == left.reserved == 100


def test_zero_free_cargo_disables_and_refuses_requisition() -> None:
    world = _trade_world()
    selected = project(world)["trade"]["cargo"][0]
    book = world.kernel.book.reserve(
        selected["id"], selected["available"], "letter:test")
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    belief = project(world)
    screen = trade.compose(
        belief, width=66, height=22, view="cargo", selected=selected["id"])
    controls = [hit for hit in screen.hits
                if hit.command == "r"]
    assert controls and not any(hit.enabled for hit in controls)
    assert "0 available" in plain_text(screen)

    game = _game(world)
    game.trade_pick = selected["id"]
    game.on_trade_key(_Key("r"))
    assert game.notices["trade"].kind == "refusal"
    assert not game.log and getattr(game, "pending_action", None) is None


@pytest.mark.parametrize("lot_id, good", [
    ("settlement:seat/999/lot/999", "grain"),
    (None, "wrong-good"),
])
def test_stale_or_wrong_selected_lot_is_atomic(lot_id, good) -> None:
    world = _trade_world()
    if lot_id is None:
        lot = next(item for item in project(world)["trade"]["cargo"]
                   if item["good"] != good)
        lot_id = lot["id"]
    before = (world.kernel.book, world.court.unrest)
    with pytest.raises(ValueError, match="no longer at the quay"):
        apply(world, A.RequisitionTrade(good, 1, lot_id))
    assert (world.kernel.book, world.court.unrest) == before


def test_selected_lot_that_is_now_crown_owned_is_atomic() -> None:
    world = _trade_world()
    selected = project(world)["trade"]["cargo"][0]
    seat_id = f"settlement:{world.chosen_alu}"
    crown = world.kernel.controller(seat_id)
    book = world.kernel.book.give(
        selected["id"], selected["available"], crown, "seized", crown)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    before = (world.kernel.book, world.court.unrest)

    with pytest.raises(ValueError, match="no longer at the quay"):
        apply(world, A.RequisitionTrade(
            selected["good"], selected["available"], selected["id"]))

    assert (world.kernel.book, world.court.unrest) == before


def test_selected_lot_that_has_left_the_quay_is_atomic() -> None:
    world = _trade_world()
    selected = project(world)["trade"]["cargo"][0]
    book = world.kernel.book.relocate(
        selected["id"], "settlement:ma_hadu", "carried")
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    before = (world.kernel.book, world.court.unrest)

    with pytest.raises(ValueError, match="no longer at the quay"):
        apply(world, A.RequisitionTrade(
            selected["good"], selected["available"], selected["id"]))

    assert (world.kernel.book, world.court.unrest) == before


def test_selected_lot_request_above_its_free_quantity_is_atomic() -> None:
    world = _trade_world()
    selected = project(world)["trade"]["cargo"][0]
    book = world.kernel.book.reserve(selected["id"], 1, "letter:test")
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    available = world.kernel.book.lots[selected["id"]].free
    before = (world.kernel.book, world.court.unrest)

    with pytest.raises(ValueError, match=rf"only {available} .* is available"):
        apply(world, A.RequisitionTrade(
            selected["good"], available + 1, selected["id"]))

    assert (world.kernel.book, world.court.unrest) == before


def test_remote_works_do_not_boost_the_capital_field_or_routes() -> None:
    opening = load_campaign("seat", SEED)
    remote = opening
    for kind in ("canal", "harbour", "road"):
        remote, _ = works.begin_build(remote, A.BeginBuild(kind, "alashiya"))
        work = remote.court.projects[f"work{remote.court.project_seq}"]
        remote, _ = works._finish(remote, work)

    baseline, _ = advance(opening)
    remote, _ = advance(remote)

    assert remote.kernel.site_extent_bonus == baseline.kernel.site_extent_bonus
    assert remote.kernel.route_capacity_bonus == \
        baseline.kernel.route_capacity_bonus
