"""HELP: the advisor that is free, always right, and never calls a model (D33).

The distinction that makes two advisors worth having: HELP knows the *game* --
which key opens what, what a fortnight costs, what a word on a screen means --
and it is never wrong, because it is a written page. COUNSEL knows the *world*,
costs an hour, and can be mistaken, because he is a person.

So nothing here is generated and nothing here is judgement. It will tell you
that reading a tablet costs two hours; it will not tell you which tablet to
read. That line is D19's, and HELP is on the safe side of it.
"""
from __future__ import annotations

from tui import style
from tui.grid import INDEX, Screen, Surface

C = INDEX

# (heading, [(key or "", text)]). A key makes the row a key cap; a row without
# one is a sentence.
PAGES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("THE FORTNIGHT", (
        ("", "A turn is a fortnight. You have a lamp's worth of hours in it,"),
        ("", "and every hour spent reading is an hour not spent elsewhere."),
        ("", "Reading a tablet costs two. The lamp shows what is left."),
        ("space", "end the fortnight and let the world move"),
    )),
    ("THE WINDOWS", (
        ("s", "the stack — what arrived; press 1-9 to read one"),
        ("t", "the stores — what is counted, and how it has moved"),
        ("r", "the roll — who is owed and who was paid"),
        ("m", "the muster — where the men are and what they are doing"),
        ("o", "the oaths — the clauses you are bound by, in full"),
        ("l", "the land — the gauge, the floor, the seed, the hands"),
        ("h", "the house — your family, and who stands to inherit"),
        ("esc", "close a window. the hall never closes but to leave"),
    )),
    ("THE WHOLE POINT", (
        ("", "Every window is a real window. Drag two apart and read them"),
        ("", "together: the letter beside the ledger it makes a claim about."),
        ("", "Nothing in this game will tell you that a figure is wrong."),
        ("", "A man reporting his own affairs reports them as he would like"),
        ("", "them read, and the scribe who copied him made his own errors."),
        ("", "The only correction is a second source."),
    )),
    ("WHAT IT WILL NOT DO", (
        ("", "It will not warn you. It will not rank what is urgent."),
        ("", "It will not confirm that an offering was accepted, or that a"),
        ("", "letter was well received. If you want to know, look, and if"),
        ("", "looking costs an hour then that is what knowing costs."),
    )),
)


def compose(width: int = 74, height: int = 34) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="HELP",
                note="[esc] close", drop=False)
    y = 2
    for title, rows in PAGES:
        if y >= height - 2:
            break
        style.bar(surface, 2, y, width - 4, " " + title,
                  fg=C["bone"], bg=C["faint"])
        y += 1
        for key, text in rows:
            if y >= height - 2:
                break
            if key:
                style.keycap(surface, 3, y, key, text[: width - 9 - len(key)])
            else:
                surface.text(5, y, text[: width - 7], C["clay"], C["ink"])
            y += 1
        y += 1
    return surface.freeze()
