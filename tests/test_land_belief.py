"""The LAND belief reads the kernel's ground, not the court's old estates.

C4 moved the crown's fields to the kernel (`Site(function="estate")`,
`kernel/farm.py`); C5 re-points `belief/project._land` at them. These tests
pin the seam: the estate, its seed, its standing crop and the season all come
from the kernel, and `last_land_due` stays a stable, positive annual figure --
the crop the land gave the crown -- rather than a negative residue of the
year's set-aside.
"""
from __future__ import annotations

from belief.project import project
from engine.kernel import farm as F
from engine.kernel import seat_people as SP
from engine.tick import advance
from load import load_scenario

SEED = 8814402919


def _belief(turns: int) -> tuple[dict, object]:
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return project(world), world


def _seat_site(world):
    kernel = world.kernel
    return kernel.field_site(SP.SEAT, kernel.controller(SP.SEAT))


def test_the_land_reads_the_kernels_estate() -> None:
    belief, world = _belief(16)
    land = belief["land"]
    estates = land["estates"]
    assert len(estates) == 1
    site_id = _seat_site(world)
    site = world.kernel.registry.sites[site_id]
    estate = estates[0]
    assert estate["id"] == site_id
    assert estate["extent"] == site.extent
    assert estate["capacity"] == site.capacity
    # The crown's own field hands, head count, not a share of the seat's.
    assert estate["hands"] > 0


def test_the_stage_is_the_grain_years_stage() -> None:
    belief, world = _belief(24)
    stage = belief["land"]["stage"]
    from engine.kernel.farm import season
    assert season(world.kernel.seasons, world.kernel.date.fortnight, stage)


def test_seed_in_the_ground_matches_the_kernel() -> None:
    belief, world = _belief(24)
    site_id = _seat_site(world)
    assert belief["land"]["seed_in_ground"] == F.under_crop(world.kernel, site_id)
    # What the ground can still take is the open part of the estate.
    site = world.kernel.registry.sites[site_id]
    assert (belief["land"]["seed_recommended"]
            == site.extent - belief["land"]["seed_in_ground"])


def test_last_land_due_is_stable_and_positive_across_a_year() -> None:
    """The floor's grain, whole. It records the harvest, and the seed the crown
    set aside out of its carried grain must not drag the figure below zero."""
    _, world = _belief(16)
    after_first = world.court.last_land_due
    assert after_first > 0
    for _ in range(24):
        world, _ = advance(world)
    assert world.court.last_land_due > 0


def test_seed_in_store_agrees_with_the_storehouse() -> None:
    belief, world = _belief(16)
    assert belief["land"]["seed_in_store"] == belief["stores"]["seed_grain"]
