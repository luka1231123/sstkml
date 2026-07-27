"""Drawn things: portraits, settings, friezes (M11, D34).

Art earns its place in exactly three windows — the hall, the altar, the tablet
house — plus a face beside anyone who speaks. Everywhere else the numbers are
the point and a picture would make them feel authored (D34).

**How the shading works.** Nothing here carries a colour. Each drawing is plain
rows of glyphs, and `draw()` assigns colour by *weight*: `█▓` are the lit face
of a thing, `▒░` its shadow, box rule and punctuation its edges. So one drawing
renders warm at an altar and cold on a ledger, and every drawing survives
`plain_text` as a picture rather than as a smear.

Every glyph is one column wide — quadrant and shade blocks, box drawing, plain
ASCII. `tui/grid.py` raises on anything else, and a test walks every drawing in
this file to make sure none of them ever desynchronises the grid.
"""
from __future__ import annotations

from tui.grid import INDEX, Surface

C = INDEX

# Glyph -> weight. `draw` colours by this, so a drawing has depth without the
# artist having to think about the palette.
LIT = set("█▓▛▜▙▟◤◥◣◢")
MID = set("▒▌▐▄▀■●◙")
DARK = set("░·:.'`,\"^~-=_+*/\\|(){}[]<>○◦□◘")


def draw(surface: Surface, x: int, y: int, rows,
         lit: int = C["bone"], mid: int = C["clay"], dark: int = C["faint"],
         edge: int | None = None, bg: int = C["ink"]) -> None:
    """Blit a drawing, colouring each glyph by its weight rather than by hand."""
    edge = dark if edge is None else edge
    for row_index, row in enumerate(rows):
        for column, glyph in enumerate(row):
            if glyph == " ":
                continue
            if glyph in LIT:
                fg = lit
            elif glyph in MID:
                fg = mid
            elif glyph in DARK:
                fg = dark
            else:
                fg = edge
            surface.put(x + column, y + row_index, glyph, fg, bg)


def size(rows) -> tuple[int, int]:
    return (max((len(row) for row in rows), default=0), len(rows))


# --- faces --------------------------------------------------------------------
#
# Twelve, and no more. A recurring face is a person; a face per correspondent is
# wallpaper. Each is 13 x 9, so any of them can go in any slot without the text
# beside it moving.

KING = (
    "   ▄█████▄   ",
    "  ▟███████▙  ",
    "  ██▀▀█▀▀██  ",
    "  █░ ▀▀▀ ░█  ",
    "  ▓▄ ▄▀▄ ▄▓  ",
    "  ▐█▄▄▄▄▄█▌  ",
    " ▗▓▒▓███▓▒▓▖ ",
    "▟███████████▙",
    "█████████████",
)

VICEROY = (
    "  ▄▄▄▄▄▄▄▄▄  ",
    " ▟█▀▀███▀▀█▙ ",
    " ██  ███  ██ ",
    " █▒ ▀▀▀▀▀ ▒█ ",
    " █▄ ▄▄▄▄▄ ▄█ ",
    " ▐█▓░███░▓█▌ ",
    "  ▀█▓▒▓▒▓█▀  ",
    " ▗███████▛▚▖ ",
    "▟█████████▙▚▙",
)

MERCHANT = (
    "    ▄▄▄▄▄    ",
    "   ▟█████▙   ",
    "  ▐██▀█▀██▌  ",
    "  ▐█ ▀▀▀ █▌  ",
    "   █▄▄▄▄▄█   ",
    "   ▒▓███▓▒   ",
    "  ▄█▀▒▓▒▀█▄  ",
    " ▟██▓░█░▓██▙ ",
    "██▀▀▀▀▀▀▀▀▀██",
)

OVERSEER = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    "  █▀▀███▀▀█  ",
    "  █  ▀▀▀  █  ",
    "  ▓▄▄▄▄▄▄▄▓  ",
    "   ▀█▓▒▓█▀   ",
    "  ░▒▓███▓▒░  ",
    " ▗█████████▖ ",
    "▟███▀▀▀▀▀███▙",
)

PRIEST = (
    "      ▲      ",
    "    ▗███▖    ",
    "   ▟█████▙   ",
    "  ▐███▀███▌  ",
    "  ▐█ ▀▀▀ █▌  ",
    "   █▄▄▄▄▄█   ",
    "  ░▓▓███▓▓░  ",
    " ▟█▓▒░█░▒▓█▙ ",
    " ███████████ ",
)

SCRIBE = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟█▀▀▀▀▀█▙  ",
    "  █▌ ▀ ▀ ▐█  ",
    "  █▌  ▄  ▐█  ",
    "  ▜█▄▄▄▄▄█▛  ",
    "   ▒▓███▓▒   ",
    " ▗▓█████████▖",
    "▐▓█▀▀▀▀▀▀▀██▌",
    "▐░░ ══════ ░▌",
)

PHYSICIAN = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟▓▓▓▓▓▓▓▙  ",
    "  █▀▀███▀▀█  ",
    "  █░ ▀▀▀ ░█  ",
    "  ▓▄▄▄▄▄▄▄▓  ",
    "  ░▒▓███▓▒░  ",
    " ▗███▓░▓███▖ ",
    "▟██▀░░░░░▀██▙",
    "██  ░░░░░  ██",
)

HERALD = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    "  ██▀███▀██  ",
    "  █▌ ▀▀▀ ▐█  ",
    "  ▐█▄▄▄▄▄█▌  ",
    "  ░▓█████▓░  ",
    "▄▄▟█▓▒░▒▓█▙▄▄",
    " ███████████ ",
    "▀▀█████████▀▀",
)

QUEEN = (
    "  ▗▄▄▄▄▄▄▄▖  ",
    " ▟█████████▙ ",
    " ██▀▀▀█▀▀▀██ ",
    " █▌  ▀▀▀  ▐█ ",
    " ▐█▄▄▄▄▄▄▄█▌ ",
    " ░▒▓█████▓▒░ ",
    "▗▓▒░▓███▓░▒▓▖",
    "▐███████████▌",
    "▐█▀▀▀▀▀▀▀▀▀█▌",
)

ENVOY = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟█▀███▀█▙  ",
    "  ██ ███ ██  ",
    "  █▒ ▀▀▀ ▒█  ",
    "  ▓█▄▄▄▄▄█▓  ",
    "  ░▒▓███▓▒░  ",
    " ▟███▓█▓███▙ ",
    "██▀▀▀███▀▀▀██",
    "     ███     ",
)

SOLDIER = (
    "  ▄▄█████▄▄  ",
    " ▟█████████▙ ",
    " ██▀▀▀█▀▀▀██ ",
    " █▌ ▀  ▀  ▐█ ",
    " █▄  ▄▄▄  ▄█ ",
    " ▜██▓▒░▒▓██▛ ",
    "▗███████████▖",
    "▐█▓▒░░█░░▒▓█▌",
    "▐█   ▐█▌   █▌",
)

STRANGER = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟▒▒▒▒▒▒▒▙  ",
    "  ▒░░░░░░░▒  ",
    "  ▒ ░░░░░ ▒  ",
    "  ░▒▒▒▒▒▒▒░  ",
    "   ░▒▒▒▒▒░   ",
    "  ░▒▒▒▒▒▒▒░  ",
    " ▗▒▒▒▒▒▒▒▒▒▖ ",
    "▐▒▒▒▒▒▒▒▒▒▒▒▌",
)

FACES = {
    "king": KING, "viceroy": VICEROY, "merchant": MERCHANT,
    "overseer": OVERSEER, "priest": PRIEST, "scribe": SCRIBE,
    "physician": PHYSICIAN, "herald": HERALD, "queen": QUEEN,
    "envoy": ENVOY, "soldier": SOLDIER, "stranger": STRANGER,
}

# What a name or a persona word means, in the order it is tried. First hit wins,
# so the specific terms come before the general ones.
ROLE_WORDS = (
    ("viceroy", "viceroy"), ("great king", "king"), ("king", "king"),
    ("queen", "queen"), ("governor", "viceroy"), ("overseer", "overseer"),
    ("steward", "overseer"), ("merchant", "merchant"), ("scribe", "scribe"),
    ("priest", "priest"), ("diviner", "priest"), ("physician", "physician"),
    ("herald", "herald"), ("envoy", "envoy"), ("commander", "soldier"),
    ("captain", "soldier"),
)


def face_for(name: str, persona: str = "") -> tuple[str, ...]:
    """The face for a person, by what he is rather than by who he is.

    Deterministic and role-based on purpose: a dozen faces reused for the
    stations of a small world reads as a court, where a face generated per
    correspondent reads as a crowd of strangers (D34).
    """
    text = f"{name} {persona}".casefold()
    for word, role in ROLE_WORDS:
        if word in text:
            return FACES[role]
    return STRANGER


# --- settings -----------------------------------------------------------------
#
# The three places D34 says earn a drawn one. Each is a room you are standing
# in, which is why the window is dressed at all.

ALTAR = (
    "                ▟▙                ",
    "               ▟██▙               ",
    "          ░    ████    ░          ",
    "         ░▒   ▐████▌   ▒░         ",
    "        ░▒▓   ▐████▌   ▓▒░        ",
    "     ▄▄▄▄▄▄▄▄▄▄▄██▄▄▄▄▄▄▄▄▄▄▄     ",
    "   ▟███████████████████████████▙  ",
    "  ▐█▒░▓▒░▓▒░▓▒░▓▒░▓▒░▓▒░▓▒░▓▒░█▌  ",
    "  ▐█████████████████████████████▌ ",
    " ▟███▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀███▙",
    "▐███░ ══════════════════════ ░███▌",
    "▐███▓░░░░░░░░░░░░░░░░░░░░░░░░▓███▌",
    "▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀",
)

SHELVES = (
    "╔══════════════════════════════╗",
    "║ ▐█▌▐█▌▐█▌ ▐█▌▐█▌ ▐█▌▐█▌▐█▌▐█▌║",
    "║ ▐▓▌▐▓▌▐▓▌ ▐▓▌▐▓▌ ▐▓▌▐▓▌▐▓▌▐▓▌║",
    "╠══════════════════════════════╣",
    "║ ▐█▌▐█▌ ▐█▌▐█▌▐█▌ ▐█▌ ▐█▌▐█▌  ║",
    "║ ▐▒▌▐▒▌ ▐▒▌▐▒▌▐▒▌ ▐▒▌ ▐▒▌▐▒▌  ║",
    "╠══════════════════════════════╣",
    "║ ▐█▌ ▐█▌▐█▌▐█▌ ▐█▌▐█▌▐█▌ ▐█▌  ║",
    "║ ▐░▌ ▐░▌▐░▌▐░▌ ▐░▌▐░▌▐░▌ ▐░▌  ║",
    "╚══════════════════════════════╝",
)

TABLET = (
    "▗▄▄▄▄▄▄▄▄▄▄▄▄▄▖",
    "▐░═══════════░▌",
    "▐░ ▀▀ ▀ ▀▀▀▀ ░▌",
    "▐░ ▀▀▀▀ ▀▀▀  ░▌",
    "▐░  ▀ ▀▀▀▀▀▀ ░▌",
    "▐░═══════════░▌",
    "▝▀▀▀▀▀▀▀▀▀▀▀▀▀▘",
)

# A cylinder-seal frieze. Rolls forever; slice it to whatever width is going.
FRIEZE = "▚▞▚▞◢◣▚▞▚▞◤◥▚▞▚▞◢◣▚▞▚▞◤◥"


def frieze(width: int) -> str:
    return (FRIEZE * (width // len(FRIEZE) + 1))[:width]


# The lamp that is the fortnight, drawn once at the altar and the hall's hour.
LAMP = (
    "  ▗▄▄▖  ",
    " ▟████▙ ",
    "▐██▀▀██▌",
    " ▀▄▄▄▄▀ ",
)


# --- the city -----------------------------------------------------------------
#
# One drawing per kind of institution, all 13 columns wide and bottom-aligned so
# they can stand in a row on the same ground line. This is the fourth station to
# earn art (D34 named three): the CITY screen is a list of buildings, and a list
# of buildings drawn as buildings is the one place where a picture carries the
# information rather than decorating it.
#
# Nothing here is coloured. `weather()` below erodes the glyphs, `draw()` shades
# what is left, and the whole silhouette therefore sags as the fabric goes.

QUAY = (
    "    ▐▌       ",
    "    ▐█▙      ",
    "    ▐███▙    ",
    "   ▄▟█████▙  ",
    " ▄█████████▙ ",
    "▟█▓▒░▒░▒░▒▓█▙",
    "█████████████",
)

SILOS = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▐█▀▀███▀▀█▌ ",
    " ▐█ ░███░ █▌ ",
    " ▐█▄▄███▄▄█▌ ",
    "▐███████████▌",
    "█████████████",
)

RAMPART = (
    "█▀█▀█▀█▀█▀█▀█",
    "█████████████",
    "███▄▄▄▄▄▄▄███",
    "███▛▀▀▀▀▀▜███",
    "███▌░░░░░▐███",
    "███▌░███░▐███",
    "█████████████",
)

FORGE = (
    "  ░   ░      ",
    "  ▒   ▒  ░   ",
    "  ▐▌ ▐▌  ▒   ",
    "  ▐███████▙  ",
    " ▟█████████▙ ",
    "▐█▓▒░███░▒▓█▌",
    "█████████████",
)

ZIGGURAT = (
    "      ▲      ",
    "     ▟█▙     ",
    "    ▟███▙    ",
    "   ▐█████▌   ",
    "  ▄▄▄███▄▄▄  ",
    " ▟█████████▙ ",
    "▟███████████▙",
    "█▓▒░▓▒█▒▓░▒▓█",
    "█████████████",
)

TABLET_HOUSE = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▐█▌▐█▌▐█▌█▌ ",
    " ▐█████████▌ ",
    " ▐█░█░█░█░█▌ ",
    "▐███████████▌",
    "█████████████",
)

CHANNEL = (
    "  ░░░░░░░░░  ",
    "▄▄▄▄▄▄▄▄▄▄▄▄▄",
    "█≈≈≈≈≈≈≈≈≈≈≈█",
    "█≈≈≈≈≈≈≈≈≈≈≈█",
    "█████████████",
)

CAUSEWAY = (
    "      ░      ",
    "     ░░░     ",
    "    ▒▒▒▒▒    ",
    "   ▒▒▒▒▒▒▒   ",
    "  ▓▓▓▓▓▓▓▓▓  ",
    " ▓▓▓▓▓▓▓▓▓▓▓ ",
    "█████████████",
)

PALACE = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▟█████████▙ ",
    "▐███▀▀▀▀▀███▌",
    "▐██▌░░░░░▐██▌",
    "▐██▌░███░▐██▌",
    "█████████████",
)

BARRACKS = (
    " ▲ ▲ ▲   ▲ ▲ ",
    " █ █ █   █ █ ",
    "▄▄▄▄▄▄▄▄▄▄▄▄▄",
    "█▛▀▀▀▀▀▀▀▀▀▜█",
    "█▌░▐█▌░▐█▌░▐█",
    "█▙▄▄▄▄▄▄▄▄▄▄█",
    "█████████████",
)

HOVEL = (      # anything the content authors that this module has never heard of
    "             ",
    "             ",
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▐█▌░░░░░▐█▌ ",
    " ▐█████████▌ ",
    "█████████████",
)

BUILDINGS = {
    "harbour": QUAY, "granary": SILOS, "walls": RAMPART, "workshop": FORGE,
    "temple": ZIGGURAT, "archive": TABLET_HOUSE, "canal": CHANNEL,
    "road": CAUSEWAY, "household": PALACE, "garrison": BARRACKS,
}

BUILDING_WIDTH = 13

# What the ground under each kind is made of. A quay standing in earth reads as
# a mistake, and it is cheap to be right.
GROUND = {"harbour": "≈", "canal": "≈"}

# The fabric going, in four steps. `█` is dressed stone and `░` is what is left
# when nobody has minded it for a decade.
_FALL = (
    {},
    {"█": "▓", "▓": "▒", "▒": "░"},
    {"█": "▒", "▓": "░", "▒": "░", "▟": "▒", "▙": "▒", "▛": "░", "▜": "░"},
    {"█": "░", "▓": "░", "▒": "░", "▟": "░", "▙": "░", "▛": " ", "▜": " ",
     "▲": "·", "▐": "░", "▌": "░", "▄": "░", "▀": "░"},
)


def weather(rows, condition: int):
    """Erode a building to match its condition, deterministically.

    The holes are punched on a fixed lattice of (x, y) rather than at random --
    this project has no random -- so the same building at the same condition is
    always the same ruin, and a player who repairs one watches it come back the
    way it went.
    """
    step = 0 if condition >= 750 else 1 if condition >= 500 else (
        2 if condition >= 250 else 3)
    if step == 0:
        return tuple(rows)
    fall = _FALL[step]
    if step == 3:
        rows = ("" .ljust(len(rows[0])),) + tuple(rows[1:])   # the roof is gone
    out = []
    for y, row in enumerate(rows):
        line = []
        for x, glyph in enumerate(row):
            glyph = fall.get(glyph, glyph)
            if step >= 2 and glyph != " " and (x * 3 + y * 5) % (9 - step) == 0:
                glyph = " "
            line.append(glyph)
        out.append("".join(line))
    return tuple(out)
