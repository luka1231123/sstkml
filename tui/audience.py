"""One audience at a time, with planning available separately."""
import textwrap
import registry

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
    style.panel(surface, 0, 0, width, height, title="THE COURT", drop=False)
    def line(y, text, tone="clay"):
        surface.text(3, y, text[:width - 6], C[tone], C["ink"])
    for x, label, key in ((3, "Court", "court"), (18, "Planning", "planning"), (36, "Last report", "report")):
        surface.text(x, 2, f"[{label}]" if key == view else label, C["bone" if key == view else "dim"], C["ink"])
        surface.link(x, 2, len(label) + 2, 1, "home:" + key)
    surface.text(width - 10, 2, "? Help", C["sky"], C["ink"])
    surface.link(width - 10, 2, 7, 1, "home:help")
    line(4, f"{b.get('date', '')} · {hours} hours", "dim")
    if view == "planning":
        line(6, "What would you like to work on?", "bone")
        labels = {"s": "Letters — write, read and review correspondence",
                  "y": "Institutions — staff and buildings", "x": "Trade — goods and routes",
                  "t": "Food and labour — rations, harvest and reserves",
                  "m": "Defence — troops and summons", "j": "People and offices",
                  "v": "Shrine — rites and oaths", "w": "World — places and reports"}
        for n, (key, _, _) in enumerate(hall.DOORS):
            line(8 + n, f"[{key.upper()}] {labels[key]}")
            surface.link(3, 8 + n, width - 6, 1, "home:door:" + key)
        line(height - 7, "[Enter] End fortnight", "gold")
        surface.link(3, height - 7, width - 6, 1, "home:end")
        style.footer(surface, [style.FooterAction("Tab", "court"), style.FooterAction("?", "help")], y=height - 2)
    elif view == "report":
        rows = [r for p in report for r in (textwrap.wrap(p, width - 6) or [""])]
        room = height - 12
        start = max(0, min(scroll, max(0, len(rows) - room)))
        for y, row in enumerate(rows[start:start + room], 7):
            line(y, row)
        if not rows:
            line(7, "No fortnight report yet.")
        style.footer(surface, [style.FooterAction("↑↓", "scroll"), style.FooterAction("Tab", "court")], y=height - 2)
    else:
        item = current(b, deferred, selected)
        items = [i for i in queue(b, selected) if i["id"] not in deferred]
        if item:
            title, rows = content(b, item, width - 6)
            line(6, title, "bone")
            line(7, f"{items.index(item) + 1} of {len(items)} audiences · {len(deferred)} deferred", "dim")
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
                    style.footer(surface, [style.FooterAction(key.upper(), label, command="home:verdict:" + verdict,
                        enabled=visible and hours >= 1 and outcome["affordable"])],
                        x=3, y=height - 7 + len(actions), width=width - 6)
                    actions.append(verdict)
                actions = []
            elif item["kind"] == "letter":
                actions = ([style.FooterAction("B", "reply", command="home:reply")]
                           if item["letter"].get("read") else
                           [style.FooterAction("Enter", f"read · {registry.BY_ID['read_letter'].cost} hours",
                                               command="home:read", enabled=hours >= registry.BY_ID['read_letter'].cost)])
            elif item["kind"] == "band":
                actions = [style.FooterAction("F", "admit", command="home:receive:settle"),
                           style.FooterAction("A", "refuse", command="home:receive:refuse")]
            else:
                actions = [style.FooterAction("Enter", "respond", command="home:respond")]
            if actions:
                style.footer(surface, actions, x=3, y=height - 5, width=width - 6)
        else:
            line(8, "No one else waits for this audience.", "bone")
            line(10, "Open Planning to work on the kingdom or end the fortnight.")
            if deferred:
                line(12, f"[R] Recall {len(deferred)} deferred matters", "sky")
                surface.link(3, 12, width - 6, 1, "home:recall")
        style.footer(surface, [style.FooterAction("←→", "audience"),
            style.FooterAction("D", "defer", command="home:defer", enabled=bool(item)),
            style.FooterAction("Tab", "planning")], x=3, y=height - 2, width=width - 6)
    style.notice(surface, 3, height - 3, width - 6, notice)
    return surface.interactive()
