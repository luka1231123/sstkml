"""The palace: the one room the king is actually in (UI/UX spec 16).

Justice, the House and Relations were three windows that all described the same
place. A man stood in the hall waiting for judgement, a brother waited for a
post, an envoy waited for an answer -- and the game put each of them behind a
different door, so the king never saw his own floor. Worse, each of the three
had a different idea of how you chose a thing and acted on it: Justice numbered
petitions, the House wanted a digit for a person and then a letter for a post,
Relations offered no orders at all.

So this is one room with three views of it. The picture at the top is not
decoration and not a portrait: **the figures on the floor are the queue**. One
man per row of the list, the selected row's man marked at his feet, and
clicking a man selects his business. What changes between the views is who is
standing there -- petitioners, the king's own household, the envoys of foreign
courts -- and what may be ordered.

Appointing was the worst of the three and is worth stating separately. It used
to be a digit for a person and then one of twenty-six letters for a post, with
nothing on screen saying that the letters were live or which person they would
act on. Here it is two steps that each say what they are: choose the man, press
`o`, and the list becomes the posts with his name in the heading until he is
placed or the choice is abandoned.
"""
from __future__ import annotations

import registry
from tui import art, render, style, workbench
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

VIEWS = (("court", "THE COURT"), ("house", "THE HOUSE"),
         ("relations", "RELATIONS"))

# Which context's orders each view offers, so a claim in the registry and a
# control on this screen cannot drift apart.
CONTEXT_OF = {"court": "justice", "house": "house", "relations": "relations"}

VERDICTS = (("f", "for", "for the petitioner"),
            ("a", "against", "against him"),
            ("s", "split", "split the difference"),
            ("d", "defer", "defer it"))

GIFT_STEP = 10
DUE_STEP = 25

# How tall the room may be drawn. Below the first band the throne is cropped
# from the bottom -- the dais goes, the king stays -- and below the second
# there is no room at all, which the specification's contraction order asks
# for: decorative art is the first thing to go (spec 6, "responsive tiers").
# The last two rows of the drawing are its floor, and the room has a floor of
# its own, so the throne is set on the room's rather than carrying a rug that
# stops after twenty-five columns.
SEAT = art.THRONE[:-2]
FULL_SCENE = len(SEAT) + 3
SHORT_SCENE = 8


def scene_rows(height: int) -> int:
    if height >= FULL_SCENE + 14:
        return FULL_SCENE
    if height >= SHORT_SCENE + 12:
        return SHORT_SCENE
    return 0


FIGURE_OF = {"court": art.PETITIONER, "house": art.KIN,
             "relations": art.BEARER}
PAINT_OF = {"court": art.PETITIONER_PAINT, "house": art.KIN_PAINT,
            "relations": art.BEARER_PAINT}


def _draw_scene(surface: Surface, x: int, y: int, width: int, rows: int,
                view: str, queue: list[workbench.Row], selected: str) -> None:
    """Cornice, pillars, throne, and the queue standing on the floor."""
    if rows <= 0:
        return
    bottom = y + rows - 1
    surface.text(x, y, art.band(art.CORNICE, width), C["gold"], C["ink"])
    surface.text(x, bottom, art.floor(width, 2), C["faint"], C["ink"])
    if rows > SHORT_SCENE:
        surface.text(x, bottom - 1, art.band("▚▞", width), C["wine"], C["ink"])

    body = rows - 2
    pillar_rows = art.pillar(body)
    art.paint(surface, x, y + 1, pillar_rows, art.pillar_paint(body))
    right_pillar = x + width - len(pillar_rows[0])
    art.paint(surface, right_pillar, y + 1, pillar_rows,
              art.pillar_paint(body))

    # The throne, cropped from the bottom when the room is short: losing the
    # dais keeps the king, and losing the king would leave a picture of a chair.
    throne_x = x + 6
    art.paint(surface, throne_x, y + 1, SEAT[:body - 1], art.THRONE_PAINT)

    # The floor, and the men on it. One per row of the list, in the same order
    # and with the same number, so a figure and a line are two views of one
    # matter rather than two lists that might disagree.
    figure = FIGURE_OF.get(view, art.PETITIONER)
    mask = PAINT_OF.get(view, art.PETITIONER_PAINT)
    step = art.FIGURE_WIDTH + 1
    floor_x = throne_x + len(art.THRONE[0]) + 3
    room = max(0, (right_pillar - 2 - floor_x) // step)
    if len(queue) > room and room:
        room -= 1       # the last standing place goes to saying who is missing
    # The men stand on the course above the paving, so the paving row is free
    # to be lit under whichever of them is selected. They are numbered above
    # their heads with the number the list gives the row, so a player can point
    # at a man and type his number without counting twice.
    stand = bottom - len(figure)
    for number, row in enumerate(queue[:room], 1):
        at = floor_x + (number - 1) * step
        bowed = row.mark == "✓"
        # A man blocks the floor he is standing on. Without this the weave of
        # the last course shows through the gap between his feet.
        surface.fill(at, stand, art.FIGURE_WIDTH, len(figure), " ")
        art.paint(surface, at, stand + (1 if bowed else 0),
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
    if len(queue) > room:
        surface.text(floor_x + room * step, stand + 2,
                     f"+{len(queue) - room}", C["dim"], C["ink"])
        surface.text(floor_x + room * step, stand + 3, "more",
                     C["dim"], C["ink"])
    if not queue:
        surface.text(floor_x, stand + 3, "the floor is empty.",
                     C["ash"], C["ink"])
    if room:
        art.paint(surface, right_pillar - 7, bottom - len(art.BRAZIER),
                  art.BRAZIER, art.BRAZIER_PAINT)


# --- the court ----------------------------------------------------------------

def _name(actor: str, b: dict) -> str:
    return render.actor_name(actor, b.get("house"))


def _court(b: dict) -> list[workbench.Row]:
    rows = []
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


def _court_detail(b: dict, chosen: str) -> list[tuple[str, str]]:
    item = next((p for p in b.get("justice", {}).get("petitions", [])
                 if p["id"] == chosen), None)
    if item is None:
        return [("Nobody waits for a judgement.", "ash")]
    lines = [
        (f"{item['kind']} · waiting {item['waiting']} fortnights", "bone"),
        ("", "clay"),
        (f"{_name(item['petitioner'], b)} petitions", "barley"),
        (f"against {_name(item['against'], b)}", "wine"),
        ("", "clay"),
    ]
    precedent = item.get("precedent")
    if precedent:
        lines.append((f"They cite {precedent['document_ref']}:", "sand"))
        lines.append((f"in another {precedent['kind']} case you ruled "
                      f"{precedent['verdict']}.", "sand"))
        lines.append(("", "clay"))
    if not item["heard"]:
        lines.append(("You know their names and the nature of", "ash"))
        lines.append(("the quarrel. Neither man has been heard.", "ash"))
    else:
        lines.append((f"{_name(item['petitioner'], b)} says:", "barley"))
        lines.extend(_wrapped(item["claim_text"], 3))
        lines.append(("", "clay"))
        lines.append((f"{_name(item['against'], b)} answers:", "wine"))
        lines.extend(_wrapped(item["counter_text"], 3))
    return lines


def _wrapped(text: str, rows: int, width: int = 44) -> list[tuple[str, str]]:
    import textwrap
    return [(line, "clay")
            for line in textwrap.wrap(text or "—", width)[:rows]]


def _court_controls(b: dict, chosen: str, hours: int) -> list[workbench.Control]:
    item = next((p for p in b.get("justice", {}).get("petitions", [])
                 if p["id"] == chosen), None)
    heard = bool(item and item["heard"])
    controls = [workbench.affordable(workbench.Control(
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
        workbench.affordable(workbench.Control(
            "marry_abroad", registry.BY_ID["marry_abroad"].mnemonic,
            enabled=person is not None, why="choose a man first"), hours),
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
    lines.append((f"in hand: {amount:,} {good}", "gold"))
    lines.append(("[ and ] change it · [g] the good", "ash"))
    lines.append((f"harbour due {revenue.get('harbour_rate', 0)}/1000"
                  "   [<] [>]", "sand"))
    return lines


def _relations_controls(b: dict, chosen: str, hours: int, amount: int,
                        good: str) -> list[workbench.Control]:
    return [
        workbench.affordable(workbench.Control(
            "send_gift", registry.BY_ID["send_gift"].mnemonic,
            label=f"send {amount:,} {good}",
            enabled=bool(chosen) and amount > 0,
            why="set an amount first" if chosen else "choose a court"), hours),
        workbench.affordable(workbench.Control(
            "marry_abroad", registry.BY_ID["marry_abroad"].mnemonic,
            label="marry into this court", enabled=bool(chosen),
            why="choose a court"), hours),
        workbench.Control(
            "set_harbour_due", registry.BY_ID["set_harbour_due"].mnemonic,
            label="harbour due · [<] [>]", command="due"),
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
    if view == "court":
        return _court_controls(b, chosen, hours)
    if view == "house":
        return _house_controls(b, person or chosen, hours, choosing)
    return _relations_controls(b, chosen, hours, amount, good)


HEADERS = {
    "court": (("matter", "the parties", "waiting", "state"), (11, 26, 6, 8)),
    "house": (("name", "they are", "post", "claim"), (17, 10, 16, 7)),
    "relations": (("court", "regard", "letters", "owed"), (19, 10, 12, 9)),
    "post": (("post", "kind", "who holds it", ""), (21, 10, 17, 2)),
}


LISTINGS = {"court": _court, "house": _house, "relations": _relations,
            "post": _posts}


def listing_rows(b: dict, listing: str) -> list[workbench.Row]:
    """Everything a view lists, whether or not it fits on the screen.

    The controller needs this and not the rows it can see: arrow keys that walk
    only the visible rows cannot reach a man below the fold, which is the same
    complaint whether the list is short because the window is small or because
    the throne behind it got taller.
    """
    return LISTINGS.get(listing, _court)(b)


def compose(b: dict, view: str = "court", selected: str = "",
            scroll: int = 0, hours: int = 0, choosing: str = "",
            person: str = "", amount: int = 0, good: str = "copper",
            notice: str = "", width: int = 96,
            height: int = 34) -> InteractiveScreen:
    """`selected` is the row of whatever is listed; `person` is the man being
    placed, which is a different thing the moment the list turns to posts."""
    listing = "post" if (view == "house" and choosing == "post") else view
    rows = listing_rows(b, listing)
    chosen = next((row.id for row in rows if row.id == selected),
                  rows[0].id if rows else "")

    who = person if choosing == "post" else chosen
    if view == "court":
        detail = _court_detail(b, chosen)
    elif view == "house":
        detail = _house_detail(b, who)
    else:
        detail = _relations_detail(b, chosen, amount, good)
    controls = controls_for(b, view, chosen, hours, choosing, person=who,
                            amount=amount, good=good)

    headers, widths = HEADERS[listing]
    band = scene_rows(height)
    queue = rows if listing != "post" else []

    title = "THE PALACE"
    note = "the men on the floor are the men in the list"
    if choosing == "post":
        named = next((p["name"] for p in _people(b) if p["id"] == person), "")
        title = f"THE PALACE — A POST FOR {named.upper()}"
        note = "choose a post, or [esc] to think better of it"

    def draw(surface, x, y, room, rows_available):
        _draw_scene(surface, x, y, room, rows_available, view, queue, chosen)

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
    }[listing]
