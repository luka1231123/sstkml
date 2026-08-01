"""Deterministic climate readings."""
from __future__ import annotations

from engine.core import lerp_table, stream


def series(seed: int, turns: int,
           curve: tuple[tuple[int, int], ...] = ()) -> tuple[int, ...]:
    rng = stream(seed, 0, "climate")
    out = []
    for turn in range(turns):
        baseline = lerp_table(curve, turn // 24) if curve else 100
        current = (baseline + rng.int(41) - 20
                   if turn % 24 == 0 else out[-1] if out else baseline)
        out.append(max(0, min(200, current + rng.int(17) - 8)))
    return tuple(out)


def gauge(world) -> int:
    index = world.kernel.climate_at(
        world.date.absolute, world.kernel.region_of(world.kernel.seat_goods.seat))
    return max(0, index * 3 // 10)
