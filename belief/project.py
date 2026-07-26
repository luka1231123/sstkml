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
        # Every number in the tablet is the scribe's copy, fixed at transcription
        # (keyed on the turn it arrived) so it reads the same each time.
        facts = {k: (transcribe(v, world.seed, arr, f"{L.id}:{k}", perr)
                     if isinstance(v, int) and not isinstance(v, bool) else v)
                 for k, v in L.facts}
        items.append({
            "id": L.id, "sender": L.sender, "topic": L.topic,
            "received_turn": arr, "age": age,
            "freshness": _freshness(age), "read": L.read, "facts": facts,
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
            val = transcribe(val, world.seed, now, f"ledger:{good}", perr)
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
        "gift_goods": [
            {"id": good, "available": stores.get(good, 0)}
            for good in sorted(world.gift_values)
            if stores.get(good, 0) > 0
        ],
    }
