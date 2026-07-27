"""The conversational Help window and its command retrieval corpus."""
from __future__ import annotations

from ai import help_agent, parser
from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import hall, help as help_page
from tui.grid import plain_text

SEED = 8814402919


def _world(turns: int = 8):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _belief() -> dict:
    return project(_world())


def test_the_corpus_covers_every_legal_parser_command_exactly() -> None:
    ids = [doc.id for doc in help_agent.DOCS]
    assert len(ids) == len(set(ids))
    assert help_agent.covered_verbs() == parser.VERBS


def test_the_corpus_knows_every_built_hall_door() -> None:
    built_keys = {key.casefold() for key, _label, target in hall.DOORS
                  if target in hall.BUILT}
    assert built_keys <= help_agent.covered_keys()


def test_retrieval_finds_the_command_and_not_merely_the_shared_verb() -> None:
    assert help_agent.retrieve(
        "How do I send the chariotry on campaign?")[0].doc.id == "assign_troops"
    assert help_agent.retrieve(
        "Can I repair the broken tablet house?")[0].doc.id == "repair"
    assert help_agent.retrieve(
        "Where do I read an unread tablet?")[0].doc.id in {"read", "inbox"}


def test_offline_help_gives_exact_grounded_instructions() -> None:
    question = "How do I send the chariotry on campaign?"
    text, source, hits = help_agent.speak(
        question, [], _belief(), SEED, 8, client=None)
    assert source == "fallback"
    assert hits[0].doc.id == "assign_troops"
    assert "assign chariotry to campaign at carchemish" in text
    assert "one hour" in text


def test_a_short_follow_up_retrieves_against_the_previous_question() -> None:
    said = [
        ("player", "How do I send the chariotry on campaign?"),
        ("tutor", "Assign the formation to campaign at a place."),
    ]
    text, _source, hits = help_agent.speak(
        "And what does that cost?", said, _belief(), SEED, 8, client=None)
    assert hits[0].doc.id == "assign_troops"
    assert "one hour" in text


def test_the_model_sees_only_retrieved_command_passages() -> None:
    hits = help_agent.retrieve("How do I repair the tablet house?", limit=2)
    prompt = help_agent.build_prompt(
        "How do I repair the tablet house?", [], hits, _belief())
    text = "\n".join(message["content"] for message in prompt)
    assert "[repair]" in text
    assert "CURRENT VALID NAMES" in text
    assert "[allocate]" not in text


def test_the_optional_model_phrases_the_retrieved_answer() -> None:
    class Client:
        def __init__(self):
            self.messages = None

        def call(self, role, messages, schema, seed, max_tokens, timeout, turn):
            self.messages = messages
            assert role == "help"
            return "Use repair <institution> in Counsel."

    client = Client()
    text, source, hits = help_agent.speak(
        "How do I repair an institution?", [], _belief(), SEED, 8, client)
    assert source == "model"
    assert hits[0].doc.id == "repair"
    assert text == "Use repair <institution> in Counsel."
    assert "[repair]" in client.messages[1]["content"]


def test_the_help_window_is_clickable_and_always_ready() -> None:
    view = help_page.compose(
        said=[("player", "How do I repair a building?"),
              ("tutor", "Tell Counsel to repair the named institution.")],
        typed="repair")
    text = plain_text(view)
    assert "Tutor:" in text and "repair█" in text
    commands = {hit.command for hit in view.hits if hit.enabled}
    assert {"Return", "Control-u", "Escape", "F1", "F2", "F3"} <= commands


def test_asking_help_changes_neither_hours_nor_the_action_log() -> None:
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = _world()
    game.hours = project(game.world)["attention"]
    game.log = []
    game.help_said = []
    game.help_typed = ""
    game.help_typing = True
    game.help_sources = ()
    game.client = None
    game.repaint = lambda: None
    before_hours = game.hours

    game.submit_help("How do I repair the tablet house?")

    assert game.hours == before_hours
    assert game.log == []
    assert game.help_said[-1][0] == "tutor"
    assert game.help_sources[0] == "repair"
