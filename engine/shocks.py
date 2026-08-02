from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import stream
from engine.kernel import farm as F
from engine.state import Shock, ShockChange, World

KINDS = (
    "drought", "crop_failure", "earthquake", "destructive_sea",
    "epidemic", "route_violence", "political_rupture", "volcanic",
)
FOOD = {"estate", "food"}


def _settlement(world: World, target: str) -> str:
    return target if target.startswith("settlement:") else f"settlement:{target}"


def land(world: World, kind: str, target: str, severity: int,
         duration: int) -> tuple[World, list]:
    if kind not in KINDS:
        raise ValueError(f"unknown shock {kind!r}")
    settlement = _settlement(world, target)
    if settlement not in world.kernel.registry.settlements:
        raise ValueError(f"unknown Alu {target!r}")
    if world.kernel.registry.settlements[settlement].fallen:
        raise ValueError(f"fallen Alu {target!r}")
    severity = max(1, min(900, severity))
    turn = world.date.absolute
    shock_id = f"{turn}:{kind}:{settlement}"
    registry = world.kernel.registry
    sites, routes, orgs = (dict(registry.sites), dict(registry.routes),
                           dict(registry.orgs))
    changes: list[ShockChange] = []

    def set_field(table: str, rows: dict, entity: str, field: str, value) -> None:
        old = rows[entity]
        changes.append(ShockChange(table, entity, field, getattr(old, field)))
        rows[entity] = dataclasses.replace(old, **{field: value})

    local_sites = [i for i, site in sites.items()
                   if site.settlement == settlement]
    local_routes = [i for i, route in routes.items()
                    if any(settlement in (leg.origin, leg.destination)
                           for leg in route.legs)]
    if kind in {"drought", "crop_failure"}:
        book = world.kernel.book
        for site_id in local_sites:
            if sites[site_id].function not in FOOD:
                continue
            if kind == "drought":
                set_field("sites", sites, site_id, "capacity",
                          sites[site_id].capacity * (1000 - severity) // 1000)
            else:
                for lot in tuple(book.at(site_id)):
                    if lot.good == F.STANDING and lot.free:
                        lost = lot.free * severity // 1000
                        if lost:
                            book = book.consume(
                                lot.id, lost, "spoiled", authority=shock_id)
        world = dataclasses.replace(
            world, kernel=dataclasses.replace(world.kernel, book=book))
    elif kind == "earthquake":
        for site_id in local_sites:
            set_field("sites", sites, site_id, "capacity",
                      sites[site_id].capacity * (1000 - severity) // 1000)
        for route_id in local_routes:
            set_field("routes", routes, route_id, "capacity",
                      routes[route_id].capacity * (1000 - severity) // 1000)
    elif kind == "destructive_sea":
        for route_id in local_routes:
            if not any(leg.mode == "sea" for leg in routes[route_id].legs):
                continue
            set_field("routes", routes, route_id, "capacity",
                      routes[route_id].capacity * (1000 - severity) // 1000)
            set_field("routes", routes, route_id, "risk",
                      min(1000, routes[route_id].risk + severity // 2))
    elif kind == "route_violence":
        for route_id in local_routes:
            set_field("routes", routes, route_id, "risk",
                      min(1000, routes[route_id].risk + severity))
    elif kind == "political_rupture":
        controller = world.kernel.controller(settlement)
        if controller:
            set_field("orgs", orgs, controller, "policy", "")
    elif kind == "volcanic":
        region = registry.settlements[settlement].region
        for site_id in sorted(sites):
            site = sites[site_id]
            if site.region == region and site.function in FOOD:
                set_field("sites", sites, site_id, "capacity",
                          site.capacity * (1000 - severity) // 1000)

    registry = dataclasses.replace(
        registry, sites=sites, routes=routes, orgs=orgs)
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, registry=registry))
    shock = Shock(shock_id, kind, settlement, turn, turn + max(1, duration),
                  severity, tuple(changes))
    world = dataclasses.replace(world, shocks=world.shocks + (shock,))
    events = [A.ShockLanded(
        shock.id, kind, settlement, severity, shock.until)]
    if kind == "epidemic":
        from engine import plague
        world, began = plague.begin(world, settlement.split(":", 1)[1])
        events += began
    return world, events


def _recover(world: World) -> tuple[World, list]:
    registry = world.kernel.registry
    tables = {"sites": dict(registry.sites), "routes": dict(registry.routes),
              "orgs": dict(registry.orgs)}
    shocks = []
    events = []
    for shock in world.shocks:
        if shock.recovered_turn >= 0 or shock.until > world.date.absolute:
            shocks.append(shock)
            continue
        for change in shock.changes:
            row = tables[change.table][change.entity]
            current = getattr(row, change.field)
            restored = ((current + change.before) // 2
                        if isinstance(current, int) else change.before)
            tables[change.table][change.entity] = dataclasses.replace(
                row, **{change.field: restored})
        shocks.append(dataclasses.replace(
            shock, recovered_turn=world.date.absolute))
        events.append(A.ShockRecovered(shock.id, shock.target))
    registry = dataclasses.replace(registry, **tables)
    world = dataclasses.replace(
        world, shocks=tuple(shocks),
        kernel=dataclasses.replace(world.kernel, registry=registry))
    return world, events


def step(world: World) -> tuple[World, list]:
    world, events = _recover(world)
    if world.date.absolute < world.pressure_turn:
        return world, events
    rng = stream(world.seed, world.date.absolute, "world.shock", "regional")
    if not rng.chance(80, 1000):
        return world, events
    targets = tuple(s for s in sorted(world.kernel.registry.settlements)
                    if not world.kernel.registry.settlements[s].fallen)
    if not targets:
        return world, events
    target = rng.pick(targets)
    kind = rng.pick(KINDS)
    world, landed = land(
        world, kind, target, 150 + rng.int(351), 2 + rng.int(11))
    return world, events + landed
