"""The palace desktop: sizes, tiers, placement, and preferences (spec 6, 21).

None of this opens a window. The geometry is integers and the assertions are
about integers, which is the only way these rules get checked on every run
rather than whenever someone happens to drag a window onto a second monitor.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tui import desktop


def test_every_class_default_is_at_least_its_own_minimum():
    for name, cls in desktop.CLASSES.items():
        assert cls.default[0] >= cls.minimum[0], name
        assert cls.default[1] >= cls.minimum[1], name


def test_every_window_default_is_at_least_its_own_minimum():
    for key, spec in desktop.WINDOWS.items():
        assert spec.default[0] >= spec.minimum[0], key
        assert spec.default[1] >= spec.minimum[1], key


def test_a_window_refuses_to_shrink_below_its_minimum_rather_than_clipping():
    least = desktop.minimum_size("hall")
    assert desktop.clamp_size("hall", 10, 10) == least
    # Above the minimum it is left alone: clamping is a floor, not a grid.
    assert desktop.clamp_size("hall", 120, 40) == (120, 40)


def test_an_entity_window_takes_its_size_from_its_kind():
    assert desktop.family("letter:tablet_12") == "letter:"
    assert desktop.family("hall") == "hall"
    assert desktop.default_size("letter:tablet_12") == (50, 20)
    assert desktop.default_size("institution:tablet_house") == (50, 19)


def test_an_unknown_window_is_treated_as_a_document():
    assert desktop.default_size("something_new") == desktop.default_size("letter:")


def test_the_tier_boundaries_are_the_ones_the_specification_names():
    assert desktop.tier(88) == desktop.WIDE
    assert desktop.tier(87) == desktop.STANDARD
    assert desktop.tier(68) == desktop.STANDARD
    assert desktop.tier(67) == desktop.COMPACT
    assert desktop.tier(52) == desktop.COMPACT
    assert desktop.tier(51) == desktop.MINIMUM


def test_the_height_bands_are_the_ones_the_specification_names():
    assert desktop.band(28) == desktop.FULL
    assert desktop.band(27) == desktop.REDUCED
    assert desktop.band(20) == desktop.REDUCED
    assert desktop.band(19) == desktop.BARE


def test_bigger_type_means_fewer_cells_not_a_magnified_picture():
    """The window keeps its rectangle; the grid inside it gets smaller."""
    small = desktop.capacity(800, 600, 8, 16)
    large = desktop.capacity(800, 600, 12, 24)
    assert small == (100, 37)
    assert large == (66, 25)
    assert large[0] < small[0] and large[1] < small[1]


def test_capacity_of_a_zero_sized_cell_is_not_a_crash():
    assert desktop.capacity(800, 600, 0, 0) == (0, 0)


def test_font_size_stays_inside_the_supported_range():
    assert desktop.clamp_font(3) == desktop.FONT_MIN
    assert desktop.clamp_font(99) == desktop.FONT_MAX
    assert desktop.clamp_font(11) == 11


def test_a_window_saved_on_a_monitor_that_is_gone_comes_back_into_view():
    area = (0, 0, 1440, 900)
    restored = desktop.clamp_to_area((3000, 1800, 600, 400), area)
    assert desktop.fits(restored, area)
    assert restored == (840, 500, 600, 400)


def test_a_window_larger_than_the_screen_is_cut_down_to_it():
    area = (0, 0, 800, 600)
    assert desktop.clamp_to_area((-50, -50, 2000, 2000), area) == (0, 0, 800, 600)


def test_clamping_respects_an_area_that_does_not_start_at_the_origin():
    area = (100, 50, 800, 600)
    restored = desktop.clamp_to_area((0, 0, 200, 200), area)
    assert restored == (100, 50, 200, 200)
    assert desktop.fits(restored, area)


def test_tiling_covers_the_area_exactly_and_never_overlaps():
    area = (0, 0, 1440, 900)
    for count in range(1, 10):
        tiles = desktop.tiled(count, area)
        assert len(tiles) == count
        covered = sum(width * height for _x, _y, width, height in tiles)
        assert covered == 1440 * 900, count
        for tile in tiles:
            assert desktop.fits(tile, area)
        for first in range(count):
            for second in range(first + 1, count):
                assert not _overlap(tiles[first], tiles[second]), (count, first)


def test_tiling_nothing_is_nothing():
    assert desktop.tiled(0, (0, 0, 100, 100)) == []


def test_cascade_steps_along_and_stays_on_the_screen():
    area = (0, 0, 1440, 900)
    rects = desktop.cascaded(5, area, (600, 400))
    assert len(rects) == 5
    assert rects[0][:2] == (0, 0)
    assert rects[1][0] > rects[0][0] and rects[1][1] > rects[0][1]
    for rect in rects:
        assert desktop.fits(rect, area)


def test_cascade_wraps_instead_of_walking_off_the_edge():
    area = (0, 0, 400, 300)
    rects = desktop.cascaded(12, area, (300, 200), step=40)
    for rect in rects:
        assert desktop.fits(rect, area)
    assert (0, 0) in [rect[:2] for rect in rects[1:]]


def test_preferences_round_trip():
    with TemporaryDirectory() as folder:
        path = Path(folder) / "settings.json"
        prefs = desktop.Preferences(font_size=14, ascii_only=True)
        prefs.remember("hall", 40, 60, 92, 34)
        assert prefs.save(path)
        again = desktop.Preferences.load(path)
    assert again.font_size == 14
    assert again.ascii_only is True
    assert again.recall("hall") == {"x": 40, "y": 60, "columns": 92, "rows": 34}


def test_a_missing_or_corrupt_settings_file_yields_defaults():
    with TemporaryDirectory() as folder:
        missing = Path(folder) / "nothing.json"
        assert desktop.Preferences.load(missing).font_size == desktop.FONT_DEFAULT
        broken = Path(folder) / "broken.json"
        broken.write_text("{not json at all")
        assert desktop.Preferences.load(broken).font_size == desktop.FONT_DEFAULT
        wrong = Path(folder) / "wrong.json"
        wrong.write_text(json.dumps([1, 2, 3]))
        assert desktop.Preferences.load(wrong).ascii_only is False


def test_old_standalone_room_geometry_compacts_once_but_world_does_not() -> None:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "settings.json"
        path.write_text(json.dumps({
            "geometry": {
                "altar": {"x": 1, "y": 2, "columns": 79, "rows": 32},
                "alu": {"x": 3, "y": 4, "columns": 117, "rows": 37},
                "counsel": {"x": 5, "y": 6, "columns": 64, "rows": 52},
                "world": {"x": 7, "y": 8, "columns": 158, "rows": 32},
            },
        }))
        prefs = desktop.Preferences.load(path)

    assert (prefs.recall("altar")["columns"],
            prefs.recall("altar")["rows"]) == desktop.default_size("altar")
    assert (prefs.recall("alu")["columns"],
            prefs.recall("alu")["rows"]) == desktop.default_size("alu")
    assert (prefs.recall("counsel")["columns"],
            prefs.recall("counsel")["rows"]) == desktop.default_size("counsel")
    assert (prefs.recall("world")["columns"],
            prefs.recall("world")["rows"]) == (158, 32)


def test_a_settings_file_cannot_smuggle_in_an_unsupported_font_size():
    with TemporaryDirectory() as folder:
        path = Path(folder) / "settings.json"
        path.write_text(json.dumps({"font_size": 400}))
        assert desktop.Preferences.load(path).font_size == desktop.FONT_MAX


def test_recalled_geometry_is_never_below_the_class_minimum():
    prefs = desktop.Preferences()
    prefs.remember("hall", 0, 0, 10, 10)
    assert prefs.recall("hall") == {
        "x": 0, "y": 0, "columns": 84, "rows": 26}


def test_recalling_a_window_that_was_never_saved_is_none():
    assert desktop.Preferences().recall("hall") is None
    prefs = desktop.Preferences(geometry={"hall": "nonsense"})
    assert prefs.recall("hall") is None
    assert desktop.Preferences(geometry={"hall": {}}).recall("hall") is None


def _overlap(first, second) -> bool:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
