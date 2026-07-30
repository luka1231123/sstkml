"""The crossing (spec 6.6, 6.7, M13.2).

The claims, in the order the chain makes them:

    a price is a reading of a place, not a number the world publishes;
    a bargain is struck where both parties are standing, and it conserves;
    a council will not sell the cover it is living on;
    a crossing takes time, and the cargo is somewhere while it takes it;
    the sea is finite, and rationed by the same allocator as the harvest;
    a voyage can be lost, and the ledger says where the grain went;
    news travels no faster than the ships, and stops when they stop;
    and the whole of it closes: ground to granary to quay to household.

The last is the milestone's exit gate. Numbers below are calibration and will
move; each test states which of the claims it is holding.
"""
from __future__ import annotations

import dataclasses

from engine import believe as B
from engine import ownership as W
from engine.kernel import carry as C
from engine.kernel import farm as F
from engine.kernel import world as K
from load_kernel import load_kernel
from tests.test_kernel_world import landlocked

MAHADU = "settlement:mahadu"
ALASHIYA = "settlement:alashiya_port"
ARI = "settlement:ari"
MERCHANT = "org:mahadu_merchant"
ISLAND = "org:alashiya_council"
INLAND = "org:ari_council"


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
    """One reading, and its shape is the claim: scarce is dear, without bound.

    Not a clearing price and not an exchange rate. Two places can price the same
    grain differently at the same moment and neither is wrong, because neither
    is looking at the other -- which is the whole of spec 6.6's "no global
    exchange" reduced to an arithmetic property.
    """
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
    """At one moment, with nothing between them but a crossing."""
    kernel = load_kernel()
    reads = {s: C.readings(kernel, s) for s in kernel.autonomous()}
    prices = {s: r["price_grain"] for s, r in reads.items()}
    cover = {s: kernel.stores(s) // sum(c.ration() for c in kernel.cohorts_of(s))
             for s in prices}

    assert len(set(prices.values())) > 1, "the same grain, two numbers"
    assert max(prices, key=lambda s: prices[s]) == min(cover, key=cover.get), \
        "and the place with the thinnest cover is the dear one"
    assert set(reads[MAHADU]) == {"price_grain", "market_grain"}, \
        "a reading is about the place; what anyone can spare is about the owner"
    assert all(r["market_grain"] == 0 for r in reads.values()), \
        "and on the first morning nothing is standing on any quay"


# --- a bargain is struck where both parties are standing ----------------------

def test_a_bargain_moves_goods_one_way_and_copper_the_other() -> None:
    """And it conserves: a sale sources nothing and sinks nothing."""
    kernel, _, logs = _run(load_kernel(), turns=20)
    sales = [c for log in logs for c in log.contracts]
    assert sales, "somebody traded"

    first = sales[0]
    assert first.good == C.GRAIN and first.pay_good == C.COPPER
    assert first.quantity > 0 and first.paid > 0
    assert first.paid == first.quantity * first.unit_price // 1000, \
        "the price paid is the price agreed, applied to what was delivered"
    assert first.seller != first.buyer


def test_a_sale_conserves_and_the_ledger_names_both_sides() -> None:
    kernel = load_kernel()
    for _ in range(20):
        before = kernel.book
        kernel, _, log = K.advance_logged(kernel)
        report = W.conservation(
            dataclasses.replace(before, transfers=()),
            dataclasses.replace(kernel.book, transfers=log.transfers))
        for good, (sourced, sunk, unexplained) in report.items():
            assert unexplained == 0, (good, sourced, sunk, unexplained)

        for contract in log.contracts:
            moved = [t for t in log.transfers
                     if t.reason == "sold" and t.good == contract.good]
            paid = [t for t in log.transfers if t.reason == "paid"]
            assert moved and paid, "both legs of the bargain are on the ledger"


def _believing(actor: str, place: str, **readings) -> B.Belief:
    """A belief made by hand, so a policy can be asked one question at a time."""
    return B.Belief(holder=actor).add(*(B.Claim(
        id=f"test|{attribute}", holder=actor, subject=place,
        attribute=attribute, value=value, source="observed",
        observed_turn=1, received_turn=1, confidence=1000)
        for attribute, value in sorted(readings.items())))


def test_a_council_will_not_sell_the_cover_it_is_living_on() -> None:
    """A settlement trades its surplus, never its subsistence.

    And "surplus" is its own grain against its own mouths, not the town's grain
    against the town's -- a granary standing in the same square belonging to a
    temple or a merchant is not cover the council can sell down against. It
    reads both figures itself, so a council that misjudged how many it feeds
    would offer the wrong quantity and nothing here would correct it.
    """
    lean = _believing(INLAND, ARI, own_grain=90_000, need=4_000, price_grain=30)
    assert C.sell_surplus(INLAND, lean, ARI) == (), \
        "a year and a bit of eating is not a surplus, it is the year"

    fat = _believing(INLAND, ARI, own_grain=150_000, need=4_000, price_grain=30)
    quote, = C.sell_surplus(INLAND, fat, ARI)
    assert quote.kind == "quote" and quote.task == C.GRAIN
    assert quote.quantity == 150_000 - 4_000 * C.KEEP_FORTNIGHTS
    assert quote.unit_price == 30, "it asks what grain is going for here"
    assert C.KEEP_FORTNIGHTS >= 24, \
        "the harvest comes once a year, so the reserve has to reach the next one"


def test_a_buyer_short_of_payment_buys_less_and_never_on_credit() -> None:
    """Three bounds, and which one bites is the story of a bad year.

    What the place is short of, what is actually standing on the quay, and what
    the council has left to pay with. The third is the one that ends a
    settlement, and it ends it with grain in sight.
    """
    comfortable = dict(own_grain=0, need=1_000, market_grain=100_000,
                       own_copper=10_000, price_grain=100)
    plenty = _believing(ISLAND, ALASHIYA, **comfortable)
    assert C.buy_shortfall(ISLAND, plenty, ALASHIYA)[0].quantity == \
        1_000 * C.COVER_TARGET, "it shops for the cover it aims at"

    for pinch, expected in (
            (dict(own_grain=1_000 * C.COVER_TARGET - 600), 600),   # wants no more
            (dict(market_grain=700), 700),                         # none for sale
            (dict(own_copper=80), 800)):                           # cannot pay
        bid = C.buy_shortfall(
            ISLAND, _believing(ISLAND, ALASHIYA, **{**comfortable, **pinch}),
            ALASHIYA)
        assert bid and bid[0].quantity == expected, (pinch, bid)

    broke = _believing(ISLAND, ALASHIYA, **{**comfortable, "own_copper": 0})
    assert C.buy_shortfall(ISLAND, broke, ALASHIYA) == (), \
        "an empty purse buys nothing, and asks for no credit"


# --- a crossing takes time ----------------------------------------------------

def test_cargo_is_somewhere_while_it_is_at_sea() -> None:
    """Owned by the buyer, held by the carrier, and located on the route.

    Spec 5.6's shipment is not a number in transit: it is goods, with an owner
    who is not the person holding them, in a place that is neither end. That
    separation is what lets a cargo be lost from somebody in particular.
    """
    kernel, _, _ = _run(load_kernel(), turns=40)
    afloat = [v for v in kernel.voyages if v.cargo]
    assert afloat, "somebody is at sea"

    voyage = afloat[0]
    assert voyage.arrives > voyage.departed, "a crossing takes fortnights"
    for lot_id in voyage.cargo:
        lot = kernel.book.lots[lot_id]
        assert lot.location == voyage.route, "not at either end"
        assert lot.holder == voyage.carrier, "somebody has charge of it"
    assert K.faults(kernel) == ()


def test_the_sea_is_finite_and_rationed_by_the_same_allocator() -> None:
    """Hold is a shared resource, granted by priority and rank like any other."""
    kernel = load_kernel()
    pools = K._capacity(kernel)
    crossings = {k: v for k, v in pools.items() if k.endswith("#cargo")}
    assert crossings, "the crossings are pools the allocator knows about"
    assert C.pool(MAHADU, ALASHIYA) in crossings
    assert C.pool(ALASHIYA, MAHADU) in crossings, "a route is not one-way"

    kernel, _, logs = _run(kernel, turns=40)
    asked = [g for log in logs for g in log.allocation.grants
             if g.resource.endswith("#cargo")]
    assert asked, "and cargoes actually competed for them"
    assert all(g.granted <= g.asked for g in asked)
    assert all(space >= 0 for log in logs
               for space in log.allocation.remaining.values()), \
        "no crossing carried more than it had"


def test_a_cargo_never_exceeds_the_hold_that_was_granted() -> None:
    """What sailed is bounded by what the allocator said it could, not by intent."""
    kernel = load_kernel()
    sailings = 0
    for _ in range(48):
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
            sailings += 1 if sailed else 0
    assert sailings, "some of them sailed"


def test_a_voyage_can_be_lost_and_the_ledger_says_where_it_went() -> None:
    kernel, events, logs = _run(load_kernel(), turns=60)
    losses = [e for e in events if e[0] == "lost_at_sea"]
    assert losses, "the sea takes some of them"

    sunk = [t for log in logs for t in log.transfers if t.reason == "lost"]
    assert sunk, "and every lost qa leaves a sink on the ledger"
    assert all(t.quantity > 0 for t in sunk)
    assert K.faults(kernel) == (), "and nothing is left half at sea"


# --- news travels no faster than the ships ------------------------------------

def test_what_a_port_knows_of_another_is_as_old_as_the_last_ship() -> None:
    kernel, _, _ = _run(load_kernel(), turns=30)
    belief = kernel.beliefs[ISLAND]
    word = belief.best(MAHADU, "price_grain")
    assert word is not None, "the island has heard of the mainland"
    assert word.source in ("reported", "assumed")
    assert word.chain or word.source == "assumed", "somebody carried it"
    assert word.observed_turn < kernel.date.absolute, \
        "it was true when it was seen, not when it arrived"


def test_a_shut_sea_blinds_a_port_and_it_does_not_know_it() -> None:
    """The consequence with teeth. Winter is when a decision is made blind.

    What makes it worth modelling is the second half: nothing tells Alashiya
    that its news has stopped. It goes on deciding from the last thing it heard,
    and cannot tell quiet from nothing to report.
    """
    kernel, _, _ = _run(load_kernel(), turns=48)
    route = kernel.registry.routes["route:mahadu_alashiya"]

    shut = kernel
    while C.sea_open(shut, route):
        shut, _, _ = _run(shut, turns=1)
    opening = shut.beliefs[ISLAND].best(MAHADU, "price_grain").observed_turn

    shut, _, _ = _run(shut, turns=3)
    assert not C.sea_open(shut, route), "still winter"
    later = shut.beliefs[ISLAND].best(MAHADU, "price_grain")
    assert later.observed_turn == opening, "no ship, no word, and no notice of it"


# --- the gate -----------------------------------------------------------------

def test_grain_reaches_the_island_from_the_ground_it_grew_in() -> None:
    """M13.2's exit gate: one conserved chain the inspector can follow.

    Cut into a household on Alashiya, and every link back to the furrow it came
    out of is a record: a household ate it, a council bought it here, a merchant
    landed it off a named voyage, bought it inland, and it was threshed out of a
    crop that was reaped off an estate at Ari. Nothing in that chain is a number
    that appeared; every step is a transfer with a reason and an authority.
    """
    kernel, events, logs = _run(load_kernel(), turns=48)
    kinds = [e[0] for e in events]

    assert "reaped" in kinds and "threshed" in kinds, "it grew somewhere"
    assert "sold" in kinds, "and it was bought"
    assert "sailed" in kinds and "landed" in kinds, "and it crossed"

    to_island = [c for log in logs for c in log.contracts
                 if c.place == ALASHIYA and c.buyer == ISLAND]
    from_inland = [c for log in logs for c in log.contracts
                   if c.place == ARI and c.seller == INLAND]
    assert to_island and from_inland, "both ends of the line traded"
    assert all(c.buyer == MERCHANT for c in from_inland), \
        "the house buys on its own account and carries the risk itself"

    landed = sum(e[4] for e in events if e[0] == "landed"
                 and e[2] == ALASHIYA and e[3] == C.GRAIN)
    bought = sum(c.quantity for c in from_inland)
    assert 0 < landed <= bought, "nothing arrived that was not first bought"


def test_the_crossing_is_what_stands_between_the_island_and_decline() -> None:
    """The counterfactual, which is the only way the gate means anything.

    Same world, same seed, same ground -- routes cut. The difference between the
    two runs is entirely the merchant, and it is the difference between a port
    that holds its people and one that does not.
    """
    supplied, _, _ = _run(load_kernel(), turns=48)
    alone, _, _ = _run(landlocked(load_kernel()), turns=48)

    assert supplied.people(ALASHIYA) > alone.people(ALASHIYA), \
        "the crossing reaches the households"
    assert alone.stores(ALASHIYA) == 0, "and without it the granary is empty"

    # It was not free, and it was not charity: the island paid in metal, and the
    # metal is standing where the grain came from.
    assert supplied.stores(ALASHIYA, C.COPPER) < alone.stores(ALASHIYA, C.COPPER)
    assert supplied.stores(ARI, C.COPPER) > alone.stores(ARI, C.COPPER)


def test_the_merchant_carries_the_risk_and_can_lose_by_it() -> None:
    """A house that crosses on a four-fortnight-old price is making a bet.

    It buys on its own account, so what it holds at any moment is stock and
    metal it has committed. The claim is not that it profits -- it is that the
    exposure is real and sits on its books rather than nobody's.
    """
    kernel, events, _ = _run(load_kernel(), turns=48)
    assert _held(kernel, MERCHANT, C.GRAIN) + _held(kernel, MERCHANT, C.COPPER) > 0

    lost = [e for e in events if e[0] == "lost_at_sea"]
    assert lost, "and some of it went down"
    afloat = [v for v in kernel.voyages if v.cargo and v.carrier == MERCHANT]
    assert all(kernel.book.lots[l].owner == MERCHANT
               for v in afloat for l in v.cargo), \
        "what is at sea is the house's, not the buyer's at the far end"


def test_the_crossing_is_deterministic() -> None:
    first, _, _ = _run(load_kernel(), turns=30)
    second, _, _ = _run(load_kernel(), turns=30)
    assert [(v.id, v.cargo, v.arrives) for v in first.voyages] == \
           [(v.id, v.cargo, v.arrives) for v in second.voyages]
    assert [(i, first.book.lots[i]) for i in sorted(first.book.lots)] == \
           [(i, second.book.lots[i]) for i in sorted(second.book.lots)]


def test_the_trade_policy_reads_belief_and_never_the_world() -> None:
    """Spec 10.11, held by the signature and then by the behaviour.

    A house with no claims decides nothing. Not "decides badly" -- there is no
    fallback to a lookup, so a merchant that has heard nothing does nothing,
    which is the correct behaviour for a merchant that has heard nothing.
    """
    assert C.trade(MERCHANT, B.Belief(holder=MERCHANT)) == ()

    only_home = B.Belief(holder=MERCHANT).add(B.Claim(
        id="c|home", holder=MERCHANT, subject=MAHADU, attribute="home", value=1,
        source="observed", observed_turn=1, received_turn=1, confidence=1000))
    assert C.home(only_home) == MAHADU
    assert C.trade(MERCHANT, only_home) == (), "one price is not a line"


def test_a_house_buys_no_more_than_a_fortnight_can_carry() -> None:
    """However full the strongbox. Without this a bargain is unbounded by anything
    physical, and a hundred thousand qa changes hands in an afternoon."""
    kernel, _, logs = _run(load_kernel(), turns=48)
    bought = [c for log in logs for c in log.contracts if c.buyer == MERCHANT]
    assert bought, "the house buys"
    assert max(c.quantity for c in bought) <= C.LINE_CARGO


def test_lots_are_folded_back_together_and_it_conserves() -> None:
    """A port that trades every fortnight accumulates lots faster than grain."""
    kernel, _, _ = _run(load_kernel(), turns=48)
    at_home = [lot for lot in kernel.book.at(MAHADU)
               if lot.good == C.GRAIN and not lot.reserved]
    by_owner: dict[str, int] = {}
    for lot in at_home:
        by_owner[lot.owner] = by_owner.get(lot.owner, 0) + 1
    assert by_owner and max(by_owner.values()) <= 2, \
        "one store per owner per place, not one per bargain ever struck"
    assert K.faults(kernel) == ()


def test_the_farm_year_still_runs_underneath_all_of_it() -> None:
    """The crossing did not replace production; grain still has to be grown."""
    kernel, events, _ = _run(load_kernel(), turns=30)
    kinds = {e[0] for e in events}
    assert {"reaped", "threshed", "set_aside", "sown"} <= kinds
    assert F.held(kernel.book, INLAND, F.SEED,
                  kernel.field_site(ARI, INLAND)) >= 0
