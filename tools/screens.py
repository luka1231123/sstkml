#!/usr/bin/env python3
"""Read what the game is showing, as text.

    ./run.sh --screens                    every screen, turn 6
    python3 tools/screens.py list
    python3 tools/screens.py hall --turns 12
    python3 tools/screens.py all --seed 8814402919 --turns 20
    python3 tools/screens.py letter 3     the third tablet on the pile, read
    python3 tools/screens.py live         what a running window game shows now

A screen is a rectangle of `(glyph, fg, bg)` (`tui/grid.py`), so it can be read
without a display, a screenshot or an eye: `plain_text` drops the colour and
hands back the glyphs. Everything the player sees is a pure function of Belief,
so re-composing it here from the same seed and turn count gives the same
rectangle the window would have painted -- there is nothing to capture.

Colour is dropped on purpose. Nothing in this game is ever said by colour alone
(spec 9.6), so if a distinction is invisible here it is a bug in the screen, not
in this tool. `--colour` puts it back if you want to look.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from belief.project import project              # noqa: E402
from engine import actions as A                 # noqa: E402
from engine.reduce import apply                 # noqa: E402
from engine.tick import advance                 # noqa: E402
from load import load_campaign                  # noqa: E402
from tui import desktop, inbox, ledgers, orders, palace, works
from tui import (altar, archive, alu, composer, counsel, document, hall,   # noqa: E402
                 help as help_page, worldmap)                       # noqa: E402
from tui.backend_term import to_ansi            # noqa: E402
from tui.grid import Screen, plain_text, pure_ascii   # noqa: E402

SEED = 8814402919
DUMP = ROOT / "saves" / "screens.txt"


def _ledger(key: str) -> dict:
    """The size and hours a workbench opens at, so the dump is what is played."""
    width, height = desktop.default_size(key)
    return {"width": width, "height": height, "hours": 8}

# name -> (title, how to compose it from Belief). The sizes are the ones
# `play_gui.TABLETS` opens the real windows at, so the wrapping read here is
# the wrapping the player gets.
SCREENS = {
    "hall": ("THE HALL", lambda b: hall.compose(
        b, *desktop.default_size("hall"))),
    "stack": ("THE TABLET HOUSE", lambda b: inbox.compose(
        b, *desktop.default_size("stack"))),
    # The five workbenches, at the sizes `tui.desktop` opens them.
    "stores": ("THE STOREHOUSE",
               lambda b: ledgers.stores(
                   b, room=True, **_ledger("stores"))),
    "roll": ("THE ROLL", lambda b: ledgers.roll(b, **_ledger("roll"))),
    "muster": ("THE CORVÉE", lambda b: ledgers.muster(b, **_ledger("muster"))),
    "oaths": ("THE OATHS", lambda b: ledgers.oaths(b, **_ledger("oaths"))),
    "land": ("THE LAND", lambda b: ledgers.land(b, **_ledger("land"))),
    "palace": ("THE PALACE", lambda b: palace.compose(
        b, view="court", hours=8,
        width=desktop.default_size("palace")[0],
        height=desktop.default_size("palace")[1])),
    "house": ("THE PALACE — THE HOUSE", lambda b: palace.compose(
        b, view="house", hours=8,
        width=desktop.default_size("palace")[0],
        height=desktop.default_size("palace")[1])),
    "relations": ("THE PALACE — RELATIONS", lambda b: palace.compose(
        b, view="relations", hours=8,
        width=desktop.default_size("palace")[0],
        height=desktop.default_size("palace")[1])),
    "help": ("FIELD MANUAL", lambda b: help_page.compose(52, 20)),
    "alu": ("THE ALU", lambda b: alu.compose(b, None, 96, 36)),
    "works": ("THE WORKS", lambda b: works.compose(b, "", 82, 32)),
    "world": ("THE KNOWN WORLD", lambda b: worldmap.compose(b, 104, 32)),
    "counsel": ("COUNSEL", lambda b: counsel.compose(
        b, _talk(b), 6, "", False, *desktop.default_size("counsel"))),
    "altar": ("THE ALTAR", lambda b: altar.compose(
        b, ["He reads the liver and says: the year will be a poor one."],
        "harvest", ("oil", 20), 78, 32)),
    "archive": ("THE SCRIBES' ROOM — RECORDS", lambda b: archive.compose(
        b, "oath", b.get("archive_index", {}).get("hits", {}).get("oath", []),
        "", False, *desktop.default_size("stack"), embedded=True)),
    "orders": ("ORDERS", lambda b: orders.compose(
        b, _LOG, max((r["turn"] for r in _LOG), default=0),
        hours=8, view="all", width=88, height=30)),
    "desk": ("THE SCRIBES' ROOM — WRITING TABLE", lambda b: _desk(b)),
}


def _talk(b: dict) -> list[tuple[str, str]]:
    """A sample exchange, so the room can be read with words in it."""
    key, question, topic = counsel.QUESTIONS[1]
    return [("king", question),
            ("scribe", counsel.answer(b, topic, SEED, 8))]


def _desk(b: dict):
    """The desk answering whatever is at the top of the pile."""
    item = b["stack"][0]
    matter = (
        "I cannot grant what this tablet asks. "
        "The needs of my house must stand.")
    blocks = composer.default_blocks()
    draft = composer.assemble(item["sender"], blocks, matter)
    # Writing is a station inside correspondence and uses that room's actual
    # capacity, not the retired standalone Desk geometry.
    width, height = desktop.default_size("stack")
    return composer.compose(
        item, draft, "reply", house=b.get("house"),
        width=width, height=height, blocks=blocks, matter=matter)


def state(chosen_alu: str = "seat", seed: int = SEED, turns: int = 6):
    """A world advanced `turns` fortnights."""
    world = load_campaign(chosen_alu, seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def read_nth(world, index: int):
    """Read the nth tablet on the pile and hand back the world and its id.

    The id, not the index: Belief sorts the stack read-last, so the letter the
    player just read is no longer where he found it. Reading goes through the
    ordinary action, because an unread letter's figures are not his to see yet.
    """
    stack = project(world)["stack"]
    if not 0 <= index < len(stack):
        return world, None
    letter_id = stack[index]["id"]
    world, _ = apply(world, A.ReadLetter(letter_id))
    return world, letter_id


# Some screens only have anything in them after an action. The reader performs
# it through the ordinary engine, so what is printed is a state the player could
# actually be in.
PREPARE = {
    "archive": lambda world: apply(world, A.SearchArchive("oath"))[0],
    "orders": lambda world: _give_orders(world),
}

# Orders reads the session log rather than the world, so the reader has to have
# given some. It gives them through the ordinary reducer and records them the
# way the game does, so what prints is a history that could really exist.
_LOG: list[dict] = []


def _give_orders(world):
    b = project(world)
    said = [A.Quarantine(b["world_graph"]["places"][1]["id"], False),
            A.SendToHarvest(b["groups"][0]["id"], True),
            A.InspectLedger("granary"),
            A.SetLandDue(400)]
    _LOG.clear()
    for action in said:
        world, _ = apply(world, action)
        _LOG.append({"turn": world.date.absolute, "action": A.to_dict(action)})
    return world


def show(screen: Screen, colour: bool = False, ascii_only: bool = False) -> str:
    if ascii_only:
        screen = pure_ascii(screen)
    if colour:
        return to_ansi(screen, colour=True)
    return plain_text(screen)


def frame(name: str, body: str, colour: bool = False) -> str:
    """A rule above each screen so a dump of several stays readable."""
    reset = "\033[0m" if colour else ""
    return f"\n{reset}── {name} " + "─" * max(0, 60 - len(name)) + "\n" + body


def live() -> int:
    """Print the dump a running window game left behind.

    `STK_DUMP=1 ./run.sh` makes the game write every window it repaints to
    `saves/screens.txt`; pressing `\\` in the hall writes it on demand. This is
    the one path that reads a real window rather than re-composing one, and it
    exists for the case where the two disagree.
    """
    if not DUMP.exists():
        print("no live dump. start the game with the recorder on:\n"
              "  STK_DUMP=1 ./run.sh\n"
              "then press \\ in the hall, or just let it write on every "
              "repaint.")
        return 1
    print(DUMP.read_text().rstrip())
    return 0


def main(argv: list[str]) -> int:
    flags = {a for a in argv[1:] if a.startswith("--")}
    words = [a for a in argv[1:] if not a.startswith("--")]

    def option(name: str, fallback: int) -> int:
        for flag in flags:
            if flag.startswith(f"--{name}="):
                return int(flag.split("=", 1)[1])
        return fallback

    which = words[0] if words else "all"
    if which == "list":
        print("\n".join(sorted(SCREENS) + ["letter <n>", "all", "live"]))
        return 0
    if which == "live":
        return live()

    colour, ascii_only = "--colour" in flags, "--ascii" in flags
    turns, seed = option("turns", 6), option("seed", SEED)

    if which == "letter":
        index = int(words[1]) - 1 if len(words) > 1 else 0
        world, letter_id = read_nth(state(seed=seed, turns=turns), index)
        if letter_id is None:
            count = len(project(world)["stack"])
            print(f"there are {count} on the pile at turn {turns}.")
            return 1
        b = project(world)
        item = next(i for i in b["stack"] if i["id"] == letter_id)
        print(frame(f"TABLET {index + 1} — {item['id']}",
                    show(document.tablet(item, house=b.get("house")),
                         colour, ascii_only), colour))
        return 0

    names = sorted(SCREENS) if which == "all" else [which]
    if which != "all" and which not in SCREENS:
        print(f"no such screen: {which}. try:  python3 tools/screens.py list")
        return 1

    base = state(seed=seed, turns=turns)
    print(f"seed {seed}, turn {turns}, "
          f"{project(base)['attention']} hours in hand")
    for name in names:
        title, compose = SCREENS[name]
        world = PREPARE[name](base) if name in PREPARE else base
        print(frame(title, show(compose(project(world)), colour, ascii_only),
                    colour))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
