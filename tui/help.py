"""The Palace Tutor: conversational, retrieval-grounded game help."""
from __future__ import annotations

import textwrap

from tui import art, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

SUGGESTIONS = (
    "How do I send troops on campaign?",
    "How do I repair a building?",
    "List every kind of order you know.",
)


def _conversation_rows(
        said: list[tuple[str, str]] | tuple[tuple[str, str], ...],
        room: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    if not said:
        intro = (
            "Ask me how to operate the palace, where to find a report, what "
            "an action costs, or the exact words for any order."
        )
        rows.extend((line, C["ash"]) for line in textwrap.wrap(intro, room))
        rows.append(("", C["clay"]))
        rows.extend((line, C["dim"]) for line in textwrap.wrap(
            "I search the current command tablets before answering. I know "
            "the rules and controls; I do not choose policy for you.", room))
        return rows
    for who, what in said:
        speaker = "you:" if who == "player" else "Tutor:"
        rows.append((speaker, C["flame"] if who == "player" else C["sky"]))
        colour = C["clay"] if who == "player" else C["bone"]
        rows.extend((f"  {line}", colour)
                    for line in textwrap.wrap(what, max(8, room - 2)))
        rows.append(("", colour))
    return rows


def compose(width: int = 100, height: int = 38,
            said: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
            typed: str = "", typing: bool = True,
            sources: tuple[str, ...] = ()) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height,
                title="THE PALACE TUTOR · HELP", drop=False)

    art.draw(surface, 3, 2, art.SCRIBE, lit=C["bone"], mid=C["dim"],
             dark=C["faint"])
    surface.text(3, 12, "the Tutor", C["clay"], C["ink"])
    surface.text(3, 13, "keeper of rules", C["ash"], C["ink"])
    surface.text(3, 15, "costs no hours", C["sky"], C["ink"])
    surface.text(3, 17, "knows controls", C["dim"], C["ink"])
    surface.text(3, 18, "and all orders", C["dim"], C["ink"])
    for row in range(2, height - 9):
        surface.put(19, row, "│", C["faint"], C["ink"])

    left = 22
    room = width - left - 3
    foot = height - 9
    available = foot - 3
    rows = _conversation_rows(said, room)
    # Help is a conversation, so the newest exchange must remain visible.
    for offset, (line, colour) in enumerate(rows[-available:]):
        surface.text(left, 2 + offset, line[:room], colour, C["ink"])
    if sources:
        source_text = "command tablets: " + ", ".join(
            source.replace("_", " ") for source in sources[:4])
        surface.text(left, foot - 1, source_text[:room], C["faint"], C["ink"])

    style.bar(surface, 2, foot, width - 4, " ASK HOW TO DO ANYTHING",
              fg=C["bone"], bg=C["faint"])
    field_width = width - 8
    visible = typed[-(field_width - 2):]
    style.bar(surface, 3, foot + 1, width - 6, " " + visible,
              fg=C["bone"], bg=C["faint"])
    if typed:
        surface.put(4 + min(len(visible), field_width - 2), foot + 1,
                    "█", C["flame"], C["faint"])
    else:
        surface.text(5, foot + 1,
                     "type a question about any screen, key, cost, or order",
                     C["ash"], C["faint"])
    surface.link(3, foot + 1, width - 6, 1, "focus")
    surface.text(3, foot + 2,
                 "answers retrieve from the current command tablets · no hours",
                 C["ash"], C["ink"])

    surface.text(3, foot + 3, "QUESTIONS READY", C["dim"], C["ink"])
    for index, suggestion in enumerate(SUGGESTIONS):
        style.keycap(surface, 3, foot + 4 + index, f"F{index + 1}",
                     suggestion[:width - 13], command=f"F{index + 1}")

    style.footer(surface, [
        style.FooterAction("enter", "ask"),
        style.FooterAction("ctrl-u", "clear"),
        style.FooterAction("esc", "return to Hall"),
    ], y=height - 2, x=2, width=width - 4)
    return surface.interactive()
