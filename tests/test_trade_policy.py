"""Court trade orders return cargo and conserve the goods in the Book."""
from __future__ import annotations

import pytest

from belief.project import project
from engine import actions as A
from engine import seat, works
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
    text = plain_text(trade.compose(
        project(load_campaign("seat", SEED)), width=66, height=22))

    assert "buys up to" in text and "counted grain" in text
    assert "requisition: take cargo now" in text
    assert "unrest rises with value" in text


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
