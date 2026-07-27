"""The works: what is being built, and what could be (spec 6.21, M12).

Two lists in one window, because they are the same decision seen from either
end. Above: the men who are already out, how many days they have put in, and
what they have eaten doing it. Below: what else could be put up, and what it
would cost in days.

What this window will not tell you is **when anything will be finished**. It
cannot: that depends on corvée you have not raised yet and a season you cannot
hurry. A completion date would be the one honest-looking lie on the screen.

Nor does anything here say a project is a good idea. Building is a bet on which
crisis is coming, made with the hands that feed you and settled a year and a
half later (6.21), and the game does not grade bets (D19).
"""
from __future__ import annotations

from tui import art, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

PICK = "abcdefgh"          # the works in hand
ORDER = "123456789"        # what could be built


def _bar(surface: Surface, x: int, y: int, width: int,
         done: int, needed: int) -> None:
    filled = 0 if needed <= 0 else min(width, done * width // needed)
    style.meter(surface, x, y, width, filled, fg=C["barley"])


def compose(b: dict, selected: str = "", width: int = 82,
            height: int = 32) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE WORKS",
                note="[esc] close", drop=False)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])

    projects = b.get("projects") or []
    plans = b.get("plans") or []
    land = b.get("land") or {}
    raised = land.get("corvee_days", 0)
    given = land.get("works_days", 0)

    style.bar(surface, 2, 3, width - 4, "  MEN OUT", fg=C["bone"],
              bg=C["faint"])
    y = 5
    if not projects:
        surface.text(4, y, "nobody is building anything.", C["ash"], C["ink"])
        y += 2
    for index, project in enumerate(projects[:len(PICK)]):
        key = PICK[index]
        chosen = key == selected
        style.keycap(surface, 3, y, key, "")
        surface.text(8, y, project["what"][:26],
                     C["bone"] if chosen else C["clay"], C["ink"])
        surface.text(35, y, "making it whole" if project["repair"]
                     else "putting it up", C["dim"], C["ink"])
        _bar(surface, 52, y, 12, project["days_done"], project["days_needed"])
        surface.text(65, y, f"{project['days_done'] * 100 // max(1, project['days_needed'])}%",
                     C["sand"], C["ink"])
        spent = project.get("spent") or {}
        if spent:
            # Heaviest first: the grain is the number that matters and the
            # oil is a rounding error nobody would have started a war over.
            eaten = ", ".join(
                f"{qty:,} {good}" for good, qty
                in sorted(spent.items(), key=lambda kv: (-kv[1], kv[0])))
            surface.text(8, y + 1, f"eaten so far: {eaten}"[:42],
                         C["ash"], C["ink"])
        surface.text(52, y + 1,
                     f"{project['days_done']:,} of {project['days_needed']:,} days",
                     C["dim"], C["ink"])
        y += 3

    # The pool. Both numbers, because the difference between them is the thing
    # the player is actually spending and it is nowhere else in the game.
    style.rule(surface, 3, y, width - 6)
    surface.text(4, y + 1, "the corvée, this season", C["dim"], C["ink"])
    surface.text(34, y + 1, f"{raised:,} days called up", C["clay"], C["ink"])
    surface.text(34, y + 2, f"{given:,} given to the works", C["clay"], C["ink"])
    surface.text(34, y + 3, f"{max(0, raised - given):,} left to the fields",
                 C["bone"], C["ink"])
    if not b.get("works_season", True):
        surface.text(4, y + 3, "the rains are on", C["ash"], C["ink"])
    y += 5

    style.bar(surface, 2, y, width - 4, "  WHAT COULD BE PUT UP",
              fg=C["bone"], bg=C["faint"])
    y += 2
    per = b.get("works_materials") or {}
    for index, plan in enumerate(plans):
        if y >= height - 4:
            break
        style.keycap(surface, 3, y, ORDER[index] if index < 9 else " ", "")
        surface.text(8, y, plan["name"][:24], C["clay"], C["ink"])
        surface.text(33, y, f"{plan['days']:,} days", C["dim"], C["ink"])
        cost = ", ".join(
            f"{qty * plan['days'] // 1000:,} {good}"
            for good, qty in sorted(per.items()) if qty)
        surface.text(44, y, cost[: width - 47], C["ash"], C["ink"])
        y += 1

    note = (" [x] call them off — what they have eaten is eaten"
            if selected else
            " [1-9] set it in hand   [a-h] a work already out   [esc] close")
    style.bar(surface, 2, height - 2, width - 4, note,
              fg=C["clay"], bg=C["lapis"])
    return surface.interactive()
