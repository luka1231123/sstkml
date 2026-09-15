"""Yabninu's introduction to the decisions in the court's own records."""

from dataclasses import dataclass
import textwrap

from belief.harvest import plan as harvest_plan
from tui import advice, collection, render, style
from tui.grid import INDEX as C, Surface


@dataclass(frozen=True)
class Matter:
    id: str
    priority: int
    title: str
    fact: str
    stake: str
    destination: str
    next_step: str
    speaker: str = advice.SCRIBE
    source: str = "court records"
    view: str = ""
    selected: str = ""


def food(b: dict) -> tuple[int, int, int | None]:
    grain = max(0, b.get("stores", {}).get("grain", 0) - b.get("ration_reserved", 0))
    need = sum(g["size"] * g["entitlement"] for g in b.get("groups", ()))
    return grain, need, grain // need if need else None


def agenda(b: dict, log=()) -> list[Matter]:
    if b.get("ended"):
        return []
    grain, need, coverage = food(b)
    intro = b.get("turn", 0) <= 2 and not any(
        r.get("action", {}).get("_t") == "InspectLedger"
        and r["action"].get("ledger") == "granary" for r in log)
    inspected = "granary" in b.get("inspected", ())
    reading = "Your inspection records" if inspected else "The keeper reports"
    found = [Matter(
        "food", 8 if intro else 9 if coverage is not None and coverage < 3 else 2,
        "Start with the keeper's grain count" if intro else "How long can we feed the roll?",
        (f"{reading} {grain:,} qa free; one full fortnight costs {need:,} qa."
         if need else "No full ration demand is recorded; food coverage is unknown."),
        "Counting improves this record. Feeding people now leaves less grain for later.",
        "stores", ("I would compare the ration queue before changing who eats." if inspected
                   else "I would inspect the grain before changing who eats."),
        source="granary and payroll", view="roll" if inspected else "stores",
        selected="" if inspected else "grain")]
    hp = harvest_plan(b)
    if hp["remaining"] and hp["need"] is not None:
        found.append(Matter(
            "harvest", 9 if hp["short_before"] else 7,
            "The harvest has a deadline",
            f"{hp['remaining']} working fortnights remain; estimated labour shortfall {hp['short_before']:,} days.",
            ("Extra hands leave their ordinary duties. Uncut crop is lost at the deadline."
             if hp["short_before"] else
             "The current roll can cover the counted crop if strength holds. Extra hands still leave other duties."),
            "stores", "I would compare the field order before sending anyone.",
            source="field count, labour roll and calendar", view="land"))
    owing = [g for g in b.get("groups", ()) if g.get("arrears_qa", 0)]
    if owing:
        group = max(owing, key=lambda g: g["arrears_qa"])
        found.append(Matter(
            "arrears", 8, "People are waiting for their grain",
            f"{group.get('member_name') or group['name']}: {group['arrears_qa']:,} qa unpaid.",
            "Repaying debt uses grain needed for future meals. It does not instantly restore goodwill.",
            "stores", "I would compare a repayment with the next ration queue.",
            source="payroll arrears", view="roll", selected=group["id"]))
    requests = [l for l in b.get("outbox", ()) if any(
        t.get("kind") == "request_good" and t.get("good") == "grain"
        for t in l.get("terms", ()))]
    pending = next((l for l in requests if not l.get("decision")), None)
    if pending:
        reply = pending.get("reply_id", "")
        found.append(Matter(
            "relief", 8 if pending.get("silent") or reply else 4,
            "The answer to our grain letter" if reply else "Our grain letter is still unanswered",
            f"{pending['id']}: {pending.get('status', 'sent')}; reply estimate turn {pending.get('expected_reply_turn', '?')}.",
            "An unanswered letter is not food in the granary. A broken route and silence can look alike.",
            "stack", "I would read the reply." if reply else "I would check the sent copy before writing again.",
            source="sent tablet and received post", view="all" if reply else "outbox",
            selected=reply or pending["id"]))
    elif coverage is not None and coverage < 4:
        found.append(Matter(
            "relief", 7, "Ask another court for grain?",
            f"The reported stores cover {coverage} full fortnights, before losses and other uses.",
            "A courier costs time. Another ruler may refuse or send less; a request guarantees no food.",
            "trade", "I would compare the known routes before asking for help.",
            source="granary, payroll and route tablets", view="relief"))
    petitions = b.get("justice", {}).get("petitions", ())
    if petitions:
        petition = max(petitions, key=lambda p: p.get("waiting", 0))
        who = render.actor_name(petition["petitioner"], b.get("house"))
        found.append(Matter(
            "justice", min(9, 7 + petition.get("waiting", 0)),
            f"{who} asks for judgement",
            petition.get("claim_text", "A claim awaits judgement.") + " " + petition.get("counter_text", ""),
            "Both parties want your seal. Paying one claim spends supplies; refusing it has a price too.",
            "palace", "I would hear both accounts before giving judgement.",
            source=petition.get("source", "court docket"), selected=petition["id"]))
    for concern in advice.concerns(b, 20):
        if concern.id in {"grain", "arrears", "justice"}:
            continue
        destination = {"summons": "muster", "plague": "plague"}.get(concern.id, concern.destination)
        found.append(Matter(
            concern.id, concern.severity, concern.title, concern.reason,
            {
                "raid": "Men defending the gate cannot work elsewhere. The reported arrival may be wrong.",
                "summons": "Sending men serves the summons and removes their labour from home.",
                "justice": "The parties want different outcomes. Read both claims before giving judgement.",
                "unread": "Reading costs court time. You do not have to answer every tablet today.",
                "offices": "An office gives someone authority over work and supplies.",
                "institutions": "Repairs use labour and supplies that other claims also need.",
                "plague": "Closing a route can limit travel and also keep goods and reports away.",
                "oaths": "Renewing an oath binds the house to its clauses.",
            }.get(concern.id, "Read the record before committing the court."),
            destination, concern.suggestion, concern.speaker, concern.basis))
    return sorted(found, key=lambda m: -m.priority)


def response(log: list[dict], now: int) -> str:
    recent = [r for r in log if r.get("turn") == now]
    if not recent:
        return "Reading the room is free. An order's cost appears before you give it."
    action = recent[-1].get("action", {})
    receipt = recent[-1].get("receipt", ())
    if receipt and action.get("_t") in {"PayArrears", "RulePetition"}:
        return receipt[0]
    return {
        "InspectLedger": "The keeper has counted it. You now have a firmer record for this fortnight.",
        "Allocate": "Your ration order is entered. Its consequences begin next fortnight.",
        "SetPriority": "The ration queue is changed. Those at its end bear the shortage first.",
        "SendToHarvest": "The field order is entered. The next report will show what changed.",
        "DispatchLetter": "The courier carries your words. A reply still has to travel back.",
        "ReadLetter": "The seal is broken. You can consider the words before deciding whether to reply.",
        "RulePetition": "Your judgement is entered. The parties must live with its terms.",
        "PlacePerson": "The appointment is entered. That person now holds the office's authority.",
    }.get(action.get("_t"), "The order is entered. You may hear another matter or let the fortnight pass.")


def compose(b: dict, log: list[dict], width=84, height=28, *, hours=0,
            selected: str = "", notice=""):
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="THE HALL — YABNINU'S BRIEFING", drop=False)
    def line(y, text, tone="clay"):
        surface.text(3, y, text[:max(1, width - 6)], C[tone], C["ink"])
    def wrap(y, text, tone="clay", limit=2):
        rows = textwrap.wrap(text, max(1, width - 6))
        for offset, row in enumerate(rows[:limit]):
            if offset == limit - 1 and len(rows) > limit:
                row = row[:max(1, width - 7)] + "…"
            line(y + offset, row, tone)
    line(2, f"{b.get('date', '')} · {hours} court hours left", "sky")
    line(3, (f"You are {render.actor_name(b.get('actor', 'the king'), b.get('house'))}. You rule through orders and letters."
             if b.get("turn", 0) <= 2 else
             "My lord, these are the people and accounts I would put before you."), "sand")
    _, _, cover = food(b)
    season = str(b.get("calendar", {}).get("stage", "unknown season")).replace("_", " ")
    line(4, (f"Food: about {cover} full fortnights" if cover is not None else "Food coverage: unknown")
         + f" · season: {season} · estimates exclude losses", "gold")
    calendar = b.get("calendar", {})
    following = str(calendar.get("next", "")).replace("_", " ")
    if following:
        line(5, f"Next: {following} in {calendar.get('next_in', '?')} fortnights · the calendar", "dim")
    matters = agenda(b, log)
    picked = next((i for i, m in enumerate(matters) if m.id == selected), 0)
    page = collection.page(len(matters), 3, max(0, picked - 2), picked)
    for offset, matter in enumerate(page.slice(matters), page.start):
        y = 6 + offset - page.start
        line(y, ("> " if offset == picked else "  ") + f"{offset + 1}. {matter.title}",
             "bone" if offset == picked else "clay")
        surface.link(2, y, width - 4, 1, "briefing:open:" + matter.id)
    line(9, f"↑↓ chooses · Enter opens · {page.label()} · Tab shows the whole palace", "dim")
    if matters:
        matter = matters[picked]
        wrap(11, f"{matter.speaker}: {matter.next_step}", "sky")
        wrap(14, matter.fact, "bone")
        wrap(17, matter.stake, "sand")
        wrap(20, response(log, b.get("turn", 0)), "barley")
        line(height - 5, f"Turn {b.get('turn', '?')} · basis: {matter.source}", "dim")
    style.notice(surface, 3, height - 4, width - 6, notice)
    line(height - 3, "Fortnight = two weeks · qa = grain measure · you may leave matters waiting", "dim")
    style.footer(surface, [style.FooterAction("Enter", "open matter"),
                           style.FooterAction("Tab", "palace"),
                           style.FooterAction("Space", "let time pass"),
                           style.FooterAction("?", "help")],
                 y=height - 2, x=2, width=width - 4)
    return surface.interactive(tuple(m.id for m in matters))
