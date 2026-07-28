"""The Hall / Home dashboard: what matters, who waits, and where to go."""
from __future__ import annotations

from tui import advice, render, style
from tui.grid import INDEX, InteractiveScreen, sparkline, Surface

C = INDEX

DOORS = (
    ("s", "Inbox", "stack"),
    ("g", "Orders", "orders"),
    ("c", "Counsel", "counsel"),
    ("t", "Stores", "stores"),
    ("r", "Roll", "roll"),
    ("l", "Land", "land"),
    ("y", "City", "city"),
    ("m", "Muster", "muster"),
    ("o", "Oaths", "oaths"),
    ("j", "Justice", "justice"),
    ("h", "House", "house"),
    ("v", "Altar", "altar"),
    ("a", "Archive", "archive"),
    ("w", "World", "world"),
    ("f", "Relations", "relations"),
    ("p", "Sickness", "plague"),
    ("?", "Help", "help"),
    ("d", "Desk", "desk"),
)

BUILT = frozenset({
    "stack", "roll", "stores", "muster", "oaths", "land", "house", "help",
    "orders",
    "desk", "archive", "altar", "world", "relations", "plague", "counsel",
    "city", "justice",
})

GROUPS = (
    ("CORRESPONDENCE", (("s", "Inbox"), ("g", "Orders"), ("c", "Counsel"),
                        ("d", "Desk"))),
    ("KINGDOM", (("t", "Stores"), ("r", "Roll"), ("l", "Land"),
                 ("y", "City"))),
    ("OBLIGATIONS", (("m", "Muster"), ("o", "Oaths"))),
    ("COURT", (("j", "Justice"), ("h", "House"), ("v", "Altar"),
               ("a", "Archive"))),
    ("WORLD", (("w", "World"), ("f", "Relations"), ("p", "Sickness"),
               ("?", "Help"))),
)


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
        people.append({
            "who": render.actor_name(petition["petitioner"], b.get("house")),
            "for": f"{petition['kind']} claim",
            "fact": f"{petition['waiting']} fortnights waiting",
            "weight": petition["waiting"],
            "tone": "blood" if petition["waiting"] >= 6 else "clay",
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
    title = f" {render.actor_name(b['actor'], b.get('house')).upper()} OF {b['scenario'].upper()}"
    style.bar(surface, 0, 0, width, title, fg=C["bone"], bg=C["lapis"])
    surface.text(width - 2 - len(b["date"]), 0, b["date"], C["sky"], C["lapis"])

    base = b["attention_base"]
    lit = 0 if base <= 0 else min(12, hours_left * 12 // base)
    surface.text(3, 2, "the lamp", C["dim"], C["ink"])
    style.meter(surface, 13, 2, 12, lit)
    surface.text(27, 2, f"{hours_left} of {base} hours", C["clay"], C["ink"])
    sea = "the sea is open" if b["sea_open"] else "the sea is shut"
    surface.text(width - 3 - len(sea), 2, sea, C["sky"], C["ink"])

    grain = render.fmt_good("grain", b["stores"].get("grain", 0))
    surface.text(3, 3, f"granary {grain}", C["barley"], C["ink"])
    surface.text(42, 3, f"unrest {b['unrest']}", C["clay"], C["ink"])
    surface.text(57, 3, f"legitimacy {b['legitimacy']}", C["clay"], C["ink"])
    series = b.get("store_history", {}).get("grain", [])
    if series:
        line = sparkline(series, min(18, max(0, width - 80)))
        surface.text(width - 3 - len(line), 3, line, C["barley"], C["ink"])


def compose(b: dict, width: int = 104, height: int = 36,
            hours_left: int | None = None,
            notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    hours = b["attention"] if hours_left is None else max(0, hours_left)
    _header(surface, b, hours)
    style.notice(surface, 3, 4, width - 6, notice)

    right_width = 31 if width >= 90 else 27
    divider = width - right_width - 2
    left_width = divider - 5
    for row in range(5, height - 2):
        surface.put(divider, row, "│", C["faint"], C["ink"])

    # Matters: the exception, then the man who raised it and what he is going
    # on. The title and the reason are facts and may be stated flatly; the
    # third line is advice, and advice is only allowed to appear in somebody's
    # mouth (UI/UX spec 20: never an unattributed `Do: send grain`).
    style.bar(surface, 2, 5, left_width + 2, " MATTERS BEFORE THE KING",
              fg=C["bone"], bg=C["faint"])
    matters = advice.concerns(b, 4)
    if not matters:
        surface.text(4, 7, "Yabninu has put no immediate concern before you.",
                     C["ash"], C["ink"])
    # Four rows apiece where there is room for the basis, three where there is
    # not: the attribution is not optional, but the grounds for it are the
    # first thing to go when the Hall is short (spec 6, order of contraction).
    # `floor` is where the hall's own people start; a matter may not run under
    # them, so a matter that does not fit whole is not drawn at all.
    floor = min(height - 9, 20)
    pitch = 4 if (floor - 7) >= len(matters) * 4 else 3
    for index, concern in enumerate(matters):
        row = 7 + index * pitch
        if row + pitch > floor:
            break
        style.keycap(surface, 4, row, str(index + 1),
                     _trunc(concern.title, left_width - 10),
                     command=str(index + 1))
        surface.text(7, row + 1, _trunc(concern.reason, left_width - 6),
                     C["ash"], C["ink"])
        surface.text(7, row + 2, _trunc(concern.said(), left_width - 6),
                     C["bone"], C["ink"])
        if pitch >= 4 and concern.basis:
            surface.text(9, row + 3,
                         _trunc("— " + concern.basis, left_width - 8),
                         C["dim"], C["ink"])

    # The physical hall remains visible beneath the advice.
    waiting_top = min(height - 9, 20)
    people = waiting(b)
    style.bar(surface, 2, waiting_top, left_width + 2,
              f" WAITING ON YOU · IN THE HALL"
              f"{'  ' + str(len(people)) if people else ''}",
              fg=C["bone"], bg=C["faint"])
    room = max(0, height - waiting_top - 3)
    if not people:
        surface.text(4, waiting_top + 2, "Nobody; the hall is empty.",
                     C["ash"], C["ink"])
    for offset, person in enumerate(people[:room]):
        row = waiting_top + 1 + offset
        who_width = max(14, left_width // 2 - 2)
        surface.text(4, row, _trunc(person["who"], who_width),
                     C["clay"], C["ink"])
        fact = _trunc(person["fact"], max(10, left_width - who_width - 7))
        surface.text(6 + who_width, row, fact, C["dim"], C["ink"])

    # Inbox and navigation rail.
    rx = divider + 2
    rw = width - rx - 2
    unread = [item for item in b.get("stack", []) if not item["read"]]
    style.bar(surface, rx, 5, rw, " INBOX", fg=C["bone"], bg=C["faint"])
    surface.text(rx + 1, 7,
                 f"{len(unread)} unread · {len(b.get('stack', []))} on the pile",
                 C["clay"], C["ink"])
    if unread:
        oldest = max(unread, key=lambda item: item["age"])
        surface.text(rx + 1, 8, _trunc(
            "oldest: " + render.actor_name(oldest["sender"], b.get("house")), rw - 2),
            C["ash"], C["ink"])
    style.keycap(surface, rx + 1, 9, "s", "Open Inbox")

    y = 11
    for heading, entries in GROUPS:
        if y >= height - 3:
            break
        surface.text(rx, y, heading, C["dim"], C["ink"])
        y += 1
        column = rx + 1
        for key, label in entries:
            if y >= height - 2:
                break
            target = next((target for door_key, _name, target in DOORS
                           if door_key == key), "")
            needed = len(key) + len(label) + 4
            if column + needed > rx + rw:
                y += 1
                column = rx + 1
            column += style.keycap(surface, column, y, key, label,
                                   enabled=target in BUILT) + 2
        y += 1

    style.footer(surface, [
        style.FooterAction("SPACE", "end the fortnight", command="space"),
        style.FooterAction("ctrl-s", "save"),
        style.FooterAction("ctrl-o", "reload"),
        style.FooterAction(":", "command"),
        style.FooterAction("\\", "read out"),
        style.FooterAction("Q", "leave the hall", command="q"),
    ])
    return surface.interactive()
