"""The Court scene is state, not a repeated palace illustration.

These tests stay on the headless cell grid. They distinguish the complete
records below the room from the people physically present on its floor, and
guard the compact Audience/Household/Envoys/Offices arrangements.
"""
from __future__ import annotations

import copy

from tui import art, palace
from tui.grid import INDEX, plain_text


def _belief() -> dict:
    return {
        "seat": "seat",
        "attention": 8,
        "justice": {"petitions": [
            {
                "id": "boundary", "kind": "boundary",
                "petitioner": "farmer", "against": "herdsman",
                "waiting": 3, "good": "grain", "present": True,
                "claim_text": "The stone was moved in the night.",
                "counter_text": "The old channel has always run there.",
            },
            {
                "id": "debt", "kind": "debt",
                "petitioner": "merchant", "against": "scribe",
                "waiting": 1, "good": "copper", "present": False,
                "claim_text": "The silver was weighed before witnesses.",
                "counter_text": "The tablet records barley, not silver.",
            },
        ]},
        "house": {
            "ruler": "king",
            "members": [
                {
                    "id": "king", "name": "The king", "alive": True,
                    "age_years": 40, "location": "seat",
                },
                {
                    "id": "sister", "name": "The king's sister",
                    "alive": True, "age_years": 36, "location": "seat",
                    "competence": "capable", "health": "well",
                    "loyalty": "warm", "post": "", "agenda": "keep the peace",
                    "interests": ["temple"], "named_heir": False,
                    "heir_rank": None, "expecting": False,
                },
                {
                    "id": "brother", "name": "The king's brother",
                    "alive": True, "age_years": 34, "location": "ma_hadu",
                    "competence": "ordinary", "health": "well",
                    "loyalty": "formal", "post": "harbour",
                    "agenda": "hold the harbour", "interests": ["ships"],
                    "named_heir": False, "heir_rank": 1, "expecting": False,
                },
            ],
            "omens": [],
        },
        "institutions": [
            {"id": "granary", "name": "the great granary",
             "kind": "granary", "head": "steward"},
            {"id": "tablet_house", "name": "the tablet house",
             "kind": "archive", "head": ""},
        ],
        "relations": [
            {
                "other": "hatti", "place": "hattusa", "esteem": "formal",
                "unanswered": 1, "obligation": -3000,
                "status_claim": "servant", "their_status_claim": "servant",
                "last_gift_from_us": 0, "last_gift_from_them": 0,
                "best_known_rival_gift": 5000,
                "envoy_present": False,
            },
            {
                "other": "alashiya", "place": "alashiya", "esteem": "warm",
                "unanswered": 0, "obligation": 0,
                "status_claim": "brother", "their_status_claim": "brother",
                "last_gift_from_us": 100, "last_gift_from_them": 100,
                "best_known_rival_gift": 0,
                "envoy_present": True,
            },
        ],
        "revenue": {"harbour_rate": 100},
    }


def _hit_count(screen, command: str) -> int:
    return sum(hit.command == command for hit in screen.hits)


def test_only_people_at_court_get_a_body_on_the_floor() -> None:
    b = _belief()
    present = palace.compose(
        b, view="house", selected="sister", width=98, height=36)
    away = palace.compose(
        b, view="house", selected="brother", width=98, height=36)

    # One hit belongs to the record row; a second belongs to a physical figure.
    assert _hit_count(present, "pick:sister") == 2
    assert _hit_count(present, "pick:brother") == 1
    assert "CHOSEN: AWAY" not in plain_text(present)
    assert "CHOSEN: AWAY" in plain_text(away)


def test_selection_moves_the_marker_under_the_selected_figure() -> None:
    b = _belief()
    b["house"]["members"][2]["location"] = "seat"
    first = palace.compose(
        b, view="house", selected="sister", width=98, height=36)
    second = palace.compose(
        b, view="house", selected="brother", width=98, height=36)

    marker_y = 3 + palace.scene_rows(36) - 1
    flame = INDEX["flame"]
    first_marks = {x for x, cell in enumerate(first[marker_y])
                   if cell[0] == "▀" and cell[1] == flame}
    second_marks = {x for x, cell in enumerate(second[marker_y])
                    if cell[0] == "▀" and cell[1] == flame}
    assert first_marks and second_marks and first_marks != second_marks


def test_vacant_and_held_offices_are_visible_without_extra_furniture() -> None:
    b = _belief()
    screen = palace.compose(
        b, view="house", choosing="post", person="sister",
        selected="tablet_house", width=98, height=36)
    text = plain_text(screen)

    assert "vacant" in text and "steward" in text
    assert "reported output now" in text
    assert "│  □  │" not in text and "│  ■  │" not in text
    assert _hit_count(screen, "pick:tablet_house") == 1
    assert _hit_count(screen, "pick:granary") == 1


def test_correspondence_does_not_conjure_a_distant_envoy() -> None:
    b = _belief()
    screen = palace.compose(
        b, view="relations", selected="hatti", width=98, height=36)
    text = plain_text(screen)

    assert "no envoy is in the room." not in text  # Alashiya is present.
    assert _hit_count(screen, "pick:hatti") == 1
    assert _hit_count(screen, "pick:alashiya") == 2
    assert "CHOSEN: AWAY" in text

    none = copy.deepcopy(b)
    none["relations"][1]["envoy_present"] = False
    empty_text = plain_text(palace.compose(
        none, view="relations", width=98, height=36))
    assert "no envoy is in the room." in empty_text


def test_the_living_room_keeps_the_public_compose_shape_at_minimum_size() -> None:
    b = _belief()
    screen = palace.compose(
        b, view="people", selected="sister", scroll=0, hours=8,
        choosing="", person="", amount=0, good="copper", notice="",
        width=68, height=24)
    assert len(screen) == 24
    assert all(len(row) == 68 for row in screen)
    assert "[o]" in plain_text(screen)
