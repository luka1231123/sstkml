"""World -> Belief for one ruler (spec 4.1).

The TUI and the AI layer read ONLY what this returns, and it returns plain
dicts of primitives -- no World object is reachable from the result. In M1 the
player's own court is nearly truth (even so, counts pass through a scribe in
M3). Belief for the wider world arrives as Claims later.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from belief.distortion import p_error, transcribe
from engine.systems import attention_available, sea_open

_MONTHS = tomllib.loads((Path(__file__).parent.parent / "content" / "months.toml").read_text())

# Ledger name -> the true stock it counts. Inspecting one bypasses the scribe.
_LEDGERS = {"granary": "grain", "seed": "seed_grain"}


def date_label(scenario: str, year: int, fortnight: int) -> str:
    culture = {"ugarit": "ugarit", "amurru": "ugarit", "pharaoh": "egypt",
               "pylos": "pylos"}.get(scenario, "ugarit")
    labels = _MONTHS[culture]
    if fortnight < 1:
        return f"yr {year}, before the year turns"
    month = labels["months"][(fortnight - 1) // 2]
    half = labels["halves"][(fortnight - 1) % 2]
    return f"yr {year}, {month}, {half}"


def _freshness(age: int) -> str:
    return "●" if age < 3 else "○" if age <= 8 else "·"


def _inbox_items(world, perr: int) -> list[dict]:
    now = world.date.absolute
    items = []
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
        facts = {k: (transcribe(v, world.seed, arr, f"{L.id}:{k}", perr)
                     if isinstance(v, int) and not isinstance(v, bool) else v)
                 for k, v in L.facts}
        items.append({
            "id": L.id, "sender": L.sender, "topic": L.topic,
            "received_turn": arr, "age": age,
            "freshness": _freshness(age), "read": L.read, "facts": facts,
            "sender_esteem": (
                _esteem_word(relation.esteem) if relation else "formal"),
            "sender_status": relation.status_claim if relation else "servant",
            "persona": persona,
            "unanswered": relation.unanswered_letters_from_them if relation else 0,
        })
    return items


def _stores(world, perr: int) -> dict:
    """The scribe's count. Big numbers make his slips dramatic; inspecting a
    ledger this turn shows the true count with no marker either way (spec 9.2)."""
    c = world.court
    now = world.date.absolute
    inspected_goods = {_LEDGERS[l] for l in c.inspected if l in _LEDGERS}
    out = {}
    for good in sorted(c.stores):
        val = c.stores[good]
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


def _land(world, perr: int) -> dict:
    """What the ruler can learn about his own fields (spec 6.4).

    Deliberately thin. He gets a gauge reading an official took and a scribe
    copied, last year's actual harvest -- true, and the only hard datum in the
    system -- and the orders he himself gave. He does NOT get the climate index,
    the yield formula, any response value, or what is standing in the field.
    Estate overseers write to him with their own report bias (6.8), and that is
    the rest of his information.
    """
    from engine.land import gauge_reading, labour_supplied

    court = world.court
    if not court.estates:
        return {}
    now = world.date.absolute
    per_head = world.land_rules.get("labour_days_per_head", 12)
    needed = sum(e.area_iku * e.labour_days_per_iku for e in court.estates.values())
    recommended = sum(e.area_iku * e.seed_per_iku for e in court.estates.values())
    return {
        # The gauge passes through the same tired hand as everything else.
        "gauge": transcribe(gauge_reading(world), world.seed, now,
                            f"gauge:{now}", perr),
        "last_harvest": court.last_harvest,
        "previous_harvest": court.previous_harvest,
        "seed_in_store": _stores(world, perr).get("seed_grain", 0),
        # He watched it go into the ground, so he knows this one exactly. For
        # most of the year it is where all the seed is, and the store reads nought.
        "seed_in_ground": sum(e.seed_sown for e in court.estates.values()),
        "seed_recommended": recommended,
        # His own standing orders, which he knows exactly because he gave them.
        "hands_to_the_fields": list(court.at_harvest),
        "corvee_days": court.corvee_days,
        # Days already given to a building site, and therefore not to the
        # fields (6.21). He knows this one exactly: he gave the order.
        "works_days": court.works_days,
        "labour_days_this_turn": labour_supplied(court, per_head),
        "labour_days_needed": needed,
        "estates": [
            {"id": e.id, "name": e.name, "place": e.place,
             "irrigated": e.irrigated,
             # A canal is a thing you can walk along and look at.
             "canal_condition": e.canal_condition if e.irrigated else None}
            for e in sorted(court.estates.values(), key=lambda e: e.id)
        ],
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
            court, inst, world.seed, world.date.absolute))
        group = court.dependents.get(inst.group)
        staff = group.output_modifier if group is not None else 1000
        out.append({
            "id": inst.id, "name": inst.name, "kind": inst.kind,
            "place": inst.place, "head": inst.head,
            "group": inst.group,
            "group_name": group.name if group is not None else "",
            "condition": condition,
            "inspected": seen,
            "capacity": inst.capacity,
            "effective": inst.capacity * condition // 1000 * staff // 1000,
            "upkeep": {good: qty for good, qty in inst.upkeep},
            "history": list(court.institution_history.get(key, ())),
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
            "spent": {good: qty for good, qty in p.spent},
            "started_turn": p.started_turn,
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
             "task": f.task, "place": f.place}
            for f in sorted(court.formations, key=lambda f: f.id)
        ],
        "garrisons": {p: garrison_strength(court, p) for p in places},
        "summons": [
            {"oath_id": s.oath_id, "place": s.place, "required": s.n,
             "due_turn": s.due_turn,
             "mustered": mustered_for(court, s.place),
             "overdue": world.date.absolute > s.due_turn}
            for s in court.summons
            if (s.oath_id, s.called_turn) in read_summons
        ],
    }


def _plague(world, perr: int) -> dict:
    """What a king can actually know about an epidemic (spec 6.12).

    He knows there is a sickness in his own city, because he can see it. He
    knows roughly how many have been buried, because somebody counts graves and
    a scribe copies the number, badly. He knows which routes he has closed and
    which oaths he has made offerings against, because he gave those orders.

    He does not know S, I, R, beta, gamma, or mortality -- nobody in 1190 BC has
    those concepts, let alone those numbers. He does not know which oath the
    gods are angry about; that is `cause_oath_id`, it is in the archive if it is
    anywhere, and finding it is the game. And there is deliberately no field
    here that says whether an offering worked. `offerings_made` is a list of
    what he did, in the order he did it, with no verdict attached, because the
    court has no way to form one. The curve is the only answer he gets.
    """
    court = world.court
    seat = world.places.get(court.seat)
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
             "received_turn": doc.received_turn,
             "snippet": arch.snippet(doc), "tags": list(doc.tags)}
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
        })
    return {
        "ruler": court.ruler,
        "reigns": court.reigns,
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


def project(world) -> dict:
    c = world.court
    d = world.date
    perr = p_error(c.scribe_competence, c.scribe_fatigue)
    items = _inbox_items(world, perr)
    # The Stack: unread first, then freshest (the scribe's importance-bias
    # ordering lands in M6). The Archive: the permanent record, by received turn
    # only -- it cannot sort by the senders' own dates (spec 6.17).
    stack = sorted(items, key=lambda it: (it["read"], -it["received_turn"]))
    archive = sorted(items, key=lambda it: it["received_turn"])
    groups = []
    for gid in sorted(c.dependents):
        g = c.dependents[gid]
        owed = g.size * g.entitlement
        groups.append({
            "id": gid, "name": g.name, "size": g.size,
            "entitlement": g.entitlement, "function": g.function,
            "place": g.place,
            "allocated": c.allocations.get(gid, owed),
            "arrears_qa": g.arrears,
            "arrears_weeks": g.arrears // max(1, owed),
            "loyalty": _loyalty_word(g.loyalty),
            "member_name": g.member_name,
        })
    relations = []
    for actor, relation in sorted(world.relations.items()):
        claim_known = (
            relation.status_claim == relation.their_status_claim
            or relation.status_mismatch_known)
        relations.append({
            "other": actor, "place": relation.place,
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
        })
    oaths = [{
        "id": oath.id, "parties": list(oath.parties),
        "superior": oath.superior, "gods": list(oath.gods),
        "sworn_turn": oath.sworn_turn, "sworn_by": oath.sworn_by,
        "dissolved": oath.dissolved,
        # After a succession this is the most important word on the screen:
        # nobody is bound, and somebody has to swear again (spec 6.9).
        "lapsed": oath.lapsed,
        "clauses": [{
            "kind": clause.kind, "args": dict(clause.args),
        } for clause in oath.clauses],
    } for oath in world.oaths]
    stores = _stores(world, perr)
    return {
        "scenario": world.scenario,
        "actor": c.actor,
        "date": date_label(world.scenario, d.year, d.fortnight),
        "year": d.year, "fortnight": d.fortnight,
        "attention": attention_available(c, d.fortnight),
        "attention_base": c.attention_base,
        "sea_open": sea_open(world.season, d.fortnight),
        "stack": stack,
        "archive": archive,
        "inspected": list(c.inspected),
        "unrest": c.unrest,
        "legitimacy": c.legitimacy,
        "stores": stores,
        "priority": list(c.priority),
        "groups": groups,
        "relations": relations,
        "oaths": oaths,
        "regnal_year": d.year,
        "house": _house(world),
        "land": _land(world, perr),
        "plague": _plague(world, perr),
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
