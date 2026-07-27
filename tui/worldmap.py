"""The known world: a diagram, not a map (M11, D34).

The distinction matters. A map would imply the king has surveyed the coast; he
has not, and nobody in 1200 BC had. What he has is a list of places he can send
a courier to, roughly how far each is, whether the road runs by land or by sea,
and how the man at the other end feels about him. That is a *graph*, and drawing
it as a graph is honest where drawing it as a coastline would not be.

So the positions here are authored — they are the shape of the world as a scribe
at Ugarit would sketch it, north at the top, the sea to the west — and they are
constant. Nothing on this screen is measured.

What it is *for*: when the sea shuts, half the edges go grey and the player can
see, in one glance, that the men he needs are now eight fortnights away by road.
That is a fact he can otherwise only assemble by remembering.
"""
from __future__ import annotations

from tui import art, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

# Where a place sits on the sketch, and what kind of place it is. Authored, not
# derived: the world is small enough to draw by hand and the drawing should
# never move under the player.
PLACES: dict[str, tuple[int, int, str]] = {
    "hattusa":    (30, 2, "great"),
    "mira":       (10, 4, "far"),
    "carchemish": (52, 3, "great"),
    "assur":      (66, 6, "far"),
    "emar":       (54, 8, "town"),
    "ura":        (24, 6, "town"),
    "babylon":    (66, 12, "far"),
    "alashiya":   (12, 11, "town"),
    "seat":       (36, 11, "seat"),
    "ma_hadu":    (30, 13, "own"),
    "gibala":     (40, 14, "own"),
    "amurru":     (38, 16, "town"),
    "byblos":     (32, 18, "town"),
    "sidon":      (28, 19, "town"),
    "tyre":       (24, 20, "town"),
    "egypt":      (10, 20, "far"),
}

# Which places the roads and the sea-lanes actually join. `sea` links vanish
# from use when the sea shuts (spec 6.4), which is the whole point of drawing
# them differently.
LINKS: tuple[tuple[str, str, str], ...] = (
    ("seat", "ma_hadu", "land"), ("seat", "gibala", "land"),
    ("seat", "carchemish", "land"), ("seat", "emar", "land"),
    ("seat", "amurru", "land"), ("carchemish", "hattusa", "land"),
    ("carchemish", "assur", "land"), ("emar", "babylon", "land"),
    ("hattusa", "mira", "land"), ("hattusa", "ura", "land"),
    ("amurru", "byblos", "land"), ("byblos", "sidon", "land"),
    ("sidon", "tyre", "land"),
    ("ma_hadu", "alashiya", "sea"), ("ma_hadu", "ura", "sea"),
    ("alashiya", "egypt", "sea"), ("tyre", "egypt", "sea"),
    ("ma_hadu", "byblos", "sea"),
)

MARKS = {"seat": "▣", "own": "◆", "great": "◈", "town": "◇", "far": "○"}

ESTEEM_TONE = {"warm": "barley", "formal": "clay", "displeased": "blood",
               "cold": "blood", "hostile": "blood"}


def _line(surface: Surface, x1: int, y1: int, x2: int, y2: int,
          glyph: str, fg: int) -> None:
    """A straight run between two nodes, drawn cell by cell.

    Integer Bresenham, and it stops short of both ends so a road never writes
    over the place it leads to.
    """
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    step_x = 1 if x1 < x2 else -1
    step_y = 1 if y1 < y2 else -1
    error = dx - dy
    x, y = x1, y1
    cells = []
    while (x, y) != (x2, y2):
        cells.append((x, y))
        doubled = error * 2
        if doubled > -dy:
            error -= dy
            x += step_x
        if doubled < dx:
            error += dx
            y += step_y
    for cell_x, cell_y in cells[2:-1]:
        if surface.at(cell_x, cell_y)[0] == " ":
            surface.put(cell_x, cell_y, glyph, fg, C["ink"])


def compose(b: dict, width: int = 86, height: int = 30) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="THE KNOWN WORLD",
                note="[esc] close", drop=False)

    open_sea = b["sea_open"]
    by_place: dict[str, list[dict]] = {}
    for relation in b["relations"]:
        by_place.setdefault(relation["place"], []).append(relation)

    top = 1
    # The roads first, so every node is drawn on top of its own connections.
    for first, second, kind in LINKS:
        if first not in PLACES or second not in PLACES:
            continue
        x1, y1, _ = PLACES[first]
        x2, y2, _ = PLACES[second]
        if kind == "sea":
            glyph, fg = ("~", C["lapis"]) if open_sea else ("~", C["faint"])
        else:
            glyph, fg = "·", C["faint"]
        _line(surface, x1, y1 + top, x2, y2 + top, glyph, fg)

    for place, (x, y, kind) in PLACES.items():
        people = by_place.get(place, [])
        esteem = people[0]["esteem"] if people else ""
        unanswered = sum(person["unanswered"] for person in people)
        tone = C[ESTEEM_TONE.get(esteem, "dim")] if people else C["ash"]
        if kind == "seat":
            tone = C["flame"]
        surface.put(x, y + top, MARKS[kind], tone, C["ink"])
        label = place.replace("_", " ")
        surface.text(x + 2, y + top, label[: width - x - 6], tone, C["ink"])
        # A number of letters they have sent and you have not answered. It is a
        # count, not a reproach: D19 forbids the reproach.
        if unanswered:
            surface.text(x + 3 + len(label), y + top, f"({unanswered})",
                         C["flame"] if unanswered >= 3 else C["dim"], C["ink"])

    # The legend, and the one line on the screen that changes with the season.
    foot = height - 4
    surface.text(3, foot, "─" * (width - 6), C["faint"], C["ink"])
    surface.text(3, foot + 1,
                 "▣ seat   ◆ yours   ◈ a great king   ◇ a town   ○ far off",
                 C["dim"], C["ink"])
    surface.text(width - 3 - 22, foot + 1, "(n) letters unanswered",
                 C["dim"], C["ink"])
    sea = ("~ the sea lanes are open" if open_sea
           else "~ the sea is shut; these lanes carry nothing")
    surface.text(3, foot + 2, sea, C["lapis"] if open_sea else C["ash"],
                 C["ink"])
    return surface.freeze()


def compose_with_frieze(b: dict, width: int = 86, height: int = 30) -> Screen:
    """The map under a seal frieze. Used when the window is opened tall."""
    screen = compose(b, width, height)
    surface = Surface(width, height)
    for y, row in enumerate(screen):
        for x, (glyph, fg, bg) in enumerate(row):
            surface.put(x, y, glyph, fg, bg)
    surface.text(2, 1, art.frieze(width - 4), C["faint"], C["ink"])
    return surface.freeze()
