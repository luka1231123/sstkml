"""Agriculture and the climate series (spec 6.4). Graduated from systems.py (D1).

Deterministic and opaque. The whole climate series is fixed at scenario start
so replay never depends on draw order. Agriculture reads the current value;
divination may read current observations and completed records, never ahead in
this series.

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
from engine import seat
from engine.core import in_range, lerp_table, stream
from engine.state import Court, World


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

    Three sources: groups whose standing function is field labour, groups the
    ruler has *ordered* to the harvest at the cost of whatever they normally do,
    and formations tasked to `harvest` (spec 6.4 line 566, D25).

    A group deep in arrears supplies less, through `output_modifier`. Starving
    the people who bring in the harvest is a slow way to lose the harvest, and
    the feedback takes a season to arrive.
    """
    from engine.troops import harvest_hands

    total = 0
    for gid in sorted(court.dependents):
        group = court.dependents[gid]
        if (not group.revolting
                and (group.function == "field_labour"
                     or gid in court.at_harvest)):
            total += group.size * per_head * group.output_modifier // 1000
    return total + harvest_hands(court, per_head)


def corvee_source_capacity(world: World) -> dict[str, int]:
    """Seasonal days the crown can call from named field-labour cohorts."""
    span = world.season.get("growing")
    turns = sum(
        1 for fortnight in range(1, 25)
        if span and in_range(fortnight, tuple(span)))
    turns = max(1, turns)
    per_head = world.land_rules.get("labour_days_per_head", 12)
    return {
        group.id: (
            group.size * per_head * turns * group.output_modifier // 1000)
        for group in sorted(
            world.court.dependents.values(), key=lambda item: item.id)
        if group.function == "field_labour" and not group.revolting
    }


def source_corvee(world: World, requested: int
                  ) -> tuple[int, tuple[tuple[str, int], ...],
                             tuple[tuple[str, int], ...]]:
    """Allocate requested days to real cohorts.

    Returns ``(raised, aggregate_sources, incremental_sources)``.
    """
    existing = dict(world.court.corvee_sources)
    incremental: dict[str, int] = {}
    remaining = max(0, requested)
    for group_id, capacity in sorted(corvee_source_capacity(world).items()):
        available = max(0, capacity - existing.get(group_id, 0))
        take = min(remaining, available)
        if take:
            existing[group_id] = existing.get(group_id, 0) + take
            incremental[group_id] = take
            remaining -= take
        if remaining <= 0:
            break
    raised = requested - remaining
    return (
        raised,
        tuple(sorted(existing.items())),
        tuple(sorted(incremental.items())),
    )


# --- the yield formula -------------------------------------------------------
def _response(world: World, table: str, x: int) -> int:
    points = world.land_tables.get(table)
    return 1000 if not points else lerp_table(points, x)


def effective_labour_days(world: World, estate: Estate) -> int:
    """Seasonal field days remaining after realized public works."""
    total_area = sum(
        item.area_iku for item in world.court.estates.values()) or 1
    works_share = world.court.works_days * estate.area_iku // total_area
    return max(0, estate.labour_days_supplied - works_share)


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

    # Public works consume the same seasonal field-labour days. Distribute the
    # realized (not merely called-up) days by estate area exactly once here.
    supplied = effective_labour_days(world, estate)
    needed = estate.area_iku * estate.labour_days_per_iku
    labour = _response(world, "labour_response",
                       1000 * supplied // max(1, needed))

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
    stores = seat.held(world)

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
        weighted_area = sum(
            estates[e].area_iku * estates[e].hands for e in estates)
        # Tax flight removes hands from the countryside, not merely from one
        # line in a ledger. Lowering the due stops further flight but cannot
        # conjure the departed households back.
        days = days * weighted_area // max(1, total_area * 1000)
        for eid in sorted(estates):
            estate = estates[eid]
            share = (days * estate.area_iku * estate.hands
                     // max(1, weighted_area))
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
        # guarded on there being an *active season*, not on a positive crop.
        # Guarding on `standing_yield` stranded every seasonal accumulator when
        # drought, seed, or labour produced a genuine zero harvest. Closing
        # unconditionally instead zeroed `last_harvest` again on the window's
        # second turn. The working fields are the one-shot marker for both cases.
        active_season = any(
            estate.seed_sown
            or estate.labour_days_supplied
            or estate.climate_turns
            or estate.standing_yield
            or estate.pest != 1000
            for estate in estates.values()
        )
        total = sum(estates[e].standing_yield for e in estates)
        if active_season:
            from engine.revenue import land_take
            taken = land_take(world, total)
            # Hold next year's seed back before anyone eats a grain of it, but
            # only enough to reach the recommendation -- a court that still has
            # seed does not need to set aside a second year's worth. A player
            # who ate the seed in winter is topped back up here, which is the
            # mercy in the mechanic: one bad decision, not a spiral.
            seed_target = sum(estates[e].area_iku * estates[e].seed_per_iku
                              for e in estates)
            want = max(0, seed_target - stores.get("seed_grain", 0))
            held = min(max(0, total - taken), want)
            stores["grain"] = stores.get("grain", 0) + taken
            stores["seed_grain"] = stores.get("seed_grain", 0) + held
            events.append(A.Threshed(total, held))
            events.append(A.LandDueTaken(
                total, court.land_due_rate, taken))
            # The season closes: the fields are reset and this year's number
            # becomes the hard datum the player reasons from for 24 turns.
            for eid in sorted(estates):
                estates[eid] = dataclasses.replace(
                    estates[eid], seed_sown=0, labour_days_supplied=0,
                    climate_sum=0, climate_turns=0, standing_yield=0, pest=1000)
            court = dataclasses.replace(
                court, previous_harvest=court.last_harvest, last_harvest=total,
                last_land_due=taken,
                at_harvest=(), corvee_days=0, corvee_sources=(), works_days=0)
        elif court.at_harvest or court.corvee_days or court.works_days:
            # The field accumulators were already closed on the first fortnight
            # of the threshing window. Do not record a second zero harvest, but
            # do not let a newly raised seasonal assignment leak into next year.
            court = dataclasses.replace(
                court, at_harvest=(), corvee_days=0,
                corvee_sources=(), works_days=0)

    court = dataclasses.replace(court, estates=estates)
    world = dataclasses.replace(world, court=court)
    # Seed leaves for the furrow and grain arrives off the threshing floor in
    # the same step, so one crossing has to name both. `sown` is the sink that
    # matters here -- it is what spec 2.2 distinguishes from eating -- and the
    # harvest is the one place in the court where goods are honestly produced.
    return seat.put(world, stores, reason_down="sown",
                    reason_up="harvested"), events


def gauge_reading(world: World) -> int:
    """The river gauge or well depth an official reports (spec 6.4).

    A proxy, not the index: it tracks the climate but coarsely and with its own
    error, and the scribe copies it before the ruler reads it. Deliberately
    lossy -- knowing the gauge is not knowing the year.
    """
    index = climate_at(world, world.date.absolute)
    return max(0, index * 3 // 10)
