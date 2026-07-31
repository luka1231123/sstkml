"""Stores, Roll, Land, Muster, and Oaths as workbenches (UI/UX spec 15).

These five were read-only tablets. Every order they described -- the ration,
the seed opened for food, the formation sent to a place, the oath re-sworn --
had to be given through Counsel. That made a language interpreter the only
mechanical route, although the model may never be the authority for an action.

So each is now a list, the selected thing's detail, and the orders that belong
to it, laid out by `tui/workbench.py`. What is here is the *reading*: which rows
a screen has, what the detail of one says, and which of the registry's actions
apply to what is currently selected.

Quantities are stepped with `[` and `]` rather than typed. A ration is chosen by
feel against a figure on the same screen, and stepping keeps the whole screen
operable from the keyboard and the mouse alike; the command palette is there for
the player who knows the exact number he wants.
"""
from __future__ import annotations

import registry
from tui import render, style
from tui.grid import InteractiveScreen, sparkline
from tui.workbench import Control, Row, affordable, compose

# What `[` and `]` move by on each screen. Coarse enough to reach a useful
# figure in a few presses, and never so fine that stepping is a chore.
STEPS = {"roll": 50, "stores": 50, "corvee": 5, "dredge": 5,
         "land_due": 25, "expiate": 10}

TASKS = ("garrison", "watch", "harvest", "campaign")

# Which store rows are a ledger the king can have counted. `inspect_ledger`
# takes `granary` or `seed` and nothing else, so the control is offered on
# exactly those two rows and is plainly absent on the others.
LEDGER_OF = {"grain": "granary", "seed_grain": "seed"}


def key_for(action_id: str) -> str:
    """The key a control prints, which is the registry's mnemonic and no other.

    Taken from the registry rather than typed here, so the Field Manual cannot
    document one key while the screen prints another -- the fifth of the
    audit's systemic problems, where help, labels, and handlers had already
    drifted apart because each was authored separately.
    """
    descriptor = registry.BY_ID.get(action_id)
    return descriptor.mnemonic if descriptor else "?"


def _spoken(value: str) -> str:
    return str(value).replace("_", " ")


def _compact_good(good: str, amount: int) -> str:
    """A complete quantity that fits a workbench detail column."""
    shown = (render.fmt_good(good, amount)
             .replace(" parisu ", "p ")
             .replace(" talent ", "tal ")
             .replace(" shekel", "sh")
             .replace(" jar ", "jr ")
             .replace(" qa", "qa")
             .replace(" log", "log"))
    for empty_remainder in (" 0qa", " 0sh", " 0log"):
        if shown.endswith(empty_remainder):
            shown = shown[:-len(empty_remainder)]
    return shown


# --- the stores ---------------------------------------------------------------

STOREHOUSE_VIEWS = (
    ("stores", "STORES"),
    ("roll", "LABOUR"),
    ("land", "LAND"),
)


def stores(b: dict, selected: str = "", width: int = 76, height: int = 26,
           scroll: int = 0, amount: int = 0, notice: str = "",
           hours: int = 0, room: bool = False) -> InteractiveScreen:
    goods = sorted(b.get("stores", {}).items())
    rows = [
        Row(good, (
            (_spoken(good), "clay"),
            (render.fmt_good(good, held),
             "gold" if good in ("bronze", "copper", "tin") else "barley"),
            (sparkline(b.get("store_history", {}).get(good, []), 12), "dim"),
        ), mark="·" if good in LEDGER_OF else "")
        for good, held in goods
    ]
    # The two records that say whether the bronze in service is being eaten.
    metal = b.get("metal", {})
    rows.append(Row("bronze_in_use", (
        ("bronze in use", "clay"),
        (render.fmt_good("bronze", metal.get("bronze_in_circulation", 0)),
         "gold"), ("equipment", "dim"))))
    rows.append(Row("melt_ledger", (
        ("melt ledger", "clay"),
        (render.fmt_good("bronze", metal.get("melt_ledger", 0)), "blood"),
        ("taken back", "dim"))))

    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    held = dict(goods).get(selected)
    ledger = LEDGER_OF.get(selected, "")
    inspected = set(b.get("inspected", []))

    detail: list[tuple[str, str]] = [(_spoken(selected).upper(), "gold"), ("", "ink")]
    if held is not None:
        detail.append((f"counted  {_compact_good(selected, held)}", "clay"))
        detail.append(
            ("your inspected count" if ledger in inspected
             else "keeper's count", "dim"))
        history = b.get("store_history", {}).get(selected, [])
        if history:
            detail += [
                ("", "ink"),
                ("RECENT COUNTS", "gold"),
                (sparkline(history, min(18, width)), "dim"),
            ]
            if len(history) > 1:
                change = history[-1] - history[0]
                detail.append((
                    f"{change:+,} base units",
                    "barley" if change >= 0 else "blood"))
    if ledger:
        detail += [
            ("", "ink"),
            (f"[i] have the {ledger} counted, and see", "sand"),
            ("    what is really on the floor", "sand"),
        ]
    if selected == "seed_grain":
        detail += [
            ("", "ink"),
            (f"open {amount:,} qa for food", "flame"),
            ("[ and ] change the amount; [e] opens it", "dim"),
            ("what is eaten is not sown", "ash"),
        ]
    if selected in {
            "bronze", "copper", "tin", "bronze_in_use", "melt_ledger"}:
        detail += [
            ("", "ink"),
            ("METAL ACCOUNT", "gold"),
            ("in service  " + _compact_good(
                "bronze", metal.get("bronze_in_circulation", 0)), "clay"),
            ("melted      " + _compact_good(
                "bronze", metal.get("melt_ledger", 0)), "blood"),
        ]

    controls = []
    if ledger:
        controls.append(affordable(
            Control("inspect_ledger", key_for("inspect_ledger")), hours))
    if selected == "seed_grain" and amount > 0:
        controls.append(Control(
            "eat_seed", key_for("eat_seed"),
            label=f"open {amount:,} qa for food"))
    note = (
        "↑↓ choose   [ ] set an amount   [e] open it for food   [esc] close"
        if selected == "seed_grain" else
        "↑↓ choose   [i] inspect   [esc] close")
    return compose(
        "THE STOREHOUSE" if room else "THE STORES",
        ("good", "counted", "recent"), (18, -22, 12),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="the storehouse is empty.",
        note=note,
        views=STOREHOUSE_VIEWS if room else (), view="stores")


# --- the roll -----------------------------------------------------------------

def roll(b: dict, selected: str = "", width: int = 82, height: int = 28,
         scroll: int = 0, amount: int = 0, priority: tuple = (),
         notice: str = "", hours: int = 0,
         room: bool = False) -> InteractiveScreen:
    groups = list(b.get("groups", []))
    rows = []
    for group in groups:
        weeks = group["arrears_weeks"]
        rows.append(Row(group["id"], (
            (group["name"], "clay"),
            (str(group["size"]), "dim"),
            (f"{group['allocated']:,}", "dim"),
            (f"{weeks}" if weeks else "—",
             "blood" if weeks >= 4 else ("flame" if weeks else "ash")),
            (group["loyalty"], "blood" if weeks >= 4 else "dim"),
        ), mark="!" if group["id"] in priority else ""))
    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    group = next((g for g in groups if g["id"] == selected), None)

    detail: list[tuple[str, str]] = []
    if group is not None:
        weeks = group["arrears_weeks"]
        detail = [
            (group["name"][:34], "gold"), ("", "ink"),
            (f"{group['size']} heads", "clay"),
            (f"allocated {group['allocated']:,} qa", "clay"),
            (f"unpaid {weeks} fortnight{'s' if weeks != 1 else ''}"
             if weeks else "paid in full",
             "blood" if weeks >= 4 else ("flame" if weeks else "dim")),
            (f"they are {group['loyalty']}", "dim"),
            ("", "ink"),
        ]
        if amount > 0:
            detail += [
                (f"allocate {amount:,} qa", "flame"),
                ("[a] enters this ration", "dim"),
            ]
        else:
            detail.append(("[ ] choose a ration amount", "dim"))
        if group["id"] in priority:
            detail += [("", "ink"), ("marked first in a short fortnight", "sand")]
        if group.get("function"):
            detail += [("", "ink"),
                       (f"they are the {_spoken(group['function'])}", "sand")]

    marked = len(priority)
    controls = []
    if group is not None and amount > 0:
        controls.append(affordable(Control(
            "allocate", key_for("allocate"),
            label=f"allocate {amount:,} qa"), hours))
    controls += [
        Control("set_priority", key_for("set_priority"),
                label=(f"priority: {marked} marked, [enter] to order"
                       if marked else "mark for priority"),
                enabled=group is not None),
        affordable(Control("send_to_harvest", key_for("send_to_harvest"),
                           label="send to the fields",
                           enabled=group is not None), hours),
    ]
    return compose(
        ("THE STOREHOUSE — LABOUR AND RATIONS" if room else
         "THE ROLL — what is owed and what was paid"),
        ("group", "heads", "allocated qa", "unpaid", "they are"),
        (26, -5, -13, -6, 12),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="nobody is on the roll.",
        note="↑↓ choose   [ ] set an amount   [a] allot   [p] mark   [enter] order   [esc] close",
        views=STOREHOUSE_VIEWS if room else (), view="roll")


# --- the land -----------------------------------------------------------------

def land(b: dict, selected: str = "", width: int = 80, height: int = 28,
         scroll: int = 0, days: int = 0, notice: str = "",
         hours: int = 0, group: str = "",
         room: bool = False) -> InteractiveScreen:
    data = b.get("land") or {}
    estates = list(data.get("estates", []))
    rows = []
    for estate in estates:
        canal = estate.get("canal_condition")
        water = (f"canal {canal}" if estate.get("irrigated")
                 and canal is not None else "rain-fed")
        rows.append(Row(estate["id"], (
            (estate["name"], "sand"),
            (_spoken(estate["place"]), "dim"),
            (water, "sky" if estate.get("irrigated") else "ash"),
            (f"{estate['hands']} hands", "clay"),
        )))
    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    estate = next((e for e in estates if e["id"] == selected), None)

    rate = data.get("land_due_rate", 0)
    detail: list[tuple[str, str]] = [
        (f"the river gauge stands at {data.get('gauge', 0)} · "
         f"the fields are in {data.get('stage', 'low water')}", "sky"),
        (f"last year the land gave the crown "
         f"{_compact_good('grain', data.get('last_land_due', 0))}", "barley"),
        (f"land due ordered   {rate}/1000", "gold"),
        (f"seed in store      "
         f"{_compact_good('grain', data.get('seed_in_store', 0))}", "sand"),
        (f"seed in the ground "
         f"{_compact_good('grain', data.get('seed_in_ground', 0))}", "sand"),
        (f"the ground can take "
         f"{_compact_good('grain', data.get('seed_recommended', 0))}", "dim"),
        (f"hands {data.get('labour_days_this_turn', 0):,}d available · "
         f"work asks {data.get('labour_days_needed', 0):,}d · "
         f"corvée {data.get('corvee_days', 0):,}d", "clay"),
    ]
    if estate is not None:
        detail += [
            ("THE ESTATE", "gold"),
            (f"ground {estate['extent']:,} qa · capacity "
             f"{estate['capacity']:,} · {estate['hands']} hands", "sand"),
            (f"sown {estate['under_crop']:,} qa · "
             f"open {max(0, estate['extent'] - estate['under_crop']):,} qa",
             "verdigris" if estate['under_crop'] else "ash"),
            (f"the palace holds "
             f"{_compact_good('grain', estate['seed'])} seed · "
             f"{_compact_good('grain', estate['sheaves'])} sheaves · "
             f"{_compact_good('grain', estate['grain'])} grain", "dim"),
        ]
    detail += [
        (f"{days} days in hand" if days else "[ ] choose work days",
         "flame" if days else "dim"),
        ("[< >] land due ±25", "dim"),
    ]

    # Hands come from the Roll, but the decision to send them belongs here,
    # where the gauge and the sowing are on the same screen. The group is
    # cycled rather than typed, so the whole order is one screen's work. The
    # chosen group names the send control in the footer, so the detail keeps
    # itself for the estate dossier.
    hands = [g for g in b.get("groups", [])]
    chosen_group = next((g for g in hands if g["id"] == group), None)

    controls = []
    if days > 0:
        controls.append(affordable(Control(
            "raise_corvee", key_for("raise_corvee"),
            label=f"raise corvée {days}d"), hours))
    if estate is not None and estate.get("irrigated") and days > 0:
        controls.append(affordable(Control(
            "dredge_canal", key_for("dredge_canal"),
            label=f"dredge {days}d"), hours))
    controls += [
        affordable(Control("inspect_ledger", key_for("inspect_ledger"), label="count the seed"),
                   hours),
        Control("set_land_due", key_for("set_land_due"), label=f"land due {rate}/1000"),
    ]
    if chosen_group is not None:
        controls.append(affordable(Control(
            "send_to_harvest", key_for("send_to_harvest"),
            label="send " + chosen_group["name"][:18]), hours))
    return compose(
        "THE STOREHOUSE — ESTATES AND HARVEST" if room else "THE LAND",
        ("estate", "place", "water", "hands"),
        (22, -10, 10, -8),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="this house holds no estates.",
        note="↑↓ choose   [ ] set days   [< >] land due   [c] call up   [g] group   [h] to the fields   [esc] close",
        views=STOREHOUSE_VIEWS if room else (), view="land")


# --- the corvée: labour and arms ----------------------------------------------

def muster(b: dict, selected: str = "", width: int = 80, height: int = 27,
           scroll: int = 0, task: str = "garrison", place: str = "",
           amount: int = 0, notice: str = "",
           hours: int = 0) -> InteractiveScreen:
    troops = b.get("troops", {})
    land = b.get("land") or {}
    formations = list(troops.get("formations", []))
    groups = list(b.get("groups", []))
    rows = [
        Row("corvee:levy", (
            ("crown corvée", "gold"),
            (f"{land.get('corvee_days', 0):,}d", "flame"),
            ("called", "clay"),
            ("this fortnight", "dim"),
        )),
        *[
            Row(f"hands:{group['id']}", (
                ("hands · " + group["name"], "clay"),
                (str(group["size"]), "dim"),
                (_spoken(group["function"]), "sand"),
                (_spoken(group["place"]), "dim"),
            ))
            for group in groups
        ],
        *[
        Row(f["id"], (
            (f["name"], "clay"),
            (str(f["strength"]), "dim"),
            (f["task"], "flame" if f["task"] == "campaign" else "clay"),
            (_spoken(f["place"]), "dim"),
        ))
        for f in formations
        ],
    ]
    for holding, men in sorted(troops.get("garrisons", {}).items()):
        rows.append(Row(f"garrison:{holding}", (
            ("holding " + _spoken(holding), "ash"), (str(men), "ash"),
            ("", "ash"), ("men", "ash"))))
    for summons in troops.get("summons", []):
        due = (f"OVERDUE {summons['due_turn']}" if summons["overdue"]
               else f"due {summons['due_turn']}")
        rows.append(Row(f"summons:{summons['place']}", (
            ("summons · " + _spoken(summons["place"]),
             "blood" if summons["overdue"] else "flame"),
            (f"{summons['mustered']}/{summons['required']}",
             "blood" if summons["mustered"] < summons["required"] else "clay"),
            (due, "blood" if summons["overdue"] else "dim"),
            (_spoken(summons["oath_id"]), "dim"),
        ), mark="!" if summons["overdue"] else ""))

    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    formation = next((f for f in formations if f["id"] == selected), None)
    group = next(
        (item for item in groups if f"hands:{item['id']}" == selected), None)

    detail: list[tuple[str, str]] = []
    if formation is not None:
        detail = [
            (formation["name"][:30], "gold"),
            (f"corvée called · {land.get('corvee_days', 0):,} person-days",
             "flame"),
            ("        ╱╲", "sand"),
            ("    ◉──╫════▷", "gold"),
            ("   ╱█╲ ║", "clay"),
            ("   ╱ ╲ ╨", "sand"),
            (" SPEAR-BEARER OF THE LEVY", "dim"),
            ("", "ink"),
            (f"{formation['strength']} men", "clay"),
            (f"now {formation['task']} at {_spoken(formation['place'])}",
             "clay"),
            ("", "ink"),
            ("SEND THEM", "gold"),
            (f"task   {task}", "flame"),
            (f"place  {_spoken(place) or 'choose one'}",
             "flame" if place else "ash"),
            ("[t] next task   [l] next place", "dim"),
            ("[a] gives the order", "dim"),
        ]
    elif selected == "corvee:levy":
        detail = [
            ("THE KING'S CALL", "gold"), ("", "ink"),
            (f"called already   {land.get('corvee_days', 0):,} person-days",
             "flame"),
            (f"hands available  {land.get('labour_days_this_turn', 0):,}d",
             "clay"),
            (f"fields ask       {land.get('labour_days_needed', 0):,}d",
             "dim"),
            (f"works consume    {land.get('works_days', 0):,}d", "dim"),
            ("", "ink"),
            (f"new call         {amount:,}d"
             if amount else "[ ] choose person-days", "ash"),
        ]
    elif group is not None:
        detail = [
            (group["name"][:30], "gold"), ("", "ink"),
            (f"{group['size']} people at {_spoken(group['place'])}", "clay"),
            (f"ordinary duty · {_spoken(group['function'])}", "sand"),
            (f"ration arrears · {group['arrears_weeks']} fortnights", "dim"),
            ("", "ink"),
            ("The same hands feed workshops, fields,", "dim"),
            ("building sites, and the levy.", "dim"),
        ]
    elif selected.startswith("summons:"):
        detail = [("A SUMMONS", "gold"), ("", "ink"),
                  ("choose a formation above, then send it", "dim")]

    detail += [
        ("", "ink"),
        (f"CALL IN HAND · {amount:,} PERSON-DAYS"
         if amount else "[ and ] set a new corvée call", "dim"),
    ]
    controls = [
        affordable(Control(
            "raise_corvee", key_for("raise_corvee"),
            label=f"raise corvée {amount:,}d" if amount else "raise corvée",
            enabled=amount > 0,
            why="choose person-days with [ and ]"), hours),
        affordable(Control("assign_troops", key_for("assign_troops"),
                           label=f"send to {task}"
                                 + (f" at {_spoken(place)}" if place else ""),
                           enabled=formation is not None and bool(place),
                           why="choose a formation and a place"), hours),
        Control("place_person", key_for("place_person"), label="give it a commander",
                enabled=formation is not None),
        Control("dismiss_person", key_for("dismiss_person"), label="take the command away",
                enabled=formation is not None),
    ]
    return compose(
        "THE MUSTER — LEVY AND SPEAR",
        ("levy / formation / summons", "heads", "duty", "place"),
        (24, -5, 10, 14),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="no hands or formations are recorded.",
        note="↑↓ choose   [ ] set days   [c] call up   [t] task   [l] place   [esc] close")


# --- the oaths ----------------------------------------------------------------

def oaths(b: dict, selected: str = "", width: int = 78, height: int = 28,
          scroll: int = 0, amount: int = 0, notice: str = "",
          hours: int = 0) -> InteractiveScreen:
    held = list(b.get("oaths", []))
    rows = []
    for oath in held:
        state = ("dissolved" if oath["dissolved"] else
                 "LAPSED" if oath["lapsed"] else "sworn")
        rows.append(Row(oath["id"], (
            (_spoken(oath["id"]), "ash" if oath["dissolved"] else
             ("wine" if oath["lapsed"] else "clay")),
            (state, "wine" if oath["lapsed"] else "dim"),
            (", ".join(_spoken(god) for god in oath["gods"]), "wine"),
        ), mark="!" if oath["lapsed"] else ""))
    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    oath = next((o for o in held if o["id"] == selected), None)

    detail: list[tuple[str, str]] = []
    if oath is not None:
        detail = [(_spoken(oath["id"])[:32], "gold"), ("", "ink")]
        detail.append(("before " + ", ".join(
            _spoken(god) for god in oath["gods"]), "wine"))
        detail.append(("between " + ", ".join(
            render.actor_name(party, b.get("house"))
            for party in oath["parties"]), "dim"))
        if oath["lapsed"]:
            detail += [
                ("", "ink"),
                ("sworn by " + render.actor_name(
                    oath["sworn_by"], b.get("house")) + ", who is dead",
                 "wine"),
                ("nobody is bound until it is sworn again", "wine"),
            ]
        detail.append(("", "ink"))
        for clause in oath.get("clauses", []):
            detail.append(("· " + _clause(clause), "bone"))
        detail.append(("", "ink"))
        if amount > 0:
            detail += [(f"lay down {amount:,}", "flame"),
                       ("[x] makes this offering", "dim")]
        else:
            detail.append(("[ ] choose an offering", "dim"))

    controls = []
    if oath is not None and oath.get("lapsed", False):
        controls.append(affordable(
            Control("swear_oath", key_for("swear_oath")), hours))
    if oath is not None and amount > 0:
        controls.append(affordable(Control(
            "expiate", key_for("expiate"),
            label=f"expiate with {amount:,}"), hours))
    return compose(
        "THE OATHS", ("tablet", "standing", "before"), (26, -12, 20),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="no oath tablet is held in this archive.",
        note="↑↓ choose   [ ] set an amount   [esc] close")


def _clause(clause: dict) -> str:
    """A clause in the words the tablet uses. Kept identical to `document`."""
    from tui.document import _clause as spoken
    return spoken(clause)
