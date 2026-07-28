"""The deterministic command palette (UI/UX spec 10, 23.1).

The palette's whole claim is that a capable text interface needs no model. So
these tests never touch `ai/`: they assert that every registered action can be
typed, that an unknown word is named rather than guessed at, and that the same
order through the palette produces the same structured action the button does.
"""
from __future__ import annotations

import re

import affordances
import palette
import registry
from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import command
from tui.grid import plain_text

SEED = 8814402919


def _belief(turns: int = 8) -> dict:
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return project(world)


def _example(descriptor: registry.ActionDescriptor, belief: dict,
             line: str) -> str | None:
    """Fill a grammar line with the first legal value for each slot."""
    def fill(match: re.Match) -> str:
        name = match.group(1)
        field = next((f for f in descriptor.fields if f.name == name), None)
        domain = field.domain if field else name
        if domain == "quantity":
            return "10"
        if domain == "text":
            return "grain"
        offers = affordances.completions(domain, "", belief)
        return offers[0] if offers else ""
    filled = re.sub(r"<([a-z_]+)>", fill, line).replace("[", "").replace("]", "")
    return None if "  " in filled or filled.strip() != filled else filled


def test_every_action_in_the_registry_can_be_typed() -> None:
    belief = _belief()
    untypable = []
    for descriptor in registry.DESCRIPTORS:
        line = _example(descriptor, belief, descriptor.grammar[0])
        if line is None:
            continue                       # nothing of this kind exists to name
        result = palette.parse(line, belief)
        if result.status != "ok":
            untypable.append((descriptor.id, line, result.message))
            continue
        if palette.handoff(result):
            continue                       # opens a workflow instead
        if palette.build(result) is None:
            untypable.append((descriptor.id, line, "did not assemble"))
    assert not untypable, untypable


def test_the_grammar_comes_from_the_registry_and_nowhere_else() -> None:
    """A reworded grammar line must not silently stop being parseable."""
    known = {line for descriptor in registry.DESCRIPTORS
             for line in descriptor.grammar}
    for text in palette.LITERAL_VALUES:
        assert text in known, text
    for text in palette.HANDOFF:
        assert text in known, text
    assert {form.text for form in palette.FORMS} == known


def test_an_unknown_verb_is_named_and_alternatives_are_offered() -> None:
    result = palette.parse("frobnicate the granary", _belief())
    assert result.status == "error"
    assert result.unknown == "frobnicate"
    assert "frobnicate" in result.message
    assert result.options, "an error must say what was legal instead"


def test_an_unknown_value_says_which_part_and_what_was_allowed() -> None:
    belief = _belief()
    result = palette.parse("repair the moon", belief)
    assert result.status == "error"
    assert result.missing == "institution"
    assert "moon" in result.message
    assert any(inst["id"] in result.options
               for inst in belief.get("institutions", []))


def test_a_half_typed_order_asks_for_the_next_part() -> None:
    belief = _belief()
    result = palette.parse("assign", belief)
    assert result.status == "incomplete"
    assert result.missing == "formation"
    assert result.options

    result = palette.parse("assign chariotry to", belief)
    assert result.status == "incomplete"
    assert result.missing == "task"
    assert set(result.options) == set(affordances.TROOP_TASKS)


def test_the_palette_never_chooses_between_two_matches() -> None:
    """Spec rule 4. An ambiguous name is refused, not resolved by position."""
    belief = {
        "institutions": [
            {"id": "granary_north", "name": "the north granary",
             "kind": "granary", "head": "", "place": "seat"},
            {"id": "granary_south", "name": "the south granary",
             "kind": "granary", "head": "", "place": "seat"},
        ],
        "relations": [], "seat": "seat", "stack": [], "groups": [],
    }
    result = palette.parse("repair granary", belief)
    assert result.status == "error"
    assert palette.build(result) is None
    assert set(result.options) == {"granary_north", "granary_south"}
    assert "more than one" in result.message


def test_the_palette_can_only_name_what_belief_already_shows() -> None:
    """Typing must not reveal what looking could not."""
    empty = {"institutions": [], "relations": [], "seat": "seat",
             "stack": [], "groups": []}
    result = palette.parse("repair the great granary", empty)
    assert result.status == "error"
    assert palette.build(result) is None


def test_a_complete_order_previews_its_meaning_and_its_cost() -> None:
    belief = _belief()
    result = palette.parse("repair the great granary", belief)
    assert result.ok
    preview = palette.preview(result)
    assert "granary_seat" in preview
    assert "1 hour" in preview
    assert result.cost == registry.BY_ID["begin_repair"].cost


def test_the_typed_path_and_the_button_build_the_same_action() -> None:
    from engine import actions as A

    belief = _belief()
    result = palette.parse("repair the great granary", belief)
    assert palette.build(result) == A.BeginRepair("granary_seat")

    result = palette.parse("quarantine alashiya", belief)
    assert palette.build(result) == A.Quarantine("alashiya", lift=False)
    result = palette.parse("lift quarantine alashiya", belief)
    assert palette.build(result) == A.Quarantine("alashiya", lift=True)


def test_tab_completes_only_when_there_is_one_answer() -> None:
    belief = _belief()
    assert palette.complete("repa", belief) == "repair"
    # Several tasks are legal, so Tab must not pick one.
    assert palette.complete("assign chariotry to ", belief) == \
        "assign chariotry to "


def test_answering_a_tablet_opens_the_desk_rather_than_acting() -> None:
    belief = _belief()
    tablet = belief["stack"][0]["id"]
    result = palette.parse(f"answer {tablet}", belief)
    assert result.ok
    assert palette.handoff(result) == "desk"
    assert result.values["tablet"] == tablet


def test_the_window_shows_the_failure_and_the_legal_alternatives() -> None:
    belief = _belief()
    line = "repair the moon"
    text = plain_text(command.compose(line, palette.parse(line, belief), 6))
    assert line in text
    assert "moon" in text
    assert "try:" in text


def test_the_window_shows_the_preview_and_the_price() -> None:
    belief = _belief()
    line = "repair the great granary"
    text = plain_text(command.compose(line, palette.parse(line, belief), 6))
    assert "granary_seat" in text
    assert "1 hour" in text


def test_the_window_says_when_there_are_not_the_hours() -> None:
    belief = _belief()
    line = "repair the great granary"
    text = plain_text(command.compose(line, palette.parse(line, belief), 0))
    assert "0 remain" in text


def test_a_field_fills_the_engine_field_of_its_own_name() -> None:
    """Arguments are matched by position, and position is not always right.

    `rule <verdict> on <petition>` says the verdict first; `RulePetition` takes
    the petition first. Assembled by position, the order named the petition
    "for" and the verdict "boundary_ashiranu" -- built without complaint and
    refused by the engine, so the one command was unusable and said nothing
    about why. Where an engine field has the same name as a descriptor field,
    that is the one it must fill.
    """
    import dataclasses

    for descriptor in registry.DESCRIPTORS:
        names = registry.argument_names(descriptor)
        engine = {field.name
                  for field in dataclasses.fields(descriptor.action_type)}
        for field in descriptor.fields:
            if field.name in engine:
                assert names[field.name] == field.name, (
                    descriptor.id, field.name, names[field.name])


def test_a_verdict_is_given_on_the_petition_it_names() -> None:
    belief = _belief()
    petition = belief["justice"]["petitions"][0]["id"]
    built = palette.build(palette.parse(f"rule for on {petition}", belief))
    assert built is not None
    assert built.petition_id == petition
    assert built.verdict == "for"
