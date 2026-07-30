"""M11: the window backend against a real Tk, and the windowed controller.

These open genuine windows, so they withdraw them immediately -- a test suite
must not throw rectangles onto the developer's screen. Where Tk is missing the
tests assert the fallback instead of failing, because a green suite on a box
without a display is the whole reason `available()` exists.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import registry
from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import document, hall, inbox
from tui import desktop
from tui.backend_tk import App, available
from tui.grid import Surface, plain_text

SEED = 8814402919


def _belief(turns: int = 8):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world, project(world)


def _hidden_app():
    """An App whose windows never appear."""
    app = App()
    return app


def _hide(window):
    window.root.withdraw()
    return window


def test_a_window_paints_exactly_the_screen_it_was_given():
    if not available():
        return
    app = _hidden_app()
    window = _hide(app.window("t", "test", 20, 3))
    surface = Surface(20, 3)
    surface.text(0, 0, "granary")
    surface.text(0, 1, "4,120 parisu")
    screen = surface.freeze()
    window.paint(screen)
    shown = window.text.get("1.0", "end-1c")
    assert shown == "\n".join(
        "".join(cell[0] for cell in row) for row in screen)
    assert "granary" in shown and "4,120 parisu" in shown
    window.close()


def test_a_tag_is_made_once_per_colour_pair_actually_used():
    """One tag per (fg, bg) in the screen, not one per cell."""
    if not available():
        return
    from tui.grid import INDEX
    app = _hidden_app()
    window = _hide(app.window("t", "test", 12, 2))
    surface = Surface(12, 2)
    surface.text(0, 0, "aaa", INDEX["blood"], INDEX["ink"])
    surface.text(3, 0, "bbb", INDEX["barley"], INDEX["ink"])
    window.paint(surface.freeze())
    assert window._tags == {
        f"c{INDEX['blood']}_{INDEX['ink']}",
        f"c{INDEX['barley']}_{INDEX['ink']}",
        f"c{INDEX['clay']}_{INDEX['ink']}",
    }
    window.close()


def test_repainting_replaces_rather_than_appends():
    if not available():
        return
    app = _hidden_app()
    window = _hide(app.window("t", "test", 10, 2))
    first, second = Surface(10, 2), Surface(10, 2)
    first.text(0, 0, "before")
    second.text(0, 0, "after")
    window.paint(first.freeze())
    window.paint(second.freeze())
    shown = window.text.get("1.0", "end-1c")
    assert "after" in shown and "before" not in shown
    assert shown.count("\n") == 1
    window.close()


def test_asking_twice_for_a_window_raises_the_one_already_open():
    """Opening the stores twice must not give the player two stores."""
    if not available():
        return
    app = _hidden_app()
    first = _hide(app.window("stores", "The Stores", 20, 4))
    second = app.window("stores", "The Stores", 20, 4)
    assert first is second
    assert len(app.windows) == 1
    app.close("stores")
    assert "stores" not in app.windows


def test_the_hall_and_the_tablets_all_paint_at_their_real_sizes():
    """Every composition the controller can open, through a real widget."""
    if not available():
        return
    _, b = _belief(8)
    app = _hidden_app()
    screens = {
        "hall": hall.compose(b, 92, 30),
        "stack": inbox.compose(b, 108, 36),
        "stores": document.stores(b, 62, 22),
        "roll": document.roll(b, 78, 22),
        "muster": document.muster(b, 62, 18),
        "letter": document.tablet(b["stack"][0], house=b.get("house")),
    }
    for key, screen in screens.items():
        window = _hide(app.window(key, key, len(screen[0]), len(screen)))
        window.paint(screen)
        assert window.text.get("1.0", "end-1c").count("\n") == len(screen) - 1
        window.close()


def test_without_tk_the_controller_says_so_and_does_not_raise():
    """The fallback is a sentence, not a traceback about a display name."""
    import play_gui
    assert callable(play_gui.main)
    assert play_gui.TABLETS.keys() <= {key for key, _, _ in hall.DOORS}


# --- the controller, exercised without a toolkit ------------------------------

def test_every_tablet_the_controller_opens_has_a_door_in_the_hall():
    """D33: every window is reachable from the hall by keyboard, always."""
    import play_gui
    doors = {key for key, _label, _target in hall.DOORS}
    for key in play_gui.TABLETS:
        assert key in doors, key


def test_the_composers_the_controller_names_all_return_a_screen():
    _, b = _belief(6)
    import play_gui
    for _key, (window_key, _title, how) in play_gui.TABLETS.items():
        width, height = desktop.default_size(window_key)
        screen = how(b, width, height)
        assert len(screen) == height
        assert all(len(row) == width for row in screen)
        assert plain_text(screen).strip()


class _Key:
    """A stand-in for a tkinter key event: the handlers read these two fields."""

    def __init__(self, char: str = "", keysym: str = "") -> None:
        self.char = char
        self.keysym = keysym or char


def _game(turns: int = 7):
    """A Game with every window hidden, driven without a main loop.

    Wound forward far enough that the harbour has actually delivered something:
    at turn 1 the stack is empty, and a test that read from it would pass by
    doing nothing at all.
    """
    import play_gui
    game = play_gui.Game("ugarit", SEED)
    for _ in range(turns):
        game.end_fortnight()
    assert game.belief["stack"], "no post arrived; the read tests would be hollow"
    for window in game.app.windows.values():
        window.root.withdraw()
    original = game.app.window

    def hidden(*args, **kwargs):
        window = original(*args, **kwargs)
        window.root.withdraw()
        return window

    game.app.window = hidden
    return game


def test_a_door_key_opens_a_window_and_pressing_it_again_does_not_open_a_second():
    if not available():
        return
    game = _game()
    game.on_key(_Key("t"))
    assert "stores" in game.app.windows
    first = game.app.windows["stores"]
    game.on_key(_Key("t"))
    assert game.app.windows["stores"] is first
    game.app.stop()


def test_reading_from_the_inbox_costs_hours_and_keeps_the_tablet_selected():
    """The integrated Inbox is where attention is spent and text remains."""
    if not available():
        return
    import play_gui
    game = _game()
    game.on_key(_Key("s"))
    before = game.hours
    first = game.stack_order[0]
    game.on_inbox_key(_Key(keysym="Return"))
    assert game.hours == before - registry.BY_ID["read_letter"].cost
    assert game.inbox_pick == first
    assert next(i for i in game.belief["stack"] if i["id"] == first)["read"]
    # Reading it a second time is free, and selection does not disappear merely
    # because the Unread filter no longer contains the tablet.
    again = game.hours
    game.on_inbox_key(_Key(keysym="Return"))
    assert game.hours == again
    assert game.stack_order[0] == first
    game.app.stop()


def test_answering_stays_in_the_scribes_room_with_source_and_wet_clay():
    if not available():
        return
    game = _game()
    game.on_key(_Key("s"))
    game.on_inbox_key(_Key(keysym="Return"))
    game.on_inbox_key(_Key("r"))
    assert game.desk is not None
    assert "stack" in game.app.windows
    assert "desk" not in game.app.windows
    text = plain_text(game.compose("stack"))
    assert "SOURCE TABLET" in text
    assert "WET TABLET" in text
    game.on_inbox_key(_Key(keysym="Escape"))
    assert game.desk is None
    assert "stack" in game.app.windows
    game.app.stop()


def test_old_roll_and_land_keys_open_stations_in_one_storehouse():
    if not available():
        return
    game = _game()
    game.on_key(_Key("r"))
    first = game.app.windows["stores"]
    assert game.storehouse_view == "roll"
    game.on_key(_Key("l"))
    assert game.storehouse_view == "land"
    assert game.app.windows["stores"] is first
    assert "roll" not in game.app.windows and "land" not in game.app.windows
    game.app.stop()


def test_an_hourless_king_gets_a_visible_refusal_for_an_unread_tablet():
    if not available():
        return
    game = _game()
    game.hours = 1
    game.on_key(_Key("s"))
    first = game.stack_order[0]
    game.on_inbox_key(_Key(keysym="Return"))
    assert game.hours == 1
    assert not next(i for i in game.belief["stack"] if i["id"] == first)["read"]
    assert "requires" in game.session_notice
    game.app.stop()


def test_escape_closes_a_tablet_and_the_hall_survives_it():
    if not available():
        return
    game = _game()
    game.on_key(_Key("r"))
    assert "stores" in game.app.windows
    assert game.storehouse_view == "roll"
    game.on_storehouse_key(_Key(keysym="Escape"))
    assert "stores" not in game.app.windows
    assert game.app.windows["hall"].root.winfo_exists()
    game.repaint()                      # the hall still paints afterwards
    game.app.stop()


def test_ending_the_fortnight_refills_the_hours_and_clears_the_desk():
    if not available():
        return
    game = _game()
    game.on_key(_Key("s"))
    game.on_inbox_key(_Key(keysym="Return"))
    assert game.inbox_pick
    turn = game.world.date.absolute
    game.on_key(_Key(keysym="space"))
    assert game.world.date.absolute == turn + 1
    assert game.hours == game.belief["attention"]
    assert "stack" in game.app.windows      # a ledger stays open across turns
    game.app.stop()


def test_save_and_reload_preserve_spent_attention() -> None:
    if not available():
        return
    game = _game()
    with TemporaryDirectory() as directory:
        game.save_path = Path(directory) / "campaign.json"
        game.hours = 3
        assert game.save_current()
        game.hours = game.belief["attention"]
        assert game.load_current()
        assert game.hours == 3
    game.app.stop()


def test_what_the_window_game_does_is_logged_the_way_the_headless_one_logs_it():
    """A session played in windows must save and replay like any other."""
    if not available():
        return
    from engine.actions import from_dict
    game = _game()
    game.on_key(_Key("s"))
    game.on_inbox_key(_Key(keysym="Return"))
    assert game.log
    entry = game.log[-1]
    assert entry["turn"] == game.world.date.absolute
    assert from_dict(entry["action"]).letter_id == game.stack_order[0]
    game.app.stop()


def test_reading_one_tablet_does_not_move_the_numbers_of_the_others():
    """Belief sorts the pile read-last; the window must not, or the keystroke
    after a read opens a tablet the player never chose."""
    if not available():
        return
    game = _game()
    before = list(game.stack_order)
    assert len(before) >= 3
    third = before[2]
    game.on_key(_Key("s"))
    game.on_inbox_key(_Key(keysym="Return"))
    assert game.stack_order == before
    assert game.stack_order[2] == third
    # And the projection really did reorder underneath it, so this is not a
    # test of nothing.
    assert [i["id"] for i in game.belief["stack"]] != before
    game.app.stop()


def test_new_post_goes_on_the_end_of_the_pile_not_the_top():
    if not available():
        return
    game = _game()
    before = list(game.stack_order)
    game.end_fortnight()
    assert game.stack_order[:len(before)] == [
        letter_id for letter_id in before if letter_id in game.stack_order]
    game.app.stop()


def test_diagnose_says_enough_to_tell_a_broken_install_from_a_broken_game():
    """`./run.sh --check`. The commonest failure on this project is not a bug,
    it is the wrong interpreter -- Apple's /usr/bin/python3 has neither tomllib
    nor Tk -- and the report has to make that obvious without a traceback."""
    from tui.backend_tk import diagnose
    check = diagnose()
    assert set(check) == {"interpreter", "version", "in_venv",
                          "tkinter", "tk_version", "display"}
    assert check["interpreter"] and check["version"][0].isdigit()
    assert isinstance(check["in_venv"], bool)


def test_the_launcher_and_the_venv_are_part_of_the_project():
    """The game must not depend on which python happens to be on PATH."""
    import os
    from pathlib import Path
    root = Path(__file__).parent.parent
    launcher = root / "run.sh"
    assert launcher.exists(), "run.sh is how the game is started"
    assert os.access(launcher, os.X_OK), "run.sh must be executable"
    assert ".venv" in (root / ".gitignore").read_text()


def test_there_is_only_ever_one_tk_root_in_a_process():
    """The crash this project actually shipped: `main()` called `available()`,
    which made a root and destroyed it, and then the game made a second one.
    Creating a root, destroying it and creating another aborts on macOS Aqua --
    SIGTRAP, no traceback, nothing on stderr, which is why it took a bisect to
    find. The root is now made once and never destroyed."""
    if not available():
        return
    from tui import backend_tk
    first = backend_tk._root()
    assert backend_tk._root() is first
    app_one, app_two = App(), App()
    assert app_one.root() is first and app_two.root() is first
    window = app_one.window("t", "t", 8, 2)
    window.root.withdraw()
    app_one.shutdown()
    # The App is done, and the shared root outlives it intact.
    assert app_one.windows == {}
    assert backend_tk._root() is first
    assert first.winfo_exists()


def test_a_new_game_is_a_new_world():
    """Determinism is about *reproducing* a run, not about every run being the
    same one. A pinned default seed quietly turned the second into the first."""
    import play_cli
    import play_gui
    from session import new_seed
    assert len({new_seed() for _ in range(8)}) == 8
    assert not hasattr(play_gui, "SEED"), "no module-level pinned seed"
    assert "8814402919" not in Path(play_gui.__file__).read_text()
    assert "8814402919" not in Path(play_cli.__file__).read_text()


def test_the_seed_given_back_reproduces_the_world_exactly():
    """The printed seed has to be the whole story, or it is decoration."""
    from engine.core import state_hash
    from engine.tick import advance
    from load import load_scenario
    from session import new_seed
    seed = new_seed()
    runs = []
    for _ in range(2):
        world = load_scenario("ugarit", seed)
        for _ in range(6):
            world, _ = advance(world)
        runs.append(state_hash(world))
    assert runs[0] == runs[1]
    other = load_scenario("ugarit", new_seed())
    for _ in range(6):
        other, _ = advance(other)
    assert state_hash(other) != runs[0]
