"""The grain year: sow, let it stand, harvest (spec 6.2, M13.2).

Three moments: sow, tend, reap. Reaping brings grain in directly, with cutting,
carrying and processing folded into `HARVEST_PER_1000`.
"""
from __future__ import annotations

import dataclasses

from engine.core import in_range
from engine.entity import EntityId, mint
from engine.kernel import resolve as R
from engine.kernel.intent import Intent

GRAIN = "grain"
SEED = "seed_grain"
STANDING = "standing_grain"

# The tasks the year is made of.
TASKS = ("sow", "tend", "reap")

# --- the authored rates (spec 6.2: integer tables, order pinned by tests) -----

SOW_PER_DAY = 3        # ploughing, broadcasting, and covering
TEND_PER_DAY = 200     # weeding and watching a standing crop, per fortnight
REAP_PER_DAY = 12      # cutting and carrying -- the year's bottleneck

# What a fortnight of the growing season takes off a standing crop.
NEGLECT_PER_1000 = 60
DROUGHT_PER_1000 = 200

# A dry year and a failed year are not the same thing by twice. Past this much
# shortfall in the climate reading the crop is not merely thinner, it is dying
# where it stands, and each further step of dryness costs the multiple.
DROUGHT_BREAK = 25
DROUGHT_BITE = 1

# What a standing crop returns as grain once it is in. The chaff and the straw
# are still lost; they are simply not counted as a good anybody holds.
HARVEST_PER_1000 = 940

# Fortnights of eating an actor keeps in hand before it sets grain aside as seed.
SEED_RESERVE_FORTNIGHTS = 2

# What a household's own pits and jars hold, in fortnights of its own eating,
# and what it loses a fortnight on everything above that. The crown's granary
# has the same pair of numbers in `systems.spoilage`, at a longer line: a palace
# store is built for the job and a yard is not.
VILLAGE_FORTNIGHTS = 24
VILLAGE_OVERFLOW_PER_1000 = 100

# Which moment of the farming year it is, as one integer an actor can hold as a claim.
NO_SEASON = 0
SEASON_CODES: tuple[tuple[str, int, str], ...] = (
    ("sowing", 1, "sow"),
    ("growing", 2, "tend"),
    ("harvest", 3, "reap"),
)
TASK_FOR = {code: task for _, code, task in SEASON_CODES}


def code_for(seasons, fortnight: int) -> int:
    """The season code an actor would hold this fortnight."""
    for name, code, _ in SEASON_CODES:
        if season(seasons, fortnight, name):
            return code
    return NO_SEASON

# Ordinal blocks, so that two steps minting lots at the same parent on the same turn cannot collide.
BLOCKS = {"sow": 200, "reap": 400, "seed": 1000, "share_seed": 1100,
          "share": 1200, "mine": 1400, "forge": 1600}

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


def extent(kernel, site_id: EntityId) -> int:
    site = kernel.registry.sites.get(site_id)
    if site is None:
        return 0
    return max(0, site.extent + kernel.site_extent_bonus.get(site_id, 0))


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


# --- the three moments --------------------------------------------------------

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
        field_extent = extent(kernel, site_id)
        if site.capacity <= 0 or field_extent <= 0:
            continue
        if site_id not in left:
            left[site_id] = max(0, field_extent - under_crop(
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
    """Bring it in, inside the window, or lose it where it stands."""
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
        standing, from_lots = cut[actor]
        grain = standing * HARVEST_PER_1000 // 1000
        if grain <= 0:
            continue
        book = book.create(_mint(settlement, turn, "reap", i), GRAIN, grain,
                           owner=actor, holder=actor, location=settlement,
                           reason="harvested", from_lots=from_lots)
        events.append(("reaped", actor, settlement, grain))

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

# The olive and the vine are not sown and not reaped. They stand, and the year
# turns on one fortnight of pressing. Before this the oil and the wine had no
# source at all: the lamps of the temple and the harbour burned the authored
# store down in about seven years, and every rite after that was skipped for
# want of a jar, which took the crown's legitimacy to nothing on its own.
GROVE_PER_1000 = 1000
GROVES = ("oil", "wine")
PRESSING = 20


def mine(kernel):
    """Phase: what the ground gives, to whoever holds it -- ore and press both."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    turn = kernel.date.absolute
    for i, site_id in enumerate(sorted(kernel.registry.sites)):
        site = kernel.registry.sites[site_id]
        if site.capacity <= 0:
            continue
        if site.function in METALS:
            got = site.capacity * MINE_PER_1000 // 1000
        elif (site.function in GROVES
              and kernel.date.fortnight == PRESSING):
            got = site.capacity * GROVE_PER_1000 // 1000
        else:
            continue
        owner = kernel.controller(site.settlement)
        if not owner or got <= 0:
            continue
        book = book.create(_mint(site.settlement, turn, "mine", i),
                           site.function, got, owner=owner, holder=owner,
                           location=site.settlement, reason="produced")
        events.append(("mined", site_id, site.function, got))
    return dataclasses.replace(kernel, book=book), events


def sown_extent(kernel, settlement: EntityId) -> int:
    """Qa of seed the settlement's food ground takes in a year."""
    return sum(extent(kernel, site.id) for site in kernel.registry.sites.values()
               if site.settlement == settlement and site.function == "food")


def share_out(kernel, crop=None):
    """The households take their own crop, where the land is held that way.

    `crop` is what the harvest brought in this year, by actor. Without it the
    whole stock is divided, which is the same thing anywhere the council's
    granary is the harvest pile -- and is wrong at the seat, where the crown's
    store stands beside it and is not the villages' to take.
    """
    # Every harvest fortnight, not only the last: the reaping runs for more than
    # one, and a share taken off the closing turn alone loses the rest.
    if crop is None:
        if not closing(kernel.seasons, kernel.date.fortnight, "harvest"):
            return kernel, []
    elif not season(kernel.seasons, kernel.date.fortnight, "harvest"):
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
        # Next year's seed comes off the harvest before anybody's share does,
        # and is set aside there and then. The council decides it on last
        # fortnight's belief, which cannot see the grain harvested this one.
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
                        _mint(settlement, turn, "share_seed", index), SEED, taken,
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


def _line_for(kernel, owner: EntityId) -> int:
    """What this owner can keep: a year of the eating it answers for.

    A household answers for itself. A council answers for its whole settlement,
    because the communal store is what the place eats out of. The crown at the
    seat is neither: its granary has an authored capacity and `systems.spoilage`
    is what holds it to it, so `keep` never reaches those lots at all.
    """
    cohort = kernel.registry.cohorts.get(owner)
    if cohort is not None:
        return cohort.ration() * VILLAGE_FORTNIGHTS
    org = kernel.registry.orgs.get(owner)
    if org is None:
        return 0
    return sum(c.ration() for c in kernel.cohorts_of(org.settlement)) \
        * VILLAGE_FORTNIGHTS


def _over_the_line(kernel, book) -> dict:
    """Per-thousand an owner loses on top, for grain it cannot keep.

    The crown has a granary and it has a capacity; a village has pits and jars
    and a year's eating is what they hold. Without the line a good harvest every
    year piles up and never comes down: the seat's villages reached six years of
    grain in their yards by year twenty, and the palaces abroad reached far
    worse -- Egypt alone stood on 849 million qa. Nothing that happened
    afterwards could bite. The line is what makes a store worth having and a bad
    year worth fearing.
    """
    held_by: dict = {}
    for lot in book.lots.values():
        if lot.good == GRAIN:
            held_by[lot.owner] = held_by.get(lot.owner, 0) + lot.free
    spill = {}
    for owner, total in held_by.items():
        line = _line_for(kernel, owner)
        if line and total > line:
            spill[owner] = (total - line) * VILLAGE_OVERFLOW_PER_1000 // total
    return spill


def keep(kernel):
    """What stored goods lose to the weather, the rats, and the waiting."""
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    # The court's own stores spoil under `systems.spoilage`, which rides on the
    # granary's roof. Everything else at the seat -- the villagers' own grain in
    # their own yards -- keeps no better here than anywhere else.
    seat = getattr(kernel.seat_goods, "seat", "")
    crown = getattr(kernel.seat_goods, "owner", "")
    spill = _over_the_line(kernel, book)
    for lot_id in sorted(book.lots):
        lot = book.lots.get(lot_id)
        if lot is None:
            continue
        if seat and lot.location == seat and lot.owner == crown:
            continue
        rate = kernel.spoilage.get(lot.good, 0)
        if lot.good == GRAIN:
            rate += spill.get(lot.owner, 0)
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
