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
from engine import report
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


def route_latency(routes, src: str, dst: str, season,
                  start_fortnight: int) -> int:
    """Travel time using the same seasonal-entry rule as letter transit."""
    path = shortest_path(routes, src, dst)
    if not path:
        return 1
    elapsed = 0
    for a, b in zip(path, path[1:]):
        route = _route_between(routes, a, b)
        legs = route.legs if route else 1
        progress = 0
        while progress < legs:
            elapsed += 1
            fortnight = (start_fortnight + elapsed - 1) % 24 + 1
            blocked = (
                progress == 0 and route is not None
                and route.seasonal and route.mode == "sea"
                and not sea_open(season, fortnight)
            )
            if not blocked:
                progress += 1
    return max(1, elapsed)


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

    world = dataclasses.replace(
        world, letters_in_transit=tuple(still), inbox=inbox)
    from engine import relations
    for letter in delivered:
        if letter.outgoing:
            world, applied = relations.deliver_protocol(world, letter)
            events += applied
    return world, events


# --- generation (A15): who writes this turn ----------------------------------
def _assert_facts(world: World, sender: str, facts: tuple,
                  exaggerate: tuple[str, ...],
                  understate: tuple[str, ...]) -> tuple[tuple, tuple]:
    """Return (asserted, true). The sender's bias is applied once, here, at the
    moment he writes -- so the tablet says the same wrong thing forever after,
    and a second source can contradict it."""
    relation = world.relations.get(sender)
    bias = relation.report_bias if relation is not None else 0
    if bias <= 0 or not (exaggerate or understate):
        return facts, ()
    asserted = report.assert_facts(
        facts, bias, exaggerate, understate,
        world.seed, world.date.absolute, sender)
    return asserted, (facts if asserted != facts else ())


def _new_letter(world: World, seq: int, sender: str, origin: str, topic: str,
                facts: tuple, outgoing: bool = False, recipient: str | None = None,
                protocol_profile: str = "", protocol_total: int = 0,
                protocol_violations: tuple[str, ...] = (),
                true_facts: tuple = (), summons_oath: str = "") -> Letter:
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
        outgoing=outgoing, true_facts=true_facts,
        protocol_profile=protocol_profile, protocol_total=protocol_total,
        protocol_violations=protocol_violations, summons_oath=summons_oath,
    )


def generate_incoming(world: World) -> tuple[World, list]:
    """A15: authored correspondents on cadence, plus a letter from any group
    whose arrears have made someone desperate (spec 6.3). Intents, not prose."""
    seq = world.letter_seq
    now = world.date.absolute
    transit = list(world.letters_in_transit)
    inbox = world.inbox
    events: list = []

    def emit(sender, origin, topic, facts, exaggerate=(), understate=(),
             summons_oath=""):
        nonlocal seq, inbox
        seq += 1
        asserted, true = _assert_facts(
            world, sender, facts, exaggerate, understate)
        L = _new_letter(world, seq, sender, origin, topic, asserted,
                        true_facts=true, summons_oath=summons_oath)
        if len(L.path) <= 1:                       # already at the seat
            inbox = inbox + (dataclasses.replace(L, arrive_turn=now),)
            events.append(A.LetterArrived(L.id, L.sender, L.topic))
        else:
            transit.append(L)

    for c in world.correspondents:
        relation = world.relations.get(c.actor)
        delayed = relation is not None and now < relation.reply_delay_until
        if (not delayed and c.cadence > 0 and now - c.offset >= 0
                and (now - c.offset) % c.cadence == 0):
            emit(c.actor, c.place, c.topic, c.facts, c.exaggerate,
                 c.understate, c.summons_oath)

    # A daughter married abroad (spec 6.10). She is a permanent asset who is
    # also an independent agent: she writes home with what the court she now
    # lives in is saying, which is intelligence available from no other source,
    # and she shades it toward her own position there. She is the best
    # correspondent in the game and she is not on your side.
    for person in sorted(world.court.house.values(), key=lambda p: p.id):
        if not (person.alive and person.married_to_court):
            continue
        offset = sum(ord(ch) for ch in person.id) % 5
        if (now - offset) % 5:
            continue
        relation = world.relations.get(person.married_to_court)
        if relation is None:
            continue
        emit(person.id, person.location, "daughter_abroad",
             (("court", person.married_to_court),
              ("regard", max(1, relation.esteem // 100)),
              ("their_debt", abs(relation.obligation) // 100)),
             exaggerate=("regard",), understate=("their_debt",))

    # Estate overseers (spec 6.4). The ruler cannot see his own fields; he gets
    # these. They inflate need and conceal failure, and their `report_bias`
    # (M7) is what turns that intent into numbers. This is the whole of the
    # player's information about the land besides the gauge and last year's
    # floor -- and it is written by men who want more hands sent to them.
    for estate in sorted(world.court.estates.values(), key=lambda e: e.id):
        overseer = f"overseer_{estate.id}"
        if overseer not in world.relations:
            continue
        offset = sum(ord(ch) for ch in estate.id) % 6
        if (now - offset) % 6:
            continue
        needed = estate.area_iku * estate.labour_days_per_iku
        short = max(0, needed - estate.labour_days_supplied)
        emit(overseer, estate.place, "estate_report",
             (("estate", estate.name), ("hands_short", short // 100),
              ("sown", estate.seed_sown // 100)),
             exaggerate=("hands_short",), understate=("sown",))

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


def inject_incoming(world: World, sender: str, origin: str, topic: str,
                    facts: tuple, exaggerate: tuple[str, ...] = (),
                    understate: tuple[str, ...] = ()) -> World:
    """Create an engine-decided incoming letter outside the cadence deck."""
    seq = world.letter_seq + 1
    asserted, true = _assert_facts(world, sender, facts, exaggerate, understate)
    letter = _new_letter(world, seq, sender, origin, topic, asserted,
                         true_facts=true)
    if len(letter.path) <= 1:
        letter = dataclasses.replace(letter, arrive_turn=world.date.absolute)
        return dataclasses.replace(
            world, inbox=world.inbox + (letter,), letter_seq=seq)
    return dataclasses.replace(
        world, letters_in_transit=world.letters_in_transit + (letter,),
        letter_seq=seq)


# --- dispatch (D1): the player's reply leaves the seat -----------------------
def dispatch_reply(world: World, target_actor: str, target_place: str,
                   topic: str, facts: tuple, profile: str = "",
                   protocol_total: int = 0,
                   protocol_violations: tuple[str, ...] = ()) -> tuple[World, list]:
    seq = world.letter_seq + 1
    L = _new_letter(world, seq, world.court.actor, target_place, topic, facts,
                    outgoing=True, recipient=target_actor,
                    protocol_profile=profile, protocol_total=protocol_total,
                    protocol_violations=protocol_violations)
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
