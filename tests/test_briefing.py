"""A new ruler can reach real decisions without a command or model question."""

import tempfile
from pathlib import Path

from engine import actions as A, seat
from session import save, load_session
from tests.test_ledgers import _game, _Key
from tui import briefing, palace
from tui.grid import plain_text


def controller(turns=1):
    game = _game(turns=turns)
    game.hall_guided = True
    game.briefing_pick = ""
    game.opened = []
    game.open_ledger = lambda key: game.opened.append(key)
    game.open_room = lambda key: game.opened.append(key)
    game.open_tablet = lambda key: game.opened.append(key)
    return game


def test_first_audience_leads_to_an_inspection_then_a_named_dispute():
    game = controller()
    matters = briefing.agenda(game.belief, game.log)
    assert [m.id for m in matters[:2]] == ["food", "justice"]
    assert "Abdi-Anu" in matters[1].title
    before, hours = game.world, game.hours
    game.on_key(_Key(keysym="Return"))
    assert game.opened == ["t"]
    assert game.world is before and game.hours == hours
    assert game.storehouse_view == "stores"
    assert game.ledger_state["stores"]["pick"] == "grain"
    assert "Press I" in game.notices["stores"]
    game.on_storehouse_key(_Key("i"))
    assert game.log[-1]["action"]["_t"] == "InspectLedger"
    assert game.hours == hours - 1
    matters = briefing.agenda(game.belief, game.log)
    assert matters[0].id == "justice"
    assert next(m for m in matters if m.id == "food").view == "roll"
    assert "firmer record" in briefing.response(game.log, game.belief["turn"])


def test_judgement_is_reviewable_and_returns_a_named_material_receipt():
    game = controller()
    game.open_briefing_matter("justice")
    assert game.opened == ["j"] and game.palace_state["view"] == "audience"
    assert game.palace_pick() == "debt_shipwright"
    before, copper = game.world, seat.held(game.world)["copper"]
    game.on_palace_key(_Key("f"))
    assert game.world is before and not game.log
    game.cancel_pending()
    assert game.world is before
    game.on_palace_key(_Key("f"))
    game.confirm_pending()
    assert seat.held(game.world)["copper"] == copper - 9000
    assert "Abdi-Anu" in briefing.response(game.log, game.belief["turn"])
    assert "9,000 copper" in briefing.response(game.log, game.belief["turn"])
    assert not any(m.id == "justice" for m in briefing.agenda(game.belief, game.log))


def test_guidance_never_consumes_time_and_every_matter_can_be_selected():
    game = controller(turns=7)
    before, hours = game.world, game.hours
    ids = [m.id for m in briefing.agenda(game.belief, game.log)]
    reached = {ids[0]}
    for _ in ids:
        game.on_key(_Key(keysym="Down"))
        reached.add(game.briefing_pick)
    assert set(ids) <= reached
    game.on_key(_Key(keysym="Tab"))
    assert not game.hall_guided
    game.on_key(_Key(keysym="Tab"))
    assert game.hall_guided and game.world is before and game.hours == hours


def test_relief_guidance_preserves_a_wet_tablet_and_opens_the_right_sent_copy():
    game = controller(turns=7)
    game.open_briefing_matter("relief")
    assert game.trade_view == "relief" and game.opened == ["x"]
    game.desk = None
    game.desk_drafts = {}
    game._open_letter_desk("alashiya_gov", target_place="alashiya")
    game.desk["matter"] = "My words are still wet."
    draft_key = game.desk["draft_key"]
    game.open_briefing_matter("unread")
    assert game.desk is None
    assert game.desk_drafts[draft_key]["matter"] == "My words are still wet."
    assert game.inbox_filter == "unread" and game.inbox_pick
    assert not game.log


def test_briefing_and_plain_verdicts_fit_supported_sizes():
    game = controller()
    for selected in [m.id for m in briefing.agenda(game.belief, game.log)]:
        screen = briefing.compose(game.belief, game.log, 84, 28,
                                  hours=game.hours, selected=selected)
        text = plain_text(screen)
        assert "qa = grain measure" in text and "[Enter] open matter" in text
        assert "basis:" in text and "two weeks" in text
        assert "you may leave matters waiting" in text
    text = plain_text(palace.compose(game.belief, view="audience", width=68, height=24, hours=7))
    assert "Pay the claim: 9,000 copper" in text
    assert "Pay the counterclaim: 3,000 copper" in text
    assert "Lower unrest means a calmer city" in text


def test_briefing_preference_is_ui_only_and_survives_a_save():
    game = controller()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "game.json"
        save(path, game.seed, "seat", game.world.date.absolute, [], game.world,
             hours_left=game.hours, hall_guided=False)
        loaded, data = load_session(path)
        assert data["hall_guided"] is False
        assert seat.held(loaded) == seat.held(game.world)
        assert data["log"] == []


def test_an_arrived_grain_answer_is_opened_without_inventing_its_decision():
    game = controller(turns=7)
    game.desk = None
    game.desk_drafts = {}
    game.trade_view = "relief"
    game.on_relief_key(_Key(keysym="Return"))
    game.on_desk_key(_Key("s"))
    game.confirm_pending()
    from engine.tick import advance
    for _ in range(5):
        game.world, _ = advance(game.world)
    matter = next(m for m in briefing.agenda(game.belief, game.log) if m.id == "relief")
    assert "seal unbroken" in matter.fact
    assert "accepted" not in matter.fact
    game.open_briefing_matter("relief")
    assert game.inbox_pick == matter.selected and game.inbox_filter == "all"


def test_next_fortnight_remembers_paid_and_waiting_people_without_repeating_receipts():
    from engine.tick import advance
    from tui import aftermath
    game = controller()
    before = game.belief
    waiting_world, _ = advance(game.world)
    from belief.project import project
    waiting = " ".join(aftermath.lines(before, project(waiting_world), []))
    assert "Still waiting: Abdi-Anu" in waiting
    game.open_briefing_matter("justice")
    game.on_palace_key(_Key("f"))
    game.confirm_pending()
    before = game.belief
    game.world, _ = advance(game.world)
    after = game.belief
    report = " ".join(aftermath.lines(before, after, game.log))
    assert "Abdi-Anu" in report and "9,000 copper" in report
    assert "Still waiting: Abdi-Anu" not in report
    assert "No ration arrears expected or recorded" in report
    game.world, _ = advance(game.world)
    assert "9,000 copper" not in " ".join(aftermath.lines(after, game.belief, game.log))
