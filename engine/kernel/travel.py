"""Journeys over kernel routes: the same distance the letters already have.

The rule this module holds is `engine.mail`'s rule, restated over
`engine.entity.Route` and its named legs: a journey is routed once, at
departure, and every closure it meets afterwards is met at a leg boundary. It
is never rerouted around a shut sea and never teleported past one. A courier
caught by winter sits in the harbour and lands in the spring, still carrying an
autumn tablet.

Two things make this module worth writing rather than reusing.

The court's route, retired in C5, was one hop with a leg count, a mode, and a
boolean that meant "the sailing window applies". The kernel's is a named chain:
each `Leg` says which span it is open in, so a route may be a road that runs all
year to a harbour and a crossing that shuts, and the journey stops at the quay
rather than at the far shore. Nothing in the court's shape can say that.

And a kernel route has a capacity the court's does not. Capacity is contested,
so it is not settled here by whoever asks first: claims go to
`engine.kernel.resolve`, the one allocator, and come back as grants that name
what each journey asked, got, and went short (spec 5.2, 5.6).

Parity with `engine.mail` is the deliverable. `shortest_path` and `latency`
below reproduce that module's answers -- including its tie-breaking -- so the
migration sequenced after this one cannot silently reroute a courier. Where the
two deliberately differ, the difference is named in the function's docstring and
is always the kernel refusing something the court guessed at:

    an unreachable destination raises rather than costing one fortnight;
    a leg that is open in no fortnight of the year raises rather than
    spinning forever in the court's progress loop.

Integers, `sorted()` over every mapping, and no draw outside
`engine.core.stream`.
"""
from __future__ import annotations

import dataclasses
import heapq
from collections.abc import Mapping

from engine.core import stream
from engine.entity import EntityId, Leg, Route
from engine.kernel import farm as F
from engine.kernel import resolve as R
from engine.kernel.intent import Intent

FAR = 1 << 30          # farther than any authored network; never arithmetic
YEAR = 24              # fortnights; the whole of a season's period


class NoRoute(ValueError):
    """Nowhere to go by. Refused at departure rather than guessed at."""


class Impassable(ValueError):
    """A leg open in no fortnight of the year. Content fault, not weather."""


class ClaimError(ValueError):
    """A claim on capacity that cannot be priced or attributed."""


# --- the graph ----------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Edge:
    """One leg, in the direction a journey would take it.

    A leg is authored one way round and travelled either way: a sea crossing is
    not one-way, and authoring the return would be bookkeeping rather than
    modelling (the same argument `engine.kernel.carry.capacity` makes about
    tonnage). `route` and `index` are kept so a step can find the risk and the
    capacity that belong to the leg, and so the inspector can name the leg the
    journey is actually on.
    """
    origin: EntityId
    destination: EntityId
    fortnights: int
    mode: str
    season: str
    route: EntityId
    index: int

    def turned(self) -> "Edge":
        return dataclasses.replace(
            self, origin=self.destination, destination=self.origin)


def _edge(route: Route, index: int, leg: Leg) -> Edge:
    return Edge(
        origin=leg.origin, destination=leg.destination,
        # A leg the author left at zero still takes a fortnight to cross. The
        # court's transit loop advances one leg per fortnight regardless of the
        # count, so treating zero as free here would put the two halves a
        # fortnight apart on the same journey.
        fortnights=max(1, leg.fortnights), mode=leg.mode, season=leg.season,
        route=route.id, index=index)


def edges(routes: Mapping[EntityId, Route]) -> tuple[Edge, ...]:
    """Every leg of every route, both ways, in a stable order."""
    found: list[Edge] = []
    for route_id in sorted(routes):
        for index, leg in enumerate(routes[route_id].legs):
            forward = _edge(routes[route_id], index, leg)
            found.append(forward)
            found.append(forward.turned())
    return tuple(found)


def adjacency(routes: Mapping[EntityId, Route]) -> dict[EntityId, tuple[Edge, ...]]:
    """Legs out of each node, sorted by where they go.

    Sorted by destination first because that is the order `engine.mail` walks
    its neighbours in, and the order neighbours are offered in is what decides
    which of two equally short paths is taken. The remaining sort keys only
    order parallel legs between the same pair, which cannot change the answer:
    both legs propose the same predecessor.
    """
    out: dict[EntityId, list[Edge]] = {}
    for edge in edges(routes):
        out.setdefault(edge.origin, []).append(edge)
    return {
        node: tuple(sorted(
            out[node],
            key=lambda e: (e.destination, e.fortnights, e.route, e.index)))
        for node in sorted(out)
    }


def shortest_path(routes: Mapping[EntityId, Route], src: EntityId,
                  dst: EntityId) -> tuple[EntityId, ...]:
    """Fewest total fortnights, seasons ignored; `()` when there is no way.

    Seasons are ignored on purpose, and it is the same purpose as in
    `engine.mail.shortest_path`: closures are handled in transit, so a shut sea
    in the winter must not quietly become a longer road in the summer's plan.

    This is the court's Dijkstra, edge for edge: the same `(distance, node)`
    heap key, neighbours in destination order, and a predecessor recorded only
    on a strict improvement. Reproducing the tie-break is the point -- two
    paths of equal length are a routine thing in an authored network, and the
    migration may not pick the other one.
    """
    if src == dst:
        return (src,)
    adj = adjacency(routes)
    distance = {src: 0}
    previous: dict[EntityId, EntityId] = {}
    frontier = [(0, src)]
    while frontier:
        so_far, node = heapq.heappop(frontier)
        if node == dst:
            break
        if so_far > distance.get(node, FAR):
            continue
        for edge in adj.get(node, ()):
            through = so_far + edge.fortnights
            if through < distance.get(edge.destination, FAR):
                distance[edge.destination] = through
                previous[edge.destination] = node
                heapq.heappush(frontier, (through, edge.destination))
    if dst not in distance:
        return ()
    walk = [dst]
    while walk[-1] != src:
        walk.append(previous[walk[-1]])
    return tuple(reversed(walk))


def edge_between(routes: Mapping[EntityId, Route], a: EntityId,
                 b: EntityId) -> Edge | None:
    """The leg a journey from `a` to `b` would use, or None.

    The shortest of them, then the lowest route id, then the earliest leg --
    which is the leg the pathfinder above actually improved the distance with.
    `engine.mail._route_between` instead takes the first hop authored between
    the pair, so the two disagree only where a network holds two legs between
    one pair with *different* lengths, and there the court's own path and
    latency already disagree with each other. `faults` reports that shape.
    """
    candidates = [edge for edge in edges(routes)
                  if edge.origin == a and edge.destination == b]
    if not candidates:
        return None
    return sorted(candidates,
                  key=lambda e: (e.fortnights, e.route, e.index))[0]


def faults(routes: Mapping[EntityId, Route]) -> tuple[str, ...]:
    """Route shapes that would make a journey unexplainable. Sentences."""
    found: list[str] = []
    lengths: dict[tuple[EntityId, EntityId], set[int]] = {}
    for route_id in sorted(routes):
        route = routes[route_id]
        if not route.legs:
            found.append(f"{route_id}: a route with no legs carries nothing")
        if route.capacity < 0:
            found.append(f"{route_id}: negative capacity")
        if route.risk < 0 or route.risk > 1000:
            found.append(f"{route_id}: risk {route.risk} is not scaled 1000")
        for index, leg in enumerate(route.legs):
            if leg.fortnights < 1:
                found.append(
                    f"{route_id}: leg {index} crosses in {leg.fortnights} "
                    "fortnights, and nothing crosses in none")
            if leg.origin == leg.destination:
                found.append(
                    f"{route_id}: leg {index} leaves from where it arrives")
            pair = tuple(sorted((leg.origin, leg.destination)))
            lengths.setdefault(pair, set()).add(max(1, leg.fortnights))
    for pair in sorted(lengths):
        if len(lengths[pair]) > 1:
            found.append(
                f"{pair[0]}--{pair[1]}: legs of {sorted(lengths[pair])} "
                "fortnights between one pair; the court's latency would take "
                "the first authored and its path the shortest")
    return tuple(found)


# --- what the world is doing to the journey -----------------------------------

@dataclasses.dataclass(frozen=True)
class Conditions:
    """Everything outside the journey that can stop it this fortnight.

    Quarantine is a court fact today and becomes a World layer over settlements
    (Phase C, places row), so it arrives here as the closed places rather than
    being read out of somebody's state. That also keeps this module honest: it
    knows what is shut, not who shut it.
    """
    fortnight: int
    seasons: Mapping[str, tuple[int, ...]] = dataclasses.field(
        default_factory=dict)
    quarantined: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.fortnight <= YEAR:
            raise ValueError(f"fortnight {self.fortnight} is not in the year")

    def at(self, fortnight: int) -> "Conditions":
        return dataclasses.replace(self, fortnight=fortnight)

    def closed(self, place: EntityId) -> bool:
        return place in self.quarantined


def conditions_of(kernel, quarantined: tuple[EntityId, ...] = ()) -> Conditions:
    """This fortnight's conditions, read off a kernel. No import of one."""
    return Conditions(
        fortnight=kernel.date.fortnight, seasons=kernel.seasons,
        quarantined=tuple(sorted(quarantined)))


def leg_open(edge: Edge, conditions: Conditions) -> bool:
    """Whether this leg may be entered at all in this fortnight.

    The authored span decides, not the mode. The court asks whether a hop is
    `seasonal` and by sea; the kernel's leg says which span it is open in, so a
    river that freezes and a pass that snows need no new flag -- and a leg with
    no span named is open all year. The predicate itself is
    `engine.kernel.farm.season`, because one definition of an authored span is
    the point of authoring it.
    """
    if not edge.season:
        return True
    return F.season(conditions.seasons, conditions.fortnight, edge.season)


def ever_open(edge: Edge, conditions: Conditions) -> bool:
    """Whether any fortnight of the year opens this leg."""
    return any(leg_open(edge, conditions.at(fortnight))
               for fortnight in range(1, YEAR + 1))


def held_by(edge: Edge, conditions: Conditions) -> str:
    """Why this leg may not be entered now: "sea", "quarantine", or "".

    Both tests are made at the boundary and nowhere else, which is the rule the
    whole module exists to keep. Quarantine takes either end, exactly as
    `engine.plague.route_is_quarantined` does: a courier waits outside a closed
    place or inside one, and a tablet is not disembodied information.
    """
    if not leg_open(edge, conditions):
        return "sea"
    if conditions.closed(edge.origin) or conditions.closed(edge.destination):
        return "quarantine"
    return ""


def latency(routes: Mapping[EntityId, Route], src: EntityId, dst: EntityId,
            seasons: Mapping[str, tuple[int, ...]],
            start_fortnight: int) -> int:
    """Fortnights from `src` to `dst`, with the seasonal-entry rule applied.

    Agrees with `engine.mail.route_latency` fortnight for fortnight on the same
    network: time passes whether or not the journey moves, and a shut leg is
    only refused at its boundary, so a journey already at sea finishes the
    crossing it started.

    Two refusals the court does not make. An unreachable destination raises
    instead of costing one fortnight, because a quoted latency of one to a place
    with no road is a number a room would print. A leg open in no fortnight
    raises instead of looping forever, which is what the court's progress loop
    does with an unauthored span.
    """
    path = shortest_path(routes, src, dst)
    if not path:
        raise NoRoute(f"no route from {src} to {dst}")
    # The fortnight is only ever read through `at`, so the base one is a
    # carrier. Wrapped into the year the way the loop below wraps it, rather
    # than trusted, because a caller may hold an absolute turn count.
    conditions = Conditions(
        fortnight=(start_fortnight - 1) % YEAR + 1, seasons=seasons)
    elapsed = 0
    for a, b in zip(path, path[1:]):
        edge = edge_between(routes, a, b)
        if edge is None:                       # unreachable: the path lied
            raise NoRoute(f"no leg from {a} to {b}")
        if not ever_open(edge, conditions):
            raise Impassable(
                f"{edge.route} leg {edge.index} is open in no fortnight")
        crossed = 0
        while crossed < edge.fortnights:
            elapsed += 1
            fortnight = (start_fortnight + elapsed - 1) % YEAR + 1
            at_boundary = crossed == 0
            if at_boundary and not leg_open(edge, conditions.at(fortnight)):
                continue                        # waits in the harbour
            crossed += 1
    return max(1, elapsed)


# --- the journey itself -------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Journey:
    """People or cargo between two places, and neither of them yet.

    The same four fields the court's `Letter` carries its transit in -- the
    path, which leg of it, how far into that leg, and the node last stood in --
    because that is what makes a closure meetable at a boundary. What it adds
    is a load: a journey may carry lots, people, or nothing, and the court's
    courier could only ever carry one tablet.

    `engine.kernel.carry.Voyage` is the same idea for a crossing that is
    already at sea with a landing turn fixed at departure. This is the
    leg-by-leg form, and the two meet when M13.4 wants a journey without a
    shipment.
    """
    id: EntityId
    actor: EntityId
    path: tuple[EntityId, ...]
    departed: int
    at_node: EntityId
    edge_index: int = 0
    fortnights_into_edge: int = 0
    load: int = 0                        # units of cargo; 0 = a party alone
    cargo: tuple[EntityId, ...] = ()     # lot ids
    people: int = 0
    held: str = ""                       # why it did not move last fortnight

    @property
    def origin(self) -> EntityId:
        return self.path[0] if self.path else ""

    @property
    def destination(self) -> EntityId:
        return self.path[-1] if self.path else ""

    @property
    def arrived(self) -> bool:
        return self.edge_index >= max(0, len(self.path) - 1)


def begin(routes: Mapping[EntityId, Route], journey_id: EntityId,
          actor: EntityId, origin: EntityId, destination: EntityId,
          turn: int, load: int = 0, cargo: tuple[EntityId, ...] = (),
          people: int = 0) -> Journey:
    """Route a journey at departure, or refuse to start it.

    Refused rather than guessed: a destination with no way to it is a decision
    somebody made from a belief that was wrong, and the honest answer is that
    the party never left. Silently walking to the nearest reachable place would
    put goods somewhere nobody sent them.
    """
    path = shortest_path(routes, origin, destination)
    if not path:
        raise NoRoute(f"no route from {origin} to {destination}")
    return Journey(
        id=journey_id, actor=actor, path=path, departed=turn, at_node=origin,
        load=load, cargo=tuple(cargo), people=people)


def current_edge(routes: Mapping[EntityId, Route],
                 journey: Journey) -> Edge | None:
    """The leg the journey is on or about to enter; None once it has arrived."""
    if journey.arrived:
        return None
    a = journey.path[journey.edge_index]
    b = journey.path[journey.edge_index + 1]
    return edge_between(routes, a, b)


def step(routes: Mapping[EntityId, Route], journey: Journey,
         conditions: Conditions) -> Journey:
    """One fortnight of one journey. Held journeys stay where they stand.

    The boundary rule in three lines: a journey between nodes is committed and
    crosses; a journey at a node may be refused; a refused journey does not
    lose its place in the path, so the fortnight the closure lifts it goes on
    from the quay rather than starting again.
    """
    if journey.arrived:
        return dataclasses.replace(journey, held="")
    edge = current_edge(routes, journey)
    if edge is None:
        raise NoRoute(
            f"{journey.id}: no leg from {journey.path[journey.edge_index]}")
    if journey.fortnights_into_edge == 0:
        held = held_by(edge, conditions)
        if held:
            return dataclasses.replace(journey, held=held)
    crossed = journey.fortnights_into_edge + 1
    if crossed < edge.fortnights:
        return dataclasses.replace(
            journey, fortnights_into_edge=crossed, held="")
    return dataclasses.replace(
        journey, at_node=edge.destination, edge_index=journey.edge_index + 1,
        fortnights_into_edge=0, held="")


def advance(routes: Mapping[EntityId, Route], journeys: tuple[Journey, ...],
            conditions: Conditions) -> tuple[Journey, ...]:
    """Every journey, one fortnight, in a stable order.

    Sorted by id although nothing here reads another journey's result: the
    order journeys are reported in is the order a room lists them, and it may
    not depend on the order a phase happened to append them.
    """
    return tuple(step(routes, journey, conditions)
                 for journey in sorted(journeys, key=lambda j: j.id))


def intercepted(routes: Mapping[EntityId, Route], journey: Journey,
                seed: int, turn: int) -> bool:
    """Whether this leg takes the journey. Drawn once, as it is entered.

    Per leg rather than once per journey against the worst leg on the path,
    which is what the court does at dispatch. A four-leg road is four chances
    to be robbed, and the court's shape cannot say so; keeping the draw at the
    boundary also means a journey that waited out a winter is not exposed twice
    for the waiting.

    The key names the journey, the route, and the leg, so adding a leg to one
    route cannot change what happened on another (spec 2.6). The draw is
    `kernel.voyage`, the registered domain for whether a crossing arrives; a
    `kernel.travel` domain of its own is the honest answer and is a change to
    `engine.core.DOMAINS`, so the key is namespaced until that lands.
    """
    edge = current_edge(routes, journey)
    if edge is None or journey.fortnights_into_edge != 0:
        return False
    risk = routes[edge.route].risk
    if risk <= 0:
        return False
    key = f"travel|{journey.id}|{edge.route}|{edge.index}"
    return stream(seed, turn, "kernel.voyage", key).chance(risk, 1000)


# --- contested capacity (spec 5.2) --------------------------------------------

def pool(route_id: EntityId) -> EntityId:
    """The exclusive pool a route's traffic draws on, named by the route.

    By route rather than by pair of places, unlike `engine.kernel.carry.pool`:
    there the actor decides to send grain to Alashiya and the world answers with
    a hull, so the pool is the destination. Here the journey is already routed,
    and what is finite is this road in this fortnight -- every leg of it draws
    on the one capacity, because a road's carrying trade is the road's.
    """
    return f"{route_id}#travel"


@dataclasses.dataclass(frozen=True)
class Claim:
    """One journey's demand on one route's capacity, before it is settled."""
    id: str
    actor: EntityId
    route: EntityId
    quantity: int
    priority: int = 0
    authority: EntityId = ""

    def __post_init__(self) -> None:
        if not self.actor:
            raise ClaimError(f"{self.id}: a claim belongs to an actor")
        if self.quantity <= 0:
            raise ClaimError(
                f"{self.id}: a claim on a route must say how much")


def route_open(route: Route, conditions: Conditions) -> bool:
    """Whether the whole route may be used now. One shut leg shuts the route.

    The same reading `engine.kernel.carry.sea_open` takes of a crossing, and it
    is about capacity rather than about a journey: a fortnight in which no hull
    can leave the quay offers no tonnage, even though a journey already at sea
    on the far leg is still crossing.
    """
    return all(
        not held_by(_edge(route, index, leg), conditions)
        for index, leg in enumerate(route.legs))


def capacity(routes: Mapping[EntityId, Route], conditions: Conditions,
             claims: tuple[Claim, ...] = ()) -> dict[EntityId, int]:
    """Tonnage per pool this fortnight. Shut routes offer none.

    A route authored with capacity zero is unmodelled rather than impassable
    (`engine.entity.Route`: "0 = unmodelled"), so it rations nothing and its
    pool is opened to everything asked of it. Writing zero there would ration
    the whole network to a standstill the first time a content author left the
    field out, which is a silent famine rather than a fault.
    """
    asked: dict[EntityId, int] = {}
    for claim in claims:
        key = pool(claim.route)
        asked[key] = asked.get(key, 0) + claim.quantity
    space: dict[EntityId, int] = {}
    for route_id in sorted(routes):
        route = routes[route_id]
        key = pool(route_id)
        if not route.legs or not route_open(route, conditions):
            space[key] = 0
        elif route.capacity == 0:
            space[key] = asked.get(key, 0)
        else:
            space[key] = route.capacity
    return space


def demands(claims: tuple[Claim, ...], turn: int) -> tuple[Intent, ...]:
    """Claims as intents, so the one allocator can settle them.

    Nothing is decided here. The point of going through `engine.kernel.resolve`
    rather than serving a list is spec 5.2: scarce capacity is allocated
    globally, not first-come by iteration order, and the result is a grant per
    claimant that says who went without.
    """
    return tuple(
        Intent(
            id=claim.id, actor=claim.actor, kind="travel", turn=turn,
            subject=claim.route, quantity=claim.quantity,
            resource=pool(claim.route), authority=claim.authority,
            priority=claim.priority)
        for claim in sorted(claims, key=lambda c: c.id))


def allocate(routes: Mapping[EntityId, Route], claims: tuple[Claim, ...],
             conditions: Conditions, turn: int,
             authority_rank=lambda intent: 0) -> R.Allocation:
    """Settle every claim on every route at once.

    Order-independent by construction: the intents are sorted by id before the
    allocator sees them, and the allocator sorts them again by priority, then
    authority rank, then actor, then id. Offering the same claims in a
    different order returns the same grants.
    """
    for claim in sorted(claims, key=lambda c: c.id):
        if claim.route not in routes:
            raise NoRoute(f"{claim.id}: claims {claim.route!r}, which is no route")
    return R.allocate(
        demands(claims, turn), capacity(routes, conditions, tuple(claims)),
        authority_rank)


def explain(allocation: R.Allocation) -> tuple[str, ...]:
    """Why each journey got what it got, as sentences.

    The record spec 3.1 asks for: what was absent, what competed for it, and
    who went without. Reported in the order the allocator decided, which is the
    order the shortfall happened in.
    """
    said: list[str] = []
    for grant in allocation.grants:
        if grant.met:
            said.append(
                f"{grant.intent}: {grant.actor} carries {grant.granted} "
                f"on {grant.resource}")
        else:
            said.append(
                f"{grant.intent}: {grant.actor} asked {grant.asked} of "
                f"{grant.resource} and carries {grant.granted}, "
                f"{grant.short} left behind")
    for resource in sorted(allocation.remaining):
        if allocation.remaining[resource]:
            said.append(
                f"{resource}: {allocation.remaining[resource]} unused")
    return tuple(said)
