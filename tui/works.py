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

import textwrap

from tui import art, collection, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

PICK = "abcdefgh"          # the works in hand
ORDER = "123456789"        # what could be built


def _bar(surface: Surface, x: int, y: int, width: int,
         done: int, needed: int) -> None:
    filled = 0 if needed <= 0 else min(width, done * width // needed)
    style.meter(surface, x, y, width, filled, fg=C["barley"])


def project_room(height: int) -> int:
    """Works in hand visible at once; three rows apiece."""
    return max(1, min(len(PICK), (height - 16) // 3))


def _project_page(b: dict, height: int, scroll: int) -> collection.Page:
    return collection.page(
        len(b.get("projects") or []), project_room(height), scroll)


def _plan_top(b: dict, height: int, scroll: int) -> int:
    """First row available to plans, matching the project/pool layout below."""
    projects = b.get("projects") or []
    out = _project_page(b, height, scroll)
    y = 5
    y += len(out.slice(projects)) * 3 if projects else 2
    if out.partial:
        y += 1
    # Rule and four corvée rows, then the plan heading and its spacer.
    return y + 7


def _material_cost(plan: dict, per: dict) -> str:
    return ", ".join(
        f"{qty * plan['days'] // 1000:,} {good}"
        for good, qty in sorted(per.items()) if qty)


def _cost_lines(cost: str, width: int) -> list[str]:
    """A complete stacked cost; no quantity or unit is discarded."""
    return textwrap.wrap(
        f"cost: {cost or 'labour only'}",
        width=max(1, width - 10),
        break_long_words=True,
        break_on_hyphens=False,
    ) or ["cost: labour only"]


def _plan_shape(b: dict, width: int) -> tuple[bool, int]:
    """Whether costs need their own rows, and rows consumed by each plan."""
    plans = b.get("plans") or []
    per = b.get("works_materials") or {}
    costs = [_material_cost(plan, per) for plan in plans]
    inline_room = max(0, width - 47)
    stacked = any(len(cost) > inline_room for cost in costs)
    if not stacked:
        return False, 1
    cost_rows = max(
        (len(_cost_lines(cost, width)) for cost in costs),
        default=1,
    )
    return True, 1 + cost_rows


def plan_page(b: dict, width: int, height: int, scroll: int = 0,
              plan_scroll: int = 0) -> collection.Page:
    """The plans whose numbered actions are genuinely visible.

    The controller uses this same page. A digit therefore cannot name a plan
    that the current window did not draw.
    """
    plans = b.get("plans") or []
    _stacked, row_height = _plan_shape(b, width)
    available = max(0, height - 2 - _plan_top(b, height, scroll))
    room = min(len(ORDER), available // row_height)
    visible = collection.page(len(plans), room, plan_scroll)
    if visible.partial:
        # A partial list spends one row saying how Shift+arrows reaches it.
        room = min(len(ORDER), max(0, available - 1) // row_height)
        visible = collection.page(len(plans), room, plan_scroll)
    return visible


def compose(b: dict, selected: str = "", width: int = 82,
            height: int = 32, notice: str = "",
            scroll: int = 0, plan_scroll: int = 0) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE WORKS",
                note="[esc] close", drop=False)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    style.notice(surface, 2, 1, width - 4, notice)

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
    # Three rows a project, so the page is what the window can actually hold.
    out = _project_page(b, height, scroll)
    for number, _absolute, project in out.rows(projects):
        key = PICK[number - 1]
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
    if out.partial:
        surface.text(4, y, f"↑↓ men out {out.label()}", C["dim"], C["ink"])
        y += 1

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
    stacked, plan_height = _plan_shape(b, width)
    buildable = plan_page(b, width, height, scroll, plan_scroll)
    for number, _absolute, plan in buildable.rows(plans):
        style.keycap(surface, 3, y, ORDER[number - 1], "")
        surface.text(8, y, plan["name"][:24], C["clay"], C["ink"])
        surface.text(33, y, f"{plan['days']:,} days", C["dim"], C["ink"])
        cost = _material_cost(plan, per)
        if stacked:
            for offset, line in enumerate(_cost_lines(cost, width), 1):
                surface.text(8, y + offset, line, C["ash"], C["ink"])
        else:
            surface.text(44, y, cost, C["ash"], C["ink"])
        y += plan_height

    if buildable.partial and y < height - 2:
        paging = (
            f"shift+↑↓ plans {buildable.label()}" if buildable.room
            else "plans do not fit · enlarge this window")
        surface.text(8, y, paging, C["dim"], C["ink"])
    visible_plans = len(buildable.slice(plans))
    plan_keys = (
        f"[1-{visible_plans}]" if visible_plans > 1
        else "[1]" if visible_plans else "")
    plan_action = (
        f"{plan_keys} set it in hand" if plan_keys
        else "enlarge to see plans")
    note = (" [x] call them off — what they have eaten is eaten"
            if selected else
            f" {plan_action}   [a-h] a work already out   [esc] close")
    style.bar(surface, 2, height - 2, width - 4, note,
              fg=C["clay"], bg=C["lapis"])
    return surface.interactive()
