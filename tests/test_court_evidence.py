"""The compact Court never hides the choice behind its controls."""
from __future__ import annotations

import copy

from belief.project import project
from engine.tick import advance
from load import load_campaign
from tui import palace
from tui.grid import plain_text

SEED = 8814402919
SIZES = ((92, 30), (74, 25), (68, 24))


def _case() -> tuple[dict, dict]:
    world = advance(load_campaign("seat", SEED))[0]
    belief = project(world)
    return belief, belief["justice"]["petitions"][0]


def _prose(screen) -> str:
    return " ".join(
        line.strip().strip("║").strip()
        for line in plain_text(screen).splitlines())


def _verdicts(screen):
    return [hit for hit in screen.hits if hit.command.startswith("verdict:")]


def test_supported_sizes_show_both_sides_and_all_stakes_before_controls() -> None:
    belief, petition = _case()
    for width, height in SIZES:
        screen = palace.compose(
            belief, view="court", selected=petition["id"], hours=8,
            width=width, height=height)
        text = _prose(screen)
        assert petition["claim_text"] in text
        assert petition["counter_text"] in text
        assert "STAKES · copper payment / unrest" in text
        assert "[F] 9,000/-12" in text and "[A] 3,000/+18" in text
        assert len(_verdicts(screen)) == 3
        assert all(hit.enabled for hit in _verdicts(screen))


def test_a_ruling_needs_one_hour() -> None:
    belief, petition = _case()
    screen = palace.compose(
        belief, view="court", selected=petition["id"], hours=0,
        width=74, height=25)
    assert _verdicts(screen) and all(not hit.enabled for hit in _verdicts(screen))


def test_hidden_authored_text_disables_the_buttons() -> None:
    belief, petition = _case()
    belief = copy.deepcopy(belief)
    belief["justice"]["petitions"][0]["claim_text"] = " ".join(
        ["claim"] * 300)
    screen = palace.compose(
        belief, view="court", selected=petition["id"], hours=8,
        width=68, height=24)
    assert _verdicts(screen) and all(not hit.enabled for hit in _verdicts(screen))
