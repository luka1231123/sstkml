"""Archived M12-adjacent ledger test.

Obsolete since C4: `dredge_canal` left the registry with the canal (the
action now refuses at `engine.reduce`, and no estate has a canal to dredge).
The refusal-with-a-notice UX this test pinned belongs to the deleted
interaction; it comes back, re-tuned, with the land re-point at C5.

Kept verbatim so the UX claim is not lost.
"""
from __future__ import annotations

from engine.tick import advance
from load import load_campaign

import registry


class _Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "", state: int = 0) -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = state


def test_the_land_will_not_dredge_a_field_with_no_canal() -> None:
    from tests.test_ledgers import _game

    game = _game()
    state = game.ledger_state["land"]
    state["amount"] = 5
    game.on_land_key(_Key("d"))
    assert not game.log
    assert game.notices["land"].kind == registry.REFUSAL
    assert "canal" in game.notices["land"]
