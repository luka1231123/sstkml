"""Works actions and evidence remain truthful at the supported minimum size."""
from __future__ import annotations

import dataclasses

import pytest

from belief.project import project
from engine import actions as A
from engine import seat, works as works_engine
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tui import works
from tui.grid import plain_text


SEED = 8814402919
MINIMUM = (62, 21)


def _belief() -> dict:
    return project(load_campaign("seat", SEED))


def _active_world(fortnight: int):
    world = load_campaign("seat", SEED)
    while world.date.fortnight != fortnight:
        world, _ = advance(world)
    world, _ = apply(world, A.BeginBuild("walls", "seat"))
    return world


def test_minimum_works_wraps_complete_costs_and_names_visible_keys() -> None:
    b = _belief()
    page = works.plan_page(b, *MINIMUM)
    text = plain_text(works.compose(b, width=MINIMUM[0], height=MINIMUM[1]))

    assert page.room == 2
    assert "42 copper, 3,500 grain" in text
    assert "108 copper, 9,000 grain" in text
    assert "[1-2] inspect" in text
    assert "[1-9] inspect" not in text
    assert "↑↓ plans 1–2 OF 9" in text
    assert "shift+↑↓" not in text
    assert "call window closed" in text
    assert "closedopens" not in text


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

    # With no work selected, ordinary arrows browse plans. The player should
    # not need a modifier merely because MEN OUT happens to be above them.
    game.on_works_key(Key(keysym="Down"))
    assert game.works_plan_scroll == 1
    assert game.works_scroll == 0


def test_works_drafts_one_useful_chunk_then_calls_it_once() -> None:
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.world = _active_world(13)
    game.hours = project(game.world)["attention"]
    game.log = []
    game.client = None
    game.works_pick = ""
    game.works_plan_pick = ""
    game.works_corvee_draft = 0
    game._size = lambda _key: MINIMUM
    game.repaint = lambda: None

    class Key:
        def __init__(self, char: str = "", keysym: str = "") -> None:
            self.char = char
            self.keysym = keysym or char
            self.state = 0

    before_hours, before_unrest = game.hours, game.world.court.unrest
    game.on_works_key(Key("]"))
    assert game.works_corvee_draft == 400
    assert not game.log
    text = plain_text(game.compose("works"))
    assert "draft 400 more days" in text
    assert "unrest +16" in text and "[c] levy" in text
    assert "crews start next fortnight" in text

    game.on_works_key(Key("c"))
    assert game.log[-1]["action"]["_t"] == "RaiseCorvee"
    assert game.log[-1]["action"]["days"] == 400
    assert game.hours == before_hours - 1
    assert game.world.court.unrest == before_unrest + 16
    assert game.works_corvee_draft == 0


def test_uncommitted_corvee_drafts_lapse_with_the_fortnight() -> None:
    import play_gui

    class Window:
        def focus(self) -> None:
            pass

    class App:
        windows = {}

        def close(self, _key: str) -> None:
            pass

        def window(self, *_args, **_kwargs):
            return Window()

    game = play_gui.Game.__new__(play_gui.Game)
    game.world = _active_world(17)
    game.counsel_pending = None
    game.stack_order = []
    game.open_letters = set()
    game.app = App()
    game.repaint = lambda: None
    game.save_current = lambda automatic=False: True
    game.works_corvee_draft = 400
    game.ledger_state["land"]["amount"] = 400

    game.end_fortnight()

    assert game.works_corvee_draft == 0
    assert game.ledger_state["land"]["amount"] == 0


@pytest.mark.parametrize("fortnight", [12, 18])
def test_corvee_call_outside_the_useful_window_is_atomic(fortnight: int) -> None:
    world = _active_world(fortnight)
    before = (
        world.court.unrest,
        seat.corvee_days(world),
        seat.corvee_sources(world),
    )
    with pytest.raises(ValueError, match="starts next fortnight"):
        apply(world, A.RaiseCorvee(400))
    assert (
        world.court.unrest,
        seat.corvee_days(world),
        seat.corvee_sources(world),
    ) == before


@pytest.mark.parametrize("fortnight", [13, 14, 15, 16, 17])
def test_every_open_call_date_buys_the_next_work_tick(fortnight: int) -> None:
    world = _active_world(fortnight)
    called, _ = apply(world, A.RaiseCorvee(400))
    progressed, _ = advance(called)
    work = next(iter(progressed.court.projects.values()))
    assert work.days_done == 400


def test_useful_call_cap_shrinks_with_the_low_water_window() -> None:
    at_13 = _active_world(13)
    at_17 = _active_world(17)
    assert works_engine.useful_call_days(at_13) == 2000
    assert works_engine.useful_call_days(at_17) == 400

    with pytest.raises(ValueError, match="only 2000 useful"):
        apply(at_13, A.RaiseCorvee(2001))


def test_useful_call_cap_never_offers_more_than_field_hands_can_supply() -> None:
    world = _active_world(13)
    cohorts = dict(world.kernel.registry.cohorts)
    cohort_id = "cohort:ugarit_field_hands"
    cohort = cohorts[cohort_id]
    cohorts[cohort_id] = dataclasses.replace(
        cohort, people=5, households=min(cohort.households, 5))
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    source_limit = seat.source_corvee(world, 10_000)[0]

    assert 0 < source_limit < 2000
    assert works_engine.useful_call_days(world) == source_limit
    assert project(world)["land"]["corvee_usable_days"] == source_limit

    with pytest.raises(ValueError, match=rf"only {source_limit} useful"):
        apply(world, A.RaiseCorvee(source_limit + 1))


def test_last_low_water_player_phase_promises_no_future_progress() -> None:
    world = _active_world(18)
    text = plain_text(works.compose(
        project(world), width=MINIMUM[0], height=24))
    assert "next advance brings no work" in text
    assert "able to move" not in text
