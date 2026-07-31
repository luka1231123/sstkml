"""The crown's ground stands in the registry (Task 2, C4).

Only the ground crosses here, not the season. The court still sows and reaps
its estates through `engine/land.py`; what changes is that the kernel now knows
the extent and the holder, so the audit can count the crown's land on both
sides instead of on neither.
"""
from engine.kernel import seat_people as SP
from load import load_scenario


def _world():
    return load_scenario("ugarit", seed=1)


def _estate_sites(world):
    return {site_id: site for site_id, site in world.kernel.registry.sites.items()
            if site_id.startswith("site:estate_")}


def test_every_court_estate_is_a_registry_site():
    world = _world()
    sites = _estate_sites(world)
    assert sorted(sites) == sorted(f"site:estate_{e}" for e in world.court.estates)
    assert sites, "the court has estates; the registry should have them too"


def test_the_extents_agree_in_qa_of_seed():
    """`Site.extent` is qa of seed; the court holds iku and a rate per iku."""
    world = _world()
    sites = _estate_sites(world)
    for estate_id, estate in world.court.estates.items():
        site = sites[f"site:estate_{estate_id}"]
        assert site.extent == estate.area_iku * estate.seed_per_iku


def test_no_estate_stands_at_a_place_the_map_does_not_have():
    """Two of the four name places the live map lost; they stand at the seat.

    The same answer `enrol` gives the garrison. A site at a settlement the
    registry has no row for is invisible to everything that walks the map,
    which is worse than standing in the wrong town.
    """
    world = _world()
    settlements = world.kernel.registry.settlements
    for site in _estate_sites(world).values():
        assert site.settlement in settlements


def test_the_ground_is_held_by_the_crown_and_counted_as_arable():
    world = _world()
    crown = world.kernel.controller(SP.SEAT)
    for site in _estate_sites(world).values():
        assert site.holder == crown
        # "food" is the vocabulary's word for arable. The audit read "estate"
        # here until C4 and so counted the crown's land as nothing.
        assert site.function == "food"


def test_capacity_stays_unmodelled_so_nothing_sows_the_field_twice():
    """`farm.under_crop` returns 0 for a site with no capacity.

    Deliberate: the court is already sowing this ground. A capacity invented
    here would put two agronomies over one field, which is the mistake C3
    caught late in the ration roll.
    """
    world = _world()
    for site in _estate_sites(world).values():
        assert site.capacity == 0
