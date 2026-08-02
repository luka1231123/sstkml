import dataclasses

from belief.project import project
from engine import actions as A
from engine.tick import advance
from load import load_campaign
from tools.gameplay_probe import run


def test_long_runs_report_every_outcome_without_impossible_state():
    rows = [run(policy, seed, 72)
            for policy in ("passive", "austerity") for seed in (1, 42)]
    assert not [error for row in rows for error in row["errors"]]
    assert all(row["events"] and row["outcomes"] for row in rows)
    assert all(0 <= row["population_ratio_min"] <= 1000 for row in rows)
    assert all(0 <= row["unrest_peak"] <= 1000 for row in rows)

    world = load_campaign("seat", 1)
    cohorts = {cid: (dataclasses.replace(c, people=1, households=1)
                     if c.settlement == "settlement:seat" else c)
               for cid, c in world.kernel.registry.cohorts.items()}
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    world, events = advance(world)
    fall = next(event for event in events if isinstance(event, A.AluFell))
    assert fall.cause == "population collapse" and world.ended
    assert all(not person.alive for person in world.court.house.values())
    assert "seat" not in {p["id"] for p in project(world)["world_graph"]["places"]}

    world = load_campaign("seat", 2)
    target = "settlement:kydonia"
    cohorts = {cid: (dataclasses.replace(c, grievance=1000)
                     if c.settlement == target else c)
               for cid, c in world.kernel.registry.cohorts.items()}
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    world, events = advance(world)
    fall = next(event for event in events
                if isinstance(event, A.AluFell) and event.alu == "kydonia")
    assert fall.cause == "maximum unrest" and not world.ended
    assert world.kernel.king(target) is None
    assert "kydonia" not in {
        p["id"] for p in project(world)["world_graph"]["places"]}
