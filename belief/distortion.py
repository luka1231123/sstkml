"""The scribe's hand (spec 6.7b). Transcription error corrupts numbers in the
documents the ruler reads. This corrupts BELIEF, never World: the granary really
holds what it holds; the tablet says otherwise. Recovering the truth costs one
hour of attention (`inspect ledger`). This is the correct place to put
unreliability -- in the player's information, not the world's physics.

Deterministic: the corruption is a pure function of (seed, when-transcribed,
document, field), so the same wrong number appears every time the player looks,
and it reproduces exactly on replay.
"""
from __future__ import annotations

from engine.core import stream


def p_error(competence: int, fatigue: int) -> int:
    """Per-number error probability in permille (spec 6.7 formula)."""
    p = fatigue * (1000 - competence) // 1000
    return 0 if p < 0 else 1000 if p > 1000 else p


def transcribe(value: int, seed: int, turn: int, key: str, perr: int,
               sexagesimal: bool = False) -> int:
    """Return the scribe's copy of an integer: usually right, sometimes wrong in
    a realistic way -- a digit transposed, a wedge miscut, or a sexagesimal slip.

    `sexagesimal` marks a bulk quantity written in places (grain in qa), where
    gaining or losing a place is the characteristic error and is dramatic
    precisely because the magnitudes are large. Counted things -- ships, men,
    towns -- are not written that way and must not slip by a factor of sixty.

    Both bugs this guards against were found by M7, when the Voicer first put
    these figures into sentences: three captured towns were copied as 180, and
    thirty-six ships off the coast as 2,160. Neither is a scribal slip. The
    first is a different war and the second is a different century.
    """
    if perr <= 0 or value == 0:
        return value
    rng = stream(seed, turn, "scribe.error", key)
    if not rng.chance(perr, 1000):
        return value
    if value >= 10 and rng.chance(1, 2):          # transpose two adjacent digits
        s = list(str(value))
        i = rng.int(len(s) - 1)
        s[i], s[i + 1] = s[i + 1], s[i]
        return int("".join(s))
    if sexagesimal and value >= 60:
        if rng.chance(1, 2):
            return value // 60                     # dropped a sexagesimal place
        return value * 60                          # added one
    return max(1, value + rng.pick((-2, -1, 1, 2)))  # a wedge too many or too few
