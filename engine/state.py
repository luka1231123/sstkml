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
    # Flight caused by high land dues never springs back when the rate falls.
    # 1000 is the opening body of hands; revenue.step only moves this downward.
    hands: int = 1000


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
    estates: Mapping[str, Estate] = dataclasses.field(default_factory=dict)
    # Groups ordered to the fields instead of their own function. The garrison
    # on the harvest is the classic Bronze Age dilemma and is one action.
    at_harvest: tuple[GroupId, ...] = ()
    corvee_days: int = 0                 # sourced field-labour days called this season
    corvee_sources: tuple[tuple[GroupId, int], ...] = ()
    # The only hard datum the player gets about the land (spec 6.4). True, and
    # a year stale.
    last_harvest: int = 0
    previous_harvest: int = 0
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
    # Where the place is, in hundredths of a degree north and east. Authored
    # court knowledge, like the name: it is drawn on the World tablet and is
    # never read by any rule. Distance in this game is counted in courier legs
    # and nothing else, so a coordinate can be wrong by a day's walk without a
    # single number in the simulation changing. Integers, because everything in
    # engine/ is -- a float here would be the one place a replay could drift.
    lat: int = 0
    lon: int = 0
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
    # If set, a letter from this correspondent is a summons under the named oath
    # (D25). The number of men is the clause's, not the letter's.
    summons_oath: str = ""


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
    archived: bool = False
    delegated_to: ActorId | None = None
    delegated_turn: int | None = None
    outgoing: bool = False       # True = the player's own reply
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
