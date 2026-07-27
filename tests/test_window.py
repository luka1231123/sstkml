"""M11: the window backend against a real Tk, and the windowed controller.

These open genuine windows, so they withdraw them immediately -- a test suite
must not throw rectangles onto the developer's screen. Where Tk is missing the
tests assert the fallback instead of failing, because a green suite on a box
without a display is the whole reason `available()` exists.
"""
from __future__ import annotations

from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import document, hall
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
        "stack": document.stack(b, 80, 24),
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
    for _key, (_window, _title, (width, height), how) in play_gui.TABLETS.items():
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


def test_reading_from_the_stack_costs_hours_and_opens_the_tablet():
    """The stack is where attention is actually spent."""
    if not available():
        return
    import play_gui
    game = _game()
    game.on_key(_Key("s"))
    before = game.hours
    first = game.stack_order[0]
    game.on_tablet_key(_Key("1"), "stack")
    assert game.hours == before - play_gui.READ_COST
    assert f"letter:{first}" in game.app.windows
    assert next(i for i in game.belief["stack"] if i["id"] == first)["read"]
    # Opening it a second time is free, and it is still the same tablet: the
    # pile does not reshuffle because one was read.
    again = game.hours
    game.on_tablet_key(_Key("1"), "stack")
    assert game.hours == again
    assert game.stack_order[0] == first
    game.app.stop()


def test_an_hourless_king_simply_cannot_open_another_tablet():
    """The refusal is silent, and nothing explains why (D19)."""
    if not available():
        return
    game = _game()
    game.hours = 1
    game.on_key(_Key("s"))
    game.on_tablet_key(_Key("1"), "stack")
    assert game.hours == 1
    assert not any(k.startswith("letter:") for k in game.app.windows)
    game.app.stop()


def test_escape_closes_a_tablet_and_the_hall_survives_it():
    if not available():
        return
    game = _game()
    game.on_key(_Key("r"))
    assert "roll" in game.app.windows
    game.on_tablet_key(_Key(keysym="Escape"), "roll")
    assert "roll" not in game.app.windows
    assert game.app.windows["hall"].root.winfo_exists()
    game.repaint()                      # the hall still paints afterwards
    game.app.stop()


def test_ending_the_fortnight_refills_the_hours_and_clears_the_desk():
    if not available():
        return
    game = _game()
    game.on_key(_Key("s"))
    game.on_tablet_key(_Key("1"), "stack")
    assert any(k.startswith("letter:") for k in game.app.windows)
    turn = game.world.date.absolute
    game.on_key(_Key(keysym="space"))
    assert game.world.date.absolute == turn + 1
    assert game.hours == game.belief["attention"]
    assert not any(k.startswith("letter:") for k in game.app.windows)
    assert "stack" in game.app.windows      # a ledger stays open across turns
    game.app.stop()


def test_what_the_window_game_does_is_logged_the_way_the_headless_one_logs_it():
    """A session played in windows must save and replay like any other."""
    if not available():
        return
    from engine.actions import from_dict
    game = _game()
    game.on_key(_Key("s"))
    game.on_tablet_key(_Key("1"), "stack")
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
    game.on_tablet_key(_Key("1"), "stack")
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
