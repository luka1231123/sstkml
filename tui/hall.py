"""The Hall: standing, passages, and matters physically before the king."""
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
    ("j", "Court", "palace"),
    ("v", "Shrine", "altar"),
    ("w", "World", "world"),
)
BUILT = frozenset(target for _key, _label, target in DOORS)
GROUPS = (
    ("KINGDOM", DOORS[1:5]),
    ("COURT", (DOORS[0],) + DOORS[5:]),
)
MARKS = {"stack": "▤", "alu": "▩", "trade": "◇", "stores": "▥",
         "muster": "⚑", "palace": "♚", "altar": "△", "world": "◉"}
PALACE = ("◢▄◣▀◤▄◥▀", "  ╲▟█▙╱", "  ╔╩█╩╗", "  ▟███▙", "  ▚·▩▤")


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def _cut(text: str, width: int) -> str:
    return text[:max(0, width)]


def _counts(b: dict) -> dict[str, int]:
    plague = b.get("plague", {})
    return {
        "stack": sum(not item.get("read") for item in b.get("stack", ())),
        "alu": len(b.get("projects", ())) + sum(
            not item.get("head") for item in b.get("institutions", ())) + sum(
            c.get("status") == "displaced" for c in b.get("cohorts", ())),
        "trade": sum(bool(x) for x in b.get("trade", {}).get("movements", ())),
        "stores": sum(bool(g.get("arrears_weeks")) for g in b.get("groups", ())),
        "muster": len(b.get("troops", {}).get("summons", ())),
        # A band at the gate waits in the same queue as a lawsuit.
        "palace": len(b.get("justice", {}).get("petitions", ())) + sum(
            c.get("status") == "petitioning" for c in b.get("cohorts", ())),
        "altar": sum(bool(o.get("lapsed")) for o in b.get("oaths", ())),
        "world": int(bool(plague.get("sickness_at_seat"))),
    }


def waiting(b: dict) -> list[dict]:
    people = []
    for group in b.get("groups", ()):
        weeks = group.get("arrears_weeks", 0)
        if weeks:
            people.append({"who": group.get("member_name") or group["name"],
                           "for": group["name"],
                           "fact": f"{weeks} fortnight{'s' if weeks != 1 else ''} unpaid",
                           "weight": weeks})
    for item in b.get("stack", ()):
        if item.get("read"):
            continue
        age = item.get("age", 0)
        people.append({
            "who": "courier from " + render.actor_name(
                item.get("sender", ""), b.get("house")),
            "for": render.letter_summary(item.get("topic", "message")),
            "fact": "unread, newly come" if age == 0 else f"unread {age} fortnights",
            "weight": age + 2})
    for summons in b.get("troops", {}).get("summons", ()):
        people.append({"who": "herald of the muster",
                       "for": f"{summons['required']} men at {summons['place']}",
                       "fact": f"{summons['mustered']} have gone", "weight": 6})
    for petition in b.get("justice", {}).get("petitions", ()):
        people.append({"who": render.actor_name(
                           petition["petitioner"], b.get("house")),
                       "for": f"{petition['kind']} claim",
                       "fact": f"{petition['waiting']} fortnights waiting",
                       "weight": petition["waiting"]})
    for bad in b.get("calamities", ()):
        people.append({"who": "the whole city knows", "for": bad["say"],
                       "fact": f"since fortnight {bad['began']}", "weight": 9})
    plague = b.get("plague", {})
    if plague.get("sickness_at_seat"):
        people.append({"who": "the physician", "for": "sickness in the lower town",
                       "fact": f"{plague.get('burials_at_seat', 0)} buried",
                       "weight": 8})
    for oath in b.get("oaths", ()):
        if oath.get("lapsed"):
            people.append({"who": "an oath messenger", "for": "the lapsed oath",
                           "fact": "nobody is bound", "weight": 5})
    return sorted(people, key=lambda row: (-row["weight"], row["who"]))


def _motion(b: dict) -> list[str]:
    rows = [f"{move['origin']} > {move['destination']} · due {move['arrives']}"
            for move in b.get("trade", {}).get("movements", ())
            if move.get("cargo")]
    rows += [f"{item.get('id', 'order')} · "
             f"{item.get('at_node') or item.get('recipient') or 'unknown'}"
             for item in b.get("outbox", ())
             if not item.get("answered") and item.get("sent_turn", -1) >= 0]
    return rows


def _header(surface: Surface, b: dict, hours: int) -> None:
    width = surface.width
    title = f" {render.actor_name(b['actor'], b.get('house')).upper()} OF {b['scenario'].upper()}"
    style.bar(surface, 0, 0, width, title, fg=C["bone"], bg=C["lapis"])
    # The month name is how the court says it; the fortnight number is how the
    # seasons, the deadlines, and every rate in the game are actually counted.
    when = f"{b['date']} · fortnight {b.get('fortnight', 0)} of 24"
    surface.text(max(3, width - 2 - len(when)), 0, when, C["sky"], C["lapis"])
    surface.text(3, 2, f"{hours} of {b['attention_base']} hours remain",
                 C["clay"], C["ink"])
    sea = "the sea is open" if b.get("sea_open") else "the sea is shut"
    surface.text(width - 3 - len(sea), 2, sea, C["sky"], C["ink"])
    grain = render.fmt_good("grain", b.get("stores", {}).get("grain", 0))
    said = render.granary_line(b)
    left = f"granary {grain}"
    if said:
        left += f" · {said}"
    surface.text(3, 3, left, C["barley"], C["ink"])
    right = width - 3
    series = b.get("store_history", {}).get("grain", ())
    if series and width > 82:
        line = sparkline(series, min(14, width - 81))
        surface.text(right - len(line), 3, line, C["barley"], C["ink"])
        right -= len(line) + 2
    mood = (f"city {render.temper(b.get('unrest', 0))}"
            f" · king {render.standing(b.get('legitimacy', 0))}")
    # The mood is dropped only when it would actually run into the granary,
    # not when it comes within an arbitrary five columns of it. The margin was
    # costing the row its third signal at sizes where all three fit.
    if right - len(mood) > 3 + len(left):
        surface.text(right - len(mood), 3, mood, C["clay"], C["ink"])


def _standing(surface: Surface, b: dict, x: int, width: int,
              height: int) -> None:
    surface.text(x, 5, "BELIEVED STANDING", C["gold"], C["ink"])
    for y, good in zip((7, 11, 15), ("grain", "copper", "tin")):
        values = b.get("store_history", {}).get(good, ())
        value = b.get("stores", {}).get(good, 0)
        before = values[-2] if len(values) > 1 else value
        delta = value - before
        surface.text(x, y, good.upper(), C["gold"], C["ink"])
        surface.text(x, y + 1, _cut(render.fmt_good(good, value), width),
                     C["bone"], C["ink"])
        change = render.fmt_good(good, abs(delta))
        surface.text(x, y + 2, _cut(f"Δ{'+' if delta >= 0 else '−'}{change}", width),
                     C["dim"], C["ink"])
    surface.text(x, 19, "LEGITIMACY", C["gold"], C["ink"])
    surface.text(x, 20, _cut(f"{b.get('legitimacy', 0)} of 1000", width),
                 C["bone"], C["ink"])
    surface.text(x, 21, _fit("what the court will bear", width),
                 C["dim"], C["ink"])
    if height >= 28:
        _year(surface, b, x, width)


def _year(surface: Surface, b: dict, x: int, width: int) -> None:
    """The grain year, drawn. Twenty-four cells, and one of them is now.

    The king has always known what month it is. The interface did not say so,
    which left the Land ledger's numbers unplannable: an ask he cannot meet is
    a different thing when the asking has two fortnights left in it.
    """
    calendar = b.get("calendar")
    if not calendar:
        return
    surface.text(x, 23, "THE YEAR", C["gold"], C["ink"])
    mark = f"fn {calendar.get('fortnight', 0)}"
    surface.text(x + width - len(mark), 23, mark, C["bone"], C["ink"])
    for index, (glyph, colour, now) in enumerate(render.year_wheel(calendar)):
        surface.put(x + index, 24, glyph,
                    C["flame"] if now else C[colour], C["ink"])
    surface.text(x, 25, render.year_says(calendar, width), C["clay"], C["ink"])


def _passages(surface: Surface, b: dict, x: int, width: int) -> None:
    for row, line in enumerate(PALACE, 5):
        surface.text(x + max(0, (width - len(line)) // 2), row, line,
                     C["sand"] if row < 9 else C["gold"], C["ink"])
    surface.text(x + max(0, (width - 21) // 2), 10, "wait beyond the doors",
                 C["ash"], C["ink"])
    counts = _counts(b)
    y = 12
    for heading, doors in GROUPS:
        surface.text(x, y, "╞ " + heading, C["gold"], C["ink"])
        y += 1
        for key, label, target in doors:
            count = counts.get(target, 0)
            tail = f"  {count}" if count else ""
            text = _fit(f"[{key}] {label} {MARKS[target]}{tail}", width)
            surface.text(x + 1, y, text, C["bone"], C["ink"])
            surface.link(x + 1, y, len(text), 1, key)
            y += 1


def _matters(surface: Surface, b: dict, x: int, width: int, height: int) -> None:
    surface.text(x, 5, "MATTERS BEFORE THE KING", C["gold"], C["ink"])
    concerns = advice.concerns(b, 2)
    y = 6
    for index, concern in enumerate(concerns, 1):
        surface.text(x, y, _cut(f"[{index}] {concern.speaker}:", width),
                     C["sky"], C["ink"])
        surface.text(x, y + 1, _fit(concern.title, width), C["clay"], C["ink"])
        surface.link(x, y, width, 2, f"concern:{index - 1}")
        y += 2
    audience_y = y + 1
    surface.text(x, audience_y, "AUDIENCE FLOOR", C["dim"], C["ink"])
    people = waiting(b)
    room = 3 if height >= 30 else 2
    if not people:
        surface.text(x, audience_y + 2, "the floor is empty", C["ash"], C["ink"])
    for index, person in enumerate(people[:room]):
        y = audience_y + 1 + index * 3
        who = person["who"].removeprefix("courier from ")
        surface.text(x, y, _fit(who, width), C["clay"], C["ink"])
        surface.text(x, y + 1, _fit(person["fact"], width), C["blood"], C["ink"])
        surface.text(x, y + 2, _fit(person["for"], width), C["dim"], C["ink"])
    motion_y = min(height - 6, audience_y + 2 + room * 3)
    surface.text(x, motion_y, "IN MOTION", C["gold"], C["ink"])
    motion = _motion(b)
    if not motion:
        surface.text(x, motion_y + 2, "nothing reported", C["ash"], C["ink"])
    for offset, line in enumerate(motion[:max(0, height - motion_y - 4)], 2):
        surface.text(x, motion_y + offset, _fit(line, width), C["sky"], C["ink"])


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
        style.footer(surface, (style.FooterAction("Escape", "close"),))
        return surface.interactive()

    left = centre = 28
    cx, rx = left, left + centre
    for divider in (cx, rx):
        for y in range(5, height - 2):
            surface.put(divider, y, "│", C["faint"], C["ink"])
    # The column runs from x to the divider, less one for the gap. It was
    # costed at six and so lost two columns it owned -- enough to cut the last
    # word off "what the court will bear" at every window size there is.
    _standing(surface, b, 3, cx - 4, height)
    _passages(surface, b, cx + 2, centre - 4)
    _matters(surface, b, rx + 2, width - rx - 5, height)
    style.footer(surface, (
        style.FooterAction("SPACE", "end the fortnight", command="space"),
        style.FooterAction(":", "command"), style.FooterAction("?", "help")))
    return surface.interactive()
