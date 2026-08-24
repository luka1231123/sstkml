import dataclasses

from belief.project import project
from engine import actions as A
from engine.tick import advance
from load import load_campaign
def test_a_city_falls_cleanly_from_collapse_or_revolt():
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
