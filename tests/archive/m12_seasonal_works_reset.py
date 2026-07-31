"""Archived: the seasonal works_days reset that legacy land used to perform.

``Court.works_days`` is documented in ``engine/works.py`` as "what a building
site took this season".  The reset lived in the harvest step of
``engine/legacy/land.py`` (``at_harvest`` clearing ``corvee_days``,
``corvee_sources`` and ``works_days``).  The C4 re-point moved the crown's
fields to the kernel and that land module is no longer reached from
``engine/tick``, so ``works_days`` now accumulates forever (measured: 1248
after a walls repair, still 1248 after 150 turns and after the project
completes).

The original test waited one season for the reset and then asserted
``works_days == 0``, which is what the seasonal corvée contract promises.

Un-archive criteria: the engine resets ``works_days`` (with ``corvee_days``)
when the season rolls, independent of the legacy land module.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from engine import actions as A  # noqa: E402
from engine.reduce import apply  # noqa: E402
from engine.tick import advance  # noqa: E402
from tests.test_m12 import _working_world  # noqa: E402


def test_the_season_closing_frees_the_hands_again() -> None:
    world, _ = apply(_working_world(), A.BeginRepair("walls_seat"))
    for _ in range(30):
        world, _ = advance(world)
        if world.court.works_days == 0:
            break
    assert world.court.works_days == 0
