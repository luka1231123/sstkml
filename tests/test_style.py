"""The furniture (`tui/style.py`) and the windows built on it.

Every assertion here reads the screen as glyphs, never as colour, which is the
rule that keeps the game playable in monochrome (spec 9.6).
"""
from __future__ import annotations

from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import document, hall, help as help_page, style
from tui.grid import INDEX, Surface, plain_text

SEED = 8814402919


def _belief(turns: int = 8) -> dict:
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return project(world)


# --- the furniture ------------------------------------------------------------

def test_a_keycap_names_the_whole_key() -> None:
    """`[space]`, not `[s]pace`: multi-character keys used to lose their tail."""
    surface = Surface(30, 1)
    written = style.keycap(surface, 0, 0, "space", "end it")
    text = plain_text(surface.freeze())
    assert text.startswith("[space] end it")
    assert written == len("[space] end it")


def test_a_disabled_keycap_is_marked_not_hidden() -> None:
    surface = Surface(30, 1)
    style.keycap(surface, 0, 0, "w", "the world", enabled=False)
    assert plain_text(surface.freeze()).strip() == "[w] the world ·"


def test_a_panel_title_survives_monochrome() -> None:
    """The title bar is a colour field; the words must not be carried by it."""
    surface = Surface(40, 6)
    style.panel(surface, 0, 0, 40, 6, title="THE OATHS", note="[esc] close")
    lines = plain_text(surface.freeze()).split("\n")
    assert "THE OATHS" in lines[0]
    assert lines[0].startswith("╔═") and lines[0].endswith("╗")
    assert "[esc] close" in lines[5]


def test_a_meter_never_rounds_a_sliver_up() -> None:
    surface = Surface(12, 1)
    style.meter(surface, 0, 0, 12, 0)
    assert plain_text(surface.freeze()) == "░" * 12
    style.meter(surface, 0, 0, 12, 12)
    assert plain_text(surface.freeze()) == "▓" * 12


def test_a_shadow_falls_down_and_right() -> None:
    surface = Surface(10, 5)
    style.shadow(surface, 0, 0, 6, 3)
    lines = plain_text(surface.freeze()).split("\n")
    assert lines[1][6] == "░"          # right edge, one row down
    assert lines[3].startswith(" ░░░░░")   # under the panel, one cell in


# --- the hall -----------------------------------------------------------------

def test_the_hall_shows_every_door_it_has() -> None:
    """A door the player cannot open is marked; a vanished one is a lie.

    Every door is built now, so what this guards is the other half: nothing is
    quietly missing from the list, and nothing is marked unbuilt that is not.
    """
    text = plain_text(hall.compose(_belief(), 92, 30))
    for key, label, target in hall.DOORS:
        assert f"[{key}] {label}" in text
        if target in hall.BUILT:
            assert f"[{key}] {label} ·" not in text
    assert "not yet built" not in text


def test_every_built_door_has_a_window_behind_it() -> None:
    import play_gui

    behind = ({key for key, _t, _s, _how in play_gui.TABLETS.values()}
              | {key for key, _t, _s, _h in play_gui.ROOMS.values()}
              | {"desk"})          # reached from a letter, not from a key
    advertised = {target for _k, _l, target in hall.DOORS
                  if target in hall.BUILT}
    assert behind == advertised


def test_the_hall_says_which_keys_end_the_fortnight() -> None:
    text = plain_text(hall.compose(_belief(), 92, 30))
    assert "[SPACE] end the fortnight" in text


# --- the new windows ----------------------------------------------------------

def test_the_oaths_show_the_figure_the_viceroy_will_exaggerate() -> None:
    """D32: the true obligation is on this page from turn 1, unremarked."""
    text = plain_text(document.oaths(_belief(), 76, 28))
    assert "provide troops" in text
    assert "n 200" in text
    assert "warn" not in text.lower()


def test_the_land_reports_no_yield_and_no_forecast() -> None:
    text = plain_text(document.land(_belief(20), 70, 24))
    assert "the river gauge stands at" in text
    assert "seed in the ground" in text
    assert "expect" not in text.lower() and "forecast" not in text.lower()


def test_the_house_draws_a_tree_without_shearing_the_columns() -> None:
    text = plain_text(document.house(_belief(40), 70, 26))
    rows = [line for line in text.split("\n") if "├─" in line or "└─" in line]
    assert rows, "the ruler has no family drawn under him"
    for row in rows:
        assert row.index("─") < 8, "the branch is not in the name column"


def test_a_quiet_fortnight_says_so_without_reassuring() -> None:
    text = plain_text(document.fortnight(_belief(), [], 66, 18))
    assert "Nothing was reported" in text
    assert "not the same as" in text


def test_a_fortnight_reports_what_happened_and_not_what_it_means() -> None:
    lines = ["  A courier has come. On the pile now: Abdi-milki."]
    text = plain_text(document.fortnight(_belief(), lines, 66, 18))
    assert "A courier has come" in text
    assert "should" not in text.lower()


def test_help_is_a_written_page_and_never_advice() -> None:
    text = plain_text(help_page.compose())
    assert "Reading a tablet costs two" in text
    assert "[s] the stack" in text
    assert "It will not warn you" in text


def test_help_fits_every_line_it_promises() -> None:
    """A truncated instruction is worse than no instruction."""
    text = plain_text(help_page.compose())
    for _title, rows in help_page.PAGES:
        for _key, sentence in rows:
            assert sentence in text, f"cut off: {sentence!r}"


def test_the_palette_is_sixteen_and_no_more() -> None:
    assert len(INDEX) == 16
    assert sorted(INDEX.values()) == list(range(16))
