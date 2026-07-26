"""Routes, couriers, letters (spec 6.6). Graduated from systems.py (D1).

The load-bearing rule: routing is computed at dispatch, but closures are handled
in transit. A letter only *enters* a seasonal sea leg when the sea is open at the
node; caught by winter, it sits in the harbour and lands in the spring flood,
still dated the previous autumn. This one rule produces most of the game's best
moments for free, so it is modelled honestly, leg by leg.
"""
from __future__ import annotations

import dataclasses
import heapq

from engine import actions as A
from engine.core import stream
from engine.state import Letter, ProtocolRecord, World
from engine.systems import sea_open


# --- graph -------------------------------------------------------------------
def _adjacency(routes) -> dict[str, list]:
    adj: dict[str, list] = {}
    for r in routes:
        adj.setdefault(r.a, []).append((r.b, r.legs, r))
        adj.setdefault(r.b, []).append((r.a, r.legs, r))
    return adj


def shortest_path(routes, src: str, dst: str) -> tuple[str, ...]:
    """Fewest total legs, seasonality ignored (closures are handled in transit).
    Deterministic tie-break by node id keeps replay stable."""
    if src == dst:
        return (src,)
    adj = _adjacency(routes)
    dist = {src: 0}
    prev: dict[str, str] = {}
    pq = [(0, src)]
    while pq:
        d, node = heapq.heappop(pq)
        if node == dst:
            break
        if d > dist.get(node, 1 << 30):
            continue
        for nb, legs, _ in sorted(adj.get(node, []), key=lambda x: x[0]):
            nd = d + legs
            if nd < dist.get(nb, 1 << 30):
                dist[nb] = nd
                prev[nb] = node
                heapq.heappush(pq, (nd, nb))
    if dst not in dist:
        return ()
    out = [dst]
    while out[-1] != src:
        out.append(prev[out[-1]])
    return tuple(reversed(out))


def _route_between(routes, a: str, b: str):
    for r in routes:
        if (r.a == a and r.b == b) or (r.a == b and r.b == a):
            return r
    return None


# --- transit -----------------------------------------------------------------
def step_letters(world: World) -> tuple[World, list]:
    """Advance every in-transit letter one fortnight. Deliver those that finish."""
    fn = world.date.fortnight
    now = world.date.absolute
    still: list[Letter] = []
    delivered: list[Letter] = []
    events: list = []

    for L in world.letters_in_transit:
        edges = list(zip(L.path, L.path[1:]))
        if L.edge_index >= len(edges):            # already at destination
            delivered.append(dataclasses.replace(L, arrive_turn=now))
            continue
        a, b = edges[L.edge_index]
        r = _route_between(world.routes, a, b)
        blocked = (L.legs_into_edge == 0 and r is not None
                   and r.seasonal and r.mode == "sea"
                   and not sea_open(world.season, fn))
        if blocked:
            still.append(L)                        # waits at the harbour
            continue
        legs = r.legs if r else 1
        lie = L.legs_into_edge + 1
        if lie >= legs:                            # reached node b
            if L.edge_index + 1 >= len(edges):
                delivered.append(dataclasses.replace(
                    L, at_node=b, edge_index=L.edge_index + 1,
                    legs_into_edge=0, arrive_turn=now))
            else:
                still.append(dataclasses.replace(
                    L, at_node=b, edge_index=L.edge_index + 1, legs_into_edge=0))
        else:
            still.append(dataclasses.replace(L, legs_into_edge=lie))

    inbox = world.inbox
    for L in delivered:
        if L.outgoing:
            events.append(A.LetterDelivered(L.id, L.recipient, L.topic))
        else:
            inbox = inbox + (L,)                    # into the Stack
            events.append(A.LetterArrived(L.id, L.sender, L.topic))

    return dataclasses.replace(world, letters_in_transit=tuple(still),
                               inbox=inbox), events


# --- generation (A15): who writes this turn ----------------------------------
def _new_letter(world: World, seq: int, sender: str, origin: str, topic: str,
                facts: tuple, outgoing: bool = False, recipient: str | None = None) -> Letter:
    seat = world.court.seat
    if outgoing:
        src, dst = seat, origin      # replies go the other way; origin is the target place
    else:
        src, dst = origin, seat
    path = shortest_path(world.routes, src, dst) or (src, dst)
    return Letter(
        id=f"L{seq}", sender=sender,
        recipient=recipient or (sender if outgoing else world.court.actor),
        topic=topic, facts=facts, sent_turn=world.date.absolute,
        path=path, edge_index=0, legs_into_edge=0, at_node=src,
        outgoing=outgoing,
    )


def generate_incoming(world: World) -> tuple[World, list]:
    """A15: authored correspondents on cadence, plus a letter from any group
    whose arrears have made someone desperate (spec 6.3). Intents, not prose."""
    seq = world.letter_seq
    now = world.date.absolute
    transit = list(world.letters_in_transit)
    inbox = world.inbox
    events: list = []

    def emit(sender, origin, topic, facts):
        nonlocal seq, inbox
        seq += 1
        L = _new_letter(world, seq, sender, origin, topic, facts)
        if len(L.path) <= 1:                       # already at the seat
            inbox = inbox + (dataclasses.replace(L, arrive_turn=now),)
            events.append(A.LetterArrived(L.id, L.sender, L.topic))
        else:
            transit.append(L)

    for c in world.correspondents:
        if c.cadence > 0 and now - c.offset >= 0 and (now - c.offset) % c.cadence == 0:
            emit(c.actor, c.place, c.topic, c.facts)

    # A group deep in arrears: a named member writes. Sparse, offset by group.
    for gid in sorted(world.court.dependents):
        g = world.court.dependents[gid]
        weeks = g.arrears // max(1, g.size * g.entitlement)
        off = sum(ord(ch) for ch in gid) % 6      # stable; builtin hash() is randomized
        if weeks >= 2 and g.member_name and (now - off) % 6 == 0:
            emit(g.member_name, g.place, "arrears_complaint",
                 (("weeks", weeks), ("group", g.name)))

    return dataclasses.replace(world, letters_in_transit=tuple(transit),
                               inbox=inbox, letter_seq=seq), events


# --- dispatch (D1): the player's reply leaves the seat -----------------------
def dispatch_reply(world: World, target_actor: str, target_place: str,
                   topic: str, facts: tuple, profile: str = "",
                   protocol_total: int = 0,
                   protocol_violations: tuple[str, ...] = ()) -> tuple[World, list]:
    seq = world.letter_seq + 1
    L = _new_letter(world, seq, world.court.actor, target_place, topic, facts,
                    outgoing=True, recipient=target_actor)
    # Interception rolled once at dispatch against the riskiest leg on the path.
    risk = 0
    for a, b in zip(L.path, L.path[1:]):
        r = _route_between(world.routes, a, b)
        if r:
            risk = max(risk, r.risk)
    events: list = [A.LetterSent(L.id, target_actor, topic)]
    protocol_log = world.protocol_log
    if profile:
        protocol_log += (ProtocolRecord(
            L.id, target_actor, profile, protocol_total,
            tuple(protocol_violations)),)
    world = dataclasses.replace(world, letter_seq=seq, protocol_log=protocol_log)
    if risk and stream(world.seed, world.date.absolute, "letters.interception", L.id).chance(risk, 1000):
        # Diverted to someone else; the sender never learns (spec 6.6).
        return world, events + [A.LetterIntercepted(L.id)]
    return dataclasses.replace(world, letters_in_transit=world.letters_in_transit + (L,)), events
