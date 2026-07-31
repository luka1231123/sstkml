"""The World dataclass tree (spec Part 4). Frozen, integer-only, hashable.

Grows as milestones land, but the shape is stable: World is truth, seen only by
engine/. Everything is a frozen dataclass or a dict iterated via sorted().
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING

from engine.core import Date

if TYPE_CHECKING:
    from engine.actions import LetterTerm
    from engine.kernel.world import Kernel
    from engine.obligation import (
        GoodsReservation,
        LetterObligation,
        MarriageProposal,
        RequestClaim,
    )

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
    revolting: bool = False   # withdraws all labour until arrears leave the revolt band


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
    # 6.22: a placement is power, not a label. Competence affects the thing
    # entrusted to this person; loyalty affects what he reports about it.
    competence: int = 500             # 0..1000
    loyalty: int = 700                # 0..1000
    post: str = ""                    # institution, governor:, command:, court:
    interests: tuple[str, ...] = ()   # offices leave permanent local interests


@dataclasses.dataclass(frozen=True)
class Omen:
    """A divination that was taken and is now on the record.

    `reported` is the diviner's forecast from the evidence available at the
    time.  There is deliberately no truth or correctness field: later history
    may vindicate the reading, contradict it, or remain ambiguous.
    """
    id: str
    turn: int
    question: str                 # "harvest" | "death" | "route"
    subject: str                  # what it was about: a person id, a place, ""
    reported: str                 # the diviner's answer, as a word
    published: bool               # announced to the court, or suppressed
    defied_turn: int | None = None


@dataclasses.dataclass(frozen=True)
class Workshop:
    """A production shop with a standing bronze demand (spec 6.5)."""
    id: str
    name: str
    group_id: GroupId             # whose hands do the work; their arrears gate output
    bronze_demand: int            # shekels per turn for maintenance and replacement


@dataclasses.dataclass(frozen=True)
class Formation:
    """A body of troops with distinct personnel and current capability.

    `task` and `place` are the whole military entity (spec 11's ASSIGN_TROOPS,
    D25). A formation is in exactly one place doing exactly one thing, and a
    king with four hundred men has four hundred men for all of it: the walls,
    the harvest, and the muster his overlord has summoned him to. `strength`
    counts those people; `ready` counts how many can currently perform the task
    with the equipment the replacement system can support."""
    id: str
    name: str
    strength: int
    equipment_floor: int          # bronze in circulation below which re-equipping fails
    replacement_rate: int         # 0..1000, derived each turn from the floor
    ready: int                    # 0..strength, actual capability consumed by systems
    task: str = "garrison"        # garrison | harvest | campaign | watch
    place: PlaceId = ""           # where they stand; the seat unless ordered elsewhere
    commander: str = ""           # PersonId; 6.22 makes a command a placement


@dataclasses.dataclass(frozen=True)
class Summons:
    """A demand for troops under an oath, and the clock it starts (spec 6.9's
    `provide_troops(n, within_turns_of_summons)`).

    `n` and `due_turn` come from the CLAUSE, not from the tablet that carries
    the demand. The letter is only the trigger, and the man who writes it is at
    liberty to ask for more men than the oath obliges -- which the viceroy of
    Carchemish does. The oath is readable from turn 1 by anyone who thinks to
    check it against the letter.
    """
    oath_id: str
    place: PlaceId                # where they are to muster: the letter's origin
    n: int                        # what the clause actually requires
    called_turn: int
    due_turn: int


@dataclasses.dataclass(frozen=True)
class MetalState:
    """Spec 6.5. `melt_ledger` only ever increases, and nothing announces it."""
    bronze_in_circulation: int    # bronze existing as tools, weapons, chariot fittings
    melt_ledger: int = 0          # CUMULATIVE shekels recycled out of circulation
    in_service_ceiling: int = 0   # what the court has hands and uses for; a fed
                                  # forge holds the stock here and never above it


@dataclasses.dataclass(frozen=True)
class HarbourCargoLot:
    """Finite, owned cargo physically present for the harbour to clear."""
    id: str
    owner: ActorId
    place: PlaceId
    good: GoodId
    quantity: int


@dataclasses.dataclass(frozen=True)
class Institution:
    """Spec 6.18. A building with a head, a condition and an output.

    `group` names the DependentGroup that staffs it, unchanged from 6.3, so the
    payroll and this are the same decision seen twice. `head` is a PersonId and
    may be empty, which costs the fabric 40 a fortnight because nobody is
    minding it.
    """
    id: str
    name: str
    kind: str                 # harbour | granary | walls | workshop | temple
                              # | archive | canal | road | household | garrison
    place: PlaceId
    group: GroupId = ""
    head: str = ""            # PersonId, or empty: the post is vacant
    condition: int = 1000     # 0..1000, the fabric; decays, nothing announces it
    capacity: int = 0         # what it could do whole and fed
    upkeep: tuple[tuple[GoodId, int], ...] = ()     # sorted good->qty per turn


@dataclasses.dataclass(frozen=True)
class Project:
    """Work in hand: a thing being built, or a thing being made whole (6.21).

    Days come out of the corvée, which is the same pool of hands the fields
    draw on, so every day here is a day the estates did not get and the bill
    arrives at the harvest a year later. Materials are consumed **as the work
    proceeds**, never at completion: an abandoned project is a loss and not a
    refund, and that is the whole reason building is a decision.

    `institution` names what is being repaired, or is empty on a build, in
    which case `kind` and `place` say what will stand there when it is done.
    """
    id: str
    institution: str          # InstitutionId being repaired, or "" on a build
    kind: str                 # what is going up (or what is being made whole)
    place: PlaceId
    name: str                 # what it will be called
    days_needed: int
    days_done: int = 0
    condition_target: int = 0     # what it stands at when finished
    capacity: int = 0             # only used on a build
    started_turn: int = 0
    spent: tuple[tuple[GoodId, int], ...] = ()   # eaten so far, never returned


@dataclasses.dataclass(frozen=True)
class Petition:
    """One dispute waiting in the hall (spec 6.19).

    The two claims are what the litigants say; `truth` is what was actually so
    and never crosses the Belief boundary.  The prose is authored because the
    figures alone do not say whether sixty cubits are a boundary or a debt.
    """
    id: str
    petitioner: str
    against: str
    kind: str
    claim: tuple[tuple[str, int], ...]
    counterclaim: tuple[tuple[str, int], ...]
    truth: tuple[tuple[str, int], ...]
    unit: str
    claim_text: str
    counter_text: str
    correction: str
    witness: str
    faction: str
    against_faction: str
    arrived_turn: int
    waiting: int = 0
    heard: bool = False


@dataclasses.dataclass(frozen=True)
class Precedent:
    """A ruling the king made and can be quoted back at him."""
    id: str
    petition_id: str
    kind: str
    verdict: str
    turn: int
    petitioner: str
    against: str
    document_ref: str


@dataclasses.dataclass(frozen=True)
class Rite:
    id: str
    fortnight: int
    hours: int
    requires: tuple[tuple[GoodId, int], ...]     # sorted good->qty
    skip_legitimacy: int
    skip_unrest: int


@dataclasses.dataclass(frozen=True)
class Court:
    actor: ActorId
    seat: PlaceId
    attention_base: int                          # hours per fortnight
    stores: Mapping[GoodId, int]                 # includes "grain" and "seed_grain"
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
    treasury_gifts_sent: tuple[GiftRecord, ...] = ()
    # --- M8: land and metal ---
    # Groups ordered to the fields instead of their own function. The garrison
    # on the harvest is the classic Bronze Age dilemma and is one action.
    at_harvest: tuple[GroupId, ...] = ()
    corvee_days: int = 0                 # sourced field-labour days called this season
    corvee_sources: tuple[tuple[GroupId, int], ...] = ()
    workshops: tuple[Workshop, ...] = ()
    formations: tuple[Formation, ...] = ()
    metals: MetalState = dataclasses.field(
        default_factory=lambda: MetalState(0, 0))
    # --- M12: the city as a machine (6.18) ---
    institutions: Mapping[str, Institution] = dataclasses.field(
        default_factory=dict)
    # 24 fortnights of what each head *reported*, for the CITY sparkline. What
    # he wrote is a real historical fact -- the letters exist -- so this is
    # World and not Belief, and it is the reported figure rather than the true
    # one because a flat line of reassurance is the thing worth drawing.
    institution_history: Mapping[str, tuple[int, ...]] = dataclasses.field(
        default_factory=dict)
    # Work in hand (6.21), and the days of this season's corvée already given
    # to it. `labour_supplied` subtracts those days from the fields, which is
    # the whole cost of building: not the goods, the hands.
    projects: Mapping[str, "Project"] = dataclasses.field(default_factory=dict)
    works_days: int = 0
    project_seq: int = 0
    # --- M12: justice (6.19) ---
    petitions: Mapping[str, Petition] = dataclasses.field(default_factory=dict)
    precedents: tuple[Precedent, ...] = ()
    # Mood is the court's memory of which interest the king has favoured. It is
    # intentionally not advice and does not say which side was truthful.
    faction_mood: Mapping[str, int] = dataclasses.field(default_factory=dict)
    # --- M12: revenue and placement (6.20, 6.22) ---
    land_due_rate: int = 300
    land_due_base: int = 300
    last_land_due: int = 0
    harbour_due_rate: int = 100
    harbour_due_customary: int = 100
    harbour_traffic: int = 1000
    last_harbour_due: int = 0
    named_heir: str = ""
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
    # --- D25: troops ---
    # Every summons this reign has received, answered or not, oldest first. They
    # are never removed: a demand that went unanswered four years ago is exactly
    # the sort of thing the other party remembers.
    summons: tuple[Summons, ...] = ()


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
    # Where the place stands on the authored map: a column and a row into
    # World.terrain. Court knowledge of the same kind as the name, drawn on the
    # World tablet and read by no rule -- distance in this game is counted in
    # courier legs and in nothing else, so a place can be a cell out of true
    # without one number in the simulation changing.
    col: int = 0
    row: int = 0
    # Whose empire answers for it, what it is (an imperial seat, a royal seat,
    # a town, and "seat" for your own), the letter drawn inside its brackets,
    # and the line the tablet writes about it. All four are authored.
    power: str = ""
    rank: str = "town"
    glyph: str = ""
    role: str = ""
    # What the mark IS, and whose it is (spec 8.3, docs/ALU_CLASSIFICATION.md).
    # An Alu is a city with a king, a hinterland, and its own decisions; a
    # palace centre is a located holding of one, with neither king nor
    # simulation of its own. `alu` is the owner and is empty on an Alu itself.
    # Both are authored: nothing is inferred from a name, a rank, or a size.
    kind: str = "alu"              # "alu" | "palace_centre"
    alu: PlaceId = ""
    harbour: bool = False          # the Alu reaches the sea through this mark
    population: int = 0            # authored opening size; S is seeded from it
    susceptible: int = 0
    infected: int = 0
    recovered: int = 0
    dead: int = 0                  # cumulative plague deaths at this place


@dataclasses.dataclass(frozen=True)
class PlagueState:
    """Integer SIR parameters and explicit material introduction state.

    An authored import is a scenario boundary condition: infected travellers
    arrive at a named place on a named turn.  Thereafter the disease can reach
    another settlement only through modeled contact.  At present the moving
    people represented in World are couriers, whose arrivals are recorded here
    for consumption by the disease phase.
    """
    beta: int = 0                  # transmission, per mille
    gamma: int = 0                 # recovery, per mille
    mortality: int = 0             # deaths among the infected, per mille
    exposure: int = 0              # chance in 1000 that an exposed arrival seeds
    import_place: PlaceId = ""     # authored external arrival boundary
    import_turn: int = -1
    import_cases: int = 0
    began_turn: int | None = None
    # Oaths the player has spent an offering on, in the order he tried them.
    # Projected because he remembers the rites, with no divine verdict.
    expiated: tuple[str, ...] = ()
    # (courier id, settlement reached) pairs accumulated by the movement phase
    # and cleared by the disease phase.  Sorting by both ids makes results
    # independent of container iteration order.
    infectious_arrivals: tuple[tuple[str, PlaceId], ...] = ()


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
    recipient: ActorId | None = None
    # Outgoing letter provenance survives after the courier leaves transit.
    # Defaults keep predecessor archive fixtures and old constructors valid.
    terms: tuple["LetterTerm", ...] = ()
    path: tuple[PlaceId, ...] = ()
    reply_to: str = ""
    scribe_id: str = ""
    seal: str = ""
    courier_id: str = ""


@dataclasses.dataclass(frozen=True)
class Route:
    a: PlaceId
    b: PlaceId
    legs: int          # fortnights to cross
    mode: str          # "sea" | "land" | "river"
    seasonal: bool     # sea legs shut outside the sailing window
    risk: int          # 0..1000 base interception/loss weight
    # The ground the route actually crosses, as (col, row) turns on the map.
    # A road is not a straight line: it follows the valley and goes round the
    # mountain, and `tools/route_geography.py` is what decides where. Empty
    # means nobody has laid it yet, and the tablet falls back to a straight one.
    course: tuple[tuple[int, int], ...] = ()


@dataclasses.dataclass(frozen=True)
class Terrain:
    """The ground itself: one character per cell, authored in `content/`.

    Scenery for the World tablet, and nothing more. No rule reads it, nothing
    is calculated from it, and a scenario that authors none simply draws a map
    of marks with no ground under them. It lives on World because `content/` is
    where it is authored and Belief is the only way anything authored reaches
    the screen.

    `west` and `north` are hundredths of a degree at column 0 and row 0, and
    `step_lon`/`step_lat` how much ground one cell covers, in the same units.
    Nothing in the engine uses them; they are carried so that a tool can turn a
    real latitude into a column once, and so that a reader of the scenario can
    tell what he is looking at.
    """
    rows: tuple[str, ...] = ()
    west: int = 0
    north: int = 0
    step_lon: int = 0
    step_lat: int = 0
    legend: str = ""


@dataclasses.dataclass(frozen=True)
class Site:
    """One holding in an Alu's hinterland: a small palace, an estate, a mine.

    A palace centre has a name; a capacity does not. Both belong to one Alu
    and are not towns; a palace centre is not addressable by courier.

    `role` is the classification and it is authored, never guessed: a palace
    centre is a place that can be raided, garrisoned, or lost on its own, and a
    capacity is not a place at all but ground and production belonging to the
    Alu. Nothing here is ever a settlement (docs/ALU_CLASSIFICATION.md §4).
    """
    kind: str            # "palace" | "grain" | "copper" | "tin" | ...
    alu: PlaceId         # whose hinterland it lies in
    role: str = "capacity"   # "palace_centre" | "capacity"
    capacity: str = ""       # "food" | "copper" | ...; empty on a palace centre
    name: str = ""           # authored on a palace centre; empty on a capacity
    col: int = 0
    row: int = 0


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
    # If set, a letter from this correspondent is a summons under the named oath
    # (D25). The number of men is the clause's, not the letter's.
    summons_oath: str = ""


@dataclasses.dataclass(frozen=True)
class Letter:
    """The physical tablet that travels and is read.

    Incoming tablets may render authored facts on demand. Outgoing tablets
    retain the player's exact text and explicit terms so replay never asks a
    model to reconstruct authoritative intent.
    """
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
    archived: bool = False
    delegated_to: ActorId | None = None
    delegated_turn: int | None = None
    outgoing: bool = False       # True = the player's own reply
    text: str = ""               # exact outgoing prose; never model-regenerated
    terms: tuple["LetterTerm", ...] = ()
    reply_to: str = ""
    scribe_id: str = ""
    seal: str = ""
    courier_id: str = ""
    # What was actually the case when he wrote (spec 6.8). Never projected into
    # Belief and never shown to the model: the ruler learns it, if at all, from a
    # second correspondent who saw the same thing. Empty means "he had no motive
    # to lie, so the assertion is the truth".
    true_facts: tuple[tuple[str, object], ...] = ()
    protocol_profile: str = ""
    protocol_total: int = 0
    protocol_violations: tuple[str, ...] = ()
    # This tablet is a summons under the named oath (D25). Carried on the letter
    # because the summons begins when the demand reaches the court, not when the
    # correspondent sat down to dictate it a month's sailing away.
    summons_oath: str = ""
    # The courier party has been co-located with an infected settlement during
    # this journey.  This is physical journey state, never projected as a fact
    # written on the tablet.
    disease_exposed: bool = False


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
    # anyone until a living man swears it again.
    # There is never a province that is loyal; there is a named man who is.
    lapsed: bool = False
    # ...with one exception, and M10 turns on it. An oath sworn to a KING is a
    # personal bond and dies with either man. A vow sworn to a GOD is a
    # dedication of the house and the city. So a vow does not lapse when the
    # man who made it dies; its tablet remains a human and institutional fact.
    binds_house: bool = False


# What a foreign court may do with a tablet that has reached it (spec 6.6, and
# the correspondence workstream in SPEC.md 6.1). Closed, because a decision the
# inspector cannot name is a decision nobody can explain afterwards. "ignore" is
# a real answer and is why silence has to be visible state rather than an
# absence: the court that never replies has decided, and the king cannot tell
# that apart from a drowned courier.
CORRESPONDENCE_DECISIONS = frozenset({
    "accept",     # the terms stand as written
    "refuse",     # the terms are declined, and the reply says so
    "counter",    # different terms are offered back
    "delay",      # the answer waits, and the case is looked at again
    "ignore",     # no reply is ever written
})


@dataclasses.dataclass(frozen=True)
class ForeignCourt:
    """What an autonomous correspondent has and needs, in its own units.

    Deliberately small, and a deletion target: SPEC.md 6.2 unifies Ugarit and
    the foreign settlements onto one material grammar, and when that lands this
    record is replaced by the kernel's stores, cohorts, and obligations. Until
    then a foreign court still has to be able to decide from something material
    rather than from an authored mood, or "the court knows its own shortage" is
    prose.

    `need` is the fortnightly draw against `stores`; `floor` is the quantity the
    court will not part with whatever it is asked, because a granary emptied for
    a friend is a granary emptied.
    """
    actor: ActorId
    place: PlaceId
    stores: Mapping[GoodId, int] = dataclasses.field(default_factory=dict)
    need: Mapping[GoodId, int] = dataclasses.field(default_factory=dict)
    floor: Mapping[GoodId, int] = dataclasses.field(default_factory=dict)
    people: int = 0


@dataclasses.dataclass(frozen=True)
class CorrespondenceCase:
    """One delivered tablet awaiting, or having received, a foreign answer.

    The case is the record the inspector reads to answer "why did Ma'hadu say
    no": it names the tablet, the actor, the turn it arrived, the terms as
    delivered, the decision, and the claim ids the decision rested on. It never
    holds World: the deciding policy is handed `(actor, belief)` and this case,
    and nothing else.

    `reply_text` stores accepted prose exactly once. Replay reads it; replay
    never asks a model for it again (spec 2.6, 2.7).
    """
    id: str
    letter_id: str
    actor: ActorId
    place: PlaceId
    received_turn: int
    terms: tuple["LetterTerm", ...] = ()
    decision: str = ""
    decided_turn: int | None = None
    # A delayed case is reconsidered on this turn; 0 while nothing is deferred.
    delay_until: int = 0
    # Terms offered back. Non-empty only on a counter.
    counter_terms: tuple["LetterTerm", ...] = ()
    # Claim ids behind the decision. Empty is legal only before deciding.
    basis: tuple[str, ...] = ()
    reply_letter_id: str = ""
    reply_text: str = ""

    def __post_init__(self) -> None:
        if self.decision and self.decision not in CORRESPONDENCE_DECISIONS:
            raise ValueError(
                f"unregistered correspondence decision: {self.decision!r}")
        if self.counter_terms and self.decision != "counter":
            raise ValueError(
                f"{self.id}: counter terms on a {self.decision or 'pending'} case")
        if self.decision and self.decided_turn is None:
            raise ValueError(f"{self.id}: a decision happens on a turn")

    def open(self) -> bool:
        """Still awaiting an answer. A delayed case is open; an ignored one is not."""
        return not self.decision or self.decision == "delay"


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
    # The autonomous world (Task 2). Always present; not yet wired into play.
    kernel: "Kernel"
    # Anything that "arrives later" is a Scheduled (spec 3.3). Sorted, stable.
    schedule: tuple["Scheduled", ...] = ()
    # Mail (spec 6.6). Places/routes/correspondents authored; the rest is live.
    places: Mapping[PlaceId, Place] = dataclasses.field(default_factory=dict)
    routes: tuple[Route, ...] = ()
    terrain: Terrain = Terrain()             # authored ground; no rule reads it
    sites: tuple[Site, ...] = ()             # the hinterland of the hubs
    correspondents: tuple[Correspondent, ...] = ()
    season: Mapping[str, tuple[int, ...]] = dataclasses.field(default_factory=dict)
    letters_in_transit: tuple[Letter, ...] = ()
    inbox: tuple[Letter, ...] = ()            # arrived letters: the Stack's source
    letter_seq: int = 0                       # monotonic id counter
    # Structured marks on dispatched tablets persist as legal/material records.
    letter_reservations: tuple["GoodsReservation", ...] = ()
    letter_obligations: tuple["LetterObligation", ...] = ()
    letter_claims: tuple["RequestClaim", ...] = ()
    marriage_proposals: tuple["MarriageProposal", ...] = ()
    # --- the far side of the correspondence (SPEC.md 6.1 phase B) ---
    # What each autonomous correspondent holds and needs, what it believes, and
    # every tablet of ours that has reached it. `foreign_beliefs` values are
    # engine.believe.Belief; the annotation stays loose so state.py keeps
    # importing nothing but the date.
    foreign_courts: Mapping[ActorId, ForeignCourt] = dataclasses.field(
        default_factory=dict)
    foreign_beliefs: Mapping[ActorId, object] = dataclasses.field(
        default_factory=dict)
    correspondence: tuple[CorrespondenceCase, ...] = ()
    case_seq: int = 0
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
    # The whole climate series, precomputed at scenario start for deterministic
    # agriculture. Indexed by absolute turn, 0..200 with 100 normal. Never
    # projected into Belief or read ahead by divination.
    climate: tuple[int, ...] = ()
    # Response tables (spec 6.4), authored in content/land.toml.
    land_tables: Mapping[str, tuple[tuple[int, int], ...]] = dataclasses.field(
        default_factory=dict)
    land_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    house_tables: Mapping[str, tuple[tuple[int, int], ...]] = dataclasses.field(
        default_factory=dict)
    house_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    # Building and repair (6.21), authored in content/works.toml.
    works_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    works_season: str = ""       # the named span in `season` mudbrick goes up in
    works_materials: Mapping[GoodId, int] = dataclasses.field(
        default_factory=dict)
    works_plans: Mapping[str, Mapping[str, int]] = dataclasses.field(
        default_factory=dict)
    # Authored disputes, including their hidden truth, fixed at load. A case
    # enters the hall when its `arrived_turn` comes.
    justice_cases: tuple[Petition, ...] = ()
    justice_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    revenue_rules: Mapping[str, int] = dataclasses.field(default_factory=dict)
    revenue_good: GoodId = "oil"
    revenue_merchants: tuple[ActorId, ...] = ()
    harbour_cargo: Mapping[str, HarbourCargoLot] = dataclasses.field(
        default_factory=dict)
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
