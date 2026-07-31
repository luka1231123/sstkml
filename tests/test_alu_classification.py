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
from tui.grid import plain_text

SEED = 8814402919
SCENARIO = Path(__file__).parent.parent / "content" / "scenarios" / "ugarit.toml"


@pytest.fixture(scope="module")
def world():
    return load_scenario("ugarit", SEED)


def test_every_mark_has_a_classification_and_an_owning_alu(world) -> None:
    alu = {p.id for p in world.places.values() if p.kind == "alu"}
    centres = {p.id for p in world.places.values() if p.kind == "palace_centre"}
    assert alu | centres == set(world.places)
    assert len(alu) == 42 and len(centres) == 6

    for place in world.places.values():
        assert place.kind in ("alu", "palace_centre")
        if place.kind == "palace_centre":
            assert place.alu in alu
        else:
            assert place.alu == ""

    for site in world.sites:
        assert site.role in ("palace_centre", "capacity")
        assert site.alu in alu, f"site at {site.col},{site.row} owns to nothing"
        assert bool(site.capacity) == (site.role == "capacity")

    counted = collections.Counter(site.role for site in world.sites)
    assert counted == {"capacity": 121, "palace_centre": 66}


def test_an_unowned_or_unclassified_mark_is_a_load_error(tmp_path) -> None:
    """The fault the classification exists to make impossible."""
    text = SCENARIO.read_text()

    orphan = text.replace('alu = "egypt"', 'alu = "atlantis"', 1)
    assert orphan != text
    with pytest.raises(ValueError, match="atlantis"):
        _load_text(orphan, tmp_path / "orphan")

    unclassified = text.replace('kind = "grain"\nrole = "capacity"',
                                'kind = "grain"\nrole = ""', 1)
    assert unclassified != text
    with pytest.raises(ValueError, match="role"):
        _load_text(unclassified, tmp_path / "unclassified")


def _load_text(text: str, root: Path):
    """Load an edited scenario through the real loader, with real content."""
    root.mkdir(parents=True, exist_ok=True)
    for item in loader.CONTENT.iterdir():
        if item.name != "scenarios":
            (root / item.name).symlink_to(item)
    (root / "scenarios").mkdir()
    (root / "scenarios" / "ugarit.toml").write_text(text)
    real = loader.CONTENT
    try:
        loader.CONTENT = root
        return loader.load_scenario("ugarit", SEED)
    finally:
        loader.CONTENT = real


def test_demoted_towns_keep_their_people_and_are_counted_once(world) -> None:
    """Ma'hadu's people did not evaporate: they are Ugarit's, and only once."""
    for centre in ("ma_hadu", "gibala", "gla", "tiryns", "ura", "sippar"):
        place = world.places[centre]
        assert place.kind == "palace_centre"
        assert place.population == 0 and place.susceptible == 0

    assert world.places["seat"].population == 11700       # 8000 + 2500 + 1200
    assert world.places["mycenae"].population == 15000    # 10000 + 5000
    assert world.places["thebes_gr"].population == 9000   # 7000 + 2000
    assert world.places["tarhuntassa"].population == 9000  # 6000 + 3000

    living = sum(p.susceptible + p.infected + p.recovered
                 for p in world.places.values())
    assert living == sum(p.population for p in world.places.values())


def test_ugarit_still_reaches_the_sea_through_its_own_harbour(world) -> None:
    harbours = [p for p in world.places.values()
                if p.harbour and p.alu == "seat"]
    assert [p.id for p in harbours] == ["ma_hadu"]
    # A route may end at a palace centre. If the loader ever refuses one,
    # Ugarit silently stops being a coastal city.
    assert any({route.a, route.b} == {"ma_hadu", "seat"}
               for route in world.routes)
    assert any(route.mode == "sea" and "ma_hadu" in (route.a, route.b)
               for route in world.routes)


def test_the_authored_import_sickens_the_alu_that_holds_the_harbour(world
                                                                   ) -> None:
    """The tablet lands travellers at Ma'hadu; the people are Ugarit's."""
    authored = tomllib.loads(SCENARIO.read_text())["plague"]
    assert authored["import_place"] == "ma_hadu"
    assert world.plague.import_place == "seat"

    sick = world
    for _ in range(12):
        sick, events = advance(sick)
    began = [e for e in events if isinstance(e, A.PlagueBegan)]
    assert [e.place_id for e in began] == ["seat"]
    seat = sick.places["seat"]
    assert seat.susceptible + seat.infected + seat.recovered + seat.dead == 11700
    assert plague.infected_places(sick) == ("seat",)


def test_every_alu_is_reachable_from_the_seat(world) -> None:
    edges: dict[str, set[str]] = collections.defaultdict(set)
    for route in world.routes:
        edges[route.a].add(route.b)
        edges[route.b].add(route.a)

    seen, queue = {"seat"}, ["seat"]
    while queue:
        for onward in sorted(edges[queue.pop()]):
            if onward not in seen:
                seen.add(onward)
                queue.append(onward)

    alu = {p.id for p in world.places.values() if p.kind == "alu"}
    assert alu - seen == set(), "an Alu no courier can reach is not in the world"


def test_the_tablet_draws_holdings_as_holdings(world) -> None:
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

    # And the palace centre itself says whose it is rather than pretending to
    # a rank of its own.
    drawn = plain_text(worldmap.compose(belief, 104, 30,
                                        selected_place="ma_hadu"))
    assert "a palace centre of Ugarit" in drawn
    assert "a town under Hatti" not in drawn
