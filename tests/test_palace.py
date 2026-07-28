"""One room for the court, the house and the foreign courts (UI/UX spec 16).

Three windows became three views of one place, so these tests are mostly about
the seams: that each view still gives every order its registry context claims,
that the picture and the list are the same queue rather than two lists that
might disagree, and that appointing a man to a post is now two steps that each
say what they are.
"""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine.tick import advance
from load import load_scenario
from tui import palace
from tui.grid import plain_text, pure_ascii

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


# --- the room -----------------------------------------------------------------

def test_the_room_is_drawn_and_still_reads_as_plain_ascii() -> None:
    b = project(_world())
    screen = palace.compose(b, view="court", hours=8, width=98, height=36)
    assert len(screen) == 36 and all(len(row) == 98 for row in screen)
    text = plain_text(pure_ascii(screen))
    assert all(ord(character) < 128 for character in text)
    assert "THE PALACE" in text


def test_the_figures_on_the_floor_are_the_rows_of_the_list() -> None:
    """The picture is the queue, so a man is selectable and numbered."""
    b = project(_world())
    screen = palace.compose(b, view="court", hours=8, width=98, height=36)
    petitions = [p["id"] for p in b["justice"]["petitions"]]
    picks = {hit.command.split(":", 1)[1] for hit in screen.hits
             if hit.command.startswith("pick:")}
    assert set(petitions[:1]) <= picks
    # Each man carries the number his row carries.
    text = plain_text(screen)
    assert "[1]" in text


def test_the_room_gives_up_its_art_before_it_gives_up_its_list() -> None:
    b = project(_world())
    least = (68, 24)
    text = plain_text(palace.compose(b, view="court", hours=8,
                                     width=least[0], height=least[1]))
    assert "hear" in text.lower() or "Hear" in text
    for height in (24, 30, 36):
        assert palace.scene_rows(height) <= max(0, height - 12)


def test_every_view_offers_every_order_its_context_claims() -> None:
    """The gap the ledgers' guard exists to catch, for this room too."""
    b = project(_world())
    for view, context in palace.CONTEXT_OF.items():
        offered = {control.action_id
                   for control in palace.controls_for(b, view, hours=8)}
        for descriptor in registry.in_context(context):
            assert descriptor.id in offered, (view, descriptor.id)


def test_every_control_the_room_offers_is_drawn_on_it() -> None:
    """A control listed and not printed is an order with no visible route."""
    b = project(_world())
    for view in palace.CONTEXT_OF:
        screen = palace.compose(b, view=view, hours=8, width=98, height=36)
        text = plain_text(screen)
        for control in palace.controls_for(b, view, hours=8):
            assert f"[{control.key}]" in text, (view, control.key)


# --- the court ----------------------------------------------------------------

def test_a_man_must_be_heard_before_he_is_judged() -> None:
    game = _game()
    petition = project(game.world)["justice"]["petitions"][0]["id"]
    game.palace_state["view"] = "court"
    game.palace_state["pick"]["court"] = petition
    game.on_palace_key(_Key("f"))
    assert not game.log
    assert game.notices["palace"].kind == registry.REFUSAL
    assert "hear him" in game.notices["palace"]

    game.on_palace_key(_Key("h"))
    assert _kinds(game) == ["HearPetition"]
    game.on_palace_key(_Key("f"))
    assert _kinds(game) == ["HearPetition", "RulePetition"]
    assert game.log[-1]["action"]["verdict"] == "for"
    assert game.log[-1]["action"]["petition_id"] == petition


def test_hearing_a_man_twice_is_refused_rather_than_charged() -> None:
    game = _game()
    petition = project(game.world)["justice"]["petitions"][0]["id"]
    game.palace_state["pick"]["court"] = petition
    game.on_palace_key(_Key("h"))
    before = game.hours
    game.on_palace_key(_Key("h"))
    assert game.hours == before
    assert "already heard" in game.notices["palace"]


# --- the house ----------------------------------------------------------------

def test_appointing_is_two_steps_that_each_say_what_they_are() -> None:
    game = _game()
    game.palace_state["view"] = "house"
    person = palace._people(game.belief)[0]["id"]
    game.palace_state["pick"]["house"] = person

    game.on_palace_key(_Key("o"))
    assert game.palace_state["choosing"] == "post"
    assert game.palace_state["person"] == person
    text = plain_text(game.compose("palace"))
    assert "A POST FOR" in text, "the heading must name the man"

    post = game.window_rows("palace")[0]
    game.palace_state["pick"]["post"] = post
    game.on_palace_key(_Key(keysym="Return"))
    assert _kinds(game) == ["PlacePerson"]
    assert game.log[0]["action"]["person_id"] == person
    assert game.log[0]["action"]["post"] == post
    assert not game.palace_state["choosing"], "the room comes back afterwards"


def test_a_choice_of_post_can_be_thought_better_of() -> None:
    game = _game()
    game.palace_state["view"] = "house"
    game.palace_state["pick"]["house"] = palace._people(game.belief)[0]["id"]
    game.on_palace_key(_Key("o"))
    game.on_palace_key(_Key(keysym="Escape"))
    assert not game.palace_state["choosing"]
    assert not game.log


def test_a_man_with_no_post_cannot_be_dismissed_from_one() -> None:
    game = _game()
    game.palace_state["view"] = "house"
    person = next(p for p in palace._people(game.belief) if not p["post"])
    game.palace_state["pick"]["house"] = person["id"]
    game.on_palace_key(_Key("k"))
    assert not game.log
    assert "holds no post" in game.notices["palace"]


def test_the_succession_can_be_settled_from_the_room() -> None:
    game = _game()
    game.palace_state["view"] = "house"
    heir = next(p for p in palace._people(game.belief) if p.get("heir_rank"))
    game.palace_state["pick"]["house"] = heir["id"]
    game.on_palace_key(_Key("n"))
    assert _kinds(game) == ["NameHeir"]


def test_naming_a_man_who_cannot_inherit_says_the_engines_reason() -> None:
    game = _game()
    game.palace_state["view"] = "house"
    brother = next(p for p in palace._people(game.belief)
                   if not p.get("heir_rank"))
    game.palace_state["pick"]["house"] = brother["id"]
    game.on_palace_key(_Key("n"))
    assert not game.log
    assert "succession" in game.notices["palace"]


# --- relations ----------------------------------------------------------------

def test_a_gift_needs_a_court_and_an_amount_and_says_which_is_missing() -> None:
    game = _game()
    state = game.palace_state
    state["view"] = "relations"
    state["pick"]["relations"] = game.belief["relations"][0]["other"]
    game.on_palace_key(_Key("i"))
    assert not game.log
    assert "amount" in game.notices["palace"]

    game.on_palace_key(_Key("]"))
    assert state["amount"] == palace.GIFT_STEP
    game.on_palace_key(_Key("i"))
    assert _kinds(game) == ["SendGift"]
    assert game.log[0]["action"]["quantity"] == palace.GIFT_STEP
    assert state["amount"] == 0, "the amount is spent, not left standing"


def test_the_good_being_given_can_be_changed() -> None:
    game = _game()
    game.palace_state["view"] = "relations"
    first = game.palace_state["good"]
    game.on_palace_key(_Key("g"))
    assert game.palace_state["good"] != first


def test_the_harbour_due_is_set_where_the_harbour_is() -> None:
    """The specification's complaint: it must not hide behind House brackets."""
    game = _game()
    game.palace_state["view"] = "relations"
    game.on_palace_key(_Key(">"))
    assert _kinds(game) == ["SetHarbourDue"]
    assert game.log[0]["action"]["rate"] == (
        game.belief["revenue"]["harbour_rate"])


# --- moving about -------------------------------------------------------------

def test_a_digit_chooses_a_view_and_the_views_keep_their_own_selection() -> None:
    game = _game()
    game.on_palace_key(_Key("2"))
    assert game.palace_state["view"] == "house"
    game.palace_state["pick"]["house"] = palace._people(game.belief)[1]["id"]
    game.on_palace_key(_Key("3"))
    assert game.palace_state["view"] == "relations"
    game.on_palace_key(_Key("2"))
    assert game.palace_pick("house") == palace._people(game.belief)[1]["id"]
