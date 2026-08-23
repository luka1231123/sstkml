"""World -> Belief for one ruler (spec 4.1).

The TUI and the AI layer read ONLY what this returns, and it returns plain
dicts of primitives -- no World object is reachable from the result. In M1 the
player's own court is nearly truth (even so, counts pass through a scribe in
M3). Belief for the wider world arrives as Claims later.
"""
from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

from belief.distortion import p_error, transcribe
from engine import seat as seat_door
from engine.state import marks, lines
from engine.systems import attention_available, sea_open

_MONTHS = tomllib.loads((Path(__file__).parent.parent / "content" / "months.toml").read_text())

# Ledger name -> the true stock it counts. Inspecting one bypasses the scribe.
_LEDGERS = {"granary": "grain", "seed": "seed_grain"}


def date_label(chosen_alu: str, year: int, fortnight: int) -> str:
    culture = "ugarit"
    labels = _MONTHS[culture]
    if fortnight < 1:
        return f"yr {year}, before the year turns"
    month = labels["months"][(fortnight - 1) // 2]
    half = labels["halves"][(fortnight - 1) % 2]
    return f"yr {year}, {month}, {half}"


def _freshness(age: int) -> str:
    return "●" if age < 3 else "○" if age <= 8 else "·"


def _term_dict(term) -> dict:
    """Project only the explicit marks present on a delivered/sent tablet."""
    return {
        "kind": term.kind,
        "good": term.good,
        "quantity": term.quantity,
        "person_id": term.person_id,
        "destination": term.destination,
        "due_turn": term.due_turn,
    }


# The topics `engine/mail.py` puts on a foreign court's returning tablet, and
# the word the interface uses for each. Held here rather than imported from
# `ai/`, because Belief feeds the language layer and never depends on it.
_REPLY_TOPICS = {
    "reply_accept": "accepted",
    "reply_refuse": "refused",
    "reply_counter": "terms offered back",
}


def _stored_reply_text(world) -> dict[str, str]:
    """Accepted reply prose, by the tablet it is written on.

    The court's own case record holds the words once they have been accepted
    (`engine/state.py`), so a reloaded or replayed game reads text rather than
    asking a model for it again (spec 2.6, 2.7). Only the tablet the king
    actually holds is keyed here; the case itself never crosses this boundary.
    """
    return {
        case.reply_letter_id: case.reply_text
        for case in world.correspondence
        if case.reply_letter_id and case.reply_text
    }


def _inbox_items(world, perr: int) -> list[dict]:
    now = world.date.absolute
    items = []
    stored = _stored_reply_text(world)
    for L in world.inbox:
        arr = L.arrive_turn if L.arrive_turn is not None else now
        age = now - arr
        # Which persona card voices this sender. Usually the sender's own id,
        # but a daughter married abroad shares one card with every other
        # daughter married abroad -- including ones born during play, who
        # cannot be authored in advance.
        writer = world.court.house.get(L.sender)
        persona = ("daughter_abroad"
                   if writer is not None and writer.married_to_court
                   else L.sender)
        # Tone inputs for the Voicer (spec 8.6). Note what is NOT here: the
        # sender's report_bias and the letter's true_facts. The model is told how
        # a man sounds, never that he is lying or by how much -- so it cannot
        # wink at the player, and the ruler must catch him from a second source.
        relation = world.relations.get(L.sender)
        # Every number in the tablet is the scribe's copy, fixed at transcription
        # (keyed on the turn it arrived) so it reads the same each time.
        # A foreign court's answer is exempt from the scribe's slip. Its figures
        # are the structured terms impressed on the same clay (spec 3.2), and a
        # miscopied figure beside an exact term would be a display fault rather
        # than a fallible man: the king reads the terms, he does not count them.
        facts = (
            {k: (transcribe(v, world.seed, arr, f"{L.id}:{k}", perr)
                 if isinstance(v, int) and not isinstance(v, bool)
                 and L.topic not in _REPLY_TOPICS else v)
             for k, v in L.facts}
            if L.read else {}
        )
        items.append({
            "id": L.id, "sender": L.sender, "topic": L.topic,
            "received_turn": arr, "age": age,
            "freshness": _freshness(age), "read": L.read, "facts": facts,
            "answered_turn": L.answered_turn,
            "archived": L.archived,
            "delegated_to": L.delegated_to,
            "delegated_turn": L.delegated_turn,
            "sender_esteem": (
                _esteem_word(relation.esteem) if relation else "formal"),
            "sender_status": relation.status_claim if relation else "servant",
            "persona": persona,
            "unanswered": relation.unanswered_letters_from_them if relation else 0,
            "body": (L.text or stored.get(L.id, "")) if L.read else "",
            "terms": (
                [_term_dict(term) for term in L.terms]
                if L.read else []),
            "reply_to": L.reply_to,
        })
    return items


def _seasonal(route) -> bool:
    """Whether the route shuts outside a named season, as the tablet says it."""
    return bool(route.legs and route.legs[0].season)


def _known_legs(world, path) -> int:
    """Courier legs along a route, from the court's own route tablet.

    Legs are inherited knowledge and already cross this boundary in
    `_world_graph`. What a closed sea will add to them is not knowable in
    advance, which is why this is an expectation and never a promise.
    """
    legs = 0
    for a, b in zip(path, path[1:]):
        route = next(
            (item for item in lines(world)
             if set(item.ends) == {a, b}), None)
        legs += route.fortnights() if route is not None else 1
    return max(1, legs) if len(tuple(path)) > 1 else 1


def _answer_state(world, record: dict, replies: dict) -> dict:
    """What the court may know about the answer to one tablet it sent.

    Everything here is derived from tablets the court is holding. The foreign
    case, its decision, and its stores are not read: a court that learned it had
    been refused before the refusal arrived would be reading World (spec 2.4).

    Silence is the reason this function exists. A tablet that has outlived its
    expected round trip is not missing from the Outbox and is not quietly
    labelled sent; it reads as unanswered, with the date it went and the road it
    went by, because an ignored letter and a drowned courier look the same from
    here and the king must be able to see that he is waiting.
    """
    now = world.date.absolute
    travel = _known_legs(world, record["path"])
    # Out, a fortnight in a foreign hall, and back. The court knows its own
    # route tablet and knows that an answer is not written the day it arrives.
    expected = record["sent_turn"] + 2 * travel + 1
    reply = replies.get(record["id"])
    state = {
        "travel_turns": travel,
        "expected_reply_turn": expected,
        "reply_id": "",
        "reply_turn": None,
        "decision": "",
        "counter_terms": [],
        "answered": reply is not None,
        "silent": False,
    }
    if reply is not None:
        state["reply_id"] = reply.id
        state["reply_turn"] = (
            reply.arrive_turn if reply.arrive_turn is not None else now)
        if reply.read:
            decision = str(dict(reply.facts).get("decision", ""))
            state["decision"] = decision
            state["counter_terms"] = [_term_dict(term) for term in reply.terms]
            state["status"] = (
                "answered — "
                + _REPLY_TOPICS.get(reply.topic, decision or "answered"))
        else:
            # The tablet is here and the answer is not yet known. Reading it
            # costs court hours like any other tablet.
            state["status"] = "answer come — seal unbroken"
    elif record["in_transit"]:
        state["status"] = "courier away — no receipt"
    elif now >= expected:
        state["silent"] = True
        state["status"] = "sent — no answer"
    else:
        state["status"] = "sent — no receipt"
    return state


def _outbox(world) -> list[dict]:
    """The ruler's own permanent sent copies, annotated with known transit.

    A courier can be intercepted without the sender learning it. Consequently
    an item that has left ``letters_in_transit`` is only labelled "sent — no
    receipt", whether it arrived or vanished. The UI never turns engine truth
    into a delivery confirmation the court did not receive.

    An answer is the one receipt the court does get, so a returning tablet is
    matched to the letter it answers here (`_answer_state`), and a tablet whose
    answer never came keeps its place on the rack as an unanswered one.
    """
    travelling = {
        letter.id: letter
        for letter in world.letters_in_transit
        if letter.outgoing
    }
    records: dict[str, dict] = {}
    for doc in world.documents:
        if doc.kind != "letter_out":
            continue
        letter_id = (
            doc.ref[2:] if doc.ref.startswith("L-") else doc.ref)
        letter = travelling.get(letter_id)
        recipient = (
            doc.recipient
            or (letter.recipient if letter is not None else None)
            or "unknown court"
        )
        topic = (
            letter.topic if letter is not None else
            next((tag for tag in doc.tags
                  if tag not in {"letter_out", str(recipient)}), "reply")
        )
        records[letter_id] = {
            "id": letter_id,
            "sender": world.court.actor,
            "recipient": recipient,
            "topic": topic,
            "sent_turn": doc.received_turn,
            "received_turn": doc.received_turn,
            "body": doc.body,
            "facts": (
                {key: value for key, value in letter.facts}
                if letter is not None else {}),
            "terms": [
                _term_dict(term)
                for term in (
                    letter.terms if letter is not None else doc.terms)
            ],
            "path": list(letter.path if letter is not None else doc.path),
            "reply_to": (
                letter.reply_to if letter is not None else doc.reply_to),
            "scribe_id": (
                letter.scribe_id if letter is not None else doc.scribe_id),
            "seal": letter.seal if letter is not None else doc.seal,
            "courier_id": (
                letter.courier_id if letter is not None else doc.courier_id),
            "in_transit": letter is not None,
            "status": (
                "courier away — no receipt"
                if letter is not None else "sent — no receipt"),
            "read": True,
            "answered_turn": None,
            "archived": False,
            "delegated_to": None,
            "delegated_turn": None,
        }

    # Compatibility for worlds produced by direct engine.mail calls rather
    # than player actions: an in-transit tablet should still be visible even
    # when no permanent sent copy was made through reduce.apply.
    for letter_id, letter in travelling.items():
        if letter_id in records:
            continue
        facts = {key: value for key, value in letter.facts}
        body_facts = ", ".join(f"{key} {value}" for key, value in letter.facts)
        body = letter.topic.replace("_", " ")
        if body_facts:
            body += ". " + body_facts
        records[letter_id] = {
            "id": letter_id,
            "sender": world.court.actor,
            "recipient": letter.recipient,
            "topic": letter.topic,
            "sent_turn": letter.sent_turn,
            "received_turn": letter.sent_turn,
            "body": body,
            "facts": facts,
            "terms": [_term_dict(term) for term in letter.terms],
            "path": list(letter.path),
            "reply_to": letter.reply_to,
            "scribe_id": letter.scribe_id,
            "seal": letter.seal,
            "courier_id": letter.courier_id,
            "in_transit": True,
            "status": "courier away — no receipt",
            "read": True,
            "answered_turn": None,
            "archived": False,
            "delegated_to": None,
            "delegated_turn": None,
        }

    # Only tablets the court is holding: `world.inbox` is what arrived, so a
    # reply still on the road cannot answer anything here.
    replies = {
        letter.reply_to: letter
        for letter in world.inbox
        if not letter.outgoing and letter.reply_to
    }
    for record in records.values():
        record.update(_answer_state(world, record, replies))
    return sorted(
        records.values(), key=lambda item: (-item["sent_turn"], item["id"]))


def _stores(world, perr: int) -> dict:
    """The scribe's count. Big numbers make his slips dramatic; inspecting a
    ledger this turn shows the true count with no marker either way (spec 9.2)."""
    c = world.court
    now = world.date.absolute
    stores = seat_door.held(world)
    inspected_goods = {_LEDGERS[l] for l in c.inspected if l in _LEDGERS}
    out = {}
    for good in sorted(stores):
        val = stores[good]
        if good in ("grain", "seed_grain") and good not in inspected_goods:
            # Bulk written in sexagesimal places, so a lost or gained place is
            # the error that matters here (and is the drama of the granary).
            val = transcribe(val, world.seed, now, f"ledger:{good}", perr,
                             sexagesimal=True)
        out[good] = val
    return out


def _loyalty_word(loyalty: int) -> str:
    for floor, word in ((850, "devoted"), (650, "loyal"), (400, "restive"),
                        (200, "sullen"), (0, "seditious")):
        if loyalty >= floor:
            return word
    return "seditious"


def _esteem_word(esteem: int) -> str:
    for floor, word in ((800, "honoured"), (650, "warm"), (500, "formal"),
                        (350, "displeased"), (0, "hostile")):
        if esteem >= floor:
            return word
    return "hostile"


def _grain_stage(kernel, fortnight: int) -> str:
    """What the grain year is doing now, in the ruler's own words (spec 6.4).

    Ranges are the authored `kernel.seasons` map and do not overlap, so one
    membership test in year order gives the word. Low water is the fallow
    turning point; it comes last only to make the order a story.
    """
    from engine.kernel.farm import season

    for name in ("sowing", "growing", "harvest", "low_water"):
        if season(kernel.seasons, fortnight, name):
            return name
    return "low_water"


# The mark an ordinary year leaves on the river wall (`engine/climate.gauge`).
GAUGE_ORDINARY = 30
GAUGE_WORDS = ((21, "the river is failing"), (27, "the river is low"),
               (33, "the river stands ordinary"), (39, "the river is full"))


def gauge_word(reading: int) -> str:
    """The gauge in words, so a number nobody has a feel for means something."""
    for mark, word in GAUGE_WORDS:
        if reading < mark:
            return word
    return "the river is in flood"


# The grain year, in the order it happens, with the task each moment asks for.
STAGES = (("sowing", "sow"), ("growing", "tend"), ("harvest", "reap"),
          ("low_water", ""))


def _calendar(kernel, fortnight: int, turn: int) -> dict:
    """The whole year at once, not only the fortnight the king stands in.

    The calendar is not secret and never was. Withholding it made every
    quantity in the Land ledger unplannable: the ruler could see that the
    harvest asked more days than he had, and could not see that the asking
    stopped in two fortnights.
    """
    wheel = [_grain_stage(kernel, f) for f in range(1, 25)]
    spans = []
    for name, task in STAGES:
        marked = [f for f in range(1, 25) if wheel[f - 1] == name]
        if not marked:
            continue
        wraps = 1 in marked and 24 in marked and len(marked) < 24
        first = next(f for f in marked if not wraps or wheel[f - 2] != name)
        last = next(f for f in reversed(marked) if not wraps or wheel[f % 24] != name)
        spans.append({"name": name, "task": task, "from": first, "to": last,
                      "fortnights": len(marked)})
    year = {"fortnight": max(0, fortnight), "turn": turn, "wheel": wheel,
            "spans": spans, "source": "the calendar", "as_of_turn": turn,
            "certainty": "counted"}
    if fortnight < 1:
        # Before the first turn resolves. The year has a shape; the king does
        # not stand anywhere in it yet, and saying otherwise would be false.
        return {**year, "stage": "", "index": 0, "length": 0, "left": 0,
                "next": "", "next_in": 0}

    stage = wheel[fortnight - 1]
    # Where in the season this is, counting from the fortnight it opened.
    index, length = 1, 1
    back = fortnight
    while wheel[(back - 2) % 24] == stage and length < 24:
        back -= 1
        index += 1
        length += 1
    ahead = fortnight
    while wheel[ahead % 24] == stage and length < 24:
        ahead += 1
        length += 1

    order = [name for name, _ in STAGES]
    following = order[(order.index(stage) + 1) % len(order)]
    ahead_by = next((n for n in range(1, 25)
                     if wheel[(fortnight - 1 + n) % 24] == following), 0)
    return {**year, "stage": stage, "index": index, "length": length,
            "left": length - index + 1,
            "next": following, "next_in": ahead_by}


def _land(world, perr: int) -> dict:
    """What the ruler can learn about his own fields (spec 6.4).

    C4 moved the crown's fields into the kernel: the ground is a `Site`
    (`kernel/farm.py`), the seed is the kernel's Book, and `Court` keeps only
    the ledger the harvest feeds it (`last_land_due`, `at_harvest`). Belief
    re-points here at C5, reading the live kernel next to the court's record,
    with the same keys the room already renders.

    What is believed and what is known: the gauge passes through the same tired
    hand as everything else, and the seed count is the scribe's (so the
    Storehouse and this room always agree). What is in the ground, what the
    ground can still take, and what the estate's fields hold are things he can
    see from the gate, so those are exact.
    """
    from engine.kernel import farm as F
    from engine.kernel import seat_people as SP
    from engine.climate import gauge

    court = world.court
    kernel = world.kernel
    seat = SP.SEAT
    controller = kernel.controller(seat)
    site_id = kernel.field_site(seat, controller)
    site = kernel.registry.sites.get(site_id)

    estates = []
    if site is not None:
        field = kernel.registry.cohorts.get("cohort:ugarit_field_hands")
        estates.append({
            "id": site_id,
            "name": site.name or "the palace fields",
            "place": (site.settlement or seat).split(":")[-1],
            "irrigated": False,
            "canal_condition": None,
            # The crown's own field hands, head count (spec 6.4).
            "hands": field.people if field is not None else 0,
            "extent": site.extent,
            "capacity": site.capacity,
            "under_crop": F.under_crop(kernel, site_id),
            "seed": F.held(kernel.book, controller, F.SEED, seat),
            "standing": F.held(kernel.book, controller, F.STANDING, site_id),
            "grain": F.held(kernel.book, controller, F.GRAIN, seat),
        })

    now = world.date.absolute
    sown = sum(e["under_crop"] for e in estates)
    open_ground = max(0, (site.extent if site is not None else 0) - sown)
    standing = sum(e["standing"] for e in estates)
    stage = _grain_stage(kernel, kernel.date.fortnight)

    # What the fields ask in the fortnight that is, and what each other moment
    # of the year would ask of the stock standing here now. The ruler can count
    # the crop; the ask is the days that count needs on this estate. Keeping
    # all four is the planning figure: an ask of nothing this fortnight while
    # eight thousand parisu stand uncut is not the same fact as an ask of
    # nothing with the barns empty.
    asks = {
        "sowing": open_ground // F.SOW_PER_DAY,
        "growing": standing // F.TEND_PER_DAY,
        "harvest": standing // F.REAP_PER_DAY,
        "low_water": 0,
    }
    ask = asks[stage]

    hands = kernel.labour(seat)
    committed = seat_door.corvee_days(world)
    reading = transcribe(gauge(world), world.seed, now, f"gauge:{now}", perr)
    return {
        "estates": estates,
        "stage": stage,
        "gauge": reading,
        "gauge_says": gauge_word(reading),
        # The gauge is a tired hand's copy of a mark on a wall, not the weather.
        "gauge_source": "the river mark, as the scribe read it",
        "gauge_certainty": "reported",
        "last_land_due": court.last_land_due,
        "land_due_rate": court.land_due_rate,
        "land_due_base": court.land_due_base,
        "seed_in_store": _stores(world, perr).get("seed_grain", 0),
        "seed_in_ground": sown,
        "seed_recommended": open_ground,
        "standing": standing,
        "hands_to_the_fields": list(seat_door.at_harvest(world)),
        "corvee_days": committed,
        "works_days": court.works_days,
        "labour_days_this_turn": hands,
        "labour_days_needed": ask,
        "labour_days_committed": committed,
        "labour_days_idle": max(0, hands - ask - committed),
        "labour_days_by_season": asks,
        "rates": {"sow": F.SOW_PER_DAY, "tend": F.TEND_PER_DAY,
                  "reap": F.REAP_PER_DAY,
                  "grain_per_1000": F.HARVEST_PER_1000},
    }


def _institutions(world) -> list[dict]:
    """The CITY page (spec 6.18). What the *heads* say, not what is so.

    `condition` here is the reported figure. A head whose men are in arrears
    flatters it, and the flattery grows with what he owes them, so the number
    is least reliable exactly when it matters most. `inspect <id>` spends an
    hour and puts the true figure in its place for this turn only (6.1).

    `effective` is derived from the *reported* condition too, for the same
    reason: the player is being shown what his officials believe the machine can
    do. What it can actually do he finds out when a ship does not clear.
    """
    from engine import institution as I

    court = world.court
    out = []
    for key in sorted(court.institutions):
        inst = court.institutions[key]
        seen = f"institution:{inst.id}" in court.inspected
        condition = (inst.condition if seen else I.reported_condition(
            world, inst, world.seed, world.date.absolute))
        group = seat_door.groups(world).get(inst.group)
        staff = group.output_modifier if group is not None else 1000
        out.append({
            "id": inst.id, "name": inst.name, "kind": inst.kind,
            "place": inst.place, "head": inst.head,
            "group": inst.group,
            "group_name": group.name if group is not None else "",
            "condition": condition,
            "inspected": seen,
            "capacity": inst.capacity,
            "effective": (inst.capacity * condition // 1000 * staff // 1000
                          * I._head_factor(court, inst) // 1000),
            "upkeep": {good: qty for good, qty in inst.upkeep},
            "history": list(court.institution_history.get(key, ())),
            "source": ("royal inspection" if seen else
                       f"report of {inst.head or 'the institution'}"),
            "as_of_turn": world.date.absolute,
            "certainty": "counted" if seen else "reported",
        })
    return out


def _works_season(world) -> bool:
    """Whether the men can work this fortnight. He can see the weather."""
    from engine import works

    return works.working_season(world)


def _projects(world) -> list[dict]:
    """Work in hand (6.21). Everything here is exact.

    No scribe stands between the ruler and a building site: he can see the men,
    he ordered them there, and the overseer's count of days is the one number
    in the game nobody has any reason to dress up. What is *not* here is any
    estimate of when it will be done -- that depends on the corvée he has not
    raised yet and the season he cannot hurry.
    """
    court = world.court
    out = []
    for key in sorted(court.projects):
        p = court.projects[key]
        out.append({
            "id": p.id, "what": p.name, "kind": p.kind, "place": p.place,
            "repair": bool(p.institution), "institution": p.institution,
            "days_done": p.days_done, "days_needed": p.days_needed,
            "days_remaining": max(0, p.days_needed - p.days_done),
            "spent": {good: qty for good, qty in p.spent},
            "condition_target": p.condition_target,
            "capacity": p.capacity,
            "started_turn": p.started_turn,
            "source": "works roll", "as_of_turn": world.date.absolute,
            "certainty": "counted",
        })
    return out


def _plans(world) -> list[dict]:
    """What can be put up, and what it would cost. Authored, so exact."""
    out = []
    for kind in sorted(world.works_plans):
        plan = world.works_plans[kind]
        out.append({"kind": kind, "name": plan["name"],
                    "days": int(plan["days"]),
                    "capacity": int(plan["capacity"])})
    return out


def _justice(world) -> dict:
    """What is knowable in the hall (spec 6.19), with truth kept out.

    Before an audience the king knows who came and what sort of matter it is.
    `hear` reveals the claim and counter-claim.  It never adds `truth`, a
    correctness flag, or the legitimacy consequence waiting in the schedule.
    """
    from engine import justice

    petitions = []
    ordered = sorted(
        world.court.petitions.values(),
        key=lambda petition: (-petition.waiting, petition.arrived_turn,
                              petition.id))
    for petition in ordered:
        cited = justice.latest_precedent(world, petition.kind)
        item = {
            "id": petition.id,
            "petitioner": petition.petitioner,
            "against": petition.against,
            "kind": petition.kind,
            "waiting": petition.waiting,
            "heard": petition.heard,
            "faction": petition.faction,
            "against_faction": petition.against_faction,
            "unit": petition.unit if petition.heard else "",
            "claim": dict(petition.claim) if petition.heard else {},
            "counterclaim": (
                dict(petition.counterclaim) if petition.heard else {}),
            "claim_text": petition.claim_text if petition.heard else "",
            "counter_text": petition.counter_text if petition.heard else "",
            "precedent": None,
            "source": "court docket", "as_of_turn": world.date.absolute,
            "certainty": "counted" if petition.heard else "reported",
        }
        if cited is not None:
            item["precedent"] = {
                "id": cited.id, "kind": cited.kind, "verdict": cited.verdict,
                "turn": cited.turn, "document_ref": cited.document_ref,
                "petitioner": cited.petitioner, "against": cited.against,
            }
        petitions.append(item)
    return {
        "petitions": petitions,
        "precedents": [
            {"id": record.id, "petition_id": record.petition_id,
             "kind": record.kind, "verdict": record.verdict,
             "turn": record.turn, "document_ref": record.document_ref,
             "petitioner": record.petitioner, "against": record.against}
            for record in world.court.precedents
        ],
    }


def _metal(world) -> dict:
    """The metal page (spec 6.5, 9.3). The melt ledger sits here among the
    stocks with no emphasis, no warning, and no notification, because the
    absence of one is the mechanic."""
    court = world.court
    if not (court.workshops or court.formations):
        return {}
    return {
        "melt_ledger": court.metals.melt_ledger,
        "bronze_in_circulation": court.metals.bronze_in_circulation,
        "workshop_demand": sum(w.bronze_demand for w in court.workshops),
        "formations": [
            {"id": f.id, "name": f.name, "strength": f.strength}
            for f in court.formations
        ],
    }


def _troops(world) -> dict:
    """Where the army is and what it has been told to do (D25).

    All of it exact: these are the king's own standing orders, and a man who
    does not know where he sent his own household troops has worse problems
    than a scribe. What is NOT exact is the summons list -- a demand that has
    arrived but has not been read is not on it, because nobody has told him.
    The clock is running all the same.
    """
    from engine.troops import garrison_strength, mustered_for

    court = world.court
    if not court.formations:
        return {}
    read_summons = {
        (letter.summons_oath, letter.arrive_turn)
        for letter in world.inbox if letter.summons_oath and letter.read
    }
    # Only places somebody is actually holding. A city he has sent men to
    # campaign at is not a city he garrisons, and a line reading nought there
    # would say the opposite of what it means.
    places = sorted({f.place for f in court.formations
                     if f.task in ("garrison", "watch")})
    return {
        "formations": [
            {"id": f.id, "name": f.name, "strength": f.strength,
             "ready": f.ready, "equipment_floor": f.equipment_floor,
             "replacement_rate": f.replacement_rate,
             "task": f.task, "place": f.place, "commander": f.commander,
             "source": "muster roll", "as_of_turn": world.date.absolute,
             "certainty": "counted"}
            for f in sorted(court.formations, key=lambda f: f.id)
        ],
        "garrisons": {p: garrison_strength(world, p) for p in places},
        "summons": [
            {"oath_id": s.oath_id, "place": s.place, "required": s.n,
             "due_turn": s.due_turn,
             "mustered": mustered_for(court, s.place),
             "overdue": world.date.absolute > s.due_turn}
            for s in court.summons
            if (s.oath_id, s.called_turn) in read_summons
        ],
    }


SEEN = {
    "drought": "the rain has failed",
    "crop_failure": "the crop has failed in the field",
    "earthquake": "the ground has shaken",
    "destructive_sea": "the sea has broken the shore",
    "epidemic": "there is sickness",
    "route_violence": "the roads are not safe",
    "political_rupture": "the ruling house is broken",
    "volcanic": "the sky is dark with ash",
    "fire": "there has been a fire",
    "locusts": "locusts have come",
    "flood": "the water has come over the banks",
}


def _calamities(world) -> list[dict]:
    """A disaster in the king's own Alu is not a report, it is a thing he can
    see from the roof. Disasters elsewhere reach him by letter or not at all,
    so they are not here."""
    seat = f"settlement:{world.chosen_alu}"
    return [{"kind": shock.kind, "say": SEEN.get(shock.kind, shock.kind),
             "began": shock.turn, "until": shock.until}
            for shock in world.shocks
            if shock.target == seat and shock.recovered_turn < 0]


def _plague(world, perr: int) -> dict:
    """What a king can actually know about an epidemic (spec 6.12).

    He knows there is a sickness in his own city, because he can see it. He
    knows roughly how many have been buried, because somebody counts graves and
    a scribe copies the number, badly. He knows which routes he has closed and
    which oaths he has made offerings against, because he gave those orders.

    He does not know S, I, R, beta, gamma, or mortality -- nobody in 1190 BC has
    those concepts, let alone those numbers.  Priests and factions may argue
    that a vow caused the sickness, but World contains no divine answer for
    Belief to hide.  `offerings_made` is simply what the ruler did, in order,
    with no verdict attached.
    """
    court = world.court
    seat = marks(world).get(court.seat)
    if seat is None:
        return {}
    return {
        # Not a count: you can see a plague or you cannot.
        "sickness_at_seat": seat.infected > 0,
        # Cumulative graves. True-ish, a fortnight stale, and mis-copied.
        "burials_at_seat": (
            transcribe(seat.dead, world.seed, world.date.absolute,
                       "burials", perr) if seat.dead else 0),
        "quarantined": list(court.quarantined),
        "offerings_made": list(world.plague.expiated),
    }


def _archive(world) -> dict:
    """The permanent record (spec 6.17), and the searches paid for this turn.

    Ordered by `received_turn` and by nothing else, because the court cannot
    order it by anything else -- the senders' dates are in other calendars with
    other epochs. The predecessor archive carries negative turns, so the oldest
    tablets in the room sort to the top of every result set.
    """
    from engine import archive as arch

    hits = {}
    for query in world.court.searched:
        hits[query] = [
            {"ref": doc.ref, "kind": doc.kind, "title": doc.title,
             "dated_as": doc.dated_as, "sender": doc.sender,
             "recipient": doc.recipient,
             "received_turn": doc.received_turn,
             "snippet": arch.snippet(doc), "body": doc.body,
             "tags": list(doc.tags)}
            for doc in arch.search(world, query)
        ]
    return {
        "size": len(world.documents),
        "searched": list(world.court.searched),
        "hits": hits,
    }


def _health_word(health: int) -> str:
    for floor, word in ((850, "in rude health"), (650, "well"),
                        (450, "ailing"), (250, "gravely ill"), (0, "sinking")):
        if health >= floor:
            return word
    return "sinking"


def _house(world) -> dict:
    """The family as the ruler knows it (spec 6.10, 9.3 tab 5).

    He knows their ages, where they are, who they married, and how they look --
    as a word, never a number, because nobody in 1190 BC had a number for it.
    He does not know who is going to die, which is precisely what the diviner
    is for and precisely why the diviner is worth lying to him about.
    """
    court = world.court
    if not court.house:
        return {}
    people = []
    for person in sorted(court.house.values(),
                         key=lambda p: (-p.age_turns, p.id)):
        people.append({
            "id": person.id, "name": person.name, "sex": person.sex,
            "age_years": person.age_turns // 24,
            "health": _health_word(person.health),
            "location": person.location,
            "spouse": person.spouse,
            "mother": person.mother, "father": person.father,
            "heir_rank": person.is_heir_rank,
            "alive": person.alive,
            "died_turn": person.died_turn,
            "married_to_court": person.married_to_court,
            "is_queen_mother": person.is_queen_mother,
            "expecting": person.pregnant_until is not None,
            "faction": person.faction,
            "agenda": person.own_agenda,
            "competence": _health_word(person.competence).replace(
                "in rude health", "exceptionally able").replace(
                "well", "capable").replace(
                "ailing", "ordinary").replace(
                "gravely ill", "poor").replace("sinking", "unfit"),
            "loyalty": _esteem_word(person.loyalty),
            "post": person.post,
            "interests": list(person.interests),
            "named_heir": court.named_heir == person.id,
            "source": "court household roll",
            "as_of_turn": world.date.absolute,
            "certainty": "reported",
        })
    return {
        "ruler": court.ruler,
        "reigns": court.reigns,
        "named_heir": court.named_heir,
        "members": people,
        # Everything the diviner has said, and nothing about whether he was
        # right. There is no field here that could answer that (spec 6.11).
        "omens": [
            {"id": o.id, "turn": o.turn, "question": o.question,
             "subject": o.subject, "reported": o.reported,
             "published": o.published, "defied": o.defied_turn is not None}
            for o in world.omens
        ],
    }


def _world_graph(world) -> dict:
    """The inherited route tablet, not live knowledge of foreign places.

    Place names and courier legs are authored court knowledge.  Projecting them
    lets the World view draw the scenario it was handed instead of carrying a
    second, hardcoded Ugarit inside the UI.  Nothing material or epidemiological
    crosses this boundary: population, route risk, infection, and every other
    live property remain in World.

    The tablet itself is dated to the opening of play.  Seasonal availability is
    different: the court knows its own calendar, so that observation is dated to
    the current turn and does not make the rest of the route record fresh.
    """
    now = world.date.absolute
    source = "court map"
    sailing = sea_open(world.season, world.date.fortnight)
    return {
        "source": source,
        "as_of_turn": 0,
        "age_turns": max(0, now),
        "places": [
            {
                "id": place.id,
                "name": place.name,
                # Where it stands on the inherited tablet, and what the
                # tablet says it is. All of it comes across on the same terms
                # as the name and says nothing about the place's condition now.
                "col": place.col,
                "row": place.row,
                "power": place.power,
                "rank": place.rank,
                "glyph": place.glyph,
                "role": place.role,
                "kind": place.kind,
                "alu": place.alu,
                "harbour": place.harbour,
                "source": source,
                "as_of_turn": 0,
                "age_turns": max(0, now),
                "certainty": "charted",
            }
            for place in sorted(marks(world).values(), key=lambda item: item.id)
        ],
        "routes": [
            {
                "id": route.id,
                "name": route.name,
                "a": route.ends[0],
                "b": route.ends[1],
                "origin": route.ends[0],
                "destination": route.ends[1],
                "mode": route.legs[0].mode,
                "seasonal": _seasonal(route),
                "legs": route.fortnights(),
                "capacity": route.capacity,
                "risk": route.risk,
                "tolls": list(route.toll_jurisdictions),
                # Scenery on the same terms as the terrain: the course is the
                # inherited map of where the road runs, not a live report.
                "course": [list(turn) for turn in route.course],
                "source": source,
                "as_of_turn": 0,
                "age_turns": max(0, now),
                "certainty": "charted",
                "availability": (
                    "closed" if _seasonal(route) and not sailing else "open"),
                "availability_source": "court calendar",
                "availability_as_of_turn": now,
            }
            for route in sorted(
                lines(world),
                key=lambda item: (
                    min(item.ends), max(item.ends),
                    item.legs[0].mode, item.fortnights()),
            )
        ],
        # The ground, drawn on the same inherited tablet as the place names,
        # and the holdings standing on it. Both are scenery: no condition, no
        # age of their own worth quoting, and nothing live behind them to leak.
        "terrain": {
            "rows": list(world.terrain.rows),
            "west": world.terrain.west,
            "north": world.terrain.north,
            "step_lon": world.terrain.step_lon,
            "step_lat": world.terrain.step_lat,
            "legend": world.terrain.legend,
        },
        "sites": [
            {"id": site.id, "kind": site.kind,
             "alu": site.settlement.split(":", 1)[1],
             "settlement": site.settlement.split(":", 1)[-1],
             "role": ("palace_centre" if site.function == "palace_centre"
                      else "capacity"),
             "function": site.function, "capacity": site.capacity,
             "extent": site.extent, "holder": site.holder,
             "region": site.region, "harbour": site.harbour,
             "population": site.population,
             "name": site.name, "col": site.col, "row": site.row,
             "source": source, "as_of_turn": 0,
             "age_turns": max(0, now), "certainty": "charted"}
            # Addressable marks are drawn from `places` above; listing them
            # here as well would put Ma'hadu in the hinterland twice.
            for site in [world.kernel.registry.sites[i]
                         for i in sorted(world.kernel.registry.sites)]
            if not site.addressable
            and not world.kernel.registry.settlements[site.settlement].fallen
        ],
    }


def _trade(world, perr: int) -> dict:
    from engine.kernel import carry

    seat = f"settlement:{world.chosen_alu}"
    controller = world.kernel.controller(seat)
    market = carry.readings(world.kernel, seat)
    cargo = []
    for lot in world.kernel.book.at(seat):
        if lot.owner != controller and lot.quantity:
            cargo.append({
                "id": lot.id, "good": lot.good, "quantity": lot.quantity,
                "reserved": lot.reserved, "available": lot.free,
                "owner": lot.owner, "holder": lot.holder,
                "location": lot.location.split(":", 1)[-1],
                "quality": lot.quality, "provenance": list(lot.provenance),
                "source": "harbour cargo roll",
                "as_of_turn": world.date.absolute, "certainty": "counted",
            })
    routes = []
    for route_id in sorted(world.kernel.registry.routes):
        route = world.kernel.registry.routes[route_id]
        if any(world.kernel.registry.settlements[leg.origin].fallen
               or world.kernel.registry.settlements[leg.destination].fallen
               for leg in route.legs):
            continue
        if not any(seat in (leg.origin, leg.destination) for leg in route.legs):
            continue
        routes.append({
            "id": route_id, "name": route.name,
            "origin": route.origin.split(":", 1)[-1],
            "destination": route.destination.split(":", 1)[-1],
            "strength": world.kernel.trade_routes.get(route_id, 0),
            "mode": route.legs[0].mode, "legs": route.fortnights(),
            "capacity": route.capacity, "risk": route.risk,
            "tolls": list(route.toll_jurisdictions),
            "seasonal": _seasonal(route), "source": "court route tablet",
            "as_of_turn": 0, "certainty": "charted",
        })
    movements = [{
        "id": voyage.id,
        "route": voyage.route,
        "carrier": voyage.carrier,
        "origin": voyage.origin.split(":", 1)[-1],
        "destination": voyage.destination.split(":", 1)[-1],
        "departed": voyage.departed,
        "arrives": voyage.arrives,
        "remaining": max(0, voyage.arrives - world.date.absolute),
        "mode": voyage.mode,
        "cargo": list(voyage.cargo),
        "news": dict(voyage.news),
        "source": "dispatch and harbour reports",
        "as_of_turn": world.date.absolute, "certainty": "reported",
    } for voyage in world.kernel.voyages
        if seat in (voyage.origin, voyage.destination)
        or voyage.carrier == controller]
    return {
        "grain_price": transcribe(
            market["price_grain"], world.seed, world.date.absolute,
            "trade:grain_price", perr),
        "cargo": cargo,
        "routes": routes,
        "movements": movements,
    }


def project(world) -> dict:
    from engine import fall
    c = world.court
    d = world.date
    perr = p_error(c.scribe_competence, c.scribe_fatigue)
    items = _inbox_items(world, perr)
    # The Stack: unread first, then freshest (the scribe's importance-bias
    # ordering lands in M6). The Archive: the permanent record, by received turn
    # only -- it cannot sort by the senders' own dates (spec 6.17).
    stack = sorted(
        (item for item in items if not item["archived"]),
        key=lambda it: (it["read"], -it["received_turn"]))
    correspondence_archive = sorted(
        (item for item in items if item["archived"]),
        key=lambda it: -it["received_turn"])
    archive = sorted(items, key=lambda it: it["received_turn"])
    outbox = _outbox(world)
    allowances = seat_door.allowances(world)
    groups = []
    roll = seat_door.groups(world)
    for gid in sorted(roll):
        g = roll[gid]
        owed = g.size * g.entitlement
        ordinary_claim = owed + min(g.arrears, owed)
        groups.append({
            "id": gid, "name": g.name, "size": g.size,
            "entitlement": g.entitlement, "function": g.function,
            "place": g.place,
            "allocated": min(
                allowances.get(gid, ordinary_claim), ordinary_claim),
            "arrears_qa": g.arrears,
            "arrears_weeks": g.arrears // max(1, owed),
            "loyalty": _loyalty_word(g.loyalty),
            "loyalty_report": g.loyalty,
            "output_modifier": g.output_modifier,
            "revolting": g.revolting,
            "at_fields": g.at_fields,
            "member_name": g.member_name,
            "source": "palace labour roll", "as_of_turn": d.absolute,
            "certainty": "counted",
        })
    seat_id = f"settlement:{world.chosen_alu}"
    cohorts = []
    for cohort in sorted(world.kernel.registry.cohorts.values(),
                         key=lambda item: item.id):
        if cohort.settlement != seat_id and not cohort.parent:
            continue
        cohorts.append({
            "id": cohort.id,
            "name": cohort.name or cohort.kind.replace("_", " "),
            "size": transcribe(cohort.people, world.seed, d.absolute,
                               f"cohort:{cohort.id}", perr),
            "people": transcribe(cohort.people, world.seed, d.absolute,
                                 f"cohort:{cohort.id}", perr),
            "households": cohort.households,
            "origin": cohort.origin,
            "ethnicity": cohort.ethnicity,
            "status": cohort.status,
            "place": cohort.settlement.split(":", 1)[-1],
            "tenure": world.kernel.tenure_of(cohort),
            "institution": cohort.institution,
            "representative": cohort.representative,
            "armed": cohort.armed,
            "parent": cohort.parent,
            "roll_id": cohort.roll_id,
            "roll_place": cohort.roll_place,
            "roll_function": cohort.roll_function,
            "task": cohort.task,
            "path": [part.split(":", 1)[-1] for part in cohort.path],
            "arrives": cohort.arrives if cohort.arrives >= 0 else None,
            "until": cohort.until if cohort.until >= 0 else None,
            "ration_source": cohort.ration_source,
            "official": cohort.official,
            "labour_per_head": cohort.labour_per_head,
            "labour": cohort.labour(),
            "ration_per_head": cohort.ration_per_head,
            "ration": cohort.ration(),
            "allowance": cohort.allowance if cohort.allowance >= 0 else None,
            "shortfall": cohort.shortfall,
            "hunger": cohort.hunger,
            "grievance": cohort.grievance,
            "precedence": cohort.precedence,
            "corvee": cohort.corvee,
            "reaping": cohort.reaping,
            "infected": cohort.infected,
            "recovered": cohort.recovered,
            "dead": cohort.dead,
            "source": "current cohort roll", "as_of_turn": d.absolute,
            "certainty": "reported",
        })
    relations = []
    for actor, relation in sorted(world.relations.items()):
        if relation.place not in world.places:
            continue
        person = world.kernel.registry.persons.get(actor)
        claim_known = (
            relation.status_claim == relation.their_status_claim
            or relation.status_mismatch_known)
        relations.append({
            "other": actor, "name": person.name if person else actor,
            "place": relation.place,
            "status_claim": relation.status_claim,
            "their_status_claim": (
                relation.their_status_claim if claim_known else "uncertain"),
            "esteem": _esteem_word(relation.esteem),
            "obligation": relation.obligation,
            "last_gift_from_us": relation.last_gift_from_us,
            "last_gift_from_them": relation.last_gift_from_them,
            "best_known_rival_gift": relation.best_known_rival_gift,
            "known_rival_gift_source": relation.known_rival_gift_source,
            "unanswered": relation.unanswered_letters_from_them,
            "seeking_patron": (
                relation.seeking_patron
                if relation.patron_notice_received else None),
            "source": "received correspondence", "as_of_turn": d.absolute,
            "certainty": "reported",
        })
    oaths = [{
        "id": oath.id, "parties": list(oath.parties),
        "superior": oath.superior, "gods": list(oath.gods),
        "sworn_turn": oath.sworn_turn, "sworn_by": oath.sworn_by,
        "dissolved": oath.dissolved,
        "binds_house": oath.binds_house,
        # After a succession this is the most important word on the screen:
        # nobody is bound, and somebody has to swear again (spec 6.9).
        "lapsed": oath.lapsed,
        "clauses": [{
            "kind": clause.kind, "args": dict(clause.args),
        } for clause in oath.clauses],
        "source": "oath tablet", "as_of_turn": d.absolute,
        "certainty": "counted",
    } for oath in world.oaths]
    obligations = []
    for kind, records in (
            ("reservation", world.letter_reservations),
            ("promise", world.letter_obligations),
            ("request", world.letter_claims),
            ("marriage proposal", world.marriage_proposals)):
        for record in records:
            item = dataclasses.asdict(record)
            item["kind"] = item.get("kind") or kind
            item.update(source="correspondence record", as_of_turn=d.absolute,
                        certainty="counted")
            obligations.append(item)
    stores = _stores(world, perr)
    priority = list(seat_door.order_of_payment(world))
    by_group = {group["id"]: group for group in groups}
    grain_left = stores.get("grain", 0)
    for rank, gid in enumerate(priority, 1):
        group = by_group[gid]
        paid = min(grain_left, group["allocated"])
        grain_left -= paid
        owed = group["size"] * group["entitlement"]
        group.update(
            priority=rank,
            next_paid=paid,
            next_short=max(0, owed - paid),
            next_status=("full" if paid >= owed else
                         "none" if paid <= 0 else "short"),
        )
    graph = _world_graph(world)
    by_place = {relation["place"]: relation for relation in relations}
    for place in graph["places"]:
        if place["id"] in by_place:
            place["court_record"] = by_place[place["id"]]
    return {
        "scenario": world.kernel.registry.settlements[
            f"settlement:{world.chosen_alu}"].name,
        "actor": c.actor,
        "date": date_label(world.chosen_alu, d.year, d.fortnight),
        "year": d.year, "fortnight": d.fortnight,
        "turn": d.absolute,
        "attention": attention_available(c, d.fortnight),
        "attention_base": c.attention_base,
        "sea_open": sea_open(world.season, d.fortnight),
        "stack": stack,
        "correspondence_archive": correspondence_archive,
        "outbox": outbox,
        "archive": archive,
        "inspected": list(c.inspected),
        "unrest": c.unrest,
        "alu_unrest": fall.unrest(world, seat_id),
        "ended": world.ended,
        "end_reason": world.end_reason,
        "legitimacy": c.legitimacy,
        "stores": stores,
        "priority": priority,
        "ration_grain_left": grain_left,
        "groups": groups,
        "cohorts": cohorts,
        "relations": relations,
        "oaths": oaths,
        "obligations": obligations,
        "rites": [{"id": rite.id, "fortnight": rite.fortnight,
                   "hours": rite.hours, "requires": dict(rite.requires),
                   "skip_legitimacy": rite.skip_legitimacy,
                   "skip_unrest": rite.skip_unrest,
                   "source": "ritual calendar", "as_of_turn": d.absolute,
                   "certainty": "counted"} for rite in c.rites],
        "regnal_year": d.year,
        "house": _house(world),
        "world_graph": graph,
        "trade": _trade(world, perr),
        "calendar": _calendar(world.kernel, d.fortnight, d.absolute),
        "land": _land(world, perr),
        "plague": _plague(world, perr),
        "calamities": _calamities(world),
        "archive_index": _archive(world),
        # Note what `_metal` does not return: `replacement_rate`. Strength is
        # visible and never falls; the ability to replace losses is not visible
        # and does (spec 6.5). The player finds out the first time he takes
        # casualties, which is several milestones away.
        "metal": _metal(world),
        "seat": world.court.seat,
        "institutions": _institutions(world),
        "projects": _projects(world),
        "plans": _plans(world),
        "justice": _justice(world),
        "revenue": {
            "land_rate": c.land_due_rate,
            "land_base": c.land_due_base,
            "last_land_due": c.last_land_due,
            "harbour_rate": c.harbour_due_rate,
            "harbour_customary": c.harbour_due_customary,
            "harbour_traffic": c.harbour_traffic,
            "last_harbour_due": c.last_harbour_due,
            "harbour_good": world.revenue_good,
            "response_min_turns": world.revenue_rules.get(
                "response_min_turns", 3),
            "response_max_turns": world.revenue_rules.get(
                "response_max_turns", 6),
        },
        "works_season": _works_season(world),
        "works_materials": dict(world.works_materials),
        "repair_days_per_point": world.works_rules.get(
            "repair_days_per_point", 3),
        "troops": _troops(world),
        "store_history": {
            good: list(series)
            for good, series in sorted(c.store_history.items())},
        "gift_goods": [
            {"id": good, "available": stores.get(good, 0)}
            for good in sorted(world.gift_values)
            if stores.get(good, 0) > 0
        ],
    }
