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
class HouseMember:
    """Not a stat block. A cast (spec 6.10).

    Everyone here is a named person with an age, a location that may be a
    foreign court, and an agenda of their own. A daughter married abroad stays
    in this list: she is a permanent asset, an independent agent, the best
    intelligence source in the game, and not on your side.
    """
    id: str
    name: str
    sex: str                      # "f" | "m"
    age_turns: int
    health: int                   # 0..1000
    location: PlaceId
    spouse: str | None = None
    mother: str | None = None
    father: str | None = None
    faction: str = "house"
    own_agenda: str = ""
    is_heir_rank: int | None = None
    alive: bool = True
    died_turn: int | None = None
    # Married to a foreign court rather than within the house: she writes home.
    married_to_court: ActorId | None = None
    is_queen_mother: bool = False
    # Absolute turn a scheduled birth is due, or None. Without this a woman
    # already carrying a child conceives again every fortnight.
    pregnant_until: int | None = None


@dataclasses.dataclass(frozen=True)
class Omen:
    """A divination that was taken and is now on the record (spec 6.11).

    `reported` is what the diviner said. Whether it was true is not stored --
    it is recomputed from the same precomputed future the engine read, so
    replay cannot drift and the player is never one field away from the answer.
    """
    id: str
    turn: int
    question: str                 # "harvest" | "death" | "route"
    subject: str                  # what it was about: a person id, a place, ""
    reported: str                 # the diviner's answer, as a word
    published: bool               # announced to the court, or suppressed
    defied_turn: int | None = None


@dataclasses.dataclass(frozen=True)
class Estate:
    """A block of crown or temple land (spec 6.4).

    The authored fields are fixed; the four below the line are the season's
    working state, reset at sowing. None of this is ever shown to the player:
    he sees a gauge reading, an overseer's letter, and last year's harvest.
    """
    id: str
    name: str
    place: PlaceId
    area_iku: int
    base_yield_per_iku: int       # qa per iku in a normal year at full inputs
    seed_per_iku: int             # the recommended sowing rate
    labour_days_per_iku: int      # needed across the whole season
    irrigated: bool = False       # canal mechanics apply (Mesopotamia, the Delta)
    canal_condition: int = 1000   # 0..1000, decays every turn, dredged at low water
    # --- per-season working state ---
    seed_sown: int = 0
    labour_days_supplied: int = 0
    climate_sum: int = 0          # accumulated growing-season index...
    climate_turns: int = 0        # ...and its divisor, for the mean
    standing_yield: int = 0       # cut and standing in the field, awaiting threshing
    pest: int = 1000              # event-driven modifier, 1000 = untouched


@dataclasses.dataclass(frozen=True)
class Workshop:
    """A production shop with a standing bronze demand (spec 6.5)."""
    id: str
    name: str
    group_id: GroupId             # whose hands do the work; their arrears gate output
    bronze_demand: int            # shekels per turn for maintenance and replacement


@dataclasses.dataclass(frozen=True)
class Formation:
    """A body of troops. Its strength does not fall when bronze runs out --
    its ability to replace losses does, which is the entire point (spec 6.5)."""
    id: str
    name: str
    strength: int
    equipment_floor: int          # bronze in circulation below which re-equipping fails
    replacement_rate: int         # 0..1000, derived each turn from the floor


@dataclasses.dataclass(frozen=True)
class MetalState:
    """Spec 6.5. `melt_ledger` only ever increases, and nothing announces it."""
    bronze_in_circulation: int    # bronze existing as tools, weapons, chariot fittings
    melt_ledger: int = 0          # CUMULATIVE shekels recycled out of circulation


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
    # --- M8: land and metal ---
    estates: Mapping[str, Estate] = dataclasses.field(default_factory=dict)
    # Groups ordered to the fields instead of their own function. The garrison
    # on the harvest is the classic Bronze Age dilemma and is one action.
    at_harvest: tuple[GroupId, ...] = ()
    corvee_days: int = 0                 # raised this season, paid for in unrest
    # The only hard datum the player gets about the land (spec 6.4). True, and
    # a year stale.
    last_harvest: int = 0
    previous_harvest: int = 0
    workshops: tuple[Workshop, ...] = ()
    formations: tuple[Formation, ...] = ()
    metals: MetalState = dataclasses.field(
        default_factory=lambda: MetalState(0, 0))
    # 24 fortnights of stock readings per good, for the STORES sparkline (9.4).
    store_history: Mapping[GoodId, tuple[int, ...]] = dataclasses.field(
        default_factory=dict)
    # --- M9: the house and the cult ---
    house: Mapping[str, HouseMember] = dataclasses.field(default_factory=dict)
    ruler: str = ""                      # person id of whoever is on the seat
    diviner_competence: int = 600
    diviner_loyalty: int = 700
    diviner_faction: str = "temple"
    reigns: int = 1                      # how many rulers this run has seen
    # --- M10: plague ---
    # Places whose routes the ruler has closed (spec 6.12). It works, and it
    # costs him trade and the esteem of whoever is on the other end -- who is
    # rarely willing to accept that his own city is the reason.
    quarantined: tuple[PlaceId, ...] = ()
    # Archive searches run this turn, so the TUI can show the hits it paid for.
    # Cleared every turn like `inspected`.
    searched: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Place:
    """A settlement, and — from M10 — a compartment model (spec 6.12).

    S/I/R/dead are integers because everything in engine/ is. The living
    population is S + I + R; `dead` is cumulative and only ever rises, which
    makes it the one plague number with an archaeological afterlife.

    None of these four fields is ever projected. Nobody in 1190 BC has an
    infection count; the ruler learns of a sickness because his officials write
    to him about it, late, and because his own dependents stop turning up.
    """
    id: PlaceId
    name: str
    population: int = 0            # authored opening size; S is seeded from it
    susceptible: int = 0
    infected: int = 0
    recovered: int = 0
    dead: int = 0                  # cumulative plague deaths at this place


@dataclasses.dataclass(frozen=True)
class PlagueState:
    """Spec 6.12: integer SIR, and a theological puzzle bolted on top.

    `cause_oath_id` is the whole design. When an epidemic begins the engine
    designates a genuinely violated oath — often one the player's PREDECESSOR
    swore, sitting in the archive since before turn 1 — and the player has to
    find it by reading. It is in `FORBIDDEN_KEYS`, never projected, and there is
    no field anywhere that tells the player whether an expiation was the right
    one. The epidemic curve is the only feedback, which is the point.
    """
    beta: int = 0                  # transmission, per mille
    gamma: int = 0                 # recovery, per mille
    mortality: int = 0             # deaths among the infected, per mille
    exposure: int = 0              # chance in 1000 that an arrival seeds a place
    cause_oath_id: str = ""        # HIDDEN. The oath the gods are angry about.
    began_turn: int | None = None
    # Oaths the player has spent an offering on, in the order he tried them.
    # Projected — he remembers what he did — but with no verdict attached.
    expiated: tuple[str, ...] = ()
    # Set when the correct oath is expiated. HIDDEN: the drop in beta is the
    # only way to find out, and it is slow enough to be deniable.
    expiated_correctly_turn: int | None = None


@dataclasses.dataclass(frozen=True)
class Document:
    """Spec 6.17. Every document ever received or sent, plus the authored
    predecessor archive, plus internal records.

    `dated_as` is the SENDER'S regnal date string, in the sender's calendar with
    the sender's epoch. It is deliberately not comparable to anything. Sorting
    is by `received_turn` only, and the player will act on a letter written
    before one he has already answered.
    """
    ref: str                       # DocRef: stable, citable, e.g. "PA-UG-014"
    kind: str                      # letter_in|letter_out|oath|ration_record|inventory|omen
    received_turn: int
    sender: ActorId | None
    dated_as: str
    body: str
    title: str = ""
    tags: tuple[str, ...] = ()


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
    # Which of those facts this correspondent has a motive to inflate or to play
    # down (spec 6.8). The bias itself lives on the Relation; this is only the
    # direction of his interest, which is a property of what he is writing about.
    exaggerate: tuple[str, ...] = ()
    understate: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Letter:
    """The unit that travels and is read. Its prose is rendered on demand from
    these structured fields -- the engine never holds letter text (spec 8.7)."""
    id: str
    sender: ActorId
    recipient: ActorId
    topic: str
    facts: tuple[tuple[str, object], ...]          # what the tablet ASSERTS
    sent_turn: int
    path: tuple[PlaceId, ...]     # node sequence, origin..seat
    edge_index: int              # which edge of the path it is crossing
    legs_into_edge: int          # progress within that edge
    at_node: PlaceId
    arrive_turn: int | None = None
    read: bool = False
    answered_turn: int | None = None
    outgoing: bool = False       # True = the player's own reply
    # What was actually the case when he wrote (spec 6.8). Never projected into
    # Belief and never shown to the model: the ruler learns it, if at all, from a
    # second correspondent who saw the same thing. Empty means "he had no motive
    # to lie, so the assertion is the truth".
    true_facts: tuple[tuple[str, object], ...] = ()
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
    # How far this correspondent's reports run from the truth, in permille of the
    # true figure (spec 6.8). 0 is an honest witness. This is a property of the
    # SENDER, not of the ruler's knowledge of him -- which is why it never enters
    # Belief: nothing tells the player that Abdi-milki trebles what he sees.
    report_bias: int = 0


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
    sworn_by: str                 # WHO swore it. Personal, not institutional.
    clauses: tuple[Clause, ...]
    dissolved: bool = False
    # Spec 6.9: oaths are personal and non-transitive. When either sworn party
    # dies, the oath lapses -- it is not broken, it simply no longer binds
    # anyone, and it accrues no liability until a living man swears it again.
    # There is never a province that is loyal; there is a named man who is.
    lapsed: bool = False
    # ...with one exception, and M10 turns on it. An oath sworn to a KING is a
    # personal bond and dies with either man. A vow sworn to a GOD is a
    # dedication of the house and the city, and the god does not accept that the
    # man who promised is dead as an argument. So a vow does not lapse, and the
    # liability for a great-grandfather's neglected festival is still accruing
    # against a king who has never heard of it. That is the archive puzzle
    # (spec 6.12), and it is what Mursili II's plague prayers are actually about.
    binds_house: bool = False


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
    # The record of what the gods were asked and what the diviner said. Beside
    # `oaths` because both are documents the court keeps, and neither records
    # whether it was true.
    omens: tuple[Omen, ...] = ()
    omen_seq: int = 0
    gift_values: Mapping[GoodId, int] = dataclasses.field(default_factory=dict)
    gift_status_floors: Mapping[str, int] = dataclasses.field(default_factory=dict)
    reciprocity_table: tuple[tuple[int, int], ...] = ()
    god_ranks: Mapping[str, int] = dataclasses.field(default_factory=dict)
    protocol_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    gift_seq: int = 0
    misfortune_deck: tuple[MisfortuneCard, ...] = ()
    # The whole climate series, precomputed at scenario start (spec 6.4) so that
    # the future is fixed the moment the game begins -- which is what lets
    # divination (6.11) read a true future value. Indexed by absolute turn,
    # 0..200 with 100 normal. Never projected into Belief, never prompted.
    climate: tuple[int, ...] = ()
    # Response tables (spec 6.4), authored in content/land.toml.
    land_tables: Mapping[str, tuple[tuple[int, int], ...]] = dataclasses.field(
        default_factory=dict)
    land_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    house_tables: Mapping[str, tuple[tuple[int, int], ...]] = dataclasses.field(
        default_factory=dict)
    house_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    # Name pools for children born in play, so a new person is still an
    # authored name rather than a generated identifier.
    house_names_f: tuple[str, ...] = ()
    house_names_m: tuple[str, ...] = ()
    # --- M10: plague and the archive ---
    plague: PlagueState = dataclasses.field(default_factory=PlagueState)
    # The archive proper (spec 6.17): the authored predecessor documents from
    # turn 1, plus every letter in and out as it happens. Ordered by
    # received_turn, because that is the only order the court can actually sort.
    documents: tuple[Document, ...] = ()
    # Debug-only breadcrumb of rng draws; excluded from the state hash.
    rng_ledger: tuple[str, ...] = ()


# Placed after World so the forward ref in schedule resolves; payload is any Event.
@dataclasses.dataclass(frozen=True)
class Scheduled:
    at: int          # absolute turn on which the payload fires
    payload: object  # an already-decided Event (engine.actions.Event)


def replace_court(w: World, **changes) -> World:
    return dataclasses.replace(w, court=dataclasses.replace(w.court, **changes))
