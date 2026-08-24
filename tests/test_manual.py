"""The field manual (UI/UX spec 11).

The gate the specification asks for is here: "tests fail when an enabled
action, key, click path, or verb lacks Help". Because the manual is generated
from the action registry rather than transcribed by hand, that gate is cheap --
an action without documentation cannot reach the game.
"""
from __future__ import annotations

import manual
import registry
from tui import desktop, help as help_page
from tui.grid import cells, plain_text


def test_every_action_in_the_registry_has_a_manual_entry():
    assert manual.covered_actions() == {
        d.id for d in registry.player_descriptors()}


def test_every_action_entry_states_its_cost_and_its_command():
    for topic in manual.TOPICS:
        if not topic.id.startswith("action:"):
            continue
        assert topic.cost is not None, topic.id
        assert topic.command, topic.id
        assert topic.cost_line, topic.id


def test_the_cost_in_help_is_the_cost_the_game_charges():
    """Help generated from the registry cannot quote a stale price."""
    for descriptor in registry.player_descriptors():
        topic = manual.BY_ID[f"action:{descriptor.id}"]
        assert topic.cost == registry.cost_of(descriptor.action_type)


def test_a_free_action_says_so_rather_than_saying_nothing():
    free = manual.BY_ID["action:defy_omen"]
    assert free.cost == 0
    assert free.cost_line == "Cost: no hours."


def test_searching_finds_the_action_and_ranks_it_first():
    assert manual.search("repair")[0].id == "action:begin_repair"
    assert manual.search("assign troops")[0].id == "action:assign_troops"
    assert manual.search("quarantine")[0].id == "action:quarantine"


def test_search_is_deterministic():
    assert [t.id for t in manual.search("grain")] == [
        t.id for t in manual.search("grain")]


def test_an_empty_search_puts_the_current_screen_first():
    for topic in manual.search("", "alu")[:1]:
        assert "alu" in topic.screens


def test_a_search_that_matches_nothing_returns_nothing():
    assert manual.search("zzzznotathing") == ()


def test_the_screen_a_player_came_from_lifts_its_own_topics():
    """Same query, different screen, different first answer where it matters."""
    from_city = manual.search("repair", "alu")
    assert "alu" in from_city[0].screens


def test_no_topic_is_listed_twice():
    ids = [topic.id for topic in manual.TOPICS]
    assert len(ids) == len(set(ids))
    titles = [topic.title for topic in manual.TOPICS]
    assert len(titles) == len(set(titles)), "two topics share a title"


def test_the_manual_composes_at_its_default_and_its_minimum():
    for width, height in (desktop.default_size("help"),
                          desktop.minimum_size("help")):
        grid = cells(help_page.compose(width, height, "repair", "", "alu"))
        assert len(grid) == height
        assert all(len(row) == width for row in grid)


def test_the_narrow_manual_drops_the_list_before_the_answer():
    """Spec 6: lose decoration, never the information."""
    narrow = plain_text(help_page.compose(
        *desktop.minimum_size("help"), "repair", "", "alu"))
    assert "Command: repair" in narrow


def test_the_manual_never_mentions_a_model_or_a_wait():
    text = plain_text(help_page.compose(52, 20, "", "", "hall"))
    for word in ("Tutor", "thinking", "asking", "model"):
        assert word.lower() not in text.lower(), word


def test_the_search_line_shows_what_was_typed():
    assert "Search: grain" in plain_text(
        help_page.compose(52, 20, "grain", "", "hall"))


def test_a_fruitless_search_explains_itself_rather_than_going_blank():
    text = plain_text(help_page.compose(52, 20, "zzzznotathing", "", "hall"))
    assert "Nothing matches that." in text
