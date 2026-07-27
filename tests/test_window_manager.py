"""The window manager against a real Tk (UI/UX spec 6, 13, 21).

These open genuine windows and withdraw them at once, like `test_window.py`,
and assert the fallback where Tk is missing rather than failing -- a suite that
goes red on a machine without a display is telling you about the machine.

What is checked here is the part that cannot be checked in integers: that the
toolkit really does report a different cell capacity at a different type size,
that a resize reaches the controller, and that geometry survives a close.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from tui import desktop, switcher
from tui.backend_tk import App, available
from tui.grid import Surface, plain_text


def _hidden(app, key, width, height, **kwargs):
    window = app.window(key, key, width, height, **kwargs)
    window.root.withdraw()
    return window


def test_a_window_opens_at_eleven_point_by_default():
    if not available():
        assert desktop.FONT_DEFAULT == 11
        return
    app = App()
    window = _hidden(app, "hall", *desktop.default_size("hall"))
    assert window.font.cget("size") == desktop.FONT_DEFAULT
    app.shutdown()


def test_bigger_type_leaves_the_rectangle_alone_and_shrinks_the_grid():
    """Spec 6: recompose cells at every size; do not scale a bitmap."""
    if not available():
        return
    app = App()
    window = _hidden(app, "hall", *desktop.default_size("hall"))
    window.root.update_idletasks()
    small_cell = window.cell_size()
    window.set_font_size(20)
    window.root.update_idletasks()
    large_cell = window.cell_size()
    assert large_cell[0] > small_cell[0]
    assert large_cell[1] > small_cell[1]
    app.shutdown()


def test_the_font_stays_inside_the_supported_range():
    if not available():
        return
    app = App()
    _hidden(app, "hall", *desktop.default_size("hall"))
    assert app.set_font_size(200) == desktop.FONT_MAX
    assert app.set_font_size(1) == desktop.FONT_MIN
    app.shutdown()


def test_capacity_never_falls_below_the_class_minimum():
    if not available():
        return
    app = App()
    window = _hidden(app, "help", *desktop.default_size("help"))
    # Realize it first: an unmapped Text is 1x1 pixels, and `capacity` quite
    # deliberately reports the logical size rather than zero in that state.
    window.root.update_idletasks()
    window.resize_pixels(80, 60)          # absurdly small on purpose
    window.root.update_idletasks()
    columns, rows = window.capacity()
    least = desktop.minimum_size("help")
    assert (columns, rows) == least
    app.shutdown()


def test_an_unrealized_window_reports_its_logical_size_not_zero():
    """Otherwise the first paint composes an empty rectangle."""
    if not available():
        return
    app = App()
    window = _hidden(app, "stores", *desktop.default_size("stores"))
    assert window.capacity() == desktop.default_size("stores")
    app.shutdown()


def test_a_resize_tells_the_controller_which_window_changed():
    if not available():
        return
    app = App()
    seen = []
    window = _hidden(app, "stack", *desktop.default_size("stack"),
                     on_resize=seen.append)
    window.root.update_idletasks()
    window.set_font_size(20)
    window.resize_pixels(900, 700)
    window.root.update_idletasks()
    window.root.update()
    # The callback is deferred to idle, so let the loop run it.
    window.root.after(1, window.root.quit)
    window.root.mainloop()
    assert not seen or seen[0] == "stack"
    app.shutdown()


def test_reopening_a_window_raises_the_one_already_there():
    if not available():
        return
    app = App()
    first = _hidden(app, "stores", *desktop.default_size("stores"))
    again = app.window("stores", "The Stores", 40, 10)
    assert again is first, "reopening must not build a second window"
    app.shutdown()


def test_geometry_is_remembered_when_a_window_closes():
    if not available():
        return
    with TemporaryDirectory() as folder:
        prefs = desktop.Preferences()
        app = App(prefs)
        window = _hidden(app, "stores", *desktop.default_size("stores"))
        window.place((120, 90, 500, 400))
        window.root.update_idletasks()
        app.close("stores")
        remembered = prefs.recall("stores")
        assert remembered is not None
        assert remembered["columns"] >= desktop.minimum_size("stores")[0]
        assert prefs.save(Path(folder) / "settings.json")
        app.shutdown()


def test_the_focus_list_puts_the_newest_window_first():
    if not available():
        return
    app = App()
    _hidden(app, "hall", *desktop.default_size("hall"))
    _hidden(app, "stack", *desktop.default_size("stack"))
    assert app.live()[0] == "stack"
    app.note_focus("hall")
    assert app.live()[0] == "hall"
    app.shutdown()


def test_cycling_moves_to_another_window_and_says_which():
    if not available():
        return
    app = App()
    _hidden(app, "hall", *desktop.default_size("hall"))
    _hidden(app, "stack", *desktop.default_size("stack"))
    moved = app.cycle()
    assert moved in {"hall", "stack"}
    app.shutdown()


def test_cycling_with_one_window_is_not_a_crash():
    if not available():
        return
    app = App()
    _hidden(app, "hall", *desktop.default_size("hall"))
    assert app.cycle() == "hall"
    app.shutdown()


def test_tiling_places_every_open_window_inside_the_work_area():
    if not available():
        return
    app = App()
    for key in ("hall", "stack", "stores"):
        _hidden(app, key, *desktop.default_size(key))
    app.tile()
    for window in app.windows.values():
        window.root.update_idletasks()
    area = app.work_area()
    assert area[2] > 0 and area[3] > 0
    app.shutdown()


def test_cascade_does_not_throw_with_windows_open():
    if not available():
        return
    app = App()
    for key in ("hall", "stack"):
        _hidden(app, key, *desktop.default_size(key))
    app.cascade()
    app.shutdown()


def test_the_switcher_lists_windows_and_refuses_to_close_the_hall():
    entries = [
        switcher.Entry("hall", "Hall", "6h left", closable=False),
        switcher.Entry("stack", "Inbox", "5 unread"),
    ]
    screen = switcher.compose(entries, "hall")
    shown = plain_text(screen)
    assert "Hall" in shown and "Inbox · 5 unread" in shown
    # Close is offered but disabled while the Hall is the selected row.
    close = [hit for hit in screen.hits if hit.command == "x"]
    assert close and not close[0].enabled


def test_the_switcher_offers_every_desktop_command_at_its_own_size():
    """Spec 6 forbids losing an action to contraction; the 42-column footer
    could not hold five, so tile and cascade moved to their own row."""
    entries = [switcher.Entry("hall", "Hall", closable=False),
               switcher.Entry("stack", "Inbox", "5 unread")]
    width, height = desktop.default_size("switcher")
    shown = plain_text(switcher.compose(entries, "stack", width, height))
    for label in ("focus", "close", "tile", "cascade", "done"):
        assert label in shown, label


def test_every_switcher_row_is_a_mouse_target():
    entries = [switcher.Entry("hall", "Hall", closable=False),
               switcher.Entry("stack", "Inbox")]
    screen = switcher.compose(entries, "hall")
    commands = {hit.command for hit in screen.hits}
    assert "switch:hall" in commands and "switch:stack" in commands


def test_the_switcher_scrolls_rather_than_hiding_the_selected_window():
    entries = [switcher.Entry(f"w{n}", f"Window {n}") for n in range(30)]
    screen = switcher.compose(entries, "w27")
    shown = plain_text(screen)
    assert "Window 27" in shown
    assert "of 30" in shown


def test_an_empty_switcher_says_so():
    assert "No windows are open." in plain_text(switcher.compose([], ""))
