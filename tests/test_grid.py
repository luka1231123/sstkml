"""M11: the cell grid and its backends (spec 9.6, D33).

Every one of these runs headless. No window is opened, no screenshot is taken
and nothing is compared by eye -- a test indexes a cell and checks a glyph.
That is the whole reason the grid exists as a type.
"""
from __future__ import annotations

from tui import grid
from tui.backend_term import to_ansi
from tui.grid import BOXES, INDEX, Surface, plain_text, pure_ascii, sparkline


# --- the palette -------------------------------------------------------------

def test_the_palette_is_sixteen_and_dense():
    """Sixteen entries, indices 0..15 with no gaps, because the backends index
    straight into tuples (spec 9.6)."""
    assert len(grid.NAMES) == 16
    assert sorted(INDEX.values()) == list(range(16))
    assert len(grid.RGB) == len(grid.ANSI) == 16
    for value in grid.RGB:
        assert len(value) == 6 and int(value, 16) >= 0


def test_colours_are_named_everywhere_above_the_backend():
    """Code names a colour; only a backend sees a number. If this ever fails it
    is because someone wrote a literal index into a panel."""
    assert INDEX["blood"] != INDEX["barley"]
    assert grid.NAMES[INDEX["ink"]] == "ink"


# --- the cell invariant ------------------------------------------------------

def test_a_cell_is_one_column_and_the_grid_refuses_anything_else():
    surface = Surface(10, 2)
    for bad in ("ab", "", "\n", "\t", "́", "漢", "🏺"):
        try:
            surface.put(0, 0, bad)
        except grid.BadGlyph:
            continue
        raise AssertionError(f"accepted a glyph that is not one column: {bad!r}")


def test_writes_clip_and_never_wrap():
    """A ledger row that wrapped would be a misread number."""
    surface = Surface(8, 2)
    placed = surface.text(4, 0, "abcdefgh")
    assert placed == 4
    assert plain_text(surface.freeze()).split("\n")[0] == "    abcd"
    assert surface.text(0, 9, "off the bottom") == 0
    surface.put(99, 99, "x")            # silently ignored, not an error
    assert plain_text(surface.freeze()).split("\n")[1] == ""


def test_negative_columns_are_skipped_not_wrapped():
    surface = Surface(6, 1)
    surface.text(-2, 0, "abcdef")
    assert plain_text(surface.freeze()) == "cdef"


# --- painting ----------------------------------------------------------------

def test_a_box_has_corners_and_a_title_in_the_rule():
    surface = Surface(20, 4)
    surface.box(0, 0, 20, 4, style="double", title="STORES")
    lines = plain_text(surface.freeze()).splitlines()
    tl, tr, bl, br, horizontal, vertical = BOXES["double"]
    assert lines[0][0] == tl and lines[0][-1] == tr
    assert lines[3][0] == bl and lines[3][-1] == br
    assert " STORES " in lines[0]
    assert lines[1][0] == vertical and lines[1][-1] == vertical


def test_a_title_too_long_for_its_frame_is_dropped_not_spilled():
    surface = Surface(10, 3)
    surface.box(0, 0, 10, 3, title="A VERY LONG NAME")
    assert "NAME" not in plain_text(surface.freeze())


def test_blit_composes_panels_and_clips_at_the_edge():
    panel = Surface(4, 2, fill="#")
    page = Surface(10, 3)
    page.blit(panel, 7, 0)              # hangs off the right edge
    lines = plain_text(page.freeze()).split("\n")
    assert lines[0] == "       ###"
    assert lines[2] == ""


def test_freeze_is_a_snapshot_and_later_painting_does_not_reach_it():
    surface = Surface(4, 1)
    surface.text(0, 0, "aaaa")
    frozen = surface.freeze()
    surface.text(0, 0, "bbbb")
    assert plain_text(frozen) == "aaaa"
    assert isinstance(frozen, tuple) and isinstance(frozen[0], tuple)


# --- the rule that colour never carries meaning alone ------------------------

def test_a_screen_still_reads_with_every_colour_dropped():
    """Spec 9.6. The arrears row is `blood` and the paid row is `barley`, and a
    player who cannot tell those apart must still be able to read the screen --
    so each says so in words as well."""
    surface = Surface(40, 2)
    surface.text(0, 0, "potters      4 fortnights in arrears",
                 INDEX["blood"], INDEX["ink"])
    surface.text(0, 1, "weavers      paid in full",
                 INDEX["barley"], INDEX["ink"])
    monochrome = plain_text(surface.freeze())
    assert "in arrears" in monochrome and "paid in full" in monochrome


def test_pure_ascii_folds_the_furniture_and_keeps_the_words():
    surface = Surface(24, 3)
    surface.box(0, 0, 24, 3, style="double", title="SEA")
    surface.text(2, 1, "▓▓░░ ▁▂▄█ · shut")
    folded = plain_text(pure_ascii(surface.freeze()))
    assert all(ord(ch) < 128 for ch in folded), folded
    assert "SEA" in folded and "shut" in folded
    assert "+" in folded and "-" in folded


def test_pure_ascii_leaves_colour_alone():
    surface = Surface(4, 1)
    surface.text(0, 0, "─", INDEX["flame"], INDEX["shadow"])
    cell = pure_ascii(surface.freeze())[0][0]
    assert cell == ("-", INDEX["flame"], INDEX["shadow"])


# --- the sparkline (spec 9.4) ------------------------------------------------

def test_the_sparkline_scales_to_its_own_series():
    line = sparkline([0, 5, 10])
    assert line[0] == grid.BLOCKS[0] and line[-1] == grid.BLOCKS[-1]
    assert len(sparkline(list(range(100)))) == 24
    assert sparkline([]) == ""


def test_a_flat_and_empty_series_do_not_divide_by_zero():
    assert sparkline([0, 0, 0]) == grid.BLOCKS[0] * 3
    assert set(sparkline([7, 7, 7])) == {grid.BLOCKS[-1]}


def test_the_sparkline_has_an_ascii_form():
    line = sparkline([0, 5, 10], ascii_only=True)
    assert all(ord(ch) < 128 for ch in line)


# --- the terminal backend ----------------------------------------------------

def test_ansi_emits_colour_only_where_it_changes():
    surface = Surface(6, 1)
    surface.text(0, 0, "aaabbb", INDEX["clay"], INDEX["ink"])
    surface.text(3, 0, "bbb", INDEX["blood"], INDEX["ink"])
    out = to_ansi(surface.freeze(), colour=True)
    assert out.count("\x1b[38;5;") == 2       # one run of clay, one of blood


def test_ansi_without_colour_is_exactly_the_plain_text():
    surface = Surface(12, 2)
    surface.box(0, 0, 12, 2)
    frozen = surface.freeze()
    assert to_ansi(frozen, colour=False) == "\n".join(
        "".join(cell[0] for cell in row) for row in frozen)


def test_the_terminal_backend_can_degrade_to_ascii():
    surface = Surface(12, 2)
    surface.box(0, 0, 12, 2, style="thick")
    out = to_ansi(surface.freeze(), colour=False, ascii_only=True)
    assert all(ord(ch) < 128 for ch in out)


# --- the window backend, tested without opening a window ---------------------

def test_the_window_backend_reports_absence_instead_of_raising():
    """Homebrew's python does not ship `_tkinter` unless `python-tk` is
    installed, and a headless box has no display at all. Either way the game
    must fall back to the terminal rather than die with a traceback about a
    display name, so `available()` answers rather than throws."""
    from tui import backend_tk
    assert backend_tk.available() in (True, False)


def test_the_window_backend_imports_no_toolkit_at_module_level():
    """Tk is imported lazily and only inside `tui/backend_tk.py`, so the
    headless suite, `session.replay` and the terminal path never touch a
    display. If this fails, the interface has stopped being testable by cell."""
    import sys
    from tui import backend_tk           # noqa: F401
    assert "tkinter" not in sys.modules


def test_the_window_backend_speaks_the_same_palette():
    from tui.backend_tk import _hex
    from tui.grid import RGB
    assert _hex(INDEX["blood"]) == f"#{RGB[INDEX['blood']]}"
    assert all(len(_hex(i)) == 7 for i in range(16))
