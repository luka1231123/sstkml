"""City-specific voluntary aims, derived entirely from the public Belief.

No World access, hidden score, state mutation, or rewards. Thresholds are
advisory targets; changing chapters reports seasons and recorded succession,
never an invented event. `chapter(b, cityslug)` is the presentation API.
"""
from __future__ import annotations

import tomllib

from belief.rations import food_forecast
from pathlib import Path

_CONTENT = Path(__file__).resolve().parent.parent / "content" / "court_chapters.toml"
_CHAPTERS = tomllib.loads(_CONTENT.read_text())


def _goal(status, say, where, short=None):
    first = say.split(". ", 1)[0]
    compact = short or (first if len(first) <= 120 else first[:117].rstrip() + "…")
    return {"status": status, "say": say, "where": where, "short": compact}


def _food(b, city, period):
    reserve_turns = 4 if city in ("tyre", "alashiya") else 3
    if period == "endurance":
        reserve_turns += 1
    groups = b.get("groups", [])
    if not groups or "grain" not in b.get("stores", {}):
        return _goal("unknown", "Read the store account and ration roll before choosing a reserve.", "Storehouse")
    demand = sum(max(0, int(g.get("size", 0))) * max(0, int(g.get("entitlement", 0))) for g in groups)
    free = max(0, int(b["stores"]["grain"]) - int(b.get("ration_reserved", 0)))
    forecast = food_forecast(b)
    needed = forecast["before_harvest"]
    # Keep one closing account in reserve against spoilage and other uses.
    bridge = forecast["budget"] * (needed + 1) if needed else 0
    target = max(demand * reserve_turns, bridge)
    status = "ready" if free >= target else "attention"
    if bridge > demand * reserve_turns:
        short = f"Grain to harvest, with one spare account: {free:,} / {target:,} qa."
    else:
        short = f"Keep {reserve_turns} full ration accounts: {free:,} / {target:,} qa."
    say = short + " Estimates exclude new arrivals and other spending; the harvest may be poor."
    if status == "attention":
        sellers = any(c.get("good") == "grain" and c.get("for_sale")
                      and c.get("available", 0) > 0 for c in b.get("trade", {}).get("cargo", ()))
        say += (" Grain is for sale in Trade; compare its price with ration cuts in Storehouse."
                if sellers else " Local merchants have no grain for sale. Review ration cuts in Storehouse or request foreign relief in Scribes.")
    return _goal(status, say, "Storehouse / Trade / Scribes", short)


def _harvest(b):
    land = b.get("land", {})
    if not land:
        return _goal("unknown", "Read the land account before committing hands elsewhere.", "Storehouse / Land")
    days = int(land.get("labour_days_this_turn", 0))
    committed = int(land.get("labour_days_committed", 0))
    needed = int(land.get("labour_days_needed", 0))
    free = max(0, days - committed)
    stage = land.get("stage", "this season")
    return _goal("ready" if free >= needed else "attention",
                 f"Cover {stage} work: the land account shows {free:,} uncommitted person-days / {needed:,} needed. Keep field hands fed and review competing works.",
                 "Storehouse / Land / Alu",
                 f"Cover {stage} work: {free:,} / {needed:,} uncommitted person-days.")


def _correspondence(b, other, label):
    relation = next((r for r in b.get("relations", []) if r.get("other", "").removeprefix("person:") == other), None)
    if relation is None:
        return _goal("unknown", f"Find a received tablet or court record before relying on {label}'s support.", "Scribes / World")
    unanswered = int(relation.get("unanswered", 0))
    esteem = relation.get("esteem", "unknown")
    healthy = unanswered == 0 and esteem in ("warm", "honoured", "formal")
    return _goal("ready" if healthy else "attention",
                 f"Keep {label} answering: the correspondence record calls relations {esteem}, with {unanswered} unanswered letters. Read the claims before replying or offering goods.",
                 "Scribes", f"Keep {label} answering: relations {esteem}; {unanswered} unanswered letters.")


def _claims(b):
    justice = b.get("justice", {})
    petitions = justice.get("petitions", [])
    rulings = justice.get("rulings", [])
    if not petitions:
        return _goal("ready" if rulings else "unknown",
                     f"Keep settlements readable: {len(rulings)} judgements recorded, no claims currently on the docket. Earlier awards remain on the record.", "Court / Records")
    oldest = max(int(p.get("waiting", 0)) for p in petitions)
    urgent = any(int(p.get("waiting", 0)) > int(p.get("grace", 2)) for p in petitions)
    return _goal("attention" if urgent or petitions else "ready",
                 f"Hear the households behind the trade: {len(petitions)} {'claim' if len(petitions) == 1 else 'claims'} on the docket; the oldest has waited {oldest} fortnights. A judgement spends its stated award and records a precedent.", "Court",
                 f"Hear {len(petitions)} {'claim' if len(petitions) == 1 else 'claims'}; the oldest has waited {oldest} fortnights.")


def _harbour(b):
    port = next((i for i in b.get("institutions", []) if i.get("kind") == "harbour"), None)
    if port is None:
        return _goal("unknown", "Ask for a quay inspection before planning on its capacity.", "Alu")
    condition = int(port.get("condition", 0))
    source = port.get("source", "the quay report")
    return _goal("ready" if condition >= 600 else "attention",
                 f"Keep the quay in repair: {source} puts its condition at {condition}/1,000. Aim for 600; feed its watch and inspect or repair it when the report weakens.", "Alu / Works",
                 f"Keep the quay in repair: condition {condition}/1,000; aim for 600 (court report).")


def _tin(b):
    demand = int(b.get("metal", {}).get("workshop_demand", 0))
    stores = b.get("stores", {})
    if not demand or "tin" not in stores:
        return _goal("unknown", "Read the forge's demand and the tin account before buying repair metal.", "Storehouse / Trade")
    target = (demand * 2 + 9) // 10
    tin = int(stores["tin"])
    return _goal("ready" if tin >= target else "attention",
                 f"Copper needs tin: the account holds {tin:,} shekels of tin; two fortnights of reported forge demand need about {target:,}. Buy tin while a seller and route are available.", "Trade / Storehouse",
                 f"Keep two forge fortnights of tin: {tin:,} / {target:,} shekels in the account.")


def _mandate(b):
    clauses = b.get("grain_mandate", [])
    if not clauses:
        return _goal("attention", "Give the steward a standing grain instruction with a reserve and spending ceiling. It buys only available grain and spends your copper.", "Trade / Grain instruction")
    report = b.get("mandate_report", [])
    result = str(report[-1]) if report else "No execution receipt has arrived yet."
    return _goal("ready", f"A standing grain instruction is sealed. Review its reserve and ceiling when circumstances change. {result}", "Trade / Grain instruction", "Standing grain instruction sealed; review the steward's latest receipt.")


def _muster(b):
    troops = b.get("troops", {})
    summons = troops.get("summons", [])
    if summons:
        outstanding = next((s for s in summons if int(s.get("mustered", 0)) < int(s.get("required", 0))), summons[0])
        mustered = int(outstanding.get("mustered", 0))
        needed = int(outstanding.get("required", 0))
        due = int(outstanding.get("due_turn", 0))
        return _goal("ready" if mustered >= needed else "attention",
                     f"The read summons calls for {needed} men at {outstanding.get('place', 'the muster')}, due turn {due}; {mustered} are recorded there. Weigh compliance against the home garrison.", "Muster / Scribes",
                     f"Read summons: {mustered} / {needed} men mustered; due turn {due}.")
    local = sum(int(f.get("ready", 0)) for f in troops.get("formations", []) if f.get("place") == b.get("seat", "seat") and f.get("task") in ("garrison", "watch"))
    return _goal("ready" if local else "attention", f"No read summons is on the muster roll; {local} ready men are recorded on local garrison or watch. Read the military reports before committing them.", "Muster / Scribes", f"Keep a home force: {local} ready men on garrison or watch; no read summons on the roll.")


def _heir(b):
    house = b.get("house", {})
    ident = house.get("named_heir")
    heir = next((p for p in house.get("members", []) if p.get("id") == ident and p.get("alive")), None)
    if heir:
        return _goal("ready", f"The household roll names {heir['name']} as heir. Revisit the choice if the family changes; other relatives may still contest the succession.", "Court / Household", f"Named heir: {heir['name']}. Review the household when circumstances change.")
    return _goal("attention", "Give the dynasty a named heir. Compare age, kinship, health and loyalties in the household roll before sealing the choice.", "Court / Household")


def _governance(b):
    account = b.get("governance", {})
    if not account:
        return _goal("unknown", "Read the governing account.", "Governance")
    status = account.get("cycle_status", "open")
    due = account.get("cycle_due", "?")
    return _goal("ready" if status in {"served", "complete", "fulfilled"} else "attention",
                 f"{account.get('title', 'Governing account')}: {status}; due turn {due}. "
                 "Read the available orders and their costs.", "Governance",
                 f"Governing account: {status}; due turn {due}.")


def chapter(b: dict, cityslug: str = "seat") -> dict:
    """Return `{title, summary, goals}` using only player-visible records.

    Goal status is `ready`, `attention`, or `unknown`; `ready` describes an
    advisory condition presently recorded, never permanent quest completion.
    """
    city = cityslug if cityslug in _CHAPTERS else next((key for key, cfg in _CHAPTERS.items() if cfg["name"] in str(b.get("scenario", ""))), "seat")
    cfg = _CHAPTERS[city]
    if b.get("ended"):
        return {"title": f"The last seal of {cfg['name']}",
                "summary": str(b.get("end_reason") or "The reign has ended; its records remain readable."),
                "goals": [_goal("ready", f"Read the surviving record: {len(b.get('justice', {}).get('rulings', []))} judgements and {int(b.get('house', {}).get('reigns', 1))} rulers recorded.", "Records / Reign")]}
    stage = b.get("calendar", {}).get("stage", b.get("land", {}).get("stage"))
    if b.get("plague", {}).get("sickness_at_seat") or b.get("threats"):
        period = "pressure"
    elif stage in ("harvest", "sowing"):
        period = stage
    elif int(b.get("house", {}).get("reigns", 1)) > 1:
        period = "succession"
    elif int(b.get("year", 1)) >= 10:
        period = "endurance"
    else:
        period = "first" if int(b.get("year", 1)) == 1 else "continuity"
    goals = list(cfg["goals"])
    if period in ("harvest", "sowing"):
        goals[1] = "harvest"
    elif period == "succession":
        goals[-1] = "heir"
    functions = {
        "food": lambda: _food(b, city, period), "harvest": lambda: _harvest(b),
        "hatti": lambda: _correspondence(b, "hatti_king", "Hatti"),
        "pharaoh": lambda: _correspondence(b, "pharaoh", "Pharaoh"),
        "sidon": lambda: _correspondence(b, "sidon_king", "Sidon"),
        "claims": lambda: _claims(b), "harbour": lambda: _harbour(b),
        "tin": lambda: _tin(b), "mandate": lambda: _mandate(b),
        "muster": lambda: _muster(b), "heir": lambda: _heir(b),
        "governance": lambda: _governance(b),
    }
    return {"title": cfg[period + "_title"],
            "summary": cfg[period + "_summary"],
            "identity": cfg["identity"],
            "goals": [functions[goal]() for goal in goals]}
