"""World forges cannot take metal they do not own."""

import dataclasses

from engine import seat
from engine.kernel import arms
from load import load_campaign


def test_foreign_forges_do_not_consume_the_crowns_metal():
    world = load_campaign("seat", 1)
    before = seat.held(world)

    kernel, _events = arms.step(world.kernel)
    after = seat.held(dataclasses.replace(world, kernel=kernel))

    assert after.get("copper", 0) == before.get("copper", 0)
    assert after.get("tin", 0) == before.get("tin", 0)
