"""What an actor means to do, and the snapshot it decided from (spec 10.10).

Two records and one rule.

An `Intent` is a decision, not an act. Producing one changes nothing, which is
what lets every actor in the world decide from the same opening state before
any of them has moved. It carries the authority relied on and the belief basis
it came from, so that spec 11.1's "every distant act links to authority and an
order or policy" is answerable from the record rather than from memory.

A `Snapshot` is the read-only opening world. Phases 3 and 4 receive it and
nothing else. Handing them the accumulating world would quietly restore the
walk-through-the-settlements ordering that `engine.kernel.turn` exists to
prevent -- a later actor would decide against an earlier actor's results.
"""
from __future__ import annotations

import dataclasses

from engine.entity import EntityId

# What an intent asks for. Closed: an unclassified intent is one the allocator
# cannot price and the inspector cannot explain.
KINDS = frozenset({
    "work",        # put person-days into something
    "produce",     # run a production process
    "consume",     # draw stores for a household or body
    "quote",       # offer to buy or sell
    "contract",    # accept a quote on stated terms
    "ship",        # move cargo along a route
    "travel",      # move people along a route
    "render",      # discharge an obligation
    "demand",      # call in an obligation
    "appoint",     # place a person in an office
    "repair",      # maintain an asset or institution
})


class IntentError(ValueError):
    """An intent that cannot be classified, priced, or attributed."""


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """The turn's opening state. Frozen, and handed out rather than the live world."""
    turn: int
    world: object

    def __post_init__(self) -> None:
        if self.turn < 0:
            raise IntentError("a snapshot is taken at a non-negative turn")


def open_turn(world, turn: int) -> Snapshot:
    return Snapshot(turn=turn, world=world)


@dataclasses.dataclass(frozen=True)
class Intent:
    id: str
    actor: EntityId
    kind: str
    turn: int
    # What the intent is about: a site, a route, an obligation, an office.
    subject: EntityId = ""
    quantity: int = 0
    # The exclusive pool this intent will draw from, if any. Empty means the
    # intent competes for nothing and needs no allocation.
    resource: EntityId = ""
    # Which named process within the kind, where the kind alone does not say.
    # Sowing, reaping, and threshing are all `produce` drawing on person-days,
    # and the allocator prices them identically; only the system that issues
    # them cares which is which, so the vocabulary belongs to that system rather
    # than here. KINDS stays closed; this does not.
    task: str = ""
    # What the actor says a thousand units are worth, in the payment good's own
    # unit. Spec 6.6 makes the unit price part of what a quote *is*, and both
    # sides of a bargain state one -- a seller's ask and a buyer's ceiling -- so
    # it belongs on the intent rather than being recomputed by whoever matches
    # them. Zero on every intent that is not a quote or an acceptance.
    unit_price: int = 0
    # The office, obligation, or order relied on. Empty is legal only for an
    # actor acting on its own account, over its own goods.
    authority: EntityId = ""
    # How the actor came to want this: the claim or observation ids behind it.
    basis: tuple[str, ...] = ()
    priority: int = 0     # obligation priority; higher is served first

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise IntentError(f"unregistered intent kind: {self.kind!r}")
        if not self.actor:
            raise IntentError(f"{self.id}: an intent belongs to an actor")
        if self.quantity < 0:
            raise IntentError(f"{self.id}: negative quantity")
        if self.resource and self.quantity <= 0:
            raise IntentError(
                f"{self.id}: an intent on a shared resource must say how much")


def faults(intents: tuple[Intent, ...],
           exists=lambda entity_id: True) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()
    for intent in sorted(intents, key=lambda i: i.id):
        if intent.id in seen:
            found.append(f"{intent.id}: duplicate intent id")
        seen.add(intent.id)
        if not exists(intent.actor):
            found.append(
                f"{intent.id}: actor {intent.actor!r} does not exist")
        if intent.subject and not exists(intent.subject):
            found.append(
                f"{intent.id}: subject {intent.subject!r} does not exist")
    return tuple(found)
