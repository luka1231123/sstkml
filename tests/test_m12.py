"""The city as a machine (spec 6.18, D39).

The load-bearing claim: `DependentGroup` is untouched, and an `Institution` is a
derived layer over it. Every test here either checks that the old system still
behaves exactly as it did, or checks one of the two new multipliers.
"""
from __future__ import annotations

import dataclasses

from belief.project import project
from engine import actions as A
from engine import institution as I
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario

SEED = 8814402919


def _world(turns: int = 0):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _with_arrears(world, group_id: str, fortnights: int):
    group = world.court.dependents[group_id]
    owed = group.size * group.entitlement * fortnights
    groups = dict(world.court.dependents)
    groups[group_id] = dataclasses.replace(group, arrears=owed)
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, dependents=groups))


# --- the entity ---------------------------------------------------------------

def test_the_scenario_authors_a_city() -> None:
    court = _world().court
    assert len(court.institutions) == 6
    kinds = {i.kind for i in court.institutions.values()}
    assert {"harbour", "granary", "workshop", "temple", "walls", "archive"} == kinds


def test_every_institution_names_a_group_or_admits_it_has_none() -> None:
    court = _world().court
    for inst in court.institutions.values():
        assert not inst.group or inst.group in court.dependents


def test_the_fabric_goes_whether_or_not_anyone_is_working() -> None:
    before = _world().court.institutions["walls_seat"].condition
    after = _world(24).court.institutions["walls_seat"].condition
    assert after < before, "an unminded wall must decay"


def test_a_vacant_post_decays_faster_than_a_minded_one() -> None:
    """40 a fortnight was the first pass and it flattened the city in two years.

    What matters is the ordering, not the figure: nobody minding it must always
    be worse than somebody minding it.
    """
    court = _world().court
    walls = court.institutions["walls_seat"]
    assert not walls.head
    minded = dataclasses.replace(walls, head="a_commander")
    assert I._decay_for(court, minded) < I._decay_for(court, walls)


def test_the_city_is_not_rubble_after_a_hundred_turns() -> None:
    """Decay is a pressure, not a countdown."""
    court = _world(96).court
    for inst in court.institutions.values():
        if inst.head:
            assert inst.condition > 400, f"{inst.id} fell apart while minded"


# --- the two multipliers ------------------------------------------------------

def test_effective_output_is_fabric_times_staff() -> None:
    world = _world(1)
    court = world.court
    forge = court.institutions["forge_palace"]
    group = court.dependents[forge.group]
    assert I.effective(court, forge) == (
        forge.capacity * forge.condition // 1000 * group.output_modifier // 1000)


def test_starving_the_staff_reduces_what_the_building_can_do() -> None:
    """Through the real path: `output_modifier` is recomputed at rations, so
    arrears injected by hand do nothing until a fortnight has actually run."""
    world = _world(1)
    world, _ = apply(world, A.Allocate("smiths_palace", 0))
    for _ in range(12):
        world, _ = advance(world)
    starved = world.court.institutions["forge_palace"]
    fed = _world(13)
    assert (I.effective(world.court, starved)
            < I.effective(fed.court, fed.court.institutions["forge_palace"]))


# --- the head who flatters ----------------------------------------------------

def test_a_head_whose_men_are_paid_reports_the_truth() -> None:
    world = _world(1)
    court = world.court
    forge = court.institutions["forge_palace"]
    assert I.reported_condition(court, forge, SEED, 1) == forge.condition


def test_a_head_whose_men_are_unpaid_flatters_the_books() -> None:
    """The lie grows with what he owes them, so the figure is least reliable
    exactly when it matters most (D11 reaching the city)."""
    world = _with_arrears(_world(1), "smiths_palace", 6)
    court = world.court
    forge = court.institutions["forge_palace"]
    assert I.reported_condition(court, forge, SEED, 1) > forge.condition


def test_no_head_ever_reports_a_perfect_thousand() -> None:
    """A flawless quay is a thing nobody has seen; 1000 would become a tell."""
    world = _with_arrears(_world(1), "smiths_palace", 40)
    court = world.court
    for inst in court.institutions.values():
        assert I.reported_condition(court, inst, SEED, 1) <= 960 or not inst.group


# --- belief -------------------------------------------------------------------

def test_belief_shows_what_the_head_said_and_not_what_is_so() -> None:
    world = _with_arrears(_world(1), "smiths_palace", 6)
    forge = world.court.institutions["forge_palace"]
    shown = next(i for i in project(world)["institutions"]
                 if i["id"] == "forge_palace")
    assert shown["condition"] > forge.condition
    assert not shown["inspected"]


def test_an_hour_spent_looking_returns_the_true_figure() -> None:
    world = _with_arrears(_world(1), "smiths_palace", 6)
    world, _ = apply(world, A.InspectLedger("institution:forge_palace"))
    shown = next(i for i in project(world)["institutions"]
                 if i["id"] == "forge_palace")
    assert shown["condition"] == world.court.institutions["forge_palace"].condition
    assert shown["inspected"]


def test_an_inspection_lapses_with_the_fortnight() -> None:
    world = _with_arrears(_world(1), "smiths_palace", 6)
    world, _ = apply(world, A.InspectLedger("institution:forge_palace"))
    world, _ = advance(world)
    shown = next(i for i in project(world)["institutions"]
                 if i["id"] == "forge_palace")
    assert not shown["inspected"]


def test_inspecting_a_thing_that_does_not_exist_is_refused() -> None:
    try:
        apply(_world(1), A.InspectLedger("institution:the_moon"))
    except ValueError:
        return
    raise AssertionError("a nonexistent institution must not be inspectable")


def test_the_reported_history_is_kept_for_its_shape() -> None:
    world = _world(30)
    history = world.court.institution_history["walls_seat"]
    assert len(history) == 24, "twenty-four fortnights, and no more"
    assert history[0] > history[-1], "an unminded wall must sag on the page"


def test_the_old_payroll_is_untouched() -> None:
    """The whole design rests on this: institutions are a layer, not a rewrite."""
    world = _world(40)
    for group in world.court.dependents.values():
        assert 0 <= group.output_modifier <= 1000
        assert group.arrears >= 0
        assert group.size > 0


# --- the outputs, wired ---------------------------------------------------------
#
# Four of the six feed a system that exists. The harbour and the walls do not:
# nothing imports by sea until M13's trade and nothing attacks until M14, and a
# multiplier with no consumer would be a number pretending to be a mechanic.

def _with_condition(world, key: str, condition: int):
    institutions = dict(world.court.institutions)
    institutions[key] = dataclasses.replace(
        institutions[key], condition=condition)
    return dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, institutions=institutions))


def test_a_court_with_no_city_is_unaffected() -> None:
    """Scenarios that author no institutions must play exactly as they did."""
    world = _world(1)
    bare = dataclasses.replace(
        world, court=dataclasses.replace(world.court, institutions={}))
    assert I.factor(bare.court, "granary") == 1000
    assert I.factor(bare.court, "workshop") == 1000


def test_a_ruined_granary_loses_more_grain_and_only_grain() -> None:
    from engine import systems

    sound = _with_condition(_world(1), "granary_seat", 1000)
    ruined = _with_condition(_world(1), "granary_seat", 0)
    _, sound_events = systems.spoilage(sound.court)
    _, ruined_events = systems.spoilage(ruined.court)
    lost = {e.good: e.amount for e in sound_events}
    lost_worse = {e.good: e.amount for e in ruined_events}
    assert lost_worse["grain"] > lost["grain"]
    assert lost_worse.get("wine", 0) == lost.get("wine", 0), (
        "a leaking granary must not spoil the cellar")


def test_a_ruined_forge_melts_faster_rather_than_slower() -> None:
    """The inversion, one level up: scaling *demand* by the forge's condition
    made a collapsing workshop ask for less, melt less, and so preserve the
    army. The fabric caps what can be made, never what the court needs."""
    def melted(condition: int) -> int:
        world = _with_condition(_world(1), "forge_palace", condition)
        world = dataclasses.replace(
            world, court=dataclasses.replace(
                world.court, stores={**world.court.stores, "tin": 400}))
        for _ in range(24):
            world, _ = advance(world)
        return world.court.metals.melt_ledger

    assert melted(200) > melted(1000), "a ruined forge must cost more, not less"


def test_a_neglected_tablet_house_returns_fewer_tablets() -> None:
    from engine import archive

    sound = _with_condition(_world(1), "tablet_house", 1000)
    neglected = _with_condition(_world(1), "tablet_house", 200)
    many = archive.search(sound, "oath")
    few = archive.search(neglected, "oath")
    assert len(few) < len(many)
    assert len(few) >= 2, "a search returning nothing reads as a bug, not neglect"


def test_a_missed_festival_lands_harder_at_a_ruined_temple() -> None:
    from engine import systems

    def after(condition: int):
        world = _with_condition(_world(1), "temple_baal", condition)
        court = dataclasses.replace(
            world.court, stores={g: 0 for g in world.court.stores})
        rite = court.rites[0]
        court, _ = systems.do_rites(court, rite.fortnight)
        return court.legitimacy

    assert after(100) < after(1000), (
        "a temple nobody repaired must make a skipped rite worse")
