"""Dues quote known arithmetic without pretending to know the future."""
from __future__ import annotations

import dataclasses

from belief import dues
from belief.project import project
from engine import actions as A
from engine import revenue, systems
from load import load_campaign


SEED = 8814402919


def test_land_forecast_prices_the_known_assessment_and_recurring_pressure() -> None:
    world = load_campaign("seat", SEED)
    belief = project(world)
    basis = belief["forecast_basis"]["land"]
    live = belief["land"]["land_due_rate"]
    # Twenty-six makes this fixture exercise the households-first remainder:
    # the crown keeps the unit that cannot be divided among the villages.
    drafted = live + 26

    quoted = dues.forecast(belief, "land", drafted)
    take = (basis["assessable"]
            - basis["assessable"] * (1000 - drafted) // 1000)
    live_take = (basis["assessable"]
                 - basis["assessable"] * (1000 - live) // 1000)

    assert quoted["take"] == take
    assert quoted["delta"] == take - live_take
    assert quoted["pressure"] == (
        max(0, drafted - belief["land"]["land_due_base"])
        // world.revenue_rules["unrest_divisor"]
    )
    assert quoted["unroofed"] == max(
        0, belief["stores"]["grain"] + take
        - systems.granary_capacity(world))
    assert quoted["approximate"] is True


def test_harbour_forecast_separates_the_take_from_the_delayed_response() -> None:
    world = load_campaign("seat", SEED)
    belief = project(world)
    assessment = revenue.harbour_assessment(world)

    quoted = dues.forecast(belief, "harbour", 200)

    assert quoted["take"] == revenue.harbour_take(assessment, 200) == 62
    assert quoted["delta"] == 31
    assert quoted["esteem_loss_each"] == 5
    assert quoted["affected_merchants"] == 2
    assert quoted["traffic_loss"] == 30
    assert quoted["delay_min"] == 3
    assert quoted["delay_max"] == 6
    assert quoted["pending"] == 0


def test_harbour_forecast_counts_old_responses_without_repricing_them() -> None:
    world = load_campaign("seat", SEED)
    world, _ = revenue.set_harbour_due(world, 125)
    belief = project(world)

    quoted = dues.forecast(belief, "harbour", 150)

    assert quoted["esteem_loss_each"] == 1
    assert quoted["affected_merchants"] == 2
    assert quoted["traffic_loss"] == 6
    assert quoted["pending"] == 2
    assert quoted["pending_traffic_loss"] == 6
    assert quoted["traffic_after"] == 988


def test_harbour_forecast_respects_idle_crews_and_the_traffic_floor() -> None:
    world = load_campaign("seat", SEED)
    cohorts = dict(world.kernel.registry.cohorts)
    crew = cohorts["cohort:mahadu_garrison"]
    cohorts[crew.id] = dataclasses.replace(crew, reaping=True)
    world = dataclasses.replace(
        world,
        court=dataclasses.replace(world.court, harbour_traffic=5),
        kernel=dataclasses.replace(
            world.kernel, registry=dataclasses.replace(
                world.kernel.registry, cohorts=cohorts)))

    quoted = dues.forecast(project(world), "harbour", 200)

    assert quoted["take"] == 0
    assert quoted["clearable"] == 0
    assert quoted["traffic_loss"] == 5
    assert quoted["traffic_after"] == 0
    assert quoted["approximate"] is True


def test_harbour_assessment_is_the_same_arithmetic_collection_uses() -> None:
    world = load_campaign("seat", SEED)
    assessment = revenue.harbour_assessment(world)

    customary, events = revenue.collect_harbour(world)
    customary_taken = sum(
        event.taken for event in events
        if isinstance(event, A.HarbourDueTaken))
    assert revenue.harbour_take(assessment, 100) == customary_taken
    assert customary.court.last_harbour_due == customary_taken

    raised, _ = revenue.set_harbour_due(world, 200)
    raised, events = revenue.collect_harbour(raised)
    raised_taken = sum(
        event.taken for event in events
        if isinstance(event, A.HarbourDueTaken))
    assert revenue.harbour_take(assessment, 200) == raised_taken
    assert raised.court.last_harbour_due == raised_taken


def test_forecasts_do_not_read_seeded_response_dates_or_unseen_climate() -> None:
    opening = load_campaign("seat", SEED)
    seeded = []
    forecasts = []
    for seed in (1, 8):
        world = dataclasses.replace(
            opening, kernel=dataclasses.replace(opening.kernel, seed=seed))
        committed, _ = revenue.set_harbour_due(world, 200)
        seeded.append(tuple(item.at for item in committed.schedule))
        forecasts.append(dues.forecast(project(world), "harbour", 200))
    assert seeded == [(4, 5), (6, 6)]
    assert forecasts[0] == forecasts[1]

    world = load_campaign("seat", SEED)
    now = world.date.absolute
    hidden_drought = {
        region: series[:now + 1] + (0,) * (len(series) - now - 1)
        for region, series in world.kernel.region_climate.items()
    }
    changed = dataclasses.replace(
        world, kernel=dataclasses.replace(
            world.kernel, region_climate=hidden_drought))
    rate = project(world)["land"]["land_due_rate"] + 25
    assert dues.forecast(project(world), "land", rate) == dues.forecast(
        project(changed), "land", rate)
