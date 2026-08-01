"""The Altar's ritual furniture must yield to its controls when resized."""
from __future__ import annotations

from belief.project import project
from engine.tick import advance
from load import load_campaign
from tui import altar, desktop
from tui.grid import plain_text

SEED = 8814402919
ART_GLYPHS = set("█▓▒░▟▙▐▌▀▄▲")
COMMANDS = {"h", "d", "r", "[", "]", "1", "2", "3", "Return"}


def _belief() -> dict:
    world = load_campaign("seat", SEED)
    for _ in range(8):
        world, _ = advance(world)
    return project(world)


def _death_altar(size: tuple[int, int]):
    belief = _belief()
    subject = next(
        person["id"]
        for person in belief["house"]["members"]
        if person["alive"]
    )
    return altar.compose(
        belief,
        ["He reads the liver and says: the year will be poor."],
        chosen="death",
        offering=("oil", 20),
        width=size[0],
        height=size[1],
        subject=subject,
    )


def test_altar_art_stays_above_controls_at_default_and_minimum() -> None:
    for size in (
        desktop.default_size("altar"),
        desktop.minimum_size("altar"),
    ):
        screen = _death_altar(size)
        lines = plain_text(screen).splitlines()
        controls_top = size[1] - 10
        for row in lines[controls_top:size[1] - 1]:
            assert not ART_GLYPHS.intersection(row[2:-2]), (size, row)


def test_minimum_shrine_keeps_a_substantial_altar_vignette() -> None:
    size = desktop.minimum_size("altar")
    screen = _death_altar(size)
    lines = plain_text(screen).splitlines()
    controls_top = size[1] - 10
    art_rows = [
        row for row in lines[2:controls_top]
        if ART_GLYPHS.intersection(row[2:-2])
    ]

    # Four rows was the emergency thumbnail used by the cramped 18-row
    # window. The declared minimum must reach the nine-row altar composition.
    assert size[1] >= 22
    assert len(art_rows) >= 9
    assert "the diviner" in "\n".join(lines[:controls_top])


def test_altar_controls_remain_legible_and_clickable_when_compact() -> None:
    for size in (
        desktop.default_size("altar"),
        desktop.minimum_size("altar"),
    ):
        screen = _death_altar(size)
        text = plain_text(screen)
        for label in (
            "of the harvest",
            "of the death",
            "of the road and the sea",
            "previous",
            "next",
            "20 oil",
            "20 wine",
            "200 grain",
            "[enter] ask",
        ):
            assert label in text, (size, label)

        enabled = {
            hit.command: hit
            for hit in screen.hits
            if hit.enabled and hit.command in COMMANDS
        }
        assert enabled.keys() == COMMANDS
        for command, hit in enabled.items():
            assert screen.command_at(hit.x, hit.y) == command
            visible = text.splitlines()[hit.y][hit.x:hit.x + hit.width]
            assert visible.strip(), (size, command)
