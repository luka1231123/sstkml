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
eating, and a tribute obligation -- because the kernel's job is the kernel, not
the whole economy.

M13.1 ran that chain flat: every fortnight of the year turned person-days into
grain at one rate, which the module admitted at the time was placeholder. M13.2
replaces it with the real agricultural year in `engine.kernel.farm` -- sowing,
growing, harvest, threshing -- and the difference is not decoration. A flat rate
has no moments, so moving labour costs the same whenever you move it. A year
with a four-fortnight harvest window has a moment where hands are everything,
and a settlement that spent them elsewhere does not get a second chance until
next year.

The other half of M13.2 is `engine.kernel.carry`, and the two halves are the
same argument. The grain year ends with a settlement that is short of ground
rather than short of effort, so no decision it can make at home closes the gap;
the crossing is how grain reaches it from somewhere with a surplus, and it is
the first thing in this world that exists in neither place while it happens.

What that buys is not a supply line, it is a second way to be wrong. A council
now decides what to sell against a winter it has not had yet, and a merchant
commits to a crossing on a price it heard about four fortnights ago, from the
last ship in -- because news travels on the same hulls as the cargo, and a ship
that sinks carries neither.
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
from engine.kernel import carry as C
from engine.kernel import farm as F
from engine.kernel import resolve as R
from engine.kernel import seat_goods as SG
from engine.kernel import turn as T
from engine.kernel.intent import Intent, Snapshot, open_turn

GRAIN = F.GRAIN

# The site functions that are ground a settlement can sow. Two names for one
# thing: the scenario map calls a grain mark a "food" capacity, the retired
# hand-authored world called it an "estate", and the crop does not care.
FIELD = frozenset({"estate", "food"})


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
    # The same series, per region, where content authors one. A world that
    # spans the Nile and the Aegean has no single weather: the flood peaks in
    # the fortnights the Levant is driest, and a drought that emptied both
    # would be a scripted event rather than a climate. A region absent here
    # falls back to `climate` above.
    region_climate: Mapping[EntityId, tuple[int, ...]] = dataclasses.field(
        default_factory=dict)
    # Per good, per fortnight, scaled 1000. Authored in content/goods.toml and
    # carried here rather than looked up, because engine/ does not read files.
    # A good absent from this mapping does not spoil.
    spoilage: Mapping[str, int] = dataclasses.field(default_factory=dict)
    # Which lots at the seat are the court's stores, and which goods it counts
    # (Task 2 C2). A descriptor, not a second stock: the quantities live in the
    # Book like everyone else's, and this says where to find them and what a
    # figure of zero means. Empty until the court's goods have crossed.
    seat_goods: "SG.SeatGoods | None" = None
    # Cargo at sea. The only thing in the world that is in neither of the places
    # it concerns, which is why it is state and the contracts that put it there
    # are not: a bargain is struck and settled in a fortnight, a crossing is not.
    voyages: tuple[C.Voyage, ...] = ()

    # --- reading ------------------------------------------------------------

    def controller(self, settlement: EntityId) -> EntityId:
        """The organization that decides for a settlement, or "" if none does."""
        for org_id in sorted(self.registry.orgs):
            org = self.registry.orgs[org_id]
            if org.settlement == settlement and org.kind in ("council", "palace"):
                return org_id
        return ""

    def tenure_of(self, cohort: Cohort) -> str:
        """How this cohort comes by its food. Its own answer, else its polity's.

        Two levels rather than one because the common case is a whole country
        arranged one way -- one authored word for Egypt covers every cohort in
        it -- and the exception is a single household inside it that is not.
        """
        if cohort.tenure:
            return cohort.tenure
        settlement = self.registry.settlements.get(cohort.settlement)
        polity = self.registry.polities.get(
            settlement.polity) if settlement else None
        return polity.tenure if polity else "pooled"

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

    def field_site(self, settlement: EntityId, actor: EntityId = "") -> EntityId:
        """The estate an actor works at a place, or the place's first estate.

        An actor that holds ground of its own gets that ground. An actor that
        holds none falls back to whatever the settlement's common fields are --
        which is also what a caller asking about the place rather than about
        anyone in particular is asking for.
        """
        estates = [i for i in sorted(self.registry.sites)
                   if self.registry.sites[i].settlement == settlement
                   and self.registry.sites[i].function in FIELD]
        if actor:
            for site_id in estates:
                if self.registry.sites[site_id].holder == actor:
                    return site_id
        for site_id in estates:
            if not self.registry.sites[site_id].holder:
                return site_id
        return estates[0] if estates else ""

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

    def climate_at(self, absolute: int, region: EntityId = "") -> int:
        series = self.region_climate.get(region) or self.climate
        if not series:
            return 100
        return series[absolute % len(series)]

    def region_of(self, settlement: EntityId) -> EntityId:
        found = self.registry.settlements.get(settlement)
        return found.region if found else ""


# --- policy (spec 10.11) ------------------------------------------------------
#
# The signature is the contract: `(actor, belief)`. A policy that took the world
# could read another settlement's granary, and nothing in the output would show
# it had. tests/test_kernel_world.py inspects these signatures.

def _work(actor: EntityId, belief: B.Belief, subject: EntityId,
          task: str, days: int) -> Intent | None:
    """One ask for person-days, or nothing if the actor wants none."""
    if days <= 0:
        return None
    return Intent(
        id=f"{actor}|{task}|{subject}", actor=actor, kind="produce", task=task,
        turn=belief.value(subject, "turn", 0), subject=subject,
        resource=f"{subject}#labour", quantity=days, authority=actor,
        priority=1, basis=tuple(c.id for c in belief.about(subject, "season")))


def _farm(actor: EntityId, belief: B.Belief, home: EntityId,
          feeds_town: bool) -> tuple[Intent, ...]:
    """Do this fortnight's field work, and set next year's seed aside.

    Every quantity comes from `belief.value(...)`, including which season it is.
    That last one matters more than it looks: a policy that asked the calendar
    would be reading the world, and the whole arrangement in spec 10.11 is that
    an actor decides from what it holds. An actor knows the season the same way
    it knows its granary -- by living there -- so the season arrives as a claim.

    `feeds_town` is the difference between a council and a temple, and it is
    about who goes hungry if the seed is set aside. A council is answerable for
    the town's rations and keeps them back first; a temple keeps back nothing,
    because the mouths it answers for are counted in the town's own.

    Only at home. Since the crossing, an actor holds claims about ports across
    the water, and nobody farms a field they have merely had word of.
    """
    intents: list[Intent] = []
    for subject in (home,) if home else ():
        task = F.TASK_FOR.get(belief.value(subject, "season", F.NO_SEASON), "")
        if not task:
            continue

        if task == "sow":
            # Bounded by the seed kept and by ground still unsown. Both are
            # things the actor can see; neither is the engine telling it what
            # it can afford.
            land = max(0, belief.value(subject, "extent", 0)
                       - belief.value(subject, "under_crop", 0))
            days = F.days_for(min(belief.value(subject, "own_seed", 0), land),
                              F.SOW_PER_DAY)
        elif task == "tend":
            days = F.days_for(belief.value(subject, "own_standing", 0),
                              F.TEND_PER_DAY)
        elif task == "reap":
            days = F.days_for(belief.value(subject, "own_standing", 0),
                              F.REAP_PER_DAY)
        else:
            days = F.days_for(belief.value(subject, "own_sheaves", 0),
                              F.THRESH_PER_DAY)

        ask = _work(actor, belief, subject, task, days)
        if ask is not None:
            intents.append(ask)

        if task != "thresh":
            continue

        # Seed for next year, out of grain that could be eaten this one. Capped
        # at the ground it could sow and at the seed already in hand, so that a
        # run of good years does not turn into a granary full of seed nobody
        # will ever put in the earth.
        reserve = (belief.value(subject, "need", 0) * F.SEED_RESERVE_FORTNIGHTS
                   if feeds_town else 0)
        spare = max(0, belief.value(subject, "own_grain", 0) - reserve)
        target = max(0, belief.value(subject, "extent", 0)
                     - belief.value(subject, "own_seed", 0))
        quantity = min(spare, target)
        if quantity > 0:
            intents.append(Intent(
                id=f"{actor}|seed|{subject}", actor=actor, kind="produce",
                task="seed", turn=belief.value(subject, "turn", 0),
                subject=subject, quantity=quantity, authority=actor,
                priority=1,
                basis=tuple(c.id for c in belief.about(subject, "own_grain"))))
    return tuple(intents)


def _render(actor: EntityId, belief: B.Belief,
            home: EntityId) -> tuple[Intent, ...]:
    """Pay what you believe you owe, out of what you believe you can spare."""
    intents: list[Intent] = []
    for subject in (home,) if home else ():
        owed = belief.value(subject, "owes", 0)
        if owed <= 0:
            continue
        # A tribute that would empty the granary is not paid; that is a
        # decision, and it is why obligations default.
        spare = max(0, belief.value(subject, "stores_grain", 0)
                    - belief.value(subject, "need", 0))
        offer = min(owed, spare)
        if offer > 0:
            intents.append(Intent(
                id=f"{actor}|render|{subject}", actor=actor, kind="render",
                turn=belief.value(subject, "turn", 0), subject=subject,
                quantity=offer, authority=actor, priority=2,
                basis=tuple(c.id for c in belief.about(subject, "owes"))))
    return tuple(intents)


def subsistence(actor: EntityId, belief: B.Belief) -> tuple[Intent, ...]:
    """Feed your people, work your fields, pay what you owe, and trade the rest.

    A council does not trade for gain and the two market clauses are not a
    change of character: it sells the surplus of a good year because copper
    keeps and grain does not, and it buys in a bad one because the alternative
    is watching a cargo it could have paid for be carried somewhere else.

    Both bounded entirely by belief, which is where a settlement is undone. What
    it will sell is what it thinks it can spare, decided against a winter it has
    not had yet. What it can buy is what it has left to pay with -- and when the
    purse empties, the grain is still on the quay and it is still not theirs.
    """
    home = C.home(belief)
    return (_farm(actor, belief, home, feeds_town=True)
            + _render(actor, belief, home)
            + C.sell_surplus(actor, belief, home)
            + C.buy_shortfall(actor, belief, home))


def cult(actor: EntityId, belief: B.Belief) -> tuple[Intent, ...]:
    """Work the god's land. Render nothing: the temple owes the crown nothing.

    A second claimant on the same person-days is the point of this policy. The
    god's estate and the town's fields draw on one body of people and one
    extent of ground, and the allocator -- not a hand-tuned split -- decides who
    goes short. The temple wins those contests on authority, which is the
    historical claim being modelled and is not the same as it being right.
    """
    return _farm(actor, belief, C.home(belief), feeds_town=False)


POLICIES = {"subsistence": subsistence, "cult": cult, "trade": C.trade}


# --- the phases ---------------------------------------------------------------

def _estate_of(world: Kernel, settlement: EntityId, actor: EntityId) -> EntityId:
    """The ground this actor farms here, or "" if it farms none.

    `field_site` falls back to the settlement's common fields for an actor that
    holds no estate, which is right for a caller asking about the place. It is
    wrong for an actor: a merchant house holds no ground, and letting it observe
    the council's extent would put a number in its belief that it has no
    business having and that nothing entitles it to act on.
    """
    site_id = world.field_site(settlement, actor)
    site = world.registry.sites.get(site_id)
    if site is None or (site.holder and site.holder != actor):
        return ""
    return site_id


def _observe(kernel: Kernel, snapshot: Snapshot) -> tuple[Kernel, list]:
    """Phase 3. Each actor counts what is in front of it, and nothing else.

    "In front of it" now has two parts, because an actor is not always in one
    place. At home it counts everything a fortnight in a small port tells you.
    Away -- wherever it has goods of its own standing on a quay -- it counts its
    own property and the price of the day, because it has a factor there doing
    exactly that.

    What it never gets from here is the state of a place it is not: the far
    port's stores, its shortfall, what it would pay. Those arrive on a ship, in
    `carry._tell`, dated to the day the ship left.
    """
    world: Kernel = snapshot.world
    beliefs = dict(kernel.beliefs)
    turn = snapshot.turn
    for actor in world.deciders():
        settlement = world.registry.orgs[actor].settlement
        need = sum(c.ration() for c in world.cohorts_of(settlement))
        owed = sum(o.outstanding() for o in world.obligations
                   if o.party == settlement and o.status in ("due", "part_paid"))
        site_id = _estate_of(world, settlement, actor)
        site = world.registry.sites.get(site_id)
        readings = {
            "stores_grain": world.stores(settlement),
            "people": world.people(settlement),
            "labour": world.labour(settlement),
            # The ground and how much of it is sown: visible from the field
            # edge, and the same figure for everyone who farms this estate.
            "extent": site.extent if site else 0,
            "under_crop": F.under_crop(world, site_id) if site_id else 0,
            # Its own property, counted. Not the temple's, not the crown's.
            "own_grain": F.held(world.book, actor, F.GRAIN, settlement),
            "own_seed": F.held(world.book, actor, F.SEED, settlement),
            "own_standing": F.held(world.book, actor, F.STANDING, site_id),
            "own_sheaves": F.held(world.book, actor, F.SHEAVES, settlement),
            "own_copper": F.held(world.book, actor, C.COPPER, settlement),
            "season": F.code_for(world.seasons, world.date.fortnight),
            # Which place this is: the actor's own claim about where it stands,
            # so that a policy holding claims about three ports can still tell
            # which one it lives in without being handed the registry.
            "home": 1,
            **C.readings(world, settlement),
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
                    basis=(f"c|{actor}|{turn}|{settlement}|people",)),
            B.Claim(id=f"{actor}|{turn}|owes", holder=actor, subject=settlement,
                    attribute="owes", value=owed, source="observed",
                    observed_turn=turn, received_turn=turn),
            B.Claim(id=f"{actor}|{turn}|turn", holder=actor, subject=settlement,
                    attribute="turn", value=turn, source="observed",
                    observed_turn=turn, received_turn=turn))
        belief = _abroad(world, belief, actor, settlement, turn)
        beliefs[actor] = belief
    return dataclasses.replace(kernel, beliefs=beliefs), []


def _abroad(world: Kernel, belief: B.Belief, actor: EntityId,
            home: EntityId, turn: int) -> B.Belief:
    """What an actor knows about the places it is not, and how it came to.

    Two ways, and neither of them is a lookup.

    Where it has goods, it has someone with them, and that person counts the
    goods and hears the price. Cargo still at sea is not here: its location is
    the route, not a settlement, and nobody on a ship is taking the market.

    Where it has none, it has custom. A merchant house that has never had word
    from a port it nonetheless knows the way to assumes grain fetches the
    ordinary price there -- and sails on that assumption the first time, which
    is how the trade starts and is a fair description of how it did. The claim
    is dated to before the world began, so the first real report supersedes it
    and it never competes with news again.
    """
    places = {lot.location for lot in world.book.owned_by(actor)
              if lot.location in world.registry.settlements
              and lot.location != home}
    for place in sorted(places):
        belief = belief.add(*OB.as_claims(OB.observe_local(actor, place, turn, {
            "own_grain": F.held(world.book, actor, F.GRAIN, place),
            "own_copper": F.held(world.book, actor, C.COPPER, place),
            "price_grain": C.readings(world, place)["price_grain"],
        }), turn))

    for place in C.reachable(world, home):
        if belief.about(place, "price_grain"):
            continue
        belief = belief.add(B.Claim(
            id=f"{actor}|custom|{place}|price_grain", holder=actor,
            subject=place, attribute="price_grain", value=C.BASE_PRICE,
            source="assumed", observed_turn=0, received_turn=turn,
            confidence=100))
    return belief


def _intents(kernel: Kernel, snapshot: Snapshot) -> tuple[Intent, ...]:
    """Phase 4. Every council decides from its own belief, from one snapshot."""
    world: Kernel = snapshot.world
    produced: list[Intent] = []
    for actor in world.deciders():
        policy = POLICIES[world.registry.orgs[actor].policy]
        produced.extend(policy(actor, kernel.beliefs[actor]))
    return tuple(sorted(produced, key=lambda i: i.id))


def _capacity(kernel: Kernel) -> dict[EntityId, int]:
    """The exclusive pools, this turn only: hands in each place, hulls on each sea.

    Both settled by the one allocator, in the one pass, by the one rule -- which
    is the whole reason spec 6.1 puts allocation in a phase of its own. A cargo
    outbid for hold and a council outbid for the harvest's hands went short the
    same way and are visible in the same record.
    """
    pools = {f"{s}#labour": kernel.labour(s)
             for s in sorted(kernel.registry.settlements)}
    pools.update(C.capacity(kernel))
    return pools


def _farm_steps(intents: tuple[Intent, ...],
                allocation: R.Allocation) -> tuple[T.Step, ...]:
    """Phase 6, in calendar order. Only one of the four bites in any fortnight.

    They are all `production` and could have been one function. They are four
    because the year is four things, and because a step that does nothing for
    twenty fortnights out of twenty-four should be visibly doing nothing rather
    than hiding inside a branch.
    """
    return (
        T.Step("production", "sowing", lambda k: F.sow(k, intents, allocation)),
        T.Step("production", "growing", lambda k: F.tend(k, intents, allocation)),
        T.Step("production", "harvest", lambda k: F.reap(k, intents, allocation)),
        T.Step("production", "threshing",
               lambda k: F.thresh(k, intents, allocation)),
        T.Step("production", "seed corn", lambda k: F.store_seed(k, intents)),
        T.Step("production", "the share", F.share_out),
        T.Step("production", "the stack", F.keep),
    )


def _food_owners(kernel: Kernel, cohort: Cohort) -> set[EntityId]:
    """Whose grain this cohort may eat. The whole of what tenure decides.

    A settlement is not one granary with a queue at it. Who may open which door
    is the arrangement a society is, and these four are the ones the Late Bronze
    Age actually ran (`entity.TENURES`).
    """
    settlement = cohort.settlement
    controller = kernel.controller(settlement)
    tenure = kernel.tenure_of(cohort)
    if tenure == "subsistence":
        # Its own harvest and nothing else. The palace store down the road is
        # not theirs, and that is the point rather than an omission.
        return {cohort.id}
    if tenure == "redistributive":
        # The state granary, and only it. They own no food to fall back on, so
        # a palace that cannot deliver is a famine with somebody to blame.
        return {controller}
    if tenure == "prebendal":
        # Fed by the house they serve, wherever they happen to live.
        return {cohort.origin or controller}
    return {settlement, controller}


def _local_food(kernel: Kernel, book: W.Book,
                cohort: Cohort) -> tuple[W.GoodsLot, ...]:
    """What a body of people may eat, in the order they will eat it.

    Grain first, then the seed corn. Reaching the second is a real decision with
    a real price -- it is next year's harvest going into this fortnight's
    bread -- and households have always made it rather than starve.

    Ownership bounds it, and bounds it tightly: `_food_owners` says whose, and
    nothing else standing in the same town is reachable.

    Two exclusions hold under every tenure, for the same reason. Grain in
    Ma'hadu that belongs to the crown because it was rendered as tribute is not
    Ma'hadu's to eat; taking it would be a seizure, which is a political act
    with consequences. And the temple's granary is not the town's either. A
    temple that feeds the hungry in a bad year is doing something -- relief,
    patronage, a claim on those it fed -- and spec 6.3 has it as a choice a
    household makes and an institution grants. Letting it happen silently every
    fortnight would delete the choice and, worse, would hide the case this world
    most wants to be able to show: a full temple store beside a hungry town.

    So the temple's grain accumulates here and nothing spends it. That is not
    an oversight, it is an unbuilt mechanism sitting in plain view, and M13.5's
    petitions are what build it. Subsistence tenure makes the same case out of
    the palace rather than the temple, and wants the same mechanism.
    """
    mine = _food_owners(kernel, cohort)
    return tuple(lot for good in (GRAIN, F.SEED)
                 for lot in _within_reach(kernel, book, cohort)
                 if lot.good == good and lot.owner in mine)


def _within_reach(kernel: Kernel, book: W.Book,
                  cohort: Cohort) -> tuple[W.GoodsLot, ...]:
    """Where the grain a body of people may eat is allowed to be standing.

    Where they are, ordinarily: a household eats out of its own house, and a
    town's people out of the town.

    A body fed by a house rather than by a place also reaches that house's own
    store, wherever it stands -- the garrison at Ma'hadu is the crown's, and the
    crown's granary is at the seat. The carriage is not modelled and the
    simplification is deliberate rather than overlooked: this is exactly what
    the court's ration roll did before the kernel took the payroll over, and
    inventing a supply line at the same time as moving the authority would make
    it impossible to say which of the two changed the answer.
    """
    lots = list(book.at(cohort.settlement))
    if kernel.tenure_of(cohort) not in ("redistributive", "prebendal"):
        return tuple(lots)
    seen = {lot.id for lot in lots}
    for owner in sorted(_food_owners(kernel, cohort)):
        org = kernel.registry.orgs.get(owner)
        if org is None or not org.settlement or org.settlement == cohort.settlement:
            continue
        lots.extend(lot for lot in book.at(org.settlement)
                    if lot.id not in seen)
    return tuple(lots)


def _mouths(kernel: Kernel) -> tuple[Cohort, ...]:
    """Whose meal this phase is answerable for, in a stable order (spec 2.6).

    Two kinds. The settlements the kernel drives, entire; and, at a settlement
    it does not drive, the bodies of people that eat from a store the Book
    already holds -- which is what redistributive tenure means and why it is the
    line the seat's payroll crossed on.

    The rest of the seat is left out, and the reason is land rather than people.
    Its households are `pooled`: they would eat the palace's grain, because the
    palace owns every lot standing there and nothing they work is theirs. They
    get their own holding when the seat's fields become the kernel's (C4), and
    feeding them out of the crown's store until then would be a famine invented
    by the migration.
    """
    seen: set[EntityId] = set()
    out: list[Cohort] = []
    for settlement in kernel.autonomous():
        for cohort in kernel.cohorts_of(settlement):
            seen.add(cohort.id)
            out.append(cohort)
    return tuple(out)


def kept_mouths(kernel: Kernel) -> tuple[Cohort, ...]:
    """The bodies of people some house owes a ration, at a place it does not run.

    The crown's payroll, and nothing else in this world yet. They are not in
    `_mouths` because they do not eat on the kernel's clock; `feed` says why.

    Served in the order the store's holder set, and the store runs out where it
    runs out. Nobody ranked means everybody equal, which is the id order.
    """
    driven = {c.id for s in kernel.autonomous() for c in kernel.cohorts_of(s)}
    fed: list[Cohort] = []
    for cohort_id in sorted(kernel.registry.cohorts):
        cohort = kernel.registry.cohorts[cohort_id]
        if cohort.id in driven:
            continue
        if kernel.tenure_of(cohort) not in ("redistributive", "prebendal"):
            continue
        if not (kernel.controller(cohort.settlement) or cohort.origin):
            continue
        fed.append(cohort)
    fed.sort(key=lambda c: (-c.precedence, c.id))
    return tuple(fed)


def _consume(kernel: Kernel) -> tuple[Kernel, list]:
    """Phase 7. People eat, and remember it when they do not."""
    return feed(kernel, _mouths(kernel))


def feed(kernel: Kernel, mouths: tuple[Cohort, ...],
         *, starve: bool = True) -> tuple[Kernel, list]:
    """The meal itself, for a named body of people.

    Taken apart from the phase because the crown's payroll eats on the
    court's clock, not the kernel's: `engine/tick.py` spends the seat's
    granary at A8, after spoilage and after the rites take their cut, and a
    ration paid at A1 instead would be the same grain leaving in a different
    order. The order is the thing being preserved (spec 6.1), so the seat's
    cohorts are left out of the phase above and `engine/seat.py::feed` calls
    this where the ration roll used to run.

    `starve` is whether going short costs people here. It is off for the crown's
    payroll, and not because they are spared: spec 6.3's band table is the
    authored answer for what a ration debt does to the body that is owed it, and
    it says desertion, loyalty and a failing workshop together. Applying that
    table and this rule to the same hungry fortnight would take the same people
    away twice. `engine/seat.py::mirror` runs the band.
    """
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "consumption")
    cohorts = dict(kernel.registry.cohorts)

    for cohort in mouths:
        want = cohort.ration()
        # What is owed and what will be handed over are two figures, and only
        # under redistributive tenure can they differ. Shortfall is measured
        # against the first: a body cut to half rations is owed the other half
        # and goes hungry for it.
        # Not capped at `want`: a store that hands over more than a fortnight's
        # ration is paying down what it already owed, and forbidding that would
        # make a debt permanent the moment it was incurred.
        cap = want if cohort.allowance < 0 else max(0, cohort.allowance)
        got = 0
        ate_seed = 0
        for lot in _local_food(kernel, book, cohort):
            if cap - got <= 0:
                break
            current = book.lots.get(lot.id)
            if current is None:
                continue
            take = min(cap - got, current.free)
            if take <= 0:
                continue
            book = book.consume(current.id, take, "consumed")
            got += take
            if current.good == F.SEED:
                ate_seed += take
        if ate_seed:
            events.append(("ate_the_seed", cohort.id, ate_seed))
        if got >= want:
            cohorts[cohort.id] = dataclasses.replace(
                cohort, hunger=max(0, cohort.hunger - 1),
                shortfall=max(0, cohort.shortfall + want - got))
            continue

        # Short. The memory first, then the people: a cohort that has been
        # hungry for three fortnights starts to lose them.
        hunger = cohort.hunger + 1
        lost = 0
        if starve and hunger >= 3:
            rng = stream(kernel.seed, kernel.date.absolute, "kernel.hunger",
                         cohort.id)
            lost = min(cohort.people,
                       1 + rng.int(max(1, cohort.people // 20)))
        cohorts[cohort.id] = dataclasses.replace(
            cohort, hunger=hunger, people=cohort.people - lost,
            households=min(cohort.households, cohort.people - lost),
            shortfall=max(0, cohort.shortfall + want - got),
            grievance=cohort.grievance if not starve
            else min(1000, cohort.grievance + 50))
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
    # Ordinal counters for the parts split off by a levy, one per place. Kept
    # per party because the id's parent is the party: two settlements rendering
    # on the same turn cannot collide, and two lots split for the same
    # obligation must not. A single ordinal per obligation was the earlier form
    # and it minted the same id twice whenever a render crossed two lots.
    parts: dict[EntityId, int] = {}
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
            # A party cannot render what the beneficiary already owns. The
            # crown's own grain sits in Ma'hadu after every tribute -- it has
            # been paid but nothing has carried it away -- and levying it again
            # would be both a double payment and, since ownership would not
            # change, an outright error.
            if lot.owner == obligation.beneficiary:
                continue
            take = min(offer - moved, lot.free)
            if take <= 0:
                continue
            ordinal = parts.get(obligation.party, 0)
            parts[obligation.party] = ordinal + 1
            # Block 2000 and up: clear of the farm steps' ordinals, which run
            # from 200 to just past 1000 at the same parent on the same turn.
            part = mint(obligation.party, kernel.date.absolute, "lot",
                        2000 + ordinal)
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
    # The turn's bargains. Here rather than in the world because every one of
    # them is agreed, delivered, and paid inside the phase that matched it; when
    # M13.3 lets a contract promise delivery next spring, it becomes state.
    contracts: tuple[C.Contract, ...] = ()


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

    events: list = []

    # Phases 2 to 5 run outside the phase runner, because between them they
    # build the two things every step inside it consumes: the snapshot each
    # actor decided from, and the allocation. The order is still 6.1's, and
    # arrivals coming first is what it is for -- a ship that lands this morning
    # is news this fortnight's decisions are made on, not next fortnight's.
    kernel, produced = C.arrivals(kernel)
    events.extend(produced)

    snapshot = open_turn(kernel, kernel.date.absolute)
    kernel, produced = _observe(kernel, snapshot)
    events.extend(produced)

    intents = _intents(kernel, snapshot)
    allocation = R.allocate(
        intents, _capacity(kernel),
        authority_rank=lambda i: kernel.registry.orgs[i.actor].authority
        if i.actor in kernel.registry.orgs else 0)

    struck: list[C.Contract] = []

    def _market(state):
        state, produced, contracts = C.market(state, intents)
        struck.extend(contracts)
        return state, produced

    # Through the phase runner rather than around it, so that the order these
    # run in is checked against spec 6.1 on every turn rather than trusted.
    kernel, produced, _trace = T.run(kernel, _farm_steps(intents, allocation) + (
        T.Step("consumption", "rations", _consume),
        T.Step("market", "bargains", _market),
        T.Step("movement", "sailings",
               lambda k: C.movement(k, intents, allocation)),
        T.Step("settlement", "obligations", lambda k: _settle(k, intents)),
        T.Step("settlement", "the stores", C.consolidate)))
    events.extend(produced)

    log = TurnLog(
        turn=kernel.date.absolute, intents=intents, allocation=allocation,
        # The book's ledger is drained on the turn's first `at_phase`, so what
        # stands on it now is this turn's movements and only this turn's.
        transfers=kernel.book.transfers,
        events=tuple(events), contracts=tuple(struck))
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
    for voyage in kernel.voyages:
        if voyage.route not in kernel.registry.routes:
            found.append(f"{voyage.id}: sails a route that does not exist")
        for endpoint in (voyage.origin, voyage.destination):
            if not exists(endpoint):
                found.append(f"{voyage.id}: puts in at {endpoint!r}, which does not")
        if voyage.arrives <= voyage.departed:
            found.append(f"{voyage.id}: arrives before it left")
        # Cargo that is not on the route it is being carried along is cargo two
        # systems disagree about the position of.
        for lot_id in voyage.cargo:
            lot = kernel.book.lots.get(lot_id)
            if lot is not None and lot.location != voyage.route:
                found.append(
                    f"{voyage.id}: carries {lot_id}, which is at {lot.location!r}")
    return tuple(found)
