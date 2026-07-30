"""Refocused Tablet House: dense arrivals, voiced clay, and living shelves."""
from __future__ import annotations

from tui import archive, inbox
from tui.grid import plain_text


def _letter(**changes) -> dict:
    item = {
        "id": "T-1",
        "sender": "hatti_king",
        "topic": "summons",
        "received_turn": 8,
        "age": 3,
        "freshness": "○",
        "read": True,
        "facts": {"troops": 60},
        "answered_turn": None,
        "archived": False,
        "delegated_to": None,
        "delegated_turn": None,
        "sender_status": "overlord",
        "body": "Model-voiced words impressed on this particular clay.",
        "body_source": "model",
    }
    item.update(changes)
    return item


def _belief(letter: dict) -> dict:
    return {
        "attention": 8,
        "stack": [letter],
        "correspondence_archive": [],
        "outbox": [],
        "house": {},
    }


def test_inbox_uses_the_grounded_model_voice_and_social_metadata() -> None:
    letter = _letter()
    text = plain_text(inbox.compose(
        _belief(letter), selected=letter["id"], filter_name="all"))
    assert "WORDS ON CLAY" in text
    assert "Model-voiced words impressed on this" in text
    assert "clay." in text
    assert "3 fortnights old" in text
    assert "overlord" in text
    assert "1 in this exchange" in text
    assert "╲·╱" in text
    assert "PgUp" not in text and "PgDn" not in text
    assert "[tab] focus tablet" in text


def test_unread_tablet_uses_a_compact_physical_prompt() -> None:
    letter = _letter(read=False, body="")
    text = plain_text(inbox.compose(
        _belief(letter), selected=letter["id"], filter_name="unread"))
    assert "THE TABLET IS UNREAD" in text
    assert "break seal" in text
    assert "2 hours" in text
    assert "Reading it takes two hours of the fortnight." not in text


def test_archive_shelves_encode_quantity_without_owning_half_the_room() -> None:
    belief = {
        "archive_index": {"size": 7, "searched": ["grain", "oath"]},
        "house": {},
    }
    hits = [{
        "ref": "A-7",
        "sender": "hatti_king",
        "dated_as": "the third month",
        "kind": "letter_in",
        "snippet": "The road and the promised men are named.",
    }]
    screen = archive.compose(
        belief, "road", hits,
        "One returned tablet concerns the road.", width=84, height=32)
    text = plain_text(screen)
    assert "7 tablets are shelved here" in text
    assert "▤" * 7 in text
    assert "KEEPER'S COLLATION" in text
    assert "The road and the promised men are named." in text
    assert any(hit.command == "open:A-7" for hit in screen.hits)


def test_delegation_names_the_person_before_the_order_is_given() -> None:
    letter = _letter()
    belief = _belief(letter)
    belief["house"] = {"members": [{
        "id": "yabninu", "name": "Yabninu", "alive": True,
        "location": "ugarit",
    }]}
    text = plain_text(inbox.compose(
        belief, selected=letter["id"], delegate_to="yabninu"))
    assert "[g] to Yabninu" in text
