"""The Field Manual: deterministic, compact, free Help (UI/UX spec 11).

This used to be the Palace Tutor -- a 100 x 38 window with a portrait, a
conversation, and a model behind it. It is now a 52 x 20 reference book:
a search line, a list of topics, the selected topic beside it, and nothing
that can be slow, absent, or wrong.

The list is the only thing that scrolls, the detail always shows the exact
control, command, and cost, and none of it costs an hour. `manual.py` builds
the topics from the action registry and the authored corpus; this file only
lays them out.
"""
from __future__ import annotations

import textwrap

import manual
from tui import style
from tui.grid import INDEX, Screen, Surface

C = INDEX


def _wrap(text: str, room: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, max(8, room)) or [""])
    return lines


def _detail_lines(topic, room: int) -> list[tuple[str, int]]:
    """The right-hand page: what it is, how to do it, what it costs."""
    # The control, the cost, and the exact command come before the prose. A
    # reference book is consulted for "which key, what does it cost, what do I
    # type"; putting the paragraph first pushed all three off a 20-row page.
    rows: list[tuple[str, int]] = [(topic.title[:room], C["bone"]), ("", C["ink"])]
    if topic.syntax:
        rows.extend((line, C["sky"]) for line in _wrap(topic.syntax, room))
    if topic.cost_line:
        rows.extend((line, C["flame"]) for line in _wrap(topic.cost_line, room))
    if topic.command:
        rows.extend((line, C["dim"])
                    for line in _wrap(f"Command: {topic.command}", room))
    rows.append(("", C["ink"]))
    rows.extend((line, C["clay"]) for line in _wrap(topic.body, room))
    for example in topic.examples:
        rows.extend((line, C["ash"])
                    for line in _wrap(f"Example: {example}", room))
    if topic.related:
        rows.append(("", C["ink"]))
        related = ", ".join(name.rstrip(":").title() for name in topic.related)
        rows.extend((line, C["faint"])
                    for line in _wrap(f"Related: {related}", room))
    return rows


def compose(width: int = 52, height: int = 20, query: str = "",
            pick: str = "", screen: str = "", scroll: int = 0) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    label = f"FIELD MANUAL · {screen.upper()}" if screen else "FIELD MANUAL"
    style.panel(surface, 0, 0, width, height, title=label, drop=False)

    # Search line. Deterministic and incremental: every keystroke re-scans the
    # whole corpus, which at this size is far inside the specification's 50 ms.
    style.bar(surface, 2, 1, width - 4, f" Search: {query}",
              fg=C["bone"], bg=C["faint"])
    if query:
        surface.put(min(width - 3, 11 + len(query)), 1, "█", C["flame"],
                    C["faint"])
    surface.link(2, 1, width - 4, 1, "focus")

    found = manual.search(query, screen)
    if not found:
        surface.text(3, 3, "Nothing matches that.", C["ash"], C["ink"])
        surface.text(3, 4, "Try a verb: repair, read, assign.",
                     C["faint"], C["ink"])
        style.footer(surface, (style.FooterAction("esc", "close"),))
        return surface.interactive()

    if pick not in {topic.id for topic in found}:
        pick = found[0].id
    selected = next(topic for topic in found if topic.id == pick)

    # A narrow manual stacks: the list is dropped and the page fills the window,
    # because a reference book with no room for the answer is not one. The
    # topic can still be changed with the arrow keys and the search line.
    split = 18 if width >= 46 else 0
    top, foot = 3, height - 3
    room = foot - top

    if split:
        for row in range(top - 1, foot):
            surface.put(split, row, "│", C["faint"], C["ink"])
        index = [topic.id for topic in found].index(pick)
        start = max(0, min(scroll, len(found) - room))
        if index < start:
            start = index
        elif index >= start + room:
            start = index - room + 1
        surface.text(1, top - 1, f"TOPICS {len(found)}"[:split - 1],
                     C["dim"], C["ink"])
        for offset, topic in enumerate(found[start:start + room]):
            y = top + offset
            chosen = topic.id == pick
            fg = C["bone"] if chosen else C["clay"]
            background = C["lapis"] if chosen else C["ink"]
            if chosen:
                surface.fill(1, y, split - 1, 1, " ", fg, background)
            surface.text(1, y, ">" if chosen else " ",
                         C["flame"] if chosen else C["dim"], background)
            surface.text(2, y, topic.title.title()[: split - 3], fg, background)
            surface.link(1, y, split - 1, 1, f"topic:{topic.id}")

    left = split + 2 if split else 2
    page_room = width - left - 2
    for offset, (line, colour) in enumerate(
            _detail_lines(selected, page_room)[:room + 1]):
        surface.text(left, top - 1 + offset, line[:page_room], colour, C["ink"])

    style.footer(surface, (
        style.FooterAction("up", "topic"),
        style.FooterAction("/", "search"),
        style.FooterAction("esc", "close"),
    ))
    surface.text(2, height - 2, "costs no hours"[: width - 4],
                 C["faint"], C["ink"])
    return surface.interactive()
