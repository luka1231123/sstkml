"""The hall: the hub, and the one window given a setting (D33, D34).

It answers the only two questions that are about a situation rather than about
data — where am I, and how much of the fortnight is left — and it does the one
thing that turns a management screen into a court: it shows **people waiting**
rather than counters.

The rules from D19 and D31 hold here as everywhere. A man waiting in the hall
says what is true of him and never what it means. Nobody in this room advises,
warns, ranks, or tells the king what to do about it. That Yadudanu has stood
here four fortnights running is the whole message.

Reads Belief and nothing else.
"""
from __future__ import annotations

from tui import render, style
from tui.grid import INDEX, Screen, Surface, sparkline

C = INDEX

# The ways out of the hall. Every window is reachable from here by keyboard,
# always, because a player who has closed one must never be stranded (D33).
DOORS = (
    ("s", "the stack", "stack"),
    ("d", "the desk", "desk"),
    ("r", "the roll", "roll"),
    ("t", "the stores", "stores"),
    ("l", "the land", "land"),
    ("m", "the muster", "muster"),
    ("o", "the oaths", "oaths"),
    ("a", "the tablet house", "archive"),
    ("v", "the altar", "altar"),
    ("h", "the house", "house"),
    ("w", "the known world", "world"),
    ("c", "counsel", "counsel"),
    ("?", "help", "help"),
)

# Which of them open. A door that is not built is drawn in ash and marked with
# a dot, never removed: a player who can see the shape of the game and be told
# "not yet" has been told the truth, and a menu that quietly shrinks has not.
# The controller reads this rather than keeping its own list.
BUILT = frozenset({"stack", "roll", "stores", "muster", "oaths", "land",
                   "house", "help", "desk", "archive", "altar", "world",
                   "counsel"})


def _trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def waiting(b: dict) -> list[dict]:
    """Who is standing in the hall, and the plain fact that put them there.

    Ordered by how long they have been waiting, not by importance, because
    ranking them would be advice.
    """
    people: list[dict] = []

    for group in b["groups"]:
        weeks = group["arrears_weeks"]
        if weeks < 1:
            continue
        people.append({
            "who": group["member_name"] or group["name"],
            "for": group["name"],
            "fact": f"{weeks} fortnight{'s' if weeks != 1 else ''} unpaid",
            "weight": weeks,
            "tone": "blood" if weeks >= 4 else "dim",
        })

    unread = [item for item in b["stack"] if not item["read"]]
    for item in unread:
        people.append({
            "who": f"a courier from {render.actor_name(item['sender'], b.get('house'))}",
            "for": render.letter_summary(item["topic"]),
            "fact": "the tablet is unread" if item["age"] == 0
                    else f"unread these {item['age']} fortnights",
            "weight": item["age"],
            "tone": "flame" if item["age"] >= 2 else "dim",
        })

    for summons in b.get("troops", {}).get("summons", []):
        people.append({
            "who": "the herald of the muster",
            "for": f"{summons['required']} men at {summons['place']}",
            "fact": f"{summons['mustered']} have gone",
            "weight": 6,
            "tone": "blood" if summons["mustered"] < summons["required"] else "barley",
        })

    if b.get("plague", {}).get("sickness_at_seat"):
        burials = b["plague"]["burials_at_seat"]
        people.append({
            "who": "the physician",
            "for": "the sickness in the lower town",
            "fact": f"{burials} buried" if burials else "he does not say how many",
            "weight": 8,
            "tone": "blood",
        })

    for oath in b["oaths"]:
        if oath.get("lapsed"):
            people.append({
                "who": "a messenger of " + render.actor_name(
                    oath.get("superior", ""), b.get("house")),
                "for": "an oath that lapsed at the succession",
                "fact": "nobody is bound",
                "weight": 5,
                "tone": "wine",
            })

    people.sort(key=lambda person: -person["weight"])
    return people


def compose(b: dict, width: int = 92, height: int = 30,
            hours_left: int | None = None) -> Screen:
    """The hall as a `Screen`. No IO, no toolkit, testable by cell.

    `hours_left` is the controller's remaining budget for the fortnight. It is
    deliberately not in Belief: `attention` is *derived* from the base less the
    rites and the unrest tax (`engine.systems.attention_available`), and what
    the king has actually spent this morning is a fact about the session, not
    about the world. Left out, the lamp shows the full allowance.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    inner = width - 4

    # --- the title bar and who you are -------------------------------------
    # A filled field across the whole top row, which is how a text-mode program
    # said "this is the application" and is still the fastest way to say it.
    title = (f" {render.actor_name(b['actor'], b.get('house')).upper()} "
             f"OF {b['scenario'].upper()}")
    style.bar(surface, 0, 0, width, title, fg=C["bone"], bg=C["lapis"])
    date = b["date"]
    surface.text(width - 2 - len(date), 0, date, C["sky"], C["lapis"])

    y = 2

    # --- the lamp, which is the fortnight ----------------------------------
    base = b["attention_base"]
    hours = b["attention"] if hours_left is None else max(0, hours_left)
    lit = 0 if base <= 0 else min(12, hours * 12 // base)
    surface.text(3, y, "the lamp", C["dim"], C["ink"])
    style.meter(surface, 13, y, 12, lit)
    surface.text(27, y, f"{hours} of {base} hours", C["clay"], C["ink"])
    sea = "the sea is open" if b["sea_open"] else "the sea is shut"
    surface.text(width - 3 - len(sea), y,
                 sea, C["sky"] if b["sea_open"] else C["ash"], C["ink"])
    y += 2

    # --- who is waiting ----------------------------------------------------
    people = waiting(b)
    style.bar(surface, 2, y, inner, " WAITING ON YOU", fg=C["bone"],
              bg=C["faint"])
    count = f"{len(people)} in the hall " if people else ""
    surface.text(width - 2 - len(count), y, count, C["clay"], C["faint"])
    y += 1

    room = max(0, height - y - 11)
    if not people:
        surface.text(5, y, "nobody. the hall is empty and it is not yet dark.",
                     C["ash"], C["ink"])
        y += 1
    # Three columns, sized off the surface rather than guessed, so nothing
    # collides at eighty columns or wastes the width at a hundred and twenty.
    who_at, fact_width = 5, 22
    for_at = who_at + 34
    fact_at = width - 3 - fact_width
    for_width = max(8, fact_at - for_at - 2)
    for person in people[:room]:
        surface.text(who_at, y, _trunc(person["who"], 32),
                     C[person["tone"]], C["ink"])
        surface.text(for_at, y, _trunc(person["for"], for_width),
                     C["dim"], C["ink"])
        fact = _trunc(person["fact"], fact_width)
        surface.text(width - 3 - len(fact), y, fact, C[person["tone"]], C["ink"])
        y += 1
    if len(people) > room:
        surface.text(5, y, f"and {len(people) - room} more, standing.",
                     C["ash"], C["ink"])
        y += 1

    # --- the state of things, stated and not interpreted -------------------
    y = height - 9
    surface.text(3, y, "─" * inner, C["faint"], C["ink"])
    y += 1
    grain = b["stores"].get("grain", 0)
    surface.text(3, y, f"granary  {render.fmt_good('grain', grain)}",
                 C["barley"], C["ink"])
    surface.text(38, y, f"unrest {b['unrest']}", C["clay"], C["ink"])
    surface.text(54, y, f"legitimacy {b['legitimacy']}", C["clay"], C["ink"])
    series = b.get("store_history", {}).get("grain", [])
    if series:
        line = sparkline(series)
        surface.text(width - 3 - len(line), y, line, C["barley"], C["ink"])
    y += 2

    # --- the ways out ------------------------------------------------------
    # Anchored to the bottom edge and given exactly the rows it has, so the
    # last line is never pushed off the surface by a long door list.
    style.bar(surface, 2, height - 6, inner, " WHERE YOU MAY GO",
              fg=C["bone"], bg=C["faint"])
    door_rows = (height - 5, height - 4, height - 3)
    row, column = 0, 3
    for key, label, target in DOORS:
        entry = f"[{key}] {label}" + ("" if target in BUILT else " ·")
        if column + len(entry) > width - 3:
            row, column = row + 1, 3
        if row >= len(door_rows):
            break
        column += style.keycap(surface, column, door_rows[row], key, label,
                               enabled=target in BUILT) + 3

    # The status bar. Text mode put the keys along the bottom and never made
    # you remember them; there is no reason to be cleverer than that.
    style.bar(surface, 0, height - 1, width,
              " [SPACE] end the fortnight   [\\] read out   [Q] leave the hall",
              fg=C["clay"], bg=C["lapis"])
    unbuilt = sum(1 for _k, _l, target in DOORS if target not in BUILT)
    if unbuilt:
        mark = f"· {unbuilt} not yet built "
        surface.text(width - 1 - len(mark), height - 1, mark,
                     C["dim"], C["lapis"])

    return surface.freeze()
