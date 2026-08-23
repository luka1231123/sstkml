"""The dashboard, clickable grid, Counsel orders, and integrated Inbox."""
from __future__ import annotations

from ai import parser
from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tui import advice, counsel, hall, inbox, style
from tui.grid import InteractiveScreen, Surface, plain_text, pure_ascii
from engine import seat

SEED = 8814402919


def _world(turns: int = 8):
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _belief(turns: int = 8) -> dict:
    return project(_world(turns))


def test_interaction_is_a_sidecar_and_ascii_keeps_it() -> None:
    surface = Surface(30, 2)
    style.keycap(surface, 2, 0, "s", "Inbox")
    view = surface.interactive()
    assert isinstance(view, InteractiveScreen)
    assert view.command_at(2, 0) == "s"
    assert plain_text(view).startswith("  [s] Inbox")
    folded = pure_ascii(view)
    assert isinstance(folded, InteractiveScreen)
    assert folded.command_at(2, 0) == "s"


def test_disabled_controls_are_visible_but_not_clickable() -> None:
    surface = Surface(30, 1)
    style.keycap(surface, 0, 0, "x", "impossible", enabled=False)
    view = surface.interactive()
    assert "impossible" in plain_text(view)
    assert view.command_at(0, 0) is None


def test_hall_is_a_clickable_dashboard_with_advice() -> None:
    b = _belief()
    matters = advice.concerns(b)
    assert matters and all(item.reason and item.suggestion for item in matters)
    view = hall.compose(b)
    text = plain_text(view)
    assert "MATTERS BEFORE THE KING" in text
    assert "Scribes" in text
    # Advice appears in somebody's mouth or not at all (UI/UX spec 20). The
    # old unattributed `Do: ...` imperative made the palace sound omniscient.
    assert "Do:" not in text
    assert all(f"{item.speaker}:" in text or item.speaker not in text
               for item in matters)
    commands = {hit.command for hit in view.hits if hit.enabled}
    assert {"concern:0", "s", "y", "j", "space"} <= commands


def test_inbox_keeps_selection_and_tablet_in_one_view() -> None:
    world = _world()
    b = project(world)
    first = next(item for item in b["stack"] if not item["read"])
    unread = inbox.compose(b, selected=first["id"], filter_name="unread")
    assert "THE TABLET IS UNREAD" in plain_text(unread)
    assert f"select:{first['id']}" in {
        hit.command for hit in unread.hits}

    world, _ = apply(world, A.ReadLetter(first["id"]))
    read = inbox.compose(
        project(world), selected=first["id"], filter_name="all")
    text = plain_text(read)
    assert "THE TABLET IS UNREAD" not in text
    assert "reached your hand" in text


def test_counsel_is_an_always_ready_clickable_order_line() -> None:
    view = counsel.compose(
        _belief(), [], 8, suggestions=["Assign the household troops."])
    text = plain_text(view)
    assert "YOU SAY OR GIVE AN ORDER" in text
    assert "[enter] tell him" in text
    commands = {hit.command for hit in view.hits if hit.enabled}
    assert {"Return", "Control-u", "Escape", "F1"} <= commands


def test_preparser_covers_new_dashboard_orders() -> None:
    b = _belief()
    examples = (
        ("build a granary at seat", A.BeginBuild),
        ("repair the tablet house", A.BeginRepair),
        ("send the household troops to campaign at carchemish", A.AssignTroops),
        ("give the smiths of the palace quarter 7000 qa", A.Allocate),
        ("close the routes to ma_hadu", A.Quarantine),
        ("search the archive for oath", A.SearchArchive),
        ("hear boundary_ashiranu", A.HearPetition),
        ("set the land due to 250", A.SetLandDue),
        ("name niqmaddu heir", A.NameHeir),
    )
    for words, expected in examples:
        result = parser.preparse(words, b)
        assert result is not None and isinstance(result.actions[0], expected), words
    marriage = parser.preparse("marry pidray to hatti_king", b)
    assert marriage is None, "foreign marriage is written at the Desk"


def test_counsel_can_recommend_a_specific_next_step_offline() -> None:
    words = counsel.recommend(_belief(), "grain")
    assert "I would" in words
    assert "granary" in words


def _headless_game():
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = _world()
    game.hours = project(game.world)["attention"]
    game.log = []
    game.counsel_said = []
    game.counsel_typed = ""
    game.counsel_typing = True
    game.client = None
    game.repaint = lambda: None
    return game


def test_counsel_previews_then_executes_a_plain_order_and_logs_it() -> None:
    game = _headless_game()
    before = seat.allowances(game.world).get("smiths_palace")
    game.submit_counsel("allocate smiths_palace 7000")
    assert before != 7000
    assert seat.allowances(game.world).get("smiths_palace") == before
    assert game.log == []
    assert game.counsel_pending is not None
    assert "I understand the order as" in game.counsel_said[-1][1]

    game.confirm_counsel_order()
    assert seat.allowances(game.world)["smiths_palace"] == 7000
    assert game.log and game.log[-1]["action"]["_t"] == "Allocate"
    assert "It is done" in game.counsel_said[-1][1]


def test_a_multi_action_counsel_order_is_atomic() -> None:
    game = _headless_game()
    before = game.world
    game.execute_counsel_actions((
        A.Allocate("smiths_palace", 7000),
        A.BeginRepair("there_is_no_such_building"),
    ))
    assert game.world is before
    assert game.log == []
    assert "cannot do that" in game.counsel_said[-1][1]
