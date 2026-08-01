import dataclasses

from engine.kernel import politics
from load import load_campaign


def test_every_alu_resolves_to_one_owner_and_king():
    kernel = load_campaign("seat", 1).kernel
    for settlement in sorted(kernel.registry.settlements):
        assert kernel.owner(settlement) is not None
        assert kernel.king(settlement) is not None


def test_succession_changes_the_king_not_the_owner():
    kernel = load_campaign("seat", 1).kernel
    owner = kernel.owner("settlement:seat")
    registry = politics.succeed(
        kernel.registry, owner.id, "person:hatti_king")
    changed = dataclasses.replace(kernel, registry=registry)

    assert changed.owner("settlement:seat").id == owner.id
    assert changed.king("settlement:seat").id == "person:hatti_king"


def test_capture_changes_the_owner_and_therefore_the_king():
    kernel = load_campaign("seat", 1).kernel
    registry = politics.capture(
        kernel.registry, "settlement:seat", "polity:hattusa")
    changed = dataclasses.replace(kernel, registry=registry)

    assert changed.owner("settlement:seat").id == "polity:hattusa"
    assert changed.king("settlement:seat").id == "person:hatti_king"
    assert "settlement:seat" in registry.holdings("polity:hattusa")
