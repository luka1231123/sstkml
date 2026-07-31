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


def test_a_court_with_no_city_has_no_institutional_output() -> None:
    """Missing infrastructure cannot be more effective than a ruined building."""
    world = _world(1)
    bare = dataclasses.replace(
        world, court=dataclasses.replace(world.court, institutions={}))
    assert I.factor(bare.court, "granary") == 0
    assert I.factor(bare.court, "workshop") == 0


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

    def staffed(condition: int):
        world = _with_condition(_world(1), "tablet_house", condition)
        institutions = dict(world.court.institutions)
        institutions["tablet_house"] = dataclasses.replace(
            institutions["tablet_house"],
            group="household",
            head="steward_granary",
        )
        return dataclasses.replace(
            world, court=dataclasses.replace(
                world.court, institutions=institutions))

    sound = staffed(1000)
    neglected = staffed(200)
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


# --- the city, drawn ----------------------------------------------------------
#
# The skyline is not decoration: it is the condition, restated as a shape, and
# it is drawn from the *reported* figure. These tests hold both claims down.

def test_every_kind_the_screen_names_has_a_building() -> None:
    from tui import art, alu

    for kind in alu.DOES:
        assert kind in art.BUILDINGS, f"{kind} would be drawn as a hovel"
        assert kind in alu.WORD, f"{kind} has no word to stand under it"
    for kind, rows in art.BUILDINGS.items():
        assert art.size(rows)[0] == art.BUILDING_WIDTH, kind
        assert art.size(rows)[1] <= 9, f"{kind} is taller than the sky"


def test_a_building_only_ever_loses_ink_as_it_falls() -> None:
    """The erosion has to be monotone or the picture is lying about the number.

    Counted rather than eyeballed: a weathering step that swapped a glyph for a
    heavier one would read, at a glance, as a building being repaired.
    """
    from tui import art

    for kind, rows in art.BUILDINGS.items():
        weights = {"█": 4, "▓": 3, "▒": 2, "░": 1, " ": 0}
        def ink(condition: int) -> int:
            return sum(weights.get(g, 2) for row in art.weather(rows, condition)
                       for g in row)
        levels = [ink(c) for c in (1000, 800, 600, 400, 200, 0)]
        assert levels == sorted(levels, reverse=True), f"{kind}: {levels}"


def test_a_ruin_is_the_same_ruin_every_time() -> None:
    """No randomness anywhere, including in the holes."""
    from tui import art

    once = art.weather(art.BUILDINGS["walls"], 300)
    twice = art.weather(art.BUILDINGS["walls"], 300)
    assert once == twice


def test_the_skyline_draws_what_the_head_says_not_what_is_so() -> None:
    """A flatterer's quay is drawn sound. That is the whole point of the screen.

    The lie already lives in `condition` by the time Belief hands it over, so
    this asserts the screen does not go behind Belief's back for the truth.
    """
    from tui import alu
    from tui.grid import plain_text

    world = _with_condition(_world(1), "harbour_mahadu", 200)
    world = _with_arrears(world, "garrison_mahadu", 8)
    b = project(world)
    quay = next(i for i in b["institutions"] if i["id"] == "harbour_mahadu")
    assert quay["condition"] > 400, "the harbourmaster should be flattering it"
    honest = [dict(i, condition=200 if i["id"] == "harbour_mahadu"
                   else i["condition"]) for i in b["institutions"]]
    said = plain_text(alu.compose(b))
    truth = plain_text(alu.compose({**b, "institutions": honest}))
    assert said != truth, "the drawing must move when the reported figure does"


def test_the_city_screen_stays_inside_its_frame() -> None:
    from tui import alu
    from tui.grid import plain_text

    b = project(_world(12))
    lines = plain_text(alu.compose(b)).splitlines()
    assert len(lines) == 36
    for line in lines:
        assert len(line) == 96
        assert line[0] in "╔║╚" and line[-1] in "╗║╝", repr(line[-20:])


def test_every_building_carries_the_key_that_opens_it() -> None:
    from tui import alu
    from tui.grid import plain_text

    b = project(_world(4))
    text = plain_text(alu.compose(b))
    for index in range(1, len(b["institutions"][:alu.DRAWN]) + 1):
        assert f"[{index}]" in text
    assert "walls" in text and "temple" in text


def test_a_vacant_post_is_marked_on_the_skyline_and_in_words() -> None:
    from tui import alu
    from tui.grid import plain_text

    b = project(_world(4))
    assert any(not i["head"] for i in b["institutions"])
    text = plain_text(alu.compose(b))
    assert "×" in text and "no one minds it" in text


def test_the_detail_window_stays_inside_its_frame() -> None:
    from tui import alu
    from tui.grid import plain_text

    b = project(_world(20))
    for inst in b["institutions"]:
        lines = plain_text(
            alu.detail(b, inst, inst.get("history"), 68, 22)).splitlines()
        assert len(lines) == 22
        for line in lines:
            assert len(line) == 68 and line[0] in "╔║╚"


def test_the_moon_over_the_city_is_the_half_of_the_month() -> None:
    """The one decoration that is also information (the calendar is lunar)."""
    from tui import alu
    from tui.grid import plain_text

    b = project(_world(1))
    former = plain_text(alu.compose({**b, "date": "yr 1, Ayyaru, former half"}))
    latter = plain_text(alu.compose({**b, "date": "yr 1, Ayyaru, latter half"}))
    assert former != latter, "the moon must turn with the fortnight"
    assert "▄▄▖" in former and "▗▄▄" in latter


def test_the_lower_town_stands_behind_the_great_houses() -> None:
    """`draw` writes nothing where a drawing has a space, so without `occlude`
    the distant town shows through the gate of the walls."""
    from tui import art
    from tui.grid import Surface, plain_text

    surface = Surface(20, 10)
    art.draw(surface, 0, 4, art.town(20))
    art.occlude(surface, 3, 3, art.BUILDINGS["walls"])
    art.draw(surface, 3, 3, art.BUILDINGS["walls"])
    lines = plain_text(surface.freeze()).splitlines()
    for row, line in enumerate(lines[3:10]):
        for column in range(3, 16):
            behind = line[column]
            assert behind in art.BUILDINGS["walls"][row] or behind == " ", (
                f"the town shows through the walls at {column},{row + 3}")


def test_nothing_drawn_reaches_the_list_below_it() -> None:
    """Decoration that leaks into the table is a misread number, eventually."""
    from tui import alu
    from tui.grid import plain_text

    b = project(_world(6))
    lines = plain_text(alu.compose(b)).splitlines()
    for line in lines[16:]:
        # Not the blocks: the sparkline is made of those. The drawn glyphs.
        assert not (set(line) & set("▟▙≈╲╱▲∩◘╫▤▩")), repr(line)


# --- building and repair (6.21) -----------------------------------------------
#
# The load-bearing claim: a building site is not a purchase. It takes the hands
# that would have brought in the harvest, it eats as it goes, and calling it off
# gets nothing back.

def _working_world(turns: int = 14, corvee: int = 6000):
    """A world in the low-water fortnights with the corvée called up and the
    seat holding grain.

    C4 moved the crown's fields to the kernel, so the mirror has no grain
    income of its own; a working world is a fed seat, which is what the kernel
    feed will be once the re-point at C5 lands.
    """
    from engine import seat, works

    world = _world(turns)
    assert works.working_season(world), "these tests need a working season"
    stores = seat.held(world)
    for good in ("grain", "seed_grain", "oil"):
        stores[good] = max(stores.get(good, 0), 2_000_000)
    world = seat.put(world, stores, reason_up="authored")
    world, _ = apply(world, A.RaiseCorvee(corvee))
    return world


def test_the_men_eat_as_they_work_and_calling_them_off_returns_nothing() -> None:
    world, _ = apply(_working_world(), A.BeginRepair("walls_seat"))
    before = world.court.stores["grain"]
    world, _ = advance(world)
    project = next(iter(world.court.projects.values()))
    assert project.spent, "a fortnight of work must have eaten something"
    eaten = dict(project.spent)["grain"]
    world, events = apply(world, A.AbandonWork(project.id))
    assert not world.court.projects
    assert any(isinstance(e, A.WorkAbandoned) for e in events)
    # The grain is gone. Nothing anywhere gives it back.
    spent_total = before - world.court.stores["grain"]
    assert spent_total >= eaten
    world, _ = advance(world)
    assert world.court.stores["grain"] <= before


def test_nothing_happens_out_of_season_and_nothing_says_so() -> None:
    """Mudbrick does not go up in the rains, and no event explains the
    stillness. The number not moving is the whole message (D19)."""
    from engine import works

    world = _working_world()
    # A circuit of walls: 4,000 days, far more than one season can finish, so
    # the project is certain to still be in hand when the rains come.
    world, _ = apply(world, A.BeginBuild("walls", "seat"))
    # Walk to a fortnight outside the working span.
    for _ in range(24):
        world, events = advance(world)
        if not works.working_season(world):
            break
    else:
        raise AssertionError("no closed season found in a whole year")
    done_before = next(iter(world.court.projects.values())).days_done
    world, events = advance(world)
    still = world.court.projects["work1"]
    assert still.days_done == done_before
    assert not [e for e in events if isinstance(e, A.WorkProgressed)]


def test_a_repair_does_not_arrive_at_a_thousand() -> None:
    """The fabric goes on going while the men work, and the player eats the
    difference. That is the cost of having left it so long."""
    world, _ = apply(_working_world(), A.BeginRepair("walls_seat"))
    for _ in range(12):
        world, _ = advance(world)
        if not world.court.projects:
            break
    walls = world.court.institutions["walls_seat"]
    assert walls.condition > 900, "the repair must actually repair"
    assert walls.condition < 1000, "and must not undo the decay it took to do"


def test_something_built_stands_empty_until_somebody_is_placed_over_it() -> None:
    world, _ = apply(_working_world(), A.BeginBuild("granary", "ma_hadu"))
    for _ in range(6):
        world, _ = advance(world)
        if not world.court.projects:
            break
    built = [i for i in world.court.institutions.values()
             if i.place == "ma_hadu" and i.kind == "granary"]
    assert built, "the granary never opened"
    assert built[0].head == "" and built[0].group == ""
    assert built[0].condition < 1000


def test_the_work_cannot_outrun_the_corvee() -> None:
    world = _working_world(corvee=300)
    world, _ = apply(world, A.BeginRepair("walls_seat"))
    world, _ = advance(world)
    assert next(iter(world.court.projects.values())).days_done == 300
    world, _ = advance(world)
    assert next(iter(world.court.projects.values())).days_done == 300, (
        "the pool is empty; the men go home until more are called up")


def test_repairing_what_is_whole_is_refused() -> None:
    world = _with_condition(_working_world(), "walls_seat", 1000)
    try:
        apply(world, A.BeginRepair("walls_seat"))
    except ValueError:
        return
    raise AssertionError("a whole wall wants nothing doing")


def test_the_new_orders_survive_a_save() -> None:
    for action in (A.BeginBuild("granary", "seat"), A.BeginRepair("walls_seat"),
                   A.AbandonWork("work1")):
        assert A.from_dict(A.to_dict(action)) == action


def test_the_works_screen_stays_inside_its_frame() -> None:
    from tui import works as works_page
    from tui.grid import plain_text

    world, _ = apply(_working_world(), A.BeginRepair("walls_seat"))
    world, _ = advance(world)
    b = project(world)
    for pick in ("", "a"):
        lines = plain_text(works_page.compose(b, pick, 82, 32)).splitlines()
        assert len(lines) == 32
        for line in lines:
            assert len(line) == 82 and line[0] in "╔║╚"
    assert "call them off" in plain_text(works_page.compose(b, "a", 82, 32))


def test_a_building_under_repair_wears_its_scaffolding() -> None:
    from tui import alu
    from tui.grid import plain_text

    world = _working_world()
    quiet = plain_text(alu.compose(project(world)))
    world, _ = apply(world, A.BeginRepair("walls_seat"))
    world, _ = advance(world)
    busy = plain_text(alu.compose(project(world)))
    assert "┄" not in quiet and "┄" in busy
    assert "the men are out on" in busy
