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
from belief import project
from tui import dues as due_text
from tui import render, style
from tui.grid import INDEX as C
from tui.grid import InteractiveScreen, sparkline
from tui.workbench import Control, Row, affordable, compose, detail_room

# What `[` and `]` move by on each screen. Coarse enough to reach a useful
# figure in a few presses, and never so fine that stepping is a chore.
STEPS = {"roll": 50, "stores": 50, "corvee": 5, "dredge": 5,
         "land_due": 25, "expiate": 10}

TASKS = ("garrison", "watch", "harvest", "campaign")
MUSTER_VIEWS = (("formations", "Formations"), ("cohorts", "Cohorts"),
                ("detachments", "Detachments"), ("draft", "Draft order"))

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


RATION_STAKES = {
    "field_labour": "next harvest",
    "garrison": "harbour",
    "household": "granary",
    "cult": "temple",
    "bronze_working": "bronze",
    "weaving": "unrest",
    "populace": "unrest",
}


# --- the stores ---------------------------------------------------------------

STOREHOUSE_VIEWS = (
    ("stores", "STORES"),
    ("roll", "RATIONS"),
    ("land", "LAND"),
    ("reserves", "RESERVES"),
    ("dues", "DUES"),
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
        # Land on grain, not on whatever sorts first. Opening the Storehouse on
        # an empty bronze row taught the player nothing on the turn he most
        # wanted to know how the granary stood.
        stocked = [row.id for row in rows if dict(goods).get(row.id)]
        selected = ("grain" if "grain" in stocked else
                    stocked[0] if stocked else rows[0].id if rows else "")
    held = dict(goods).get(selected)
    ledger = LEDGER_OF.get(selected, "")
    inspected = set(b.get("inspected", []))

    detail: list[tuple[str, str]] = [(_spoken(selected).upper(), "gold"), ("", "ink")]
    if held is not None:
        detail.append((f"counted  {render.fmt_good(selected, held)}", "clay"))
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
                    ("+" if change >= 0 else "−")
                    + render.fmt_good(selected, abs(change)),
                    "barley" if change >= 0 else "blood"))
    if ledger:
        detail += [("", "ink"), (f"[i] count the {ledger} yourself", "sand")]
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
            ("in service  " + render.fmt_good(
                "bronze", metal.get("bronze_in_circulation", 0)), "clay"),
            ("melted      " + render.fmt_good(
                "bronze", metal.get("melt_ledger", 0)), "blood"),
        ]
        # Why the forge is idle, said plainly. Bronze is nine parts copper to
        # one of tin, so a full copper yard and an empty tin chest is a stopped
        # forge -- and the melt ledger going up while nothing is smelted is the
        # army being taken apart. The player should not have to infer that.
        stores = b.get("stores", {})
        if not stores.get("tin") and stores.get("copper"):
            detail += [
                ("no tin: the forge cannot make bronze,", "flame"),
                ("and what is in service is being melted", "flame"),
            ]

    controls = []
    if ledger:
        controls.append(affordable(
            Control("inspect_ledger", key_for("inspect_ledger")), hours))
    note = ("Tab view   ↑↓ choose   Enter record   [ ] amount" if room
            else "↑↓ choose   Enter record   [ ] amount")
    return compose(
        "THE STOREHOUSE" if room else "THE STORES",
        # One unit to a quantity means the counted column no longer has to
        # hold "1,204 parisu 18 qa", and the four columns it gives back go to
        # the detail pane, which was the one that could not fit its sentence.
        ("good", "counted", "recent"), (18, -18, 12),
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
    active = tuple(b.get("priority", ()))
    order = priority or active
    order += tuple(group["id"] for group in groups
                   if group["id"] not in order)
    by_id = {group["id"]: dict(group) for group in groups}
    if selected not in by_id:
        selected = order[0] if order else ""
    if amount > 0 and selected in by_id:
        # Preview the proposed ration in the queue before the order is given.
        by_id[selected]["allocated"] = amount
    grain = b.get("stores", {}).get("grain", 0)
    for rank, gid in enumerate(order, 1):
        group = by_id[gid]
        paid = min(grain, group["allocated"])
        grain -= paid
        owed = group["size"] * group["entitlement"]
        group["priority"] = rank
        group["next_paid"] = paid
        group["next_short"] = max(0, owed - paid)
        group["next_status"] = (
            "full" if paid >= owed else "none" if paid <= 0 else "short")
    groups = [by_id[gid] for gid in order]
    rows = []
    for group in groups:
        status = group["next_status"]
        rows.append(Row(group["id"], (
            (group["name"], "clay"),
            (f"{group['allocated']:,}", "dim"),
            (status, "blood" if status == "none" else
             "flame" if status == "short" else "barley"),
            (RATION_STAKES.get(group.get("function", ""), "unrest"), "dim"),
        ), mark=str(group["priority"])))
    group = next((g for g in groups if g["id"] == selected), None)

    detail: list[tuple[str, str]] = []
    if group is not None:
        weeks = group["arrears_weeks"]
        owed = group["size"] * group["entitlement"]
        repayment = min(group.get("arrears_qa", 0),
                        max(0, group["next_paid"] - owed))
        detail = [
            (group["name"], "gold"),
            (f"queue {group['priority']} · "
             f"{RATION_STAKES.get(group.get('function', ''), 'unrest')} at stake",
             "sand"),
            ((f"gets {owed:,} current + {repayment:,} arrears"
              if repayment else
              f"gets {group['next_paid']:,} of {owed:,} qa"), "clay"),
            (f"{group['next_status']} with the grain now",
             "blood" if group["next_status"] == "none" else
             "flame" if group["next_status"] == "short" else "barley"),
            (f"already unpaid {weeks} fortnight{'s' if weeks != 1 else ''}"
             if weeks else "no old arrears",
             "blood" if weeks >= 4 else ("flame" if weeks else "dim")),
        ]
        if amount > 0:
            detail += [
                (f"allocate {amount:,} qa", "flame"),
                ("DRAFT · [a] gives this ration", "flame"),
            ]
        else:
            detail.append(("[ ] draft a different ration", "dim"))
        detail.append(("QUEUE DRAFT · Enter gives the order" if priority
                       else "QUEUE IN FORCE",
                       "flame" if priority else "dim"))

    here = order.index(selected) if selected in order else -1
    controls = []
    if group is not None and amount > 0:
        controls.append(affordable(Control(
            "allocate", key_for("allocate"),
            label=f"allocate {amount:,} qa"), hours))
    controls += [
        Control("set_priority", "←", label="feed earlier",
                enabled=here > 0, why="already first"),
        Control("set_priority", "→", label="feed later",
                enabled=0 <= here < len(order) - 1, why="already last",
                command="ration:later"),
        affordable(Control("send_to_harvest", key_for("send_to_harvest"),
                           label=("recall from fields" if group is not None
                                  and group.get("at_fields")
                                  else "send to fields"),
                           enabled=group is not None), hours),
    ]
    if priority:
        controls.insert(-1, Control(
            "set_priority", "Enter", label="give ration order",
            command="ration:commit"))
    return compose(
        ("THE STOREHOUSE — LABOUR AND RATIONS" if room else
         "RATIONS — who eats first"),
        ("group", "ration qa", "next", "at stake"),
        (25, -10, -6, 12),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="nobody is on the roll.",
        note=(f"grain now {b.get('stores', {}).get('grain', 0):,} qa · "
              f"after this queue {grain:,} qa"),
        views=STOREHOUSE_VIEWS if room else (), view="roll", list_min=7)


# --- the land -----------------------------------------------------------------

def _year_band(surface, x: int, y: int, room: int, b: dict) -> None:
    """The grain year and this fortnight's hands, drawn across the top.

    Three rows and no prose: the wheel says how long each season is and where
    the king stands in it, the bar says how much of the labour the season has
    actually asked for. Both were already in Belief and neither was drawn.
    """
    calendar = b.get("calendar") or {}
    data = b.get("land") or {}
    if not calendar:
        return
    cells = render.year_wheel(calendar)
    surface.text(x, y, "THE GRAIN YEAR", C["gold"], C["ink"])
    for index, (glyph, colour, now) in enumerate(cells):
        if 16 + index >= room:
            break
        surface.put(x + 16 + index, y, glyph,
                    C["flame"] if now else C[colour], C["ink"])
    mark = f"fortnight {calendar.get('fortnight', 0)} of 24"
    if 16 + len(cells) + 2 + len(mark) <= room:
        surface.text(x + 16 + len(cells) + 2, y, mark, C["bone"], C["ink"])

    stage = calendar.get("stage", "low_water")
    surface.text(x, y + 1, render.year_says(calendar, room),
                 C[render.STAGE_COLOUR.get(stage, "clay")], C["ink"])
    # What the season means, and the river beside it -- the gauge rides here
    # as well as in the detail pane, which the smallest window truncates away.
    says = render.STAGE_SAYS.get(stage, "")
    river = data.get("gauge_says", "")
    surface.text(x, y + 2, f"{says} · {river}"[:room] if river else says[:room],
                 C["ash"], C["ink"])

    have = data.get("labour_days_this_turn", 0)
    asks = data.get("labour_days_needed", 0)
    idle = data.get("labour_days_idle", 0)
    bar = render.labour_bar(have, asks, data.get("labour_days_committed", 0))
    surface.text(x, y + 3, "THE HANDS", C["gold"], C["ink"])
    surface.text(x + 16, y + 3, bar, C["barley"], C["ink"])
    said = (f"{have:,} person-days · asks {asks:,} · {idle:,} idle")
    column = x + 16 + len(bar) + 2
    surface.text(column, y + 3, said[:max(0, room - 16 - len(bar) - 2)],
                 C["clay"] if idle else C["flame"], C["ink"])

    # What is queued behind the season. An ask of nothing means one thing with
    # the fields bare and another with a crop still standing. It
    # rides beside the bar where there is width for it and drops to its own
    # row where there is not, so a narrow window loses a line and not a fact.
    coming = (data.get("labour_days_by_season") or {}).get(
        calendar.get("next", ""), 0)
    if not coming:
        return
    queued = (f"then {calendar.get('next', '').replace('_', ' ')} asks "
              f"{coming:,} in {calendar.get('next_in', 0)}")
    beside = column - x + len(said) + 2
    if beside + len(queued) <= room:
        surface.text(x + beside, y + 3, queued, C["sand"], C["ink"])
    else:
        surface.text(x + 16, y + 4, queued[:max(0, room - 16)],
                     C["sand"], C["ink"])


def land(b: dict, selected: str = "", width: int = 80, height: int = 28,
         scroll: int = 0, days: int = 0, notice: str = "",
         hours: int = 0, group: str = "",
         room: bool = False) -> InteractiveScreen:
    data = b.get("land") or {}
    estates = list(data.get("estates", []))
    # The list is a chooser, not a record. Place and water are facts about the
    # estate the player has already picked, so they belong in the pane that
    # describes it -- and taking them out of the table gives the pane twenty
    # columns it did not have, which is the difference between a figure that
    # fits and one that ends in an ellipsis.
    rows = [Row(estate["id"], ((estate["name"], "sand"),
                               (f"{estate['hands']}", "clay")))
            for estate in estates]
    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    estate = next((e for e in estates if e["id"] == selected), None)

    # The pane is built to the width it will actually get. Two facts to a row
    # where there is room for two, one where there is not -- which halves the
    # height of the dossier without dropping a single figure from it.
    pane = detail_room((22, -6), width)
    half = pane // 2

    def paired(left: str, right: str, tone: str) -> list[tuple[str, str]]:
        if not right:
            return [(left[:pane], tone)]
        if len(left) + 2 + len(right) <= pane and len(left) < half:
            return [(f"{left:<{half}}{right}", tone)]
        return [(left[:pane], tone), (right[:pane], tone)]

    # Every figure in these two sections is qa, so the unit is named once in
    # the heading and never again. Repeating it on twelve rows is the same
    # noise the parisu remainder was, spelt differently.
    def qa(amount: int) -> str:
        return f"{amount:,}"

    rate = data.get("land_due_rate", 0)
    detail: list[tuple[str, str]] = [("THE CROP · qa", "gold")]
    detail += paired(f"seed {qa(data.get('seed_in_store', 0))} stored",
                     f"standing {qa(data.get('standing', 0))}", "sand")
    detail += paired(f"sown {qa(data.get('seed_in_ground', 0))}", "", "sand")
    detail += [(f"open ground takes "
                f"{qa(data.get('seed_recommended', 0))}"[:pane], "dim"),
               ("THE RIVER", "gold"),
               (f"gauge {data.get('gauge', 0)} · ordinary "
                f"{project.GAUGE_ORDINARY} · the scribe's copy"[:pane], "sky"),
               ("THE DUE", "gold")]
    detail += paired(f"ordered {rate}/1000",
                     f"took {qa(data.get('last_land_due', 0))} qa last year",
                     "gold")
    if estate is not None:
        canal = estate.get("canal_condition")
        water = (f"canal {canal}" if estate.get("irrigated")
                 and canal is not None else "rain-fed")
        open_ground = max(0, estate["extent"] - estate["under_crop"])
        detail.append(("THE ESTATE · qa", "gold"))
        detail += paired(f"at {_spoken(estate['place'])} · {water}",
                         f"{estate['hands']} hands", "dim")
        detail += paired(f"ground {qa(estate['extent'])}",
                         f"returns {estate['capacity']:,}/1000", "sand")
        detail += paired(f"sown {qa(estate['under_crop'])}",
                         f"open {qa(open_ground)}",
                         "verdigris" if estate["under_crop"] else "ash")
        detail += paired(f"holds {qa(estate['seed'])} seed", "", "dim")
        detail += paired(f"      {qa(estate['grain'])} grain", "", "dim")
    # The note row under the list already prints [ ] days and [< >] due, and
    # the footer prints the due itself. Only the chosen figure is state rather
    # than a repeated hint, so only the chosen figure is kept here.
    if days:
        detail += [("", "ink"), (f"{days} days in hand", "flame")]

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
            "levy_cohort", key_for("levy_cohort"),
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
        verb = "recall " if chosen_group.get("at_fields") else "send "
        controls.append(affordable(Control(
            "send_to_harvest", key_for("send_to_harvest"),
            label=verb + chosen_group["name"][:18]), hours))
    # The band takes four rows and is worth them only on a screen tall enough
    # to keep a list under it.
    band = 6 if (b.get("calendar") and height >= 24) else 0

    def draw(surface, x, y, room, _rows):
        _year_band(surface, x + 2, y, room - 4, b)

    return compose(
        "THE STOREHOUSE — ESTATES AND HARVEST" if room else "THE LAND",
        ("estate", "hands"),
        (22, -6),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="this house holds no estates.",
        note="Tab view   ↑↓ choose   [ ] days   [< >] due   [g] hands",
        views=STOREHOUSE_VIEWS if room else (), view="land",
        scene=draw, scene_rows=band)


def storehouse_account(b: dict, view: str, selected: str = "",
                       width: int = 80, height: int = 28, scroll: int = 0,
                       notice: str = "", hours: int = 0,
                       drafts: dict[str, int] | None = None,
                       **_ignored) -> InteractiveScreen:
    dated = b.get("date", "this fortnight")
    drafts = drafts or {}
    if view == "reserves":
        wanted = ("grain", "seed_grain", "bronze", "copper", "tin")
        rows = [Row(good, ((_spoken(good), "clay"),
                           (render.fmt_good(good, b.get("stores", {}).get(good, 0)), "gold"),
                           (dated, "dim"))) for good in wanted]
        headers, widths = ("reserve", "counted", "record"), (18, 24, 18)
    else:
        revenue, land_data = b.get("revenue", {}), b.get("land", {})
        land_rate = drafts.get("land", land_data.get("land_due_rate", 0))
        harbour_rate = drafts.get(
            "harbour", revenue.get("harbour_rate", 0))
        rows = [Row("land", (("land due", "clay"),
                              (f"{land_rate}/1000", "flame" if "land" in drafts else "gold"),
                              (f"last {land_data.get('last_land_due', 0):,} grain", "dim")),
                         mark="*" if "land" in drafts else ""),
                Row("harbour", (("harbour due", "clay"),
                                 (f"{harbour_rate}/1000", "flame" if "harbour" in drafts else "gold"),
                                 (f"last {revenue.get('last_harbour_due', 0):,} {revenue.get('harbour_good', 'oil')}", "dim")),
                    mark="*" if "harbour" in drafts else "")]
        headers, widths = ("account", "rate", "last taken"), (18, 14, 28)
    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    chosen = next((row for row in rows if row.id == selected), None)
    detail = [("DATED ACCOUNT", "gold"), (str(dated), "sky")]
    if chosen and view != "dues":
        detail += [("", "ink")] + list(chosen.cells)
    if view == "dues":
        revenue, land_data = b.get("revenue", {}), b.get("land", {})
        rate = (drafts.get(selected, land_data.get("land_due_rate", 0))
                if selected == "land" else
                drafts.get(selected, revenue.get("harbour_rate", 0)))
        detail = due_text.detail(
            b, selected, rate, draft=selected in drafts)
    controls = []
    if view == "dues" and selected in drafts:
        controls.append(Control(
            "set_land_due" if selected == "land" else "set_harbour_due",
            "Enter", label="give this due", command="due:commit"))
    return compose(
        f"THE STOREHOUSE — {view.upper()}", headers, widths, rows, selected,
        detail, controls, hours, width, height, scroll, notice,
        note=("Tab view   ↑↓ choose"
              + ("   [< >] draft" if view == "dues" else "")
              + ("   Enter give" if view == "dues" and selected in drafts
                 else "")),
        views=STOREHOUSE_VIEWS, view=view)


# --- the corvée: labour and arms ----------------------------------------------

def muster(b: dict, selected: str = "", width: int = 80, height: int = 27,
           scroll: int = 0, task: str = "garrison", place: str = "",
           amount: int = 0, notice: str = "",
           hours: int = 0, view: str = "formations") -> InteractiveScreen:
    troops = b.get("troops", {})
    formations = list(troops.get("formations", []))
    rows = [
        Row(f["id"], (
            (f["name"], "clay"),
            (str(f["strength"]), "dim"),
            (f["task"], "flame" if f["task"] == "campaign" else "clay"),
            (_spoken(f["place"]), "dim"),
        ))
        for f in formations
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

    if view in {"cohorts", "detachments"}:
        cohorts = [c for c in b.get("cohorts", ())
                   if (bool(c.get("parent") or c.get("task"))) == (view == "detachments")]
        rows = [Row(c["id"], ((c.get("name", c["id"]), "clay"),
                              (str(c.get("size", 0)), "dim"),
                              (_spoken(c.get("task", "at home")), "sand"),
                              (_spoken(c.get("place", "")), "dim")))
                for c in cohorts]
    elif view == "draft":
        rows = [Row("draft", (("levy heads from cohort", "gold"),
                              ("exact", "flame"), ("typed", "clay"),
                              ("[c]", "dim")))]

    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    formation = next((f for f in formations if f["id"] == selected), None)

    detail: list[tuple[str, str]] = []
    if formation is not None:
        detail = [
            (formation["name"][:30], "gold"),
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
    elif selected.startswith("summons:"):
        detail = [("A SUMMONS", "gold"), ("", "ink"),
                  ("choose a formation above, then send it", "dim")]

    controls = []
    if view in {"cohorts", "draft"}:
        controls.append(affordable(Control(
            "levy_cohort", key_for("levy_cohort"), label="write exact levy"), hours))
    elif view == "detachments":
        controls.append(Control("release_cohort", "r", label="release detachment"))
    else:
        controls += [
            affordable(Control("assign_troops", key_for("assign_troops"),
                               label=f"send to {task}"
                                     + (f" at {_spoken(place)}" if place else ""),
                               enabled=formation is not None and bool(place),
                               why="choose a formation and a place"), hours),
            Control("place_person", key_for("place_person"), label="give command",
                    enabled=formation is not None),
            Control("dismiss_person", key_for("dismiss_person"), label="remove command",
                    enabled=formation is not None),
        ]
    return compose(
        "THE MUSTER — LEVY AND SPEAR",
        ("levy / formation / summons", "heads", "duty", "place"),
        (24, -5, 10, 14),
        rows, selected, detail, controls, hours, width, height, scroll,
        notice, empty="no hands or formations are recorded.",
        note="Tab / Shift-Tab view   ↑↓ choose   Enter open",
        views=MUSTER_VIEWS, view=view)


# --- the oaths ----------------------------------------------------------------

def oaths(b: dict, selected: str = "", width: int = 78, height: int = 28,
          scroll: int = 0, amount: int = 0, notice: str = "",
          hours: int = 0, views=(), view: str = "") -> InteractiveScreen:
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
        note=("Tab / Shift-Tab view   ↑↓ choose" if views else
              "↑↓ choose   [ ] set an amount   [esc] close"),
        views=views, view=view)


def _clause(clause: dict) -> str:
    """A clause in the words the tablet uses. Kept identical to `document`."""
    from tui.document import _clause as spoken
    return spoken(clause)


def obligations(b: dict, selected: str = "", width: int = 78,
                height: int = 28, scroll: int = 0,
                notice: str = "", hours: int = 0) -> InteractiveScreen:
    rows = []
    records = {}
    for record in b.get("obligations", []):
        key = record["id"]
        records[key] = record
        due = record.get("due_turn", 0)
        rows.append(Row(key, ((record.get("kind", "obligation"), "bone"),
                              (record.get("status", ""), "clay"),
                              (f"due {due}" if due else "no date", "dim"))))
    for oath in b.get("oaths", []):
        for index, clause in enumerate(oath.get("clauses", [])):
            key = f"{oath['id']}:{index}"
            records[key] = (oath, clause)
            rows.append(Row(key, ((_clause(clause), "bone"),
                                  (_spoken(oath["id"]), "dim"),
                                  ("lapsed" if oath["lapsed"] else "binding",
                                   "wine" if oath["lapsed"] else "clay"))))
    if not any(row.id == selected for row in rows):
        selected = rows[0].id if rows else ""
    detail = []
    if selected in records:
        record = records[selected]
        if isinstance(record, tuple):
            oath, clause = record
            detail = [("OBLIGATION", "gold"), ("", "ink"),
                      (_clause(clause), "bone"),
                      ("tablet " + _spoken(oath["id"]), "dim"),
                      ("sworn turn " + str(oath["sworn_turn"]), "sky"),
                      ("parties " + ", ".join(render.actor_name(
                          party, b.get("house")) for party in oath["parties"]), "clay")]
        else:
            detail = [("CORRESPONDENCE OBLIGATION", "gold")]
            detail += [(f"{key.replace('_', ' ')}  {value}", "clay")
                       for key, value in record.items()
                       if key not in {"source", "certainty", "history"}]
    return compose(
        "THE SHRINE — OBLIGATIONS", ("clause", "tablet", "standing"),
        (31, 22, 10), rows, selected, detail, [], hours, width, height,
        scroll, notice, empty="no obligation is written on an oath tablet.",
        note="Tab / Shift-Tab view   ↑↓ choose",
        views=tuple((name, name.title()) for name in
                    ("rites", "offerings", "oaths", "obligations")),
        view="obligations")
