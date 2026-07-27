"""M8 land and metal: climate, the yield formula, labour, canals, the bronze
chain, and the melt ledger that nothing announces."""
from __future__ import annotations

import dataclasses
import json

from belief.project import project
from engine import actions as A
from engine import land, metal
from engine.core import lerp_table, state_hash
from engine.reduce import apply
from engine.state import Estate, Formation, MetalState, Workshop
from engine.tick import advance
from load import load_scenario
from session import replay, save
from tools.balance import run as balance_run

SEED = 8814402919


def _run(turns: int, seed: int = SEED):
    world = load_scenario("ugarit", seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


# --- the climate series (spec 6.4) -------------------------------------------

def test_the_whole_climate_is_fixed_before_turn_one():
    """Precomputed at scenario start, so a bad year was always going to be a bad
    year -- and so divination (6.11) can read a true future value."""
    a = load_scenario("ugarit", SEED)
    assert len(a.climate) == 30 * 24
    assert all(0 <= value <= 200 for value in a.climate)
    # Same seed, same future. Different seed, different future.
    assert load_scenario("ugarit", SEED).climate == a.climate
    assert load_scenario("ugarit", SEED + 1).climate != a.climate
    # Nothing that happens in play perturbs it.
    played = _run(40)
    assert played.climate == a.climate
    # The authored drought curve bends it: the late years are drier than the first.
    early = sum(a.climate[:24 * 3]) // (24 * 3)
    late = sum(a.climate[24 * 9:24 * 12]) // (24 * 3)
    assert late < early - 10, f"the downturn is not in the series ({early} -> {late})"


def test_climate_never_reaches_belief_or_a_prompt():
    world = _run(14)
    blob = json.dumps(project(world))
    assert "climate" not in blob
    for value in world.climate[:40]:
        # The gauge is a lossy proxy; the index itself must not be readable.
        assert f'"index": {value}' not in blob


# --- the yield formula (spec 6.4) --------------------------------------------

def test_the_yield_formula_is_evaluated_strictly_left_to_right():
    """Spec 6.4 demands this order and says to document it, because integer
    floor division is not associative. Grouping the multiplications first
    silently inflates every harvest in the game, so it is pinned here."""
    world = _run(1)
    estate = world.court.estates["royal_lands"]
    got = land.estate_yield(world, estate)

    mean = estate.climate_sum // estate.climate_turns
    water = lerp_table(world.land_tables["water_response"], mean)
    need = estate.area_iku * estate.labour_days_per_iku
    labour = lerp_table(world.land_tables["labour_response"],
                        1000 * estate.labour_days_supplied // need)
    rec = estate.area_iku * estate.seed_per_iku
    seed = lerp_table(world.land_tables["seed_response"],
                      1000 * estate.seed_sown // rec)

    value = estate.area_iku * estate.base_yield_per_iku
    value = value * water // 1000
    value = value * labour // 1000
    value = value * seed // 1000
    value = value * 1000 // 1000          # canal: not irrigated
    value = value * estate.pest // 1000
    assert got == value

    # Why the order is worth pinning: integer floor division is not
    # associative, so grouping the multiplications is a different function.
    # Ugarit's authored areas happen to divide cleanly and the two agree there,
    # which is exactly why this is demonstrated on numbers that do not -- a
    # scenario whose figures are less tidy would diverge silently.
    step_by_step = 7 * 999 // 1000 * 999 // 1000
    grouped = 7 * 999 * 999 // 1_000_000
    assert step_by_step == 5 and grouped == 6


def test_a_dry_year_and_a_short_sowing_both_cut_the_yield():
    world = _run(1)
    estate = world.court.estates["royal_lands"]
    full = land.estate_yield(world, estate)

    drought = land.estate_yield(world, dataclasses.replace(
        estate, climate_sum=55 * estate.climate_turns))
    assert drought < full // 2, "a drought must be ruinous, not an inconvenience"

    half_sown = land.estate_yield(world, dataclasses.replace(
        estate, seed_sown=estate.seed_sown // 2))
    assert full // 3 < half_sown < full * 2 // 3, "land sown at half rate yields about half"

    no_hands = land.estate_yield(world, dataclasses.replace(
        estate, labour_days_supplied=0))
    assert no_hands == 0


def test_the_canal_falls_off_a_cliff_below_three_hundred():
    """Spec 6.4: one year of neglect is recoverable, two are not."""
    world = _run(1)
    table = world.land_tables["canal_response"]
    assert lerp_table(table, 1000) == 1000
    assert lerp_table(table, 400) > lerp_table(table, 300) * 5 // 4
    assert lerp_table(table, 200) < lerp_table(table, 300) // 2


# --- the season (spec 3.2, 6.4) ----------------------------------------------

def test_the_season_runs_sow_grow_harvest_thresh_once_a_year():
    world = load_scenario("ugarit", SEED)
    sown = harvested = threshed = 0
    for _ in range(48):
        world, events = advance(world)
        for event in events:
            sown += isinstance(event, A.Sown)
            harvested += isinstance(event, A.Harvested)
            threshed += isinstance(event, A.Threshed)
    assert threshed == 2, "exactly one threshing floor a year"
    assert sown == 2 and harvested == 2 * len(world.court.estates)


def test_last_harvest_survives_the_whole_threshing_window():
    """Regression. The threshing window is two fortnights wide and the season
    close ran unguarded, so `last_harvest` -- the player's one hard datum about
    his own land -- was zeroed on the window's second turn."""
    world = load_scenario("ugarit", SEED)
    opening = world.court.last_harvest
    assert opening > 0, "the predecessor's harvest must exist on turn one"
    seen = []
    for _ in range(30):
        world, _ = advance(world)
        seen.append(world.court.last_harvest)
    assert 0 not in seen, "last_harvest was zeroed mid-window"
    assert world.court.last_harvest != opening, "a new year must replace it"


def test_the_seed_is_in_the_ground_for_most_of_the_year():
    """Opening the game with seed both sown and sitting in the granary double
    counted it, and made `eat seed` a free action the next threshing quietly
    undid. The store is only stocked between threshing and sowing."""
    world = load_scenario("ugarit", SEED)
    assert world.court.stores["seed_grain"] == 0
    assert sum(e.seed_sown for e in world.court.estates.values()) > 0
    stocked = []
    for _ in range(24):
        world, _ = advance(world)
        if world.court.stores["seed_grain"]:
            stocked.append(world.date.fortnight)
    assert stocked and set(stocked) <= set(range(12, 19)), (
        f"seed sat in the store outside the f12-f18 window: {sorted(set(stocked))}")


def test_eating_the_seed_is_paid_for_at_the_threshing_floor():
    """The purest collapse mechanic in the game: free now, ruinous 19 turns on."""
    def play(eat_qa: int) -> int:
        world = load_scenario("ugarit", SEED)
        for _ in range(40):
            world, _ = advance(world)
            # Fortnight 15: the store is full, the sowing is four turns off,
            # and nothing about eating it costs anything today.
            if eat_qa and world.date.fortnight == 15:
                world, _ = apply(world, A.EatSeed(eat_qa))
        return world.court.last_harvest

    whole = play(0)
    halved = play(42000)
    assert halved < whole * 7 // 10, (
        f"eating half the seed barely moved the harvest ({whole} -> {halved})")


# --- labour (spec 6.4) -------------------------------------------------------

def test_sending_a_group_to_the_fields_is_one_action_and_adds_hands():
    world = _run(2)
    before = land.labour_supplied(world.court, 12)
    world, events = apply(world, A.SendToHarvest("garrison_mahadu", True))
    after = land.labour_supplied(world.court, 12)
    assert after > before
    assert any(isinstance(e, A.SentToHarvest) for e in events)
    world, _ = apply(world, A.SendToHarvest("garrison_mahadu", False))
    assert land.labour_supplied(world.court, 12) == before


def test_starving_the_field_hands_costs_next_years_harvest():
    """The feedback the whole system is for: it takes a season to arrive."""
    def play(pay: bool) -> int:
        world = load_scenario("ugarit", SEED)
        for _ in range(40):
            world, _ = advance(world)
            if not pay:
                world, _ = apply(world, A.Allocate("field_hands", 0))
        return world.court.last_harvest

    assert play(False) < play(True) * 8 // 10


def test_corvee_buys_labour_with_unrest():
    world = _run(2)
    unrest = world.court.unrest
    world, events = apply(world, A.RaiseCorvee(4000))
    assert world.court.corvee_days == 4000
    assert world.court.unrest > unrest
    assert any(isinstance(e, A.CorveeRaised) for e in events)
    # Capped per season, and the cap is refused outright rather than silently
    # clamped to nothing -- a levy that raises no one should say so.
    cap = world.land_rules["corvee_max_days"]
    world, _ = apply(world, A.RaiseCorvee(cap))
    assert world.court.corvee_days == cap
    try:
        apply(world, A.RaiseCorvee(1))
        raise AssertionError("the corvee cap was not enforced")
    except ValueError:
        pass


def test_a_canal_may_only_be_dredged_at_low_water():
    world = _run(1)
    estates = dict(world.court.estates)
    estates["royal_lands"] = dataclasses.replace(
        estates["royal_lands"], irrigated=True, canal_condition=200)
    world = dataclasses.replace(
        world, court=dataclasses.replace(world.court, estates=estates))
    try:
        apply(world, A.DredgeCanal("royal_lands", 1000))
        raise AssertionError("dredged at high water")
    except ValueError:
        pass
    # Roll to the low-water window and it works.
    while world.date.fortnight not in range(14, 19):
        world, _ = advance(world)
    condition = world.court.estates["royal_lands"].canal_condition
    world, events = apply(world, A.DredgeCanal("royal_lands", 2000))
    assert world.court.estates["royal_lands"].canal_condition > condition
    assert any(isinstance(e, A.CanalDredged) for e in events)


def test_an_unirrigated_estate_has_no_canal_to_neglect():
    world = _run(30)
    for estate in world.court.estates.values():
        assert not estate.irrigated
        assert estate.canal_condition == 1000, "dryland canals must not decay"


# --- the bronze chain (spec 6.5) ---------------------------------------------

def test_tin_is_the_chokepoint():
    """bronze = min(copper // 9, tin) * 10. A mountain of copper and no tin
    makes no bronze at all, and that is the entire design."""
    assert metal.smelt(900, 100) == (1000, 900, 100)
    assert metal.smelt(900, 10) == (100, 90, 10)      # tin-bound
    assert metal.smelt(90, 100) == (100, 90, 10)      # copper-bound
    assert metal.smelt(1_000_000, 0) == (0, 0, 0)     # no tin, no bronze


def test_the_melt_ledger_only_ever_rises_and_records_every_melt():
    """Circulation is no longer conserved -- it wears down and is made up.

    What is still exact: the ledger never falls, every shekel that leaves
    circulation *by melting* lands on it, and the forge never builds a hoard
    above what the court has hands and uses for.
    """
    world = _run(1)
    ledger = world.court.metals.melt_ledger
    ceiling = world.court.metals.in_service_ceiling
    for _ in range(70):
        before = world.court.metals.bronze_in_circulation
        world, events = advance(world)
        metals = world.court.metals
        assert metals.melt_ledger >= ledger, "the melt ledger may never fall"
        melted = sum(e.amount for e in events
                     if isinstance(e, A.BronzeMelted))
        assert metals.melt_ledger - ledger == melted, (
            "every shekel melted must land on the ledger, and nothing else")
        ledger = metals.melt_ledger
        assert 0 <= metals.bronze_in_circulation <= ceiling, (
            "the forge maintains the kit; it does not accumulate a hoard")
        assert metals.bronze_in_circulation <= before + 600, (
            "circulation cannot rise by more than the forge can make")


def test_starving_the_smiths_loses_the_army_rather_than_saving_it():
    """The inversion the 32-seed sweep found, locked shut.

    Before attrition, cutting the forge collapsed demand, so nothing was
    smelted, nothing was melted, and circulation sat at its opening figure for
    the whole run -- chariotry ended at a perfect 1000 on exactly the seeds
    where the smiths went unpaid. Starving the workshops preserved the army,
    which is the opposite of what 6.5 is for.
    """
    world = _run(1)
    for group_id in world.court.dependents:
        world, _ = apply(world, A.Allocate(group_id, 0))
    for _ in range(60):
        world, _ = advance(world)
    metals = world.court.metals
    assert metals.bronze_in_circulation < metals.in_service_ceiling, (
        "an unpaid forge must still lose the kingdom's bronze")
    chariotry = next(f for f in world.court.formations if f.id == "chariotry")
    assert chariotry.replacement_rate < 1000, (
        "starving the smiths must not preserve the chariotry")


def test_a_fed_forge_with_tin_holds_the_kit_at_its_ceiling():
    """The other half: paying them and having tin is what standing still costs."""
    world = _run(1)
    for _ in range(12):
        world, _ = advance(world)
    metals = world.court.metals
    assert metals.bronze_in_circulation > metals.in_service_ceiling * 9 // 10
    assert world.court.stores.get("tin", 0) < 1800, "the forge must be eating tin"

def test_strength_holds_while_replacement_falls():
    """Spec 6.5's whole point. The player loses the army without losing a
    battle, and the only warning is a number on a page nobody reads."""
    world = load_scenario("ugarit", SEED)
    opening = {f.id: f.strength for f in world.court.formations}
    for _ in range(72):
        world, _ = advance(world)
    chariotry = next(f for f in world.court.formations if f.id == "chariotry")
    assert {f.id: f.strength for f in world.court.formations} == opening, (
        "strength must not fall: that is not how this fails")
    assert chariotry.replacement_rate < 1000, "the floor was never crossed"
    assert world.court.metals.melt_ledger > 0


def test_nothing_announces_the_melt():
    """No event, no footer line, no belief field. The absence is the mechanic."""
    from tui import render
    world = load_scenario("ugarit", SEED)
    for _ in range(60):
        world, events = advance(world)
        lines = " ".join(render.events_lines(events, world.court)).casefold()
        for word in ("melt", "melted", "bronze", "circulation", "replacement"):
            assert word not in lines, f"the footer mentioned {word!r}"
    # And the belief layer shows strength but never the replacement rate.
    belief = project(world)
    assert belief["metal"]["formations"][0]["strength"] > 0
    assert "replacement_rate" not in json.dumps(belief)
    # The ledger IS there, on the stores page, with no emphasis.
    assert belief["metal"]["melt_ledger"] > 0
    assert "melted to date" in render.stores_screen(belief)


def test_starving_the_smiths_slows_the_forge():
    world = _run(4)
    fed, _ = metal.step(world)
    groups = dict(world.court.dependents)
    groups["smiths_palace"] = dataclasses.replace(
        groups["smiths_palace"], output_modifier=200)
    starved, _ = metal.step(dataclasses.replace(
        world, court=dataclasses.replace(world.court, dependents=groups)))
    assert (starved.court.stores["tin"] > fed.court.stores["tin"]
            or starved.court.stores["bronze"] < fed.court.stores["bronze"])


# --- what the player may see (spec 6.4) --------------------------------------

def test_the_player_sees_proxies_and_never_the_formula():
    world = _run(14)
    belief = project(world)
    land_view = belief["land"]
    # The hard datum is true and unmediated.
    assert land_view["last_harvest"] == world.court.last_harvest
    # Everything about how the yield is made is absent.
    blob = json.dumps(belief)
    for hidden in ("base_yield", "standing_yield", "water_response",
                   "labour_response", "seed_response", "climate_sum", "pest"):
        assert hidden not in blob, f"{hidden} reached the player"
    # The gauge is a reading, not the index.
    assert 0 <= land_view["gauge"] <= 100


def test_the_overseers_inflate_need_and_conceal_the_sowing():
    """Spec 6.4's estate letters, carried by M7's report bias."""
    world = _run(20)
    seen = 0
    for letter in world.inbox:
        if not letter.sender.startswith("overseer_"):
            continue
        asserted, true = dict(letter.facts), dict(letter.true_facts)
        if not true:
            continue
        seen += 1
        assert asserted["hands_short"] >= true["hands_short"]
        assert asserted["sown"] <= true["sown"]
    assert seen, "no overseer wrote in 20 turns"


# --- determinism -------------------------------------------------------------

def test_replay_survives_land_and_metal():
    world = load_scenario("ugarit", SEED)
    log, turns = [], 0
    for turn in range(30):
        world, _ = advance(world)
        turns += 1
        if turn == 4:
            for action in (A.SendToHarvest("weavers", True),
                           A.RaiseCorvee(2000), A.EatSeed(1000)):
                world, _ = apply(world, action)
                log.append({"turn": world.date.absolute,
                            "action": A.to_dict(action)})
    save("/tmp/m8_test.json", SEED, "ugarit", turns, log, world)
    assert state_hash(replay("/tmp/m8_test.json")) == state_hash(world)


def test_two_runs_are_byte_identical():
    assert state_hash(_run(40)) == state_hash(_run(40))


# --- balance (spec 10.4) -----------------------------------------------------

def test_the_deficit_is_survivable_by_cutting_and_fatal_by_drifting():
    prudent = balance_run("prudent", 72)["rows"]
    passive = balance_run("passive", 72)["rows"]

    # Drifting empties the granary and maxes unrest: the deficit is real.
    assert any(row["grain"] == 0 for row in passive)
    assert max(row["unrest"] for row in passive) > 900

    # Cutting the payroll to fit survives, at a visible and bounded price.
    assert all(row["grain"] > 0 for row in prudent)
    assert max(row["unrest"] for row in prudent) < 600, (
        "letting one group go must not saturate unrest (see recompute_unrest)")
    assert prudent[-1]["harvest"] > 900_000, "a managed court keeps its harvest"


def test_the_army_becomes_unreplaceable_in_a_well_run_court():
    """M8's stated target: a run where the army becomes unreplaceable and the
    player never noticed. It has to happen in a court that is doing well --
    a court in ruins has stopped commissioning bronze."""
    rows = balance_run("prudent", 72)["rows"]
    pinched = next(r for r in rows if r["chariotry"] < 1000)
    assert 30 < pinched["turn"] < 65, f"pinched at turn {pinched['turn']}"
    assert pinched["grain"] > 0 and pinched["unrest"] < 600, (
        "the squeeze must arrive while the court still looks healthy")
    assert rows[-1]["chariotry"] < 700
    assert rows[-1]["melt"] > rows[-1]["circulation"] // 3
