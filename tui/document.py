"""Tablets: the plain windows, and the ones that do the reading (D34).

A tablet is a document you pick up. Small, plain, many at once, closed in a
keystroke, and — the part that matters — **all of them share their furniture**,
so the eye goes straight to the figures. Two of these side by side is how a
claim gets checked against a record, which is the whole reason D33 paid for
operating-system windows.

Nothing in here is dressed as a place. Atmosphere on a ledger would make the
numbers feel authored, and the numbers are the one thing in this game that must
feel found.
"""
from __future__ import annotations

import textwrap

from tui import render, style
from tui.grid import INDEX, Screen, Surface, sparkline

C = INDEX

Row = tuple[tuple[str, str], ...]        # ((text, colour name), ...)


def _frame(surface: Surface, title: str, note: str = "") -> None:
    """The shared furniture. Every tablet gets exactly this and no more.

    One call, so that every window in the game is dressed identically and the
    eye goes to the figures rather than to the frame (`tui/style.py`).
    """
    style.panel(surface, 0, 0, surface.width, surface.height,
                title=title, note=note, drop=False)


def _trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def ledger(title: str, headers: tuple[str, ...], rows: list[Row],
           widths: tuple[int, ...], width: int = 64, height: int = 24,
           note: str = "[esc] close") -> Screen:
    """A table. Cold on purpose (spec 9.3: it should look like a payroll).

    `widths` are column widths; a negative width right-aligns, which is what
    every number in the game wants and no word does.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    _frame(surface, title, note)

    right = width - 3            # never write onto the frame

    def columns(y: int, cells, header: bool = False) -> None:
        x = 3
        bg = C["faint"] if header else C["ink"]
        for index, width_spec in enumerate(widths):
            if index >= len(cells) or x >= right:
                break
            text, tone = cells[index] if not header else (cells[index], "bone")
            span = min(abs(width_spec), right - x)
            if span <= 0:
                break
            text = _trunc(str(text), span)
            at = x + (span - len(text)) if width_spec < 0 else x
            surface.text(at, y, text, C[tone], bg)
            x += span + 2

    # The column heads sit in a band rather than above a rule: text mode made a
    # heading by inverting it, and a band survives `plain_text` because the
    # words are still there.
    style.bar(surface, 2, 2, width - 4, " ", fg=C["bone"], bg=C["faint"])
    columns(2, headers, header=True)
    room = height - 5
    for offset, row in enumerate(rows[:room]):
        columns(4 + offset, row)
    if len(rows) > room:
        surface.text(3, height - 2, f"…and {len(rows) - room} more",
                     C["ash"], C["ink"])
    return surface.freeze()


def tablet(item: dict, body: str | None = None, house: dict | None = None,
           width: int = 62, height: int = 26) -> Screen:
    """One letter, as the object it is.

    The sender's own dating is shown as he wrote it and never converted: the
    courts share no epoch (spec 6.17), and quietly normalising it would hand the
    player a synchronisation nobody in 1200 BC had.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    who = render.actor_name(item["sender"], house)
    _frame(surface, who.upper(), "[esc] close")

    # Truncated against the frame, not the surface: `text` clips at the edge of
    # the world, which for a boxed window means writing over the right border.
    surface.text(3, 2, _trunc(render.letter_summary(item["topic"]), width - 6),
                 C["dim"], C["ink"])
    stamp = f"reached your hand, turn {item['received_turn']}"
    surface.text(3, 3, stamp, C["ash"], C["ink"])
    surface.text(3, 4, "─" * (width - 6), C["faint"], C["ink"])

    if body is None:
        body = render.letter_body(item["sender"], item["topic"], item["facts"])
    # Authored templates wrap at their own margin; a blank line is a real
    # paragraph break and a single newline is not, so the second is unwrapped
    # before rewrapping to this window's width.
    y = 6
    paragraphs = [" ".join(block.split())
                  for block in body.split("\n\n") if block.strip()]
    for paragraph in paragraphs:
        for line in textwrap.wrap(paragraph, width - 8) or [""]:
            if y >= height - 4:
                break
            surface.text(4, y, line, C["clay"], C["ink"])
            y += 1
        y += 1

    # The figures it asserts, pulled out where they can be compared with a
    # second tablet. This is the whole point of the window kind.
    facts = item.get("facts") or {}
    if facts and y < height - 2:
        y = max(y, height - 3 - len(facts))
        surface.text(3, y - 1, "─" * (width - 6), C["faint"], C["ink"])
        for key, value in facts.items():
            if y >= height - 1:
                break
            surface.text(4, y, f"it says {key}", C["dim"], C["ink"])
            shown = f"{value:,}" if isinstance(value, int) else str(value)
            surface.text(width - 4 - len(shown), y, shown, C["bone"], C["ink"])
            y += 1
    return surface.freeze()


# --- the tablets the game actually opens -------------------------------------

def order_of(b: dict, previous: list[str] | None = None) -> list[str]:
    """The order the pile is shown in, held steady across a fortnight.

    Belief sorts the stack read-last (`belief/project.py`), which is right for
    a summary and wrong for a window you are pressing numbers at: reading iv
    would slide everything below it up a row, and the next keystroke would open
    a tablet the player never chose. So the window keeps the order it was first
    given and new arrivals go on the end. A pile on a desk does not reshuffle
    itself because you picked one up.
    """
    live = [item["id"] for item in b["stack"]]
    if not previous:
        return live
    kept = [letter_id for letter_id in previous if letter_id in live]
    return kept + [letter_id for letter_id in live if letter_id not in kept]


def stack(b: dict, width: int = 80, height: int = 24,
          order: list[str] | None = None) -> Screen:
    items = b["stack"]
    if order:
        by_id = {item["id"]: item for item in items}
        items = [by_id[letter_id] for letter_id in order if letter_id in by_id]
    rows: list[Row] = []
    for index, item in enumerate(items):
        rows.append((
            (render._num(index), "ash"),
            (item["freshness"], "flame" if not item["read"] else "ash"),
            (render.actor_name(item["sender"], b.get("house")), "clay"),
            (render.letter_summary(item["topic"]), "dim"),
            ("unread" if not item["read"] else "read",
             "flame" if not item["read"] else "ash"),
        ))
    unread = sum(1 for item in items if not item["read"])
    return ledger(f"THE STACK — {len(items)} on the pile, {unread} unread",
                  ("", "", "from", "concerning", ""),
                  rows, (4, 1, 24, 24, -8), width, height,
                  note="[1-9] read  ·  [esc] close")


def stores(b: dict, width: int = 62, height: int = 22) -> Screen:
    rows: list[Row] = []
    for good, amount in sorted(b["stores"].items()):
        series = b.get("store_history", {}).get(good, [])
        rows.append((
            (good.replace("_", " "), "clay"),
            (render.fmt_good(good, amount), "gold" if good in
             ("bronze", "copper", "tin") else "barley"),
            (sparkline(series, 12), "dim"),
        ))
    return ledger("THE STORES", ("", "counted", "these twelve"),
                  rows, (16, -22, 12), width, height)


def roll(b: dict, width: int = 78, height: int = 22) -> Screen:
    """The payroll, and it looks like one on purpose (spec 9.3.4)."""
    rows: list[Row] = []
    for group in b["groups"]:
        weeks = group["arrears_weeks"]
        rows.append((
            (group["name"], "clay"),
            (str(group["size"]), "dim"),
            (f"{group['allocated']:,}", "dim"),
            (f"{weeks}" if weeks else "—", "blood" if weeks >= 4 else
             ("flame" if weeks else "ash")),
            (group["loyalty"], "blood" if weeks >= 4 else "dim"),
        ))
    return ledger("THE ROLL — what is owed and what was paid",
                  ("group", "heads", "allocated qa", "unpaid", "they are"),
                  rows, (30, -5, -13, -6, 12), width, height)


def page(title: str, lines: list[tuple[int, str, str]], width: int = 70,
         height: int = 26, note: str = "[esc] close") -> Screen:
    """A framed page of written lines: `(indent, text, colour)`.

    For the windows that are a document rather than a table — an oath with its
    clauses under it, a family tree. Same furniture as `ledger`, so the two read
    as the same kind of object on the desk.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    _frame(surface, title, note)
    y = 2
    for indent, text, tone in lines:
        if y >= height - 1:
            surface.text(3, height - 2, "…and more below", C["ash"], C["ink"])
            break
        if text == "─":
            surface.text(3, y, "─" * (width - 6), C["faint"], C["ink"])
        else:
            surface.text(3 + indent, y, _trunc(text, width - 6 - indent),
                         C[tone], C["ink"])
        y += 1
    return surface.freeze()


def _clause(clause: dict) -> str:
    """A clause as the tablet has it: the kind, then its terms, unrounded.

    Deliberately close to the machine — `provide_troops  200 men, within 2` and
    not "you owe Hatti two hundred men". The clause is evidence, and evidence
    that has been paraphrased for the player is evidence he cannot check a
    viceroy's letter against.
    """
    args = dict(clause["args"])
    parts = []
    for key, value in sorted(args.items()):
        if value is True:
            parts.append(key.replace("_", " "))
        elif value is False:
            continue
        elif isinstance(value, int):
            parts.append(f"{key.replace('_', ' ')} {value:,}")
        else:
            parts.append(f"{key.replace('_', ' ')} {value}")
    return f"{clause['kind'].replace('_', ' ')}   " + ", ".join(parts)


def fortnight(b: dict, lines: list[str], width: int = 66,
              height: int = 18) -> Screen:
    """The turn boundary: what happened while you were not looking.

    A fortnight passing is the heaviest thing that happens in this game and it
    used to be a redraw. It gets its own window, in the middle of the desk, and
    it says only what occurred — a courier came, a rite was not kept. It never
    says what it means, and it never says what to do about it, which is what
    keeps it a report and not an advisor (D19).

    An empty fortnight is shown as an empty fortnight. Quiet is information.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height,
                title="THE FORTNIGHT TURNS", note="[space] on  ·  [esc] close",
                focus=True, drop=False)
    surface.text(3, 2, b["date"], C["sky"], C["ink"])
    surface.text(3, 3, "─" * (width - 6), C["faint"], C["ink"])
    y = 5
    if not lines:
        surface.text(3, y, "Nothing was reported. That is not the same as",
                     C["ash"], C["ink"])
        surface.text(3, y + 1, "nothing having happened.", C["ash"], C["ink"])
    for line in lines:
        for wrapped in textwrap.wrap(line.strip(), width - 8) or [""]:
            if y >= height - 2:
                break
            surface.text(4, y, wrapped, C["clay"], C["ink"])
            y += 1
    return surface.freeze()


def oaths(b: dict, width: int = 76, height: int = 28) -> Screen:
    """The oath tablets. The clauses are readable; the liability is not (D26).

    Every figure a superior will later claim is already here, in the clause, in
    the player's own archive. Nothing on this page says which oath a god is
    angry about, and nothing ever will.
    """
    lines: list[tuple[int, str, str]] = []
    for oath in b["oaths"]:
        state = ("dissolved" if oath["dissolved"]
                 else "LAPSED — nobody is bound" if oath["lapsed"] else "sworn")
        tone = ("ash" if oath["dissolved"]
                else "wine" if oath["lapsed"] else "clay")
        lines.append((0, f"{oath['id']}   ({state})", tone))
        lines.append((2, "before " + ", ".join(oath["gods"]), "wine"))
        lines.append((2, "between " + ", ".join(
            render.actor_name(p, b.get("house")) for p in oath["parties"]),
            "dim"))
        if oath["lapsed"]:
            lines.append((2, "sworn by " + render.actor_name(
                oath["sworn_by"], b.get("house")) + ", who is dead", "wine"))
        for clause in oath["clauses"]:
            lines.append((2, f"· {_clause(clause)}", "bone"))
        lines.append((0, "─", "faint"))
    if not lines:
        lines = [(0, "no oath tablet is held in this archive.", "ash")]
    return page("THE OATHS", lines, width, height)


def land(b: dict, width: int = 70, height: int = 24) -> Screen:
    """The gauge, the floor, the seed, the hands. No yield and no forecast."""
    data = b.get("land")
    if not data:
        return page("THE LAND", [(0, "this house holds no estates.", "ash")],
                    width, height)
    seed, ground = data["seed_in_store"], data["seed_in_ground"]
    lines: list[tuple[int, str, str]] = [
        (0, f"the river gauge stands at {data['gauge']}", "sky"),
        (0, "─", "faint"),
        (0, f"last year's threshing floor   "
            f"{render.fmt_good('grain', data['last_harvest'])}", "barley"),
        (0, f"the year before               "
            f"{render.fmt_good('grain', data['previous_harvest'])}", "dim"),
        (0, "", "clay"),
        (0, f"seed in store                 "
            f"{render.fmt_good('grain', seed)}", "sand"),
        (0, f"seed in the ground            "
            f"{render.fmt_good('grain', ground)}", "sand"),
        (0, f"the sowing asks for           "
            f"{render.fmt_good('grain', data['seed_recommended'])}", "dim"),
        (0, "─", "faint"),
        (0, f"hands on the land this fortnight   "
            f"{data['labour_days_this_turn']:,} days", "clay"),
        (0, f"the work asks for                  "
            f"{data['labour_days_needed']:,} days", "dim"),
        (0, f"corvee days called                 {data['corvee_days']:,}",
         "dim"),
        (0, "", "clay"),
    ]
    for estate in data["estates"]:
        canal = estate.get("canal_condition")
        state = (f"canal {canal}" if estate["irrigated"] and canal is not None
                 else "rain-fed")
        # No area and no yield: Belief does not carry them, because a king who
        # wants to know what a field gave has to ask the man who worked it.
        name = _trunc(estate["name"], 30).ljust(31)
        lines.append((0, f"{name}{estate['place']:<12}{state}", "sand"))
    return page("THE LAND", lines, width, height)


def house(b: dict, width: int = 70, height: int = 26) -> Screen:
    """The family as a tree. Whose claim is better is never stated (D19)."""
    data = b.get("house")
    if not data:
        return page("THE HOUSE", [(0, "no house is recorded.", "ash")],
                    width, height)
    members = {person["id"]: person for person in data["members"]}
    ruler = members.get(data["ruler"])

    def person(p: dict, indent: int, branch: str = "") -> tuple[int, str, str]:
        # The branch is part of the name column, not a prefix to it: padding the
        # name alone shears every indented row two cells to the right.
        name = f"{branch}{p['name']}"[:26].ljust(26)
        if not p["alive"]:
            return (indent, f"{name} died in turn {p['died_turn']}", "ash")
        marks = []
        if p["heir_rank"]:
            marks.append(f"heir {p['heir_rank']}")
        if p["expecting"]:
            marks.append("with child")
        if p["married_to_court"]:
            marks.append("at the court of " + render.actor_name(
                p["married_to_court"], data))
        if p["is_queen_mother"]:
            marks.append("the queen mother")
        tail = ("  " + ", ".join(marks)) if marks else ""
        return (indent, f"{name}{p['age_years']:>3}  "
                        f"{p['health']:<12}{tail}", "clay")

    lines: list[tuple[int, str, str]] = [
        (0, f"regnal year {b['regnal_year']}, reign {data['reigns']} of this run",
         "sky"),
        (0, "─", "faint"),
    ]
    if ruler:
        lines.append(person(ruler, 0))
        spouse = members.get(ruler["spouse"] or "")
        if spouse:
            lines.append(person(spouse, 0, "├─ "))
        children = [p for p in data["members"] if p["father"] == ruler["id"]]
        for index, child in enumerate(children):
            branch = "└─ " if index == len(children) - 1 else "├─ "
            lines.append(person(child, 0, branch))
    others = [p for p in data["members"]
              if p is not ruler and p["id"] != (ruler or {}).get("spouse")
              and p["father"] != (ruler or {}).get("id")]
    if others:
        lines.append((0, "─", "faint"))
        for p in others:
            lines.append(person(p, 0))
    return page("THE HOUSE", lines, width, height)


def muster(b: dict, width: int = 62, height: int = 18) -> Screen:
    troops = b.get("troops", {})
    rows: list[Row] = [
        ((f["name"], "clay"), (str(f["strength"]), "dim"),
         (f["task"], "flame" if f["task"] == "campaign" else "clay"),
         (f["place"], "dim"))
        for f in troops.get("formations", [])
    ]
    for holding, men in sorted(troops.get("garrisons", {}).items()):
        rows.append((("holding " + holding, "ash"), (str(men), "ash"),
                     ("", "ash"), ("men", "ash")))
    return ledger("THE MUSTER", ("formation", "men", "at", "place"),
                  rows, (26, -5, 10, 12), width, height)
