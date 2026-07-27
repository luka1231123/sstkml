"""A world of settlements that run themselves (spec 6.1, M13.1 exit gate).

The gate this is built to pass:

    With Ugarit idle or removed, the other settlements continue to produce,
    consume, decide, and change.

So nothing here refers to the player, and no settlement is privileged. Each one
has a controlling organization; that organization looks at what it can see,
decides from what it believes, competes for what is scarce, and lives with the
result. Delete any settlement and the rest carry on, because none of them was
reading anything the others owned.

The economy modelled is deliberately one chain -- fields, labour, grain,
eating, and a tribute obligation -- because M13.1's job is the kernel, not the
economy. M13.2 puts the grain slice on top of it.

One honest limitation, stated rather than hidden: production here runs every
fortnight and is not gated on the agricultural seasons. The kernel needs a
production phase that competes for labour and conserves goods, and it has one;
it does not yet need the sowing-growing-harvest-threshing chain, which is
exactly what M13.2 delivers on top of this. The seasons are authored and used
-- the tribute falls due in the harvest window -- but the fields do not keep
them yet. Do not read the grain figures here as a balanced economy.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine import believe as B
from engine import obligation as O
from engine import observe as OB
from engine import ownership as W
from engine.core import Date, stream
from engine.entity import Cohort, EntityId, Registry, check, mint
from engine.kernel import resolve as R
from engine.kernel import turn as T
from engine.kernel.intent import Intent, Snapshot, open_turn

GRAIN = "grain"


@dataclasses.dataclass(frozen=True)
class Kernel:
    """Everything the autonomous world is. No court, no player, no exceptions."""
    seed: int
    date: Date
    registry: Registry
    book: W.Book
    obligations: tuple[O.Obligation, ...] = ()
    beliefs: Mapping[EntityId, B.Belief] = dataclasses.field(
        default_factory=dict)
    seasons: Mapping[str, tuple[int, ...]] = dataclasses.field(
        default_factory=dict)
    climate: tuple[int, ...] = ()     # by absolute turn; 100 is an ordinary year

    # --- reading ------------------------------------------------------------

    def controller(self, settlement: EntityId) -> EntityId:
        """The organization that decides for a settlement, or "" if none does."""
        for org_id in sorted(self.registry.orgs):
            org = self.registry.orgs[org_id]
            if org.settlement == settlement and org.kind == "council":
                return org_id
        return ""

    def cohorts_of(self, settlement: EntityId) -> tuple[Cohort, ...]:
        return tuple(self.registry.cohorts[c] for c in sorted(self.registry.cohorts)
                     if self.registry.cohorts[c].settlement == settlement)

    def stores(self, settlement: EntityId, good: str = GRAIN) -> int:
        return sum(lot.quantity for lot in self.book.at(settlement)
                   if lot.good == good)

    def people(self, settlement: EntityId) -> int:
        return sum(c.people for c in self.cohorts_of(settlement))

    def labour(self, settlement: EntityId) -> int:
        return sum(c.labour() for c in self.cohorts_of(settlement))

    def field_site(self, settlement: EntityId) -> EntityId:
        for site_id in sorted(self.registry.sites):
            site = self.registry.sites[site_id]
            if site.settlement == settlement and site.function == "estate":
                return site_id
        return ""

    def deciders(self) -> tuple[EntityId, ...]:
        """Every organization that decides, in a stable order.

        More than one per settlement: a palace and a temple both draw on the
        same people, and which of them goes short in a thin year is settled by
        the allocator rather than by an authored split.
        """
        return tuple(
            org_id for org_id in sorted(self.registry.orgs)
            if self.registry.orgs[org_id].policy in POLICIES
            and self.registry.settlements[
                self.registry.orgs[org_id].settlement].autonomous)

    def autonomous(self) -> tuple[EntityId, ...]:
        """The settlements that decide for themselves, in a stable order."""
        return tuple(
            s for s in sorted(self.registry.settlements)
            if self.registry.settlements[s].autonomous and self.controller(s))

    def climate_at(self, absolute: int) -> int:
        if not self.climate:
            return 100
        return self.climate[absolute % len(self.climate)]


# --- policy (spec 10.11) ------------------------------------------------------
#
# The signature is the contract: `(actor, belief)`. A policy that took the world
# could read another settlement's granary, and nothing in the output would show
# it had. tests/test_kernel_world.py inspects these signatures.

def subsistence(actor: EntityId, belief: B.Belief) -> tuple[Intent, ...]:
    """Feed your people, work your fields, pay what you believe you owe.

    Everything below comes from `belief.value(...)`. If the council has not
    seen its granary this turn it acts on the last count it has, which is the
    entire reason claims carry a date.
    """
    intents: list[Intent] = []

    # The council knows its own place: the claims it holds about labour, stores,
    # and what it owes are keyed by the settlement it sits in. Sorted, so that
    # a council with claims about more than one place decides in a fixed order.
    subjects = sorted({c.subject for c in belief.claims
                       if c.attribute in ("labour", "stores_grain", "owes")})
    for subject in subjects:
        labour = belief.value(subject, "labour", 0)
        if labour > 0:
            intents.append(Intent(
                id=f"{actor}|work|{subject}", actor=actor, kind="work",
                turn=belief.value(subject, "turn", 0), subject=subject,
                resource=f"{subject}#labour", quantity=labour,
                authority=actor, priority=1,
                basis=tuple(c.id for c in belief.about(subject, "labour"))))

        owed = belief.value(subject, "owes", 0)
        stores = belief.value(subject, "stores_grain", 0)
        if owed > 0:
            # Render only what the council believes it can spare. A tribute
            # that would empty the granary is not paid; that is a decision, and
            # it is why obligations default.
            spare = max(0, stores - belief.value(subject, "need", 0))
            offer = min(owed, spare)
            if offer > 0:
                intents.append(Intent(
                    id=f"{actor}|render|{subject}", actor=actor, kind="render",
                    turn=belief.value(subject, "turn", 0), subject=subject,
                    quantity=offer, authority=actor, priority=2,
                    basis=tuple(c.id for c in belief.about(subject, "owes"))))
    return tuple(intents)


def cult(actor: EntityId, belief: B.Belief) -> tuple[Intent, ...]:
    """Work the god's land. Render nothing: the temple owes the crown nothing.

    A second claimant on the same person-days is the point of this policy. The
    fields and the temple estate draw on one body of people, and the allocator
    -- not a hand-tuned split -- decides who goes short.
    """
    intents: list[Intent] = []
    subjects = sorted({c.subject for c in belief.claims
                       if c.attribute == "labour"})
    for subject in subjects:
        labour = belief.value(subject, "labour", 0)
        if labour <= 0:
            continue
        # The temple asks for the share of the season's hands custom gives it,
        # and asks for all of it whether or not the fields can spare them.
        intents.append(Intent(
            id=f"{actor}|work|{subject}", actor=actor, kind="work",
            turn=belief.value(subject, "turn", 0), subject=subject,
            resource=f"{subject}#labour", quantity=labour * 3 // 10,
            authority=actor, priority=1,
            basis=tuple(c.id for c in belief.about(subject, "labour"))))
    return tuple(intents)


POLICIES = {"subsistence": subsistence, "cult": cult}


# --- the phases ---------------------------------------------------------------

def _observe(kernel: Kernel, snapshot: Snapshot) -> tuple[Kernel, list]:
    """Phase 3. Each council counts what is in front of it, and nothing else."""
    world: Kernel = snapshot.world
    beliefs = dict(kernel.beliefs)
    turn = snapshot.turn
    for actor in world.deciders():
        settlement = world.registry.orgs[actor].settlement
        need = sum(c.ration() for c in world.cohorts_of(settlement))
        owed = sum(o.outstanding() for o in world.obligations
                   if o.party == settlement and o.status in ("due", "part_paid"))
        readings = {
            "stores_grain": world.stores(settlement),
            "people": world.people(settlement),
            "labour": world.labour(settlement),
        }
        belief = beliefs.get(actor, B.Belief(holder=actor))
        belief = OB.project(
            belief, OB.observe_local(actor, settlement, turn, readings), turn)
        # Two things the council works out rather than sees, recorded as its own
        # claims so that a policy reading only belief can still use them.
        belief = belief.add(
            B.Claim(id=f"{actor}|{turn}|need", holder=actor, subject=settlement,
                    attribute="need", value=need, source="inferred",
                    observed_turn=turn, received_turn=turn,
                    basis=(f"c|{actor}|{turn}|people",)),
            B.Claim(id=f"{actor}|{turn}|owes", holder=actor, subject=settlement,
                    attribute="owes", value=owed, source="observed",
                    observed_turn=turn, received_turn=turn),
            B.Claim(id=f"{actor}|{turn}|turn", holder=actor, subject=settlement,
                    attribute="turn", value=turn, source="observed",
                    observed_turn=turn, received_turn=turn))
        beliefs[actor] = belief
    return dataclasses.replace(kernel, beliefs=beliefs), []


def _intents(kernel: Kernel, snapshot: Snapshot) -> tuple[Intent, ...]:
    """Phase 4. Every council decides from its own belief, from one snapshot."""
    world: Kernel = snapshot.world
    produced: list[Intent] = []
    for actor in world.deciders():
        policy = POLICIES[world.registry.orgs[actor].policy]
        produced.extend(policy(actor, kernel.beliefs[actor]))
    return tuple(sorted(produced, key=lambda i: i.id))


def _capacity(kernel: Kernel) -> dict[EntityId, int]:
    """The exclusive pools. One labour pool per settlement, this turn only."""
    return {f"{s}#labour": kernel.labour(s)
            for s in sorted(kernel.registry.settlements)}


def _produce(kernel: Kernel, allocation: R.Allocation) -> tuple[Kernel, list]:
    """Phase 6. Granted person-days become grain, or do not."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    climate = kernel.climate_at(kernel.date.absolute)

    # Each organization's granted days make its own grain: the temple's estate
    # is not the council's granary, and a lot has one owner.
    made: dict[tuple[EntityId, EntityId], int] = {}
    for grant in allocation.grants:
        if not grant.resource.endswith("#labour") or grant.granted <= 0:
            continue
        settlement = grant.resource.rsplit("#", 1)[0]
        site_id = kernel.field_site(settlement)
        if not site_id:
            continue
        site = kernel.registry.sites[site_id]
        # qa per person-day, scaled 1000, against the year's climate.
        key = (settlement, grant.actor)
        made[key] = (made.get(key, 0)
                     + grant.granted * site.capacity // 1000 * climate // 100)

    deciders = kernel.deciders()
    for settlement, owner in sorted(made):
        quantity = made[(settlement, owner)]
        if quantity <= 0:
            continue
        # The settlement is the stable parent, and the ordinal is the owner's
        # place among that settlement's own deciders -- not among the world's,
        # or an organization founded in Alashiya would renumber Ma'hadu's lots.
        local = [o for o in deciders
                 if kernel.registry.orgs[o].settlement == settlement]
        lot_id = mint(settlement, kernel.date.absolute, "lot",
                      local.index(owner) if owner in local else 0)
        book = book.create(lot_id, GRAIN, quantity, owner=owner,
                           holder=owner, location=settlement,
                           reason="harvested")
        events.append(("harvested", settlement, quantity))
    return dataclasses.replace(kernel, book=book), events


def _consume(kernel: Kernel) -> tuple[Kernel, list]:
    """Phase 7. People eat, and remember it when they do not."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "consumption")
    cohorts = dict(kernel.registry.cohorts)

    # Only the settlements the kernel actually drives. Ugarit's households are
    # fed by the legacy court (spec 10.12), and eating their grain here as well
    # would model the same mouths twice.
    for settlement in kernel.autonomous():
        for cohort in kernel.cohorts_of(settlement):
            want = cohort.ration()
            got = 0
            for lot in book.at(settlement):
                if lot.good != GRAIN or want - got <= 0:
                    continue
                take = min(want - got, lot.free)
                if take <= 0:
                    continue
                book = book.consume(lot.id, take, "consumed")
                got += take
            if got >= want:
                cohorts[cohort.id] = dataclasses.replace(
                    cohort, hunger=max(0, cohort.hunger - 1))
                continue

            # Short. The memory first, then the people: a cohort that has been
            # hungry for three fortnights starts to lose them.
            hunger = cohort.hunger + 1
            lost = 0
            if hunger >= 3:
                rng = stream(kernel.seed, kernel.date.absolute, "kernel.hunger",
                             cohort.id)
                lost = min(cohort.people,
                           1 + rng.int(max(1, cohort.people // 20)))
            cohorts[cohort.id] = dataclasses.replace(
                cohort, hunger=hunger, people=cohort.people - lost,
                households=min(cohort.households, cohort.people - lost),
                grievance=min(1000, cohort.grievance + 50))
            events.append(("hungry", cohort.id, want - got, lost))

    registry = dataclasses.replace(kernel.registry, cohorts=cohorts)
    return dataclasses.replace(kernel, book=book, registry=registry), events


def _settle(kernel: Kernel, intents: tuple[Intent, ...]) -> tuple[Kernel, list]:
    """Phase 10. Obligations fall due, are rendered, or are not."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "settlement")
    obligations = list(kernel.obligations)

    for i, obligation in enumerate(obligations):
        if obligation.status == "pending" and O.falls_due(
                obligation, kernel.date, dict(kernel.seasons)):
            obligations[i] = O.move(obligation, "due")
            events.append(("due", obligation.id, obligation.owed()))

    offered = {i.subject: i.quantity for i in intents if i.kind == "render"}
    for i, obligation in enumerate(obligations):
        if obligation.status not in ("due", "part_paid"):
            continue
        offer = min(offered.get(obligation.party, 0), obligation.outstanding())
        if offer <= 0:
            continue
        moved = 0
        for lot in book.at(obligation.party):
            if lot.good != obligation.good or moved >= offer:
                continue
            take = min(offer - moved, lot.free)
            if take <= 0:
                continue
            # Offset well clear of the production ordinals above, so a levy and
            # a harvest in the same fortnight cannot mint the same id.
            part = mint(obligation.party, kernel.date.absolute, "lot", 100 + i)
            book = book.give(
                lot.id, take, obligation.beneficiary, "levied",
                authority=obligation.id,
                new_id=None if take == lot.quantity else part)
            moved += take
        if moved > 0:
            obligations[i] = O.render(obligation, moved)
            events.append(("rendered", obligation.id, moved))

    # What is still due when its window has closed has been defaulted on. The
    # engine records that and does nothing about it: what follows is the
    # beneficiary's to decide, and it may not even know yet.
    for i, obligation in enumerate(obligations):
        if obligation.status in ("due", "part_paid") and not O.falls_due(
                obligation, kernel.date, dict(kernel.seasons)):
            obligations[i] = O.move(obligation, "defaulted")
            events.append(("defaulted", obligation.id,
                           obligation.outstanding()))

    # A yearly render is not one debt settled forever. Once the window has
    # passed, the clause stands again for next year -- and the history of what
    # was paid late, or never, travels with it.
    for i, obligation in enumerate(obligations):
        if (not obligation.open
                and obligation.due.kind in ("season", "every")
                and not O.falls_due(obligation, kernel.date,
                                    dict(kernel.seasons))):
            obligations[i] = O.renew(obligation)

    return dataclasses.replace(
        kernel, book=book, obligations=tuple(obligations)), events


# --- the turn -----------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class TurnLog:
    """What a turn actually did. The inspector's whole evidence base (spec 7.5).

    Not stored in the world. The run is deterministic, so a developer asking
    why something happened re-runs the world and collects these -- which keeps
    an ever-growing causal log out of the save file without giving up the
    ability to answer the question.
    """
    turn: int
    intents: tuple[Intent, ...] = ()
    allocation: R.Allocation = dataclasses.field(default_factory=R.Allocation)
    transfers: tuple[W.Transfer, ...] = ()
    events: tuple = ()


def advance(kernel: Kernel) -> tuple[Kernel, list]:
    """One fortnight, phases in order, every settlement crossing them together."""
    kernel, events, _log = advance_logged(kernel)
    return kernel, events


def advance_logged(kernel: Kernel) -> tuple[Kernel, list, TurnLog]:
    """`advance`, and the workings alongside the result."""
    date = kernel.date
    fortnight = date.fortnight % 24 + 1
    kernel = dataclasses.replace(kernel, date=Date(
        year=date.year + (1 if fortnight == 1 else 0), fortnight=fortnight,
        absolute=date.absolute + 1))

    snapshot = open_turn(kernel, kernel.date.absolute)
    events: list = []

    kernel, produced = _observe(kernel, snapshot)
    events.extend(produced)

    intents = _intents(kernel, snapshot)
    allocation = R.allocate(
        intents, _capacity(kernel),
        authority_rank=lambda i: kernel.registry.orgs[i.actor].authority
        if i.actor in kernel.registry.orgs else 0)

    # Through the phase runner rather than around it, so that the order these
    # run in is checked against spec 6.1 on every turn rather than trusted.
    kernel, produced, _trace = T.run(kernel, (
        T.Step("production", "fields", lambda k: _produce(k, allocation)),
        T.Step("consumption", "rations", _consume),
        T.Step("settlement", "obligations", lambda k: _settle(k, intents))))
    events.extend(produced)

    log = TurnLog(
        turn=kernel.date.absolute, intents=intents, allocation=allocation,
        # The book's ledger is drained on the turn's first `at_phase`, so what
        # stands on it now is this turn's movements and only this turn's.
        transfers=kernel.book.transfers,
        events=tuple(events))
    return kernel, events, log


def faults(kernel: Kernel) -> tuple[str, ...]:
    """Phase 17. Everything spec 11.1 asks of this kernel, in one call."""
    exists = kernel.registry.exists
    found = list(check(kernel.registry))
    found.extend(W.faults(kernel.book, exists=exists))
    found.extend(O.faults(kernel.obligations, exists=exists))
    for actor in sorted(kernel.beliefs):
        for claim in kernel.beliefs[actor].claims:
            if claim.holder != actor:
                found.append(f"{claim.id}: held by the wrong actor")
    return tuple(found)
