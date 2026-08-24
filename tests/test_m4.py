"""M4 guard/parser: model output is optional, closed, and number-safe."""
import json

from ai.client import ModelUnavailable
from ai.numeric_guard import guard, normalise
from ai.parser import parse, preparse
from belief.project import project
from engine import actions as A
from engine.tick import advance
from load import load_campaign


def test_digit_and_word_forms_share_a_value():
    assert guard("Twenty ships; 20 were counted.", {"20"}) == (True, [])
    assert guard("A hundred men and one thousand jars.", {"100", "1000"}) == (True, [])


def test_stray_numbers_are_named():
    assert guard("I sent 4 ships, but perhaps five arrived.", {"4"}) == (False, ["five"])
    assert guard("This is my third letter.", {"2"}) == (False, ["third"])


def test_sexagesimal_and_grouped_digits():
    assert normalise("1;20") == "80"
    assert guard("The tablet records 1;20 qa and 1,200 more.", {"80", "1200"}) == (True, [])
    assert guard("The tablet records 2:30 qa.", {"80"}) == (False, ["2:30"])


def test_authored_formula_numbers_can_be_allowed():
    text = "At my lord's feet, seven times and seven times I fall."
    assert guard(text, {"seven"}) == (True, [])


class _Client:
    def __init__(self, response=None, unavailable=False):
        self.response = response
        self.unavailable = unavailable

    def call(self, *args):
        if self.unavailable:
            raise ModelUnavailable("offline")
        return json.dumps(self.response)


def _belief():
    return project(load_campaign("seat", 8814402919))


def test_preparser_handles_high_confidence_prose():
    result = preparse("give smiths_palace 8400 qa", _belief())
    assert result.actions == (A.Allocate("smiths_palace", 8400),)
    assert result.source == "preparser"

    world = load_campaign("seat", 8814402919)
    while not world.inbox:
        world, _ = advance(world)
    result = preparse(
        "reply i excuse the closed sea and promise attention", project(world))
    assert result.actions[0].intent == "excuse the closed sea and promise attention"


def test_parser_accepts_only_current_ids():
    valid = {"kind": "actions", "actions": [
        {"verb": "ALLOCATE", "args": {"group": "smiths_palace", "qa": 8400}},
    ]}
    result = parse("see that smiths_palace receive 8400", _belief(), 6, 1, 1, _Client(valid))
    assert result.actions == (A.Allocate("smiths_palace", 8400),)

    invented = {"kind": "actions", "actions": [
        {"verb": "ALLOCATE", "args": {"group": "invented_group", "qa": 8400}},
    ]}
    result = parse("give somebody 8400", _belief(), 6, 1, 1, _Client(invented))
    assert result.question and not result.actions


def test_parser_rejects_model_invented_numbers_and_survives_offline():
    invented = {"kind": "actions", "actions": [
        {"verb": "ALLOCATE", "args": {"group": "ghosts", "qa": 999}},
    ]}
    result = parse("use some seed", _belief(), 6, 1, 1, _Client(invented))
    assert result.question and not result.actions
    assert parse("do something subtle", _belief(), 6, 1, 1,
                 _Client(unavailable=True)).unavailable
