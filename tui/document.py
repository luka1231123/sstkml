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

from tui import render
from tui.grid import INDEX, Screen, Surface, sparkline

C = INDEX

Row = tuple[tuple[str, str], ...]        # ((text, colour name), ...)


def _frame(surface: Surface, title: str, note: str = "") -> None:
    """The shared furniture. Every tablet gets exactly this and no more."""
    width, height = surface.width, surface.height
    surface.box(0, 0, width, height, style="single", fg=C["faint"],
                title=title, title_fg=C["bone"])
    if note and width > len(note) + 6:
        surface.text(width - 3 - len(note), height - 1, note, C["ash"], C["ink"])


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
        for index, width_spec in enumerate(widths):
            if index >= len(cells) or x >= right:
                break
            text, tone = cells[index] if not header else (cells[index], "dim")
            span = min(abs(width_spec), right - x)
            if span <= 0:
                break
            text = _trunc(str(text), span)
            at = x + (span - len(text)) if width_spec < 0 else x
            surface.text(at, y, text, C[tone], C["ink"])
            x += span + 2

    columns(2, headers, header=True)
    surface.text(3, 3, "─" * (width - 6), C["faint"], C["ink"])
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

    surface.text(3, 2, render.letter_summary(item["topic"]), C["dim"], C["ink"])
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
