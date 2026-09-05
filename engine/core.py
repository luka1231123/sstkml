"""Determinism primitives: typed ids, substream RNG, calendar, canonical JSON, hashing.

stdlib only. This module is the whole project's insurance policy (spec Part 2).
Nothing here reads the clock, the filesystem, the network, or a global RNG.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from hashlib import blake2b

MASK64 = (1 << 64) - 1

# --- IDs ---------------------------------------------------------------------
# Spec 1.3 wants typed newtypes. In practice they are opaque authored strings;
# we keep them as `str` and lean on naming (place_id, actor_id) for clarity.
# NewType would add friction without catching real bugs in a dynamic pipeline.

# --- RNG: substreams, never a sequence (spec 2.2) ----------------------------

# Every draw names a domain. Typos must fail loudly, not spawn a silent stream.
DOMAINS: frozenset[str] = frozenset({
    "climate",
    "climate.drought",
    "names",
    "scribe.error",
    "letters.interception",
    "plague.transmission",
    "house.conception",
    "divination",
    "rivals",
    "displacement",
    "world.shock",
    "world.raid",
    "relations.patron_notice",
    "report.bias",
    "house.mortality",
    "house.sex",
    "succession",
    "justice.correction",
    "revenue.merchant",
    # M13.1 kernel (spec 10.10). Its own domain, so that adding a draw to the
    # kernel cannot perturb any of the single-city systems above.
    "kernel.hunger",
    # M13.2: whether a crossing arrives. Keyed by the voyage, so that adding a
    # second ship in a fortnight does not change what happened to the first.
    "kernel.voyage",
})


class Rng:
    """SplitMix64. Small, fast, no state stored in World (spec 2.2)."""

    __slots__ = ("s",)

    def __init__(self, seed: int) -> None:
        self.s = seed & MASK64

    def _next(self) -> int:
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def int(self, n: int) -> int:
        """Uniform in [0, n). Rejection sampling to kill modulo bias."""
        if n <= 0:
            raise ValueError("Rng.int needs n > 0")
        limit = MASK64 - (MASK64 % n)
        while True:
            x = self._next()
            if x <= limit:
                return x % n

    def pick(self, seq):
        return seq[self.int(len(seq))]

    def chance(self, num: int, den: int) -> bool:
        """True with probability num/den. num<=0 never, num>=den always."""
        if num <= 0:
            return False
        if num >= den:
            return True
        return self.int(den) < num

    def weighted(self, pairs: tuple[tuple[object, int], ...]):
        """pairs = ((item, weight), ...); weights are non-negative ints."""
        total = sum(w for _, w in pairs)
        if total <= 0:
            raise ValueError("weighted needs positive total weight")
        r = self.int(total)
        acc = 0
        for item, w in pairs:
            acc += w
            if r < acc:
                return item
        return pairs[-1][0]  # unreachable, guards float drift that can't happen


def stream(seed: int, turn: int, domain: str, key: str = "") -> Rng:
    if domain not in DOMAINS:
        raise KeyError(f"unregistered rng domain: {domain!r}")
    h = blake2b(f"{seed}|{turn}|{domain}|{key}".encode(), digest_size=8).digest()
    return Rng(int.from_bytes(h, "big"))


# --- Calendar (spec Part 3): one engine unit, the fortnight -------------------

@dataclasses.dataclass(frozen=True)
class Date:
    year: int        # regnal year of the current ruler
    fortnight: int   # 1..24
    absolute: int    # turns since scenario start; engine-only, never rendered

    def advance(self) -> "Date":
        f = self.fortnight + 1
        y = self.year
        if f > 24:
            f = 1
            y += 1
        return Date(year=y, fortnight=f, absolute=self.absolute + 1)


def in_range(fortnight: int, span: tuple[int, ...]) -> bool:
    """Seasonal flag membership. Spans are inclusive fortnight ranges or lists.

    A 2-tuple [a,b] is a range; anything else is an explicit membership list.
    Ranges may wrap the year end (a > b), e.g. growing = [23, 7].
    """
    if len(span) == 2:
        a, b = span
        if a <= b:
            return a <= fortnight <= b
        return fortnight >= a or fortnight <= b
    return fortnight in span


def lerp_table(table: tuple[tuple[int, int], ...], x: int) -> int:
    """Integer linear interpolation over authored, sorted points (spec 2.3)."""
    if not table:
        raise ValueError("lerp_table needs at least one point")
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) // max(1, x1 - x0)
    return table[-1][1]


# --- Canonical JSON + hashing (spec 2.3, 2.4, 2.5) ---------------------------

class _Float(Exception):
    pass


def _canon(obj):
    """Recursively convert to JSON-ready primitives with total ordering.

    Rejects floats and sets (spec 2.5). Dataclasses become dicts tagged with
    their type. Mappings and dataclass fields are emitted in sorted key order.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, str):
        return obj
    if obj is None:
        return None
    if isinstance(obj, float):
        raise _Float(f"float reached canonical_json: {obj!r}")
    if isinstance(obj, (set, frozenset)):
        raise TypeError("sets are not canonicalizable; use a sorted tuple")
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {"_t": type(obj).__name__}
        for f in dataclasses.fields(obj):
            out[f.name] = _canon(getattr(obj, f.name))
        return out
    if isinstance(obj, Mapping):
        return {str(k): _canon(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (tuple, list)):
        return [_canon(v) for v in obj]
    raise TypeError(f"cannot canonicalize {type(obj).__name__}")


def canonical_json(obj) -> str:
    import json
    return json.dumps(_canon(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def state_hash(world) -> str:
    # rng_ledger is debug-only and excluded from the hash (spec 4.0 state model).
    payload = _canon(world)
    if isinstance(payload, dict):
        payload.pop("rng_ledger", None)
    import json
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return "b3:" + blake2b(blob.encode(), digest_size=16).hexdigest()
