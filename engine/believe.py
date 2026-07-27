"""What an actor holds to be true (spec 5.8, 10.11).

Engine-internal and quite separate from `belief/`, which projects the player's
court and is the only World-to-player boundary. This is the same idea turned
inward: every actor in the world decides from its own claims, and those claims
are dated, sourced, and often wrong.

Three rules do the work.

A `Claim` records where it came from and when it was observed, not merely what
it says. "Ma'hadu had four thousand qa" is useless without "as of six
fortnights ago, from a carrier who was told it in a wineshop".

Conflicts are kept. Two claims that disagree both stay, because an actor
holding contradictory reports is the ordinary case and resolving it silently
would be the engine deciding what a person concluded.

A deduction records its inputs and does not overwrite them. Belief grows; it is
not corrected in place.
"""
from __future__ import annotations

import dataclasses

from engine.entity import EntityId

# How a claim came to be held. Closed, because "how do you know that" must
# always have an answer the inspector can print.
SOURCES = frozenset({
    "observed",    # the holder was there and saw it
    "reported",    # someone told the holder
    "inferred",    # the holder concluded it from other claims
    "assumed",     # the holder has no evidence and is going on custom
})

# How the holder came by an observation. Bounds what it could have seen.
METHODS = frozenset({"present", "counted", "inspected", "overheard", "read"})


class BeliefError(ValueError):
    """A claim that cannot say where it came from."""


@dataclasses.dataclass(frozen=True)
class Observation:
    """What an actor could perceive at a place and time, with its limits."""
    id: str
    observer: EntityId
    subject: EntityId
    attribute: str
    value: int
    turn: int
    method: str = "present"
    place: EntityId = ""

    def __post_init__(self) -> None:
        if self.method not in METHODS:
            raise BeliefError(f"unregistered observation method: {self.method!r}")


@dataclasses.dataclass(frozen=True)
class Claim:
    """What an actor asserts, and everything needed to weigh it."""
    id: str
    holder: EntityId
    subject: EntityId
    attribute: str
    value: int
    source: str
    observed_turn: int          # when the underlying fact was seen
    received_turn: int          # when this holder came to hold it
    chain: tuple[EntityId, ...] = ()    # who it passed through, in order
    basis: tuple[str, ...] = ()         # observation or claim ids behind it
    confidence: int = 1000              # scaled 1000

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise BeliefError(f"unregistered claim source: {self.source!r}")
        if self.source == "inferred" and not self.basis:
            raise BeliefError(f"{self.id}: an inference must name its inputs")

    def age(self, now: int) -> int:
        """Fortnights between the fact and the present. Never negative."""
        return max(0, now - self.observed_turn)


@dataclasses.dataclass(frozen=True)
class Belief:
    """One actor's claims. Append-only, and contradictions are allowed to stand."""
    holder: EntityId
    claims: tuple[Claim, ...] = ()

    def add(self, *claims: Claim) -> "Belief":
        for claim in claims:
            if claim.holder != self.holder:
                raise BeliefError(
                    f"{claim.id} is held by {claim.holder!r}, not {self.holder!r}")
        return dataclasses.replace(self, claims=self.claims + claims)

    def about(self, subject: EntityId, attribute: str = "") -> tuple[Claim, ...]:
        return tuple(c for c in self.claims
                     if c.subject == subject
                     and (not attribute or c.attribute == attribute))

    def best(self, subject: EntityId, attribute: str) -> Claim | None:
        """The claim this actor would act on: freshest, then most confident.

        Not "the true one" -- the actor has no access to that. Ties break on
        claim id so that two equally fresh, equally trusted reports resolve the
        same way on every machine.
        """
        candidates = self.about(subject, attribute)
        if not candidates:
            return None
        return max(candidates,
                   key=lambda c: (c.observed_turn, c.confidence, c.id))

    def value(self, subject: EntityId, attribute: str,
              default: int = 0) -> int:
        claim = self.best(subject, attribute)
        return default if claim is None else claim.value

    def conflicts(self, subject: EntityId, attribute: str) -> bool:
        values = {c.value for c in self.about(subject, attribute)}
        return len(values) > 1

    def stale(self, now: int, older_than: int) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.age(now) > older_than)


def infer(belief: Belief, claim_id: str, subject: EntityId, attribute: str,
          value: int, inputs: tuple[Claim, ...], turn: int) -> Belief:
    """Add a conclusion. Its inputs stay exactly where they were."""
    if not inputs:
        raise BeliefError(f"{claim_id}: an inference must name its inputs")
    return belief.add(Claim(
        id=claim_id, holder=belief.holder, subject=subject, attribute=attribute,
        value=value, source="inferred",
        observed_turn=min(c.observed_turn for c in inputs),
        received_turn=turn, basis=tuple(c.id for c in inputs),
        confidence=min(c.confidence for c in inputs)))
