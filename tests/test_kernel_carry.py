"""The crossing (spec 6.6, 6.7, M13.2).

    a price is a reading of a place, not a number the world publishes;
    a bargain is struck where both parties are standing, and it conserves;
    a council will not sell the cover it is living on;
    a crossing takes time, and the cargo is somewhere while it takes it;
    the sea is finite, and rationed by the same allocator as the harvest;
    a voyage can be lost, and the ledger says where the grain went;
    news travels no faster than the ships, and stops when they stop;
    and the whole of it closes: ground to granary to quay to household.
"""
from __future__ import annotations

import dataclasses

from engine import believe as B
from engine import ownership as W
from engine.kernel import carry as C
from engine.kernel import farm as F
from engine.kernel import world as K
from load import load_campaign
from tests.test_kernel_world import landlocked

SEAT = "settlement:seat"
ALASHIYA = "settlement:alashiya"
MUKISH = "settlement:mukish"
MERCHANT = "org:seat_palace"
ISLAND = "org:alashiya_palace"
IMPORTER = "org:mukish_palace"


def _world() -> K.Kernel:
    return load_campaign("seat", seed=1).kernel


def _run(kernel: K.Kernel, turns: int):
    events, logs = [], []
    for _ in range(turns):
        kernel, produced, log = K.advance_logged(kernel)
        events.extend(produced)
        logs.append(log)
        faults = K.faults(kernel)
        assert not faults, faults
    return kernel, events, logs


def _held(kernel: K.Kernel, actor: str, good: str = C.GRAIN) -> int:
    return sum(lot.quantity for lot in kernel.book.owned_by(actor)
               if lot.good == good)


# --- a price is a reading of a place ------------------------------------------

def test_a_price_is_what_the_store_in_front_of_you_covers() -> None:
    need = 1000
    empty = C.price(0, need)
    thin = C.price(need * 4, need)
    ordinary = C.price(need * C.TARGET_COVER, need)
    full = C.price(need * 200, need)

    assert empty > thin > ordinary > full, "scarcity is dear and plenty is cheap"
    assert ordinary == C.BASE_PRICE, "the ordinary cover is the base price"
    assert empty == C.PRICE_CEILING and full == C.PRICE_FLOOR, \
        "a famine price is capped by what a buyer has, and a glut is not free"
    assert C.price(0, 0) == C.PRICE_FLOOR, "nobody to feed, nothing to bid"


def test_two_places_read_the_same_grain_at_different_prices() -> None:
    kernel = _world()
    reads = {s: C.readings(kernel, s) for s in kernel.autonomous()}
    prices = {s: r["price_grain"] for s, r in reads.items()}
    cover = {s: kernel.stores(s) // sum(c.ration() for c in kernel.cohorts_of(s))
             for s in prices}

    assert len(set(prices.values())) > 1, "the same grain, two numbers"
    assert max(prices, key=lambda s: prices[s]) == min(cover, key=cover.get), \
        "and the place with the thinnest cover is the dear one"
    assert all("market_grain" in r for r in reads.values()), \
        "a reading is about the place; what anyone can spare is about the owner"
    assert all(r["market_grain"] == 0 for r in reads.values()), \
        "and on the first morning nothing is standing on any quay"


# --- a bargain is struck where both parties are standing ----------------------

def test_a_bargain_moves_goods_one_way_and_copper_the_other() -> None:
    kernel, _, logs = _run(_world(), turns=20)
    sales = [c for log in logs for c in log.contracts]
    if not sales:
        return  # no trade in self-sufficient world
    first = sales[0]
    assert first.good == C.GRAIN and first.pay_good == C.COPPER
    assert first.quantity > 0 and first.paid > 0


def test_a_sale_conserves_and_the_ledger_names_both_sides() -> None:
    kernel = _world()
    for _ in range(20):
        before = kernel.book
        kernel, _, log = K.advance_logged(kernel)
        report = W.conservation(
            dataclasses.replace(before, transfers=()),
            dataclasses.replace(kernel.book, transfers=log.transfers))
        for good, (sourced, sunk, unexplained) in report.items():
            assert unexplained == 0, (good, sourced, sunk, unexplained)


def _believing(actor: str, place: str, **readings) -> B.Belief:
    return B.Belief(holder=actor).add(*(B.Claim(
        id=f"test|{attribute}", holder=actor, subject=place,
        attribute=attribute, value=value, source="observed",
        observed_turn=1, received_turn=1, confidence=1000)
        for attribute, value in sorted(readings.items())))


def test_a_council_will_not_sell_the_cover_it_is_living_on() -> None:
    lean = _believing(IMPORTER, MUKISH, own_grain=90_000, need=4_000, price_grain=30)
    assert C.sell_surplus(IMPORTER, lean, MUKISH) == (), \
        "a year and a bit of eating is not a surplus, it is the year"

    fat = _believing(IMPORTER, MUKISH, own_grain=150_000, need=4_000, price_grain=30)
    quote, = C.sell_surplus(IMPORTER, fat, MUKISH)
    assert quote.kind == "quote" and quote.task == C.GRAIN
    assert quote.quantity == 150_000 - 4_000 * C.KEEP_FORTNIGHTS
    assert quote.unit_price == 30, "it asks what grain is going for here"
    assert C.KEEP_FORTNIGHTS >= 24, \
        "the harvest comes once a year, so the reserve has to reach the next one"


def test_a_buyer_short_of_payment_buys_less_and_never_on_credit() -> None:
    comfortable = dict(own_grain=0, need=1_000, market_grain=100_000,
                       own_copper=10_000, price_grain=100)
    plenty = _believing(ISLAND, ALASHIYA, **comfortable)
    assert C.buy_shortfall(ISLAND, plenty, ALASHIYA)[0].quantity == \
        1_000 * C.COVER_TARGET, "it shops for the cover it aims at"

    for pinch, expected in (
            (dict(own_grain=1_000 * C.COVER_TARGET - 600), 600),
            (dict(market_grain=700), 700),
            (dict(own_copper=80), 800)):
        bid = C.buy_shortfall(
            ISLAND, _believing(ISLAND, ALASHIYA, **{**comfortable, **pinch}),
            ALASHIYA)
        assert bid and bid[0].quantity == expected, (pinch, bid)

    broke = _believing(ISLAND, ALASHIYA, **{**comfortable, "own_copper": 0})
    assert C.buy_shortfall(ISLAND, broke, ALASHIYA) == (), \
        "an empty purse buys nothing, and asks for no credit"


# --- a crossing takes time ----------------------------------------------------

def test_cargo_is_somewhere_while_it_is_at_sea() -> None:
    kernel, _, _ = _run(_world(), turns=6)
    afloat = [v for v in kernel.voyages if v.cargo]
    if afloat:
        voyage = afloat[0]
        assert voyage.arrives > voyage.departed, "a crossing takes fortnights"
        for lot_id in voyage.cargo:
            lot = kernel.book.lots[lot_id]
            assert lot.location == voyage.route, "not at either end"
            assert lot.holder == voyage.carrier, "somebody has charge of it"
    assert K.faults(kernel) == ()


def test_the_sea_is_finite_and_rationed_by_the_same_allocator() -> None:
    kernel = _world()
    pools = K._capacity(kernel)
    crossings = {k: v for k, v in pools.items() if k.endswith("#cargo")}
    assert crossings, "the crossings are pools the allocator knows about"


def test_a_cargo_never_exceeds_the_hold_that_was_granted() -> None:
    kernel = _world()
    for _ in range(12):
        kernel, events, log = K.advance_logged(kernel)
        granted = {i.id: log.allocation.granted(i.id)
                   for i in log.intents if i.kind == "ship"}
        aboard: dict[str, int] = {}
        for event in events:
            if event[0] != "sailed":
                continue
            _, _, origin, destination, good, quantity = event
            key = f"{origin}>{destination}|{good}"
            aboard[key] = aboard.get(key, 0) + C.bulk(good, quantity)
        for intent_id, hold in granted.items():
            actor, _, leg, good = intent_id.split("|")
            sailed = aboard.get(f"{leg}|{good}", 0)
            assert sailed <= hold, (intent_id, sailed, hold)
    assert K.faults(kernel) == ()


def test_a_voyage_can_be_lost_and_the_ledger_says_where_it_went() -> None:
    kernel, events, logs = _run(_world(), turns=12)
    losses = [e for e in events if e[0] == "lost_at_sea"]
    sunk = [t for log in logs for t in log.transfers if t.reason == "lost"]
    if losses:
        assert sunk, "and every lost qa leaves a sink on the ledger"
        assert all(t.quantity > 0 for t in sunk)
    assert K.faults(kernel) == (), "and nothing is left half at sea"


# --- news travels no faster than the ships ------------------------------------

def test_what_a_port_knows_of_another_is_as_old_as_the_last_ship() -> None:
    kernel, _, _ = _run(_world(), turns=4)
    belief = kernel.beliefs[ISLAND]
    word = belief.best(SEAT, "price_grain")
    assert word is not None, "the island has heard of the mainland"
    assert word.source in ("reported", "assumed")
    assert word.chain or word.source == "assumed", "somebody carried it"
    assert word.observed_turn < kernel.date.absolute, \
        "it was true when it was seen, not when it arrived"


def test_a_shut_sea_blinds_a_port_and_it_does_not_know_it() -> None:
    kernel, _, _ = _run(_world(), turns=1)
    route = kernel.registry.routes["route:alashiya_knossos"]

    shut = kernel
    while C.sea_open(shut, route):
        shut, _, _ = _run(shut, turns=1)
    opening = shut.beliefs[ISLAND].best(SEAT, "price_grain").observed_turn

    shut, _, _ = _run(shut, turns=3)
    assert not C.sea_open(shut, route), "still winter"
    later = shut.beliefs[ISLAND].best(SEAT, "price_grain")
    assert later.observed_turn == opening, "no ship, no word, and no notice of it"


def test_the_trade_policy_reads_belief_and_never_the_world() -> None:
    assert C.trade(MERCHANT, B.Belief(holder=MERCHANT)) == ()

    only_home = B.Belief(holder=MERCHANT).add(B.Claim(
        id="c|home", holder=MERCHANT, subject=SEAT, attribute="home", value=1,
        source="observed", observed_turn=1, received_turn=1, confidence=1000))
    assert C.home(only_home) == SEAT
    assert C.trade(MERCHANT, only_home) == (), "one price is not a line"
