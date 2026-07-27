"""The city: the machine, and its condition as a history (spec 6.18, M12).

The screen exists because of a specific failure mode. A system with two hidden
multipliers, a head who flatters one of them, and decay measured in years can
become a thing the player cannot form a theory about — and a system you cannot
form a theory about reads as random, which is worse than reads as hard.

So condition is shown **as a shape, not a number**. Twelve fortnights of
sparkline per institution: a line that sags tells the player something he can
act on, where 604 tells him nothing at all. The figure is beside it for anyone
who wants to do the arithmetic.

What is not here: any statement that a condition is bad, any threshold, any
colour that means danger on its own, and any suggestion about what to repair
first. The player reads the shapes and decides (D19).
"""
from __future__ import annotations

from tui import document, style
from tui.grid import INDEX, Screen, Surface, sparkline

C = INDEX

# What each kind stops doing when it stops. Stated plainly and without warning:
# the player should be able to learn the machine by reading it once.
DOES = {
    "harbour": "clears cargoes",
    "granary": "holds the grain",
    "walls": "stands, or does not",
    "workshop": "makes bronze",
    "temple": "keeps the rites",
    "archive": "finds tablets",
    "canal": "waters the fields",
    "road": "carries couriers",
    "household": "attends you",
    "garrison": "holds the place",
}


def compose(b: dict, history: dict[str, list[int]] | None = None,
            width: int = 88, height: int = 28) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE CITY",
                note="[esc] close", drop=False)

    institutions = b.get("institutions") or []
    history = history or {}

    style.bar(surface, 2, 2, width - 4,
              "  what stands             it              he has been saying"
              "   now   kept by", fg=C["bone"], bg=C["faint"])

    y = 4
    for inst in institutions:
        if y >= height - 5:
            break
        # Vacant posts are marked with a word, never with a colour alone.
        vacancy = "" if inst["head"] else "no one minds it"
        surface.text(3, y, inst["name"][:23], C["clay"], C["ink"])
        surface.text(27, y, DOES.get(inst["kind"], inst["kind"])[:16],
                     C["dim"], C["ink"])

        series = history.get(inst["id"]) or inst.get("history") or [
            inst["condition"]]
        line = sparkline(series, 12)
        surface.text(45, y, line, C["sand"], C["ink"])

        figure = str(inst["condition"])
        surface.text(64 - len(figure), y, figure,
                     C["bone"] if inst["inspected"] else C["dim"], C["ink"])
        surface.text(65, y, "!" if inst["inspected"] else " ",
                     C["barley"], C["ink"])

        staff = vacancy or inst["group_name"] or "—"
        surface.text(67, y, staff[: width - 70],
                     C["blood"] if vacancy else C["dim"], C["ink"])
        y += 1

    if not institutions:
        surface.text(3, y, "this court holds nothing that could fall down.",
                     C["ash"], C["ink"])

    foot = height - 4
    surface.text(3, foot, "─" * (width - 6), C["faint"], C["ink"])
    surface.text(3, foot + 1,
                 "the figure is what the man in charge of it reports. "
                 "a ! is one you went and saw.", C["ash"], C["ink"])
    style.bar(surface, 2, height - 2, width - 4,
              " [1-9] go and look for yourself — one hour   [esc] close",
              fg=C["clay"], bg=C["lapis"])
    return surface.freeze()


def detail(b: dict, inst: dict, history: list[int] | None = None,
           width: int = 62, height: int = 20) -> Screen:
    """One institution, opened. What it is, what it needs, what it can do."""
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    document._frame(surface, inst["name"].upper(), "[esc] close")
    surface.text(3, 2, DOES.get(inst["kind"], inst["kind"]), C["dim"], C["ink"])
    surface.text(3, 3, "─" * (width - 6), C["faint"], C["ink"])

    rows = [
        ("condition", f"{inst['condition']}"
                      + ("" if inst["inspected"] else "  (he says)")),
        ("whole, it could", f"{inst['capacity']}"),
        ("as it stands", f"{inst['effective']}"),
        ("kept by", inst["group_name"] or "nobody on the roll"),
        ("in the charge of", inst["head"] or "NOBODY — the post is vacant"),
        ("at", inst["place"]),
    ]
    y = 5
    for label, value in rows:
        surface.text(4, y, label, C["dim"], C["ink"])
        surface.text(24, y, value[: width - 28], C["clay"], C["ink"])
        y += 1
    if inst["upkeep"]:
        y += 1
        surface.text(4, y, "it wants, a fortnight", C["dim"], C["ink"])
        for good, qty in sorted(inst["upkeep"].items()):
            surface.text(24, y, f"{qty} {good}", C["clay"], C["ink"])
            y += 1
    if history:
        surface.text(4, height - 3, sparkline(history, width - 10),
                     C["sand"], C["ink"])
    return surface.freeze()
