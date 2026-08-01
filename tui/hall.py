"""The Hall: a palace threshold for triage, attendance, and passage."""
from __future__ import annotations

from tui import advice, art, render, style
from tui.grid import INDEX, InteractiveScreen, sparkline, Surface

C = INDEX

# Eight rooms. Orders lives inside the Alu, Counsel inside the Court,
# Oaths inside the Shrine, and Sickness inside the World, so the halls of the
# kingdom are the Hall, Scribes, Alu, Trade, Court, Shrine, World, and Muster.
# Help and the Storehouse station are utilities, not doors.
DOORS = (
    ("s", "Scribes", "stack"),
    ("x", "Trade", "trade"),
    ("m", "Muster", "muster"),
    ("y", "Alu", "alu"),
    ("j", "Court", "palace"),
    ("v", "Shrine", "altar"),
    ("w", "World", "world"),
)

BUILT = frozenset({
    "stack", "muster",
    "alu", "trade", "palace", "altar", "world",
})

GROUPS = (
    ("KINGDOM", (("y", "Alu"), ("x", "Trade"))),
    ("DUTY", (("m", "Muster"),)),
    ("COURT", (("j", "Court"), ("v", "Shrine"))),
    ("BEYOND", (("w", "World"),)),
)

_TARGET_OF = {key: target for key, _label, target in DOORS}


def _trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def waiting(b: dict) -> list[dict]:
    """Who is physically waiting, ordered by time rather than hidden urgency."""
    people: list[dict] = []
    for group in b.get("groups", []):
        weeks = group["arrears_weeks"]
        if weeks:
            people.append({
                "who": group["member_name"] or group["name"],
                "for": group["name"],
                "fact": f"{weeks} fortnight{'s' if weeks != 1 else ''} unpaid",
                "weight": weeks,
                "tone": "blood" if weeks >= 4 else "dim",
            })
    for item in (letter for letter in b.get("stack", []) if not letter["read"]):
        people.append({
            "who": f"a courier from {render.actor_name(item['sender'], b.get('house'))}",
            "for": render.letter_summary(item["topic"]),
            "fact": ("unread, newly come" if item["age"] == 0 else
                     f"unread {item['age']} fortnights"),
            "weight": item["age"],
            "tone": "flame" if item["age"] >= 2 else "dim",
        })
    for summons in b.get("troops", {}).get("summons", []):
        people.append({
            "who": "herald of the muster",
            "for": f"{summons['required']} men at {summons['place']}",
            "fact": f"{summons['mustered']} have gone",
            "weight": 6,
            "tone": "blood" if summons["mustered"] < summons["required"]
                    else "barley",
        })
    for petition in b.get("justice", {}).get("petitions", []):
        waiting = petition["waiting"]
        people.append({
            "who": render.actor_name(petition["petitioner"], b.get("house")),
            "for": f"{petition['kind']} claim",
            "fact": (
                f"{waiting} fortnight{'s' if waiting != 1 else ''} waiting"),
            "weight": waiting,
            "tone": "blood" if waiting >= 6 else "clay",
        })
    plague = b.get("plague", {})
    if plague.get("sickness_at_seat"):
        people.append({
            "who": "the physician",
            "for": "sickness in the lower town",
            "fact": (f"{plague['burials_at_seat']} buried"
                     if plague["burials_at_seat"] else "he will not say how many"),
            "weight": 8,
            "tone": "blood",
        })
    for oath in b.get("oaths", []):
        if oath.get("lapsed"):
            people.append({
                "who": "a messenger of " + render.actor_name(
                    oath.get("superior", ""), b.get("house")),
                "for": "an oath lapsed at succession",
                "fact": "nobody is bound",
                "weight": 5,
                "tone": "wine",
            })
    people.sort(key=lambda person: -person["weight"])
    return people


def _header(surface: Surface, b: dict, hours_left: int) -> None:
    width = surface.width
    title = (
        f" {render.actor_name(b['actor'], b.get('house')).upper()}"
        f" OF {b['scenario'].upper()}")
    date = b["date"]
    date_x = max(1, width - len(date) - 2)
    style.bar(surface, 0, 0, width, _trunc(title, max(0, date_x - 2)),
              fg=C["bone"], bg=C["lapis"])
    surface.text(date_x, 0, date, C["sky"], C["lapis"])
    surface.text(1, 1, art.band(art.CORNICE, max(0, width - 2)),
                 C["gold"], C["ink"])

    base = b["attention_base"]
    meter_width = 10 if width >= 84 else 6
    lit = 0 if base <= 0 else min(
        meter_width, hours_left * meter_width // base)
    surface.text(3, 2, "the lamp", C["dim"], C["ink"])
    style.meter(surface, 12, 2, meter_width, lit)
    hour_x = 14 + meter_width
    surface.text(hour_x, 2, f"{hours_left} of {base} hours",
                 C["clay"], C["ink"])
    sea = "the sea is open" if b["sea_open"] else "the sea is shut"
    surface.text(width - 3 - len(sea), 2, sea, C["sky"], C["ink"])

    grain = render.fmt_good("grain", b["stores"].get("grain", 0))
    series = b.get("store_history", {}).get("grain", [])
    spark_width = min(14, max(0, width - 80)) if series else 0
    facts = (
        f"granary {grain} · unrest {b['unrest']}"
        f" · legitimacy {b['legitimacy']}")
    facts_width = max(0, width - 6 - spark_width)
    surface.text(3, 3, _trunc(facts, facts_width), C["clay"], C["ink"])
    if spark_width:
        line = sparkline(series, spark_width)
        surface.text(width - 3 - len(line), 3, line, C["barley"], C["ink"])


def _architecture(surface: Surface, rail_x: int) -> tuple[int, int]:
    """Draw the passage between audience floor and palace doors.

    At ordinary sizes it is a five-cell palm pillar. At the minimum it
    contracts to a carved jamb, returning those four cells to information.
    """
    if surface.width >= 84:
        pillar_x = rail_x - 7
        rows = tuple(
            row.replace("▓", "▒")
            for row in art.pillar(max(7, surface.height - 7))
        )
        art.paint(surface, pillar_x, 5, rows, art.pillar_paint(len(rows)))
        return pillar_x - 1, rail_x
    divider = rail_x - 2
    for row in range(5, surface.height - 2):
        glyph = "╫" if (row - 5) % 4 == 0 else "│"
        surface.put(divider, row, glyph, C["sand"], C["ink"])
    return divider - 1, rail_x


def _matter_mark(severity: int) -> tuple[str, int]:
    if severity >= 9:
        return "▲", C["blood"]
    if severity >= 6:
        return "◆", C["flame"]
    return "◇", C["gold"]


def _visitor_mark(person: dict) -> tuple[str, int]:
    if person["tone"] == "blood":
        return "▲", C["blood"]
    if person["tone"] in {"flame", "wine"}:
        return "◆", C[person["tone"]]
    return "○", C["dim"]


def _door_group(surface: Surface, x: int, y: int, width: int,
                heading: str, entries: tuple[tuple[str, str], ...]) -> int:
    """Draw one lintel and pack its doors onto the rows beneath it."""
    label = f"╞ {heading} "
    surface.text(x, y, label + "─" * max(0, width - len(label)),
                 C["gold"], C["ink"])
    y += 1
    column = x + 1
    right = x + width
    for key, name in entries:
        needed = len(key) + len(name) + 4
        if column > x + 1 and column + needed > right:
            y += 1
            column = x + 1
        column += style.keycap(
            surface, column, y, key, name,
            enabled=_TARGET_OF.get(key, "") in BUILT) + 1
    return y + 1


def compose(b: dict, width: int = 84, height: int = 28,
            hours_left: int | None = None,
            notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    hours = b["attention"] if hours_left is None else max(0, hours_left)
    _header(surface, b, hours)
    style.notice(surface, 3, 4, width - 6, notice)

    right_width = 31 if width >= 90 else 27
    rx = width - right_width
    left_edge, rx = _architecture(surface, rx)
    left_x = 2
    left_width = max(0, left_edge - left_x)
    rw = max(0, width - rx - 2)

    # Raised seals are the triage hierarchy: the shape is visible without
    # colour, and the attributed evidence remains the substance of each row.
    style.bar(surface, left_x, 5, left_width, " MATTERS BEFORE THE KING",
              fg=C["bone"], bg=C["faint"])
    matter_limit = 4 if height >= 30 else 3
    matters = advice.concerns(b, matter_limit)
    if not matters:
        surface.text(4, 7, "Yabninu has put no immediate concern before you.",
                     C["ash"], C["ink"])
    for index, concern in enumerate(matters):
        row = 7 + index * 2
        if row + 1 >= height - 7:
            break
        mark, tone = _matter_mark(concern.severity)
        surface.text(4, row, mark, tone, C["ink"])
        style.keycap(surface, 6, row, str(index + 1),
                     _trunc(concern.title, max(0, left_width - 12)),
                     command=str(index + 1))
        report = f"{concern.speaker}: {concern.reason}"
        surface.text(7, row + 1, _trunc(report, max(0, left_width - 7)),
                     C["ash"], C["ink"])

    # The audience floor rises when there are fewer matters; blank rows do not
    # masquerade as atmosphere. Every visitor carries both business and age.
    waiting_top = min(height - 7, 8 + max(1, len(matters)) * 2)
    people = waiting(b)
    style.bar(surface, left_x, waiting_top, left_width,
              f" AUDIENCE FLOOR · {len(people)} WAITING ON YOU",
              fg=C["bone"], bg=C["faint"])
    room = max(0, height - waiting_top - 3)
    if not people:
        surface.text(4, waiting_top + 2, "Nobody waits; the hall is empty.",
                     C["ash"], C["ink"])
    shown = min(len(people), room)
    if len(people) > room and room:
        shown -= 1
    for offset, person in enumerate(people[:shown]):
        row = waiting_top + 1 + offset
        mark, tone = _visitor_mark(person)
        surface.text(4, row, mark, tone, C["ink"])
        who_width = min(22, max(12, left_width // 3))
        surface.text(6, row, _trunc(person["who"], who_width),
                     C["clay"], C["ink"])
        detail = f"{person['fact']} · {person['for']}"
        detail_width = max(0, left_width - who_width - 6)
        surface.text(7 + who_width, row, _trunc(detail, detail_width),
                     C["dim"], C["ink"])
    if len(people) > room and room:
        rest = len(people) - shown
        surface.text(4, waiting_top + room,
                     _trunc(f"+ {rest} wait beyond the doors", left_width - 2),
                     C["ash"], C["ink"])

    # Tablet wing. Scribes keeps its place at the top of the passages rather
    # than being repeated again in a generic navigation group; Orders is not a
    # door here, it is a station inside the Alu.
    unread = [item for item in b.get("stack", []) if not item["read"]]
    style.bar(surface, rx, 5, rw, f" INBOX · {len(unread)} UNREAD",
              fg=C["bone"], bg=C["faint"])
    if unread:
        oldest = max(unread, key=lambda item: item["age"])
        age = "new" if oldest["age"] == 0 else f"{oldest['age']} fn"
        surface.text(rx + 1, 6, _trunc(
            f"oldest · {render.actor_name(oldest['sender'], b.get('house'))}"
            f" · {age}", rw - 2),
            C["ash"], C["ink"])
    else:
        surface.text(rx + 1, 6, "no unread tablets", C["ash"], C["ink"])
    column = rx + 1
    style.keycap(surface, column, 7, "s", "Scribes")
    surface.text(rx, 8, "─" * rw, C["faint"], C["ink"])

    y = 9
    for heading, entries in GROUPS:
        if y >= height - 4:
            break
        y = _door_group(surface, rx, y, rw, heading, entries)

    # The paving belongs to the room, but also gives the audience and passages
    # a common ground instead of two dashboard columns floating in black.
    surface.text(1, height - 2, art.floor(max(0, width - 2), 2),
                 C["faint"], C["ink"])

    style.footer(surface, [
        style.FooterAction("SPACE", "end the fortnight", command="space"),
        style.FooterAction("ctrl-s", "save"),
        style.FooterAction("ctrl-o", "reload"),
        style.FooterAction(":", "command"),
        style.FooterAction("\\", "read out"),
        style.FooterAction("?", "help"),
        style.FooterAction("Q", "leave the hall", command="q"),
    ])
    return surface.interactive()
