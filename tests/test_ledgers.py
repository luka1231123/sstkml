"""The five ledgers act as well as report (UI/UX spec 15, phase 4).

The exit gate for this phase is one sentence: *Counsel is unnecessary for all
current simulation actions.* Counsel is the optional model layer, so an order
reachable only through it does not exist when the model is off -- and the
specification names AI-off as the reference configuration, not a degraded one.

These tests drive each workbench through its own key handler, headless, and
assert the world actually changed.
"""
from __future__ import annotations

from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import ledgers, workbench
from tui.grid import plain_text

import registry

SEED = 8814402919


class _Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "", state: int = 0) -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = state


def _world(turns: int = 8):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _game():
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = _world()
    game.hours = project(game.world)["attention"]
    game.log = []
    game.client = None
    game.repaint = lambda: None
    return game


def _kinds(game) -> list[str]:
    return [entry["action"]["_t"] for entry in game.log]


# --- the gate -----------------------------------------------------------------

def test_counsel_is_unnecessary_for_every_action() -> None:
    """Phase 4's exit gate, asserted rather than asserted-to-have-been-done."""
    from tools import inventory

    orphans = [problem for problem in inventory.faults()
               if "Counsel" in problem or "direct route" in problem]
    assert not orphans, orphans


def test_each_workbench_offers_every_action_its_context_claims() -> None:
    from tools import inventory

    assert not inventory._workbench_gaps()


# --- the stores ---------------------------------------------------------------

def test_the_stores_can_have_a_ledger_counted() -> None:
    game = _game()
    game.ledger_state["stores"]["pick"] = "grain"
    game.on_stores_key(_Key("i"))
    assert _kinds(game) == ["InspectLedger"]
    assert game.notices["stores"].kind == registry.SUCCESS


def test_the_stores_can_open_seed_for_food_and_say_when_they_cannot() -> None:
    game = _game()
    state = game.ledger_state["stores"]
    state["pick"] = "grain"
    game.on_stores_key(_Key("e"))
    assert not game.log
    assert game.notices["stores"].kind == registry.REFUSAL
    assert "seed" in game.notices["stores"]

    state["pick"] = "seed_grain"
    game.on_stores_key(_Key("]"))
    assert state["amount"] == ledgers.STEPS["stores"]
    game.on_stores_key(_Key("e"))
    assert _kinds(game) == ["EatSeed"]
    assert state["amount"] == 0, "the amount is spent, not left standing"


# --- the roll -----------------------------------------------------------------

def test_the_roll_allocates_to_the_chosen_group() -> None:
    game = _game()
    state = game.ledger_state["roll"]
    game.on_roll_key(_Key(keysym="Down"))
    chosen = state["pick"]
    assert chosen
    game.on_roll_key(_Key("]"))
    game.on_roll_key(_Key("a"))
    assert _kinds(game) == ["Allocate"]
    assert game.log[0]["action"]["group_id"] == chosen


def test_marking_for_priority_is_free_until_it_is_ordered() -> None:
    game = _game()
    state = game.ledger_state["roll"]
    game.on_roll_key(_Key(keysym="Down"))
    before = game.hours
    game.on_roll_key(_Key("p"))
    assert state["priority"], "marking is remembered"
    assert not game.log, "marking gives no order"
    assert game.hours == before

    game.on_roll_key(_Key(keysym="Return"))
    assert _kinds(game) == ["SetPriority"]
    assert not state["priority"], "the marks clear once ordered"


def test_the_roll_sends_hands_to_the_fields() -> None:
    game = _game()
    game.on_roll_key(_Key(keysym="Down"))
    game.on_roll_key(_Key("h"))
    assert _kinds(game) == ["SendToHarvest"]


# --- the land -----------------------------------------------------------------

def test_the_land_raises_a_corvee_and_moves_the_due() -> None:
    game = _game()
    state = game.ledger_state["land"]
    game.on_land_key(_Key("]"))
    game.on_land_key(_Key("c"))
    assert _kinds(game) == ["RaiseCorvee"]
    assert state["amount"] == 0

    game.on_land_key(_Key(">"))
    assert _kinds(game)[-1] == "SetLandDue"


def test_the_land_will_not_dredge_a_field_with_no_canal() -> None:
    game = _game()
    state = game.ledger_state["land"]
    state["amount"] = 5
    game.on_land_key(_Key("d"))
    assert not game.log
    assert game.notices["land"].kind == registry.REFUSAL
    assert "canal" in game.notices["land"]


def test_the_land_sends_a_chosen_group_to_the_fields() -> None:
    game = _game()
    game.on_land_key(_Key("h"))
    assert not game.log, "no group is chosen yet"
    assert game.notices["land"].kind == registry.REFUSAL

    game.on_land_key(_Key("g"))
    assert game.ledger_state["land"]["group"]
    game.on_land_key(_Key("h"))
    assert _kinds(game) == ["SendToHarvest"]


# --- the corvée and muster ----------------------------------------------------

def test_the_corvee_window_holds_labour_and_military_evidence_together() -> None:
    game = _game()
    formation = game.belief["troops"]["formations"][0]
    screen = ledgers.muster(
        game.belief, selected=formation["id"], amount=10,
        place=game.belief["seat"],
        width=72, height=24, hours=game.hours)
    text = plain_text(screen)
    actions = {hit.command for hit in screen.hits if hit.enabled}

    assert "THE CORVÉE — LEVY AND SPEAR" in text
    assert "corvée called" in text
    assert "hands ·" in text
    assert formation["name"] in text
    assert "SPEAR-BEARER OF THE LEVY" in text
    assert "════▷" in text
    assert {"do:raise_corvee", "do:assign_troops"} <= actions


def test_the_corvee_window_can_call_person_days() -> None:
    game = _game()
    state = game.ledger_state["muster"]
    game.on_muster_key(_Key("]"))
    assert state["amount"] == ledgers.STEPS["corvee"]
    game.on_muster_key(_Key("c"))
    assert _kinds(game) == ["RaiseCorvee"]
    assert game.log[0]["action"]["days"] == ledgers.STEPS["corvee"]
    assert state["amount"] == 0

def test_the_muster_sends_a_formation_to_a_task_and_a_place() -> None:
    game = _game()
    state = game.ledger_state["muster"]
    formation = game.belief["troops"]["formations"][0]
    state["pick"] = formation["id"]
    game.on_muster_key(_Key("a"))
    assert not game.log, "no place is chosen yet"
    assert game.notices["muster"].kind == registry.REFUSAL

    game.on_muster_key(_Key("t"))
    game.on_muster_key(_Key("l"))
    assert state["place"]
    game.on_muster_key(_Key("a"))
    assert _kinds(game) == ["AssignTroops"]
    assert game.log[0]["action"]["task"] == state["task"]


# --- the oaths ----------------------------------------------------------------

def test_only_a_lapsed_oath_can_be_sworn_again() -> None:
    game = _game()
    state = game.ledger_state["oaths"]
    state["pick"] = game.ledger_rows("oaths")[0]
    game.on_oaths_key(_Key("s"))
    assert not game.log
    assert "lapsed" in game.notices["oaths"]


def test_an_oath_can_be_expiated_with_what_is_laid_down() -> None:
    game = _game()
    state = game.ledger_state["oaths"]
    state["pick"] = game.ledger_rows("oaths")[0]
    game.on_oaths_key(_Key("]"))
    game.on_oaths_key(_Key("x"))
    assert _kinds(game) == ["Expiate"]


# --- the shape ----------------------------------------------------------------

def test_no_control_is_ever_dropped_for_want_of_room() -> None:
    """A control that is not printed is an action with no visible route."""
    controls = [
        workbench.Control("allocate", "a", label="a very long caption indeed"),
        workbench.Control("set_priority", "p", label="another long one here"),
        workbench.Control("send_to_harvest", "h", label="and a third, longer"),
    ]
    for width in (48, 60, 80, 120):
        laid = workbench._lay_out(controls, 8, width)
        printed = [control.action_id for row in laid for control, _c in row]
        assert printed == [c.action_id for c in controls], width


def test_irrelevant_zero_value_controls_are_removed_but_cost_refusals_remain() -> None:
    belief = project(_world())
    ordinary = plain_text(
        ledgers.oaths(belief, hours=0, width=82, height=28))
    assert "expiate with 0" not in ordinary
    assert "only a lapsed oath" not in ordinary

    oaths = list(belief["oaths"])
    lapsed = {
        **belief,
        "oaths": [{**oaths[0], "lapsed": True}] + oaths[1:],
    }
    text = plain_text(ledgers.oaths(
        lapsed, amount=50, hours=0, width=82, height=28))
    assert "Swear" in text or "swear" in text
    assert "2h" in text


def test_the_workbenches_render_at_every_tier() -> None:
    from tui import desktop

    belief = project(_world())
    screens = {
        "stores": ledgers.stores, "roll": ledgers.roll, "land": ledgers.land,
        "muster": ledgers.muster, "oaths": ledgers.oaths,
    }
    for key, compose in screens.items():
        least = desktop.minimum_size(key)
        for size in (least, desktop.default_size(key), (110, 40)):
            text = plain_text(compose(belief, width=size[0], height=size[1],
                                      hours=6))
            assert text, (key, size)
            # The list must never be squeezed away entirely.
            screen = compose(belief, width=size[0], height=size[1], hours=6)
            rows = [hit for hit in screen.hits
                    if hit.command.startswith("pick:")]
            assert rows, (key, size)
