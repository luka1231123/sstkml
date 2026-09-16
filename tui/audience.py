"""One audience at a time. The fortnight starts here and leaves for the Hall."""
import textwrap
import registry

from tui import advice, palace, render, style
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


def content(b, item, width):
    if item["kind"] == "case":
        case = item["case"]
        rows = palace._evidence_lines(b, case, width)
        end = next(i for i, (text, _) in enumerate(rows) if text.startswith("STAKES"))
        return render.actor_name(case["petitioner"], b.get("house")), rows[:end]
    if item["kind"] == "letter":
        letter = item["letter"]
        who = render.actor_name(letter["sender"], b.get("house"))
        if not letter.get("read"):
            return f"A messenger from {who}", [("A sealed letter awaits you.", "clay")]
        rows = [(line, "clay") for paragraph in letter.get("body", "").splitlines()
                for line in (textwrap.wrap(paragraph, width) or [""])]
        return f"Letter from {who}", rows or [("The letter has been opened. No text is recorded.", "clay")]
    if item["kind"] == "band":
        band = item["band"]
        return "People at the gate", palace._court_detail(b, band["id"], width)
    concern = item["concern"]
    return concern.speaker, [(concern.title, "gold")] + [
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
                visible = len(rows) <= room
                for key, verdict, _ in palace.VERDICTS:
                    outcome = item["case"]["outcomes"][verdict]
                    label = {"for": "pay claim", "against": "pay counterclaim", "split": "split"}[verdict]
                    label += f" · {outcome['amount']:,} {outcome['good']} · unrest {outcome['unrest']:+} · 1 hour"
                    style.footer(surface, [style.FooterAction(key, label, command="home:verdict:" + verdict,
                        enabled=visible and hours >= 1 and outcome["affordable"])],
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
        style.footer(surface, [style.FooterAction("←→", "audience"),
            style.FooterAction("d", "defer", command="home:defer", enabled=bool(item)),
            style.FooterAction("tab", "leave court", command="home:hall")], x=3, y=height - 2, width=width - 6)
    style.notice(surface, 3, height - 3, width - 6, notice)
    return surface.interactive()
