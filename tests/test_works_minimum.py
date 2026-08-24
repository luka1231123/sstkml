"""Works actions and evidence remain truthful at the supported minimum size."""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine import works as works_engine
from load import load_campaign
from tui import works
from tui.grid import plain_text


SEED = 8814402919
MINIMUM = (62, 21)


def _belief() -> dict:
    return project(load_campaign("seat", SEED))


def test_minimum_works_wraps_complete_costs_and_names_visible_keys() -> None:
    b = _belief()
    page = works.plan_page(b, *MINIMUM)
    text = plain_text(works.compose(b, width=MINIMUM[0], height=MINIMUM[1]))

    assert page.room == 2
    assert "42 copper, 3,500 grain" in text
    assert "108 copper, 9,000 grain" in text
    assert "[1-2] inspect" in text
    assert "[1-9] inspect" not in text
    assert "shift+↑↓ plans 1–2 OF 9" in text


def test_minimum_active_work_keeps_every_panel_border_intact() -> None:
    world = load_campaign("seat", SEED)
    world, _ = works_engine.begin_build(
        world, A.BeginBuild("walls", "seat"))
    text = plain_text(works.compose(
        project(world), width=MINIMUM[0], height=24))

    assert "waiting for low water" in text
    assert all(line.startswith(("╔", "║", "╚"))
               and line.endswith(("╗", "║", "╝"))
               for line in text.splitlines())


def test_minimum_works_cannot_commission_a_plan_it_does_not_show() -> None:
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.world = load_campaign("seat", SEED)
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

    # Only 1 and 2 are printed at this size, and commissioning follows the
    # visible inspection rather than sharing the selection keystroke.
    game.on_works_key(Key("3"))
    assert not ordered
    game.on_works_key(Key("2"))
    assert game.works_plan_pick == game.belief["plans"][1]["kind"]
    assert not ordered
    game.on_works_key(Key(keysym="Return"))
    assert ordered and ordered[0].kind == game.belief["plans"][1]["kind"]

    # The printed Shift+Down instruction scrolls the plan list, not MEN OUT.
    game.on_works_key(Key(keysym="Down", state=1))
    assert game.works_plan_scroll == 1
    assert game.works_scroll == 0
