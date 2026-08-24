"""A world of settlements that run themselves (spec 6.1, M13.1 exit gate)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine import believe as B
from engine import obligation as O
from engine import observe as OB
from engine import ownership as W
from engine.core import Date, stream
from engine.entity import HUNGER_MAX, Cohort, EntityId, Person, Polity, Registry, check, mint
from engine.kernel import arms as AR
from engine.kernel import carry as C
from engine.kernel import farm as F
from engine.kernel import resolve as R
from engine.kernel import seat_goods as SG
from engine.kernel import turn as T
from engine.kernel.intent import Intent, Snapshot, open_turn

GRAIN = F.GRAIN

# The site functions that are ground a settlement can sow.
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
    # The same series, per region, where content authors one.
    region_climate: Mapping[EntityId, tuple[int, ...]] = dataclasses.field(
        default_factory=dict)
    # Per good, per fortnight, scaled 1000.
    spoilage: Mapping[str, int] = dataclasses.field(default_factory=dict)
    # What the crown takes from its own villages' harvest, per 1000. The
    # court owns the figure; `engine.tick` pushes it in each turn.
    land_due_per_1000: int = 1000 - F.HOUSEHOLD_SHARE_PER_1000
    # Calm-state analysis: the authored downturn is frozen and every reading is
    # an ordinary year, so the economy can be measured without the collapse the
    # campaign is about. `engine.tick` pushes it in from `World.baseline`.
    baseline: bool = False
    # Which lots at the seat are the court's stores, and which goods it counts (Task 2 C2).
    seat_goods: "SG.SeatGoods | None" = None
    # Cargo at sea.
    voyages: tuple[C.Voyage, ...] = ()
    trade_routes: Mapping[EntityId, int] = dataclasses.field(default_factory=dict)
    # Court infrastructure is outside the autonomous kernel, so the court
    # adapter derives these at the opening of each turn. They are bonuses over
    # authored ground and route capacity, keyed by the thing they improve.
    site_extent_bonus: Mapping[EntityId, int] = dataclasses.field(
        default_factory=dict)
    route_capacity_bonus: Mapping[EntityId, int] = dataclasses.field(
        default_factory=dict)

    # --- reading ------------------------------------------------------------

    def controller(self, settlement: EntityId) -> EntityId:
        """The organization that decides for a settlement, or "" if none does."""
        for org_id in sorted(self.registry.orgs):
            org = self.registry.orgs[org_id]
            if org.settlement == settlement and org.kind in ("council", "palace"):
                return org_id
        return ""

    def owner(self, settlement: EntityId) -> Polity | None:
        held = self.registry.settlements.get(settlement)
        return self.registry.polities.get(held.owner) if held else None

    def king(self, settlement: EntityId) -> Person | None:
        polity = self.owner(settlement)
        person = self.registry.persons.get(polity.ruler) if polity else None
        return person if person and person.alive else None

    def tenure_of(self, cohort: Cohort) -> str:
        """How this cohort comes by its food."""
        if cohort.tenure:
            return cohort.tenure
        settlement = self.registry.settlements.get(cohort.settlement)
        polity = self.registry.polities.get(
            settlement.owner) if settlement else None
        return polity.tenure if polity else "pooled"

    def cohorts_of(self, settlement: EntityId) -> tuple[Cohort, ...]:
        return tuple(self.registry.cohorts[c] for c in sorted(self.registry.cohorts)
                     if self.registry.cohorts[c].settlement == settlement)

    def stores(self, settlement: EntityId, good: str = GRAIN) -> int:
        return sum(lot.quantity for lot in self.book.at(settlement)
                   if lot.good == good)

    def people(self, settlement: EntityId) -> int:
        return sum(c.people for c in self.cohorts_of(settlement)
                   if not c.in_transit)

    def commercial_routes(self) -> tuple[EntityId, ...]:
        return tuple(sorted(route for route, strength in self.trade_routes.items()
                            if strength >= 3))

    def labour(self, settlement: EntityId) -> int:
        return sum(c.labour() for c in self.cohorts_of(settlement)
                   if not c.in_transit
                   and (not c.roll_id or c.kind == "field_labour"
                        or c.reaping))

    def field_site(self, settlement: EntityId, actor: EntityId = "") -> EntityId:
        """The estate an actor works at a place, or the place's first estate."""
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
        """Every organization that decides, in a stable order."""
        return tuple(
            org_id for org_id in sorted(self.registry.orgs)
            if self.registry.orgs[org_id].policy in POLICIES
            and not self.registry.settlements[
                self.registry.orgs[org_id].settlement].fallen
            and self.registry.settlements[
                self.registry.orgs[org_id].settlement].autonomous)

    def farmers(self) -> tuple[EntityId, ...]:
        """Every organization that works ground, in a stable order."""
        driven = set(self.deciders())
        out = list(driven)
        for sid in sorted(self.registry.settlements):
            if self.registry.settlements[sid].fallen:
                continue
            if sid in {self.registry.orgs[o].settlement for o in driven}:
                continue
            holder = self.controller(sid)
            if holder and self.field_site(sid, holder):
                out.append(holder)
        return tuple(sorted(out))

    def autonomous(self) -> tuple[EntityId, ...]:
        """The settlements that decide for themselves, in a stable order."""
        return tuple(
            s for s in sorted(self.registry.settlements)
            if not self.registry.settlements[s].fallen
            and self.registry.settlements[s].autonomous and self.controller(s))

    def climate_at(self, absolute: int, region: EntityId = "") -> int:
        if self.baseline:
            return 100
        series = self.region_climate.get(region) or self.climate
        if not series:
            return 100
        return series[absolute % len(series)]

    def region_of(self, settlement: EntityId) -> EntityId:
        found = self.registry.settlements.get(settlement)
        return found.region if found else ""


# --- policy (spec 10.11) ------------------------------------------------------

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
    """Do this fortnight's field work, and set next year's seed aside."""
    intents: list[Intent] = []
    for subject in (home,) if home else ():
        task = F.TASK_FOR.get(belief.value(subject, "season", F.NO_SEASON), "")
        if not task:
            continue

        if task == "sow":
            # Bounded by the seed kept and by ground still unsown.
            land = max(0, belief.value(subject, "extent", 0)
                       - belief.value(subject, "under_crop", 0))
            days = F.days_for(min(belief.value(subject, "own_seed", 0), land),
                              F.SOW_PER_DAY)
        elif task == "tend":
            days = F.days_for(belief.value(subject, "own_standing", 0),
                              F.TEND_PER_DAY)
        else:
            days = F.days_for(belief.value(subject, "own_standing", 0),
                              F.REAP_PER_DAY)

        ask = _work(actor, belief, subject, task, days)
        if ask is not None:
            intents.append(ask)

        # Seed comes off the harvest, which is the only moment there is grain
        # to take it from.
        if task != "reap":
            continue

        # Seed for next year, out of grain that could be eaten this one.
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
        # A tribute that would empty the granary is not paid; that is a decision, and it is why.
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
    """Feed your people, work your fields, pay what you owe, and trade the rest."""
    home = C.home(belief)
    return (_farm(actor, belief, home, feeds_town=True)
            + _render(actor, belief, home)
            + C.sell_surplus(actor, belief, home)
            + C.buy_shortfall(actor, belief, home))


def cult(actor: EntityId, belief: B.Belief) -> tuple[Intent, ...]:
    """Work the god's land."""
    return _farm(actor, belief, C.home(belief), feeds_town=False)


POLICIES = {"subsistence": subsistence, "cult": cult, "trade": C.trade}


# --- the phases ---------------------------------------------------------------

def _estate_of(world: Kernel, settlement: EntityId, actor: EntityId) -> EntityId:
    """The ground this actor farms here, or "" if it farms none."""
    site_id = world.field_site(settlement, actor)
    site = world.registry.sites.get(site_id)
    if site is None or (site.holder and site.holder != actor):
        return ""
    return site_id


def _observe(kernel: Kernel, snapshot: Snapshot) -> tuple[Kernel, list]:
    """Phase 3."""
    world: Kernel = snapshot.world
    beliefs = dict(kernel.beliefs)
    turn = snapshot.turn
    for actor in world.farmers():
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
            # The ground and how much of it is sown: visible from the field edge, and the same.
            "extent": F.extent(world, site_id) if site else 0,
            "under_crop": F.under_crop(world, site_id) if site_id else 0,
            # Its own property, counted.
            "own_grain": F.held(world.book, actor, F.GRAIN, settlement),
            "own_seed": F.held(world.book, actor, F.SEED, settlement),
            "own_standing": F.held(world.book, actor, F.STANDING, site_id),
            "own_copper": F.held(world.book, actor, C.COPPER, settlement),
            "season": F.code_for(world.seasons, world.date.fortnight),
            # How long the grain in the yard feeds the roll.
            "cover": world.stores(settlement, F.GRAIN) // max(1, need),
            # Which place this is: the actor's own claim about where it stands, so that a policy.
            "home": 1,
            **C.readings(world, settlement),
        }
        belief = beliefs.get(actor, B.Belief(holder=actor))
        belief = OB.project(
            belief, OB.observe_local(actor, settlement, turn, readings), turn)
        # Two things the council works out rather than sees, kept as its own claims.
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
    """What an actor knows about the places it is not, and how it came to."""
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
    driven = set(world.deciders())
    produced: list[Intent] = []
    for actor in world.farmers():
        belief = kernel.beliefs[actor]
        if actor in driven:
            policy = POLICIES[world.registry.orgs[actor].policy]
            produced.extend(policy(actor, belief))
        else:
            # Field work only.
            produced.extend(_farm(actor, belief, C.home(belief),
                                  feeds_town=False))
    return tuple(sorted(produced, key=lambda i: i.id))


def _capacity(kernel: Kernel) -> dict[EntityId, int]:
    """The exclusive pools, this turn only: hands in each place, hulls on each sea."""
    pools = {f"{s}#labour": kernel.labour(s)
             for s in sorted(kernel.registry.settlements)}
    pools.update(C.capacity(kernel))
    return pools


def _food_owners(kernel: Kernel, cohort: Cohort) -> set[EntityId]:
    """Whose grain this cohort may eat."""
    settlement = cohort.settlement
    controller = kernel.controller(settlement)
    tenure = kernel.tenure_of(cohort)
    if tenure == "subsistence":
        # Its own harvest and nothing else.
        return {cohort.id}
    if tenure == "redistributive":
        # The state granary, and only it.
        return {controller}
    if tenure == "prebendal":
        # Fed by the house they serve, wherever they happen to live.
        return {cohort.origin or controller}
    return {settlement, controller}


def _local_food(kernel: Kernel, book: W.Book,
                cohort: Cohort) -> tuple[W.GoodsLot, ...]:
    """What a body of people may eat, in the order they will eat it."""
    mine = _food_owners(kernel, cohort)
    return tuple(lot for good in _foods(kernel, cohort)
                 for lot in _within_reach(kernel, book, cohort)
                 if lot.good == good and lot.owner in mine)


def _foods(kernel: Kernel, cohort: Cohort) -> tuple[str, ...]:
    """What a body of people may eat: grain, and never the seed corn.

    Seed is capital for next year's field. It is set aside by `store_seed` and
    returned to the ground at sowing; eating it converts a short year into a
    lost one, so it is protected here rather than left to the mouth.
    """
    return (GRAIN,)


def _within_reach(kernel: Kernel, book: W.Book,
                  cohort: Cohort) -> tuple[W.GoodsLot, ...]:
    """Where the grain a body of people may eat is allowed to be standing."""
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


def _reaped(captured: dict) -> dict[EntityId, int]:
    """What each harvest brought in this turn, less the seed it then set aside."""
    made: dict[EntityId, int] = {}
    for event in captured.get("production", ()):
        if not isinstance(event, tuple) or len(event) < 3:
            continue
        if event[0] == "reaped":
            made[event[1]] = made.get(event[1], 0) + event[3]
        elif event[0] == "set_aside":
            made[event[1]] = made.get(event[1], 0) - event[2]
    return made


def _mouths(kernel: Kernel) -> tuple[Cohort, ...]:
    """Whose meal this phase is answerable for, in a stable order (spec 2.6).

    Every settlement, the seat included. The seat's villages hold their own
    crop and eat it; the crown's roll is redistributive and is served
    separately by `engine.seat.feed` out of the store.
    """
    out: list[Cohort] = []
    for settlement in kernel.autonomous():
        for cohort in kernel.cohorts_of(settlement):
            if not cohort.in_transit:
                out.append(cohort)
    for settlement in sorted(kernel.registry.settlements):
        place = kernel.registry.settlements[settlement]
        if place.fallen or place.autonomous:
            continue
        for cohort in kernel.cohorts_of(settlement):
            if cohort.in_transit:
                continue
            if kernel.tenure_of(cohort) in ("redistributive", "prebendal"):
                continue
            out.append(cohort)
    return tuple(out)


def kept_mouths(kernel: Kernel) -> tuple[Cohort, ...]:
    """The bodies of people some house owes a ration, at a place it does not run."""
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


# What a fed body of people adds to itself in a year, per thousand. Low on
# purpose: a bronze-age roll grows in generations, not in reigns, and a campaign
# is twenty years. It is the loop that matters, not the speed of it -- surplus
# grain becomes mouths, mouths eat the surplus, and the two find each other.
BIRTH_PER_1000 = 1
BIRTH_FORTNIGHT = 16


def _breed(kernel: Kernel) -> tuple[Kernel, list]:
    """Phase 11. The roll grows where the year fed it, once a year.

    Hunger is the whole of the check. A body of people that went short at any
    point since the last count does not grow this year: the loop closes on food
    rather than on any authored ceiling, so a settlement settles at the number
    its ground will carry and famine is what pushes it back down.
    """
    if kernel.date.fortnight != BIRTH_FORTNIGHT:
        return kernel, []
    cohorts = dict(kernel.registry.cohorts)
    events: list = []
    for cid in sorted(cohorts):
        cohort = cohorts[cid]
        if cohort.hunger or cohort.people <= 0 or cohort.in_transit:
            continue
        born = cohort.people * BIRTH_PER_1000 // 1000
        if born <= 0:
            continue
        cohorts[cid] = dataclasses.replace(
            cohort, people=cohort.people + born,
            households=cohort.households + born * cohort.households
            // max(1, cohort.people))
        events.append(("born", cid, born))
    if not events:
        return kernel, []
    registry = dataclasses.replace(kernel.registry, cohorts=cohorts)
    return dataclasses.replace(kernel, registry=registry), events


def _consume(kernel: Kernel) -> tuple[Kernel, list]:
    """Phase 7. People eat, and remember it when they do not."""
    return feed(kernel, _mouths(kernel))


def feed(kernel: Kernel, mouths: tuple[Cohort, ...],
         *, starve: bool = True) -> tuple[Kernel, list]:
    """The meal itself, for a named body of people."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "consumption")
    cohorts = dict(kernel.registry.cohorts)

    for cohort in mouths:
        want = cohort.ration()
        # A recovered granary clears at most one old ration alongside this
        # fortnight's meal. Otherwise one missed payment is permanent unless
        # the player discovers a hidden double-allocation trick.
        claim = want + min(cohort.shortfall, want)
        # An explicit allowance remains an explicit ceiling; the ordinary roll
        # repays arrears automatically when grain exists.
        cap = (claim if cohort.allowance < 0
               else min(claim, max(0, cohort.allowance)))
        got = 0
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
        if got >= want:
            cohorts[cohort.id] = dataclasses.replace(
                cohort, hunger=max(0, cohort.hunger - 1),
                shortfall=max(0, cohort.shortfall + want - got))
            continue

        # Short.
        hunger = min(HUNGER_MAX, cohort.hunger + 1)
        lost = 0
        if starve and hunger >= 3:
            rng = stream(kernel.seed, kernel.date.absolute, "kernel.hunger",
                         cohort.id)
            lost = min(cohort.people,
                       1 + rng.int(max(1, cohort.people // 320)))
        cohorts[cohort.id] = dataclasses.replace(
            cohort, hunger=hunger, people=cohort.people - lost,
            households=min(cohort.households, cohort.people - lost),
            shortfall=max(0, cohort.shortfall + want - got),
            grievance=cohort.grievance if not starve
            else min(1000, cohort.grievance + 4))
        events.append(("hungry", cohort.id, want - got, lost))

    registry = dataclasses.replace(kernel.registry, cohorts=cohorts)
    return dataclasses.replace(kernel, book=book, registry=registry), events


def _collectors(kernel: Kernel) -> dict[EntityId, tuple[EntityId, EntityId]]:
    """Who actually takes a tribute owed to a polity, and where they take it."""
    found: dict[EntityId, tuple[EntityId, EntityId]] = {}
    for pid in sorted(kernel.registry.polities):
        seat = kernel.registry.polities[pid].seat
        holder = kernel.controller(seat) if seat else ""
        if holder:
            found[pid] = (holder, seat)
    return found


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
    collector = _collectors(kernel)
    # Ordinal counters for the parts split off by a levy, one per place.
    parts: dict[EntityId, int] = {}
    for i, obligation in enumerate(obligations):
        if obligation.status not in ("due", "part_paid"):
            continue
        offer = min(offered.get(obligation.party, 0), obligation.outstanding())
        if offer <= 0:
            continue
        moved = 0
        taker, where = collector.get(
            obligation.beneficiary, (obligation.beneficiary, ""))
        for lot in book.at(obligation.party):
            if lot.good != obligation.good or moved >= offer:
                continue
            # A party cannot render what the collector already owns.
            if lot.owner == taker:
                continue
            take = min(offer - moved, lot.free)
            if take <= 0:
                continue
            ordinal = parts.get(obligation.party, 0)
            parts[obligation.party] = ordinal + 1
            # Block 2000 and up: clear of the farm steps' ordinals, which run from 200 to just past.
            part = mint(obligation.party, kernel.date.absolute, "lot",
                        2000 + ordinal)
            whole = take == lot.quantity
            book = book.give(
                lot.id, take, taker, "levied",
                authority=obligation.id,
                new_id=None if whole else part)
            # And it is carried.
            if where:
                book = book.relocate(lot.id if whole else part, where,
                                     "levied", authority=obligation.id)
            moved += take
        if moved > 0:
            obligations[i] = O.render(obligation, moved)
            events.append(("rendered", obligation.id, moved))

    # What is still due when its window has closed has been defaulted on.
    for i, obligation in enumerate(obligations):
        if obligation.status in ("due", "part_paid") and not O.falls_due(
                obligation, kernel.date, dict(kernel.seasons)):
            obligations[i] = O.move(obligation, "defaulted")
            events.append(("defaulted", obligation.id,
                           obligation.outstanding()))

    # A yearly render is not one debt settled forever.
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
    """What a turn actually did."""
    turn: int
    intents: tuple[Intent, ...] = ()
    allocation: R.Allocation = dataclasses.field(default_factory=R.Allocation)
    transfers: tuple[W.Transfer, ...] = ()
    events: tuple = ()
    # The turn's bargains.
    contracts: tuple[C.Contract, ...] = ()


def advance(kernel: Kernel) -> tuple[Kernel, list]:
    """One fortnight, phases in order, every settlement crossing them together."""
    kernel, events, _log = advance_logged(kernel)
    return kernel, events


def advance_logged(kernel: Kernel, extra_steps: tuple[T.Step, ...] = (),
                   phase_events: dict[str, list] | None = None,
                   ) -> tuple[Kernel, list, TurnLog]:
    """Advance one ordered turn, optionally including another world layer."""
    snapshot = None
    intents: tuple[Intent, ...] = ()
    allocation = R.Allocation()
    struck: list[C.Contract] = []
    captured = phase_events if phase_events is not None else {}

    def calendar(state):
        return dataclasses.replace(state, date=state.date.advance()), []

    def observe(state):
        nonlocal snapshot
        snapshot = open_turn(state, state.date.absolute)
        return _observe(state, snapshot)

    def decide(state):
        nonlocal intents
        intents = _intents(state, snapshot)
        return state, []

    def allocate(state):
        nonlocal allocation
        allocation = R.allocate(
            intents, _capacity(state),
            authority_rank=lambda i: state.registry.orgs[i.actor].authority
            if i.actor in state.registry.orgs else 0)
        return state, []

    def market(state):
        state, produced, contracts = C.market(state, intents)
        struck.extend(contracts)
        return state, produced

    def record(step: T.Step) -> T.Step:
        def run(state):
            state, produced = step.run(state)
            captured.setdefault(step.phase, []).extend(produced or ())
            return state, produced
        return T.Step(step.phase, step.name, run)

    core = tuple(map(record, (
        T.Step("calendar", "date", calendar),
        T.Step("arrivals", "journeys", C.arrivals),
        T.Step("observe", "local knowledge", observe),
        T.Step("intents", "decisions", decide),
        T.Step("allocate", "capacity", allocate),
        T.Step("production", "sowing", lambda k: F.sow(k, intents, allocation)),
        T.Step("production", "growing", lambda k: F.tend(k, intents, allocation)),
        T.Step("production", "harvest", lambda k: F.reap(k, intents, allocation)),
        T.Step("production", "seed corn", lambda k: F.store_seed(k, intents)),
        T.Step("production", "the mines", F.mine),
        T.Step("production", "the share",
               lambda k: F.share_out(k, _reaped(captured))),
        T.Step("production", "the forge", AR.step),
        T.Step("production", "the stack", F.keep),
        T.Step("consumption", "rations", _consume),
        T.Step("market", "bargains", market),
        T.Step("movement", "sailings", lambda k: C.movement(k, intents, allocation)),
        T.Step("settlement", "obligations", lambda k: _settle(k, intents)),
        T.Step("settlement", "the stores", C.consolidate),
        T.Step("health", "the roll", _breed),
    )))
    steps = tuple(sorted(core + extra_steps, key=lambda step: T.index(step.phase)))
    kernel, events, _trace = T.run(kernel, steps)

    log = TurnLog(
        turn=kernel.date.absolute, intents=intents, allocation=allocation,
        # The book's ledger drains on the turn's first `at_phase`.
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
        # Cargo that is not on the route it is being carried along is cargo two systems disagree.
        for lot_id in voyage.cargo:
            lot = kernel.book.lots.get(lot_id)
            if lot is not None and lot.location != voyage.route:
                found.append(
                    f"{voyage.id}: carries {lot_id}, which is at {lot.location!r}")
    return tuple(found)
