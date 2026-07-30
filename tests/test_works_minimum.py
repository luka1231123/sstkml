"""Works actions and evidence remain truthful at the supported minimum size."""
from __future__ import annotations

from belief.project import project
from load import load_scenario
from tui import works
from tui.grid import plain_text


SEED = 8814402919
MINIMUM = (62, 21)


def _belief() -> dict:
    return project(load_scenario("ugarit", SEED))


def test_minimum_works_wraps_complete_costs_and_names_visible_keys() -> None:
    b = _belief()
    page = works.plan_page(b, *MINIMUM)
    text = plain_text(works.compose(b, width=MINIMUM[0], height=MINIMUM[1]))

    assert page.room == 2
    assert "42 copper, 3,500 grain" in text
    assert "108 copper, 9,000 grain" in text
    assert "[1-2] set it in hand" in text
    assert "[1-9] set it in hand" not in text
    assert "shift+↑↓ plans 1–2 OF 9" in text


def test_minimum_works_cannot_commission_a_plan_it_does_not_show() -> None:
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.world = load_scenario("ugarit", SEED)
    game.works_pick = ""
    game.works_scroll = 0
    game.works_plan_scroll = 0
    game._size = lambda _key: MINIMUM
    game.repaint = lambda: None
    ordered = []
    game.order = lambda action, **_kwargs: ordered.append(action)

    class Key:
        def __init__(self, char: str = "", keysym: str = "",
                     state: int = 0) -> None:
            self.char = char
            self.keysym = keysym or char
            self.state = state

    # Only 1 and 2 are printed at this size.
    game.on_works_key(Key("3"))
    assert not ordered
    game.on_works_key(Key("2"))
    assert ordered and ordered[0].kind == game.belief["plans"][1]["kind"]

    # The printed Shift+Down instruction scrolls the plan list, not MEN OUT.
    game.on_works_key(Key(keysym="Down", state=1))
    assert game.works_plan_scroll == 1
    assert game.works_scroll == 0
