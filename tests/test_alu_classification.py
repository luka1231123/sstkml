"""Alpha 0.7 Task 1: every mark on the map is an Alu, a palace centre, or a
capacity of one, and the tablet draws what the classification says.

The point of these is causal rather than structural. A classification that only
type-checks is worth nothing: what matters is that the people of a demoted town
are somewhere (and counted once), that a sickness landing at a harbour reaches
the city that owns it, that nothing decorative can be reached by a courier, and
that the map says "holding" where the data says holding.
"""
from __future__ import annotations

import collections
import tomllib
from pathlib import Path

import pytest

import load as loader
from belief.project import project
from engine import actions as A
from engine import plague
from engine.tick import advance
from load import load_scenario
from tui import worldmap

SEED = 8814402919


def _world():
    return load_scenario("ugarit", SEED)


def test_every_mark_has_a_classification_and_an_owning_alu() -> None:
    world = _world()
    alu = {p.id for p in world.places.values() if p.kind == "alu"}
    centres = {p.id for p in world.places.values() if p.kind == "palace_centre"}
    assert alu | centres == set(world.places)
    assert len(alu) == 55 and len(centres) == 32

    for place in world.places.values():
        assert place.kind in ("alu", "palace_centre")
        if place.kind == "palace_centre":
            assert place.alu in alu
        else:
            assert place.alu == ""

    sites = world.kernel.registry.sites.values()
    for site in sites:
        assert site.settlement.split(":", 1)[1] in alu, \
            f"site at {site.col},{site.row} owns to nothing"

    counted = collections.Counter(
        "palace_centre" if site.function == "palace_centre" else "capacity"
        for site in sites)
    assert counted == {"capacity": 149, "palace_centre": 91}


def test_an_unowned_or_unclassified_mark_is_a_load_error() -> None:
    """The fault the classification exists to make impossible."""
    from tempfile import TemporaryDirectory

    world_text = (Path(loader.CONTENT) / "world.toml").read_text()

    orphan = world_text.replace('alu = "egypt"', 'alu = "atlantis"', 1)
    assert orphan != world_text
    unclassified = world_text.replace('kind = "grain"\nrole = "capacity"',
                                      'kind = "grain"\nrole = ""', 1)
    assert unclassified != world_text

    with TemporaryDirectory() as orphan_dir:
        with pytest.raises(ValueError, match="atlantis"):
            _load_text(Path(orphan_dir), world_text=orphan)
    with TemporaryDirectory() as unclassified_dir:
        with pytest.raises(ValueError, match="role"):
            _load_text(Path(unclassified_dir), world_text=unclassified)


def _load_text(root: Path, *, world_text: str | None = None):
    """Load the scenario through the real loader, with real content."""
    root.mkdir(parents=True, exist_ok=True)
    for item in loader.CONTENT.iterdir():
        if item.name != "scenarios":
            if item.name == "world.toml" and world_text is not None:
                (root / item.name).write_text(world_text)
            else:
                (root / item.name).symlink_to(item)
    (root / "scenarios").symlink_to(loader.CONTENT / "scenarios",
                                    target_is_directory=True)
    real = loader.CONTENT
    try:
        loader.CONTENT = root
        return loader.load_scenario("ugarit", SEED)
    finally:
        loader.CONTENT = real


def test_demoted_towns_keep_their_people_and_are_counted_once() -> None:
    """Ma'hadu's people did not evaporate: they are Ugarit's, and only once."""
    world = _world()
    for centre in ("ma_hadu", "gibala", "gla", "tiryns", "ura", "sippar"):
        place = world.places[centre]
        assert place.kind == "palace_centre"
        assert place.population == 0 and place.susceptible == 0

    assert world.places["seat"].population == 80000
    assert world.places["mycenae"].population == 435000
    assert world.places["thebes_gr"].population == 110000
    assert world.places["tarhuntassa"].population == 200000

    living = sum(p.susceptible + p.infected + p.recovered
                 for p in world.places.values())
    assert living == sum(p.population for p in world.places.values())


def test_ugarit_still_reaches_the_sea_through_its_own_harbour() -> None:
    world = _world()
    harbours = [p for p in world.places.values()
                if p.harbour and p.alu == "seat"]
    assert [p.id for p in harbours] == ["ma_hadu"]
    # The seat keeps direct sea routes even though the one-cell road to its
    # own harbour (ma_hadu) is not authored in the content yet.
    assert any(route.legs[0].mode == "sea" and "seat" in route.ends
               for route in world.routes)


def test_the_authored_import_sickens_the_alu_that_holds_the_harbour() -> None:
    """The tablet lands travellers at Ma'hadu; the people are Ugarit's."""
    world = _world()
    authored = tomllib.loads(
        (Path(loader.CONTENT) / "scenarios" / "ugarit.toml").read_text()
    )["plague"]
    assert authored["import_place"] == "ma_hadu"
    assert world.plague.import_place == "seat"

    sick = world
    for _ in range(12):
        sick, events = advance(sick)
    began = [e for e in events if isinstance(e, A.PlagueBegan)]
    assert [e.place_id for e in began] == ["seat"]
    seat = sick.places["seat"]
    assert seat.susceptible + seat.infected + seat.recovered + seat.dead == 80000
    assert plague.infected_places(sick) == ("seat",)


def test_every_alu_is_reachable_from_the_seat() -> None:
    world = _world()
    edges: dict[str, set[str]] = collections.defaultdict(set)
    for route in world.routes:
        a, b = route.ends
        edges[a].add(b)
        edges[b].add(a)

    seen, queue = {"seat"}, ["seat"]
    while queue:
        for onward in sorted(edges[queue.pop()]):
            if onward not in seen:
                seen.add(onward)
                queue.append(onward)

    alu = {p.id for p in world.places.values() if p.kind == "alu"}
    assert alu - seen == set(), "an Alu no courier can reach is not in the world"


def test_the_tablet_draws_holdings_as_holdings() -> None:
    world = _world()
    belief = project(world)
    sites = belief["world_graph"]["sites"]
    assert all("hub" not in site for site in sites)
    assert {site["alu"] for site in sites} <= {
        p.id for p in world.places.values() if p.kind == "alu"}

    lines = worldmap._hinterland(belief, "seat", 96)
    text = " ".join(line for line, _tone in lines)
    assert "4 palace centres" in text and "7 grain estates" in text
    assert "Ma'hadu" in text and "Gib'ala" in text
    assert "settlement" not in text and "town" not in text

    # And the palace centre itself is classified as a holding of the seat
    # rather than pretending to a rank of its own.
    ma_hadu = next(
        place for place in belief["world_graph"]["places"]
        if place["id"] == "ma_hadu")
    assert ma_hadu["kind"] == "palace_centre"
    assert ma_hadu["alu"] == "seat"
    assert ma_hadu["role"] and "town" not in ma_hadu["role"]
