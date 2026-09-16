"""The Hall: the dashboard the ruler plans from, between audiences."""
from __future__ import annotations

from tui import advice, render, style
from tui.grid import INDEX, InteractiveScreen, Surface, sparkline

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


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


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
    when = f"{b['date']} · fortnight {b.get('fortnight', 0)} of 24"
    surface.text(max(3, width - 2 - len(when)), 0, when, C["sky"], C["lapis"])
    surface.text(3, 2, f"{hours} of {b['attention_base']} hours remain", C["clay"], C["ink"])
    sea = "the sea is open" if b.get("sea_open") else "the sea is shut"
    surface.text(width - 3 - len(sea), 2, sea, C["sky"], C["ink"])
    said = render.granary_line(b)
    if said:
        surface.text(3, 3, f"granary · {said}", C["barley"], C["ink"])


def _year(surface: Surface, b: dict, width: int) -> None:
    """The year gets the full width: it is the fact every plan is made against."""
    calendar = b.get("calendar") or {}
    surface.text(3, 5, "THE YEAR", C["gold"], C["ink"])
    for index, (glyph, colour, now) in enumerate(render.year_wheel(calendar)):
        surface.put(13 + index, 5, glyph, C["flame"] if now else C[colour], C["ink"])
    surface.text(3, 6, _fit(render.year_says(calendar, width - 6), width - 6),
                 C["clay"], C["ink"])


def _standing(surface: Surface, b: dict, x: int, width: int, height: int) -> int:
    surface.text(x, 8, "STORES", C["gold"], C["ink"])
    for y, good in enumerate(("grain", "copper", "tin"), 9):
        values = b.get("store_history", {}).get(good, ())
        value = b.get("stores", {}).get(good, 0)
        delta = value - (values[-2] if len(values) > 1 else value)
        line = f"{good:<7}{render.fmt_good(good, value)}"
        surface.text(x, y, _fit(line, width), C["bone"], C["ink"])
        mark = f"Δ{'+' if delta >= 0 else '−'}{render.fmt_good(good, abs(delta))}"
        if width - len(mark) > len(line) + 1:
            surface.text(x + width - len(mark), y, mark,
                         C["dim"] if not delta else C["barley"] if delta > 0 else C["blood"],
                         C["ink"])
        series = b.get("store_history", {}).get(good, ())
        if len(series) > 2 and width > 44:
            surface.text(x + width - len(mark) - 9, y, sparkline(series, 8), C["faint"], C["ink"])
    surface.text(x, 13, "STANDING", C["gold"], C["ink"])
    surface.text(x, 14, _fit(f"king {render.standing(b.get('legitimacy', 0))}"
                             f" · {b.get('legitimacy', 0)} of 1000", width), C["bone"], C["ink"])
    surface.text(x, 15, _fit(f"city {render.temper(b.get('unrest', 0))}"
                             f" · {b.get('unrest', 0)} of 1000", width), C["bone"], C["ink"])
    groups = b.get("groups", ())
    if not groups or height < 28:
        return 18
    # What the next fortnight already owes, and what underfeeding costs in work.
    promised = sum(g.get("allocated", 0) for g in groups)
    need = sum(g.get("size", 0) * g.get("entitlement", 0) for g in groups)
    now = sum(g.get("labour_now", 0) for g in groups)
    fed = sum(g.get("labour_if_fed", 0) for g in groups)
    arrears = sum(g.get("arrears_qa", 0) for g in groups)
    surface.text(x, 17, "RATIONS AND LABOUR", C["gold"], C["ink"])
    # A number against an identical number tells the king nothing. Say the
    # shortfall when there is one, and say it is met when there is not.
    said = [(f"rations {need - promised:,} qa short of {need:,}" if promised < need
             else f"rations paid in full · {need:,} qa",
             "blood" if promised < need else "bone"),
            (f"{fed - now:,} work days lost to hunger" if fed > now
             else f"work in full · {fed:,} days", "blood" if fed > now else "bone")]
    reserved, free = b.get("ration_reserved", 0), b.get("ration_grain_left", 0)
    if reserved or free:
        said.append((f"reserved {reserved:,} qa · unspent {free:,} qa", "clay"))
    if arrears:
        said.append((f"arrears {arrears:,} qa", "blood"))
    season = b.get("works_season_name")
    if season:
        said.append((f"works: {season} · {b.get('works_rate', 0)} men-days a point", "dim"))
    for offset, (line, tone) in enumerate(said[:max(0, height - 26)], 18):
        surface.text(x, offset, _fit(line, width), C[tone], C["ink"])
    return 25


def _matters(surface: Surface, b: dict, x: int, width: int, height: int) -> None:
    """Three matters, then what is unresolved, then what is on the road."""
    surface.text(x, 8, "MATTERS BEFORE THE KING", C["gold"], C["ink"])
    y = 9
    # One row a matter, speaker first: the advice still comes out of a mouth,
    # and the rows it saves go to what is actually still waiting.
    for index, concern in enumerate(advice.concerns(b, 3), 1):
        surface.text(x, y, _fit(f"[{index}] {concern.speaker}: {concern.title}", width),
                     C["sky"], C["ink"])
        surface.link(x, y, width, 1, f"concern:{index - 1}")
        y += 1
    floor = height - 8
    waiting_rows, motion_rows = waiting(b), _motion(b)
    spare = max(0, floor - y - 4)
    for_waiting = min(len(waiting_rows) or 1, max(1, spare - min(len(motion_rows) or 1, 3)))
    y += 1
    surface.text(x, y, "STILL WAITING", C["gold"], C["ink"])
    if not waiting_rows:
        surface.text(x, y + 1, "nothing is left hanging", C["ash"], C["ink"])
    for offset, row in enumerate(waiting_rows[:for_waiting], 1):
        surface.text(x, y + offset, _fit(row["say"], width), C["blood"], C["ink"])
    y += 1 + max(1, min(for_waiting, len(waiting_rows))) + 1
    if y >= floor:
        return
    surface.text(x, y, "IN MOTION", C["gold"], C["ink"])
    if not motion_rows:
        surface.text(x, y + 1, "nothing is on the road", C["ash"], C["ink"])
    for offset, line in enumerate(motion_rows[:max(0, floor - y - 1)], 1):
        surface.text(x, y + offset, _fit(line, width), C["sky"], C["ink"])


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


def compose(b: dict, width: int = 84, height: int = 28,
            hours_left: int | None = None, notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    hours = b["attention"] if hours_left is None else max(0, hours_left)
    _header(surface, b, hours)
    style.notice(surface, 3, 4, width - 6, notice)
    if b.get("ended"):
        surface.text(3, 7, "THE ALU HAS FALLEN", C["blood"], C["ink"])
        surface.text(3, 9, _fit(b.get("end_reason", "the reign is ended"), width - 6),
                     C["bone"], C["ink"])
        style.footer(surface, (style.FooterAction("esc", "close"),))
        return surface.interactive()
    _year(surface, b, width)
    split = max(30, (width - 9) // 2)
    for y in range(8, height - 7):
        surface.put(split + 3, y, "│", C["faint"], C["ink"])
    _standing(surface, b, 3, split - 1, height)
    _matters(surface, b, split + 5, width - split - 8, height)
    _doors(surface, b, height)
    style.footer(surface, (
        style.FooterAction("space", "end the fortnight", command="space"),
        style.FooterAction("l", "report", command="home:report"),
        style.FooterAction("o", "orders", command="home:orders"),
        style.FooterAction(":", "command"), style.FooterAction("?", "help")))
    return surface.interactive()
