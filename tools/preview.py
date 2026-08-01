#!/usr/bin/env python3
"""Print a composed screen to the terminal. Development only.

    python3 tools/preview.py hall [turns] [--ascii] [--mono]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from belief.project import project              # noqa: E402
from engine.tick import advance                 # noqa: E402
from load import load_campaign                  # noqa: E402
from tui import hall                            # noqa: E402
from tui.backend_term import to_ansi            # noqa: E402

SEED = 8814402919


def main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else "hall"
    turns = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 6
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    belief = project(world)
    screens = {"hall": hall.compose}
    if which not in screens:
        print(f"no such screen: {which}; have {', '.join(screens)}")
        return 1
    screen = screens[which](belief)
    print(to_ansi(screen, colour="--mono" not in argv,
                  ascii_only="--ascii" in argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
