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
