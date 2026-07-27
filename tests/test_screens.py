"""Reading a screen as text (`tools/screens.py`).

The tool exists so a screen can be inspected without a display or a camera, and
these check the two properties that make it trustworthy: the text it prints is
the same rectangle the window would paint, and nothing in it is said by colour
alone.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import screens                                          # noqa: E402
from belief.project import project                      # noqa: E402
from tui import document, hall                          # noqa: E402
from tui.grid import Screen, Surface, plain_text        # noqa: E402


def _belief(turns: int = 8) -> dict:
    return project(screens.state(turns=turns))


def test_plain_text_is_one_line_per_row() -> None:
    screen = hall.compose(_belief(), 92, 30)
    lines = plain_text(screen).split("\n")
    assert len(lines) == 30


def test_plain_text_carries_no_escape_codes() -> None:
    """The point of the reader: it prints glyphs, not terminal control."""
    text = screens.show(hall.compose(_belief(), 92, 30))
    assert "\033" not in text


def test_the_hall_names_a_person_and_a_number_in_plain_text() -> None:
    """Colour never carries meaning alone (spec 9.6), so both survive here."""
    text = screens.show(hall.compose(_belief(), 92, 30))
    assert "WAITING ON YOU" in text
    assert "courier" in text
    assert "granary" in text
    assert "hours" in text


def test_every_named_screen_renders() -> None:
    b = _belief()
    for name, (_title, compose) in screens.SCREENS.items():
        text = screens.show(compose(b))
        assert text.strip(), f"{name} came back blank"


def test_reading_the_nth_tablet_returns_that_tablet() -> None:
    """Belief sorts the stack read-last, so the index must not be reused."""
    world = screens.state(turns=8)
    before = project(world)["stack"][2]["id"]
    world, letter_id = screens.read_nth(world, 2)
    assert letter_id == before
    item = next(i for i in project(world)["stack"] if i["id"] == letter_id)
    assert item["read"]


def test_a_tablet_reads_as_a_letter() -> None:
    world, letter_id = screens.read_nth(screens.state(turns=8), 0)
    b = project(world)
    item = next(i for i in b["stack"] if i["id"] == letter_id)
    text = screens.show(document.tablet(item, house=b.get("house")))
    assert "reached your hand" in text
    assert "[esc] close" in text


def test_nothing_is_written_over_the_frame() -> None:
    """A long summary used to clip at the surface, i.e. onto the right border."""
    world, letter_id = screens.read_nth(screens.state(turns=8), 0)
    b = project(world)
    item = next(i for i in b["stack"] if i["id"] == letter_id)
    for row in document.tablet(item, house=b.get("house"), width=62):
        assert row[0][0] in "╔║╚", "the left border was overwritten"
        assert row[-1][0] in "╗║╝", "the right border was overwritten"


def test_the_ascii_fold_leaves_no_box_drawing() -> None:
    text = screens.show(hall.compose(_belief(), 92, 30), ascii_only=True)
    assert not set(text) & set("╔╗╚╝═║┌┐└┘─│┏┓┗┛━┃▓▇")


def _fake_window(title: str, screen: Screen):
    class W:
        def __init__(self) -> None:
            self.title, self.last = title, screen
            self.root = type("R", (), {"winfo_exists": lambda self: True})()
    return W()


def test_a_transcript_reads_several_windows_at_once() -> None:
    """`App.transcript` without Tk: it may only touch `title` and `last`.

    That is what lets a running game be read from outside, and it must not
    quietly start depending on a live toolkit.
    """
    from tui.backend_tk import App

    app = App()
    small = Surface(12, 2)
    small.text(0, 0, "granary")
    app.windows = {
        "hall": _fake_window("The Hall", small.freeze()),
        "stores": _fake_window("The Stores", small.freeze()),
    }
    text = app.transcript()
    assert "The Hall [hall]" in text
    assert "The Stores [stores]" in text
    assert text.count("granary") == 2
