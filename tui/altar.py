"""The altar: a setting, because an omen at an altar is a ritual (D34).

This is one of the three windows in the game that is drawn as a place, and the
reason is specific. Divination in a list is a dropdown labelled "question type";
divination at an altar is a man standing at a stone with a liver in his hands
while the king waits. The mechanics are identical. The window is not.

What is *not* dressed up: the answer. The diviner interprets the evidence
available now, imperfectly and through his factional interests. A wrong reading
is a plausible neighbouring interpretation, never privileged access to future
engine state. Nothing on this screen marks a reading as correct, because nobody
in the world can know that verdict when it is given.
"""
from __future__ import annotations

import textwrap

from tui import art, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

# question -> (key, what the king is asking about, what it costs him)
QUESTIONS = (
    ("h", "of the harvest", "harvest"),
    ("d", "of a death in the house", "death"),
    ("r", "of the road and the sea", "route"),
)

OFFERINGS = (("1", "oil", 20), ("2", "wine", 20), ("3", "grain", 200))


def compose(b: dict, readings: list[str], chosen: str = "harvest",
            offering: tuple[str, int] | None = None,
            width: int = 78, height: int = 32,
            subject: str = "", notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE ALTAR", drop=False)

    # The room. The frieze runs above the stone, the diviner stands beside it.
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    art.draw(surface, (width - 34) // 2, 3, art.ALTAR,
             lit=C["flame"], mid=C["blood"], dark=C["wine"], edge=C["faint"])
    art.draw(surface, 3, 8, art.PRIEST, lit=C["bone"], mid=C["dim"],
             dark=C["faint"])
    surface.text(3, 18, "the diviner", C["wine"], C["ink"])

    y = 17
    surface.text(20, y, "─" * (width - 23), C["faint"], C["ink"])
    y += 1

    # What he has said, most recent last, in his own voice.
    if not readings:
        for line in textwrap.wrap(
                "He waits with his hands on the stone. He will not begin until "
                "he is asked, and he will not ask what you want to hear.",
                width - 24):
            surface.text(20, y, line, C["ash"], C["ink"])
            y += 1
    for reading in readings[-4:]:
        for line in textwrap.wrap(reading, width - 24):
            if y >= height - 11:
                break
            surface.text(20, y, line, C["bone"], C["ink"])
            y += 1
        y += 1

    # --- what may be asked ---------------------------------------------------
    foot = height - 10
    style.bar(surface, 2, foot, width - 4, " WHAT YOU WOULD KNOW",
              fg=C["bone"], bg=C["faint"])
    people = [
        person for person in b.get("house", {}).get("members", [])
        if person.get("alive")
    ]
    chosen_person = next(
        (person for person in people if person["id"] == subject), None)
    subject_name = (
        chosen_person["name"] if chosen_person is not None
        else "choose a living member of the house")
    for offset, (key, label, topic) in enumerate(QUESTIONS):
        shown = (
            f"of the death of {subject_name}" if topic == "death" else label)
        style.keycap(surface, 3, foot + 1 + offset, key, shown[:55])
        if topic == chosen:
            surface.text(width - 10, foot + 1 + offset, "◄ this",
                         C["flame"], C["ink"])

    if chosen == "death":
        style.keycap(surface, 37, foot + 4, "[", "previous",
                     enabled=len(people) > 1)
        style.keycap(surface, 53, foot + 4, "]", "next",
                     enabled=len(people) > 1)

    style.bar(surface, 2, foot + 5, width - 4, " WHAT YOU WOULD GIVE",
              fg=C["bone"], bg=C["faint"])
    column = 3
    for key, good, quantity in OFFERINGS:
        label = f"{quantity} {good}"
        chosen_one = offering is not None and offering[0] == good
        style.keycap(surface, column, foot + 6, key, label)
        if chosen_one:
            surface.text(column + len(key) + 4 + len(label), foot + 6, "◄",
                         C["flame"], C["ink"])
        column += len(key) + 8 + len(label)
    guidance = (
        notice if notice else
        "a larger offering does not buy a truer answer. it buys a readier one.")
    surface.text(3, foot + 7, guidance[:width - 6],
                 C["flame"] if notice else C["ash"], C["ink"])
    style.bar(surface, 2, height - 2, width - 4,
              " [enter] put the question   ·   two hours, and what you laid down",
              fg=C["clay"], bg=C["lapis"])
    return surface.interactive()
