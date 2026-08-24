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
from engine import actions as A
from engine import revenue
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tui import ledgers, trade as trade_page, workbench
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
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _game(turns: int = 8, world=None):
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = world if world is not None else _world(turns)
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
    game.on_stores_key(_Key("i"))
    assert _kinds(game) == ["InspectLedger"]
    assert game.ledger_state["stores"]["pick"] == "grain"
    assert game.notices["stores"].kind == registry.SUCCESS


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


def test_reordering_rations_is_free_until_the_full_order_is_given() -> None:
    game = _game()
    state = game.ledger_state["roll"]
    active = list(game.belief["priority"])
    state["pick"] = active[0]
    before = game.hours
    game.on_roll_key(_Key(keysym="Right"))
    assert state["priority"][:2] == active[1::-1]
    assert not game.log
    assert game.hours == before

    game.on_roll_key(_Key(keysym="Return"))
    assert _kinds(game) == ["SetPriority"]
    assert len(game.log[0]["action"]["order"]) == len(active)
    assert not state["priority"]


def test_every_ration_group_is_reachable_at_the_storehouse_size() -> None:
    game = _game()
    game.storehouse_view = "roll"
    order = list(game.belief["priority"])
    screen = game.compose("stores")
    visible = {hit.command.split(":", 1)[1] for hit in screen.hits
               if hit.command.startswith("pick:")}
    assert set(order) <= visible

    for _ in order:
        game.on_storehouse_key(_Key(keysym="Down"))
    assert game.ledger_state["roll"]["pick"] == order[-1]
    assert order[-1] in {
        hit.command.split(":", 1)[1]
        for hit in game.compose("stores").hits
        if hit.command.startswith("pick:")}


def test_a_ration_draft_previews_then_clears_when_given() -> None:
    game = _game()
    group = next(item for item in game.belief["groups"]
                 if item["id"] == "palace_dependents")
    state = game.ledger_state["roll"]
    state["pick"] = group["id"]
    game.on_roll_key(_Key("["))
    step = max(ledgers.STEPS["roll"],
               group["size"] * group["entitlement"] // 4)
    expected = max(0, group["allocated"] - step)
    assert state["amount"] == expected
    text = plain_text(game.compose_ledger(
        "roll", game.belief, 82, 28, ""))
    assert f"allocate {expected:,} qa" in text and "DRAFT" in text

    game.on_roll_key(_Key("a"))
    assert _kinds(game) == ["Allocate"]
    assert state["amount"] == 0


def test_first_ration_bracket_adjusts_the_visible_ration() -> None:
    game = _game()
    state = game.ledger_state["roll"]
    group_id = game.belief["priority"][0]
    group = next(item for item in game.belief["groups"]
                 if item["id"] == group_id)
    step = max(ledgers.STEPS["roll"],
               group["size"] * group["entitlement"] // 4)

    game.on_roll_key(_Key("["))

    assert state["pick"] == group_id
    assert state["amount"] == max(0, group["allocated"] - step)


def test_the_roll_toggles_hands_in_and_out_of_the_fields() -> None:
    game = _game()
    game.ledger_state["roll"]["pick"] = "palace_dependents"
    game.on_roll_key(_Key("h"))
    assert _kinds(game) == ["SendToHarvest"]
    assert game.log[-1]["action"]["to_fields"] is True
    assert "recall from fields" in plain_text(game.compose_ledger(
        "roll", game.belief, 82, 28, ""))

    game.on_roll_key(_Key("h"))
    assert _kinds(game) == ["SendToHarvest", "SendToHarvest"]
    assert game.log[-1]["action"]["to_fields"] is False


# --- the land -----------------------------------------------------------------

def test_the_land_readies_a_corvee_and_drafts_the_due() -> None:
    game = _game(13)
    game.world, _ = apply(game.world, A.BeginBuild("walls", "seat"))
    state = game.ledger_state["land"]
    game.on_land_key(_Key("]"))
    text = plain_text(game.compose_ledger(
        "land", game.belief, 84, 29, ""))
    assert "raise corvée 400d · unrest +16" in text
    game.on_land_key(_Key("c"))
    assert _kinds(game) == ["RaiseCorvee"]
    assert state["amount"] == 0

    game.on_land_key(_Key(">"))
    assert game.storehouse_view == "dues"
    assert game.ledger_state["dues"]["rates"]["land"] == (
        game.belief["land"]["land_due_rate"] + ledgers.STEPS["land_due"])
    game.on_storehouse_account_key(_Key(keysym="Return"))
    assert _kinds(game) == ["RaiseCorvee", "SetLandDue"]


def test_due_steps_make_one_draft_and_one_policy_order() -> None:
    game = _game()
    game.storehouse_view = "dues"
    state = game.ledger_state["dues"]
    state["pick"] = "harbour"
    before_schedule = len(game.world.schedule)

    for _ in range(4):
        game.on_storehouse_key(_Key(">"))
    assert not game.log
    assert len(game.world.schedule) == before_schedule
    assert state["rates"]["harbour"] == 200
    assert "DRAFT" in plain_text(game.compose("stores"))

    game.on_storehouse_key(_Key(keysym="Return"))
    assert _kinds(game) == ["SetHarbourDue"]
    assert game.log[0]["action"]["rate"] == 200
    assert len(game.world.schedule) == before_schedule + 2
    assert not state["rates"]


def test_trade_due_uses_the_same_single_commit_draft() -> None:
    game = _game()
    game.trade_view = "dues"
    game.on_trade_key(_Key(">"))
    game.on_trade_key(_Key(">"))
    assert not game.log
    assert game.ledger_state["dues"]["rates"]["harbour"] == 150

    game.on_trade_key(_Key(keysym="Return"))
    assert _kinds(game) == ["SetHarbourDue"]
    assert game.log[0]["action"]["rate"] == 150


def test_stepping_a_due_back_to_the_live_rate_cancels_the_draft() -> None:
    game = _game()
    game.trade_view = "dues"
    game.on_trade_key(_Key(">"))
    game.on_trade_key(_Key("<"))
    assert not game.ledger_state["dues"]["rates"]

    game.on_trade_key(_Key(keysym="Return"))
    assert not game.log


def test_due_drafts_show_the_take_and_the_cost_at_real_window_sizes() -> None:
    belief = project(_world())
    for width, height in ((82, 28), (84, 29)):
        text = plain_text(ledgers.storehouse_account(
            belief, "dues", selected="land", drafts={"land": 175},
            width=width, height=height))
        assert "LAND DUE · DRAFT" in text
        assert "this harvest" in text and "storage risk" in text
        assert "unrest +6" in text and "Enter gives one order" in text

    for width, height in ((66, 22), (72, 24)):
        text = plain_text(trade_page.compose(
            belief, width=width, height=height, view="dues", due_draft=150))
        assert "next clearance" in text and "~48 oil  (+16)" in text
        assert "2 merchants take offence" in text
        assert "up to −12 in 3–6 fortnights" in text
        assert "finance / requisition" not in text


def test_harbour_due_shows_old_and_new_trade_losses_without_hidden_scores() -> None:
    world, _ = revenue.set_harbour_due(load_campaign("seat", SEED), 125)
    belief = project(world)
    text = plain_text(trade_page.compose(
        belief, width=66, height=22, view="dues", due_draft=150))
    assert "new trade loss" in text and "up to −6" in text
    assert "already pending" in text and "up to −6 from 2 answers" in text
    assert "traffic after" in text and "~988 / 1,000" in text
    assert "esteem" not in text
    lowered = plain_text(trade_page.compose(
        belief, width=66, height=22, view="dues", due_draft=100))
    assert "past offence remains" in lowered and "esteem" not in lowered


def test_storehouse_only_offers_enter_when_a_due_is_drafted() -> None:
    belief = project(_world())
    quiet = plain_text(ledgers.storehouse_account(
        belief, "dues", selected="land", width=82, height=28, drafts={}))
    drafted = plain_text(ledgers.storehouse_account(
        belief, "dues", selected="land", width=82, height=28,
        drafts={"land": 175}))
    assert "Enter give" not in quiet and "Enter gives one order" not in quiet
    assert "Enter give" in drafted and "Enter gives one order" in drafted


def test_storehouse_skips_the_duplicate_reserves_tab() -> None:
    belief = project(_world())
    text = plain_text(ledgers.stores(
        belief, width=84, height=29, room=True))
    assert tuple(key for key, _label in ledgers.STOREHOUSE_VIEWS) == (
        "stores", "roll", "land", "dues")
    assert "RESERVES" not in text
    assert "grain" in text


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

def test_the_muster_keeps_formation_orders_together() -> None:
    game = _game()
    formation = game.belief["troops"]["formations"][0]
    screen = ledgers.muster(
        game.belief, selected=formation["id"],
        place=game.belief["seat"],
        width=72, height=24, hours=game.hours)
    text = plain_text(screen)
    actions = {hit.command for hit in screen.hits if hit.enabled}

    assert "THE MUSTER — FORMATIONS" in text
    assert formation["name"] in text
    assert "SPEAR FORMATION" in text
    assert "════▷" in text
    assert "do:assign_troops" in actions

def test_the_muster_sends_a_formation_to_a_task_and_a_place() -> None:
    game = _game()
    state = game.ledger_state["muster"]
    formation = game.belief["troops"]["formations"][0]
    game.on_muster_key(_Key("a"))
    assert not game.log, "no place is chosen yet"
    assert state["pick"] == formation["id"]
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
    assert not game.log and game.pending_action is not None
    game.confirm_pending()
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
            # The list must never be squeezed away entirely. The land list is
            # the one honest exception: since C4 the crown's fields are the
            # kernel's ground, so there are no estates to pick until the
            # re-point at C5.
            screen = compose(belief, width=size[0], height=size[1], hours=6)
            rows = [hit for hit in screen.hits
                    if hit.command.startswith("pick:")]
            if key == "land":
                continue
            assert rows, (key, size)
