"""The city: the machine, drawn, and its condition as a history (spec 6.18, M12).

The screen exists because of a specific failure mode. A system with two hidden
multipliers, a head who flatters one of them, and decay measured in years can
become a thing the player cannot form a theory about — and a system you cannot
form a theory about reads as random, which is worse than reads as hard.

So condition is shown **as a shape, not a number**, twice over.

*As a skyline.* Every institution is a building standing on the same ground
line, and the building is eroded to match its condition (`art.weather`): dressed
stone at 800, hollowed at 400, a dithered footprint at 100. A player who has
never read a figure on this screen can still see which quarter of his city is
going. This is the fourth station to earn art (D34 named three), and it earns it
because here the picture *is* the information.

*As a line.* Twelve fortnights of sparkline per institution: a line that sags
tells the player something he can act on, where 604 tells him nothing at all.

Both are drawn from the **reported** condition — what the heads say, not what is
so. A harbourmaster in arrears writes that his quay is sound, and so the quay is
drawn sound, and it goes on being drawn sound until the player spends an hour
walking down to it. The lie is in the picture, which is where a lie belongs.

What is not here: any statement that a condition is bad, any threshold, any
colour that means danger on its own, and any suggestion about what to repair
first. The player reads the shapes and decides (D19).
"""
from __future__ import annotations

from tui import art, collection, document, style
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

# lit, mid, dark, edge. Mudbrick and plaster for most of it; the temple takes
# the gold leaf, the forge its fire, the water its own colour.
HUES = {
    "harbour": (C["sand"], C["clay"], C["faint"], C["sky"]),
    "canal": (C["sky"], C["lapis"], C["faint"], C["sky"]),
    "temple": (C["gold"], C["sand"], C["faint"], C["dim"]),
    "workshop": (C["flame"], C["sand"], C["faint"], C["dim"]),
    "walls": (C["clay"], C["dim"], C["faint"], C["faint"]),
    "granary": (C["barley"], C["sand"], C["faint"], C["dim"]),
    "garrison": (C["clay"], C["dim"], C["faint"], C["blood"]),
    "road": (C["sand"], C["ash"], C["faint"], C["dim"]),
}
DEFAULT_HUE = (C["sand"], C["clay"], C["faint"], C["dim"])

SLOT = art.BUILDING_WIDTH          # 13
PITCH = SLOT + 2
DRAWN = 6                          # how many will stand in the skyline
COMPACT_HEIGHT = 33                # full Works précis first fits with four rows


# What to write under a building. The kind, not the name: `walls` under the
# walls, where the name would put `Ugarit` under them and say nothing.
WORD = {
    "harbour": "harbour", "granary": "granary", "walls": "walls",
    "workshop": "forge", "temple": "temple", "archive": "tablets",
    "canal": "canal", "road": "road", "household": "palace",
    "garrison": "garrison",
}


def _spoken(word: str) -> str:
    """Content ids are written `master_smith`; nobody says it that way."""
    return word.replace("_", " ")


def _short(inst: dict, kinds: list[str]) -> str:
    """A label that fits under a building, and that distinguishes it.

    The kind reads best -- `walls` under the walls, where the name would put
    `Ugarit` under them and say nothing -- so it is used unless the city holds
    two of a kind, in which case the name has to do the telling apart.
    """
    word = WORD.get(inst["kind"], inst["kind"])
    if kinds.count(inst["kind"]) > 1:
        parts = [w for w in inst["name"].replace("-", " ").split()
                 if w.lower() not in ("the", "of", "at", "a")]
        word = parts[-1] if parts else word
    return word[:SLOT]


# Where the birds are. Fixed, like everything else here: a scatter that is the
# same scatter every fortnight reads as a place, where one that moved would read
# as an animation nobody asked for.
BIRDS = ((13, 4), (17, 3), (22, 4), (40, 3), (45, 4))


def sky(surface: Surface, b: dict, width: int, horizon: int) -> None:
    """The moon, some birds, and a haze on the hills behind the lower town.

    The moon is the one decoration on this screen that is also information: the
    month is lunar and the turn is half of one, so a waxing moon is the former
    half of Ayyaru and a waning moon the latter. Nothing says so. A player who
    never notices loses nothing; a player who does has a clock he never has to
    read.
    """
    latter = "latter" in b.get("date", "")
    moon = art.MOON_WANING if latter else art.MOON_WAXING
    art.draw(surface, width - 12, 2, moon,
             lit=C["bone"], mid=C["sand"], dark=C["faint"], edge=C["faint"])

    for bx, by in BIRDS:
        if bx < width - 14:
            surface.text(bx, by, art.BIRD, C["ash"], C["ink"])

    for row, cloud in enumerate(art.CLOUD):
        surface.text(width - 34, 2 + row, cloud, C["faint"], C["ink"])

    # The far shore the lower town stands on. Drawn under the band, so the town
    # has a ground of its own and does not float above the palace quarter.
    surface.text(3, horizon, "▁" * (width - 6), C["faint"], C["ink"])


def lower_town(surface: Surface, width: int, base: int) -> None:
    """The rest of Ugarit: everything that is not a great house, drawn faint.

    Two thirds of the screen used to be empty field. The palace quarter standing
    alone on bare ground read as six objects in a diagram; standing in front of
    a town it reads as the top of something. Nothing here is clickable and
    nothing here is simulated -- this is the only purely decorative element on
    the screen, and it is drawn faint enough to stay behind the six that are not.
    """
    band = art.town(width - 6, offset=0)
    # One colour, and the dimmest that still reads: a distant thing drawn with
    # the foreground's range of light and shade competes with the foreground.
    art.draw(surface, 3, base - len(band) + 1, band,
             lit=C["faint"], mid=C["faint"], dark=C["faint"], edge=C["faint"])


def scaffold(surface: Surface, left: int, top: int, ground: int) -> None:
    """Poles and rungs over a building the men are out on.

    Drawn in the two-column gap either side of the slot, so it never eats a
    column of the building itself, and rung by rung across it. A player who
    ordered a repair four fortnights ago and has forgotten should be able to
    see, without reading anything, that his men are still up there.
    """
    for y in range(top, ground):
        surface.put(left - 1, y, "│", C["ash"], C["ink"])
        surface.put(left + SLOT, y, "│", C["ash"], C["ink"])
    for y in range(top + 1, ground, 3):
        surface.text(left - 1, y, "┄" * (SLOT + 2), C["ash"], C["ink"])


def skyline(surface: Surface, x: int, ground: int, institutions: list[dict],
            width: int, under_work: frozenset = frozenset()) -> None:
    """The city, standing or not, on one line of ground.

    Bottom-aligned so a tall temple and a low channel share a horizon. Buildings
    are eroded from the reported condition, which is the only condition anyone
    in the palace has.
    """
    room = max(1, (width - x - 2) // PITCH)
    standing = institutions[:min(DRAWN, room)]
    kinds = [i["kind"] for i in standing]
    for index, inst in enumerate(standing):
        left = x + index * PITCH
        rows = art.weather(
            art.BUILDINGS.get(inst["kind"], art.HOVEL), inst["condition"])
        lit, mid, dark, edge = HUES.get(inst["kind"], DEFAULT_HUE)
        art.occlude(surface, left, ground - len(rows), rows)
        art.draw(surface, left, ground - len(rows), rows,
                 lit=lit, mid=mid, dark=dark, edge=edge)
        if inst["id"] in under_work:
            scaffold(surface, left, ground - len(rows), ground)

        # The ground each thing stands in. A quay in earth reads as a mistake.
        earth = art.GROUND.get(inst["kind"], "▒")
        surface.text(left, ground, earth * SLOT,
                     C["sky"] if earth == "≈" else C["ash"], C["ink"])

        # The number you press, and a word for what it is. A vacant post is
        # marked here as well as in the list, because the skyline is where the
        # eye goes first and a building nobody minds should say so.
        label = _short(inst, kinds)
        pad = left + (SLOT - len(label) - 4) // 2
        surface.text(pad, ground + 1, "[", C["dim"], C["ink"])
        surface.text(pad + 1, ground + 1, str(index + 1), C["flame"], C["ink"])
        surface.text(pad + 2, ground + 1, "]", C["dim"], C["ink"])
        surface.text(pad + 4, ground + 1, label,
                     C["bone"] if inst["inspected"] else C["clay"], C["ink"])
        surface.link(pad, ground + 1, 4 + len(label), 1, str(index + 1))
        if not inst["head"]:
            surface.text(pad + 4 + len(label) + 1, ground + 1, "×",
                         C["blood"], C["ink"])


def _divider(surface: Surface, x: int, y: int, width: int) -> None:
    """A rule with beads on it. A plain line is furniture; this is a border."""
    surface.text(x, y, "─" * width, C["faint"], C["ink"])
    for column in range(0, width, 11):
        surface.text(x + column, y, "◦", C["ash"], C["ink"])


def table_room(height: int) -> int:
    """How many institutions the table can hold at this height.

    Public because the controller resolves a typed `[3]` against the same page
    the screen drew. Two independent calculations of "which row is the third
    one" is exactly how a number key comes to open the wrong building.
    """
    # A reduced window is a four-house street: all four drawn buildings also
    # get a row and a number key. The full composition spends nine lines on the
    # Works précis, and can therefore grow its table one row at a time.
    if height < COMPACT_HEIGHT:
        return max(1, min(4, height - 20))
    return max(1, min(9, (height - 9) - 20))


def compose(b: dict, history: dict[str, list[int]] | None = None,
            width: int = 96, height: int = 36,
            notice: str = "", scroll: int = 0) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE CITY",
                note="[esc] close", drop=False)

    institutions = b.get("institutions") or []
    history = history or {}

    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])

    projects = b.get("projects") or []
    under_work = frozenset(p["institution"] for p in projects if p["institution"])

    compact = height < COMPACT_HEIGHT
    ground = 12 if compact else 14
    sky(surface, b, width, horizon=ground - 3 if compact else ground - 6)
    lower_town(surface, width, base=ground - 4 if compact else ground - 7)
    standing = collection.page(
        len(institutions), table_room(height), scroll)
    shown = standing.slice(institutions)
    if institutions:
        skyline(surface, 3, ground, shown, width, under_work)
    else:
        surface.text(3, ground - 1,
                     "this court holds nothing that could fall down.",
                     C["ash"], C["ink"])
        surface.text(3, ground, "▒" * (width - 6), C["ash"], C["ink"])

    table = ground + 3
    if compact:
        # At the window's reduced height the skyline is the primary report.
        # Keep its full-size, weathered buildings, then give each one a terse
        # ledger row. The Works précis is available through [n] and is omitted
        # here so it cannot cover the labels or make the numbered houses false.
        style.bar(surface, 2, table, width - 4, "",
                  fg=C["bone"], bg=C["faint"])
        surface.text(3, table, "what stands", C["bone"], C["faint"])
        surface.text(22, table, "it does", C["bone"], C["faint"])
        surface.text(37, table, "report", C["bone"], C["faint"])
        surface.text(53, table, "kept by", C["bone"], C["faint"])
        if standing.partial:
            label = "↑↓ " + standing.label()
            surface.text(max(3, width - 3 - len(label)), table - 1, label,
                         C["ash"], C["ink"])
    else:
        style.bar(surface, 2, table, width - 4,
                  "  what stands             it              he has been saying"
                  "   now   kept by"
                  + (f"   {standing.label()}" if standing.partial else ""),
                  fg=C["bone"], bg=C["faint"])

    works_top = height - 9
    y = table + (1 if compact else 2)
    for number, _absolute, inst in standing.rows(institutions):
        if not compact and y >= works_top - 1:
            break
        # Vacant posts are marked with a word, never with a colour alone.
        vacancy = "" if inst["head"] else "no one minds it"
        # The row carries the same number as the building above it. The
        # skyline only has room for six; the table can show more, and every
        # row it shows must be openable by the key printed on it.
        surface.text(1, y, str(number), C["flame"], C["ink"])
        if compact:
            surface.link(1, y, 20, 1, str(number))
            surface.text(3, y, inst["name"][:18], C["clay"], C["ink"])
            surface.text(22, y, DOES.get(inst["kind"], inst["kind"])[:13],
                         C["dim"], C["ink"])
        else:
            surface.link(1, y, 24, 1, str(number))
            surface.text(3, y, inst["name"][:22], C["clay"], C["ink"])
            surface.text(27, y, DOES.get(inst["kind"], inst["kind"])[:16],
                         C["dim"], C["ink"])

        series = history.get(inst["id"]) or inst.get("history") or [
            inst["condition"]]
        staff = vacancy or inst["group_name"] or "—"
        figure = str(inst["condition"])
        if compact:
            surface.text(37, y, sparkline(series, 8), C["sand"], C["ink"])
            surface.text(50 - len(figure), y, figure,
                         C["bone"] if inst["inspected"] else C["dim"], C["ink"])
            surface.text(51, y, "!" if inst["inspected"] else " ",
                         C["barley"], C["ink"])
            surface.text(53, y, staff[:max(0, width - 56)],
                         C["blood"] if vacancy else C["dim"], C["ink"])
        else:
            surface.text(45, y, sparkline(series, 12), C["sand"], C["ink"])
            surface.text(64 - len(figure), y, figure,
                         C["bone"] if inst["inspected"] else C["dim"], C["ink"])
            surface.text(65, y, "!" if inst["inspected"] else " ",
                         C["barley"], C["ink"])
            surface.text(67, y, staff[: width - 70],
                         C["blood"] if vacancy else C["dim"], C["ink"])
        y += 1

    # Work in hand, stated and not judged. Three lines at most: the rest is on
    # the WORKS screen, which is where anything can be done about it.
    if not compact:
        style.bar(surface, 2, works_top, width - 4,
                  "  the men are out on", fg=C["bone"], bg=C["faint"])
        if not projects:
            surface.text(3, works_top + 1,
                         "nothing. the city is as you found it.",
                         C["ash"], C["ink"])
        for index, project in enumerate(projects[:3]):
            row = works_top + 1 + index
            surface.text(3, row, project["what"][:26], C["clay"], C["ink"])
            surface.text(31, row, "making it whole" if project["repair"]
                         else "putting it up", C["dim"], C["ink"])
            share = project["days_done"] * 12 // max(
                1, project["days_needed"])
            style.meter(surface, 48, row, 12, share, fg=C["barley"])
            surface.text(
                62, row,
                f"{project['days_done']:,} of {project['days_needed']:,} days",
                C["dim"], C["ink"])

    foot = height - 4
    _divider(surface, 3, foot, width - 6)
    revenue = b.get("revenue", {})
    if notice:
        style.notice(surface, 3, foot + 1, width - 6, notice)
    else:
        surface.text(
            3, foot + 1,
            ("the figure is what he reports; ! is one you saw; "
             f"harbour due {revenue.get('harbour_rate', 0)}/1000, "
             f"last took {revenue.get('last_harbour_due', 0)} "
             f"{revenue.get('harbour_good', 'oil')}.")[: width - 6],
            C["ash"], C["ink"])
    if compact:
        if shown:
            footer = (f" [1-{len(shown)}] go and look — one hour"
                      "   [n] the works   [esc] close")
        else:
            footer = " no houses stand here   [n] the works   [esc] close"
    else:
        footer = (" [1-9] go and look for yourself — one hour"
                  "   [n] the works   [esc] close")
    style.bar(surface, 2, height - 2, width - 4, footer,
              fg=C["clay"], bg=C["lapis"])
    return surface.interactive()


def detail(b: dict, inst: dict, history: list[int] | None = None,
           width: int = 68, height: int = 22) -> Screen:
    """One institution, opened: the building itself, and what it can do."""
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    document._frame(surface, inst["name"].upper(), "[esc] close")
    surface.text(3, 2, DOES.get(inst["kind"], inst["kind"]), C["dim"], C["ink"])
    style.rule(surface, 3, 3, width - 6)

    rows = art.weather(
        art.BUILDINGS.get(inst["kind"], art.HOVEL), inst["condition"])
    lit, mid, dark, edge = HUES.get(inst["kind"], DEFAULT_HUE)
    left = width - SLOT - 5
    art.draw(surface, left, 5, rows, lit=lit, mid=mid, dark=dark, edge=edge)
    surface.text(left, 5 + len(rows), art.GROUND.get(inst["kind"], "▒") * SLOT,
                 C["sky"] if inst["kind"] in art.GROUND else C["ash"], C["ink"])

    facts = [
        ("condition", f"{inst['condition']}"
                      + ("" if inst["inspected"] else "  (he says)")),
        ("whole, it could", f"{inst['capacity']}"),
        ("as it stands", f"{inst['effective']}"),
        ("kept by", inst["group_name"] or "nobody on the roll"),
        ("in the charge of",
         _spoken(inst["head"]) if inst["head"] else "NOBODY — the post is open"),
        ("at", _spoken(inst["place"])),
    ]
    y = 5
    column = left - 1
    for label, value in facts:
        surface.text(4, y, label, C["dim"], C["ink"])
        surface.text(21, y, value[: max(0, column - 21)], C["clay"], C["ink"])
        y += 1
    if inst["upkeep"]:
        y += 1
        surface.text(4, y, "it wants, a fortnight", C["dim"], C["ink"])
        for good, qty in sorted(inst["upkeep"].items()):
            surface.text(26, y, f"{qty} {good}", C["clay"], C["ink"])
            y += 1
    if history:
        surface.text(4, height - 6, "what he has been saying",
                     C["dim"], C["ink"])
        surface.text(4, height - 5, sparkline(history, width - 10),
                     C["sand"], C["ink"])

    # The one verb on this screen. What it costs is stated in days, because
    # days are what it costs -- the grain is a consequence and the player can
    # work it out on the WORKS screen if he cares to.
    project = next((p for p in (b.get("projects") or [])
                    if p["institution"] == inst["id"]), None)
    if project is not None:
        surface.text(4, height - 3,
                     f"the men are out on it: {project['days_done']:,} of "
                     f"{project['days_needed']:,} days", C["barley"], C["ink"])
    elif inst["condition"] < 1000:
        want = (1000 - inst["condition"]) * b.get("repair_days_per_point", 3)
        style.bar(surface, 2, height - 2, width - 4,
                  f" [r] set the men to it — about {want:,} days of corvée",
                  fg=C["clay"], bg=C["lapis"])
    return surface.interactive()
