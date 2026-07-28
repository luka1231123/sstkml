"""The Orders workbench reads intent back (UI/UX spec 13, audit problem 13).

The window has one job that nothing else in the game does: answer *did I
already order that, and does it still stand*. Everything here is about that
question staying true as more orders are given.
"""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from tui import orders
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


def _world(turns: int = 6):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _given(world, actions):
    log = []
    for action in actions:
        world, _ = apply(world, action)
        log.append({"turn": world.date.absolute, "action": A.to_dict(action)})
    return world, log


def _game(actions=()):
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world, game.log = _given(_world(), list(actions))
    game.hours = project(game.world)["attention"]
    game.client = None
    game.repaint = lambda: None
    return game


# --- what still stands --------------------------------------------------------

def test_a_later_order_about_the_same_thing_overtakes_the_first() -> None:
    _world_, log = _given(_world(), [A.SetLandDue(400), A.SetLandDue(450)])
    first, second = reversed(orders.history(log))
    assert first.state == orders.SUPERSEDED
    assert second.state == orders.STANDING


def test_two_orders_about_different_things_both_stand() -> None:
    world = _world()
    b = project(world)
    places = [place["id"] for place in b["world_graph"]["places"][:2]]
    _world_, log = _given(world, [A.Quarantine(places[0], False),
                                  A.Quarantine(places[1], False)])
    assert [order.state for order in orders.history(log)] == [
        orders.STANDING, orders.STANDING]


def test_lifting_a_closure_leaves_nothing_in_force() -> None:
    world = _world()
    place = project(world)["world_graph"]["places"][0]["id"]
    _world_, log = _given(world, [A.Quarantine(place, False),
                                  A.Quarantine(place, True)])
    standing = [order for order in orders.history(log)
                if order.state == orders.STANDING]
    assert not standing, "a lifted closure is not still closing anything"


def test_an_order_with_no_inverse_is_simply_done() -> None:
    _world_, log = _given(_world(), [A.InspectLedger("granary")])
    order, = orders.history(log)
    assert order.state == orders.GIVEN
    assert orders.countermand(order) is None


# --- reading it back ----------------------------------------------------------

def test_an_order_reads_back_in_the_words_it_was_given_in() -> None:
    world = _world()
    b = project(world)
    group = b["groups"][0]
    _world_, log = _given(world, [A.SendToHarvest(group["id"], True)])
    order, = orders.history(log)
    said = orders.phrase(order, project(_world_))
    assert group["name"] in said, said
    assert "_" not in said, "engine ids are not a record anybody can audit"


def test_the_reverse_of_an_order_is_not_called_by_its_name() -> None:
    world = _world()
    place = project(world)["world_graph"]["places"][0]["id"]
    _world_, log = _given(world, [A.Quarantine(place, True)])
    order, = orders.history(log)
    assert "Lift" in orders.phrase(order, project(_world_))


def test_every_action_the_registry_knows_can_be_read_back() -> None:
    """A logged order with no way to phrase it is a hole in the record."""
    b = project(_world())
    for descriptor in registry.DESCRIPTORS:
        record = {"turn": 0, "action": {"_t": descriptor.action_type.__name__}}
        order, = orders.history([record])
        said = orders.phrase(order, b)
        slot = orders.SLOTS.get(descriptor.action_type.__name__)
        names = {descriptor.label, slot.off_label if slot else ""}
        assert said.split(":")[0] in names, (descriptor.id, said)


# --- the window ---------------------------------------------------------------

def test_the_window_shows_each_view_and_says_when_one_is_empty() -> None:
    world = _world()
    b = project(world)
    _world_, log = _given(world, [A.InspectLedger("granary")])
    for key, _label in orders.VIEWS:
        text = plain_text(orders.compose(b, log, world.date.absolute,
                                         hours=8, view=key))
        assert "ORDERS" in text
    empty = plain_text(orders.compose(b, [], world.date.absolute, view="standing"))
    assert "no order of yours is still in force" in empty


def test_countermanding_gives_the_inverse_order_at_its_own_price() -> None:
    world = _world()
    place = project(world)["world_graph"]["places"][0]["id"]
    game = _game([A.Quarantine(place, False)])
    before = game.hours
    game.orders_state["pick"] = orders.history(game.log)[0].id
    game.on_orders_key(_Key("u"))
    kinds = [entry["action"] for entry in game.log]
    assert kinds[-1]["_t"] == "Quarantine" and kinds[-1]["lift"] is True
    assert game.hours == before - registry.BY_ID["quarantine"].cost
    assert not [order for order in orders.history(game.log)
                if order.state == orders.STANDING]


def test_an_order_that_cannot_be_unsaid_says_so_rather_than_failing() -> None:
    game = _game([A.InspectLedger("granary")])
    game.orders_state["view"] = "all"
    game.orders_state["pick"] = orders.history(game.log)[0].id
    game.on_orders_key(_Key("u"))
    assert len(game.log) == 1
    assert game.notices["orders"].kind == registry.REFUSAL
    assert "unsaid" in game.notices["orders"]


def test_the_tabs_answer_to_their_own_numbers() -> None:
    game = _game([A.InspectLedger("granary")])
    game.on_orders_key(_Key("3"))
    assert game.orders_state["view"] == "all"
    game.on_orders_key(_Key(command="tab:fortnight"))
    assert game.orders_state["view"] == "fortnight"
