"""One allocation for the whole world (spec 6.1 phase 5, 10.10)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine.entity import EntityId
from engine.kernel.intent import Intent


class AllocationError(ValueError):
    """A claim on a pool that does not exist, or a capacity below zero."""


@dataclasses.dataclass(frozen=True)
class Grant:
    """What one intent actually got. The record the inspector answers from."""
    intent: str
    actor: EntityId
    resource: EntityId
    asked: int
    granted: int
    authority: EntityId = ""

    @property
    def short(self) -> int:
        return self.asked - self.granted

    @property
    def met(self) -> bool:
        return self.granted == self.asked


@dataclasses.dataclass(frozen=True)
class Allocation:
    grants: tuple[Grant, ...] = ()
    remaining: Mapping[EntityId, int] = dataclasses.field(default_factory=dict)

    def for_intent(self, intent_id: str) -> Grant | None:
        for grant in self.grants:
            if grant.intent == intent_id:
                return grant
        return None

    def granted(self, intent_id: str) -> int:
        grant = self.for_intent(intent_id)
        return grant.granted if grant else 0

    def unmet(self) -> tuple[Grant, ...]:
        return tuple(grant for grant in self.grants if not grant.met)


def rank(intent: Intent, authority_rank) -> tuple:
    """The sort key."""
    return (-intent.priority, -authority_rank(intent), intent.actor, intent.id)


def allocate(intents: tuple[Intent, ...],
             capacity: Mapping[EntityId, int],
             authority_rank=lambda intent: 0) -> Allocation:
    """Settle every claim on every pool at once."""
    for resource in sorted(capacity):
        if capacity[resource] < 0:
            raise AllocationError(f"{resource}: negative capacity")

    claims = [i for i in intents if i.resource]
    for intent in claims:
        if intent.resource not in capacity:
            raise AllocationError(
                f"{intent.id}: claims {intent.resource!r}, which has no capacity")

    left = dict(capacity)
    grants: list[Grant] = []
    for intent in sorted(claims, key=lambda i: rank(i, authority_rank)):
        available = left[intent.resource]
        given = min(intent.quantity, available)
        left[intent.resource] = available - given
        grants.append(Grant(
            intent=intent.id, actor=intent.actor, resource=intent.resource,
            asked=intent.quantity, granted=given, authority=intent.authority))

    # Grants are reported in the order they were decided, which is the order the shortfall happened.
    return Allocation(grants=tuple(grants), remaining=left)


def faults(allocation: Allocation,
           capacity: Mapping[EntityId, int]) -> tuple[str, ...]:
    """Spec 11.1: nothing exceeds capacity, and nothing was granted twice."""
    found: list[str] = []
    spent: dict[EntityId, int] = {}
    for grant in allocation.grants:
        if grant.granted < 0 or grant.granted > grant.asked:
            found.append(
                f"{grant.intent}: granted {grant.granted} of {grant.asked} asked")
        spent[grant.resource] = spent.get(grant.resource, 0) + grant.granted
    for resource in sorted(spent):
        limit = capacity.get(resource, 0)
        if spent[resource] > limit:
            found.append(
                f"{resource}: granted {spent[resource]} of {limit} available")
        left = allocation.remaining.get(resource, 0)
        if spent[resource] + left != limit:
            found.append(
                f"{resource}: {spent[resource]} granted and {left} left "
                f"do not account for {limit}")
    return tuple(found)
