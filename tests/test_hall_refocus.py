"""Focused contracts for the Hall's palace hierarchy and contraction."""
from __future__ import annotations

from belief.project import project
from engine.tick import advance
from load import load_campaign
from tui import desktop, hall
from tui.grid import plain_text


SEED = 8814402919


def _belief(turns: int = 8) -> dict:
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return project(world)


def test_hall_reads_as_palace_threshold_not_unframed_dashboard() -> None:
    text = plain_text(hall.compose(_belief(), 92, 34))
    assert "◢▄◣▀◤▄◥▀" in text
    assert "╲▟█▙╱" in text
    assert "▚·▩▤" in text
    assert "MATTERS BEFORE THE KING" in text
    assert "AUDIENCE FLOOR" in text
    assert "╞ KINGDOM" in text and "╞ COURT" in text


def test_minimum_hall_keeps_every_palace_door_visible_and_clickable() -> None:
    width, height = desktop.minimum_size("hall")
    view = hall.compose(_belief(), width, height)
    text = plain_text(view)
    commands = {hit.command for hit in view.hits if hit.enabled}
    for key, label, target in hall.DOORS:
        assert f"[{key}]" in text
        assert label in text
        if target in hall.BUILT:
            assert key in commands
    assert "wait beyond the doors" in text


def test_minimum_hall_keeps_the_carved_palace_column() -> None:
    width, height = desktop.minimum_size("hall")
    text = plain_text(hall.compose(_belief(), width, height))
    assert width == 84
    assert "╲▟█▙╱" in text
    assert "╔╩█╩╗" in text
    assert "▟███▙" in text


def test_minimum_header_keeps_the_turns_three_primary_signals_separate() -> None:
    b = _belief()
    width, height = desktop.minimum_size("hall")
    lines = plain_text(hall.compose(b, width, height)).splitlines()
    assert f"{b['attention']} of {b['attention_base']} hours" in lines[2]
    assert "the sea is " in lines[2]
    assert "granary " in lines[3]
    assert "unrest " in lines[3]
    assert "legitimacy " in lines[3]


def test_audience_row_shows_both_wait_and_business_when_space_allows() -> None:
    b = _belief()
    first = hall.waiting(b)[0]
    text = plain_text(hall.compose(b, 120, 36))
    assert first["fact"] in text
    assert first["for"] in text


def test_lintel_ornament_ends_cleanly_without_truncation_ellipsis() -> None:
    width, height = desktop.minimum_size("hall")
    lines = plain_text(hall.compose(_belief(), width, height)).splitlines()
    lintels = [line for line in lines if "╞ " in line]
    assert len(lintels) == len(hall.GROUPS)
    assert all("…" not in line.split("╞ ", 1)[1] for line in lintels)
