"""A verdict is never offered over testimony the Court has hidden."""
from __future__ import annotations

import copy

from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tui import palace
from tui.grid import plain_text


SEED = 8814402919
SIZES = ((92, 30), (68, 24))


def _heard_case() -> tuple[dict, dict]:
    world = load_campaign("seat", SEED)
    world, _ = advance(world)
    petition_id = project(world)["justice"]["petitions"][0]["id"]
    world, _ = apply(world, A.HearPetition(petition_id))
    belief = project(world)
    petition = next(
        item for item in belief["justice"]["petitions"]
        if item["id"] == petition_id)
    return belief, petition


def _prose(screen) -> str:
    """Join pane text without inserting the box border between wrapped rows."""
    return " ".join(
        line.strip().strip("║").strip()
        for line in plain_text(screen).splitlines())


def _verdict_hits(screen):
    return [
        hit for hit in screen.hits
        if hit.command.startswith("verdict:")
    ]


def test_supported_court_sizes_show_both_sides_before_enabling_verdicts() -> None:
    belief, petition = _heard_case()
    for width, height in SIZES:
        screen = palace.compose(
            belief, view="court", selected=petition["id"], hours=8,
            width=width, height=height)
        text = _prose(screen)
        assert petition["claim_text"] in text
        assert petition["counter_text"] in text
        assert "CLAIM ·" in text and "ANSWER ·" in text
        verdicts = _verdict_hits(screen)
        assert len(verdicts) == len(palace.VERDICTS)
        assert all(hit.enabled for hit in verdicts)


def test_heard_testimony_displaces_room_art_before_it_displaces_evidence() -> None:
    belief, petition = _heard_case()
    compact = plain_text(palace.compose(
        belief, view="court", selected=petition["id"], hours=8,
        width=68, height=24))
    assert "AUDIENCE ·" not in compact
    assert "CLAIM ·" in compact and "ANSWER ·" in compact


def test_exceptionally_long_hidden_evidence_disables_every_verdict() -> None:
    belief, petition = _heard_case()
    belief = copy.deepcopy(belief)
    selected = next(
        item for item in belief["justice"]["petitions"]
        if item["id"] == petition["id"])
    selected["claim_text"] = " ".join(["claim"] * 300)
    screen = palace.compose(
        belief, view="court", selected=petition["id"], hours=8,
        width=68, height=24)
    verdicts = _verdict_hits(screen)
    assert len(verdicts) == len(palace.VERDICTS)
    assert all(not hit.enabled for hit in verdicts)
