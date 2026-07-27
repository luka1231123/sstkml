"""M12 6.20 and 6.22: dues, delayed merchants, offices, and the heir."""
from __future__ import annotations

import dataclasses

from belief.project import project
from engine import actions as A
from engine import house, institution
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from tui import household
from tui.grid import plain_text

SEED = 8814402919


def test_customary_dues_open_on_the_authored_rates():
    world = load_scenario("ugarit", SEED)
    assert world.court.land_due_rate == world.court.land_due_base == 300
    assert (world.court.harbour_due_rate
            == world.court.harbour_due_customary == 100)
    assert world.court.last_land_due == world.court.last_harvest * 300 // 1000


def test_the_land_due_is_the_ordered_share_of_the_gross_floor():
    world = load_scenario("ugarit", SEED)
    world, _ = apply(world, A.SetLandDue(400))
    due = None
    for _ in range(14):
        world, events = advance(world)
        due = next((event for event in events
                    if isinstance(event, A.LandDueTaken)), due)
    assert due is not None
    assert due.taken == due.gross * 400 // 1000
    assert world.court.last_harvest == due.gross
    assert world.court.last_land_due == due.taken


def test_a_raised_land_due_causes_repeated_flight_and_lowering_does_not_restore():
    world = load_scenario("ugarit", SEED)
    world, _ = apply(world, A.SetLandDue(500))
    world, _ = advance(world)
    first = {key: estate.hands for key, estate in world.court.estates.items()}
    assert set(first.values()) == {960}
    assert world.court.unrest >= 50
    world, _ = advance(world)
    assert set(estate.hands for estate in world.court.estates.values()) == {921}
    world, _ = apply(world, A.SetLandDue(300))
    world, _ = advance(world)
    assert {key: estate.hands for key, estate in world.court.estates.items()} == {
        key: 921 for key in first}


def test_harbour_due_is_in_kind_and_scales_with_the_working_harbour():
    world = load_scenario("ugarit", SEED)
    before = world.court.stores["oil"]
    world, events = advance(world)
    due = next(event for event in events
               if isinstance(event, A.HarbourDueTaken))
    # Upkeep and spoilage also move oil; the collection itself is pinned here.
    assert due.good == "oil" and due.taken > 0
    ruined = load_scenario("ugarit", SEED)
    harbour = ruined.court.institutions["harbour_mahadu"]
    institutions = dict(ruined.court.institutions)
    institutions[harbour.id] = dataclasses.replace(
        harbour, condition=0)
    ruined = dataclasses.replace(
        ruined, court=dataclasses.replace(
            ruined.court, institutions=institutions))
    ruined, events = advance(ruined)
    empty = next(event for event in events
                 if isinstance(event, A.HarbourDueTaken))
    assert empty.taken == 0 < due.taken
    assert before > world.court.stores["oil"]  # upkeep remains larger than due


def test_merchants_answer_a_raised_harbour_due_only_after_three_to_six_turns():
    world = load_scenario("ugarit", SEED)
    opening = {actor: world.relations[actor].esteem
               for actor in world.revenue_merchants}
    world, _ = apply(world, A.SetHarbourDue(300))
    decisions = [item for item in world.schedule
                 if isinstance(item.payload, A.MerchantResponseDue)]
    assert len(decisions) == len(world.revenue_merchants)
    assert all(3 <= item.at - world.date.absolute <= 6 for item in decisions)
    first_due = min(item.at for item in decisions)
    while world.date.absolute < first_due - 1:
        world, _ = advance(world)
    assert {a: world.relations[a].esteem for a in opening} == opening
    old_traffic = world.court.harbour_traffic
    world, events = advance(world)
    withdrawn = [e for e in events if isinstance(e, A.MerchantWithdrew)]
    assert withdrawn
    assert world.court.harbour_traffic < old_traffic
    assert any(world.relations[a].esteem < opening[a] for a in opening)


def test_appointing_and_dismissing_really_fills_and_vacates_the_post():
    world = load_scenario("ugarit", SEED)
    world, events = apply(
        world, A.PlacePerson("talmi_teshub", "harbour_mahadu"))
    event = events[0]
    assert event.displaced == "harbourmaster"
    assert world.court.institutions["harbour_mahadu"].head == "talmi_teshub"
    assert world.court.house["talmi_teshub"].post == "harbour_mahadu"
    assert "harbour_mahadu" in world.court.house["talmi_teshub"].interests
    world, events = apply(world, A.DismissPerson("harbour_mahadu"))
    assert events == [A.PersonDismissed("talmi_teshub", "harbour_mahadu")]
    assert world.court.institutions["harbour_mahadu"].head == ""
    assert world.court.house["talmi_teshub"].post == ""


def test_competence_changes_decay_and_loyalty_changes_the_report():
    able = load_scenario("ugarit", SEED)
    loyal = load_scenario("ugarit", SEED)
    able, _ = apply(able, A.PlacePerson("talmi_teshub", "harbour_mahadu"))
    loyal, _ = apply(loyal, A.PlacePerson("yarim_limu", "harbour_mahadu"))
    able_inst = able.court.institutions["harbour_mahadu"]
    loyal_inst = loyal.court.institutions["harbour_mahadu"]
    # Talmi is able but less loyal: the fabric lasts and his report flatters it.
    assert institution._decay_for(able.court, able_inst) < institution._decay_for(
        loyal.court, loyal_inst)
    assert institution.reported_condition(
        able.court, able_inst, SEED, 1) > able_inst.condition
    assert institution.reported_condition(
        loyal.court, loyal_inst, SEED, 1) == loyal_inst.condition


def test_placement_generalizes_to_governorship_command_and_foreign_court():
    world = load_scenario("ugarit", SEED)
    world, _ = apply(world, A.PlacePerson(
        "talmi_teshub", "governor:ma_hadu"))
    assert world.court.house["talmi_teshub"].location == "ma_hadu"
    world, _ = apply(world, A.PlacePerson(
        "talmi_teshub", "command:household_troops"))
    formation = next(f for f in world.court.formations
                     if f.id == "household_troops")
    assert formation.commander == "talmi_teshub"
    world, _ = apply(world, A.PlacePerson(
        "talmi_teshub", "court:carchemish_viceroy"))
    assert world.court.house["talmi_teshub"].location == "carchemish"
    assert "talmi_teshub" in world.relations


def test_naming_the_younger_son_costs_legitimacy_and_arms_the_elder_faction():
    world = load_scenario("ugarit", SEED)
    before = world.court.legitimacy
    world, events = apply(world, A.NameHeir("ibiranu"))
    assert events == [A.HeirNamed("ibiranu", 2)]
    assert world.court.named_heir == "ibiranu"
    assert world.court.legitimacy == before - 60
    assert world.court.faction_mood["elder_prince"] == 60
    assert house.succession_score(
        world, world.court.house["ibiranu"]) > house.succession_score(
            world, world.court.house["niqmaddu"])


def test_naming_the_first_son_has_no_displacement_penalty():
    world = load_scenario("ugarit", SEED)
    before = world.court.legitimacy
    world, events = apply(world, A.NameHeir("niqmaddu"))
    assert events == [A.HeirNamed("niqmaddu", 1)]
    assert world.court.legitimacy == before
    assert not world.court.faction_mood


def test_revenue_and_placement_cross_the_belief_boundary_without_hidden_truth():
    world = load_scenario("ugarit", SEED)
    world, _ = apply(world, A.PlacePerson(
        "talmi_teshub", "harbour_mahadu"))
    belief = project(world)
    assert belief["revenue"]["land_rate"] == 300
    talmi = next(p for p in belief["house"]["members"]
                 if p["id"] == "talmi_teshub")
    assert talmi["post"] == "harbour_mahadu"
    assert talmi["competence"] == "capable"
    assert "truth" not in repr(belief)


def test_the_windowed_house_exposes_people_offices_and_controls():
    world = load_scenario("ugarit", SEED)
    screen = household.compose(
        project(world), "talmi_teshub", 86, 34)
    text = plain_text(screen)
    assert "Talmi-Teshub" in text
    assert "THE OFFICES" in text
    assert "name heir" in text
    assert "land due" in text and "harbour" in text


def test_new_actions_and_delayed_payloads_round_trip_through_the_log_registry():
    values = (
        A.SetLandDue(350), A.SetHarbourDue(150),
        A.PlacePerson("talmi_teshub", "walls_seat"),
        A.DismissPerson("walls_seat"), A.NameHeir("niqmaddu"),
        A.MerchantResponseDue("sinaranu", -2, -6),
    )
    assert tuple(A.from_dict(A.to_dict(value)) for value in values) == values
