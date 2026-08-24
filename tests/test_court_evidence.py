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
SIZES = ((92, 30), (74, 25), (68, 24))


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
        assert text.index(petition["counter_text"]) < text.index(
            "[f] for the petitioner")
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


def test_court_only_shows_the_controls_for_the_current_step() -> None:
    belief, petition = _heard_case()
    heard = palace.compose(
        belief, view="court", selected=petition["id"], hours=8,
        width=68, height=24)
    text = plain_text(heard)
    commands = {hit.command for hit in heard.hits}

    assert "take them in" not in text and "turn them away" not in text
    assert "already heard" not in text and "[h] Hear" not in text
    assert {f"verdict:{verdict}" for _key, verdict, _label in palace.VERDICTS} \
        <= commands


def test_verdict_controls_wait_until_both_sides_are_heard() -> None:
    belief, petition = _heard_case()
    unheard = copy.deepcopy(belief)
    selected = next(
        item for item in unheard["justice"]["petitions"]
        if item["id"] == petition["id"])
    selected["heard"] = False
    selected["claim_text"] = ""
    selected["counter_text"] = ""

    screen = palace.compose(
        unheard, view="court", selected=petition["id"], hours=8,
        width=68, height=24)
    text = plain_text(screen)
    assert "[h] Hear" in text
    assert not _verdict_hits(screen)
    assert "take them in" not in text and "turn them away" not in text


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
