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
class ArchiveLetter:
    """Move an arrived tablet off the active pile without destroying it."""
    letter_id: str
    archived: bool = True


@dataclasses.dataclass(frozen=True)
class DelegateLetter:
    """Entrust follow-up to a named, living member of the court household.

    Delegation is a recorded responsibility, not an automatic answer: the
    correspondent continues to wait until the ruler actually sends a reply.
    """
    letter_id: str
    person_id: str


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


@dataclasses.dataclass(frozen=True)
class SendToHarvest:
    """Order a group to the fields instead of its own function (spec 6.4).
    One line, because the garrison-or-the-harvest choice must be one line."""
    group_id: str
    to_fields: bool = True


@dataclasses.dataclass(frozen=True)
class AssignTroops:
    """Spec 11: `ASSIGN_TROOPS formation=<id> task=... place=<id>`. The same
    men hold the walls, bring in the barley, or go north to a muster, and they
    cannot do two of those (D25). An empty `place` means the seat."""
    formation_id: str
    task: str                     # garrison | harvest | campaign | watch
    place: str = ""


@dataclasses.dataclass(frozen=True)
class RaiseCorvee:
    """Labour levied outside the ration lists entirely, and paid for in unrest."""
    days: int


@dataclasses.dataclass(frozen=True)
class DredgeCanal:
    """Restore an irrigated estate's canal. Only in the low-water window."""
    estate_id: str
    days: int


@dataclasses.dataclass(frozen=True)
class MarryAbroad:
    """Send a daughter to a foreign court (spec 6.10). The primary instrument
    of foreign policy, and it is not reversible."""
    person_id: str
    actor: str


@dataclasses.dataclass(frozen=True)
class ConsultDiviner:
    question: str        # "harvest" | "death" | "route"
    subject: str = ""
    offering_good: str = ""
    offering_quantity: int = 0


@dataclasses.dataclass(frozen=True)
class SuppressOmen:
    omen_id: str


@dataclasses.dataclass(frozen=True)
class DefyOmen:
    omen_id: str


@dataclasses.dataclass(frozen=True)
class SwearOath:
    """Re-swear a lapsed oath. Every succession requires this, and the other
    party will want something for it (spec 6.9)."""
    oath_id: str


@dataclasses.dataclass(frozen=True)
class Quarantine:
    """Close the routes to a place (spec 6.12). It works, and it costs: the
    trade stops, the correspondent takes it personally, and the letters that
    would have told you what was happening there stop too."""
    place_id: str
    lift: bool = False


@dataclasses.dataclass(frozen=True)
class Expiate:
    """Make an offering against one named oath. Nothing in the response will
    tell you whether it was the right one (spec 6.12)."""
    oath_id: str
    offering: int = 0


@dataclasses.dataclass(frozen=True)
class SearchArchive:
    """Spec 6.17: keyword and tag, one hour per query."""
    query: str


@dataclasses.dataclass(frozen=True)
class HearPetition:
    """Spend an audience hour hearing both sides. Truth remains hidden."""
    petition_id: str


@dataclasses.dataclass(frozen=True)
class RulePetition:
    """Give one of 6.19's four verdicts, heard or unheard."""
    petition_id: str
    verdict: str                 # for | against | split | defer


@dataclasses.dataclass(frozen=True)
class SetLandDue:
    rate: int                    # per thousand of the gross harvest


@dataclasses.dataclass(frozen=True)
class SetHarbourDue:
    rate: int                    # per thousand of cargo cleared


@dataclasses.dataclass(frozen=True)
class PlacePerson:
    person_id: str
    post: str                    # institution id | governor: | command: | court:


@dataclasses.dataclass(frozen=True)
class DismissPerson:
    post: str                    # institution id | governor: | command: | court:


@dataclasses.dataclass(frozen=True)
class NameHeir:
    person_id: str


# --- Events ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TurnAdvanced:
    year: int
    fortnight: int


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
class DependentsDeparted:
    group_id: str
    place_id: str
    heads: int
    reason: str


@dataclasses.dataclass(frozen=True)
class DependentsDied:
    group_id: str
    place_id: str
    heads: int
    cause: str


@dataclasses.dataclass(frozen=True)
class GroupRevoltChanged:
    group_id: str
    place_id: str
    revolting: bool
    heads: int


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
class LetterArchived:
    letter_id: str
    archived: bool


@dataclasses.dataclass(frozen=True)
class LetterDelegated:
    letter_id: str
    person_id: str
    turn: int


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


# --- M8: land and metal ------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Sown:
    seed_qa: int
    recommended_qa: int


@dataclasses.dataclass(frozen=True)
class Harvested:
    estate_id: str
    qa: int


@dataclasses.dataclass(frozen=True)
class Threshed:
    qa: int
    held_back_as_seed: int


@dataclasses.dataclass(frozen=True)
class SentToHarvest:
    group_id: str
    to_fields: bool


@dataclasses.dataclass(frozen=True)
class TroopsAssigned:
    formation_id: str
    task: str
    place: str


@dataclasses.dataclass(frozen=True)
class SummonsReceived:
    """A demand for men arrived and the clock started (D25). The count here is
    the oath's, not the tablet's -- the tablet is free to ask for more."""
    oath_id: str
    place: str
    n: int
    due_turn: int


@dataclasses.dataclass(frozen=True)
class CorveeRaised:
    days: int
    unrest_delta: int
    sources: tuple[tuple[str, int], ...] = ()


@dataclasses.dataclass(frozen=True)
class CanalDredged:
    estate_id: str
    days: int
    condition: int


@dataclasses.dataclass(frozen=True)
class BronzeSmelted:
    bronze: int
    copper_used: int
    tin_used: int


@dataclasses.dataclass(frozen=True)
class BronzeWorn:
    """Bronze leaving service through wear, loss, burial, and breakage."""
    amount: int


@dataclasses.dataclass(frozen=True)
class FormationCapabilityChanged:
    formation_id: str
    before: int
    after: int
    replacement_rate: int


@dataclasses.dataclass(frozen=True)
class InstitutionDecayed:
    """The fabric went a little. Nothing surfaces this (spec 6.18, D19)."""
    institution_id: str
    condition: int


@dataclasses.dataclass(frozen=True)
class InstitutionUpkeepConsumed:
    institution_id: str
    good: str
    amount: int


@dataclasses.dataclass(frozen=True)
class BronzeMelted:
    """Recycled out of circulation to meet a shortfall. Nothing surfaces this
    to the player; it is the melt ledger's only input (spec 6.5)."""
    amount: int
    ledger_total: int


@dataclasses.dataclass(frozen=True)
class WorkshopDemandMet:
    demand: int
    from_stores: int


# --- M9: the house and the cult ----------------------------------------------

@dataclasses.dataclass(frozen=True)
class Conceived:
    mother: str
    father: str
    due_turn: int


@dataclasses.dataclass(frozen=True)
class ChildBorn:
    child_id: str
    mother: str
    father: str
    sex: str


@dataclasses.dataclass(frozen=True)
class HouseMemberDied:
    person_id: str
    name: str
    age_years: int


@dataclasses.dataclass(frozen=True)
class RulerSucceeded:
    person_id: str
    name: str
    contested: bool
    rivals: int


@dataclasses.dataclass(frozen=True)
class SuccessionFailed:
    last_ruler: str


@dataclasses.dataclass(frozen=True)
class MarriedAbroad:
    person_id: str
    name: str
    actor: str


@dataclasses.dataclass(frozen=True)
class OmenTaken:
    omen_id: str
    question: str
    subject: str
    reported: str


@dataclasses.dataclass(frozen=True)
class OmenSuppressed:
    omen_id: str


@dataclasses.dataclass(frozen=True)
class OmenLeaked:
    omen_id: str
    legitimacy_delta: int


@dataclasses.dataclass(frozen=True)
class OmenDefied:
    omen_id: str
    legitimacy_delta: int


@dataclasses.dataclass(frozen=True)
class OathSworn:
    oath_id: str
    sworn_by: str


@dataclasses.dataclass(frozen=True)
class PlagueBegan:
    place_id: str
    turn: int


@dataclasses.dataclass(frozen=True)
class PlagueSpread:
    place_id: str


@dataclasses.dataclass(frozen=True)
class PlagueProgressed:
    """Material SIR ledger for one settlement and one disease phase."""
    place_id: str
    new_infections: int
    recovered: int


@dataclasses.dataclass(frozen=True)
class PlagueDeaths:
    place_id: str
    dead: int


@dataclasses.dataclass(frozen=True)
class OathExpiated:
    """A performed ritual, with no objective divine verdict."""
    oath_id: str
    offering: int


@dataclasses.dataclass(frozen=True)
class QuarantineSet:
    place_id: str
    lifted: bool


@dataclasses.dataclass(frozen=True)
class ArchiveSearched:
    query: str
    hits: int


@dataclasses.dataclass(frozen=True)
class OathLapsed:
    oath_id: str
    reason: str


@dataclasses.dataclass(frozen=True)
class PetitionArrived:
    petition_id: str
    petitioner: str
    against: str
    kind: str


@dataclasses.dataclass(frozen=True)
class PetitionHeard:
    petition_id: str


@dataclasses.dataclass(frozen=True)
class PetitionRuled:
    petition_id: str
    verdict: str
    precedent_ref: str = ""


@dataclasses.dataclass(frozen=True)
class JusticeCorrectionDue:
    """Hidden scheduled payload. Only its witness tablet enters Belief."""
    petition_id: str
    witness: str
    finding: str
    legitimacy_delta: int


@dataclasses.dataclass(frozen=True)
class LandDueSet:
    rate: int


@dataclasses.dataclass(frozen=True)
class HarbourDueSet:
    rate: int


@dataclasses.dataclass(frozen=True)
class LandDueTaken:
    gross: int
    rate: int
    taken: int


@dataclasses.dataclass(frozen=True)
class HarbourDueTaken:
    good: str
    cargoes: int
    rate: int
    taken: int
    lot_id: str = ""
    owner: str = ""
    cleared: int = 0


@dataclasses.dataclass(frozen=True)
class HarbourCargoWithdrawn:
    lot_id: str
    owner: str
    good: str
    quantity: int


@dataclasses.dataclass(frozen=True)
class MerchantResponseDue:
    actor: str
    esteem_delta: int
    traffic_delta: int


@dataclasses.dataclass(frozen=True)
class MerchantWithdrew:
    actor: str
    esteem_delta: int
    traffic_delta: int


@dataclasses.dataclass(frozen=True)
class EstateLabourFled:
    estate_id: str
    place_id: str
    before: int
    after: int


@dataclasses.dataclass(frozen=True)
class PersonPlaced:
    person_id: str
    post: str
    displaced: str = ""


@dataclasses.dataclass(frozen=True)
class PersonDismissed:
    person_id: str
    post: str


@dataclasses.dataclass(frozen=True)
class HeirNamed:
    person_id: str
    displaced_rank: int


# --- M12: building and repair (6.21) ------------------------------------------

@dataclasses.dataclass(frozen=True)
class BeginBuild:
    """Put something up that is not there. Days, materials, and a season."""
    kind: str
    place: str


@dataclasses.dataclass(frozen=True)
class BeginRepair:
    """Buy back the years nobody minded it. Cheaper than building, and nothing
    reminds you that it wants doing."""
    institution: str


@dataclasses.dataclass(frozen=True)
class AbandonWork:
    """Call the men off. What has been eaten stays eaten (6.21)."""
    project: str


@dataclasses.dataclass(frozen=True)
class WorkBegun:
    project: str
    what: str
    days_needed: int


@dataclasses.dataclass(frozen=True)
class WorkProgressed:
    project: str
    days: int
    days_done: int
    days_needed: int


@dataclasses.dataclass(frozen=True)
class WorkMaterialConsumed:
    project: str
    good: str
    amount: int


@dataclasses.dataclass(frozen=True)
class WorkFinished:
    project: str
    institution: str
    what: str
    built: bool


@dataclasses.dataclass(frozen=True)
class WorkAbandoned:
    project: str
    what: str
    days_lost: int


@dataclasses.dataclass(frozen=True)
class OfferingConsumed:
    purpose: str
    good: str
    amount: int


# --- Registry for log round-tripping -----------------------------------------

_TYPES = {
    c.__name__: c for c in (
        EndTurn, Allocate, SetPriority, EatSeed, ReadLetter, ArchiveLetter,
        DelegateLetter, DictateReply,
        InspectLedger, SendGift, SendToHarvest, RaiseCorvee, DredgeCanal,
        HearPetition, RulePetition,
        SetLandDue, SetHarbourDue, PlacePerson, DismissPerson, NameHeir,
        AssignTroops, TroopsAssigned, SummonsReceived,
        Sown, Harvested, Threshed, SentToHarvest, CorveeRaised, CanalDredged,
        BronzeSmelted, BronzeWorn, FormationCapabilityChanged,
        BronzeMelted, WorkshopDemandMet,
        InstitutionDecayed, InstitutionUpkeepConsumed,
        BeginBuild, BeginRepair, AbandonWork, WorkBegun, WorkProgressed,
        WorkMaterialConsumed, WorkFinished, WorkAbandoned, OfferingConsumed,
        MarryAbroad, ConsultDiviner, SuppressOmen, DefyOmen, SwearOath,
        Conceived, ChildBorn, HouseMemberDied, RulerSucceeded,
        SuccessionFailed, MarriedAbroad, OmenTaken, OmenSuppressed,
        OmenLeaked, OmenDefied, OathSworn, OathLapsed,
        Quarantine, Expiate, SearchArchive,
        PlagueBegan, PlagueSpread, PlagueProgressed, PlagueDeaths, OathExpiated,
        QuarantineSet, ArchiveSearched,
        PetitionArrived, PetitionHeard, PetitionRuled, JusticeCorrectionDue,
        LandDueSet, HarbourDueSet, LandDueTaken, HarbourDueTaken,
        HarbourCargoWithdrawn, EstateLabourFled,
        MerchantResponseDue, MerchantWithdrew, PersonPlaced, PersonDismissed,
        HeirNamed,
        TurnAdvanced, Spoiled, RationsPaid, DependentsDeparted,
        DependentsDied, GroupRevoltChanged, RitePerformed,
        RiteSkipped, UnrestChanged, Grumbling, SeedEaten, AllocationSet,
        PrioritySet, LetterArrived, LetterDelivered, LetterSent,
        LetterIntercepted, LetterRead, LetterArchived, LetterDelegated,
        LedgerInspected, GiftSent, GiftArrived,
        GiftJudged, RumourArrived, PatronNoticeDue, PatronSought,
        ProtocolApplied, OathViolated,
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
