"""M4 numeric guard: model prose may repeat prompted numbers and no others."""
from ai.numeric_guard import guard, normalise


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
