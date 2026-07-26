"""The World dataclass tree (spec Part 4). Frozen, integer-only, hashable.

Grows as milestones land, but the shape is stable: World is truth, seen only by
engine/. Everything is a frozen dataclass or a dict iterated via sorted().
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine.core import Date

# Type aliases for readers. These are authored strings, not generated counters.
GoodId = str
GroupId = str
PlaceId = str
ActorId = str


@dataclasses.dataclass(frozen=True)
class GiftRecord:
    id: str
    sender: ActorId
    recipient: ActorId
    good: GoodId
    quantity: int
    value: int
    sent_turn: int
    arrive_turn: int | None = None
    adequacy: int | None = None


@dataclasses.dataclass(frozen=True)
class DependentGroup:
    """A named body of people the crown feeds. Arrears is the system's memory."""
    id: GroupId
    name: str
    size: int                 # heads
    entitlement: int          # qa per head per fortnight
    function: str             # "bronze_working" | "garrison" | "weaving" | "cult" | "household"
    place: PlaceId
    arrears: int = 0          # cumulative unpaid qa
    loyalty: int = 700        # 0..1000
    output_modifier: int = 1000  # 0..1000, derived + cached
    member_name: str = ""     # the face of a cut (spec 6.3); assigned at load


@dataclasses.dataclass(frozen=True)
class Rite:
    id: str
    fortnight: int
    hours: int
    requires: tuple[tuple[GoodId, int], ...]     # sorted good->qty
    skip_legitimacy: int
    skip_unrest: int
    skip_deck_weight: int


@dataclasses.dataclass(frozen=True)
class Court:
    actor: ActorId
    seat: PlaceId
    attention_base: int                          # hours per fortnight
    stores: Mapping[GoodId, int]                 # includes "grain" and "seed_grain"
    grain_income: int                            # estate deliveries per turn (agriculture replaces in M8)
    dependents: Mapping[GroupId, DependentGroup]
    allocations: Mapping[GroupId, int]           # target qa to pay each group this turn
    priority: tuple[GroupId, ...]                # pay-down order when grain is short
    rites: tuple[Rite, ...]
    unrest: int = 0                              # seat unrest, 0..1000
    legitimacy: int = 700                        # 0..1000
    # The scribe who copies every number the ruler reads (spec 6.7). His errors
    # corrupt Belief, never World. A single palace scribe in M3; personnel with
    # kin-interests and fatigue arrive in M6/M9.
    scribe_competence: int = 850                 # 0..1000
    scribe_fatigue: int = 300                    # 0..1000
    # Ledgers inspected THIS turn: the ruler spent an hour and saw the true
    # count, bypassing the scribe. Cleared every turn (spec 6.1).
    inspected: tuple[str, ...] = ()
    liability: Mapping[str, int] = dataclasses.field(default_factory=dict)
    treasury_gifts_sent: tuple[GiftRecord, ...] = ()
    misfortune_weight: int = 0


@dataclasses.dataclass(frozen=True)
class Place:
    id: PlaceId
    name: str


@dataclasses.dataclass(frozen=True)
class Route:
    a: PlaceId
    b: PlaceId
    legs: int          # fortnights to cross
    mode: str          # "sea" | "land" | "river"
    seasonal: bool     # sea legs shut outside the sailing window
    risk: int          # 0..1000 base interception/loss weight


@dataclasses.dataclass(frozen=True)
class Correspondent:
    """An authored NPC who writes on a cadence (spec A15 intents, M2 templates)."""
    actor: ActorId
    place: PlaceId
    cadence: int                              # write every N turns
    offset: int
    topic: str
    facts: tuple[tuple[str, object], ...]     # structured; prose rendered lazily


@dataclasses.dataclass(frozen=True)
class Letter:
    """The unit that travels and is read. Its prose is rendered on demand from
    these structured fields -- the engine never holds letter text (spec 8.7)."""
    id: str
    sender: ActorId
    recipient: ActorId
    topic: str
    facts: tuple[tuple[str, object], ...]
    sent_turn: int
    path: tuple[PlaceId, ...]     # node sequence, origin..seat
    edge_index: int              # which edge of the path it is crossing
    legs_into_edge: int          # progress within that edge
    at_node: PlaceId
    arrive_turn: int | None = None
    read: bool = False
    answered_turn: int | None = None
    outgoing: bool = False       # True = the player's own reply
    protocol_profile: str = ""
    protocol_total: int = 0
    protocol_violations: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Relation:
    other: ActorId
    place: PlaceId
    status_claim: str
    their_status_claim: str
    esteem: int
    obligation: int
    last_gift_from_us: int
    last_gift_from_them: int
    best_known_rival_gift: int
    known_rival_gift_source: ActorId | None
    unanswered_letters_from_them: int = 0
    is_vassal: bool = False
    status_mismatch_known: bool = False
    seeking_patron: bool = False
    patron_notice_received: bool = False
    reply_delay_until: int = 0


@dataclasses.dataclass(frozen=True)
class Clause:
    kind: str
    args: tuple[tuple[str, object], ...]


@dataclasses.dataclass(frozen=True)
class Oath:
    id: str
    parties: tuple[ActorId, ActorId]
    superior: ActorId | None
    gods: tuple[str, ...]
    sworn_turn: int
    sworn_by: str
    clauses: tuple[Clause, ...]
    dissolved: bool = False


@dataclasses.dataclass(frozen=True)
class MisfortuneCard:
    id: str
    weight: int
    liability_weight: int
    good: GoodId
    loss: int
    legitimacy_delta: int
    unrest_delta: int


@dataclasses.dataclass(frozen=True)
class ProtocolRecord:
    """Derived result retained for M6 consequences; prose stays in the action log."""
    letter_id: str
    recipient: ActorId
    profile: str
    total: int
    violations: tuple[str, ...]
    applied_turn: int | None = None


@dataclasses.dataclass(frozen=True)
class World:
    seed: int
    scenario: str
    date: Date
    court: Court
    # Anything that "arrives later" is a Scheduled (spec 3.3). Sorted, stable.
    schedule: tuple["Scheduled", ...] = ()
    # Mail (spec 6.6). Places/routes/correspondents authored; the rest is live.
    places: Mapping[PlaceId, Place] = dataclasses.field(default_factory=dict)
    routes: tuple[Route, ...] = ()
    correspondents: tuple[Correspondent, ...] = ()
    season: Mapping[str, tuple[int, ...]] = dataclasses.field(default_factory=dict)
    letters_in_transit: tuple[Letter, ...] = ()
    inbox: tuple[Letter, ...] = ()            # arrived letters: the Stack's source
    letter_seq: int = 0                       # monotonic id counter
    protocol_log: tuple[ProtocolRecord, ...] = ()
    relations: Mapping[ActorId, Relation] = dataclasses.field(default_factory=dict)
    oaths: tuple[Oath, ...] = ()
    gift_values: Mapping[GoodId, int] = dataclasses.field(default_factory=dict)
    gift_status_floors: Mapping[str, int] = dataclasses.field(default_factory=dict)
    reciprocity_table: tuple[tuple[int, int], ...] = ()
    god_ranks: Mapping[str, int] = dataclasses.field(default_factory=dict)
    protocol_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    gift_seq: int = 0
    misfortune_deck: tuple[MisfortuneCard, ...] = ()
    # Debug-only breadcrumb of rng draws; excluded from the state hash.
    rng_ledger: tuple[str, ...] = ()


# Placed after World so the forward ref in schedule resolves; payload is any Event.
@dataclasses.dataclass(frozen=True)
class Scheduled:
    at: int          # absolute turn on which the payload fires
    payload: object  # an already-decided Event (engine.actions.Event)


def replace_court(w: World, **changes) -> World:
    return dataclasses.replace(w, court=dataclasses.replace(w.court, **changes))
