"""Closed Action and Event unions (spec 2.1).

Action = player (or scripted-policy) intent. Events = what actually happened,
the record the UI and belief layer read. Both are frozen dataclasses; a small
registry lets the save log round-trip them through JSON.
"""
from __future__ import annotations

import dataclasses

# --- Actions -----------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class EndTurn:
    pass


@dataclasses.dataclass(frozen=True)
class Allocate:
    group_id: str
    qa: int          # target grain to pay this group per turn; effect from T+1 (spec D3)


@dataclasses.dataclass(frozen=True)
class SetPriority:
    order: tuple[str, ...]   # group ids, pay-down order


@dataclasses.dataclass(frozen=True)
class EatSeed:
    qa: int          # move seed_grain into the granary now, ruin the sowing later


@dataclasses.dataclass(frozen=True)
class ReadLetter:
    letter_id: str   # reveal a Stack item's body; costs attention


@dataclasses.dataclass(frozen=True)
class DictateReply:
    letter_id: str   # the Stack item being answered
    intent: str      # free-text purpose; prose is composed outside engine/
    text: str = ""   # exact sent text; replay re-grades this, never a stored score
    profile: str = ""
    protocol_total: int = 0
    protocol_violations: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class InspectLedger:
    ledger: str      # "granary" | "seed" — spend an hour, see the true count


@dataclasses.dataclass(frozen=True)
class SendGift:
    recipient: str
    good: str
    quantity: int


# --- Events ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TurnAdvanced:
    year: int
    fortnight: int


@dataclasses.dataclass(frozen=True)
class GrainReceived:
    amount: int


@dataclasses.dataclass(frozen=True)
class Spoiled:
    good: str
    amount: int


@dataclasses.dataclass(frozen=True)
class RationsPaid:
    group_id: str
    owed: int
    paid: int
    arrears: int
    debt_weeks: int


@dataclasses.dataclass(frozen=True)
class RitePerformed:
    rite_id: str
    hours: int
    full: bool       # False = offered less than required (partial credit)


@dataclasses.dataclass(frozen=True)
class RiteSkipped:
    rite_id: str


@dataclasses.dataclass(frozen=True)
class UnrestChanged:
    delta: int
    reason: str


@dataclasses.dataclass(frozen=True)
class Grumbling:
    """A named member of a group in arrears speaks up (spec 6.3, debt_weeks>=2)."""
    group_id: str
    member_name: str
    debt_weeks: int


@dataclasses.dataclass(frozen=True)
class SeedEaten:
    amount: int


@dataclasses.dataclass(frozen=True)
class AllocationSet:
    group_id: str
    qa: int


@dataclasses.dataclass(frozen=True)
class PrioritySet:
    order: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class LetterArrived:
    letter_id: str
    sender: str
    topic: str


@dataclasses.dataclass(frozen=True)
class LetterDelivered:
    letter_id: str
    recipient: str
    topic: str


@dataclasses.dataclass(frozen=True)
class LetterSent:
    letter_id: str
    recipient: str
    topic: str


@dataclasses.dataclass(frozen=True)
class LetterIntercepted:
    letter_id: str


@dataclasses.dataclass(frozen=True)
class LetterRead:
    letter_id: str


@dataclasses.dataclass(frozen=True)
class LedgerInspected:
    ledger: str
    true_value: int


@dataclasses.dataclass(frozen=True)
class GiftSent:
    gift_id: str
    recipient: str
    good: str
    quantity: int
    value: int
    arrival_turn: int


@dataclasses.dataclass(frozen=True)
class GiftArrived:
    gift_id: str


@dataclasses.dataclass(frozen=True)
class GiftJudged:
    gift_id: str
    recipient: str
    adequacy: int
    esteem_delta: int


@dataclasses.dataclass(frozen=True)
class RumourArrived:
    observer: str
    subject: str
    gift_value: int


@dataclasses.dataclass(frozen=True)
class PatronNoticeDue:
    actor: str


@dataclasses.dataclass(frozen=True)
class PatronSought:
    actor: str


@dataclasses.dataclass(frozen=True)
class ProtocolApplied:
    recipient: str
    esteem_delta: int
    violations: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class OathViolated:
    oath_id: str
    clause_kind: str


@dataclasses.dataclass(frozen=True)
class MisfortuneOccurred:
    card_id: str
    good: str
    loss: int


# --- Registry for log round-tripping -----------------------------------------

_TYPES = {
    c.__name__: c for c in (
        EndTurn, Allocate, SetPriority, EatSeed, ReadLetter, DictateReply,
        InspectLedger, SendGift,
        TurnAdvanced, GrainReceived, Spoiled, RationsPaid, RitePerformed,
        RiteSkipped, UnrestChanged, Grumbling, SeedEaten, AllocationSet,
        PrioritySet, LetterArrived, LetterDelivered, LetterSent,
        LetterIntercepted, LetterRead, LedgerInspected, GiftSent, GiftArrived,
        GiftJudged, RumourArrived, PatronNoticeDue, PatronSought,
        ProtocolApplied, OathViolated, MisfortuneOccurred,
    )
}


def to_dict(obj) -> dict:
    d = {"_t": type(obj).__name__}
    for f in dataclasses.fields(obj):
        v = getattr(obj, f.name)
        d[f.name] = list(v) if isinstance(v, tuple) else v
    return d


def from_dict(d: dict):
    cls = _TYPES[d["_t"]]
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in d:
            if f.default is not dataclasses.MISSING:
                kwargs[f.name] = f.default
                continue
            raise KeyError(f.name)
        v = d[f.name]
        if isinstance(v, list):
            v = tuple(v)
        kwargs[f.name] = v
    return cls(**kwargs)
