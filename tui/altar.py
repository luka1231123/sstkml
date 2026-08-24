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

from tui import art, style, workbench
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
VIEWS = ("rites", "offerings", "oaths", "obligations")

# question -> (key, what the king is asking about, what it costs him)
QUESTIONS = (
    ("h", "of the harvest", "harvest"),
    ("k", "of a death in the house", "death"),
    ("r", "of the road and the sea", "route"),
)

OFFERINGS = (("o", "oil", 20), ("w", "wine", 20), ("g", "grain", 200))

_MEDIUM_ALTAR = art.ALTAR[:8] + (art.ALTAR[-1],)
_MEDIUM_PRIEST = art.PRIEST[:6] + (art.PRIEST[-1],)
_SMALL_ALTAR = (
    "      ▟▙      ",
    "   ▄▄▄██▄▄▄   ",
    " ▟██████████▙ ",
    "▀▀▀▀▀▀▀▀▀▀▀▀▀",
)
_SMALL_PRIEST = (
    "  ▲  ",
    " ▗█▖ ",
    " ▐█▌ ",
    " ███ ",
)


def _room(surface: Surface, width: int, controls_top: int,
          readings: list[str]) -> None:
    """Draw only in the space above the fixed ritual controls.

    The original room assumed a 32-row window while the desktop actually opens
    it at 24 rows. Its altar and priest therefore continued through the
    questions and offerings. Each height band now owns a bounded vignette; the
    controls never have to paint legibility back over a statue.
    """
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])

    if controls_top >= 17:
        altar_rows, priest_rows = art.ALTAR, art.PRIEST
        altar_y, priest_y, words_y = 3, 7, 17
        priest_x, words_x = 3, 20
    elif controls_top >= 12:
        altar_rows, priest_rows = _MEDIUM_ALTAR, _MEDIUM_PRIEST
        altar_y, priest_y, words_y = 2, 3, 11
        priest_x, words_x = 3, 18
    else:
        altar_rows, priest_rows = _SMALL_ALTAR, _SMALL_PRIEST
        altar_y, priest_y, words_y = 2, 2, 6
        priest_x, words_x = 3, 16

    altar_x = max(priest_x + len(priest_rows[0]) + 1,
                  width - len(altar_rows[0]) - 3)
    art.draw(surface, altar_x, altar_y, altar_rows,
             lit=C["flame"], mid=C["blood"], dark=C["wine"],
             edge=C["faint"])
    art.draw(surface, priest_x, priest_y, priest_rows,
             lit=C["bone"], mid=C["dim"], dark=C["faint"])
    if words_y < controls_top:
        surface.text(priest_x, words_y, "the diviner",
                     C["wine"], C["ink"])

    room = max(0, controls_top - words_y)
    line_width = max(10, width - words_x - 3)
    lines: list[str] = []
    if readings:
        for reading in readings[-4:]:
            wrapped = textwrap.wrap(reading, line_width) or [""]
            if lines:
                lines.append("")
            lines.extend(wrapped)
    elif room and controls_top >= 12:
        lines = ["He waits at the stone."]
    for offset, line in enumerate(lines[-room:] if room else ()):
        surface.text(words_x, words_y + offset, line[:line_width],
                     C["bone"] if readings else C["ash"], C["ink"])


def compose(b: dict, readings: list[str], chosen: str = "harvest",
            offering: tuple[str, int] | None = None,
            width: int = 78, height: int = 32,
            subject: str = "", notice: str = "",
            view: str = "rites") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE SHRINE", drop=False)
    if view == "offerings":
        workbench.tabs(surface, 2, 2, width,
                       tuple((name, name.title()) for name in VIEWS), view)
        surface.text(3, 5, "OFFERINGS IN THE STOREHOUSE", C["gold"], C["ink"])
        stores = b.get("stores", {})
        for row, (key, good, quantity) in enumerate(OFFERINGS, 7):
            chosen_one = offering is not None and offering[0] == good
            surface.text(2, row, ">" if chosen_one else " ", C["flame"], C["ink"])
            style.keycap(surface, 4, row, key, f"{quantity} {good}")
            surface.text(28, row, f"held {stores.get(good, 0):,}", C["clay"], C["ink"])
        surface.text(3, 12, "The chosen offering is consumed when a rite is performed.",
                     C["dim"], C["ink"])
        style.footer(surface, (style.FooterAction("Tab", "view"),
                               style.FooterAction("Enter", "return to rites"),
                               style.FooterAction("Esc", "close")),
                     y=height - 2, x=2, width=width - 4)
        return surface.interactive()

    # --- what may be asked ---------------------------------------------------
    foot = height - 10
    _room(surface, width, foot, readings)
    workbench.tabs(surface, 2, 2, width,
                   tuple((name, name.title()) for name in VIEWS), view)
    rites = b.get("rites", ())
    if rites:
        for index, rite in enumerate(rites[:max(1, (foot - 5) // 2)]):
            y = 3 + index * 2
            needs = ", ".join(f"{qty} {good}" for good, qty in rite["requires"].items())
            line = (f"{rite['id'].replace('_', ' ')} · fortnight "
                    f"{rite['fortnight']} · {rite['hours']}h")
            surface.text(3, y, line[:width - 6],
                         C["sky"], C["ink"])
            needs = needs.replace(", ", " + ")
            consequence = (f"{needs} · skip L{rite['skip_legitimacy']:+} "
                           f"U{rite['skip_unrest']:+}")
            surface.text(5, y + 1, consequence[:width - 8],
                         C["dim"], C["ink"])
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
        else "choose a house member")
    for offset, (key, label, topic) in enumerate(QUESTIONS):
        shown = (
            f"of the death of {subject_name}" if topic == "death" else label)
        label_room = max(8, width - 18)
        style.keycap(surface, 3, foot + 1 + offset, key, shown[:label_room])
        if topic == chosen:
            surface.text(width - 9, foot + 1 + offset, "◄ this",
                         C["flame"], C["ink"])

    if chosen == "death":
        style.keycap(surface, 3, foot + 4, "[", "previous",
                     enabled=len(people) > 1)
        style.keycap(surface, 19, foot + 4, "]", "next",
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
    if notice:
        style.notice(surface, 3, foot + 7, width - 6, notice)
    else:
        surface.text(
            3, foot + 7,
            "a larger offering does not buy a truer answer. "
            "it buys a readier one."[:width - 6],
            C["ash"], C["ink"])
    active = next((o for o in reversed(b.get("house", {}).get("omens", ()))
                   if o.get("published") and not o.get("defied")), None)
    actions = ([style.FooterAction("s", "suppress · 2h", command="do:suppress_omen"),
                style.FooterAction("d", "defy", command="do:defy_omen")]
               if active else
               [style.FooterAction("Enter", "ask · 2h + offering", command="altar:ask")])
    actions += [style.FooterAction("Tab", "view"),
                style.FooterAction("Esc", "close")]
    style.footer(surface, actions, y=height - 2, x=2, width=width - 4)
    return surface.interactive()
