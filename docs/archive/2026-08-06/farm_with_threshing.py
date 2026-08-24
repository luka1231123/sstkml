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
DROUGHT_PER_1000 = 200

# A dry year and a failed year are not the same thing by twice. Past this much
# shortfall in the climate reading the crop is not merely thinner, it is dying
# where it stands, and each further step of dryness costs the multiple.
DROUGHT_BREAK = 25
DROUGHT_BITE = 1

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
          "mine": 1400,
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
        dry = max(0, 100 - climate)
        weather = (dry + max(0, dry - DROUGHT_BREAK) * DROUGHT_BITE) \
            * DROUGHT_PER_1000

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


# What a working mine yields in a fortnight, per thousand of its authored
# capacity. The sites, their capacities and their metals were all authored and
# nothing ever dug them: world tin fell from 2,600 to 800 in four years, copper
# from 102,000 to 36,612, and the bronze chain could only ever run down. Metal
# is meant to be scarce and far away, not finite.
MINE_PER_1000 = 120
METALS = ("copper", "tin", "gold", "silver")


def mine(kernel):
    """Phase: the ore comes up, and belongs to whoever holds the ground."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    turn = kernel.date.absolute
    for i, site_id in enumerate(sorted(kernel.registry.sites)):
        site = kernel.registry.sites[site_id]
        if site.function not in METALS or site.capacity <= 0:
            continue
        owner = kernel.controller(site.settlement)
        if not owner:
            continue
        got = site.capacity * MINE_PER_1000 // 1000
        if got <= 0:
            continue
        book = book.create(_mint(site.settlement, turn, "mine", i),
                           site.function, got, owner=owner, holder=owner,
                           location=site.settlement, reason="produced")
        events.append(("mined", site_id, site.function, got))
    return dataclasses.replace(kernel, book=book), events


def sown_extent(kernel, settlement: EntityId) -> int:
    """Qa of seed the settlement's food ground takes in a year."""
    return sum(site.extent for site in kernel.registry.sites.values()
               if site.settlement == settlement and site.function == "food")


def share_out(kernel, crop=None):
    """The households take their own crop, where the land is held that way.

    `crop` is what the floor made this year, by actor. Without it the whole
    stock is divided, which is the same thing anywhere the council's granary is
    the harvest pile -- and is wrong at the seat, where the crown's store stands
    beside it and is not the villages' to take.
    """
    # Every threshing fortnight, not only the last: the floor works for more
    # than one, and a share taken off the closing turn alone loses the rest.
    if crop is None:
        if not closing(kernel.seasons, kernel.date.fortnight, "threshing"):
            return kernel, []
    elif not season(kernel.seasons, kernel.date.fortnight, "threshing"):
        return kernel, []
    return divide(kernel, kernel.book.at_phase(kernel.date.absolute,
                                               "production"), crop)


def divide(kernel, book=None, crop=None):
    """The division itself, without the calendar."""
    events: list = []
    book = kernel.book if book is None else book
    turn = kernel.date.absolute
    index = 0
    # Every settlement, the seat included: the crown's villages hold their crop
    # the same way anyone else's do, and the crown keeps the due.
    for settlement in sorted(kernel.registry.settlements):
        if kernel.registry.settlements[settlement].fallen:
            continue
        holders = [c for c in kernel.cohorts_of(settlement)
                   if kernel.tenure_of(c) == "subsistence" and c.people > 0]
        if not holders:
            continue
        council = kernel.controller(settlement)
        people = sum(c.people for c in holders)
        # The crown's own villages render what the court set; everybody else's
        # render the customary share.
        crown = getattr(kernel.seat_goods, "seat", "")
        # The opening division (`crop is None`) shares out an authored heap. The
        # crown's granary is not one: its villages are authored their own.
        if crop is None and settlement == crown:
            continue
        keep_rate = (1000 - kernel.land_due_per_1000 if settlement == crown
                     else HOUSEHOLD_SHARE_PER_1000)
        # The crown renders no more grain than it can roof. What the granary
        # cannot take stays with the villages, so a bigger due needs a bigger
        # granary and the store fills to the same line every harvest.
        room = -1
        if settlement == crown and kernel.granary_capacity > 0 and crop:
            # What stood in the granary before this floor's crop reached it.
            prior = max(0, held(book, council, GRAIN, settlement)
                        - crop.get(council, 0))
            room = max(0, kernel.granary_capacity - prior)

        # Next year's seed comes off the floor before anybody's share does, and
        # is set aside there and then. The council decides its reserve on last
        # fortnight's belief, which cannot see the crop threshed this one.
        seed_first = 0
        if crop is not None:
            want = max(0, sown_extent(kernel, settlement)
                       - held(book, council, SEED, settlement))
            spare = min(crop.get(council, 0),
                        held(book, council, GRAIN, settlement))
            seed_first = min(want, max(0, spare))
            if seed_first > 0:
                book, taken, from_lots = _draw(
                    book, _lots(book, council, GRAIN, settlement), seed_first,
                    "expended", authority=council)
                if taken > 0:
                    book = book.create(
                        _mint(settlement, turn, "seed", index), SEED, taken,
                        owner=council, holder=council, location=settlement,
                        reason="produced", from_lots=from_lots)
                    index += 1
                    events.append(("set_aside", council, taken))
                seed_first = taken

        # Grain and seed both.
        for good in (GRAIN, SEED):
            stock = sum(lot.free for lot in _lots(book, council, good,
                                                  settlement))
            if crop is not None:
                # The seed is already out of the book; the crop it came out of
                # has to lose it too, or it is held back twice.
                left = max(0, crop.get(council, 0) - seed_first)
                stock = min(stock, left if good == GRAIN else 0)
            share = stock * keep_rate // 1000
            if good == GRAIN and room >= 0:
                share = max(share, stock - room)
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
