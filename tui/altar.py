"""The altar: a setting, because an omen at an altar is a ritual (D34).

This is one of the three windows in the game that is drawn as a place, and the
reason is specific. Divination in a list is a dropdown labelled "question type";
divination at an altar is a man standing at a stone with a liver in his hands
while the king waits. The mechanics are identical. The window is not.

What is *not* dressed up: the answer. The diviner reads from a future that
genuinely already exists (the climate series, `will_die_on`) and he lies about
it by his competence and his loyalty — a wrong reading is always a plausible
neighbour, never noise (M9). Nothing on this screen marks a reading as doubtful,
because nothing in the world would.
"""
from __future__ import annotations

import textwrap

from tui import art, style
from tui.grid import INDEX, Screen, Surface

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
            width: int = 78, height: int = 32) -> Screen:
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
    for offset, (key, label, topic) in enumerate(QUESTIONS):
        style.keycap(surface, 3, foot + 1 + offset, key, label)
        if topic == chosen:
            surface.text(30, foot + 1 + offset, "◄ this", C["flame"], C["ink"])

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
    surface.text(3, foot + 7,
                 "a larger offering does not buy a truer answer. it buys a "
                 "readier one.", C["ash"], C["ink"])
    style.bar(surface, 2, height - 2, width - 4,
              " [enter] put the question   ·   an hour, and what you laid down",
              fg=C["clay"], bg=C["lapis"])
    return surface.freeze()
