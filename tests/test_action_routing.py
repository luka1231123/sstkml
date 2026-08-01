"""Every order answers in the window it was given in (UI/UX spec 21, phase 1).

The audit's eighth systemic problem was that refusals were silent or reported
only into the Hall, behind whichever window the player was actually looking at.
A key that appears to do nothing is indistinguishable from a key the game does
not have, so these tests assert the outcome lands where the order was given --
and that it says which prerequisite was missing rather than merely failing.
"""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine.tick import advance
from load import load_campaign
from tui import style
from tui.grid import Surface, plain_text, pure_ascii

import registry

SEED = 8814402919


def _world(turns: int = 8):
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _controller(hours: int | None = None):
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = _world()
    game.hours = project(game.world)["attention"] if hours is None else hours
    game.log = []
    game.client = None
    game.repaint = lambda: None
    return game


def test_a_refused_order_returns_why_and_costs_no_hours() -> None:
    game = _controller(hours=0)
    before = game.world

    result = game.do(A.InspectLedger("granary"), window="stores")

    assert result.status == registry.REFUSAL
    assert not result            # falsy, so `if self.do(...)` still reads right
    assert result.missing == "attention"
    assert "0 remain" in result.message
    assert game.hours == 0
    assert game.world is before  # a refusal must not touch the world
    assert game.log == []


def test_the_refusal_lands_in_the_window_that_gave_the_order() -> None:
    game = _controller(hours=0)
    game.do(A.InspectLedger("granary"), window="stores")

    assert "0 remain" in game.notices["stores"]
    assert game.notices["stores"].kind == registry.REFUSAL
    # And the Hall keeps the session's record of it.
    assert game.notices["hall"] == game.notices["stores"]


def test_a_successful_order_reports_success_where_it_was_given() -> None:
    game = _controller()
    result = game.do(A.SetLandDue(250), window="land")

    assert result.ok
    assert result.status == registry.SUCCESS
    assert game.notices["land"].kind == registry.SUCCESS
    assert game.log, "a successful order is logged for replay"


def test_the_result_carries_the_registry_cost_and_the_action_it_names() -> None:
    game = _controller()
    result = game.do(A.InspectLedger("granary"), window="stores")

    descriptor = registry.BY_ID["inspect_ledger"]
    assert result.action_id == "inspect_ledger"
    assert result.cost == descriptor.cost
    assert result.hours_left == game.hours


def test_outcomes_are_marked_by_glyph_not_by_colour_alone() -> None:
    """Spec 6: every colour-coded state also has a glyph or a word."""
    marks = set()
    for kind in ("success", "refusal", "preview", "cancelled", "info"):
        surface = Surface(40, 3)
        style.notice(surface, 1, 1, 38, style.Notice("a thing happened", kind))
        text = plain_text(surface.freeze())
        assert "a thing happened" in text
        marks.add(text.strip()[0])
    # Success and refusal in particular must not share a mark.
    assert len(marks) >= 2

    surface = Surface(40, 3)
    style.notice(surface, 1, 1, 38, style.Notice("refused", "refusal"))
    folded = plain_text(pure_ascii(surface.freeze()))
    assert "refused" in folded
    assert "?" not in folded, "the mark must survive the pure-ASCII fold"


def test_a_notice_is_still_an_ordinary_string() -> None:
    """Screens written against `notice: str` must not need to change."""
    line = style.Notice("that requires 2 hours", registry.REFUSAL)
    assert isinstance(line, str)
    assert line[:4] == "that"
    assert line.kind == registry.REFUSAL
    assert not style.Notice("")


# --- the adviser (UI/UX spec 20) ---------------------------------------------

def test_no_advice_is_ever_unattributed() -> None:
    from tui import advice

    belief = project(_world())
    matters = advice.concerns(belief, 9)
    assert matters, "the fixture must actually raise concerns"
    for concern in matters:
        assert concern.speaker, concern.id
        assert concern.said().startswith(concern.speaker + ":")
        # An imperative in the palace's own voice is the thing being removed.
        assert not concern.said().startswith("Do:")


def test_advice_says_what_it_rests_on() -> None:
    from tui import advice

    belief = project(_world())
    for concern in advice.concerns(belief, 9):
        assert concern.basis, concern.id


def test_a_vacant_post_speaks_through_the_scribe_and_says_so() -> None:
    from tui import advice

    held = {"institutions": [
        {"id": "g", "kind": "granary", "head": "steward_granary", "name": "g"}]}
    empty = {"institutions": [
        {"id": "g", "kind": "granary", "head": "", "name": "g"}]}
    assert advice.speaker_for(held, "granary") == (
        "the steward of the granary", True)
    assert advice.speaker_for(empty, "granary") == (advice.SCRIBE, False)
    # And a kind the city does not have at all is nobody's business but his.
    assert advice.speaker_for(empty, "harbour") == (advice.SCRIBE, False)


def test_the_hall_attributes_every_matter_it_draws() -> None:
    from tui import advice, hall
    from tui.grid import plain_text

    belief = project(_world())
    text = plain_text(hall.compose(belief, 92, 34, hours_left=6))
    assert "Do:" not in text
    drawn = [c for c in advice.concerns(belief, 4)
             if c.title[:20] in text]
    assert drawn, "the fixture must put something on the Hall"
    for concern in drawn:
        assert f"{concern.speaker}:"[:24] in text, concern.id


def test_judgement_matters_route_to_the_court_door() -> None:
    from tui import advice, hall

    belief = project(_world())
    judgement = next(
        concern for concern in advice.concerns(belief, 9)
        if concern.id == "justice")
    assert judgement.destination == "palace"
    assert any(target == judgement.destination
               for _key, _label, target in hall.DOORS)
