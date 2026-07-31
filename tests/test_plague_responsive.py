"""Responsive contract for the Sickness and Closures ledger."""
from __future__ import annotations

from belief.project import project
from load import load_scenario
from tui import desktop, plague
from tui.grid import plain_text


SEED = 8_814_402_919


def _belief() -> dict:
    return project(load_scenario("ugarit", SEED))


def _assert_frame_is_intact(text: str, width: int, height: int) -> None:
    rows = text.splitlines()
    assert len(rows) == height
    assert all(len(row) == width for row in rows)
    assert rows[0][0] == "╔" and rows[0][-1] == "╗"
    assert rows[-1][0] == "╚" and rows[-1][-1] == "╝"
    assert all(row[0] == "║" and row[-1] == "║"
               for row in rows[1:-1])


def test_compact_sickness_layout_keeps_complete_dossier_and_controls():
    for label, size in (
        ("compact", (64, 22)),
        ("default", desktop.default_size("plague")),
        ("minimum", desktop.minimum_size("plague")),
    ):
        belief = _belief()
        selected = plague.place_dossiers(belief)[0]["id"]

        view = plague.compose(
            belief, selected_place=selected, width=size[0], height=size[1],
            notice="route order refused",
        )
        text = plain_text(view)

        _assert_frame_is_intact(text, *size)
        assert "SELECTED PLACE DOSSIER" in text, label
        assert "sickness · no current report is held" in text, label
        assert "not a live view" in text, label
        assert "KNOWN PLACES" in text, label
        assert "[q] close" in text, label
        assert "[esc] close" in text, label
        assert "route order refused" in text, label
        assert "│" not in text, "compact layout must not retain the crushed divider"
        assert f"plague:select:{selected}" in {
            hit.command for hit in view.hits if hit.enabled
        }


def test_wide_sickness_layout_retains_two_readable_panes():
    belief = _belief()
    selected = plague.place_dossiers(belief)[-1]["id"]

    view = plague.compose(
        belief, selected_place=selected, width=78, height=28,
        scroll=10_000,
    )
    text = plain_text(view)

    _assert_frame_is_intact(text, 78, 28)
    assert "│" in text
    assert "SELECTED PLACE DOSSIER" in text
    assert "no current report is held" in text
    assert "not a live view" in text
    assert "[q] close" in text
    assert "[esc] close" in text
    assert f"plague:select:{selected}" in {
        hit.command for hit in view.hits if hit.enabled
    }


def test_compact_closed_place_uses_lift_label_without_footer_loss():
    belief = _belief()
    selected = plague.place_dossiers(belief)[0]["id"]
    belief = {
        **belief,
        "plague": {
            **belief["plague"],
            "quarantined": [selected],
        },
    }

    text = plain_text(plague.compose(
        belief, selected_place=selected,
        width=desktop.minimum_size("plague")[0],
        height=desktop.minimum_size("plague")[1],
    ))

    assert "routes ordered closed" in text
    assert "[q] lift" in text
    assert "[esc] close" in text
    _assert_frame_is_intact(text, *desktop.minimum_size("plague"))
