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


# One letter per palette entry, for painting a drawing cell by cell. Sixteen
# colours, sixteen letters, and the letters are arbitrary on purpose: they name
# the palette entry, never the meaning, because meaning is never carried by a
# colour in this game (spec 9.6).
PAINT = {
    "i": "ink", "c": "clay", "d": "dim", "f": "faint", "l": "flame",
    "r": "blood", "b": "barley", "g": "gold", "z": "lapis", "e": "verdigris",
    "m": "bone", "h": "shadow", "a": "ash", "w": "wine", "n": "sand",
    "k": "sky",
}


def paint(surface: Surface, x: int, y: int, rows, mask,
          default: int = C["clay"], bg: int = C["ink"]) -> None:
    """Blit a drawing, colouring each cell from a mask laid over it.

    `draw` colours by the weight of the glyph, which is right for a silhouette
    and wrong for a painted thing: a gold crown, a bronze lamp and a wine-dyed
    canopy are all the same block. The mask is a second picture of the same
    shape, one letter per cell naming a palette entry, so the drawing and its
    colouring are written and edited side by side -- and a row that drifts out
    of step with the other is visible on the page rather than at run time.
    """
    for row_index, row in enumerate(rows):
        tones = mask[row_index] if row_index < len(mask) else ""
        for column, glyph in enumerate(row):
            if glyph == " ":
                continue
            letter = tones[column] if column < len(tones) else " "
            fg = C.get(PAINT.get(letter, ""), default)
            surface.put(x + column, y + row_index, glyph, fg, bg)


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

# --- the throne room ----------------------------------------------------------
#
# The one room the player is actually *in*. Everywhere else he is reading; here
# he is sitting, and people are standing in front of him waiting to be dealt
# with. So the scene is not decoration: the figures on the floor are the queue,
# one for each matter, and the one under the marker is the one the list has
# selected. Clicking a man selects his business.
#
# Drawn in the same block idiom as the faces above. The earlier litigants were
# plain ASCII on the theory that a silhouette should survive the strictest
# degrade path, but `pure_ascii` folds the blocks for exactly that reason, so
# the theory cost the room its whole visual register for nothing.

# The throne under its canopy, on a stepped dais, between the pillars of the
# hall. Painted rather than shaded: the mask beneath each drawing gives it a
# gilt canopy crown, a wine-dyed cloth, a gold diadem and a lit face, which is
# what makes it a room the king is sitting in rather than a diagram of a chair.
THRONE = (
    "◢▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄◣",
    "█▚▞▚▞▚▞▚▞▚▞▚▞▚▞▚▞▚▞▚▞▚▞▚█",
    "▐░▒▓▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▓▒░▌",
    "╔═╩═╩═╩═╩═╩═╩═╩═╩═╩═╩═╩═╗",
    "║▓█▌     ,▄███▄,     ▐█▓║",
    "║▓█▌    ▟█▄▀▀▀▄█▙    ▐█▓║",
    "║▓█▌    ▐█ ◘ ◘ █▌    ▐█▓║",
    "║▓█▌    ▐█▓▒▄▒▓█▌    ▐█▓║",
    "║▓█▌   ▟▓▒█████▒▓▙   ▐█▓║",
    "║▓█▙▄▄▟▓▒███████▒▓▙▄▄▟█▓║",
    "╚═╩═╩═╩═╩═╩═╩═╩═╩═╩═╩═╩═╝",
)

THRONE_PAINT = (
    "ggggggggggggggggggggggggg",
    "gwwwwwwwwwwwwwwwwwwwwwwwg",
    "gwwwwwwwwwwwwwwwwwwwwwwwg",
    "nnnnnnnnnnnnnnnnnnnnnnnnn",
    "nnnn     ggggggg     nnnn",
    "nnnn    ggggggggg    nnnn",
    "nnnn    mmmmmmmmm    nnnn",
    "nnnn    mmwwwwwmm    nnnn",
    "nnnn   wwwwwwwwwww   nnnn",
    "nnnnnnwwwwwwwwwwwwwwwnnnn",
    "nnnnnnnnnnnnnnnnnnnnnnnnn",
)

# One figure per waiting matter, nine columns wide so a rank of them fits.
# Three kinds, because what a man is doing in the room is worth a glance: a
# petitioner stands with his arms out, a man of the house wears the long robe
# of the palace, an envoy carries what he has brought.
PETITIONER = (
    "   ,▄.   ",
    "  ▟▒█▒▙  ",
    "  ▝▀█▀▘  ",
    " ╱▐▓█▓▌╲ ",
    "  ▐▓█▓▌  ",
    "  ▐░█░▌  ",
    "  ▟▘ ▝▙  ",
)

PETITIONER_PAINT = (
    "   ccc   ",
    "  mmmmm  ",
    "  ccccc  ",
    " ccccccc ",
    "  nnnnn  ",
    "  nnnnn  ",
    "  aa aa  ",
)

BOWED = (
    "         ",
    "   ,▄.   ",
    "  ▟▒█▒▙  ",
    "  ▝▀█▀▘  ",
    " ╱▐▓█▓▌╲ ",
    "  ▐░█░▌  ",
    "  ▟▘ ▝▙  ",
)

BOWED_PAINT = (
    "         ",
    "   aaa   ",
    "  ddddd  ",
    "  aaaaa  ",
    " aaaaaaa ",
    "  aaaaa  ",
    "  aa aa  ",
)

KIN = (
    "   ,▄.   ",
    "  ▟▒█▒▙  ",
    "  ▝▀█▀▘  ",
    " ╱▐▓█▓▌╲ ",
    "  ▐▓█▓▌  ",
    "  ▐░█░▌  ",
    "  ▐▒█▒▌  ",
)

KIN_PAINT = (
    "   ggg   ",
    "  mmmmm  ",
    "  ccccc  ",
    " ccwwwcc ",
    "  wwwww  ",
    "  wwwww  ",
    "  wwwww  ",
)

BEARER = (
    "   ,▄.   ",
    "  ▟▒█▒▙  ",
    "  ▝▀█▀▘  ",
    " ╱▐▓█▓▌▟▙",
    "  ▐▓█▓▌█▌",
    "  ▐░█░▌▀▘",
    "  ▟▘ ▝▙  ",
)

BEARER_PAINT = (
    "   kkk   ",
    "  mmmmm  ",
    "  ccccc  ",
    " ccccccee",
    "  cccccee",
    "  nnnnnee",
    "  aa aa  ",
)

FIGURE_WIDTH = 9

# A pillar of the hall: palm capital, fluted shaft, moulded base. Drawn to
# whatever height the room has left, so it stands on the floor rather than
# floating above it.
PILLAR_CAPITAL = ("╲▟█▙╱", "═╬█╬═", "╔╩█╩╗")
PILLAR_SHAFT = ("║░█░║", "╠▒█▒╣", "║▓█▓║", "╠▒█▒╣")
PILLAR_BASE = ("╚╦█╦╝", "═╩█╩═", "▟███▙")
PILLAR_PAINT = {"capital": "ggggg", "shaft": "nnnnn", "base": "nnnnn"}

# A lamp on its stand, in the corners of the floor. The flame is the only
# flickering thing in the room, so it takes the one colour that means the lamp.
BRAZIER = (
    " .:. ",
    " ▟▓▙ ",
    "═╬█╬═",
    " ╱█╲ ",
    "▄▟█▙▄",
)

BRAZIER_PAINT = (
    " lll ",
    " lll ",
    "ggggg",
    " nnn ",
    "nnnnn",
)


def pillar(height: int) -> tuple[str, ...]:
    """A pillar drawn to fit, banded rather than one glyph repeated flat."""
    body = max(0, height - len(PILLAR_CAPITAL) - len(PILLAR_BASE))
    shaft = tuple(PILLAR_SHAFT[index % len(PILLAR_SHAFT)]
                  for index in range(body))
    return PILLAR_CAPITAL + shaft + PILLAR_BASE


def pillar_paint(height: int) -> tuple[str, ...]:
    rows = pillar(height)
    return tuple(
        PILLAR_PAINT["capital"] if index < len(PILLAR_CAPITAL)
        else PILLAR_PAINT["base"] if index >= len(rows) - len(PILLAR_BASE)
        else PILLAR_PAINT["shaft"]
        for index in range(len(rows)))


# Ornament along the top of a wall: a repeating Levantine guilloche, in five
# glyphs rather than one so it reads as carving and not as a rule.
CORNICE = "◢▄◣▀◤▄◥▀"
PAVING = "▚▞:▞▚·▩▤∙▤▩·"


def band(motif: str, width: int, offset: int = 0) -> str:
    """A repeating ornament cut to a width, at an offset so courses interlock."""
    return "".join(motif[(index + offset) % len(motif)]
                   for index in range(max(0, width)))


def floor(width: int, offset: int = 0) -> str:
    """Tiled paving. The offset lets two courses sit out of step."""
    return band(PAVING, width, offset)

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
    "   ╱▐███▙    ",
    "  ╱▄▟█████▙  ",
    " ▄█████████▙ ",
    "▟█≡≡≡≡≡≡≡≡▓█▙",
    "██▤██▤██▤██▤█",
)

SILOS = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▐█▀▀███▀▀█▌ ",
    " ▐█ ▩███▩ █▌ ",
    " ▐█▄▄███▄▄█▌ ",
    "▐███≡≡≡≡≡███▌",
    "███▪██∩██▪███",
)

RAMPART = (
    "█▀█▀█▀█▀█▀█▀█",
    "█▪███▪███▪███",
    "███▄▄▄▄▄▄▄███",
    "███▛▀▀▀▀▀▜███",
    "███▌░░░░░▐███",
    "███▌░░∩░░▐███",
    "██≡≡≡≡≡≡≡≡≡██",
)

FORGE = (
    "  ░ · ░      ",
    "  ▒   ▒  ░   ",
    "  ▐▌ ▐▌  ▒   ",
    "  ▐███████▙  ",
    " ▟███▪█▪███▙ ",
    "▐█▓▒░◘◘◘░▒▓█▌",
    "███≡≡≡≡≡≡≡███",
)

ZIGGURAT = (
    "      ▲      ",
    "     ▟█▙     ",
    "    ▟█∩█▙    ",
    "   ▐█████▌   ",
    "  ▄▄▄≡≡≡▄▄▄  ",
    " ▟███≡≡≡███▙ ",
    "▟██▪█≡≡≡█▪██▙",
    "█▓▒░▓≡≡≡▓░▒▓█",
    "████▪█∩█▪████",
)

TABLET_HOUSE = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▐█▤▤█▤▤█▤█▌ ",
    " ▐█████████▌ ",
    " ▐█▤▤█▤▤█▤█▌ ",
    "▐████∩██████▌",
    "███≡≡≡≡≡≡≡███",
)

CHANNEL = (
    "  ╫░░░░░░░╫  ",
    "▄▄▄▄▄▄▄▄▄▄▄▄▄",
    "█≈≈≈≈≈≈≈≈≈≈≈█",
    "█≈≈≈≈≈≈≈≈≈≈≈█",
    "██≡██≡██≡████",
)

CAUSEWAY = (
    "      ░      ",
    "     ░░░     ",
    "    ▒▒▒▒▒    ",
    "   ▒▒▒▒▒▒▒   ",
    "  ▓▓▓▓▓▓▓▓▓  ",
    "▪▓▓▓▓▓▓▓▓▓▓▪ ",
    "█████████████",
)

PALACE = (
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▟█▪█▪█▪█▪█▙ ",
    "▐███▀▀▀▀▀███▌",
    "▐██▌╫╫╫╫╫▐██▌",
    "▐██▌╫╫∩╫╫▐██▌",
    "███≡≡≡≡≡≡≡███",
)

BARRACKS = (
    " ▲ ▲ ▲   ▲ ▲ ",
    " █ █ █   █ █ ",
    "▄▄▄▄▄▄▄▄▄▄▄▄▄",
    "█▛▀▀▀▀▀▀▀▀▀▜█",
    "█▌◘░◘░◘░◘░◘▐█",
    "█▙▄▄▄▄▄▄▄▄▄▄█",
    "███≡≡≡∩≡≡≡███",
)

HOVEL = (
    "             ",
    "             ",
    "   ▄▄▄▄▄▄▄   ",
    "  ▟███████▙  ",
    " ▐█▌▪░░░▪▐█▌ ",
    " ▐████∩████▌ ",
    "██≡≡≡≡≡≡≡≡≡██",
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
    {"█": "▒", "▓": "░", "▒": "░", "▟": "▒", "▙": "▒", "▛": "░", "▜": "░",
     "≡": "·", "▤": "·", "▩": "·", "◘": "·", "╫": "·", "▪": "·", "∩": "·"},
    {"█": "░", "▓": "░", "▒": "░", "▟": "░", "▙": "░", "▛": " ", "▜": " ",
     "▲": "·", "▐": "░", "▌": "░", "▄": "░", "▀": "░", "≡": " ", "▤": " ",
     "▩": " ", "◘": " ", "╫": " ", "▪": " ", "∩": " ", "╱": " ", "·": " "},
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


# --- the lower town -----------------------------------------------------------
#
# What stands behind the palace quarter. Three rows, drawn faint, and never the
# same run twice across a width: the motifs are different widths and cycle in a
# fixed order, so the band desynchronises with itself and reads as a town rather
# than as wallpaper. Fixed order, because there is no random in this project.

_T_HOUSE = (
    " ▄▄▄▄ ",
    "▗████▖",
    "▐█▪▪█▌",
)
_T_GABLE = (
    "  ▟▙ ",
    " ▟██▙",
    "▐███▌",
)
_T_HUT = (
    "▗▄▄▖",
    "▐██▌",
    "▐▪▪▌",
)
_T_SHRINE = (
    "  ▄▄▄  ",
    " ▟███▙ ",
    "▐█▪∩▪█▌",
)
_T_PALM = (
    "▚▄█▄▞",
    "  █  ",
    "  █  ",
)
_T_YARD = (
    "   ",
    "   ",
    "▫ ▫",
)
_T_ROW = (
    "▗▄▄▖▗▄▖ ",
    "▐██▌▐█▌ ",
    "▐▪█▌▐▪▌ ",
)

TOWN_MOTIFS = (_T_HOUSE, _T_YARD, _T_HUT, _T_GABLE, _T_ROW, _T_PALM,
               _T_SHRINE, _T_YARD, _T_GABLE, _T_HUT, _T_HOUSE, _T_PALM,
               _T_SHRINE, _T_ROW, _T_HUT, _T_YARD)


def town(width: int, offset: int = 0) -> tuple[str, ...]:
    """A band of lower town `width` columns wide. Three rows, bottom-aligned."""
    rows = ["", "", ""]
    index = offset
    while len(rows[0]) < width:
        motif = TOWN_MOTIFS[index % len(TOWN_MOTIFS)]
        for line, piece in zip(range(3), motif):
            rows[line] += piece
        index += 1
    return tuple(row[:width] for row in rows)


def occlude(surface: Surface, x: int, y: int, rows, bg: int = C["ink"]) -> None:
    """Clear what stands behind a drawing, per column, beneath its silhouette.

    `draw` writes nothing where a drawing has a space, which is right for a
    picture on an empty field and wrong for one standing in front of a town: the
    lower town would show through the gate of the walls. Blanking the whole
    bounding box would cut a rectangle out of the sky instead, so each column is
    cleared only from its own first ink downwards.
    """
    for column in range(max(len(row) for row in rows)):
        top = next((index for index, row in enumerate(rows)
                    if column < len(row) and row[column] != " "), None)
        if top is None:
            continue
        for index in range(top, len(rows)):
            surface.put(x + column, y + index, " ", C["ink"], bg)


# --- the sky ------------------------------------------------------------------

# The month is lunar and the turn is half of one, so the moon over the city is
# the calendar: waxing in the former half, waning in the latter. It is the one
# decoration on this screen that is also information.
MOON_WAXING = (
    " ▄▄▖ ",
    "▐███▌",
    " ▀▀▘ ",
)
MOON_WANING = (
    " ▗▄▄ ",
    "▐███▌",
    " ▝▀▀ ",
)

BIRD = "╲╱"
CLOUD = ("▗▄▄▄▖  ▄▄", " ▀▀▀▀▀▀▀ ")
