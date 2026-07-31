"""M8 land and metal: climate, the yield formula, labour, canals, the bronze
chain, and the melt ledger that nothing announces."""
from __future__ import annotations

import dataclasses
import json

from belief.project import project
from engine import actions as A
from engine import metal
from engine.legacy import land
from engine.core import lerp_table, state_hash
from engine.reduce import apply
from engine.state import Formation, MetalState, Workshop
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
    """Precomputed for deterministic agriculture, not privileged prophecy."""
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


# --- the season (spec 3.2, 6.4) ----------------------------------------------

def test_the_canal_falls_off_a_cliff_below_three_hundred():
    """Spec 6.4: one year of neglect is recoverable, two are not."""
    world = _run(1)
    table = world.land_tables["canal_response"]
    assert lerp_table(table, 1000) == 1000
    assert lerp_table(table, 400) > lerp_table(table, 300) * 5 // 4
    assert lerp_table(table, 200) < lerp_table(table, 300) // 2


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

def test_personnel_hold_while_equipped_capability_falls():
    """People remain, but an unequipped formation cannot keep full capability."""
    world = load_scenario("ugarit", SEED)
    opening = {f.id: f.strength for f in world.court.formations}
    for _ in range(72):
        world, _ = advance(world)
    chariotry = next(f for f in world.court.formations if f.id == "chariotry")
    assert {f.id: f.strength for f in world.court.formations} == opening, (
        "equipment failure must not silently kill personnel")
    assert chariotry.replacement_rate < 1000, "the floor was never crossed"
    assert chariotry.ready < chariotry.strength
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
    # C4: the court no longer holds its fields, so the room is empty until
    # the belief re-points at C5.
    assert belief["land"] == {}
    # Everything about how the yield is made is absent.
    blob = json.dumps(belief)
    for hidden in ("base_yield", "standing_yield", "water_response",
                   "labour_response", "seed_response", "climate_sum", "pest"):
        assert hidden not in blob, f"{hidden} reached the player"


def test_the_overseers_are_silent_while_the_estates_are_away():
    """C4: the estate letters read the crown's fields, which are the kernel's
    ground now; they come back with the re-point at C5."""
    world = _run(20)
    assert not any(
        letter.sender.startswith("overseer_") for letter in world.inbox)


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
# The two M8 balance runs are archived at tests/archive/obsolete_m8_balance.py:
# C4 moved the crown's fields to the kernel, so the court mirror has no grain
# income and a scripted run drains to zero whatever the payroll does. They
# return, re-tuned, when the kernel feed re-points at C5.

