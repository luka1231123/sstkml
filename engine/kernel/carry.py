"""The crossing: quotes, contracts, loading, journeys, delivery, payment.

Spec 6.6 and 6.7, and the whole of M13.2's reason for existing. The grain year
in `engine.kernel.farm` ends with a settlement that cannot feed itself and
cannot decide its way out, because the ground has an extent. This is the
mechanism by which grain reaches it from somewhere that has some -- or does not.

Four things had to be true before any of it was worth building, and the farm
chain is what made them true: grain is physical, it is owned by somebody, the
place that needs it is short of ground rather than short of effort, and the
place that has it has a surplus it did not plan.

The chain, in the order the phases run it:

    market      a seller quotes, a buyer accepts, goods and payment change
                owner -- both parties standing in the same place
    movement    the buyer loads what it now owns, and a voyage departs
    arrivals    two fortnights later it lands, or it does not
    market      the cargo is now at the far place, and is sold there

There is no cross-place bargaining, and that is deliberate rather than a
shortcut. A merchant at Ma'hadu cannot agree a price with a council on Alashiya
without a round trip to do it in, so it does what the period's merchants did: it
buys on its own account, carries, and sells on arrival at whatever the price
there turns out to be. The risk of the crossing is entirely its own, and the
thing it is risking on is a price it last heard about four fortnights ago.

That staleness is the point. News travels on the same ships as the cargo, so
what a merchant believes about the far port is exactly as old as its last
returning voyage -- and a ship that sinks carries no news home either.

Two prices, one function. Everyone values grain by how many fortnights of eating
the local store represents, so a place with a full granary sells cheap and a
place with an empty one pays dearly. Nobody is reading anyone else's books: each
actor prices what it can see, and the merchant's margin is the difference
between two places it has to physically cross between.

What is not built here, and is M13.3's:

Forward delivery. Every bargain struck below is settled where it is struck, so
no contract outlives its turn and none is carried in the world's state. When a
contract can promise delivery next spring, it becomes state and this changes.

Vessels. A route's `capacity` is the port's whole carrying trade per fortnight,
not one hull; individual ships with condition, crew, and provisioning are the
next milestone's. What is real here is that the sea shuts, the crossing takes
time, capacity is finite and rationed by the same allocator as everything else,
and a voyage can be lost outright.

Credit. A buyer short of payment buys less. It cannot promise to pay later,
because a debt that outlives the turn is the same state problem as a forward
contract, and M13.3 builds both together.
"""
from __future__ import annotations

import dataclasses

from engine import believe as B
from engine.core import stream
from engine.entity import EntityId, mint
from engine.kernel import farm as F
from engine.kernel import resolve as R
from engine.kernel.intent import Intent

GRAIN = F.GRAIN
COPPER = "copper"

# --- price (spec 6.6) ---------------------------------------------------------
#
# Shekels of copper per thousand qa of grain, from one reading: how many
# fortnights of eating the store in front of you represents. It is deterministic
# and tunable and is not offered as an ancient formula.
#
# The shape is what matters. Price rises without bound as the store empties and
# flattens once there is plenty, because the last qa before starvation is worth
# everything and the ten-thousandth is worth what anyone will give. The floor
# and ceiling are the admission that neither end is really unbounded: a glut does
# not make grain free, and a famine price is capped by what the buyer has.

BASE_PRICE = 60          # what a thousand qa fetches at an ordinary cover
TARGET_COVER = 12        # fortnights of eating that counts as ordinary
PRICE_FLOOR = 15
PRICE_CEILING = 400

# What a council keeps before it will sell anything at all, and it has to be a
# year. Grain arrives once, in the harvest fortnights, and is eaten for the
# twenty-four after them: a council reading its granary the morning after
# threshing is looking at everything it will have until this time next year.
# A smaller figure here does not make it a bolder trader, it makes it a council
# that sells its winter in the autumn -- which the port duly did, at a good
# price, and then starved with the money in the strongbox.
#
# This is a different reserve from `farm`'s seed, and larger. Seed is set aside
# against next year; this is what the town lives on to reach it.
KEEP_FORTNIGHTS = 26

# What a council will hold if it can buy: the cover it aims at, and therefore
# the size of the deficit it goes shopping with. Above a year, because a place
# that buys its food wants the next harvest's worth in hand before the sea
# shuts, not on the day it runs out.
COVER_TARGET = 28

# The margin a merchant wants on a thousand qa before it is worth crossing. Not
# a cost that is charged anywhere -- the crossing's real costs are the loading
# labour, the capacity, and the chance of losing the lot -- but the merchant's
# own rule of thumb about when a voyage is worth making.
CROSSING_MARGIN = 40

# The most one house buys in one fortnight, whatever its purse says. A merchant
# with a full strongbox standing in front of a granary is not thereby able to
# buy the granary: it can only buy what it can move, and what it can move is one
# season's worth of the line it works. Without this the house bids its entire
# capital into a single bargain, which is how a hundred thousand qa changes
# hands in an afternoon -- an artefact of there being no vessels yet, not a
# thing about the period. M13.3's hulls replace this with the real bound.
LINE_CARGO = 4000

# Qa a person loads or discharges in a day. Small enough that a cargo is a real
# call on the same person-days the harvest wants, which is the interesting case:
# the sailing season and the harvest window overlap.
LOAD_PER_DAY = 25

# How much hold a unit of a good takes, relative to a qa of grain. Copper is
# dense and grain is not: sixty shekels of copper stow like one qa of grain,
# which is why a ship can bring back the price of the cargo it carried out.
BULK = {COPPER: 60}

# Ordinal blocks for lots minted here, clear of `farm`'s (200-1100) and the
# settlement phase's (2000+).
BLOCKS = {"sale": 3000, "pay": 3400, "land": 3800}

# Where the fortnight's ordinary traffic numbers its journeys from, clear of the
# cargo voyages leaving the same route on the same turn.
DISPATCH = 100


def price(stores: int, need: int) -> int:
    """What a thousand qa is worth where this much is standing against this need."""
    if need <= 0:
        return PRICE_FLOOR
    cover = stores // need
    if cover <= 0:
        return PRICE_CEILING
    return max(PRICE_FLOOR, min(PRICE_CEILING,
                                BASE_PRICE * TARGET_COVER // cover))


def bulk(good: str, quantity: int) -> int:
    """Hold a quantity takes, in qa-of-grain equivalents. Rounded up."""
    per = BULK.get(good, 1)
    return -(-max(0, quantity) // per)


def unbulk(good: str, hold: int) -> int:
    """The quantity that fits in this much hold. The inverse of `bulk`."""
    return max(0, hold) * BULK.get(good, 1)


# --- the world's side of it ---------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Voyage:
    """Cargo at sea: spec 5.6's Journey and Shipment, which here are one thing.

    They are one thing because nothing in M13.2 travels without cargo or
    alongside a different journey. When envoys and troops move in M13.4 they
    will want the journey without the shipment, and this splits.

    `news` is spec 5.6's "intended report path", captured at departure: the
    readings the origin would have given anyone who asked, on the day the ship
    left. It arrives with the ship or not at all.
    """
    id: EntityId
    route: EntityId
    carrier: EntityId                    # who has the cargo while it is at sea
    origin: EntityId
    destination: EntityId
    departed: int
    arrives: int
    cargo: tuple[EntityId, ...] = ()     # lot ids
    news: tuple[tuple[str, int], ...] = ()


@dataclasses.dataclass(frozen=True)
class Contract:
    """One bargain struck (spec 5.5). Not world state; see the module docstring.

    Every contract below is agreed, delivered, and paid inside the phase that
    matched it, so it is a record of what happened rather than a promise that
    outlives the turn. It rides in the turn log, which is what the inspector
    reads.
    """
    id: EntityId
    seller: EntityId
    buyer: EntityId
    place: EntityId
    good: str
    quantity: int
    unit_price: int          # per thousand, in `pay_good`
    pay_good: str
    paid: int
    turn: int


def settlement_of(kernel, place: EntityId) -> EntityId:
    """The settlement a route endpoint belongs to. A harbour is not a town."""
    site = kernel.registry.sites.get(place)
    return site.settlement if site else place


def sea_open(kernel, route) -> bool:
    """Whether every leg of a route is in season. One shut leg shuts the route."""
    return all(not leg.season
               or F.season(kernel.seasons, kernel.date.fortnight, leg.season)
               for leg in route.legs)


def pool(origin: EntityId, destination: EntityId) -> EntityId:
    """The exclusive pool a cargo draws on, named by where it is going.

    By destination rather than by route id, because an actor decides to send
    grain to Alashiya; which route carries it, and whether one exists, is the
    world's answer and not part of the decision. This is also what lets the
    trade policy name a pool without being handed the route table.
    """
    return f"{origin}>{destination}#cargo"


def capacity(kernel) -> dict[EntityId, int]:
    """Every crossing's tonnage this fortnight. Zero when the sea is shut.

    Both directions of every route, because a sea crossing is not one-way and
    authoring the return leg separately would be bookkeeping rather than
    modelling. Two routes between the same pair add their capacity together.
    """
    pools: dict[EntityId, int] = {}
    for route_id in sorted(kernel.registry.routes):
        route = kernel.registry.routes[route_id]
        if not route.legs:
            continue
        here = settlement_of(kernel, route.origin)
        there = settlement_of(kernel, route.destination)
        space = route.capacity if sea_open(kernel, route) else 0
        for key in (pool(here, there), pool(there, here)):
            pools[key] = pools.get(key, 0) + space
    return pools


def route_between(kernel, origin: EntityId, destination: EntityId):
    """The route a cargo would go by, or None. Lowest id wins a tie."""
    for route_id in sorted(kernel.registry.routes):
        route = kernel.registry.routes[route_id]
        if not route.legs:
            continue
        ends = {settlement_of(kernel, route.origin),
                settlement_of(kernel, route.destination)}
        if ends == {origin, destination} and sea_open(kernel, route):
            return route
    return None


def reachable(kernel, settlement: EntityId) -> tuple[EntityId, ...]:
    """Everywhere a route runs to from here, in season or not.

    Out of season as well as in, because a merchant knows where the crossing
    goes in the winter too. What it cannot do in the winter is sail it.
    """
    found: set[EntityId] = set()
    for route_id in sorted(kernel.registry.routes):
        route = kernel.registry.routes[route_id]
        if not route.legs:
            continue
        ends = {settlement_of(kernel, route.origin),
                settlement_of(kernel, route.destination)}
        if settlement in ends:
            found |= ends - {settlement}
    return tuple(sorted(found))


# --- what a place looks like to anyone standing in it -------------------------

def readings(kernel, settlement: EntityId) -> dict[str, int]:
    """The market as a person in it would describe it. No books are opened.

    Both figures are about the place rather than about whoever is looking, which
    is what makes them the things that travel: what grain is going for here, and
    whether there is any standing on the quay that is not already somebody's
    stores. A carrier can repeat either to a stranger.

    What is deliberately not here is how much anyone can spare or is short of.
    Those are positions, not readings -- they depend on whose granary it is and
    how many mouths that owner feeds -- and an actor works them out below from
    what it counted of its own, which is the only place it could honestly get
    them. Putting them here once meant a council read the whole town's grain,
    the merchant's warehouse included, as cover it could sell down against.
    """
    need = sum(c.ration() for c in kernel.cohorts_of(settlement))
    stores = kernel.stores(settlement, GRAIN)
    mine = {settlement, kernel.controller(settlement)}
    market = sum(lot.free for lot in kernel.book.at(settlement)
                 if lot.good == GRAIN and lot.owner not in mine)
    return {"price_grain": price(stores, need), "market_grain": market}


# --- policy (spec 10.11): `(actor, belief)`, and never the world --------------

def _quote(actor: EntityId, turn: int, place: EntityId, good: str,
           quantity: int, unit_price: int) -> Intent:
    return Intent(
        id=f"{actor}|sell|{place}|{good}", actor=actor, kind="quote", turn=turn,
        subject=place, quantity=quantity, task=good, unit_price=unit_price,
        authority=actor)


def _accept(actor: EntityId, turn: int, place: EntityId, good: str,
            quantity: int, ceiling: int, basis: tuple[str, ...]) -> Intent:
    return Intent(
        id=f"{actor}|buy|{place}|{good}", actor=actor, kind="contract",
        turn=turn, subject=place, quantity=quantity, task=good,
        unit_price=ceiling, authority=actor, basis=basis)


def _ship(actor: EntityId, turn: int, origin: EntityId, destination: EntityId,
          good: str, quantity: int) -> Intent | None:
    hold = bulk(good, quantity)
    if hold <= 0:
        return None
    return Intent(
        id=f"{actor}|ship|{origin}>{destination}|{good}", actor=actor, kind="ship",
        turn=turn, subject=destination, quantity=hold, task=good,
        resource=pool(origin, destination), authority=actor)


def sell_surplus(actor: EntityId, belief: B.Belief,
                 home: EntityId) -> tuple[Intent, ...]:
    """Offer what you believe you can spare, at what you believe it is worth.

    A council does not trade for gain; it sells the surplus of a good year
    because copper keeps and grain does not. What it will not sell is the cover
    it is living on: its own grain, against its own mouths, for the months it
    has to get through. Both numbers are its own counting, so a council that
    misjudged how many it feeds would offer the wrong quantity and nothing here
    would correct it.
    """
    spare = (belief.value(home, "own_grain", 0)
             - belief.value(home, "need", 0) * KEEP_FORTNIGHTS)
    ask = belief.value(home, "price_grain", 0)
    if spare <= 0 or ask <= 0:
        return ()
    return (_quote(actor, belief.value(home, "turn", 0), home, GRAIN, spare, ask),)


def buy_shortfall(actor: EntityId, belief: B.Belief,
                  home: EntityId) -> tuple[Intent, ...]:
    """Buy what is standing in your own harbour, if you are short and can pay.

    Bounded three ways, and which one bites is the whole story of a bad year:
    what the place is short of, what is actually for sale here, and what the
    council has left to pay with. The third is the one that ends a settlement,
    and it ends it while there is grain on the quay.
    """
    deficit = (belief.value(home, "need", 0) * COVER_TARGET
               - belief.value(home, "own_grain", 0))
    offered = belief.value(home, "market_grain", 0)
    purse = belief.value(home, "own_copper", 0)
    ceiling = belief.value(home, "price_grain", 0)
    if deficit <= 0 or offered <= 0 or purse <= 0 or ceiling <= 0:
        return ()
    affordable = purse * 1000 // ceiling
    quantity = min(deficit, offered, affordable)
    if quantity <= 0:
        return ()
    return (_accept(actor, belief.value(home, "turn", 0), home, GRAIN, quantity,
                    ceiling,
                    tuple(c.id for c in belief.about(home, "own_grain"))),)


def trade(actor: EntityId, belief: B.Belief) -> tuple[Intent, ...]:
    """A merchant house runs one line: buy at the cheapest end, sell at the dearest.

    Everything below is a claim and nothing is a lookup. The price at its seat it
    saw this morning. The price at each end it had from the last carrier in,
    which left there before it left here -- so a house commits its whole purse
    to a crossing on a number that is at best four fortnights old, and the
    voyage is a bet that the number has not moved. In the fortnight a foreign
    harvest comes in, it has moved a long way.

    One buying place and one selling place, rather than a bid at every port it
    knows. That is a real restriction and it is the right one: a house that
    could work both ends of three markets at once would need a simultaneous view
    of all of them, which is exactly what nobody in this world has. What it can
    do is keep a factor at each end of one line and move money one way along it
    while the goods go the other.

    Goods and money both route through the seat, because the seat is the only
    place the house has a route from -- Ma'hadu is a transshipment port and this
    is what being one consists of. Grain comes down to the port and goes out;
    copper comes in and goes up. Nothing crosses in one hop that has no crossing.

    Grain always moves toward the dearest place the house knows of, one hop at a
    time, and only while that place is dearer than where the grain is standing
    by more than the crossing margin. Stating it as a single destination rather
    than as a pairwise comparison at each quay is what keeps the line from
    reversing itself: there is one maximum, so there is one direction, and the
    margin is the dead band that stops a fortnight's small move from flipping it.
    Grain that is not moving is grain that is for sale where it stands -- a
    factor with stock and no onward leg sells it at the local price, which is
    also how a cargo that arrived into a fallen market eventually clears.
    """
    seat = home(belief)
    if not seat:
        return ()
    turn = belief.value(seat, "turn", 0)
    prices = {place: belief.value(place, "price_grain", 0)
              for place in _subjects(belief)
              if belief.value(place, "price_grain", 0) > 0}
    if len(prices) < 2:
        return ()

    # Ties by id, and stable: sorting first means `max` and `min` take the
    # lowest-id place among equals rather than whichever the mapping offered.
    order = sorted(prices)
    dearest = max(order, key=lambda p: prices[p])
    cheapest = min(order, key=lambda p: prices[p])
    worth_it = (dearest != cheapest
                and prices[dearest] - prices[cheapest] > CROSSING_MARGIN)

    intents: list[Intent] = []
    for place in order:
        grain = belief.value(place, "own_grain", 0)
        copper = belief.value(place, "own_copper", 0)

        # Buy where it is cheapest, with the money that is standing there, and
        # with as much of it as a fortnight's carrying can lift.
        if worth_it and place == cheapest and copper > 0:
            want = min(copper * 1000 // prices[place], LINE_CARGO)
            if want > 0:
                intents.append(_accept(
                    actor, turn, place, GRAIN, want, prices[place],
                    tuple(c.id for c in belief.about(dearest, "price_grain"))))

        # The next hop toward the dearest market, if the grain here has one.
        onward = ""
        if prices[dearest] - prices[place] > CROSSING_MARGIN:
            onward = dearest if place == seat else seat
        if grain > 0 and onward:
            intents.append(_ship(actor, turn, place, onward, GRAIN, grain))
        elif grain > 0:
            # No leg worth making: the factor sells where it is standing.
            intents.append(_quote(actor, turn, place, GRAIN, grain,
                                  prices[place]))

        # Money goes the other way along the line, to whichever end is buying.
        if worth_it and place != cheapest and copper > 0:
            intents.append(_ship(actor, turn, place,
                                 cheapest if place == seat else seat,
                                 COPPER, copper))
    return tuple(i for i in intents if i is not None)


def home(belief: B.Belief) -> EntityId:
    """Where this actor is, out of its own belief rather than out of a table.

    An actor that holds claims about three ports has to be able to say which one
    it is standing in, and a policy is handed nothing but its own name and its
    own belief. So `home` is a claim like any other -- observed, dated, and
    minted in phase 3 where every other observation is.
    """
    for claim in reversed(belief.claims):
        if claim.attribute == "home" and claim.value == 1:
            return claim.subject
    return ""


def _subjects(belief: B.Belief) -> tuple[EntityId, ...]:
    return tuple(sorted({c.subject for c in belief.claims}))


# --- phase 8: the market ------------------------------------------------------

def _ids(parent: EntityId, turn: int, block: str):
    """Lot ids from one block, handed out in call order within a single step."""
    ordinal = BLOCKS[block]
    while True:
        yield mint(parent, turn, "lot", ordinal)
        ordinal += 1


def _move(book, seller: EntityId, buyer: EntityId, good: str, place: EntityId,
          quantity: int, reason: str, ids, authority: EntityId = ""):
    """Move a quantity of one owner's goods at one place to another owner."""
    moved = 0
    lots = tuple(lot for lot in book.owned_by(seller)
                 if lot.good == good and lot.location == place)
    for lot in lots:
        if moved >= quantity:
            break
        current = book.lots.get(lot.id)
        if current is None:
            continue
        take = min(quantity - moved, current.free)
        if take <= 0:
            continue
        book = book.give(
            current.id, take, buyer, reason, authority=authority,
            new_id=None if take == current.quantity else next(ids))
        moved += take
    return book, moved


def market(kernel, intents: tuple[Intent, ...]):
    """Phase 8. Quotes and acceptances meet, at one place, and goods change hands.

    Matched greedily and in a fixed order: the cheapest ask first, the highest
    bid first, ties by intent id. Nothing is prorated, for the same reason the
    labour allocator does not prorate -- a buyer who was outbid should be
    visibly short rather than quietly given a fraction.

    The price paid is the seller's ask. A buyer whose ceiling is above it does
    not get the difference back; what its ceiling bought was the right to be
    served at all. Modelling the haggle between the two is a bargaining problem
    and it is spec 6.6's, not this milestone's.
    """
    events: list = []
    contracts: list[Contract] = []
    book = kernel.book.at_phase(kernel.date.absolute, "market")
    turn = kernel.date.absolute

    for place in sorted(kernel.registry.settlements):
        asks = sorted((i for i in intents
                       if i.kind == "quote" and i.subject == place),
                      key=lambda i: (i.unit_price, i.id))
        bids = sorted((i for i in intents
                       if i.kind == "contract" and i.subject == place),
                      key=lambda i: (-i.unit_price, i.id))
        if not asks or not bids:
            continue
        left = {ask.id: ask.quantity for ask in asks}
        sale = _ids(place, turn, "sale")
        pay = _ids(place, turn, "pay")

        for bid in bids:
            want = bid.quantity
            for ask in asks:
                if want <= 0:
                    break
                if ask.task != bid.task or ask.actor == bid.actor:
                    continue
                if ask.unit_price > bid.unit_price:
                    break            # asks ascend: nothing after this is cheaper
                unit = ask.unit_price
                purse = sum(lot.free for lot in book.owned_by(bid.actor)
                            if lot.good == COPPER and lot.location == place)
                stock = sum(lot.free for lot in book.owned_by(ask.actor)
                            if lot.good == ask.task and lot.location == place)
                quantity = min(want, left[ask.id], stock, purse * 1000 // unit)
                if quantity <= 0:
                    continue

                book, delivered = _move(book, ask.actor, bid.actor, ask.task,
                                        place, quantity, "sold", sale,
                                        authority=ask.id)
                if delivered <= 0:
                    continue
                cost = delivered * unit // 1000
                book, paid = _move(book, bid.actor, ask.actor, COPPER, place,
                                   cost, "paid", pay, authority=bid.id)
                left[ask.id] -= delivered
                want -= delivered
                contracts.append(Contract(
                    id=f"{ask.id}>{bid.id}@{turn}", seller=ask.actor,
                    buyer=bid.actor, place=place, good=ask.task,
                    quantity=delivered, unit_price=unit, pay_good=COPPER,
                    paid=paid, turn=turn))
                events.append(("sold", ask.actor, bid.actor, place, ask.task,
                               delivered, unit))

    return dataclasses.replace(kernel, book=book), events, tuple(contracts)


# --- phase 9: loading and departure -------------------------------------------

def movement(kernel, intents: tuple[Intent, ...], allocation: R.Allocation):
    """Phase 9. What was granted hold, and can be carried, goes aboard and sails.

    Three separate things have to be true and each of them refuses differently.
    The sea must be open, or there is no route and nothing moves. Hold must have
    been granted, and it was rationed against every other cargo by the same
    allocator that rations the harvest's hands. And the goods must actually be
    there -- a merchant that intended to buy and was outbid loads what it has,
    which is nothing.
    """
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "movement")
    turn = kernel.date.absolute
    voyages = list(kernel.voyages)
    sailings = sorted((i for i in intents if i.kind == "ship"),
                      key=lambda i: i.id)

    for ordinal, intent in enumerate(sailings):
        hold = allocation.granted(intent.id)
        if hold <= 0:
            continue
        origin = _origin_of(intent.resource)
        route = route_between(kernel, origin, intent.subject)
        if route is None:
            continue

        wanted = unbulk(intent.task, hold)
        cargo: list[EntityId] = []
        aboard = 0
        for lot in tuple(book.owned_by(intent.actor)):
            if aboard >= wanted:
                break
            if lot.good != intent.task or lot.location != origin or lot.free <= 0:
                continue
            take = min(wanted - aboard, lot.free)
            if take < lot.quantity:
                # Part of a lot sails and the rest stays on the quay: the two
                # are in different places from here on and cannot be one lot.
                part = mint(origin, turn, "lot", BLOCKS["land"] + len(cargo))
                book = book.split(lot.id, take, part)
                lot_id = part
            else:
                lot_id = lot.id
            if book.lots[lot_id].holder != intent.actor:
                book = book.hand(lot_id, intent.actor, "loaded",
                                 authority=intent.id)
            book = book.relocate(lot_id, route.id, "carried", authority=intent.id)
            cargo.append(lot_id)
            aboard += take

        if not cargo:
            continue
        voyage = Voyage(
            id=mint(route.id, turn, "journey", ordinal), route=route.id,
            carrier=intent.actor, origin=origin, destination=intent.subject,
            departed=turn, arrives=turn + route.fortnights(),
            cargo=tuple(cargo),
            news=tuple(sorted(readings(kernel, origin).items())))
        voyages.append(voyage)
        events.append(("sailed", voyage.id, origin, intent.subject,
                       intent.task, aboard))

    kernel = dataclasses.replace(kernel, book=book, voyages=tuple(voyages))
    return _dispatch(kernel, events)


def _dispatch(kernel, events: list):
    """The ordinary traffic, which carries word whether or not it carries cargo.

    Nothing here is a courier system -- orders and envoys are M13.4's. This is
    the plainer fact underneath one: a road that a village uses and a sea lane
    that a port lives by have people going along them all the time, and what
    those people know arrives when they do.

    Modelled as a voyage with an empty hold, so it costs no capacity and gets
    everything else for free: it takes the crossing's time, it is stopped by the
    season, and it can be lost. That last is worth having. A settlement whose
    news does not come is not told that its news did not come; it goes on acting
    on the last thing it heard, and cannot tell the difference between quiet and
    nothing to report.

    The consequence with teeth is seasonal. When the sea shuts, Alashiya goes
    dark for four fortnights, and every decision made about it in that time is
    made on a picture of a port as it stood before the winter.
    """
    turn = kernel.date.absolute
    voyages = list(kernel.voyages)
    for route_id in sorted(kernel.registry.routes):
        route = kernel.registry.routes[route_id]
        if not route.legs or not sea_open(kernel, route):
            continue
        here = settlement_of(kernel, route.origin)
        there = settlement_of(kernel, route.destination)
        for ordinal, (origin, destination) in enumerate(
                ((here, there), (there, here))):
            if origin == destination:
                continue
            voyages.append(Voyage(
                # Ordinals from a block of their own, clear of the fortnight's
                # cargo voyages at the same route on the same turn.
                id=mint(route_id, turn, "journey", DISPATCH + ordinal),
                route=route_id, carrier=origin, origin=origin,
                destination=destination, departed=turn,
                arrives=turn + route.fortnights(),
                news=tuple(sorted(readings(kernel, origin).items()))))
    return dataclasses.replace(kernel, voyages=tuple(voyages)), events


def _origin_of(resource: EntityId) -> EntityId:
    return resource.split(">", 1)[0] if ">" in resource else ""


def loading_days(intents: tuple[Intent, ...],
                 allocation: R.Allocation) -> dict[EntityId, int]:
    """Person-days a fortnight's sailings would take, by actor. Read by nobody yet.

    Kept as a reading rather than wired in: loading is a real call on the same
    hands the harvest wants, but charging it against the labour pool needs the
    cargo to be known in phase 5, and the cargo is not bought until phase 8.
    Spec 6.1 will not have phase 8 run before phase 5, and it is right. The fix
    is a standing order placed a fortnight ahead, which is M13.4's.
    """
    days: dict[EntityId, int] = {}
    for intent in intents:
        if intent.kind != "ship":
            continue
        got = allocation.granted(intent.id)
        if got > 0:
            days[intent.actor] = days.get(intent.actor, 0) + F.days_for(
                unbulk(intent.task, got), LOAD_PER_DAY)
    return days


# --- phase 2: arrivals --------------------------------------------------------

def arrivals(kernel):
    """Phase 2. The ships due today land, and what they carry lands with them.

    Both cargoes: the goods, and what the crew knows. A voyage that is lost
    delivers neither, which is the honest form of the thing -- the far port does
    not learn that the ship sank, it learns nothing at all, and goes on believing
    whatever the last one told it.
    """
    events: list = []
    if not kernel.voyages:
        return kernel, events

    turn = kernel.date.absolute
    book = kernel.book.at_phase(turn, "arrivals")
    still = tuple(v for v in kernel.voyages if v.arrives > turn)
    due = tuple(v for v in kernel.voyages if v.arrives <= turn)
    landed: list[Voyage] = []

    for voyage in due:
        risk = kernel.registry.routes[voyage.route].risk
        rng = stream(kernel.seed, turn, "kernel.voyage", voyage.id)
        if rng.chance(risk, 1000):
            for lot_id in voyage.cargo:
                lot = book.lots.get(lot_id)
                if lot is not None:
                    book = book.consume(lot_id, lot.quantity, "lost",
                                        authority=voyage.id)
            # A cargo lost is an event with a hole in the ledger behind it. A
            # courier lost is only an absence, and is logged as one: nobody at
            # the far end knows a ship was even due.
            events.append((
                "lost_at_sea" if voyage.cargo else "no_word",
                voyage.id, voyage.route, voyage.destination))
            continue

        for lot_id in voyage.cargo:
            lot = book.lots.get(lot_id)
            if lot is None:
                continue
            book = book.relocate(lot_id, voyage.destination, "unloaded",
                                 authority=voyage.id)
            if lot.holder != lot.owner:
                book = book.hand(lot_id, lot.owner, "unloaded",
                                 authority=voyage.id)
            events.append(("landed", voyage.id, voyage.destination, lot.good,
                           lot.quantity))
        landed.append(voyage)

    kernel = dataclasses.replace(kernel, book=book, voyages=still)
    return _tell(kernel, tuple(landed), events)


def _tell(kernel, landed: tuple[Voyage, ...], events: list):
    """What the crews say when they come ashore (spec 5.8, 6.1 phase 2).

    A dated, sourced, second-hand claim with the carrier in its chain -- the
    ordinary form of everything an actor knows about anywhere it is not. The
    value is not distorted here; it is simply old, and it says how old.
    """
    if not landed:
        return kernel, events
    turn = kernel.date.absolute
    beliefs = dict(kernel.beliefs)
    for voyage in landed:
        for actor in kernel.deciders():
            if kernel.registry.orgs[actor].settlement != voyage.destination:
                continue
            belief = beliefs.get(actor, B.Belief(holder=actor))
            belief = belief.add(*(B.Claim(
                id=f"{voyage.id}>{actor}|{attribute}", holder=actor,
                subject=voyage.origin, attribute=attribute, value=value,
                source="reported", observed_turn=voyage.departed,
                received_turn=turn, chain=(voyage.carrier,), confidence=900)
                for attribute, value in voyage.news))
            beliefs[actor] = belief
        events.append(("news", voyage.origin, voyage.destination,
                       turn - voyage.departed))
    return dataclasses.replace(kernel, beliefs=beliefs), events


# --- phase 10: the stores tidy up ---------------------------------------------

def consolidate(kernel):
    """Fold identical lots together. Bookkeeping, and it conserves.

    Every sale splits a lot, so a port that trades every fortnight accumulates
    lots faster than it accumulates grain, and nothing distinguishes them: same
    good, same owner, same holder, same place. A store is a store. Reserved lots
    and anything at sea are left alone, because those are distinguished by
    something the fields do not show.
    """
    book = kernel.book.at_phase(kernel.date.absolute, "settlement")
    groups: dict[tuple, list[EntityId]] = {}
    for lot_id in sorted(book.lots):
        lot = book.lots[lot_id]
        if lot.reserved or lot.location in kernel.registry.routes:
            continue
        groups.setdefault(
            (lot.good, lot.owner, lot.holder, lot.location, lot.quality),
            []).append(lot_id)

    merged = 0
    for key in sorted(groups):
        ids = groups[key]
        for lot_id in ids[1:]:
            book = book.merge(ids[0], lot_id)
            merged += 1
    events = [("consolidated", merged)] if merged else []
    return dataclasses.replace(kernel, book=book), events
