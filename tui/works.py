"""The works: what is being built, and what could be (spec 6.21, M12).

Two lists in one window, because they are the same decision seen from either
end. Above: the men already out and what they have spent. Below: each plan's
live return, failure case, labour, supplies, upkeep, and current stock.

What this window will not tell you is **when anything will be finished**. It
cannot: that depends on corvée you have not raised yet and a season you cannot
hurry. A completion date would be the one honest-looking lie on the screen.

The window names the wager without grading it. Building is still a bet on which
crisis is coming, settled long after the supplies leave the store (6.21).
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
    materials = plan.get("materials")
    if materials is not None:
        return ", ".join(
            f"{qty:,} {good}" for good, qty in sorted(materials.items())
            if qty)
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
    if width >= 76:
        return False, 1
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


def _detail_rows(plan: dict, b: dict, width: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []

    def add(label: str, value: str, colour: int) -> None:
        wrapped = textwrap.wrap(
            f"{label} · {value}", width=max(1, width),
            break_long_words=False, break_on_hyphens=False) or [label]
        rows.extend((line, colour) for line in wrapped)

    rows.append((plan.get("category", "WORK"), C["bone"]))
    add("RETURN", plan.get("effect", "adds institutional capacity"), C["sky"])
    add("WAGER", plan.get("tradeoff", "uses labour and supplies"), C["flame"])
    rate = b.get("works_rate", 400)
    season = b.get("works_season_name", "low water") or "low water"
    add("LABOUR", f"{plan['days']:,} corvée days; at most {rate:,} each fortnight in {season}", C["clay"])
    add("SUPPLY", _material_cost(plan, b.get("works_materials") or {})
        or "labour only", C["barley"])
    upkeep = plan.get("upkeep") or {}
    if upkeep:
        add("UPKEEP", ", ".join(
            f"{qty:,} {good} each fortnight"
            for good, qty in sorted(upkeep.items())), C["sand"])
    stores = b.get("stores") or {}
    materials = plan.get("materials") or {}
    if materials:
        add("IN STORE", ", ".join(
            f"{stores.get(good, 0):,} {good}"
            for good in sorted(materials)), C["dim"])
    return rows


def _draw_detail(surface: Surface, plan: dict, b: dict, x: int, y: int,
                 width: int, bottom: int) -> None:
    for line, colour in _detail_rows(plan, b, width):
        if y >= bottom:
            break
        surface.text(x, y, line, colour, C["ink"])
        y += 1


def corvee_remaining(b: dict) -> int:
    land = b.get("land") or {}
    cap = max(0, land.get("corvee_max_days", 0)
              - land.get("corvee_days", 0))
    return min(cap, max(0, land.get("corvee_usable_days", cap)))


def corvee_unrest(b: dict, days: int) -> int:
    land = b.get("land") or {}
    increase = days * land.get("corvee_unrest_per_1000_days", 0) // 1000
    return min(max(0, 1000 - b.get("unrest", 0)), increase)


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
            scroll: int = 0, plan_scroll: int = 0,
            selected_plan: str = "", corvee_draft: int = 0) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE WORKS",
                note="[esc] close", drop=False)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    style.notice(surface, 2, 1, width - 4, notice)
    brief = (
        "CORVÉE, NOT COIN · LOW WATER · STORE-FED CREWS · NEW WORK OPENS HEADLESS"
        if width >= 76 else
        "CORVÉE, NOT COIN · LOW WATER · STORE-FED CREWS")
    surface.text(3, 2, brief[:max(0, width - 6)], C["dim"], C["ink"])

    projects = b.get("projects") or []
    plans = b.get("plans") or []
    land = b.get("land") or {}
    raised = land.get("corvee_days", 0)
    given = land.get("works_days", 0)
    remaining = corvee_remaining(b)
    call_open = land.get("corvee_call_open", True)
    corvee_draft = min(max(0, corvee_draft), remaining)
    draft_unrest = corvee_unrest(b, corvee_draft)

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
        mode = "making it whole" if project["repair"] else "putting it up"
        percent = f"{project['days_done'] * 100 // max(1, project['days_needed'])}%"
        content_right = width - 3
        bar_width = 12 if width >= 72 else 8
        bar_x = min(52, max(8, content_right - len(percent) - 1 - bar_width))
        percent_x = bar_x + bar_width + 1
        mode_x = min(35, max(8, bar_x - len(mode) - 2))
        name_width = max(1, mode_x - 9)
        style.keycap(surface, 3, y, key, "")
        surface.text(8, y, project["what"][:name_width],
                     C["bone"] if chosen else C["clay"], C["ink"])
        surface.text(mode_x, y, mode, C["dim"], C["ink"])
        _bar(surface, bar_x, y, bar_width,
             project["days_done"], project["days_needed"])
        surface.text(percent_x, y, percent, C["sand"], C["ink"])
        spent = project.get("spent") or {}
        days_text = (
            f"{project['days_done']:,} of {project['days_needed']:,} days")
        days_x = min(52, max(8, content_right - len(days_text) + 1))
        if spent:
            # Heaviest first: the grain is the number that matters and the
            # oil is a rounding error nobody would have started a war over.
            eaten = ", ".join(
                f"{qty:,} {good}" for good, qty
                in sorted(spent.items(), key=lambda kv: (-kv[1], kv[0])))
            surface.text(8, y + 1,
                         f"spent so far: {eaten}"[:max(0, days_x - 9)],
                         C["ash"], C["ink"])
        surface.text(days_x, y + 1, days_text, C["dim"], C["ink"])
        surface.text(8, y + 2, project.get("status", ""),
                     C["barley"] if project.get("status", "").startswith("able")
                     else C["ash"], C["ink"])
        y += 3
    if out.partial:
        surface.text(4, y, f"↑↓ men out {out.label()}", C["dim"], C["ink"])
        y += 1

    # The pool. Both numbers, because the difference between them is the thing
    # the player is actually spending and it is nowhere else in the game.
    style.rule(surface, 3, y, width - 6)
    surface.text(4, y + 1, "the corvée, this season", C["dim"], C["ink"])
    surface.text(34, y + 1,
                 f"{raised:,} called · {max(0, raised - given):,} free",
                 C["clay"], C["ink"])
    surface.text(4, y + 2, "given to the works", C["dim"], C["ink"])
    surface.text(34, y + 2, f"{given:,} days", C["clay"], C["ink"])
    if not call_open:
        away = land.get("corvee_call_opens_in", 0)
        opens = (f"opens in {away} fortnight{'s' if away != 1 else ''}"
                 if away else "opens before low water")
        surface.text(4, y + 3, "new crews cannot be called now",
                     C["ash"], C["ink"])
        surface.text(34, y + 3, opens, C["ash"], C["ink"])
    elif corvee_draft:
        surface.text(4, y + 3, f"draft {corvee_draft:,} more days",
                     C["flame"], C["ink"])
        surface.text(34, y + 3, f"unrest +{draft_unrest} · [c] levy",
                     C["flame"], C["ink"])
    elif remaining:
        step = min(remaining, max(1, b.get("works_rate", 400)))
        surface.text(4, y + 3, f"[ ] draft {step:,} more days",
                     C["ash"], C["ink"])
    else:
        enough = ("commission a work before calling crews"
                  if not projects else
                  "enough crews are already called for this season")
        surface.text(4, y + 3, enough, C["ash"], C["ink"])
    season_note = (
        "crews start next fortnight"
        if call_open and not b.get("works_season", True) else
        "low water closes; the next advance brings no work"
        if b.get("works_season", True) and not call_open else
        "low water: crews can work while the fields are idle"
        if b.get("works_season", True) else
        "work begins at low water")
    surface.text(4, y + 4, season_note, C["ash"], C["ink"])
    y += 5

    style.bar(surface, 2, y, width - 4, "  WHAT COULD BE PUT UP",
              fg=C["bone"], bg=C["faint"])
    y += 2
    per = b.get("works_materials") or {}
    stacked, plan_height = _plan_shape(b, width)
    buildable = plan_page(b, width, height, scroll, plan_scroll)
    visible = buildable.slice(plans)
    chosen = next((plan for plan in visible
                   if plan.get("kind") == selected_plan), None)
    chosen = chosen or (visible[0] if visible else None)
    wide = width >= 76
    list_top = y
    divider = max(36, min(42, width // 2))
    for number, _absolute, plan in buildable.rows(plans):
        active = chosen is not None and plan.get("kind") == chosen.get("kind")
        style.keycap(surface, 3, y, ORDER[number - 1], "")
        right = divider if wide else width - 2
        surface.text(8, y, plan["name"][:max(1, right - 20)],
                     C["bone"] if active else C["clay"], C["ink"])
        days = f"{plan['days']:,}d"
        surface.text(max(8, right - len(days) - 2), y, days,
                     C["sand"], C["ink"])
        surface.link(2, y, max(1, right - 3), plan_height,
                     f"works:plan:{plan.get('kind', '')}")
        cost = _material_cost(plan, per)
        if stacked:
            for offset, line in enumerate(_cost_lines(cost, width), 1):
                surface.text(8, y + offset, line, C["ash"], C["ink"])
        y += plan_height

    if wide and chosen is not None:
        for row in range(list_top, height - 2):
            surface.put(divider, row, "│", C["faint"], C["ink"])
        _draw_detail(surface, chosen, b, divider + 3, list_top,
                     max(1, width - divider - 5), height - 2)

    if buildable.partial and y < height - 2:
        paging = (
            f"shift+↑↓ plans {buildable.label()}" if buildable.room
            else "plans do not fit · enlarge this window")
        edge = divider if wide else width - 2
        surface.text(8, y, paging[:max(0, edge - 8)], C["dim"], C["ink"])
    visible_plans = len(buildable.slice(plans))
    plan_keys = (
        f"[1-{visible_plans}]" if visible_plans > 1
        else "[1]" if visible_plans else "")
    plan_action = (
        f"{plan_keys} inspect · [enter] commission" if plan_keys
        else "enlarge to see plans")
    if corvee_draft:
        note = (f" [ ] corvée {corvee_draft:,}d · unrest +{draft_unrest}"
                " · [c] levy")
    elif selected:
        note = (" [x] call off" +
                (" · [ ] draft corvée" if call_open and remaining else ""))
    else:
        note = (f" {plan_action}" +
                (" · [ ] corvée" if call_open and remaining else ""))
    style.bar(surface, 2, height - 2, width - 4, note,
              fg=C["clay"], bg=C["lapis"])
    return surface.interactive()
