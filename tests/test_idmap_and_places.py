"""Which kernel settlement a court place answers to (Task 2 C1).

The court and the kernel name the same world twice, and the join between the
two used to be guessed from the strings: a place was matched if some
settlement's id looked like it. That is wrong in both directions -- it missed
Mari, which answers to Dur Katlimmu, and it would have accepted any settlement
whose name happened to resemble a mark's.

What these pin is that the join is read off the content, that a scenario which
cannot supply it fails to load, and that the id map for the part no rule
derives cannot go stale in silence.
"""
import dataclasses

import pytest

from load import kernel_settlement, load_idmap, load_scenario

SEED = 8814402919


def test_every_court_place_answers_to_a_settlement():
    """The finding the audit used to report twenty-six of, all of them false."""
    world = load_scenario("ugarit", SEED)
    orphans = [place for place in world.places
               if kernel_settlement(world, place)
               not in world.kernel.registry.settlements]
    assert orphans == []


def test_a_mark_answers_to_its_alu_and_not_to_its_own_name():
    """The case the string match could never have got right."""
    world = load_scenario("ugarit", SEED)
    assert kernel_settlement(world, "mari") == "settlement:dur_katlimmu"
    assert kernel_settlement(world, "argos") == "settlement:mycenae"
    assert kernel_settlement(world, "ma_hadu") == "settlement:seat"
    # An Alu answers to itself.
    assert kernel_settlement(world, "byblos") == "settlement:byblos"


def test_a_mark_whose_alu_does_not_exist_fails_to_load():
    """Fails at the content, not at the courier with nowhere to arrive.

    The check lives in `parse_places`, which is why `mint_registry` does not
    repeat it: every mark has a real Alu by the time a registry is minted, and
    every Alu becomes a settlement, so the join holds by construction. This
    pins the rule the derivation rests on.
    """
    import tomllib

    from load import CONTENT, parse_places

    cfg = tomllib.loads((CONTENT / "world.toml").read_text())
    for row in cfg["places"]:
        if row["id"] == "mari":
            row["alu"] = "nowhere"
            break
    else:
        pytest.fail("the scenario no longer has Mari to break")
    with pytest.raises(ValueError, match="palace centre of unknown Alu"):
        parse_places(cfg)


def test_the_id_map_cannot_name_an_entity_that_does_not_exist():
    """A stale name fails on the run that broke it, not when it is first read."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import load

    world = load_scenario("ugarit", SEED)
    with TemporaryDirectory() as directory:
        content = Path(directory) / "kernel"
        content.mkdir()
        (content / "idmap.toml").write_text(
            '[estates]\nnorth_field = "site:no_such_site"\n')
        original = load.CONTENT
        load.CONTENT = Path(directory)
        try:
            with pytest.raises(ValueError, match="do not exist"):
                load_idmap(world.kernel.registry)
        finally:
            load.CONTENT = original


def test_an_empty_section_is_not_an_error():
    """Sections fill as the migration reaches them (C3, C4, C6).

    Empty because its step has not run is a different thing from wrong, and an
    id map that raised on the first would never survive to catch the second.
    """
    world = load_scenario("ugarit", SEED)
    idmap = load_idmap(world.kernel.registry)
    assert idmap == {
        "actors": {},
        "estates": {
            "royal_lands": "site:seat_372_76",
            "siyannu": "site:seat_374_80",
            "ilishtamai": "site:seat_374_82",
            "temple_lands": "site:seat_374_86",
        },
        "institutions": {},
        "groups": {},
    }
