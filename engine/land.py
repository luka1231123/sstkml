"""Agriculture and the climate series (spec 6.4). Graduated from systems.py (D1).

Deterministic and opaque. The whole climate series is fixed at scenario start,
before the player has made a single decision, which is what makes divination
able to read a true future value later (6.11) and what makes a bad year a thing
that was always going to happen rather than a thing the dice did to you.

The player never sees any input to the yield formula. He sees a gauge reading
that a tired official copied, letters from overseers who inflate need and
conceal failure, and last year's actual harvest -- which is true, and which is
the only hard datum in the system.

The season runs sowing -> growing -> harvest -> threshing, and each phase reads
state the previous one left. Seed eaten in the winter is not punished when it is
eaten; it is punished at sowing, and the bill arrives at threshing, which is
about nineteen turns after the keystroke.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import in_range, lerp_table, stream
from engine.state import Court, Estate, World


# --- the climate series ------------------------------------------------------
def climate_series(seed: int, turns: int,
                   drought_curve: tuple[tuple[int, int], ...] = ()) -> tuple[int, ...]:
    """Precompute the whole run's climate (spec 6.4). 0..200, 100 = normal.

    An authored drought curve gives the scenario's shape -- the long dry
    downturn of the twelfth century, if that is the story being told -- and the
    seeded noise gives each year its own character. Drawn from a single stream
    at turn 0, so the series is a property of the seed and nothing that happens
    later can perturb it.
    """
    rng = stream(seed, 0, "climate")
    out = []
    for turn in range(turns):
        year = turn // 24
        baseline = lerp_table(drought_curve, year) if drought_curve else 100
        # A year has a character, and fortnights within it wobble around it.
        annual = baseline + rng.int(41) - 20 if turn % 24 == 0 else None
        if annual is not None:
            current = annual
        else:
            current = out[-1] if out else baseline
        value = current + rng.int(17) - 8
        out.append(0 if value < 0 else 200 if value > 200 else value)
    return tuple(out)


def climate_at(world: World, turn: int) -> int:
    """The index for one turn. Falls back to normal past the end of the series
    rather than raising: a long game must not die of arithmetic."""
    if not world.climate:
        return 100
    return world.climate[turn] if 0 <= turn < len(world.climate) else 100


# --- labour ------------------------------------------------------------------
def labour_supplied(court: Court, per_head: int) -> int:
    """Labour-days available to the fields this turn (spec 6.4).

    Four sources: groups whose standing function is field labour, groups the
    ruler has *ordered* to the harvest at the cost of whatever they normally do,
    formations tasked to `harvest` (spec 6.4 line 566, D25), and corvee raised
    outside the lists entirely and paid for in unrest.

    A group deep in arrears supplies less, through `output_modifier`. Starving
    the people who bring in the harvest is a slow way to lose the harvest, and
    the feedback takes a season to arrive.
    """
    from engine.troops import harvest_hands

    total = 0
    for gid in sorted(court.dependents):
        group = court.dependents[gid]
        if group.function == "field_labour" or gid in court.at_harvest:
            total += group.size * per_head * group.output_modifier // 1000
    # The corvée the building site already took is not in the fields. This
    # subtraction is the entire cost of building (6.21): not the goods, the
    # hands, billed a year later at the harvest with nothing to connect it to.
    left = max(0, court.corvee_days - court.works_days)
    return total + harvest_hands(court, per_head) + left


# --- the yield formula -------------------------------------------------------
def _response(world: World, table: str, x: int) -> int:
    points = world.land_tables.get(table)
    return 1000 if not points else lerp_table(points, x)


def estate_yield(world: World, estate: Estate) -> int:
    """Spec 6.4, and the order of operations is load-bearing.

        yield_qa = area_iku * base_yield_per_iku
                 * water // 1000 * labour // 1000 * seed // 1000
                 * canal // 1000 * pest // 1000

    Evaluate strictly left to right. Integer floor division is not associative:
    `a * w // 1000 * l // 1000` and `a * w * l // 1000000` differ, and grouping
    the multiplications first would quietly inflate every harvest in the game.
    The spec says to document this, so: this is the documentation, and
    `tests/test_m8.py` pins it.
    """
    mean_climate = (estate.climate_sum // estate.climate_turns
                    if estate.climate_turns else 100)
    water = _response(world, "water_response", mean_climate)

    needed = estate.area_iku * estate.labour_days_per_iku
    labour = _response(world, "labour_response",
                       1000 * estate.labour_days_supplied // max(1, needed))

    recommended = estate.area_iku * estate.seed_per_iku
    seed = _response(world, "seed_response",
                     1000 * estate.seed_sown // max(1, recommended))

    canal = (_response(world, "canal_response", estate.canal_condition)
             if estate.irrigated else 1000)

    value = estate.area_iku * estate.base_yield_per_iku
    value = value * water // 1000
    value = value * labour // 1000
    value = value * seed // 1000
    value = value * canal // 1000
    value = value * estate.pest // 1000
    return value


# --- A6: the agriculture phase step ------------------------------------------
def step(world: World) -> tuple[World, list]:
    """Sowing, growth, harvest, threshing -- whichever the fortnight calls for."""
    fortnight = world.date.fortnight
    court = world.court
    if not court.estates:
        return world, []

    def phase(name: str) -> bool:
        span = world.season.get(name)
        return bool(span) and in_range(fortnight, tuple(span))

    events: list = []
    estates = dict(court.estates)
    stores = dict(court.stores)

    # Canals decay every turn regardless of season, and are dredged only in the
    # authored low-water window (that action lives in reduce.py).
    decay = world.land_rules.get("canal_decay_per_turn", 60)
    for eid in sorted(estates):
        estate = estates[eid]
        if estate.irrigated and decay:
            estates[eid] = dataclasses.replace(
                estate, canal_condition=max(0, estate.canal_condition - decay))

    if phase("sowing"):
        # Sow from the seed stock, best effort, largest estate first so a short
        # stock produces one properly sown field rather than four starved ones.
        for eid in sorted(estates, key=lambda e: (-estates[e].area_iku, e)):
            estate = estates[eid]
            recommended = estate.area_iku * estate.seed_per_iku
            want = max(0, recommended - estate.seed_sown)
            if want <= 0:
                continue
            take = min(want, stores.get("seed_grain", 0))
            if take <= 0:
                continue
            stores["seed_grain"] = stores.get("seed_grain", 0) - take
            estates[eid] = dataclasses.replace(
                estate, seed_sown=estate.seed_sown + take)
        sown = sum(estates[e].seed_sown for e in estates)
        if sown > sum(court.estates[e].seed_sown for e in court.estates):
            events.append(A.Sown(sown, sum(
                estates[e].area_iku * estates[e].seed_per_iku for e in estates)))

    if phase("growing"):
        index = climate_at(world, world.date.absolute)
        days = labour_supplied(
            dataclasses.replace(court, estates=estates),
            world.land_rules.get("labour_days_per_head", 12))
        # Labour is shared out by area, so a big estate takes the bigger share.
        total_area = sum(estates[e].area_iku for e in estates) or 1
        for eid in sorted(estates):
            estate = estates[eid]
            share = days * estate.area_iku // total_area
            estates[eid] = dataclasses.replace(
                estate,
                climate_sum=estate.climate_sum + index,
                climate_turns=estate.climate_turns + 1,
                labour_days_supplied=estate.labour_days_supplied + share)

    if phase("harvest"):
        world_for_yield = dataclasses.replace(
            world, court=dataclasses.replace(court, estates=estates))
        for eid in sorted(estates):
            estate = estates[eid]
            if estate.standing_yield:
                continue                      # already cut this season
            harvested = estate_yield(world_for_yield, estate)
            estates[eid] = dataclasses.replace(estate, standing_yield=harvested)
            events.append(A.Harvested(eid, harvested))

    if phase("threshing"):
        # The window is more than one fortnight wide, so everything here must be
        # guarded on there actually being a crop on the floor. Closing the season
        # unconditionally zeroed `last_harvest` on the window's second turn, and
        # since that is the player's one hard datum about the land, every
        # decision downstream of it was being made against a nought.
        total = sum(estates[e].standing_yield for e in estates)
        if total:
            stores["grain"] = stores.get("grain", 0) + total
            # Hold next year's seed back before anyone eats a grain of it, but
            # only enough to reach the recommendation -- a court that still has
            # seed does not need to set aside a second year's worth. A player
            # who ate the seed in winter is topped back up here, which is the
            # mercy in the mechanic: one bad decision, not a spiral.
            seed_target = sum(estates[e].area_iku * estates[e].seed_per_iku
                              for e in estates)
            want = max(0, seed_target - stores.get("seed_grain", 0))
            held = min(total, want)
            stores["grain"] -= held
            stores["seed_grain"] = stores.get("seed_grain", 0) + held
            events.append(A.Threshed(total, held))
            # The season closes: the fields are reset and this year's number
            # becomes the hard datum the player reasons from for 24 turns.
            for eid in sorted(estates):
                estates[eid] = dataclasses.replace(
                    estates[eid], seed_sown=0, labour_days_supplied=0,
                    climate_sum=0, climate_turns=0, standing_yield=0, pest=1000)
            court = dataclasses.replace(
                court, previous_harvest=court.last_harvest, last_harvest=total,
                at_harvest=(), corvee_days=0, works_days=0)

    court = dataclasses.replace(court, estates=estates, stores=stores)
    return dataclasses.replace(world, court=court), events


def gauge_reading(world: World) -> int:
    """The river gauge or well depth an official reports (spec 6.4).

    A proxy, not the index: it tracks the climate but coarsely and with its own
    error, and the scribe copies it before the ruler reads it. Deliberately
    lossy -- knowing the gauge is not knowing the year.
    """
    index = climate_at(world, world.date.absolute)
    return max(0, index * 3 // 10)
