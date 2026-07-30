"""What is owed, to whom, and on what terms (spec 5.5, 10.9).

Taxes, corvée, rations, tribute, gifts, oaths, debts, and summons are one
structure with an explicit clause. The clause kinds are closed: an obligation
the engine cannot classify is one the causal audit cannot follow.

The consequence of default is not an effect this module applies. It is what the
parties *believe* follows, carried as text on the obligation and acted on by
whoever holds the right -- who may be wrong about it, may not find out, or may
not dare. An engine that punished default automatically would be deciding a
political question with arithmetic, which Law 5 forbids.
"""
from __future__ import annotations

import dataclasses

from engine.core import Date, in_range
from engine.entity import EntityId, GoodId

# Closed (spec 10.9). Adding a kind is a specification change.
CLAUSES = frozenset({
    "fixed_quantity",   # so many units of a good, by a date
    "share_of_yield",   # a scaled share of a measured production event
    "per_head",         # a quantity scaled by counted people or animals
    "service_days",     # labour or military service, in person-days
    "on_demand",        # rendered when the holder of the right calls for it
})

DUE_KINDS = frozenset({
    "season",     # every year, within a named season span
    "every",      # every N fortnights from a start turn
    "on_date",    # one absolute turn
    "on_trigger", # when a named event happens
    "never",      # on_demand obligations, which have no calendar
})

OPEN = frozenset({"pending", "due", "part_paid"})
CLOSED = frozenset({"discharged", "defaulted", "remitted", "disputed"})
STATUSES = OPEN | CLOSED

# pending -> due -> part_paid -> discharged | defaulted | remitted | disputed
TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"due", "remitted", "disputed"}),
    "due": frozenset({"part_paid", "discharged", "defaulted", "remitted",
                      "disputed"}),
    "part_paid": frozenset({"discharged", "defaulted", "remitted", "disputed"}),
    "discharged": frozenset(),
    "defaulted": frozenset({"part_paid", "discharged", "remitted", "disputed"}),
    "remitted": frozenset(),
    "disputed": frozenset({"discharged", "defaulted", "remitted"}),
}


class ClauseError(ValueError):
    """An obligation that does not say what it requires."""


@dataclasses.dataclass(frozen=True)
class Due:
    """When the clause falls due. Parameters mean whatever `kind` says."""
    kind: str
    span: str = ""          # named season span, for "season"
    every: int = 0          # fortnights, for "every"
    start: int = 0          # absolute turn, for "every" and "on_date"
    trigger: str = ""       # event name, for "on_trigger"

    def __post_init__(self) -> None:
        if self.kind not in DUE_KINDS:
            raise ClauseError(f"unregistered due kind: {self.kind!r}")
        if self.kind == "season" and not self.span:
            raise ClauseError("a seasonal due needs a named span")
        if self.kind == "every" and self.every <= 0:
            raise ClauseError("a recurring due needs a positive interval")
        if self.kind == "on_trigger" and not self.trigger:
            raise ClauseError("a triggered due needs a trigger name")


@dataclasses.dataclass(frozen=True)
class Obligation:
    id: EntityId
    party: EntityId          # who owes
    beneficiary: EntityId    # who is owed
    clause: str
    due: Due
    good: GoodId = ""        # for quantity clauses; "" for service
    quantity: int = 0        # units, or person-days for service_days
    rate: int = 0            # scaled 1000, for share_of_yield and per_head
    authority: EntityId = "" # the office or instrument relied on
    status: str = "pending"
    rendered: int = 0        # what has actually been rendered against it
    consequence: str = ""    # what the parties believe follows from default
    history: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.clause not in CLAUSES:
            raise ClauseError(f"unregistered clause: {self.clause!r}")
        if self.status not in STATUSES:
            raise ClauseError(f"unregistered status: {self.status!r}")
        if self.clause == "fixed_quantity" and self.quantity <= 0:
            raise ClauseError(f"{self.id}: fixed_quantity needs a quantity")
        if self.clause in ("share_of_yield", "per_head") and self.rate <= 0:
            raise ClauseError(f"{self.id}: {self.clause} needs a rate")
        if self.clause == "service_days" and self.quantity <= 0:
            raise ClauseError(f"{self.id}: service_days needs person-days")
        if self.clause == "on_demand" and self.due.kind != "never":
            raise ClauseError(
                f"{self.id}: an on_demand clause has no calendar")
        if self.clause != "on_demand" and self.due.kind == "never":
            raise ClauseError(f"{self.id}: {self.clause} needs a due rule")

    @property
    def open(self) -> bool:
        return self.status in OPEN

    def owed(self, measure: int = 0) -> int:
        """What this clause requires in full.

        `measure` is the quantity the clause scales against: the yield for
        `share_of_yield`, the head count for `per_head`. It is ignored by the
        clauses that state their own quantity.
        """
        if self.clause in ("fixed_quantity", "service_days", "on_demand"):
            return self.quantity
        return measure * self.rate // 1000

    def outstanding(self, measure: int = 0) -> int:
        return max(0, self.owed(measure) - self.rendered)


# --- letter-carried terms ----------------------------------------------------

@dataclasses.dataclass(frozen=True)
class GoodsReservation:
    """Goods removed from a sender's stores when a tablet is dispatched."""

    id: str
    source_letter: str
    term_index: int
    party: EntityId
    beneficiary: EntityId
    authority: EntityId
    good: GoodId
    quantity: int
    created_turn: int
    due_turn: int
    status: str = "reserved"
    history: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class LetterObligation:
    """A promise recorded by a letter; it is not a transfer of goods."""

    id: str
    source_letter: str
    term_index: int
    party: EntityId
    beneficiary: EntityId
    authority: EntityId
    kind: str
    good: GoodId
    quantity: int
    destination: EntityId
    created_turn: int
    due_turn: int
    status: str = "promised"
    history: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class RequestClaim:
    """A request becomes a claim only when its tablet reaches the addressee."""

    id: str
    source_letter: str
    term_index: int
    party: EntityId
    beneficiary: EntityId
    authority: EntityId
    good: GoodId
    quantity: int
    created_turn: int
    due_turn: int
    status: str = "claimed"
    history: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class MarriageProposal:
    """A delivered proposal concerning a living person, never a marriage."""

    id: str
    source_letter: str
    term_index: int
    party: EntityId
    beneficiary: EntityId
    authority: EntityId
    person_id: EntityId
    created_turn: int
    due_turn: int
    status: str = "pending"
    history: tuple[str, ...] = ()


def falls_due(obligation: Obligation, date: Date,
              seasons: dict, trigger: str = "") -> bool:
    """Whether the calendar (or an event) puts this clause in hand this turn."""
    due = obligation.due
    if due.kind == "never":
        return False
    if due.kind == "season":
        span = seasons.get(due.span)
        return bool(span) and in_range(date.fortnight, tuple(span))
    if due.kind == "every":
        elapsed = date.absolute - due.start
        return elapsed >= 0 and elapsed % due.every == 0
    if due.kind == "on_date":
        return date.absolute == due.start
    return bool(trigger) and trigger == due.trigger


def move(obligation: Obligation, status: str, note: str = "") -> Obligation:
    """Advance the status, refusing any step the lifecycle does not allow."""
    if status not in STATUSES:
        raise ClauseError(f"unregistered status: {status!r}")
    if status not in TRANSITIONS[obligation.status]:
        raise ClauseError(
            f"{obligation.id}: {obligation.status} does not lead to {status}")
    entry = note or f"{obligation.status}->{status}"
    return dataclasses.replace(
        obligation, status=status, history=obligation.history + (entry,))


def render(obligation: Obligation, quantity: int,
           measure: int = 0, note: str = "") -> Obligation:
    """Record what was actually rendered, and settle the status accordingly.

    Rendering does not move goods. The caller moves them through
    `engine.ownership` and records the rendering here, so that the two ledgers
    can be checked against each other rather than trusted.
    """
    if quantity <= 0:
        raise ClauseError("a rendering is a positive quantity")
    if not obligation.open and obligation.status != "defaulted":
        raise ClauseError(
            f"{obligation.id}: nothing can be rendered against {obligation.status}")
    rendered = obligation.rendered + quantity
    entry = note or f"rendered {quantity}"
    obligation = dataclasses.replace(
        obligation, rendered=rendered, history=obligation.history + (entry,))
    if rendered >= obligation.owed(measure):
        return move(obligation, "discharged")
    if obligation.status == "due":
        return move(obligation, "part_paid")
    return obligation


def renew(obligation: Obligation) -> Obligation:
    """Open a recurring clause for its next term.

    A yearly tribute is not one debt that is settled forever. Once its window
    has passed -- discharged, defaulted, or remitted -- the clause stands again
    for the next year, with nothing rendered against it. The history carries
    over: what was paid late, and what was never paid at all, is exactly what
    the beneficiary remembers.
    """
    if obligation.due.kind not in ("season", "every"):
        raise ClauseError(f"{obligation.id}: {obligation.due.kind} does not recur")
    if obligation.open:
        raise ClauseError(
            f"{obligation.id}: still {obligation.status}; nothing to renew")
    return dataclasses.replace(
        obligation, status="pending", rendered=0,
        history=obligation.history + (f"renewed from {obligation.status}",))


def faults(obligations: tuple[Obligation, ...],
           exists=lambda entity_id: True) -> tuple[str, ...]:
    """Everything wrong with a set of obligations, as sentences."""
    found: list[str] = []
    seen: set[EntityId] = set()
    for obligation in sorted(obligations, key=lambda o: o.id):
        if obligation.id in seen:
            found.append(f"{obligation.id}: duplicate obligation id")
        seen.add(obligation.id)
        for field in ("party", "beneficiary"):
            value = getattr(obligation, field)
            if not exists(value):
                found.append(
                    f"{obligation.id}: {field} names {value!r}, which does not exist")
        if obligation.party == obligation.beneficiary:
            found.append(f"{obligation.id}: owed by its own beneficiary")
        if obligation.rendered < 0:
            found.append(f"{obligation.id}: negative rendering")
        if obligation.clause != "on_demand" and obligation.quantity < 0:
            found.append(f"{obligation.id}: negative quantity")
    return tuple(found)
