"""M7 Voicer: report bias, persona cards, the prompt boundary, and scheduling."""
from __future__ import annotations

import dataclasses
import re
import threading
import time

from ai import voicer as V
from ai.client import (FORBIDDEN_KEYS, ModelUnavailable, PromptLeak,
                       safe_fields)
from ai.composer import compose
from ai.numeric_guard import guard
from ai.parser import parse
from belief.project import project
from engine import report
from engine.core import state_hash
from engine.tick import advance
from load import load_scenario
from session import replay, save

SEED = 8814402919


def _run(turns: int, seed: int = SEED, scenario: str = "ugarit"):
    world = load_scenario(scenario, seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _letters_from(world, sender: str):
    return [L for L in world.inbox if L.sender == sender]


# --- the sender's lie (spec 6.8) ---------------------------------------------

def test_report_bias_distorts_at_the_source_in_the_direction_of_interest():
    world = _run(14)
    letters = _letters_from(world, "alashiya_gov")
    assert letters, "the governor of Alashiya writes on a 3-turn cadence"
    for L in letters:
        asserted, true = dict(L.facts), dict(L.true_facts)
        assert true, "a biased sender must retain what was actually the case"
        # He is frightened and wants troops: the fleet grows, the garrison shrinks.
        assert asserted["ships"] > true["ships"] == 12
        assert asserted["men"] < true["men"] == 30


def test_an_honest_correspondent_asserts_the_truth():
    world = _run(20)
    # Emar's overseer serves the ruler and has report_bias 0.
    for L in _letters_from(world, "emar_overseer"):
        assert L.true_facts == (), "no bias means nothing to remember"
        assert dict(L.facts)["ships"] == 0
    # Gubla is frantic but nearly accurate -- the control case of spec 6.8.
    assert world.relations["byblos_king"].report_bias < 200
    for L in _letters_from(world, "byblos_king"):
        true = dict(L.true_facts) or dict(L.facts)
        assert dict(L.facts)["towns_taken"] - true["towns_taken"] <= 1


def test_bias_is_deterministic_but_not_a_constant_multiplier():
    a, b = _run(14), _run(14)
    assert [L.facts for L in a.inbox] == [L.facts for L in b.inbox]

    # Same true value, same sender, different turns -> the ratio must move, or
    # the player learns one correction factor and the system stops being a
    # judgement about a source.
    ratios = {
        report.assert_value(12, 2200, +1, SEED, turn, "alashiya_gov", "ships")
        for turn in range(40)
    }
    assert len(ratios) > 3, "a constant multiplier would be learnable in three letters"


def test_bias_directions_and_edges():
    assert report.assert_value(12, 0, +1, SEED, 3, "x", "k") == 12      # honest
    assert report.assert_value(12, 2200, 0, SEED, 3, "x", "k") == 12    # no motive
    assert report.assert_value(0, 2200, +1, SEED, 3, "x", "k") == 0     # nothing to inflate
    assert report.assert_value(30, 2200, -1, SEED, 3, "x", "k") < 30
    assert report.assert_value(1, 3000, -1, SEED, 3, "x", "k") >= 1     # never vanishes
    # Non-numeric facts pass through untouched; booleans are not integers here.
    out = dict(report.assert_facts(
        (("enemy", "the Lukka"), ("seen", True), ("ships", 10)),
        2000, ("ships", "seen"), (), SEED, 3, "x"))
    assert out["enemy"] == "the Lukka" and out["seen"] is True and out["ships"] > 10


def test_belief_shows_the_assertion_and_never_the_truth():
    world = _run(14)
    belief = project(world)
    letters = {L.id: L for L in world.inbox}
    for item in belief["stack"]:
        L = letters[item["id"]]
        assert set(item["facts"]) == {k for k, _ in L.facts}
        assert "true_facts" not in item and "report_bias" not in item
    # The scribe's copy sits ON TOP of the sender's lie: two independent layers.
    assert all("report_bias" not in str(value) for value in belief.values())


def test_replay_still_matches_with_asserted_and_true_facts_on_letters():
    world = _run(12)
    path = "/tmp/m7_test.json"
    save(path, SEED, "ugarit", 12, [], world, [])
    assert state_hash(replay(path)) == state_hash(world)


def test_a_scribes_slip_on_a_counted_thing_stays_a_slip():
    """Regression, found by M7. The scribe's fallback error was `value * 60`, so
    anything under 60 that did not transpose gained a whole sexagesimal place:
    three captured towns copied as 180, thirty-six ships as 2,160. Invisible in
    a granary of 180,000 qa; ruinous the moment a Voicer wrote it in a sentence.
    Ships and towns are counted, not written in places -- only bulk may slip."""
    from belief.distortion import transcribe
    for true in list(range(1, 12)) + [30, 36, 59, 90]:
        for turn in range(60):
            got = transcribe(true, SEED, turn, "L1:ships", 1000)
            assert got <= max(10, true * 10), (
                f"copying {true} produced {got}: that is not a slip")
    # Bulk grain keeps its dramatic sexagesimal slips: that is the M3 game.
    slips = {transcribe(180000, SEED, t, "ledger:grain", 1000, sexagesimal=True)
             for t in range(60)}
    assert any(value >= 180000 * 60 or value <= 180000 // 60 for value in slips)


# --- the prompt boundary (spec 8.9) ------------------------------------------

def test_safe_fields_is_a_type_boundary_not_a_convention():
    assert safe_fields({"tone": "cold", "min_lines": 6}) == {
        "tone": "cold", "min_lines": 6}
    for bad in ({"liability": 220}, {"report_bias": 900},
                {"true_facts": "x"}, {"cause_oath_id": "o1"},
                {"climate": 3}, {"seed": 1}):
        try:
            safe_fields(bad)
            raise AssertionError(f"safe_fields admitted {bad!r}")
        except PromptLeak:
            pass
    # No World object may be reachable from a prompt field.
    world = _run(2)
    for bad in ({"court": world.court}, {"w": world}, {"facts": {"a": 1}},
                {"flag": True}, {7: "x"}):
        try:
            safe_fields(bad)
            raise AssertionError(f"safe_fields admitted {bad!r}")
        except PromptLeak:
            pass


def test_no_prompt_any_role_builds_ever_contains_a_forbidden_key():
    """Spec 8.9, stated as a test: the model must never see these."""
    world = _run(14)
    assert "liability" not in {
        field.name for field in dataclasses.fields(type(world.court))}
    belief = project(world)
    prompts: list[str] = []

    class Recorder:
        """Records what each role would send, then takes the unavailable path so
        every role falls back exactly as it does when Ollama is not running."""
        ai_log: list = []

        def call(self, role, messages, schema, seed, max_tokens, timeout, turn=0):
            prompts.append(" ".join(m["content"] for m in messages))
            raise ModelUnavailable("recorded; no generation wanted")

    client = Recorder()
    voicer_prompts = [" ".join(m["content"] for m in V.build_prompt(item))
                      for item in belief["stack"]]
    prompts.extend(voicer_prompts)
    for item in belief["stack"]:
        V.voice(item, SEED, 14, client)
    compose("hatti_king", "refuse the grain", {"ships": 4}, SEED, 14, client)
    parse("read the first letter", belief, 10, SEED, 14, client)
    assert prompts and voicer_prompts

    # Two enforcement layers, and they check different things. `safe_fields` is
    # the real boundary and matches field names exactly (test above). This scan
    # is belt-and-braces over the finished prose, so it must skip the handful of
    # guarded names that are also ordinary game vocabulary the player may see --
    # `seed` is the RNG seed here and the seed-grain ledger there.
    ALSO_GAME_WORDS = {"seed", "accuracy", "knowledge", "collapse", "climate"}
    blob = " ".join(prompts).casefold()
    for key in FORBIDDEN_KEYS - ALSO_GAME_WORDS:
        assert not re.search(rf"(?<!\w){re.escape(key)}(?!\w)", blob), (
            f"forbidden key {key!r} reached a prompt")
    assert "liability" not in blob


def test_the_voicer_is_told_the_lie_and_never_the_truth():
    """The sharp end of Law 1. A blob-wide scan for the true figures is pure
    noise -- 12 is both the governor's true ship count and Amurru's line band --
    so this checks the one place a figure carries meaning: the FACTS block the
    model is told it may quote.

    Checked per fact, not per letter. Comparing one fact's truth against every
    number in the block conflates them, and once M8 put more letters on the pile
    the collisions were routine -- the governor's asserted ships coming out at
    30 while his true garrison was also 30 is a coincidence, not a leak.
    """
    world = _run(14)
    letters = {L.id: L for L in world.inbox}
    lies = 0
    for item in project(world)["stack"]:
        L = letters[item["id"]]
        prompt = " ".join(m["content"] for m in V.build_prompt(item))
        block = prompt.split("FACTS YOU ASSERT", 1)[1]
        numbers = set(re.findall(r"\d+", block))
        assert numbers == {str(v) for v in item["facts"].values()
                           if isinstance(v, int) and not isinstance(v, bool)}
        labels = V._LETTERS.get(item["topic"], {}).get("labels", {})
        for key, value in L.true_facts:
            if not isinstance(value, int) or dict(L.facts).get(key) == value:
                continue
            lies += 1
            label = labels.get(key, key)
            assert f"{label}: {item['facts'][key]}" in block
            assert f"{label}: {value}" not in block, (
                f"the true {key} ({value}) leaked past {L.sender}'s lie")
    assert lies, "no letter on this pile was distorted; the test proves nothing"


# --- persona cards (spec 8.6) ------------------------------------------------

def test_every_correspondent_has_a_persona_and_it_shapes_the_prompt():
    world = _run(1)
    for c in world.correspondents:
        card = V.persona(c.actor)
        assert card["who"] and card["tone"] and card["wants"] and card["address"]
        assert len(card["lines"]) == 2 and card["lines"][0] <= card["lines"][1]

    world = _run(14)
    belief = project(world)
    item = next(it for it in belief["stack"] if it["sender"] == "alashiya_gov")
    text = " ".join(m["content"] for m in V.build_prompt(item))
    assert "Abdi-milki" in text and "frightened" in text
    assert str(item["facts"]["ships"]) in text
    # Silence is audible: an ignored correspondent is told he has been ignored.
    pressed = dict(item, unanswered=3)
    assert "3 times" in " ".join(m["content"] for m in V.build_prompt(pressed))


def test_every_asserted_fact_is_spelled_out_for_the_model():
    """A bare engine key misleads: handed `men: 10` the model put ten men aboard
    the ships rather than leaving ten to hold the island."""
    world = _run(1)
    for c in world.correspondents:
        labels = V._LETTERS.get(c.topic, {}).get("labels", {})
        for key, _ in c.facts:
            assert key in labels, f"{c.topic}.{key} has no label for the Voicer"
            assert not any(ch.isdigit() for ch in labels[key]), (
                f"label {c.topic}.{key} asserts a number of its own")

    item = _item()
    block = " ".join(m["content"] for m in V.build_prompt(item)
                     ).split("FACTS YOU ASSERT", 1)[1]
    assert "men you have under arms" in block and "men:" not in block


def test_the_number_of_unanswered_letters_is_licensed():
    """The prompt tells him he has written N times, so 'this is my third asking'
    must survive the guard. It was passing only when N happened to be 7, which
    is formulaic ('seven times and seven times')."""
    item = dict(_item(), unanswered=4)
    allowed = V._allowed_numbers(item["facts"], item["unanswered"])
    assert guard("I have written to you four times.", allowed)[0]
    assert not guard("I have written to you nine times.", allowed)[0]
    assert not guard("I have written to you 4 times, and sent 900 men.", allowed)[0]


def test_persona_is_voice_only_and_cannot_move_an_outcome():
    """A persona may not carry a figure the engine should be deciding."""
    for actor, card in V._PERSONAS.items():
        blob = " ".join(str(card.get(k, "")) for k in
                        ("who", "temper", "tone", "wants", "address"))
        assert not any(ch.isdigit() for ch in blob), (
            f"persona {actor!r} asserts a number; that belongs in the scenario")


# --- generation, guard, and fallback (spec 8.6, 8.7) -------------------------

class FakeClient:
    """A model that says whatever it was told to, and counts its calls."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.ai_log: list = []
        self.flagged = 0

    def call(self, role, messages, schema, seed, max_tokens, timeout, turn=0):
        self.calls += 1
        return self.replies[min(self.calls - 1, len(self.replies) - 1)]

    def flag_last(self, role, **flags):
        self.flagged += 1


def _item(world=None):
    world = world or _run(14)
    return next(it for it in project(world)["stack"]
                if it["sender"] == "alashiya_gov")


def test_clean_model_text_is_used_and_licensed_numbers_pass():
    item = _item()
    ships = item["facts"]["ships"]
    text, source = V.voice(
        item, SEED, 14, FakeClient([f"To the king my lord.\n{ships} ships stand off my coast."]))
    assert source == "model" and str(ships) in text


def test_an_invented_number_costs_one_rewrite_then_the_template():
    item = _item()
    liar = FakeClient(["I have seen 999 ships and 40000 men."])
    text, source = V.voice(item, SEED, 14, liar)
    assert liar.calls == 2, "one regeneration, naming the stray numbers"
    assert liar.flagged >= 1, "every guard failure is logged for tuning"
    assert source == "fallback" and text == V.fallback_body(item)
    # The corrective line must actually name what was rejected.
    assert not guard("999 ships", V._allowed_numbers(item["facts"]))[0]


def test_the_game_plays_with_the_model_off():
    item = _item()
    assert V.voice(item, SEED, 14, None) == (V.fallback_body(item), "fallback")
    quiet = V.Voicer(None, SEED)
    quiet.schedule([item], 14)
    assert quiet.body(item) == (V.fallback_body(item), "fallback")
    assert quiet.note() == ""


def test_generation_is_capped_and_runs_in_stack_order():
    world = _run(24)
    stack = project(world)["stack"]
    assert len(stack) > V.CAP_PER_TURN, "the pile must outrun the scribes to test this"

    seen: list[str] = []

    class Ordered(FakeClient):
        def call(self, role, messages, schema, seed, max_tokens, timeout, turn=0):
            seen.append(messages[1]["content"])
            return super().call(role, messages, schema, seed, max_tokens, timeout, turn)

    v = V.Voicer(Ordered(["To the king, my lord. It is as I have said."]), SEED)
    v.schedule(stack, 24)
    assert v.wait(), "the worker must finish"
    assert len(seen) == V.CAP_PER_TURN
    assert v.skipped == len(stack) - V.CAP_PER_TURN and v.note()
    # Top of the pile first (spec 8.7): the interesting items are there.
    from tui.render import actor_name
    for prompt, item in zip(seen, stack[:V.CAP_PER_TURN]):
        assert actor_name(item["sender"]) in prompt
    for item in stack[:V.CAP_PER_TURN]:
        assert v.body(item)[1] == "model"
    for item in stack[V.CAP_PER_TURN:]:
        assert v.body(item) == (V.fallback_body(item), "fallback")


def test_reading_an_unfinished_body_never_waits():
    item = _item()
    started = threading.Event()

    class Slow(FakeClient):
        def call(self, *a, **kw):
            started.set()
            time.sleep(5)
            return "too late"

    v = V.Voicer(Slow([]), SEED)
    v.schedule([item], 14)
    assert started.wait(2), "the worker should have begun"
    t0 = time.monotonic()
    text, source = v.body(item)
    assert time.monotonic() - t0 < 0.5, "body() must never block on the model"
    assert source == "fallback" and text == V.fallback_body(item)


def test_a_new_turn_abandons_the_previous_pile():
    item = _item()
    v = V.Voicer(FakeClient(["To the king, my lord."]), SEED)
    v.schedule([item], 14)
    assert v.wait()
    v.schedule([item], 15)                    # already generated: nothing to do
    assert v.skipped == 0 and v.body(item)[1] == "model"


def test_a_failing_worker_does_not_take_the_game_down():
    item = _item()

    class Broken(FakeClient):
        def call(self, *a, **kw):
            raise RuntimeError("the model has fallen over")

    v = V.Voicer(Broken([]), SEED)
    v.schedule([item], 14)
    assert v.wait()
    assert v.body(item) == (V.fallback_body(item), "fallback")
