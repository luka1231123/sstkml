"""What a correspondent *claims*, as against what is true (spec 6.8, 8.6).

This is the second and separate layer of unreliability, and it must not be
confused with the first:

  * `belief/distortion.py` is the SCRIBE. He copies faithfully and sometimes
    slips. His errors corrupt the ruler's BELIEF; the tablet itself is right.
  * this module is the SENDER. He is frightened, or ambitious, or covering a
    shortfall. His distortion is part of the WORLD -- the tablet really does
    say twenty ships. No amount of counting at home recovers the truth; only
    another source does.

So the bias is applied once, at generation, and both the asserted and the true
figures are carried on the Letter. Belief projects only the asserted ones. The
model is handed the asserted ones and never sees the others, which is what makes
Law 1 hold: it cannot leak a truth it was never told.

Integer-only and pure, like everything else under engine/.
"""
from __future__ import annotations

from engine.core import stream

# Bias is permille of the true value and may exceed 1000: a terrified governor
# reporting three times the ships he can see is the interesting case, not an
# outlier. Beyond this the letters stop reading as testimony and start reading
# as farce.
MAX_BIAS = 3000


def _magnitude(bias: int, seed: int, turn: int, actor: str, key: str) -> int:
    """Deterministic jitter in [bias//2, bias]. A constant multiplier would be
    learnable in three letters -- 'halve whatever Abdi-milki says' -- which is a
    puzzle, not a judgement. Varying it keeps the player weighing the source."""
    bias = max(0, min(MAX_BIAS, bias))
    if bias == 0:
        return 0
    span = bias - bias // 2
    if span <= 0:
        return bias
    return bias // 2 + stream(seed, turn, "report.bias", f"{actor}:{key}").int(span + 1)


def assert_value(value: int, bias: int, direction: int, seed: int, turn: int,
                 actor: str, key: str) -> int:
    """The figure the sender puts on the tablet.

    direction: +1 he inflates it (threats, enemies, his own need), -1 he plays
    it down (his own strength, his own stores), 0 he has no reason to lie.
    An honest correspondent (bias 0) asserts the truth in every direction.
    """
    if direction == 0 or value == 0 or bias <= 0:
        return value
    m = _magnitude(bias, seed, turn, actor, key)
    if m == 0:
        return value
    if direction > 0:
        return value * (1000 + m) // 1000
    # Understatement is the same distortion run the other way, so that a bias of
    # 2000 halves-and-then-some just as it trebles when inflating.
    return max(1, value * 1000 // (1000 + m))


def assert_facts(facts: tuple[tuple[str, object], ...], bias: int,
                 exaggerate: tuple[str, ...], understate: tuple[str, ...],
                 seed: int, turn: int, actor: str) -> tuple[tuple[str, object], ...]:
    """Apply the sender's bias to the numeric facts he is about to assert.

    Non-numeric facts (an enemy's name, a good) pass through: this system lies
    about quantities, which is what a ledger-keeping court can eventually catch.
    Booleans are left alone -- `isinstance(True, int)` is a trap.
    """
    out = []
    for key, value in facts:
        if isinstance(value, int) and not isinstance(value, bool):
            direction = 1 if key in exaggerate else -1 if key in understate else 0
            value = assert_value(value, bias, direction, seed, turn, actor, key)
        out.append((key, value))
    return tuple(out)
