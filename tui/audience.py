"""One audience at a time. The fortnight starts here and leaves for the Hall."""
import textwrap
import registry

from belief.facts import facts
from tui import advice, hall, palace, render, style
from tui.grid import Surface, INDEX as C


def queue(b, selected=""):
    items = []
    for concern in advice.concerns(b, 30):
        if concern.id in {"raid", "summons", "plague"}:
            items.append({"id": "urgent:" + concern.id, "kind": "urgent", "concern": concern})
    items += [{"id": "case:" + p["id"], "kind": "case", "case": p}
              for p in b.get("justice", {}).get("petitions", ())]
    items += [{"id": "band:" + p["id"], "kind": "band", "band": p}
              for p in palace.petitioners(b)]
    for letter in sorted(b.get("stack", ()), key=lambda l: (l.get("received_turn", 0), l["id"])):
        needs_reply = any(t.get("kind", "").startswith("request_") for t in letter.get("terms", ()))
        if not letter.get("archived") and letter.get("answered_turn") is None and (
                not letter.get("read") or needs_reply or letter.get("received_turn") == b.get("turn")
                or selected == "letter:" + letter["id"]):
            items.append({"id": "letter:" + letter["id"], "kind": "letter", "letter": letter})
    return items


def current(b, deferred=(), selected=""):
    items = [i for i in queue(b, selected) if i["id"] not in deferred]
    return next((i for i in items if i["id"] == selected), next(iter(items), None))


def _who(b, actor, width):
    return [(row, "sand") for row in render.who_rows(actor, width, b.get("house"))]


def content(b, item, width):
    if item["kind"] == "case":
        case = item["case"]
        rows = []
        claim_text, counter_text = case["claim_text"], case["counter_text"]
        if case["id"].startswith("court:payroll:"):
            amount = int(case.get("claim", {}).get("amount", 0))
            claim_text = (f"The filed claim asks for {amount:,} qa of unpaid rations. "
                          "An award clears debt; surplus grain stays with the households.")
            counter_text = ("Refuse, or pay half. A judgement leaves the standing "
                            "ration allowance unchanged.")
        for actor, said, tone, label in (
                (case["petitioner"], claim_text, "barley", "CLAIM"),
                (case["against"], counter_text, "wine", "RESPONSE")):
            name = render.actor_name(actor, b.get("house"))
            rows.append((f"{label} · {name}", tone))
            if said.startswith(name + " says "):
                said = said[len(name) + 6:]
                said = said[:1].upper() + said[1:]
            rows.extend((row, "clay") for row in textwrap.wrap(
                said or "No testimony recorded.", width, max_lines=3, placeholder=" …"))
        if case.get("beneficiary", case["petitioner"]) != case["petitioner"]:
            rows.append((f"Grain joins {case['beneficiary_name']} reserves.", "sand"))
        waited, grace = case["waiting"], case["grace"]
        delay = (f"Delay adds {case['waiting_unrest']} anger each fortnight"
                 if waited >= grace else f"{max(0, grace - waited)} fortnights before delay adds anger")
        cap = case.get("waiting_penalty_cap")
        if cap is not None and waited >= grace + cap:
            delay = "Waiting penalty has reached its cap; the claim remains open."
        elif cap is not None:
            delay += f" · capped after {cap} charges"
        if not case.get("waiting_unrest"):
            delay = "This claim has no delay penalty."
        rows.append((delay, "sand"))
        rows.append((f"Available: {b.get('stores', {}).get(case['good'], 0):,} {case['good']} · [enter/v] testimony", "dim"))
        return case["kind"].replace("_", " ").capitalize(), rows
    if item["kind"] == "letter":
        letter = item["letter"]
        who = _who(b, letter["sender"], width)
        if not letter.get("read"):
            return "A sealed letter", who
        rows = [(line, "clay") for paragraph in letter.get("body", "").splitlines()
                for line in (textwrap.wrap(paragraph, width) or [""])]
        rows = [(line, 'sand') for line in textwrap.wrap(render.reply_effect(letter), width)] + [('', 'clay')] + rows
        return "Letter", who + [("", "clay")] + rows
    if item["kind"] == "band":
        band = item["band"]
        return "People at the gate", palace._court_detail(b, band["id"], width)
    concern = item["concern"]
    return concern.title, _who(b, concern.speaker, width) + [
        (line, "clay") for line in textwrap.wrap(concern.reason, width)]


def compose(b, width=84, height=28, *, hours=0, view="court", selected="",
            deferred=(), scroll=0, report=(), notice=""):
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height,
                title="THE LAST REPORT" if view == "report" else "THE COURT", drop=False)
    def line(y, text, tone="clay"):
        surface.text(3, y, text[:width - 6], C[tone], C["ink"])
    surface.text(width - 10, 2, "? Help", C["sky"], C["ink"])
    surface.link(width - 10, 2, 7, 1, "home:help")
    line(2, f"{b.get('date', '')} · {hours} hours", "dim")
    surface.text(width - 23, 2, "F2 Reign", C["sky"], C["ink"])
    surface.link(width - 23, 2, 8, 1, "home:reign")
    if view == "report":
        rows = [r for p in report for r in (textwrap.wrap(p, width - 6) or [""])]
        room = height - 12
        start = max(0, min(scroll, max(0, len(rows) - room)))
        for y, row in enumerate(rows[start:start + room], 7):
            line(y, row)
        if not rows:
            line(7, "No fortnight report yet.")
        style.footer(surface, [style.FooterAction("↑↓", "scroll"), style.FooterAction("esc", "back to the hall", command="home:hall")], y=height - 2)
    else:
        worst = facts(b)[0]
        if worst["urgency"]:
            line(1, hall.fact_line(worst).strip(), "blood" if worst["urgency"] > 1 else "bone")
        item = current(b, deferred, selected)
        items = [i for i in queue(b, selected) if i["id"] not in deferred]
        if item:
            title, rows = content(b, item, width - 6)
            line(6, title, "bone")
            line(4, f"{items.index(item) + 1} of {len(items)} audiences · {len(deferred)} deferred", "dim")
            room = height - (17 if item["kind"] == "case" else 15)
            start = max(0, min(scroll, max(0, len(rows) - room)))
            for y, (text, tone) in enumerate(rows[start:start + room], 9):
                line(y, text, tone)
            if len(rows) > room:
                line(height - 6, "↑↓ scroll to read more", "dim")
            actions = []
            if item["kind"] == "case":
                line(height - 8, "Each award spends stores and changes city anger.", "dim")
                for key, verdict, _ in palace.VERDICTS:
                    outcome = item["case"]["outcomes"][verdict]
                    label = {"for": "Grant", "against": "Refuse" if not outcome["amount"] else "Counter-offer", "split": "Compromise"}[verdict]
                    label += f" · {outcome['amount']:,} {outcome['good']} · anger {outcome['unrest']:+} · 1h"
                    style.footer(surface, [style.FooterAction(key, label, command="home:verdict:" + verdict,
                        enabled=hours >= 1 and outcome["affordable"])],
                        x=3, y=height - 7 + len(actions), width=width - 6)
                    actions.append(verdict)
                actions = []
            elif item["kind"] == "letter":
                actions = ([style.FooterAction("b", "reply", command="home:reply")]
                           if item["letter"].get("read") else
                           [style.FooterAction("enter", f"read · {registry.BY_ID['read_letter'].cost} hours",
                                               command="home:read", enabled=hours >= registry.BY_ID['read_letter'].cost)])
            elif item["kind"] == "band":
                actions = [style.FooterAction("f", "admit", command="home:receive:settle"),
                           style.FooterAction("a", "refuse", command="home:receive:refuse")]
            else:
                actions = [style.FooterAction("enter", "respond", command="home:respond")]
            if actions:
                style.footer(surface, actions, x=3, y=height - 5, width=width - 6)
        else:
            line(8, "No one else waits for this audience.", "bone")
            line(10, "Enter the hall to plan, and to end the fortnight.")
            if deferred:
                line(12, f"[R] Recall {len(deferred)} deferred matters", "sky")
                surface.link(3, 12, width - 6, 1, "home:recall")
        style.footer(surface, [style.FooterAction("tab", "Hall", command="home:hall"),
            style.FooterAction("←→", "next"),
            style.FooterAction("d", "defer", command="home:defer", enabled=bool(item)),
            style.FooterAction("v", "details", command="home:evidence", enabled=bool(item)),
            style.FooterAction("F3", "aims", command="home:charter")], x=3, y=height - 2, width=width - 6)
    style.notice(surface, 3, height - 3, width - 6, notice)
    return surface.interactive()


def evidence(b, item, width=76, height=30, scroll=0):
    s = Surface(width, height)
    style.panel(s, 0, 0, width, height, title='THE FULL TESTIMONY', drop=False)
    if item['kind'] == 'case':
        rows = palace._evidence_lines(b, item['case'], width - 6)
    else:
        _, rows = content(b, item, width - 6)
    room = height - 7
    start = max(0, min(scroll, max(0, len(rows) - room)))
    for y, (row, tone) in enumerate(rows[start:start + room], 3):
        s.text(3, y, row[:width - 6], C[tone], C['ink'])
    s.text(3, height - 4, f'Testimony {start + 1}–{min(len(rows), start + room)} of {len(rows)} · reading is free', C['dim'], C['ink'])
    style.footer(s, [style.FooterAction('↑↓', 'scroll'), style.FooterAction('esc', 'return to court')])
    return s.interactive()
