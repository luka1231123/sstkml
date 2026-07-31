"""What the seat holds, for the court's own systems (Task 2 C2).

`engine.kernel.seat_goods` is the seam; this is the doorway the court walks
through it. The systems that spend the seat's goods -- metal, works, revenue,
institutions, the terms of a letter -- ask `held` for the figures and hand the
result to `put`, and from there the Book is what the answer came out of.

`Court.stores` is still written, as a mirror. It is read by belief projection,
by the interface, and by a long tail of tests, and those move in C5; until they
do, a system that updated only one of the two records would leave the other
saying something false for the rest of the turn. Writing both from one place is
what keeps the overlap honest, and it is one line to delete when the mirror
goes.

A world with no kernel falls back to the flat mapping. Tests build courts
directly, without a scenario behind them, and a system that raised on those
would be untestable in isolation for the sake of a migration.
"""
from __future__ import annotations

import dataclasses

from engine.entity import GoodId
from engine.kernel import seat_goods as SG
from engine.state import World


def _view(world: World):
    kernel = getattr(world, "kernel", None)
    return kernel.seat_goods if kernel is not None else None


def held(world: World) -> dict[GoodId, int]:
    """The seat's stores, out of the Book. A fresh mapping, safe to mutate."""
    view = _view(world)
    if view is None:
        return dict(world.court.stores)
    return SG.in_hand(world.kernel.book, view)


def put(world: World, stores: dict[GoodId, int], *,
        reason_down: str = "consumed", reason_up: str = "authored",
        authority: str = "") -> World:
    """Record what a system decided about the seat's stores.

    `reason_down` and `reason_up` are why the goods left or entered the world,
    and a caller that knows should say: rations are `consumed`, a smelt is
    `melted` one way and `produced` the other. The defaults are the honest
    answer for a system whose flat arithmetic never said.
    """
    court = dataclasses.replace(world.court, stores=dict(stores))
    view = _view(world)
    if view is None:
        return dataclasses.replace(world, court=court)
    book, view = SG.settle(world.kernel.book, view, stores,
                           reason_down=reason_down, reason_up=reason_up,
                           authority=authority)
    kernel = dataclasses.replace(world.kernel, book=book, seat_goods=view)
    return dataclasses.replace(world, court=court, kernel=kernel)


def record(world: World, court, **why) -> World:
    """Put a court back on the world, and its stores through the seam.

    For the systems that still take and return a bare `Court` -- spoilage,
    rites, rations. They cannot reach the Book from where they stand, so the
    caller carries their figures across, and the Book is in step again before
    anything downstream reads it.
    """
    world = dataclasses.replace(world, court=court)
    return put(world, dict(court.stores), **why)
