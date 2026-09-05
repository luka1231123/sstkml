"""Regional raids reuse people, routes, stores, and the player's formations."""
from __future__ import annotations

import dataclasses

from belief.project import project
from engine import actions as A
from engine import defence, displacement
from engine.reduce import apply
from load import load_campaign
from tui import advice, hall, ledgers, render, worldmap
from tui.grid import plain_text


SEED = 1
ORIGIN = "settlement:carchemish"
TARGET = "settlement:emar"


def _arrive(world):
    cohorts = dict(world.kernel.registry.cohorts)
    party = next(
        cohort for cohort in cohorts.values()
        if cohort.status == "travelling_raider")
    target = party.path[-1]
    cohorts[party.id] = dataclasses.replace(
        party, settlement=target, status="attacker", path=(),
        arrives=world.date.absolute)
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    return dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry)), party.id


def _raid(*, aided: bool = False):
    world = load_campaign("seat", SEED)
    if aided:
        world, _ = apply(world, A.AssignTroops(
            "household_troops", "campaign", "emar"))
    world, launched = defence.start_raid(world, ORIGIN, TARGET, 2600)
    world, party = _arrive(world)
    world, outcome = defence.step(world)
    return world, launched, outcome, party


def test_a_raid_is_existing_people_on_an_existing_route() -> None:
    world = load_campaign("seat", SEED)
    people = sum(cohort.people for cohort in world.kernel.registry.cohorts.values())

    changed, events = defence.start_raid(world, ORIGIN, TARGET, 2600)

    party = next(
        cohort for cohort in changed.kernel.registry.cohorts.values()
        if cohort.status == "travelling_raider")
    assert events == [A.RaidLaunched(ORIGIN, TARGET, 2600, 1, 1)]
    assert party.people == 2600 and party.armed
    assert party.path == (ORIGIN, TARGET)
    assert sum(cohort.people for cohort in
               changed.kernel.registry.cohorts.values()) == people


def test_a_successful_raid_moves_real_goods_and_damages_one_place() -> None:
    opening = load_campaign("seat", SEED)
    before_target = {
        good: opening.kernel.stores(TARGET, good)
        for good in ("grain", "tin", "copper")}
    before_origin = {
        good: opening.kernel.stores(ORIGIN, good)
        for good in ("grain", "tin", "copper")}
    before_capacity = {
        site.id: site.capacity for site in opening.kernel.registry.sites.values()
        if site.settlement == TARGET}

    world, _launched, outcome, party = _raid()

    event = outcome[0]
    assert isinstance(event, A.RaidSucceeded)
    assert isinstance(outcome[1], A.AluFell)
    assert world.kernel.registry.settlements[TARGET].fallen
    assert (event.grain, event.tin, event.copper) == (7_914_000, 100, 750)
    assert world.kernel.stores(ORIGIN, "grain") == \
        before_origin["grain"] + event.grain
    assert world.kernel.stores(TARGET, "tin") == \
        before_target["tin"] - event.tin
    assert world.kernel.stores(ORIGIN, "copper") == \
        before_origin["copper"] + event.copper
    # Grain paid for the fight; metal was only transferred, never minted.
    assert world.kernel.stores(ORIGIN, "tin") + \
        world.kernel.stores(TARGET, "tin") == \
        before_origin["tin"] + before_target["tin"]
    assert world.kernel.registry.sites[event.damaged].capacity < \
        before_capacity[event.damaged]
    assert world.kernel.registry.cohorts[party].status == "travelling_return"


def test_an_occupation_changes_owner_and_leaves_one_garrison() -> None:
    world = load_campaign("seat", SEED)
    former = world.kernel.registry.settlements[TARGET].owner
    conqueror = world.kernel.registry.settlements[ORIGIN].owner
    origin_tin = world.kernel.stores(ORIGIN, "tin")
    target_tin = world.kernel.stores(TARGET, "tin")
    world, launched = defence.start_raid(
        world, ORIGIN, TARGET, 2600, occupy=True)
    world, party = _arrive(world)

    world, outcome = defence.step(world)

    assert launched[0].intent == "occupy"
    assert outcome == [A.AluOccupied("emar", former, conqueror, 2600)]
    settlement = world.kernel.registry.settlements[TARGET]
    assert settlement.owner == conqueror and not settlement.fallen
    occupiers = world.kernel.registry.cohorts[party]
    assert (occupiers.settlement, occupiers.status, occupiers.task,
            occupiers.armed) == (TARGET, "household", "garrison", True)
    assert world.kernel.stores(ORIGIN, "tin") == origin_tin
    assert world.kernel.stores(TARGET, "tin") == target_tin
    emar = next(place for place in project(world)["world_graph"]["places"]
                if place["id"] == "emar")
    assert emar["occupied_by"] == \
        world.kernel.registry.polities[conqueror].name
    assert emar["occupied_turn"] == world.date.absolute
    map_text = plain_text(worldmap.compose(
        project(world), selected_place="emar", width=80, height=27))
    assert "occupied by" in map_text

    # Burning an occupied outlying town does not kill a ruler at his own seat.
    ruler = world.kernel.registry.polities[conqueror].ruler
    from engine import fall
    world, _ = fall.bring_down(world, TARGET, "later sack")
    assert world.kernel.registry.persons[ruler].alive


def test_occupation_intent_survives_the_journey() -> None:
    world, _ = defence.start_raid(
        load_campaign("seat", SEED), ORIGIN, TARGET, 2600, occupy=True)
    party = next(cohort for cohort in world.kernel.registry.cohorts.values()
                 if cohort.status == "travelling_raider")
    date = dataclasses.replace(world.date, absolute=party.arrives)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, date=date))

    arrived, _ = displacement.arrivals(world)

    party = arrived.kernel.registry.cohorts[party.id]
    assert (party.status, party.task) == ("attacker", "occupy")


def test_sending_a_campaign_changes_the_regional_result() -> None:
    unaided, _launched, lost, _party = _raid(aided=False)
    aided, _launched, held, _party = _raid(aided=True)

    assert isinstance(lost[0], A.RaidSucceeded)
    assert isinstance(held[0], A.RaidDefeated)
    assert aided.kernel.stores(TARGET, "tin") > \
        unaided.kernel.stores(TARGET, "tin")
    assert aided.relations["emar_overseer"].esteem == \
        unaided.relations["emar_overseer"].esteem + \
        defence.ALLY_DEFENDED_ESTEEM


def test_a_vassal_abandoned_to_a_raid_loses_regard() -> None:
    world = load_campaign("seat", SEED)
    actor = "person:byblos_king"
    before = world.relations[actor].esteem
    world, _ = defence.start_raid(
        world, "settlement:sidon", "settlement:byblos", 4000)
    world, _party = _arrive(world)

    world, outcome = defence.step(world)

    assert isinstance(outcome[0], A.RaidSucceeded)
    assert world.relations[actor].esteem == \
        before + defence.VASSAL_ABANDONED_ESTEEM


def test_a_ruler_who_raids_the_player_loses_regard() -> None:
    world = load_campaign("seat", SEED)
    actor = "person:amurru_king"
    before = world.relations[actor].esteem
    world, _ = defence.start_raid(
        world, "settlement:amurru", "settlement:seat", 1000)
    world, _party = _arrive(world)

    world, _outcome = defence.step(world)

    assert world.relations[actor].esteem == \
        before + defence.RAIDED_SEAT_ESTEEM


def test_surviving_raiders_return_and_rejoin_their_people() -> None:
    opening = load_campaign("seat", SEED)
    before = opening.kernel.people(ORIGIN)
    world, _launched, _outcome, party_id = _raid()
    party = world.kernel.registry.cohorts[party_id]
    date = dataclasses.replace(world.date, absolute=party.arrives)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, date=date))

    returned, _ = displacement.arrivals(world)

    assert party_id not in returned.kernel.registry.cohorts
    assert returned.kernel.people(ORIGIN) == before


def test_sustained_hunger_can_launch_a_rare_autonomous_raid() -> None:
    world = load_campaign("seat", SEED)
    cohorts = dict(world.kernel.registry.cohorts)
    for cohort in world.kernel.cohorts_of(ORIGIN):
        cohorts[cohort.id] = dataclasses.replace(cohort, hunger=10)
    date = dataclasses.replace(world.date, absolute=55)
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(world, kernel=dataclasses.replace(
        world.kernel, registry=registry, date=date))

    changed, events = defence.launch(world)

    assert events and isinstance(events[0], A.RaidLaunched)
    assert events[0].origin == ORIGIN
    assert any(cohort.status == "travelling_raider"
               for cohort in changed.kernel.registry.cohorts.values())


def test_fortnight_report_says_what_changed_without_a_battle_log() -> None:
    event = A.RaidSucceeded(
        ORIGIN, TARGET, 2600, 2400, 7000, 100, 0, 66, "site:emar")

    lines = render.events_lines(
        [event], load_campaign("seat", SEED).court)

    assert lines == [
        "  Word comes from emar: raiders from carchemish carried off "
        "7,000 grain, 100 tin."]

    lines = render.events_lines(
        [A.AluOccupied("emar", "polity:emar", "polity:carchemish", 2600)],
        load_campaign("seat", SEED).court)
    assert lines == [
        "  emar is occupied by carchemish; 2,600 armed settlers remain there."]


def test_a_raid_on_the_seat_stays_visible_until_it_arrives() -> None:
    world, events = defence.start_raid(
        load_campaign("seat", SEED),
        "settlement:amurru", "settlement:seat", 1000)
    belief = project(world)

    assert len(belief["threats"]) == 1
    assert belief["threats"][0]["origin"] == "amurru"
    assert belief["threats"][0]["remaining"] == 1
    assert hall._counts(belief)["world"] == 1
    concern = next(item for item in advice.concerns(belief)
                   if item.id == "raid")
    assert concern.destination == "muster"
    assert "next fortnight" in concern.reason
    muster = plain_text(ledgers.muster(
        belief, width=80, height=27, hours=8))
    assert "raiders · amurru" in muster and "next" in muster

    report = render.events_lines(events, world.court)
    assert report == [
        "  Raiders from amurru are coming: 1,000 people, due next fortnight."]


def test_a_raid_on_a_correspondent_invites_a_campaign() -> None:
    world, _events = defence.start_raid(
        load_campaign("seat", SEED), ORIGIN, TARGET, 2600)
    belief = project(world)

    threat = belief["threats"][0]
    assert threat["target"] == "emar"
    concern = next(item for item in advice.concerns(belief)
                   if item.id == "raid")
    assert "campaign at emar" in concern.order_prompt
    assert "due at emar" in concern.reason
    muster = plain_text(ledgers.muster(
        belief, selected=f"threat:{threat['id']}",
        width=80, height=27, hours=8))
    assert "send a campaign to emar" in muster
