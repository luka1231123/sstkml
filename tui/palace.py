"""The palace: the one room the king is actually in (UI/UX spec 16).

Justice, the House and Relations were three windows that all described the same
place. A man stood in the hall waiting for judgement, a brother waited for a
post, an envoy waited for an answer -- and the game put each of them behind a
different door, so the king never saw his own floor. Worse, each of the three
had a different idea of how you chose a thing and acted on it: Justice numbered
petitions, the House wanted a digit for a person and then a letter for a post,
Relations offered no orders at all.

So this is one room with three views and an office arrangement. The picture at
the top is not decoration: **the figures on the floor are who is present**.
The list below is the complete record, so a relative abroad or a distant court
does not acquire a body merely because the king can select its row. A selected
person at court is marked at their feet; a selected absence says AWAY.
Audience, Household, Envoys and Offices each move different furniture onto the
same floor.

Appointing was the worst of the three and is worth stating separately. It used
to be a digit for a person and then one of twenty-six letters for a post, with
nothing on screen saying that the letters were live or which person they would
act on. Here it is two steps that each say what they are: choose the man, press
`o`, and the list becomes the posts with his name in the heading until he is
placed or the choice is abandoned.
"""
from __future__ import annotations

import dataclasses
import textwrap

import registry
from tui import art, render, style, workbench
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

VIEWS = (("people", "PEOPLE"), ("offices", "OFFICES"),
         ("household", "HOUSE"), ("audience", "AUDIENCE"),
         ("justice", "JUSTICE"), ("advisers", "ADVICE"))

# Which context's orders each view offers, so a claim in the registry and a
# control on this screen cannot drift apart.
CONTEXT_OF = {"court": "justice", "house": "house", "relations": "relations"}

VERDICTS = (("f", "for", "for the petitioner"),
            ("a", "against", "against him"),
            ("s", "split", "split the difference"),
            ("d", "defer", "defer it"))

GIFT_STEP = 10
DUE_STEP = 25

# The old room spent twenty rows drawing the same throne before it disclosed
# whether anybody was there. Eleven rows are enough for architecture, a
# state-line and actual figures. At the minimum window size those eleven rows
# are still surrendered before controls are: below this threshold the room
# contracts to the workbench, not to a useless miniature.
FULL_SCENE = 11
SHORT_SCENE = FULL_SCENE


def scene_rows(height: int) -> int:
    if height >= FULL_SCENE + 12:
        return FULL_SCENE
    return 0


FIGURE_OF = {"court": art.PETITIONER, "house": art.KIN,
             "relations": art.BEARER}
PAINT_OF = {"court": art.PETITIONER_PAINT, "house": art.KIN_PAINT,
            "relations": art.BEARER_PAINT}


# Furniture is deliberately small. The room is recognizable, but its mode is
# carried by the things placed on the floor instead of one immutable palace
# picture looming over every decision.
JUDGEMENT_SEAT = (
    "    ◈        ",
    "  ╭───╮      ",
    "  │░▓░│      ",
    "  ╰─┬─╯      ",
    "  ══╧══      ",
    "             ",
    "             ",
)

HOUSE_STATIONS = (
    " OFFICES     ",
    " ┌─┐   ┌─┐  ",
    " │■│   │□│  ",
    " └┬┘   └┬┘  ",
    " ═╧═════╧═  ",
    "             ",
    "             ",
)

ENVOY_GATE = (
    " TABLETS     ",
    " ╔═╤═══╤═╗  ",
    " ║ ▤   ▤ ║  ",
    " ║ ▤   ▤ ║  ",
    " ╚═╧═══╧═╝  ",
    "             ",
    "             ",
)


def _court_place(b: dict) -> str:
    """The place in which the ruler's audience room physically stands."""
    house = b.get("house", {})
    ruler = house.get("ruler")
    person = next((member for member in house.get("members", [])
                   if member.get("id") == ruler), None)
    return str((person or {}).get("location") or b.get("seat") or "seat")


def _present_rows(b: dict, listing: str,
                  rows: list[workbench.Row]) -> list[tuple[int, workbench.Row]]:
    """Rows whose people are actually standing in the room.

    The full list remains available below. Presence is intentionally a stricter
    claim: correspondence with a court does not conjure its envoy onto the
    floor, and a prince posted abroad is recorded but absent.
    """
    by_id = {row.id: row for row in rows}
    present: set[str]
    if listing == "court":
        present = {
            item["id"] for item in b.get("justice", {}).get("petitions", [])
            if item.get("present", True)
        }
    elif listing == "house":
        place = _court_place(b)
        present = {
            person["id"] for person in _people(b)
            if person.get("at_court",
                          str(person.get("location", "")) == place)
        }
    elif listing == "relations":
        present = {
            relation["other"] for relation in b.get("relations", [])
            if relation.get("envoy_present") or relation.get("at_court")
        }
    else:
        present = set(by_id)
    return [(number, row) for number, row in enumerate(rows, 1)
            if row.id in present and row.id in by_id]


def _scene_caption(b: dict, listing: str, rows: list[workbench.Row],
                   standing: list[tuple[int, workbench.Row]]) -> str:
    present = len(standing)
    if listing == "court":
        heard = sum(1 for item in b.get("justice", {}).get("petitions", [])
                    if item.get("heard"))
        advisers = len(_advisers(b))
        return (f"AUDIENCE · {_count(present, 'MATTER')} PRESENT · "
                f"{heard} HEARD · {_count(advisers, 'ADVISER')}")
    if listing == "house":
        vacant = sum(not institution.get("head")
                     for institution in b.get("institutions", []))
        away = max(0, len(rows) - present)
        return (f"HOUSEHOLD · {present} AT COURT · {away} AWAY · "
                f"{_count(vacant, 'OFFICE')} VACANT")
    if listing == "relations":
        return (f"ENVOYS · {present} PRESENT · "
                f"{_count(max(0, len(rows) - present), 'COURT')} BY TABLET")
    vacant = sum(row.mark == "!" for row in rows)
    return (f"OFFICES · {_count(vacant, 'VACANCY', 'VACANCIES')} · "
            f"{len(rows) - vacant} HELD")


def _count(number: int, singular: str, plural: str = "") -> str:
    return f"{number} {singular if number == 1 else plural or singular + 'S'}"


def _advisers(b: dict) -> list[dict]:
    """Model-backed court characters exposed across the Belief boundary.

    This surface never calls a model and never invents a judgement. It renders
    only the identities/presence supplied by the controller's Belief-grounded
    adviser layer, keeping generated interpretation visibly separate from
    engine facts.
    """
    raw = b.get("court_advisers", [])
    if not isinstance(raw, list):
        return []
    advisers = []
    for entry in raw:
        if isinstance(entry, str):
            advisers.append({"id": entry, "name": entry, "present": True})
        elif isinstance(entry, dict) and entry.get("present", True):
            advisers.append(entry)
    return advisers


def _adviser_voice(b: dict, subject: str) -> tuple[str, str, str] | None:
    """Return an already-generated voice for this subject, never hidden fact."""
    raw = b.get("court_advice", [])
    if isinstance(raw, dict):
        raw = raw.get(subject, raw if raw.get("subject") == subject else {})
        raw = [raw] if isinstance(raw, dict) and raw else []
    if not isinstance(raw, list):
        return None
    voice = next((entry for entry in raw
                  if isinstance(entry, dict)
                  and entry.get("subject") in (None, "", subject)
                  and entry.get("text")), None)
    if voice is None:
        return None
    name = str(voice.get("adviser_name") or voice.get("name") or "An adviser")
    return name, str(voice["text"]), str(voice.get("basis") or "")


def _draw_furniture(surface: Surface, x: int, y: int, listing: str) -> None:
    furniture = {
        "court": JUDGEMENT_SEAT,
        "house": HOUSE_STATIONS,
        "relations": ENVOY_GATE,
    }.get(listing, JUDGEMENT_SEAT)
    art.draw(surface, x, y, furniture, lit=C["bone"], mid=C["sand"],
             dark=C["faint"], edge=C["gold"])


def _draw_stations(surface: Surface, x: int, y: int, width: int, bottom: int,
                   numbered: list[tuple[int, workbench.Row]],
                   selected: str) -> None:
    """Office stools: occupied is solid, vacant is a visible empty station."""
    step = 9
    room = max(0, width // step)
    visible = numbered[:room]
    for place, (number, row) in enumerate(visible):
        at = x + place * step
        vacant = row.mark == "!"
        here = row.id == selected
        surface.text(at + 1, y, f"[{number}]", C["bone"] if here else C["dim"],
                     C["ink"])
        surface.text(at, y + 1, "┌─────┐", C["gold"], C["ink"])
        surface.text(at, y + 2, "│  □  │" if vacant else "│  ■  │",
                     C["blood"] if vacant else C["clay"], C["ink"])
        surface.text(at, y + 3, "└──┬──┘", C["sand"], C["ink"])
        surface.text(at, y + 4, " VACANT" if vacant else "  HELD ",
                     C["blood"] if vacant else C["dim"], C["ink"])
        if here:
            surface.text(at, bottom, "▀" * 7, C["flame"], C["ink"])
        surface.link(at, y, 7, 5, f"pick:{row.id}")
    if len(numbered) > room:
        surface.text(x + room * step, y + 2, f"+{len(numbered) - room}",
                     C["dim"], C["ink"])


def _draw_scene(surface: Surface, x: int, y: int, width: int, rows: int,
                view: str, queue: list[workbench.Row], selected: str,
                b: dict | None = None, listing: str = "") -> None:
    """A compact audience room whose occupants and furniture are the state."""
    if rows <= 0:
        return
    b = b or {}
    listing = listing or view
    bottom = y + rows - 1
    surface.text(x, y, art.band(art.CORNICE, width), C["gold"], C["ink"])
    surface.text(x, bottom, art.floor(width, 2), C["faint"], C["ink"])

    body = rows - 2
    pillar_rows = art.pillar(body)
    art.paint(surface, x, y + 1, pillar_rows, art.pillar_paint(body))
    right_pillar = x + width - len(pillar_rows[0])
    art.paint(surface, right_pillar, y + 1, pillar_rows,
              art.pillar_paint(body))

    standing = _present_rows(b, listing, queue)
    caption = _scene_caption(b, listing, queue, standing)
    surface.text(x + 7, y + 1, caption[:max(0, width - 14)],
                 C["bone"], C["ink"])
    selected_here = any(row.id == selected for _number, row in standing)
    if selected and not selected_here and listing != "post":
        flag = "CHOSEN: AWAY"
        surface.text(x + width - len(flag) - 7, y + 2, flag,
                     C["blood"], C["ink"])

    floor_x = x + 22
    if listing == "post":
        _draw_furniture(surface, x + 7, y + 3, "court")
        _draw_stations(surface, floor_x, y + 2,
                       max(0, right_pillar - 2 - floor_x), bottom,
                       list(enumerate(queue, 1)), selected)
        return

    _draw_furniture(surface, x + 7, y + 3, listing)

    # One standing figure per listed matter, retaining the list's absolute
    # number even when people before it are away.
    figure = FIGURE_OF.get(view, art.PETITIONER)
    mask = PAINT_OF.get(view, art.PETITIONER_PAINT)
    step = art.FIGURE_WIDTH + 1
    room = max(0, (right_pillar - 2 - floor_x) // step)
    if len(standing) > room and room:
        room -= 1       # the last standing place goes to saying who is missing
    stand = bottom - len(figure)
    for place, (number, row) in enumerate(standing[:room]):
        at = floor_x + place * step
        bowed = row.mark == "✓"
        surface.fill(at, stand, art.FIGURE_WIDTH, len(figure), " ")
        art.paint(surface, at, stand,
                  art.BOWED if bowed else figure,
                  art.BOWED_PAINT if bowed else mask)
        here = row.id == selected
        if here:
            surface.text(at, bottom, "▀" * art.FIGURE_WIDTH,
                         C["flame"], C["ink"])
        label = f"[{number}]"
        surface.text(at + (art.FIGURE_WIDTH - len(label)) // 2, stand - 1,
                     label, C["bone"] if here else C["dim"], C["ink"])
        surface.link(at, stand - 1, art.FIGURE_WIDTH, len(figure) + 1,
                     f"pick:{row.id}")
    if len(standing) > room:
        surface.text(floor_x + room * step, stand + 2,
                     f"+{len(standing) - room}", C["dim"], C["ink"])
        surface.text(floor_x + room * step, stand + 3, "more",
                     C["dim"], C["ink"])
    if not standing:
        empty = {
            "court": "no petitioner stands before you.",
            "house": "no one of the house is at court.",
            "relations": "no envoy is in the room.",
        }.get(listing, "the floor is empty.")
        surface.text(floor_x, stand + 3, empty[:max(0, width - 30)],
                     C["ash"], C["ink"])
    if room:
        art.paint(surface, right_pillar - 7, bottom - len(art.BRAZIER),
                  art.BRAZIER, art.BRAZIER_PAINT)


# --- the court ----------------------------------------------------------------

def _name(actor: str, b: dict) -> str:
    return render.actor_name(actor, b.get("house"))


def _where(place: str) -> str:
    return place.split(":", 1)[-1].replace("_", " ") or "the road"


def petitioners(b: dict) -> list[dict]:
    """Bands of displaced people waiting at the gate for an answer."""
    return [c for c in b.get("cohorts", ())
            if c.get("status") == "petitioning"]


def _court(b: dict) -> list[workbench.Row]:
    rows = []
    for band in petitioners(b):
        rows.append(workbench.Row(
            band["id"],
            (("reception", "bone"),
             (f"{band['people']:,} from {_where(band.get('origin', ''))}", "clay"),
             (f"hunger {band.get('hunger', 0)}", "dim"),
             ("at the gate", "flame")),
            mark="!"))
    for item in b.get("justice", {}).get("petitions", []):
        parties = f"{_name(item['petitioner'], b)} v {_name(item['against'], b)}"
        rows.append(workbench.Row(
            item["id"],
            ((item["kind"], "bone"), (parties, "clay"),
             (f"{item['waiting']} fn", "dim"),
             ("heard" if item["heard"] else "not heard",
              "barley" if item["heard"] else "flame")),
            mark="✓" if item["heard"] else ""))
    return rows


def _court_item(b: dict, chosen: str) -> dict | None:
    return next((petition
                 for petition in b.get("justice", {}).get("petitions", [])
                 if petition["id"] == chosen), None)


def _evidence_lines(b: dict, item: dict, width: int) -> list[tuple[str, str]]:
    """The complete heard claim and answer, compact enough for stacked Court."""
    width = max(12, width)
    lines: list[tuple[str, str]] = [
        (f"{item['kind']} · heard · waiting {item['waiting']} fn", "bone"),
        (f"CLAIM · {_name(item['petitioner'], b)}", "barley"),
    ]
    lines.extend(
        (line, "clay")
        for line in textwrap.wrap(
            item["claim_text"] or "—", width,
            break_long_words=False, break_on_hyphens=False)
    )
    lines.append((f"ANSWER · {_name(item['against'], b)}", "wine"))
    lines.extend(
        (line, "clay")
        for line in textwrap.wrap(
            item["counter_text"] or "—", width,
            break_long_words=False, break_on_hyphens=False)
    )
    return lines


def _court_detail(b: dict, chosen: str,
                  width: int = 44) -> list[tuple[str, str]]:
    band = next((c for c in petitioners(b) if c["id"] == chosen), None)
    if band is not None:
        eats = band["people"] * band.get("ration_per_head", 10)
        return [
            (f"{band['people']:,} people from {_where(band.get('origin', ''))}",
             "bone"),
            (f"hungry {band.get('hunger', 0)} fortnights · "
             f"grievance {band.get('grievance', 0)}", "clay"),
            (f"they would eat {eats:,} qa a fortnight", "clay"),
            ("", "clay"),
            ("Take them in and they are yours to feed. Turn them away and "
             "they go hungry to the next gate, or take what they need at "
             "this one.", "ash"),
        ]
    item = next((p for p in b.get("justice", {}).get("petitions", [])
                 if p["id"] == chosen), None)
    if item is None:
        return [("Nobody waits for a judgement.", "ash")]
    if item["heard"]:
        # Evidence comes before commentary, precedent, or room atmosphere.
        # These are the words the verdict acts upon and may not be below a
        # clipped detail pane while its keys remain live.
        lines = _evidence_lines(b, item, width)
        lines.append(("", "clay"))
    else:
        lines = [
            (f"{item['kind']} · waiting {item['waiting']} fortnights", "bone"),
            (f"{_name(item['petitioner'], b)} petitions against "
             f"{_name(item['against'], b)}", "clay"),
            ("", "clay"),
        ]
    voice = _adviser_voice(b, chosen)
    if voice:
        name, words, basis = voice
        lines.append((f"{name}, at the dais:", "gold"))
        lines.extend(_wrapped(words, 3, 30))
        if basis:
            lines.extend(_wrapped(f"heard from: {basis}", 2, 30))
        lines.append(("", "clay"))
    elif _advisers(b):
        names = ", ".join(str(adviser.get("name") or adviser.get("id"))
                          for adviser in _advisers(b))
        lines.append((f"at the dais: {names}", "gold"))
        lines.append(("They have not yet spoken.", "ash"))
        lines.append(("", "clay"))
    precedent = item.get("precedent")
    if precedent:
        lines.append((f"They cite {precedent['document_ref']}:", "sand"))
        lines.append((f"in another {precedent['kind']} case you ruled "
                      f"{precedent['verdict']}.", "sand"))
        lines.append(("", "clay"))
    if not item["heard"]:
        lines.append(("You know their names and the nature of", "ash"))
        lines.append(("the quarrel. Neither man has been heard.", "ash"))
    return lines


def _wrapped(text: str, rows: int, width: int = 44) -> list[tuple[str, str]]:
    return [(line, "clay")
            for line in textwrap.wrap(text or "—", width)[:rows]]


RECEPTIONS = (("t", "settle", "take them in"),
              ("y", "refuse", "turn them away"))


def _court_controls(b: dict, chosen: str, hours: int) -> list[workbench.Control]:
    band = next((c for c in petitioners(b) if c["id"] == chosen), None)
    controls = [workbench.affordable(workbench.Control(
        "receive_cohort", key, label=label, enabled=band is not None,
        why="nobody waits at the gate", command=f"receive:{decision}"), hours)
        for key, decision, label in RECEPTIONS]
    if band is not None:
        return controls
    item = next((p for p in b.get("justice", {}).get("petitions", [])
                 if p["id"] == chosen), None)
    heard = bool(item and item["heard"])
    controls += [workbench.affordable(workbench.Control(
        "hear_petition", registry.BY_ID["hear_petition"].mnemonic,
        enabled=bool(item) and not heard,
        why="already heard" if heard else "nobody waits"), hours)]
    for key, verdict, label in VERDICTS:
        controls.append(workbench.Control(
            "rule_petition", key, label=label, enabled=heard,
            why="hear him first" if item is not None else "nobody waits",
            command=f"verdict:{verdict}"))
    return controls


# --- the house ----------------------------------------------------------------

def _people(b: dict) -> list[dict]:
    house = b.get("house", {})
    members = [p for p in house.get("members", [])
               if p["alive"] and p["id"] != house.get("ruler")]
    members.sort(key=lambda person: (-person["age_years"], person["id"]))
    return members


def _post_name(post: str, b: dict) -> str:
    for institution in b.get("institutions", []):
        if institution["id"] == post:
            return institution["name"]
    return post.replace(":", " of ").replace("_", " ")


def _house(b: dict) -> list[workbench.Row]:
    rows = []
    for person in _people(b):
        claims = []
        if person.get("named_heir"):
            claims.append("NAMED HEIR")
        elif person.get("heir_rank"):
            claims.append(f"heir {person['heir_rank']}")
        if person.get("expecting"):
            claims.append("with child")
        post = person.get("post") or ""
        rows.append(workbench.Row(
            person["id"],
            ((person["name"], "bone"),
             (person["competence"], "dim"),
             (_post_name(post, b) if post else "no post",
              "clay" if post else "ash"),
             (", ".join(claims) or "—",
              "gold" if person.get("named_heir") else "dim")),
            mark="*" if person.get("named_heir") else ""))
    return rows


def _posts(b: dict) -> list[workbench.Row]:
    rows = []
    for institution in b.get("institutions", []):
        head = institution["head"]
        rows.append(workbench.Row(
            institution["id"],
            ((institution["name"], "bone"),
             (institution["kind"], "dim"),
             (_name(head, b) if head else "vacant",
              "clay" if head else "blood"),
             ("", "dim")),
            mark="" if head else "!"))
    return rows


def _household(b: dict) -> list[workbench.Row]:
    seat = _court_place(b)
    at_court = {p["id"] for p in _people(b) if p.get("location") == seat}
    return [row for row in _house(b) if row.id in at_court]


def _adviser_rows(b: dict) -> list[workbench.Row]:
    advisers = {p["id"] for p in _people(b) if p.get("post")}
    advisers |= {str(p.get("id", "")) for p in _advisers(b)}
    return [row for row in _house(b) if row.id in advisers]


def _audience(b: dict) -> list[workbench.Row]:
    waiting = {p["id"] for p in b.get("justice", {}).get("petitions", [])
               if p.get("present", True) and not p.get("heard")}
    return [row for row in _court(b) if row.id in waiting]


def _post_detail(b: dict, chosen: str) -> list[tuple[str, str]]:
    post = next((item for item in b.get("institutions", [])
                 if item["id"] == chosen), None)
    if post is None:
        return [("No office is selected.", "ash")]
    return [(post["name"], "gold"), (post["kind"], "dim"),
            ("held by " + (_name(post["head"], b) if post["head"] else "nobody"),
             "clay" if post["head"] else "blood")]


def _house_detail(b: dict, chosen: str) -> list[tuple[str, str]]:
    person = next((p for p in _people(b) if p["id"] == chosen), None)
    if person is None:
        return [("No adult of the house is available.", "ash")]
    post = person.get("post") or ""
    lines = [
        (person["name"], "bone"),
        (f"{person['age_years']} years · {person['health']} · "
         f"{person['loyalty']}", "clay"),
        (f"at {person['location'].replace('_', ' ')}", "sky"),
        ("", "clay"),
        (f"post: {_post_name(post, b) if post else 'none'}",
         "clay" if post else "ash"),
        (f"wants: {person.get('agenda') or 'nothing recorded'}", "dim"),
        (f"interests: {', '.join(person.get('interests', [])) or 'none'}",
         "dim"),
    ]
    if person.get("married_to_court"):
        lines.append((f"married to {_name(person['married_to_court'], b)}",
                      "wine"))
    omens = b.get("house", {}).get("omens", [])
    if omens:
        lines.append(("", "clay"))
        lines.append(("RECENT OMENS", "gold"))
        for omen in omens[-3:]:
            state = "defied" if omen["defied"] else (
                "published" if omen["published"] else "held")
            lines.append((f"{omen['question']} · {state}", "wine"))
    return lines


def _house_controls(b: dict, chosen: str, hours: int,
                    choosing: str) -> list[workbench.Control]:
    person = next((p for p in _people(b) if p["id"] == chosen), None)
    if choosing == "post":
        return [workbench.Control(
            "place_person", "enter", label="place him in the chosen post",
            command="place"),
            workbench.Control("", "esc", label="think better of it",
                              command="cancel")]
    posted = bool(person and person.get("post"))
    return [
        workbench.affordable(workbench.Control(
            "place_person", registry.BY_ID["place_person"].mnemonic,
            label="give him a post", enabled=person is not None,
            why="choose a man first", command="choose-post"), hours),
        workbench.affordable(workbench.Control(
            "dismiss_person", registry.BY_ID["dismiss_person"].mnemonic,
            label="dismiss him from it", enabled=posted,
            why="he holds no post"), hours),
        workbench.affordable(workbench.Control(
            "name_heir", registry.BY_ID["name_heir"].mnemonic,
            enabled=person is not None, why="choose a man first"), hours),
        workbench.Control(
            "dispatch_letter", "m", label="propose marriage by letter",
            enabled=person is not None, why="choose a person first",
            command="letter-marriage"),
    ]


# --- relations ----------------------------------------------------------------

def _relations(b: dict) -> list[workbench.Row]:
    rows = []
    for relation in b.get("relations", []):
        owed = relation["unanswered"]
        rows.append(workbench.Row(
            relation["other"],
            ((_name(relation["other"], b), "bone"),
             (relation["esteem"], "clay"),
             (f"{owed} unanswered" if owed else "answered",
              "blood" if owed else "barley"),
             (f"{relation['obligation']:,}", "gold")),
            mark="!" if owed else ""))
    return rows


def _relations_detail(b: dict, chosen: str, amount: int,
                      good: str) -> list[tuple[str, str]]:
    relation = next((r for r in b.get("relations", [])
                     if r["other"] == chosen), None)
    if relation is None:
        return [("No foreign relationship is recorded.", "ash")]
    revenue = b.get("revenue", {})
    lines = [
        (_name(relation["other"], b), "bone"),
        (f"at {relation['place'].replace('_', ' ')}", "sky"),
        ("", "clay"),
        (f"their regard: {relation['esteem']}", "clay"),
        (f"we claim to be their {relation['status_claim']}", "dim"),
        (f"they claim to be our {relation['their_status_claim']}", "dim"),
        (f"obligation on the tablets: {relation['obligation']:,}", "gold"),
        (f"last gift from us: {relation['last_gift_from_us']:,}", "dim"),
        (f"last gift from them: {relation['last_gift_from_them']:,}", "dim"),
        (f"best rival gift reported: {relation['best_known_rival_gift']:,}",
         "dim"),
        (f"letters awaiting answer: {relation['unanswered']}",
         "blood" if relation["unanswered"] else "dim"),
    ]
    if relation.get("seeking_patron"):
        lines.append(("They are seeking another patron.", "blood"))
    lines.append(("", "clay"))
    lines.append(("Gifts and marriage proposals are written at the Desk.",
                  "gold"))
    lines.append((f"harbour due {revenue.get('harbour_rate', 0)}/1000 · Trade",
                  "sand"))
    return lines


def _relations_controls(b: dict, chosen: str, hours: int, amount: int,
                        good: str) -> list[workbench.Control]:
    return [
        workbench.Control(
            "dispatch_letter", "g", label="offer a gift by letter",
            enabled=bool(chosen), why="choose a court",
            command="letter-gift"),
        workbench.Control(
            "dispatch_letter", "m", label="propose marriage by letter",
            enabled=bool(chosen), why="choose a court",
            command="letter-marriage"),
    ]


# --- the window ---------------------------------------------------------------

def controls_for(b: dict, view: str, chosen: str = "", hours: int = 0,
                 choosing: str = "", person: str = "", amount: int = 0,
                 good: str = "copper") -> list[workbench.Control]:
    """Every order this view offers, whether or not it can be given now.

    One list, read both by the screen that draws it and by the guard that
    checks it against `registry.in_context`. A control's `command` is what
    clicking it says, and for several of them that is not `do:<id>` -- four
    verdicts are one action, and appointing begins by changing the list rather
    than by giving an order -- so the action a control belongs to cannot be
    recovered from the drawn screen, and the guard has to read this instead.
    """
    if view in {"court", "audience", "justice"}:
        return _court_controls(b, chosen, hours)
    if view in {"house", "people", "household", "advisers"}:
        return _house_controls(b, person or chosen, hours, choosing)
    if view == "offices":
        return []
    return _relations_controls(b, chosen, hours, amount, good)


HEADERS = {
    "court": (("matter", "the parties", "waiting", "state"), (11, 26, 6, 8)),
    "house": (("name", "they are", "post", "claim"), (17, 10, 16, 7)),
    "relations": (("court", "regard", "letters", "owed"), (19, 10, 12, 9)),
    "post": (("post", "kind", "who holds it", ""), (21, 10, 17, 2)),
}
HEADERS.update({"people": HEADERS["house"], "household": HEADERS["house"],
                "advisers": HEADERS["house"], "offices": HEADERS["post"],
                "audience": HEADERS["court"], "justice": HEADERS["court"]})


LISTINGS = {"court": _court, "house": _house, "relations": _relations,
            "post": _posts, "people": _house, "household": _household,
            "advisers": _adviser_rows, "offices": _posts,
            "audience": _audience, "justice": _court}


def listing_rows(b: dict, listing: str) -> list[workbench.Row]:
    """Everything a view lists, whether or not it fits on the screen.

    The controller needs this and not the rows it can see: arrow keys that walk
    only the visible rows cannot reach a man below the fold, which is the same
    complaint whether the list is short because the window is small or because
    the throne behind it got taller.
    """
    return LISTINGS.get(listing, _court)(b)


def _detail_geometry(width: int, widths: tuple[int, ...],
                     detail_min: int = 30) -> tuple[bool, int]:
    """Mirror the workbench split so evidence wraps to its actual pane."""
    natural = sum(abs(spec) for spec in widths) + 2 * len(widths) + 2
    stacked = width < 68 or natural > width - detail_min - 6
    if stacked:
        return True, max(12, width - 5)
    list_width = max(30, min(natural, width - detail_min - 6))
    return False, max(12, width - (list_width + 4) - 2)


def _detail_capacity(rows: list[workbench.Row],
                     controls: list[workbench.Control],
                     widths: tuple[int, ...], width: int, height: int,
                     scene: int, note: str, detail_min: int = 30) -> int:
    """Rows the workbench will actually expose in its detail pane."""
    stacked, _detail_width = _detail_geometry(width, widths, detail_min)
    top = 3 + scene
    footer_rows = workbench.rows_needed(controls, 0, width)
    available = height - top - 4 - footer_rows - (2 if note else 0)
    if stacked:
        room = max(1, min(available - 4, max(available // 3, 5)))
        return max(0, available - room - 1)
    detail_floor = height - 2 - footer_rows - (1 if note else 0)
    return max(0, detail_floor - (top + 1))


def compose(b: dict, view: str = "court", selected: str = "",
            scroll: int = 0, hours: int = 0, choosing: str = "",
            person: str = "", amount: int = 0, good: str = "copper",
            notice: str = "", width: int = 96,
            height: int = 34) -> InteractiveScreen:
    """`selected` is the row of whatever is listed; `person` is the man being
    placed, which is a different thing the moment the list turns to posts."""
    listing = "post" if (view in {"house", "people", "household", "advisers"}
                          and choosing == "post") else view
    rows = listing_rows(b, listing)
    chosen = next((row.id for row in rows if row.id == selected),
                  rows[0].id if rows else "")

    who = person if choosing == "post" else chosen
    headers, widths = HEADERS[listing]
    _stacked, detail_width = _detail_geometry(width, widths)
    if view in {"court", "audience", "justice"}:
        detail = _court_detail(b, chosen, detail_width)
    elif view in {"house", "people", "household", "advisers"}:
        detail = _house_detail(b, who)
    elif view == "offices":
        detail = _post_detail(b, chosen)
    else:
        detail = _relations_detail(b, chosen, amount, good)
    controls = controls_for(b, view, chosen, hours, choosing, person=who,
                            amount=amount, good=good)

    band = scene_rows(height)
    queue = rows
    scene_listing = {"people": "house", "household": "house",
                     "advisers": "house", "audience": "court",
                     "justice": "court", "offices": "post"}.get(listing, listing)

    title = "THE COURT — RELATIONS" if view == "relations" else "THE COURT"
    note = "↑↓ choose   Enter open   Tab view   [c] counsel"
    if choosing == "post":
        named = next((p["name"] for p in _people(b) if p["id"] == person), "")
        title = f"THE COURT — A POST FOR {named.upper()}"
        note = "choose a post, or [esc] to think better of it"

    # Once testimony is heard, the room yields architecture before it yields
    # the words a verdict acts upon. Supported sizes fit ordinary cases in a
    # compact stacked pane; exceptionally long evidence leaves verdicts
    # visibly disabled rather than asking the king to judge hidden text.
    if view in {"court", "audience", "justice"}:
        petition = _court_item(b, chosen)
        if petition is not None and petition["heard"]:
            evidence_rows = len(_evidence_lines(b, petition, detail_width))
            capacity = _detail_capacity(
                rows, controls, widths, width, height, band, note)
            if band and evidence_rows > capacity:
                band = 0
                capacity = _detail_capacity(
                    rows, controls, widths, width, height, band, note)
            if evidence_rows > capacity:
                controls = [
                    dataclasses.replace(
                        control, enabled=False,
                        why="enlarge the Court to see all evidence")
                    if control.action_id == "rule_petition" else control
                    for control in controls
                ]

    def draw(surface, x, y, room, rows_available):
        _draw_scene(surface, x, y, room, rows_available, view, queue, chosen,
                    b=b, listing=scene_listing)

    return workbench.compose(
        title, headers, widths, rows, chosen, detail, controls, hours,
        width, height, scroll, notice,
        empty=_empty(listing), views=VIEWS, view=view,
        note=note, scene=draw, scene_rows=band, detail_min=30)


def _empty(listing: str) -> str:
    return {
        "court": "nobody waits for a judgement.",
        "house": "no adult of the house waits on you.",
        "relations": "no foreign court is in correspondence.",
        "post": "there is no post to give.",
        "people": "no person is recorded at this court.",
        "household": "no member of the household is at court.",
        "advisers": "no adviser holds a court office.",
        "offices": "there is no court office.",
        "audience": "nobody waits in audience.",
        "justice": "no petition is on the docket.",
    }[listing]
