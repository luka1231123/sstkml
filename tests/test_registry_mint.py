"""mint_registry produces a sound kernel Registry from a scenario (Task 2, C1)."""
import dataclasses
import tomllib
from pathlib import Path

import pytest

from engine.entity import check
from load import CONTENT, mint_registry
from load import load_campaign, parse_places, parse_sites


def _mint():
    name = "seat"
    scenario_cfg = tomllib.loads((CONTENT / "courts" / f"{name}.toml").read_text())
    world_cfg = tomllib.loads((CONTENT / "world.toml").read_text())
    cfg = {**world_cfg, **scenario_cfg}
    places = parse_places(cfg)
    return cfg, mint_registry(places, parse_sites(cfg, places), cfg)


def test_settlement_and_region_counts():
    cfg, registry = _mint()
    assert len(registry.settlements) == 55
    assert len(registry.regions) == 8


def test_seat_is_the_only_non_autonomous_settlement():
    cfg, registry = _mint()
    seat_id = f"settlement:{cfg['seat']}"
    for sid, settlement in registry.settlements.items():
        if sid == seat_id:
            assert settlement.autonomous is False
        else:
            assert settlement.autonomous is True


def test_registry_has_no_referential_faults():
    _, registry = _mint()
    assert check(registry) == ()


def test_every_alu_has_one_local_owner_and_overlordship_is_separate():
    _, registry = _mint()
    assert len(registry.polities) == len(registry.settlements)
    for sid, settlement in registry.settlements.items():
        assert registry.holdings(settlement.owner) == (sid,)
        polity = registry.polities[settlement.owner]
        assert polity.ruler in registry.persons
    assert registry.polities["polity:seat"].overlord == "polity:hattusa"
    assert registry.polities["polity:hattusa"].overlord == ""


def test_routes_are_minted_one_per_scenario_row():
    cfg, registry = _mint()
    assert len(registry.routes) == len(cfg["routes"])
    assert len(registry.routes) > 0


def test_bad_site_function_raises():
    name = "seat"
    cfg = tomllib.loads((CONTENT / "courts" / f"{name}.toml").read_text())
    full = {**tomllib.loads((CONTENT / "world.toml").read_text()), **cfg}
    places = parse_places(full)
    sites = list(parse_sites(full, places))
    index = next(i for i, s in enumerate(sites) if s.role != "palace_centre")
    sites[index] = dataclasses.replace(sites[index], capacity="bogus_resource")
    with pytest.raises(ValueError):
        mint_registry(places, tuple(sites), full)


# --- detail.toml: the numbers the map cannot carry (Task 2, C1) ----------------

def _kernel():
    return load_campaign("seat", seed=1).kernel


def test_the_detail_file_gives_the_ground_its_numbers():
    kernel = _kernel()
    fields = [s for s in kernel.registry.sites.values() if s.function == "food"]
    assert fields
    assert any(s.extent > 0 and s.capacity > 0 for s in fields)
    for site in fields:
        assert site.region in kernel.registry.regions


def test_the_cohort_split_conserves_the_authored_population():
    cfg, registry = _mint()
    kernel = _kernel()
    authored = sum(int(p.get("population", 0)) for p in cfg["places"]
                   if p.get("kind", "alu") == "alu")
    assert sum(c.people for c in kernel.registry.cohorts.values()) == authored
    assert len(kernel.registry.cohorts) > len(registry.cohorts)


def test_every_settlement_has_an_organization_that_decides():
    kernel = _kernel()
    for sid in sorted(kernel.registry.settlements):
        assert kernel.controller(sid), f"{sid} decides nothing"


def test_opening_stores_are_lots_owned_by_the_controller():
    kernel = _kernel()
    for sid in sorted(kernel.registry.settlements):
        assert kernel.stores(sid) > 0, f"{sid} opens with no grain"
    for lot in kernel.book.lots.values():
        assert lot.owner in kernel.registry.orgs


def test_a_tributary_owes_its_overlord_and_a_free_place_owes_nothing():
    kernel = _kernel()
    parties = {o.party for o in kernel.obligations}
    assert kernel.obligations
    for obligation in kernel.obligations:
        assert obligation.party in kernel.registry.settlements
        assert obligation.beneficiary in kernel.registry.polities
    free = [s for s in kernel.registry.settlements if s not in parties]
    assert free


def test_the_weather_is_the_region_s_and_not_the_world_s():
    kernel = _kernel()
    assert len(kernel.region_climate) == len(kernel.registry.regions)
    nile = [kernel.climate_at(t, "region:nile") for t in range(96)]
    levant = [kernel.climate_at(t, "region:north_levant") for t in range(96)]
    assert nile != levant


def test_the_scenario_seasons_reach_the_kernel():
    kernel = _kernel()
    assert kernel.seasons["harvest"] == (8, 11)
    assert kernel.seasons["sowing"]


def test_detail_rows_must_name_entities_the_scenario_made():
    import dataclasses as dc

    from load import load_detail
    _cfg, registry = _mint()
    hollow = dc.replace(registry, settlements={})
    with pytest.raises(ValueError):
        load_detail(hollow)
