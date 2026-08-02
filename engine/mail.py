"""Routes, couriers, letters (spec 6.6). Graduated from systems.py (D1).

The load-bearing rule: routing is computed at dispatch, but closures are handled
in transit. A letter only *enters* a seasonal sea leg when the sea is open at the
node; caught by winter, it sits in the harbour and lands in the spring flood,
still dated the previous autumn. This one rule produces most of the game's best
moments for free, so it is modelled honestly, leg by leg.

Quarantine uses the same boundary rule.  A tablet is not disembodied
information: its courier waits outside a closed place (or inside one) until the
closure lifts.  Couriers also provide the first concrete journey/contact path
for disease; wider cargo and population journeys belong to M13.1.
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
def crossing(route) -> int:
    """Fortnights to cross a route. A letter edge is the whole route."""
    return max(1, route.fortnights())


def sea_entry(route) -> bool:
    """Whether entering this route means entering a seasonal sea leg.

    The rule is about the boundary, so it is the first leg that decides: a
    courier stopped by the winter is stopped before he sets out.
    """
    leg = route.legs[0] if route.legs else None
    return bool(leg and leg.season and leg.mode == "sea")


def _adjacency(routes) -> dict[str, list]:
    adj: dict[str, list] = {}
    for r in routes:
        a, b = r.ends
        adj.setdefault(a, []).append((b, crossing(r), r))
        adj.setdefault(b, []).append((a, crossing(r), r))
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
        if set(r.ends) == {a, b}:
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
        legs = crossing(route) if route else 1
        progress = 0
        while progress < legs:
            elapsed += 1
            fortnight = (start_fortnight + elapsed - 1) % 24 + 1
            blocked = (
                progress == 0 and route is not None
                and sea_entry(route)
                and not sea_open(season, fortnight)
            )
            if not blocked:
                progress += 1
    return max(1, elapsed)


# --- transit -----------------------------------------------------------------
def step_letters(world: World) -> tuple[World, list]:
    """Advance every in-transit letter one fortnight. Deliver those that finish."""
    from engine.plague import route_is_quarantined

    fn = world.date.fortnight
    now = world.date.absolute
    still: list[Letter] = []
    delivered: list[Letter] = []
    events: list = []
    infectious_arrivals = list(world.plague.infectious_arrivals)
    seen_ids: set[str] = set()

    for L in world.letters_in_transit:
        # A physical tablet has one identity. Old/replayed state containing the
        # same object twice must not dispatch or deliver it twice.
        if L.id in seen_ids:
            continue
        seen_ids.add(L.id)
        # The courier party shares the settlement it is leaving.  Once exposed
        # it remains a possible contact for this short journey; whether contact
        # actually establishes an outbreak is decided in engine.plague.
        current = world.places.get(L.at_node)
        if (not L.disease_exposed and current is not None
                and current.infected > 0):
            L = dataclasses.replace(L, disease_exposed=True)

        edges = list(zip(L.path, L.path[1:]))
        if L.edge_index >= len(edges):            # already at destination
            delivered.append(dataclasses.replace(L, arrive_turn=now))
            continue
        a, b = edges[L.edge_index]
        r = _route_between(world.routes, a, b)
        at_boundary = L.legs_into_edge == 0
        seasonal_block = (
            at_boundary and r is not None
            and sea_entry(r)
            and not sea_open(world.season, fn)
        )
        quarantine_block = (
            at_boundary
            and route_is_quarantined(world.court, a, b)
        )
        blocked = seasonal_block or quarantine_block
        if blocked:
            still.append(L)                        # waits at the boundary
            continue
        legs = crossing(r) if r else 1
        lie = L.legs_into_edge + 1
        if lie >= legs:                            # reached node b
            if L.disease_exposed:
                infectious_arrivals.append((L.id, b))
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

    plague = dataclasses.replace(
        world.plague,
        infectious_arrivals=tuple(sorted(infectious_arrivals)))
    world = dataclasses.replace(
        world, letters_in_transit=tuple(still), inbox=inbox, plague=plague)
    from engine import letter_terms
    for letter in delivered:
        if letter.outgoing and letter.terms:
            world, _term_results = letter_terms.apply_delivered_terms(
                world, letter)
    # The addressee now knows what the tablet says, and owes an answer. Claims
    # first, then the case: the decision that follows next turn must rest on
    # claims that already exist (engine/foreign_belief.py).
    from engine import foreign_belief
    for letter in delivered:
        if letter.outgoing:
            world, e = foreign_belief.receive(world, letter)
            events += e
    # A foreign court's answer carries terms of its own. They take effect where
    # they land, the same way ours do when they arrive abroad.
    for letter in delivered:
        if not letter.outgoing and letter.terms:
            world, e = letter_terms.apply_incoming_terms(world, letter)
            events += e
    from engine import relations
    recorded_protocol = {record.letter_id for record in world.protocol_log}
    for letter in delivered:
        # Structured DispatchLetter carries its profile but no legacy numeric
        # grade. Only the older path with a ProtocolRecord applies that score.
        if letter.outgoing and letter.id in recorded_protocol:
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


def _same_substance(letter: Letter, sender: str, topic: str,
                    facts: tuple) -> bool:
    """Whether an unanswered tablet already carries this actual matter.

    A biased correspondent may assert a different number every time the
    cadence comes round even when nothing in the world changed. Comparing the
    assertion would turn report noise into a flood. ``true_facts`` retains the
    state that caused a biased report; an honest report's asserted facts are
    already that state.

    Answered tablets are history rather than pending business, so a sender may
    write the same matter again after the court replies.
    """
    if (letter.outgoing or letter.sender != sender or letter.topic != topic
            or letter.answered_turn is not None):
        return False
    substance = letter.true_facts or letter.facts
    normalize = lambda rows: tuple(sorted(rows, key=lambda pair: pair[0]))
    return normalize(substance) == normalize(facts)


ESCALATION_INTERVAL = 12


def _matter_pending(inbox, transit, sender: str, topic: str,
                    facts: tuple, now: int) -> bool:
    """True when another copy would add no timely decision.

    Both arrived and travelling tablets count. Otherwise a three-fortnight
    cadence can put several copies on the same winter sea lane before the
    first one reaches court. A changed report may escalate, but not more than
    twice a year while the court has left the matter unanswered; smaller
    changes accumulate into the next report instead of becoming separate rows.
    """
    pending = [
        letter for letter in tuple(inbox) + tuple(transit)
        if not letter.outgoing and letter.sender == sender
        and letter.topic == topic and letter.answered_turn is None
    ]
    if not pending:
        return False
    if any(_same_substance(letter, sender, topic, facts)
           for letter in pending):
        return True
    latest = max(letter.sent_turn for letter in pending)
    return now - latest < ESCALATION_INTERVAL


def generate_incoming(world: World) -> tuple[World, list]:
    """A15: actors write when their scheduled account has new substance.

    Cadence says when a correspondent is able or expected to report. It no
    longer manufactures another active tablet when an unanswered or travelling
    copy already says the same thing. A changed quantity, condition, deadline,
    or request remains a new matter and may produce an escalation.

    Group arrears still put a named person at the writing board (spec 6.3).
    These are intents, not prose.
    """
    seq = world.letter_seq
    now = world.date.absolute
    transit = list(world.letters_in_transit)
    inbox = world.inbox
    events: list = []

    def emit(sender, origin, topic, facts, exaggerate=(), understate=(),
             summons_oath=""):
        nonlocal seq, inbox
        if _matter_pending(inbox, transit, sender, topic, facts, now):
            return
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
        if c.place not in world.places:
            continue
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

    # C4: the overseer letters read the court's estates, which are the
    # kernel's ground now. They return when the belief re-points at C5.

    # A group deep in arrears: a named member writes. Sparse, offset by group.
    from engine import seat
    for gid, g in sorted(seat.groups(world).items()):
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
def _recipient_place(world: World, recipient: str) -> str:
    relation = world.relations.get(recipient)
    if relation is not None:
        return relation.place
    correspondent = next(
        (item for item in world.correspondents if item.actor == recipient),
        None)
    if correspondent is None:
        raise ValueError(f"unknown correspondent: {recipient}")
    return correspondent.place


def _validate_dispatch(world: World, action: A.DispatchLetter) -> Letter | None:
    """Validate the whole dispatch without changing any World field."""
    if not action.text.strip():
        raise ValueError("dispatch text must not be blank")
    destination = _recipient_place(world, action.recipient)
    if destination not in world.places:
        raise ValueError(f"the Alu at {destination} has fallen")
    path = tuple(action.path)
    if not path or path[0] != world.court.seat:
        raise ValueError(
            f"dispatch path must begin at court seat {world.court.seat}")
    if path[-1] != destination:
        raise ValueError(
            f"dispatch path must end at recipient place {destination}")
    for a, b in zip(path, path[1:]):
        if _route_between(world.routes, a, b) is None:
            raise ValueError(f"dispatch path has no route edge: {a} -> {b}")

    reply = None
    if action.reply_to:
        reply = next(
            (letter for letter in world.inbox
             if letter.id == action.reply_to),
            None)
        if reply is None:
            raise ValueError(f"no such reply tablet: {action.reply_to}")
        if reply.sender != action.recipient:
            raise ValueError(
                "reply recipient does not match the referenced tablet")
        if reply.answered_turn is not None:
            raise ValueError(f"tablet already answered: {action.reply_to}")
    return reply


def apply_dispatch(world: World,
                   action: A.DispatchLetter) -> tuple[World, list]:
    """Seal one exact outgoing tablet and put its courier on the chosen path.

    This is transactional over immutable World state: recipient, reply and
    every route hop are checked before a Letter is constructed; the referenced
    incoming tablet is marked answered only after construction succeeds.
    """
    reply = _validate_dispatch(world, action)
    seq = world.letter_seq + 1
    letter_id = f"L{seq}"
    existing_ids = {
        letter.id
        for letter in world.inbox + world.letters_in_transit
    }
    archived_ids = {
        document.ref[2:]
        for document in world.documents
        if document.ref.startswith("L-")
    }
    recorded_ids = {record.letter_id for record in world.protocol_log}
    if letter_id in existing_ids | archived_ids | recorded_ids:
        raise ValueError(f"duplicate letter id: {letter_id}")

    letter = Letter(
        id=letter_id,
        sender=world.court.actor,
        recipient=action.recipient,
        topic="reply",
        facts=(),
        sent_turn=world.date.absolute,
        path=tuple(action.path),
        edge_index=0,
        legs_into_edge=0,
        at_node=action.path[0],
        outgoing=True,
        text=action.text,
        terms=tuple(action.terms),
        reply_to=action.reply_to,
        scribe_id=action.scribe_id,
        seal=action.seal,
        courier_id=action.courier_id,
        protocol_profile=action.profile,
    )

    # Terms cross the same atomic seal boundary as the exact prose. Gifts are
    # reserved once here; promises become records rather than goods.
    from engine import letter_terms
    reserved = letter_terms.reserve_terms_at_dispatch(world, letter)
    world = reserved.world

    inbox = world.inbox
    if reply is not None:
        inbox = tuple(
            dataclasses.replace(
                item, answered_turn=world.date.absolute)
            if item.id == reply.id else item
            for item in inbox
        )
    world = dataclasses.replace(
        world, inbox=inbox, letter_seq=seq)

    # The court's sealed copy persists even if the courier is intercepted.
    from engine import archive
    world = archive.file_letter(world, letter)

    journey = sum(
        (crossing(_route_between(world.routes, a, b))
         for a, b in zip(letter.path, letter.path[1:])),
        start=0,
    )
    events: list = [A.LetterSent(
        letter.id, action.recipient, letter.topic)]
    events.extend(
        A.GiftSent(
            reservation.id,
            action.recipient,
            reservation.good,
            reservation.quantity,
            reservation.quantity * world.gift_values[reservation.good],
            world.date.absolute + max(1, journey),
        )
        for reservation in reserved.reservations
    )
    risk = max(
        (_route_between(world.routes, a, b).risk
         for a, b in zip(letter.path, letter.path[1:])),
        default=0,
    )
    intercepted = (
        risk > 0
        and stream(
            world.seed, world.date.absolute,
            "letters.interception", letter.id,
        ).chance(risk, 1000)
    )
    if intercepted:
        world = letter_terms.mark_intercepted_terms(world, letter)
        return world, events + [A.LetterIntercepted(letter.id)]
    return dataclasses.replace(
        world,
        letters_in_transit=world.letters_in_transit + (letter,),
    ), events


def foreign_reply(world: World, case, decision) -> tuple[World, Letter, list]:
    """A foreign court's answer starts its journey to the seat.

    The engine writes facts, never prose: `decision`, the terms offered back,
    and the tablet being answered. The language layer voices those facts on
    demand and its accepted words are stored, so replay reads text rather than
    asking a model for it again (spec 2.6, 2.7).

    A reply is an ordinary incoming tablet. It crosses the same routes, waits
    out the same closed sea, and can be intercepted -- in which case the court
    waits for an answer that no longer exists.
    """
    seq = world.letter_seq + 1
    facts: tuple[tuple[str, object], ...] = (("decision", decision.kind),)
    for index, term in enumerate(decision.terms):
        facts += (
            (f"term{index}_kind", term.kind),
            (f"term{index}_good", term.good),
            (f"term{index}_quantity", term.quantity),
            (f"term{index}_due_turn", term.due_turn),
        )
    letter = _new_letter(
        world, seq, case.actor, case.place, f"reply_{decision.kind}", facts)
    letter = dataclasses.replace(
        letter, terms=tuple(decision.terms), reply_to=case.letter_id)
    world = dataclasses.replace(world, letter_seq=seq)

    events: list = [A.LetterSent(letter.id, world.court.actor, letter.topic)]
    risk = max(
        (route.risk for route in
         (_route_between(world.routes, a, b)
          for a, b in zip(letter.path, letter.path[1:]))
         if route is not None),
        default=0,
    )
    if risk and stream(world.seed, world.date.absolute,
                       "letters.interception", letter.id).chance(risk, 1000):
        return world, letter, events + [A.LetterIntercepted(letter.id)]
    return dataclasses.replace(
        world, letters_in_transit=world.letters_in_transit + (letter,),
    ), letter, events


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
