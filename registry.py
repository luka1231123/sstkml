"""One declarative description per player action (UI/UX spec 21, 19).

Every player action used to carry its cost in three places: the GUI charged a
constant at the call site, `ai.parser.action_cost` charged a second one on the
typed path, and the normative table in the UI specification stated a third. The
audit found them already disagreeing -- `DelegateLetter` charged 1h through the
Inbox and 0h through the parser, so the same order cost the player a different
hour depending on how they said it.

That is the bug this module exists to make impossible. A descriptor states the
cost, the label, the contexts it appears in, the command grammar, the mnemonic,
and the help topic *once*. Screens, hit regions, key handlers, the command
parser, Help, and the terminal game all read it. Nothing else is allowed to
name a cost.

No engine call and no toolkit import lives here: this is a table about actions,
not a place where they happen. `tools/inventory.py` checks it against the real
action union, so an action added to the engine without a route into the game
fails the suite rather than becoming unreachable.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A

# Status values for `ActionResult`. A refusal is a first-class outcome: the
# whole point of routing results through one type is that "nothing happened"
# has to say why, in the window the player was looking at (spec 21).
PREVIEW = "preview"
SUCCESS = "success"
REFUSAL = "refusal"
CANCELLED = "cancelled"


@dataclasses.dataclass(frozen=True)
class Field:
    """One argument an action needs, and the domain it is drawn from.

    `domain` names a set of legal entities ("person", "tablet", "group") rather
    than holding them: the legal set depends on Belief at the moment of asking,
    and a descriptor is a constant. Resolution happens against current
    affordances only (spec 8.4), never against the whole world.
    """
    name: str
    domain: str
    optional: bool = False
    argument: str = ""
    """Which engine field this fills, when it is not the one in this position.

    Fields are matched to the action's dataclass by position, which is right
    for almost all of them and reads better than restating every engine name.
    It is wrong wherever the grammar's word order differs from the engine's:
    `rule <verdict> on <petition>` says the verdict first and `RulePetition`
    takes the petition first, so building by position silently swapped the two
    and made the order unusable. Say the name in those cases.
    """


@dataclasses.dataclass(frozen=True)
class ActionDescriptor:
    id: str
    action_type: type
    label: str
    short_label: str
    contexts: tuple[str, ...]
    grammar: tuple[str, ...]
    cost: int
    fields: tuple[Field, ...] = ()
    mnemonic: str = ""
    help_topic: str = ""
    examples: tuple[str, ...] = ()
    confirm: bool = False
    batch: bool = False
    # Old save logs may contain actions which no longer belong to the live
    # interface. Keep their descriptor for decoding/cost compatibility while
    # excluding them from contexts, controls, and typed player affordances.
    player_accessible: bool = True


@dataclasses.dataclass(frozen=True)
class ActionResult:
    """What came of an attempt, in the shape every surface renders.

    `status` is one of the four constants above. A refusal carries `missing` so
    the window can say which prerequisite was absent rather than printing a
    blank line and swallowing the order (spec 2, "impossible input must explain
    itself").
    """
    status: str
    action_id: str = ""
    message: str = ""
    cost: int = 0
    hours_left: int = 0
    missing: str = ""
    targets: tuple[str, ...] = ()
    events: tuple = ()
    order_id: str = ""
    undo: str = ""

    @property
    def ok(self) -> bool:
        return self.status == SUCCESS

    def __bool__(self) -> bool:
        """A result is truthy exactly when the order went through.

        Callers written against the older `-> bool` reading of "did it work"
        keep their meaning; a refusal must never read as success merely because
        an object was returned.
        """
        return self.ok


def _d(*args, **kwargs) -> ActionDescriptor:
    return ActionDescriptor(*args, **kwargs)


# The normative map from UI/UX specification section 19. The `cost` column is
# the product contract: it is the attention the action costs on *every* path.
DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    _d("end_fortnight", A.EndTurn, "End fortnight", "End", ("hall",),
       ("end fortnight",), 0, mnemonic="space", help_topic="end_turn",
       confirm=True),
    _d("allocate", A.Allocate, "Allocation", "Allocate", ("roll",),
       ("allocate <amount> to <group>",), 0,
       (Field("amount", "quantity"), Field("group", "group")),
       mnemonic="a", help_topic="allocate"),
    _d("set_priority", A.SetPriority, "Priority", "Priority", ("roll",),
       ("prioritize <groups>",), 0, (Field("groups", "group"),),
       mnemonic="p", help_topic="priority", batch=True),
    _d("read_letter", A.ReadLetter, "Read", "Read", ("stack", "letter"),
       ("read <tablet>",), 2, (Field("tablet", "tablet"),),
       mnemonic="r", help_topic="read"),
    _d("file_letter", A.ArchiveLetter, "File", "File", ("stack", "letter"),
       ("file <tablet>", "restore <tablet>"), 0, (Field("tablet", "tablet"),),
       mnemonic="f", help_topic="file_letter"),
    _d("delegate_letter", A.DelegateLetter, "Delegate", "Delegate",
       ("stack", "letter"), ("delegate <tablet> to <person>",), 1,
       (Field("tablet", "tablet"), Field("person", "person")),
       mnemonic="g", help_topic="delegate_letter"),
    _d("dictate_reply", A.DictateReply, "Answer", "Answer",
       ("stack", "letter", "desk"), ("answer <tablet>",), 2,
       (Field("tablet", "tablet"),), mnemonic="w",
       help_topic="reply", confirm=True),
    _d("dispatch_letter", A.DispatchLetter, "Seal and send", "Dispatch",
       ("desk",), ("write to <court>",), 2,
       mnemonic="s", help_topic="reply", confirm=True),
    _d("inspect_ledger", A.InspectLedger, "Inspect count", "Inspect",
       ("stores", "land"), ("inspect granary", "inspect seed"), 1,
       (Field("ledger", "ledger"),), mnemonic="i", help_topic="inspect"),
    _d("send_gift", A.SendGift, "Gift", "Gift", ("relations", "letter"),
       ("gift <amount> <good> to <actor>",), 1,
       (Field("amount", "quantity"), Field("good", "good"),
        Field("actor", "actor")),
       # Not 'g': Delegate already owns that letter on a tablet, where both
       # actions are offered at once.
       mnemonic="i", help_topic="gift", confirm=True,
       player_accessible=False),
    _d("send_to_harvest", A.SendToHarvest, "Send to fields", "Send",
       ("roll", "land"), ("send <group> to harvest", "recall <group>"), 1,
       (Field("group", "group"),), mnemonic="h", help_topic="harvest_labour"),
    _d("assign_troops", A.AssignTroops, "Assign", "Assign", ("muster",),
       ("assign <formation> to <task> at <place>",), 1,
       (Field("formation", "formation"), Field("task", "task"),
        Field("place", "place", optional=True)),
       mnemonic="a", help_topic="assign_troops"),
     _d("raise_corvee", A.RaiseCorvee, "Raise corvée", "Corvée",
        ("land", "works", "muster"), ("raise corvee <days>",), 1,
        (Field("days", "quantity"),), mnemonic="c", help_topic="corvee",
        player_accessible=False),
     _d("levy_cohort", A.LevyCohort, "Levy cohort", "Levy",
        ("muster",),
        ("levy <heads> from <cohort> to <destination> for <duration> on <task> rationed by <ration_source> under <official>",), 1,
        (Field("cohort", "cohort"), Field("heads", "quantity"),
         Field("destination", "place"), Field("duration", "quantity"),
         Field("task", "corvee_task"), Field("ration_source", "institution"),
         Field("official", "person")),
        mnemonic="c", help_topic="corvee", confirm=True),
     _d("release_cohort", A.ReleaseCohort, "Release detachment", "Release",
        ("muster",), ("release <detachment>",), 0,
        (Field("detachment", "detachment"),), help_topic="corvee"),
     _d("receive_cohort", A.ReceiveCohort, "Answer displaced cohort", "Answer",
        ("alu", "justice"), ("<decision> <cohort> [to <place>]",), 1,
        (Field("cohort", "displaced"), Field("decision", "reception"),
         Field("destination", "place", optional=True)),
        help_topic="world", confirm=True),
     _d("finance_trade", A.FinanceTrade, "Finance trade", "Finance",
        ("trade",), ("finance <amount> <good>",), 1,
        (Field("amount", "quantity", argument="quantity"),
         Field("good", "good", argument="good")),
        mnemonic="f", help_topic="trade", confirm=True),
     _d("requisition_trade", A.RequisitionTrade, "Requisition cargo",
        "Requisition", ("trade",),
        ("requisition <amount> <good>",), 1,
        (Field("amount", "quantity", argument="quantity"),
         Field("good", "good", argument="good")),
        mnemonic="r", help_topic="trade", confirm=True),
     _d("exempt_trade", A.ExemptTrade, "Exempt trade from dues", "Exempt",
        ("trade",), ("exempt trade",), 0,
        mnemonic="e", help_topic="trade", confirm=True),
     _d("marry_abroad", A.MarryAbroad, "Marry abroad", "Marry",
       ("house", "relations"), ("marry <person> to <court>",), 2,
       (Field("person", "person"), Field("court", "actor")),
       mnemonic="m", help_topic="marry", confirm=True,
       player_accessible=False),
    _d("consult_diviner", A.ConsultDiviner, "Consult", "Consult", ("altar",),
       ("consult <question> [for <subject>] [with <offering>]",), 2,
       (Field("question", "question"), Field("subject", "person", True),
        Field("offering", "good", True)),
       mnemonic="c", help_topic="divination"),
    _d("suppress_omen", A.SuppressOmen, "Suppress", "Suppress",
       ("altar",), ("suppress <omen>",), 2, (Field("omen", "omen"),),
       mnemonic="s", help_topic="omen_response", confirm=True),
    _d("defy_omen", A.DefyOmen, "Defy", "Defy", ("altar",),
       ("defy <omen>",), 0, (Field("omen", "omen"),),
       mnemonic="d", help_topic="omen_response", confirm=True),
    _d("swear_oath", A.SwearOath, "Re-swear", "Swear", ("oaths",),
       ("swear <oath>",), 2, (Field("oath", "oath"),),
       mnemonic="s", help_topic="swear", confirm=True),
    _d("quarantine", A.Quarantine, "Close", "Close",
       ("plague", "world", "trade"),
       ("quarantine <place>", "lift quarantine <place>"), 1,
       (Field("place", "place"),), mnemonic="q", help_topic="quarantine",
       confirm=True),
    _d("expiate", A.Expiate, "Expiate", "Expiate", ("oaths", "altar"),
       ("expiate <oath> with <amount>",), 2,
       (Field("oath", "oath"), Field("amount", "quantity")),
       mnemonic="x", help_topic="expiate", confirm=True),
    _d("search_archive", A.SearchArchive, "Search", "Search", ("archive",),
       ("search archive for <terms>",), 1, (Field("terms", "text"),),
       mnemonic="s", help_topic="search"),
    _d("hear_petition", A.HearPetition, "Hear", "Hear", ("justice",),
       ("hear <petition>",), 1, (Field("petition", "petition"),),
       mnemonic="h", help_topic="justice_orders"),
    _d("rule_petition", A.RulePetition, "Rule", "Rule", ("justice",),
       ("rule <verdict> on <petition>",), 0,
       (Field("verdict", "verdict", argument="verdict"),
        Field("petition", "petition", argument="petition_id")),
       mnemonic="r", help_topic="justice_orders", confirm=True),
    _d("set_land_due", A.SetLandDue, "Set land due", "Land due", ("land",),
       ("set land due to <rate>",), 0, (Field("rate", "quantity"),),
       mnemonic="u", help_topic="dues"),
    _d("set_harbour_due", A.SetHarbourDue, "Set harbour due", "Harbour due",
       ("trade",), ("set harbour due to <rate>",), 0,
       (Field("rate", "quantity"),), mnemonic="u", help_topic="dues"),
    _d("place_person", A.PlacePerson, "Appoint", "Appoint",
       ("house", "institution", "muster"), ("appoint <person> to <post>",), 0,
       (Field("person", "person"), Field("post", "post")),
       # Not 'a': Assign owns that key in the Muster, where posts are filled.
       mnemonic="o", help_topic="appointments"),
    _d("dismiss_person", A.DismissPerson, "Dismiss", "Dismiss",
       ("house", "institution", "muster"), ("dismiss <post>",), 0,
       (Field("post", "post"),), mnemonic="k", help_topic="appointments",
       confirm=True),
    _d("name_heir", A.NameHeir, "Name heir", "Heir", ("house",),
       ("name <person> heir",), 0, (Field("person", "person"),),
       mnemonic="n", help_topic="heir", confirm=True),
    _d("begin_build", A.BeginBuild, "Begin", "Build", ("works",),
       ("build <kind> at <place>",), 1,
       (Field("kind", "plan"), Field("place", "place")),
       mnemonic="b", help_topic="build", confirm=True),
    _d("begin_repair", A.BeginRepair, "Repair", "Repair",
       ("alu", "institution", "works"), ("repair <institution>",), 1,
       (Field("institution", "institution"),), mnemonic="r",
       help_topic="repair", confirm=True),
    _d("abandon_work", A.AbandonWork, "Abandon", "Abandon", ("works",),
       ("abandon <project>",), 1, (Field("project", "project"),),
       mnemonic="z", help_topic="abandon", confirm=True),
)


BY_ID = {d.id: d for d in DESCRIPTORS}
BY_TYPE = {d.action_type: d for d in DESCRIPTORS}


def describe(action) -> ActionDescriptor | None:
    """The descriptor for an action instance or class, if it has one."""
    key = action if isinstance(action, type) else type(action)
    return BY_TYPE.get(key)


def cost_of(action) -> int:
    """The attention an action costs, on every path there is.

    This is the only function in the project permitted to answer that question.
    An action with no descriptor costs nothing, which is the right default for
    the engine's own event records -- they are not player intent and are never
    charged.
    """
    descriptor = describe(action)
    return 0 if descriptor is None else descriptor.cost


def argument_names(descriptor: ActionDescriptor) -> dict[str, str]:
    """Which engine field each descriptor field fills.

    The two lists are positional unless a field says otherwise: `Field("group",
    "group")` fills `group_id` because it comes first in both. That contract
    was already load-bearing -- the command palette builds actions by position
    -- but it was written down nowhere, and where it did not hold it swapped
    two arguments in silence. It reads the engine dataclass rather than
    restating its field names, so renaming one cannot leave a stale copy here.
    """
    engine = [field.name
              for field in dataclasses.fields(descriptor.action_type)]
    return {field.name: (field.argument or engine[index])
            for index, field in enumerate(descriptor.fields)
            if field.argument or index < len(engine)}


def player_descriptors() -> tuple[ActionDescriptor, ...]:
    """Descriptors which may be offered to the player in a new session.

    ``DESCRIPTORS`` remains the complete compatibility registry. In
    particular, old SendGift and MarryAbroad records still need their stable
    type and attention metadata when an existing reign is replayed.
    """
    return tuple(
        descriptor for descriptor in DESCRIPTORS
        if descriptor.player_accessible
    )


def in_context(context: str) -> tuple[ActionDescriptor, ...]:
    """Every action a given window can offer, in declaration order."""
    return tuple(
        descriptor for descriptor in player_descriptors()
        if context in descriptor.contexts
    )


def contexts() -> tuple[str, ...]:
    seen: list[str] = []
    for descriptor in player_descriptors():
        for context in descriptor.contexts:
            if context not in seen:
                seen.append(context)
    return tuple(seen)
