"""The grain year: sowing, growing, reaping, threshing (spec 6.2, M13.2)."""
from __future__ import annotations

import dataclasses

from engine.core import in_range
from engine.entity import EntityId, mint
from engine.kernel import resolve as R
from engine.kernel.intent import Intent

GRAIN = "grain"
SEED = "seed_grain"
STANDING = "standing_grain"
SHEAVES = "sheaves"
FODDER = "fodder"

# The tasks the year is made of.
TASKS = ("sow", "tend", "reap", "thresh")

# --- the authored rates (spec 6.2: integer tables, order pinned by tests) -----

SOW_PER_DAY = 3        # ploughing, broadcasting, and covering
TEND_PER_DAY = 200     # weeding and watching a standing crop, per fortnight
REAP_PER_DAY = 12      # cutting and stacking -- the year's bottleneck
THRESH_PER_DAY = 22    # threshing floor and winnowing

# What a fortnight of the growing season takes off a standing crop.
NEGLECT_PER_1000 = 60
DROUGHT_PER_1000 = 150

# The threshing floor.
GRAIN_PER_1000 = 940
FODDER_PER_1000 = 700

# Fortnights of eating an actor keeps in hand before it sets grain aside as seed.
SEED_RESERVE_FORTNIGHTS = 2

# Which moment of the farming year it is, as one integer an actor can hold as a claim.
NO_SEASON = 0
SEASON_CODES: tuple[tuple[str, int, str], ...] = (
    ("sowing", 1, "sow"),
    ("growing", 2, "tend"),
    ("harvest", 3, "reap"),
    ("threshing", 4, "thresh"),
)
TASK_FOR = {code: task for _, code, task in SEASON_CODES}


def code_for(seasons, fortnight: int) -> int:
    """The season code an actor would hold this fortnight."""
    for name, code, _ in SEASON_CODES:
        if season(seasons, fortnight, name):
            return code
    return NO_SEASON

# Ordinal blocks, so that two steps minting lots at the same parent on the same turn cannot collide.
BLOCKS = {"sow": 200, "reap": 400, "thresh": 600, "fodder": 800, "seed": 1000,
          "share": 1200}

# What a household keeps of the crop it worked, where the land is held that way (`entity.TENURES`.
HOUSEHOLD_SHARE_PER_1000 = 850


# --- the calendar -------------------------------------------------------------

def season(seasons, fortnight: int, name: str) -> bool:
    """Whether this fortnight falls in an authored span. Absent span, never."""
    span = seasons.get(name)
    return bool(span) and in_range(fortnight, tuple(span))


def closing(seasons, fortnight: int, name: str) -> bool:
    """Whether this is the span's last fortnight -- the deadline, not the season."""
    span = tuple(seasons.get(name, ()))
    if not span:
        return False
    return fortnight == (span[1] if len(span) == 2 else max(span))


def days_for(quantity: int, per_day: int) -> int:
    """Person-days to handle a quantity, rounded up. Nobody works half a day."""
    return -(-max(0, quantity) // per_day) if per_day > 0 else 0


# --- reading the world --------------------------------------------------------

def granted(intents: tuple[Intent, ...],
            allocation: R.Allocation) -> dict[tuple[EntityId, str], int]:
    """Person-days each actor actually got, by task. The join the steps read."""
    days: dict[tuple[EntityId, str], int] = {}
    for intent in intents:
        if intent.kind != "produce" or intent.task not in TASKS:
            continue
        got = allocation.granted(intent.id)
        if got > 0:
            key = (intent.actor, intent.task)
            days[key] = days.get(key, 0) + got
    return days


def _lots(book, owner: EntityId, good: str, location: EntityId = ""):
    """An owner's lots of one good, in id order. Never anybody else's."""
    return tuple(lot for lot in book.owned_by(owner)
                 if lot.good == good and (not location or lot.location == location))


def held(book, owner: EntityId, good: str, location: EntityId = "") -> int:
    return sum(lot.free for lot in _lots(book, owner, good, location))


def under_crop(kernel, site_id: EntityId) -> int:
    """How much of an estate is sown, in qa of seed -- everybody's crop together."""
    site = kernel.registry.sites.get(site_id)
    if site is None or site.capacity <= 0:
        return 0
    standing = sum(lot.quantity for lot in kernel.book.at(site_id)
                   if lot.good == STANDING)
    return standing * 1000 // site.capacity


def _draw(book, lots, quantity: int, reason: str, authority: EntityId = ""):
    """Take a quantity across an owner's lots, in id order."""
    taken = 0
    drawn: list[EntityId] = []
    for lot in lots:
        if taken >= quantity:
            break
        # Re-read: an earlier iteration may have emptied this lot out of the book.
        current = book.lots.get(lot.id)
        if current is None:
            continue
        take = min(quantity - taken, current.free)
        if take <= 0:
            continue
        book = book.consume(current.id, take, reason, authority=authority)
        taken += take
        drawn.append(current.id)
    return book, taken, tuple(drawn)


def _farmers(kernel) -> tuple[EntityId, ...]:
    """Deciders, in the order the allocator would serve them."""
    def rank(actor: EntityId) -> tuple:
        org = kernel.registry.orgs.get(actor)
        return (-(org.authority if org else 0), actor)
    return tuple(sorted(kernel.farmers(), key=rank))


def _settlement_of(kernel, actor: EntityId) -> EntityId:
    org = kernel.registry.orgs.get(actor)
    return org.settlement if org else ""


def _sowable(kernel, book, actor: EntityId, settlement: EntityId):
    """The seed this actor can put in the ground, whoever's house it sits in."""
    lots = list(_lots(book, actor, SEED, settlement))
    if actor != kernel.controller(settlement):
        return tuple(lots)
    for cohort in kernel.cohorts_of(settlement):
        if kernel.tenure_of(cohort) == "subsistence":
            lots.extend(_lots(book, cohort.id, SEED, settlement))
    return tuple(lots)


# --- the four moments ---------------------------------------------------------

def sow(kernel, intents: tuple[Intent, ...], allocation: R.Allocation):
    """Seed goes into the ground."""
    events: list = []
    if not season(kernel.seasons, kernel.date.fortnight, "sowing"):
        return kernel, events

    book = kernel.book.at_phase(kernel.date.absolute, "production")
    days = granted(intents, allocation)
    turn = kernel.date.absolute

    # Land left is recomputed per actor, in served order.
    left: dict[EntityId, int] = {}
    planted: dict[EntityId, tuple[EntityId, int]] = {}
    for actor in _farmers(kernel):
        got = days.get((actor, "sow"), 0)
        if got <= 0:
            continue
        settlement = _settlement_of(kernel, actor)
        site_id = kernel.field_site(settlement, actor)
        if not site_id:
            continue
        site = kernel.registry.sites[site_id]
        if site.capacity <= 0 or site.extent <= 0:
            continue
        if site_id not in left:
            left[site_id] = max(0, site.extent - under_crop(
                dataclasses.replace(kernel, book=book), site_id))

        sowable = _sowable(kernel, book, actor, settlement)
        seed = min(sum(lot.free for lot in sowable),
                   got * SOW_PER_DAY,
                   left[site_id])
        if seed <= 0:
            continue

        book, sown, from_lots = _draw(book, sowable, seed, "sown",
                                      authority=actor)
        if sown <= 0:
            continue
        left[site_id] -= sown
        planted[actor] = (site_id, sown * site.capacity // 1000, from_lots)

    for i, actor in enumerate(sorted(planted)):
        site_id, quantity, from_lots = planted[actor]
        if quantity <= 0:
            continue
        book = book.create(_mint(site_id, turn, "sow", i), STANDING, quantity,
                           owner=actor, holder=actor, location=site_id,
                           reason="produced", from_lots=from_lots)
        events.append(("sown", actor, site_id, quantity))
    return dataclasses.replace(kernel, book=book), events


def tend(kernel, intents: tuple[Intent, ...], allocation: R.Allocation):
    """The crop stands there."""
    events: list = []
    if not season(kernel.seasons, kernel.date.fortnight, "growing"):
        return kernel, events

    book = kernel.book.at_phase(kernel.date.absolute, "production")
    days = granted(intents, allocation)

    for actor in _farmers(kernel):
        lots = _lots(book, actor, STANDING)
        standing = sum(lot.quantity for lot in lots)
        if standing <= 0:
            continue

        # The weather is the region's, not the world's.
        region = kernel.region_of(_settlement_of(kernel, actor))
        climate = kernel.climate_at(kernel.date.absolute, region)
        weather = max(0, 100 - climate) * DROUGHT_PER_1000

        wanted = days_for(standing, TEND_PER_DAY)
        got = min(days.get((actor, "tend"), 0), wanted)
        neglect = (wanted - got) * 1000 // wanted if wanted else 0

        # Order pinned: neglect first, then weather.
        lost = (standing * neglect * NEGLECT_PER_1000 // 1_000_000
                + standing * weather // 100_000)
        lost = min(standing, lost)
        if lost <= 0:
            continue
        book, gone, _ = _draw(book, lots, lost, "spoiled")
        if gone > 0:
            events.append(("withered", actor, gone, neglect, climate))
    return dataclasses.replace(kernel, book=book), events


def reap(kernel, intents: tuple[Intent, ...], allocation: R.Allocation):
    """Cut and stack it, inside the window, or lose it where it stands."""
    events: list = []
    fortnight = kernel.date.fortnight
    if not season(kernel.seasons, fortnight, "harvest"):
        return kernel, events

    book = kernel.book.at_phase(kernel.date.absolute, "production")
    days = granted(intents, allocation)
    turn = kernel.date.absolute

    cut: dict[EntityId, int] = {}
    for actor in _farmers(kernel):
        lots = _lots(book, actor, STANDING)
        standing = sum(lot.quantity for lot in lots)
        if standing <= 0:
            continue
        want = min(standing, days.get((actor, "reap"), 0) * REAP_PER_DAY)
        if want <= 0:
            continue
        book, taken, from_lots = _draw(book, lots, want, "expended",
                                       authority=actor)
        if taken > 0:
            cut[actor] = (taken, from_lots)

    for i, actor in enumerate(sorted(cut)):
        settlement = _settlement_of(kernel, actor)
        quantity, from_lots = cut[actor]
        lot_id = _mint(settlement, turn, "reap", i)
        book = book.create(lot_id, SHEAVES, quantity, owner=actor,
                           holder=actor, location=settlement,
                           reason="harvested", from_lots=from_lots)
        events.append(("reaped", actor, settlement, quantity))

    # The deadline.
    if closing(kernel.seasons, fortnight, "harvest"):
        for actor in _farmers(kernel):
            lots = _lots(book, actor, STANDING)
            standing = sum(lot.quantity for lot in lots)
            if standing <= 0:
                continue
            book, gone, _ = _draw(book, lots, standing, "spoiled")
            if gone > 0:
                events.append(("unreaped", actor, gone))
    return dataclasses.replace(kernel, book=book), events


def thresh(kernel, intents: tuple[Intent, ...], allocation: R.Allocation):
    """Sheaves become grain a household can eat and straw an ox can."""
    events: list = []
    if not season(kernel.seasons, kernel.date.fortnight, "threshing"):
        return kernel, events

    book = kernel.book.at_phase(kernel.date.absolute, "production")
    days = granted(intents, allocation)
    turn = kernel.date.absolute

    done: dict[EntityId, int] = {}
    for actor in _farmers(kernel):
        lots = _lots(book, actor, SHEAVES)
        stacked = sum(lot.quantity for lot in lots)
        if stacked <= 0:
            continue
        want = min(stacked, days.get((actor, "thresh"), 0) * THRESH_PER_DAY)
        if want <= 0:
            continue
        book, taken, from_lots = _draw(book, lots, want, "expended",
                                       authority=actor)
        if taken > 0:
            done[actor] = (taken, from_lots)

    for i, actor in enumerate(sorted(done)):
        settlement = _settlement_of(kernel, actor)
        stacked, from_lots = done[actor]
        grain = stacked * GRAIN_PER_1000 // 1000
        straw = stacked * FODDER_PER_1000 // 1000
        if grain > 0:
            book = book.create(_mint(settlement, turn, "thresh", i), GRAIN,
                               grain, owner=actor, holder=actor,
                               location=settlement, reason="produced",
                               from_lots=from_lots)
        if straw > 0:
            book = book.create(_mint(settlement, turn, "fodder", i), FODDER,
                               straw, owner=actor, holder=actor,
                               location=settlement, reason="produced",
                               from_lots=from_lots)
        events.append(("threshed", actor, settlement, grain, straw))
    return dataclasses.replace(kernel, book=book), events


def store_seed(kernel, intents: tuple[Intent, ...]):
    """Grain set aside as next year's seed: food chosen against."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    turn = kernel.date.absolute

    wanted = {i.actor: i.quantity for i in intents
              if i.kind == "produce" and i.task == "seed" and i.quantity > 0}
    for i, actor in enumerate(sorted(wanted)):
        settlement = _settlement_of(kernel, actor)
        lots = _lots(book, actor, GRAIN, settlement)
        take = min(wanted[actor], sum(lot.free for lot in lots))
        if take <= 0:
            continue
        book, taken, from_lots = _draw(book, lots, take, "expended",
                                       authority=actor)
        if taken <= 0:
            continue
        book = book.create(_mint(settlement, turn, "seed", i), SEED, taken,
                           owner=actor, holder=actor, location=settlement,
                           reason="produced", from_lots=from_lots)
        events.append(("set_aside", actor, taken))
    return dataclasses.replace(kernel, book=book), events


def share_out(kernel):
    """The households take their own crop, where the land is held that way."""
    if not closing(kernel.seasons, kernel.date.fortnight, "threshing"):
        return kernel, []
    return divide(kernel, kernel.book.at_phase(kernel.date.absolute,
                                               "production"))


def divide(kernel, book=None):
    """The division itself, without the calendar."""
    events: list = []
    book = kernel.book if book is None else book
    turn = kernel.date.absolute
    index = 0
    for settlement in kernel.autonomous():
        holders = [c for c in kernel.cohorts_of(settlement)
                   if kernel.tenure_of(c) == "subsistence" and c.people > 0]
        if not holders:
            continue
        council = kernel.controller(settlement)
        people = sum(c.people for c in holders)

        # Grain and seed both.
        for good in (GRAIN, SEED):
            stock = sum(lot.free for lot in _lots(book, council, good,
                                                  settlement))
            share = stock * HOUSEHOLD_SHARE_PER_1000 // 1000
            if share <= 0:
                continue
            # By heads, and the remainder stays with the council rather than going to whoever sorts.
            for cohort in holders:
                due = share * cohort.people // people
                if due <= 0:
                    continue
                book, taken, from_lots = _draw(
                    book, _lots(book, council, good, settlement), due,
                    "expended", authority=council)
                if taken <= 0:
                    continue
                book = book.create(
                    _mint(settlement, turn, "share", index), good, taken,
                    owner=cohort.id, holder=cohort.id, location=settlement,
                    reason="produced", from_lots=from_lots)
                index += 1
                events.append(("shared_out", cohort.id, settlement, good, taken))
    return dataclasses.replace(kernel, book=book), events


def keep(kernel):
    """What stored goods lose to the weather, the rats, and the waiting."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    # The seat is the court's, the same way its mouths are (`world._consume`).
    seat = getattr(kernel.seat_goods, "seat", "")
    for lot_id in sorted(book.lots):
        lot = book.lots.get(lot_id)
        if lot is None:
            continue
        if seat and lot.location == seat:
            continue
        rate = kernel.spoilage.get(lot.good, 0)
        if rate <= 0:
            continue
        lost = min(lot.free, lot.quantity * rate // 1000)
        if lost <= 0:
            continue
        book = book.consume(lot_id, lost, "spoiled")
        events.append(("spoiled", lot.owner, lot.good, lost))
    return dataclasses.replace(kernel, book=book), events


def _mint(parent: EntityId, turn: int, block: str, index: int) -> EntityId:
    """One lot id, inside this step's reserved ordinal block."""
    return mint(parent, turn, "lot", BLOCKS[block] + index)
