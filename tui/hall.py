"""The Hall: the dashboard the ruler plans from, between audiences."""
from __future__ import annotations
import textwrap

from ai import narrator
from belief.facts import facts
from tui import advice, render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
DOORS = (
    ("s", "Scribes", "stack"),
    ("y", "Alu", "alu"),
    ("x", "Trade", "trade"),
    ("t", "Storehouse", "stores"),
    ("m", "Muster", "muster"),
    ("j", "Palace", "palace"),
    ("v", "Shrine", "altar"),
    ("w", "World", "world"),
)
BUILT = frozenset(target for _key, _label, target in DOORS)
MARKS = {"stack": "▤", "alu": "▩", "trade": "◇", "stores": "▥",
         "muster": "⚑", "palace": "♚", "altar": "△", "world": "◉"}
URGENT = {3: "!!", 2: "!"}


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def fact_line(f: dict) -> str:
    return f"{URGENT.get(f['urgency'], ''):<3}{f['say']}".rstrip()


def urgent(fs: list[dict]) -> list[dict]:
    """The facts that get a line and a pick of their own; calm ones share one line."""
    return [f for f in fs if f["urgency"]] or fs[:1]


def picked(fs: list[dict], pick: str) -> dict:
    """The fact under the cursor: the one named, else the worst."""
    return next((f for f in fs if f["id"] == pick), fs[0])


def _counts(b: dict) -> dict[str, int]:
    plague = b.get("plague", {})
    return {
        "stack": sum(not item.get("read") for item in b.get("stack", ())),
        "alu": len(b.get("projects", ())) + sum(
            not item.get("head") for item in b.get("institutions", ())) + sum(
            c.get("status") == "displaced" for c in b.get("cohorts", ())),
        "trade": len(b.get("trade", {}).get("cargo", ())) + sum(
            bool(move.get("cargo"))
            for move in b.get("trade", {}).get("movements", ())),
        "stores": sum(bool(g.get("arrears_weeks")) for g in b.get("groups", ())),
        "muster": len(b.get("troops", {}).get("summons", ())),
        "palace": len(b.get("justice", {}).get("petitions", ())) + sum(
            c.get("status") == "petitioning" for c in b.get("cohorts", ())),
        "altar": sum(bool(o.get("lapsed")) for o in b.get("oaths", ())),
        "world": (int(bool(plague.get("sickness_at_seat")))
                  + len(b.get("threats", ()))),
    }


def waiting(b: dict) -> list[dict]:
    """What is unresolved, worst first. Court hears people; the Hall counts them."""
    rows = []
    for group in b.get("groups", ()):
        weeks = group.get("arrears_weeks", 0)
        if weeks:
            rows.append({"say": f"{group['name']} unpaid {weeks} fortnight"
                                f"{'s' if weeks != 1 else ''}", "weight": weeks})
    for summons in b.get("troops", {}).get("summons", ()):
        rows.append({"say": f"muster at {summons['place']}: "
                            f"{summons['mustered']} of {summons['required']} men",
                     "weight": 6})
    for petition in b.get("justice", {}).get("petitions", ()):
        waits = petition["waiting"]
        rows.append({"say": f"{render.actor_name(petition['petitioner'], b.get('house'))}"
                            f" waits {waits} fortnight{'s' if waits != 1 else ''}",
                     "weight": waits})
    for item in b.get("stack", ()):
        if not item.get("read"):
            age = item.get("age", 0)
            rows.append({"say": f"unread from "
                                f"{render.actor_name(item.get('sender', ''), b.get('house'))}"
                                + (f" · {age}f old" if age else " · new"),
                         "weight": age + 2})
    for debt in b.get("aid_debts", ()):
        left = debt["due_turn"] - b.get("turn", 0)
        rows.append({"say": f"owe {render.actor_name(debt['creditor'], b.get('house'))} "
                            f"{render.fmt_good(debt['good'], debt['owed'])} · due in {left}f",
                     "weight": 10 if left < 4 else 5})
    for bad in b.get("calamities", ()):
        rows.append({"say": f"{bad['say']} since fortnight {bad['began']}", "weight": 9})
    plague = b.get("plague", {})
    if plague.get("sickness_at_seat"):
        rows.append({"say": f"sickness in the lower town, {plague.get('burials_at_seat', 0)} buried",
                     "weight": 8})
    for oath in b.get("oaths", ()):
        if oath.get("lapsed"):
            rows.append({"say": "the lapsed oath binds nobody", "weight": 5})
    for institution in b.get("institutions", ()):
        if not institution.get("head"):
            rows.append({"say": f"{institution.get('name', institution.get('id'))} has no head",
                         "weight": 4})
    return sorted(rows, key=lambda row: (-row["weight"], row["say"]))


def _motion(b: dict) -> list[str]:
    rows = [f"{move['origin']} > {move['destination']} · due {move['arrives']}"
            for move in b.get("trade", {}).get("movements", ())
            if move.get("cargo")]
    rows += [f"{item.get('id', 'order')} · awaiting reply from "
             f"{item.get('at_node') or item.get('recipient') or 'unknown'}"
             for item in b.get("outbox", ())
             if not item.get("answered") and item.get("sent_turn", -1) >= 0]
    rows += [f"{p.get('name', p.get('id'))} · {p.get('progress', 0)}% built"
             for p in b.get("projects", ())]
    return rows


def _header(surface: Surface, b: dict, hours: int) -> None:
    width = surface.width
    title = f" {render.actor_name(b['actor'], b.get('house')).upper()} OF {b['scenario'].upper()}"
    style.bar(surface, 0, 0, width, title, fg=C["bone"], bg=C["lapis"])
    when = (f"{b['date']} of 24" if "fortnight" in b["date"]
            else f"{b['date']} · fortnight {b.get('fortnight', 0)} of 24")
    surface.text(max(3, width - 2 - len(when)), 0, when, C["sky"], C["lapis"])
    surface.text(3, 1, f"{hours} of {b['attention_base']} hours remain", C["clay"], C["ink"])
    sea = "the sea is open" if b.get("sea_open") else "the sea is shut"
    surface.text(width - 3 - len(sea), 1, sea, C["sky"], C["ink"])


def _brief(surface: Surface, y: int, head: str, text: str, *, limit=3) -> int:
    """The scribe's words as a paragraph. Returns the first free row."""
    surface.text(3, y, head, C["gold"], C["ink"])
    rows = textwrap.wrap(text, surface.width - 6, max_lines=limit, placeholder=" …")
    for row, line in enumerate(rows, y + 1):
        surface.text(3, row, line, C["bone"], C["ink"])
    return y + 1 + len(rows)


def _facts(surface: Surface, fs: list[dict], y: int, width: int, chosen: str) -> int:
    """One line for each fact; a click or [e] asks why. Returns the first free row."""
    surface.text(3, y, "WHERE THINGS STAND", C["gold"], C["ink"])
    surface.text(3 + width - 9, y, "[↑↓] pick", C["dim"], C["ink"])
    y += 1
    own = urgent(fs)[:3]
    for f in own:
        rows = textwrap.wrap(fact_line(f), width, subsequent_indent="   ")
        tone = "blood" if f["urgency"] > 1 else "bone" if f["id"] == chosen else "clay"
        for row, line in enumerate(rows, y):
            surface.text(3, row, line, C[tone], C["ink"])
        if f["id"] == chosen:
            surface.text(1, y, ">", C["flame"], C["ink"])
        surface.link(3, y, width, len(rows), "why:" + f["id"])
        y += len(rows)
    calm = "; ".join(f["say"] for f in fs if not f["urgency"])
    for line in textwrap.wrap("Calm: " + calm, width, max_lines=2, placeholder=" …") if calm else ():
        surface.text(3, y, line, C["ash"], C["ink"])
        y += 1
    return y


def _matters(surface: Surface, b: dict, y: int, width: int, floor: int) -> None:
    """The matters the officers raise; a digit or a click opens each."""
    if y >= floor:
        return
    surface.text(3, y, "MATTERS BEFORE THE KING", C["gold"], C["ink"])
    y += 1
    for index, concern in enumerate(advice.concerns(b, 3), 1):
        title = f"[{index}] {concern.speaker}: {concern.title}"
        for line in textwrap.wrap(title, width, subsequent_indent="    ")[:2]:
            if y >= floor:
                return
            surface.text(3, y, line, C["sky"], C["ink"])
            surface.link(3, y, width, 1, f"concern:{index - 1}")
            y += 1


def _year(surface: Surface, b: dict, x: int, y: int, width: int) -> int:
    """The year as one glyph a fortnight, and where it stands. Returns the first free row."""
    calendar = b.get("calendar") or {}
    surface.text(x, y, "THE YEAR", C["gold"], C["ink"])
    for index, (glyph, colour, now) in enumerate(render.year_wheel(calendar)):
        surface.put(x + index, y + 1, glyph, C["flame"] if now else C[colour], C["ink"])
    says = textwrap.wrap(render.year_says(calendar, 2 * width - 5), width)
    for row, line in enumerate(says, y + 2):
        surface.text(x, row, line, C["clay"], C["ink"])
    return y + 2 + len(says)


def _pending(surface: Surface, b: dict, x: int, y: int, width: int, floor: int) -> None:
    """What is unresolved, then what is on the road, whole rows as far as the room goes."""
    blocks = (("STILL WAITING", [row["say"] for row in waiting(b)], "no matter waits", "blood"),
              ("IN MOTION", _motion(b), "nothing is on the road", "sky"))
    for n, (head, rows, none, tone) in enumerate(blocks):
        if y >= floor - 1:
            return
        surface.text(x, y, head, C["gold"], C["ink"])
        room, lines = max(1, (floor - y - 1) // (2 - n)), []
        for row in rows:
            said = textwrap.wrap(row, width, max_lines=2, placeholder="…")
            if len(lines) + len(said) <= room:
                lines += said
        for row, line in enumerate(lines or [_fit(rows[0], width) if rows else none], y + 1):
            surface.text(x, row, line, C[tone] if rows else C["ash"], C["ink"])
        y += 2 + max(1, len(lines))


def _doors(surface: Surface, b: dict, height: int) -> None:
    counts, width = _counts(b), surface.width
    cell = max(16, (width - 6) // 4)
    surface.text(3, height - 6, "THE DOORS", C["gold"], C["ink"])
    for index, (key, label, target) in enumerate(DOORS):
        x, y = 3 + (index % 4) * cell, height - 5 + index // 4
        count = counts.get(target, 0)
        text = _fit(f"[{key}] {label}" + (f" ({count})" if count else ""), cell - 2)
        surface.text(x, y, text, C["bone"], C["ink"])
        surface.link(x, y, len(text), 1, key)


def compose(b: dict, width: int = 84, height: int = 28, hours_left: int | None = None,
            notice: str = "", briefing: str | None = None, pick: str = "",
            why: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    hours = b["attention"] if hours_left is None else max(0, hours_left)
    _header(surface, b, hours)
    style.notice(surface, 3, height - 2, width - 6, notice)
    surface.text(width // 2 - 5, 1, "[F2] Reign", C["sky"], C["ink"])
    surface.link(width // 2 - 5, 1, 10, 1, "home:reign")
    if b.get("ended"):
        surface.text(3, 7, "THE ALU HAS FALLEN", C["blood"], C["ink"])
        surface.text(3, 9, _fit(b.get("end_reason", "the reign is ended"), width - 6),
                     C["bone"], C["ink"])
        style.footer(surface, (style.FooterAction("esc", "close"),))
        return surface.interactive()
    fs = facts(b)
    text = why or (narrator.template(fs, []) if briefing is None else briefing)
    top = _brief(surface, 2, "THE SCRIBE EXPLAINS" if why else "THE PALACE SCRIBE", text, limit=6 if why else 3) + 1
    if why:
        style.keycap(surface, width - 14, 2, "esc", "close")
    cols = max(50, (width - 9) // 2)
    side, room, floor = cols + 6, max(20, width - cols - 9), height - 7
    for y in range(top, floor):
        surface.put(side - 2, y, "│", C["faint"], C["ink"])
    _matters(surface, b, _facts(surface, fs, top, cols, picked(fs, pick)["id"]) + 1, cols, floor)
    _pending(surface, b, side, _year(surface, b, side, top, room) + 1, room, floor)
    _doors(surface, b, height)
    style.footer(surface, (
        style.FooterAction("space", "end", command="space"),
        style.FooterAction("tab", "court", command="home:court"),
        style.FooterAction("F3", "aims", command="home:charter"),
        style.FooterAction("l", "report", command="home:report"),
        style.FooterAction("enter", "act", command="home:act"),
        style.FooterAction("?", "help")))
    return surface.interactive()
