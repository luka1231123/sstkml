"""The lightweight court model is a product requirement, not an opt-in."""
from __future__ import annotations

import json
import inspect
import os
from types import SimpleNamespace
from unittest.mock import patch

from ai import client
from ai.composer import MatterCorrection
from tui import composer


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_the_supported_lightweight_model_is_the_default() -> None:
    assert client.MODEL == "qwen3:4b-instruct"


def test_model_status_requires_the_configured_model() -> None:
    payload = {"models": [{"name": "qwen3:4b-instruct"}]}
    with patch.dict(os.environ, {}, clear=False), patch(
            "urllib.request.urlopen", return_value=_Response(payload)):
        ready, detail = client.model_status()
    assert ready and "qwen3:4b-instruct" in detail

    payload = {"models": [{"name": "some-other-model:latest"}]}
    with patch("urllib.request.urlopen", return_value=_Response(payload)):
        ready, detail = client.model_status()
    assert not ready and "not installed" in detail


def test_existing_14b_install_is_an_immediate_compatibility_model() -> None:
    payload = {"models": [
        {"name": "qwen3:4b"},
        {"name": "qwen3:14b"},
    ]}
    with patch.dict(os.environ, {}, clear=False), patch(
            "urllib.request.urlopen", return_value=_Response(payload)):
        ready, detail = client.model_status()
    assert ready
    assert "qwen3:14b is ready as a compatibility model" in detail


def test_missing_service_explains_how_to_install_the_court_voice() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        ready, detail = client.model_status()
    assert not ready
    message = client.required_model_message(detail)
    assert "ollama pull qwen3:4b-instruct" in message
    assert "scribes" in message and "advisers" in message


def test_windowed_game_no_longer_has_an_ai_off_switch() -> None:
    import play_gui
    source = inspect.getsource(play_gui.Game.__init__)
    assert "STK_NO_AI" not in source


def test_desk_requests_only_a_correction_of_the_kings_matter() -> None:
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = 7
    game.world = SimpleNamespace(date=SimpleNamespace(absolute=4))
    game.client = object()
    game.repaint = lambda: None
    game.notify = lambda *_args, **_kwargs: None
    matter = "I cannot send sixty men. The ships must guard Ugarit."
    blocks = composer.default_blocks()
    game.desk = {
        "letter_id": "T-1", "intent": "reply", "dictating": False,
        "dictated": False, "generation": 0, "composing": False,
        "matter": matter, "buffer": matter, "blocks": blocks,
        "draft": composer.assemble("hatti_king", blocks, matter),
    }
    game._run_model = lambda work, done: done(work(), None)
    corrected = MatterCorrection(
        "I cannot send sixty men. Ugarit's ships must keep guard.", "model")

    with patch.object(
            play_gui.ai_composer, "correct_matter",
            return_value=corrected) as call:
        game._request_desk_draft({
            "id": "T-1", "sender": "hatti_king",
            "facts": {"troops": 999},
        })

    assert game.desk["draft"].source == "model"
    assert game.desk["matter"] == corrected.text
    assert game.desk["advisor_origin"] == matter
    assert "999" not in game.desk["draft"].text
    assert not game.desk["composing"]
    assert call.call_args.args[1] == matter


def test_cached_model_voice_is_attached_to_belief_without_mutating_facts() -> None:
    import play_gui

    class Voice:
        def body(self, _item):
            return "The king's guarded living voice.", "model"

    game = play_gui.Game.__new__(play_gui.Game)
    game.voicer = Voice()
    original = {"stack": [{"id": "T-1", "facts": {"grain": 60}}]}
    enriched = game._language_belief(original)

    assert enriched["stack"][0]["body_source"] == "model"
    assert enriched["stack"][0]["body"] == "The king's guarded living voice."
    assert "body" not in original["stack"][0]
    assert enriched["stack"][0]["facts"] == {"grain": 60}
