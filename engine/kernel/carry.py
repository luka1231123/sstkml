"""The crossing: quotes, contracts, loading, journeys, delivery, payment."""
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

BASE_PRICE = 60          # what a thousand qa fetches at an ordinary cover
TARGET_COVER = 12        # fortnights of eating that counts as ordinary
PRICE_FLOOR = 15
PRICE_CEILING = 400

# What a council keeps before it will sell anything at all, and it has to be a year.
KEEP_FORTNIGHTS = 26

# The cover a council aims at when buying, and so the size of its order.
COVER_TARGET = 28

# The margin a merchant wants on a thousand qa before it is worth crossing.
CROSSING_MARGIN = 40

# The most one house buys in one fortnight, whatever its purse says.
LINE_CARGO = 4000

# Qa a person loads or discharges in a day.
LOAD_PER_DAY = 25

# How much hold a unit of a good takes, relative to a qa of grain.
BULK = {COPPER: 60}

# Ordinal blocks for lots minted here, clear of `farm`'s (200-1100) and the settlement phase's.
BLOCKS = {"sale": 3000, "pay": 3400, "land": 3800}

# Where the fortnight's ordinary traffic numbers its journeys from, clear of the cargo voyages.
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
    """Cargo at sea: spec 5.6's Journey and Shipment, which here are one thing."""
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
    """One bargain struck (spec 5.5)."""
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
    """The exclusive pool a cargo draws on, named by where it is going."""
    return f"{origin}>{destination}#cargo"


def capacity(kernel) -> dict[EntityId, int]:
    """Every crossing's tonnage this fortnight."""
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
    """Everywhere a route runs to from here, in season or not."""
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
    """The market as a person in it would describe it."""
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
    """Offer what you believe you can spare, at what you believe it is worth."""
    spare = (belief.value(home, "own_grain", 0)
             - belief.value(home, "need", 0) * KEEP_FORTNIGHTS)
    ask = belief.value(home, "price_grain", 0)
    if spare <= 0 or ask <= 0:
        return ()
    return (_quote(actor, belief.value(home, "turn", 0), home, GRAIN, spare, ask),)


def buy_shortfall(actor: EntityId, belief: B.Belief,
                  home: EntityId) -> tuple[Intent, ...]:
    """Buy what is standing in your own harbour, if you are short and can pay."""
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
    """A merchant house runs one line: buy at the cheapest end, sell at the dearest."""
    seat = home(belief)
    if not seat:
        return ()
    turn = belief.value(seat, "turn", 0)
    prices = {place: belief.value(place, "price_grain", 0)
              for place in _subjects(belief)
              if belief.value(place, "price_grain", 0) > 0}
    if len(prices) < 2:
        return ()

    # Ties by id, and stable: sorting first means `max` and `min` take the lowest-id place among.
    order = sorted(prices)
    dearest = max(order, key=lambda p: prices[p])
    cheapest = min(order, key=lambda p: prices[p])
    worth_it = (dearest != cheapest
                and prices[dearest] - prices[cheapest] > CROSSING_MARGIN)

    intents: list[Intent] = []
    for place in order:
        grain = belief.value(place, "own_grain", 0)
        copper = belief.value(place, "own_copper", 0)

        # Buy where it is cheapest, with the money standing there.
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
    """Where this actor is, out of its own belief rather than out of a table."""
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
    """Phase 8."""
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
    """Phase 9."""
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
                # Part of a lot sails and the rest stays on the quay: the two are in different.
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
    """The ordinary traffic, which carries word whether or not it carries cargo."""
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
                # Ordinals from a block of their own, clear of cargo voyages.
                id=mint(route_id, turn, "journey", DISPATCH + ordinal),
                route=route_id, carrier=origin, origin=origin,
                destination=destination, departed=turn,
                arrives=turn + route.fortnights(),
                news=tuple(sorted(readings(kernel, origin).items()))))
    return dataclasses.replace(kernel, voyages=tuple(voyages)), events


def _origin_of(resource: EntityId) -> EntityId:
    return resource.split(">", 1)[0] if ">" in resource else ""


# --- phase 2: arrivals --------------------------------------------------------

def arrivals(kernel):
    """Phase 2."""
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
            # A cargo lost is an event with a hole in the ledger behind it.
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
    """What the crews say when they come ashore (spec 5.8, 6.1 phase 2)."""
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
    """Fold identical lots together."""
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
