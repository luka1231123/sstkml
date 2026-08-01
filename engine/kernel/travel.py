"""Journeys over kernel routes: the same distance the letters already have."""
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
    """One leg, in the direction a journey would take it."""
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
        # A leg the author left at zero still takes a fortnight to cross.
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
    """Legs out of each node, sorted by where they go."""
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
    """Fewest total fortnights, seasons ignored; `()` when there is no way."""
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
    """The leg a journey from `a` to `b` would use, or None."""
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
    """Everything outside the journey that can stop it this fortnight."""
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


def leg_open(edge: Edge, conditions: Conditions) -> bool:
    """Whether this leg may be entered at all in this fortnight."""
    if not edge.season:
        return True
    return F.season(conditions.seasons, conditions.fortnight, edge.season)


def ever_open(edge: Edge, conditions: Conditions) -> bool:
    """Whether any fortnight of the year opens this leg."""
    return any(leg_open(edge, conditions.at(fortnight))
               for fortnight in range(1, YEAR + 1))


def held_by(edge: Edge, conditions: Conditions) -> str:
    """Why this leg may not be entered now: "sea", "quarantine", or ""."""
    if not leg_open(edge, conditions):
        return "sea"
    if conditions.closed(edge.origin) or conditions.closed(edge.destination):
        return "quarantine"
    return ""


def latency(routes: Mapping[EntityId, Route], src: EntityId, dst: EntityId,
            seasons: Mapping[str, tuple[int, ...]],
            start_fortnight: int) -> int:
    """Fortnights from `src` to `dst`, with the seasonal-entry rule applied."""
    path = shortest_path(routes, src, dst)
    if not path:
        raise NoRoute(f"no route from {src} to {dst}")
    # The fortnight is only ever read through `at`, so the base one is a carrier.
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
    """People or cargo between two places, and neither of them yet."""
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
    """Route a journey at departure, or refuse to start it."""
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
    """One fortnight of one journey."""
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
    """Every journey, one fortnight, in a stable order."""
    return tuple(step(routes, journey, conditions)
                 for journey in sorted(journeys, key=lambda j: j.id))


def intercepted(routes: Mapping[EntityId, Route], journey: Journey,
                seed: int, turn: int) -> bool:
    """Whether this leg takes the journey."""
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
    """The exclusive pool a route's traffic draws on, named by the route."""
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
    """Whether the whole route may be used now."""
    return all(
        not held_by(_edge(route, index, leg), conditions)
        for index, leg in enumerate(route.legs))


def capacity(routes: Mapping[EntityId, Route], conditions: Conditions,
             claims: tuple[Claim, ...] = ()) -> dict[EntityId, int]:
    """Tonnage per pool this fortnight."""
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
    """Claims as intents, so the one allocator can settle them."""
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
    """Settle every claim on every route at once."""
    for claim in sorted(claims, key=lambda c: c.id):
        if claim.route not in routes:
            raise NoRoute(f"{claim.id}: claims {claim.route!r}, which is no route")
    return R.allocate(
        demands(claims, turn), capacity(routes, conditions, tuple(claims)),
        authority_rank)


def explain(allocation: R.Allocation) -> tuple[str, ...]:
    """Why each journey got what it got, as sentences."""
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
