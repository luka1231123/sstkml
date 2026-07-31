"""The grain year: sowing, growing, reaping, threshing (spec 6.2, M13.2).

M13.1 made grain out of person-days every fortnight of the year, and said so in
its own docstring rather than pretending otherwise. This is the chain that
replaces it, and the reason it matters is not realism for its own sake: it is
that an undifferentiated production rate has no *moments*. If a fortnight of
labour always yields the same grain, then diverting hands to the temple, or to
a corvee, or losing them to hunger, costs the same in every fortnight of the
year -- and a player who moves labour has no timing to get wrong.

A grain year has four moments, and they are not interchangeable:

    sowing      seed goes into the ground, and the ground takes only so much
    growing     the crop stands there being lost, to neglect and to weather
    harvest     it must be cut inside a short window or it is lost entirely
    threshing   what was cut becomes what can be eaten

Between them they produce the pressures the rest of the game is built on. Seed
is food you have chosen not to eat. The harvest window is short and hungry
people are weak, so a bad winter takes the next harvest too. And the ground has
an extent, so a settlement cannot sow its way out of a famine -- it has to get
grain from somewhere else, which is the whole of M13.2's reason for existing.

Everything is one quantity changing form. A qa of seed becomes some qa of
standing crop, which becomes qa of sheaves, which becomes qa of grain and qa of
fodder. Every step is a `Book` transfer, so `ownership.conservation` accounts
for each good separately and the inspector can follow a single harvest from the
furrow to the household that ate it.

Two limitations, stated rather than hidden.

Land is capped inside `sow` rather than in the global allocator, because an
`Intent` claims one exclusive resource and sowing's is person-days. Two
claimants on one estate are therefore served in the allocator's own order --
authority, then id -- rather than by bidding. Nothing yet leases or contests
fields; when M13.3 does, land becomes a pool like any other and this cap goes.

The estate is a single number, not a set of plots. Fallow, rotation, and
soil exhaustion are not modelled, so `extent` should be read as "the ground
worked in a year", already net of whatever is resting.
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
SHEAVES = "sheaves"
FODDER = "fodder"

# The tasks the year is made of. This module owns the vocabulary; `Intent.task`
# does not police it, because the allocator prices person-days identically
# whichever of these they go into.
TASKS = ("sow", "tend", "reap", "thresh")

# --- the authored rates (spec 6.2: integer tables, order pinned by tests) -----
#
# Person-days per qa, expressed as the qa one person handles in a day, because
# that is the direction the sources give. They are calibrated together: what
# matters is not any one of them but that reaping is the year's labour peak,
# which is why the harvest window is the moment a settlement can be hurt by
# losing hands. See tests/test_kernel_farm.py, which pins the ratios.

SOW_PER_DAY = 3        # ploughing, broadcasting, and covering
TEND_PER_DAY = 200     # weeding and watching a standing crop, per fortnight
REAP_PER_DAY = 12      # cutting and stacking -- the year's bottleneck
THRESH_PER_DAY = 22    # threshing floor and winnowing

# What a fortnight of the growing season takes off a standing crop.
#
# Neglect is scaled by how much of the tending the crop wanted it did not get,
# so a crop nobody touches all winter loses about two fifths of itself and a
# crop fully tended loses nothing. Weather is scaled by how far below an
# ordinary year the climate index sits: a year at 62 takes something over a
# third of the crop across a whole growing season, which is a shortfall no
# amount of local effort closes and is meant to be.
NEGLECT_PER_1000 = 60
DROUGHT_PER_1000 = 150

# The threshing floor. A thousand qa of sheaves is not a thousand qa of grain:
# some is lost to the floor and the wind, and the straw is a different good with
# a different use.
GRAIN_PER_1000 = 940
FODDER_PER_1000 = 700

# Fortnights of eating an actor keeps in hand before it sets grain aside as
# seed. Deliberately small, and the reasoning matters.
#
# The obvious rule -- keep back everything you will eat before the next harvest,
# then set aside what is left -- is prudent for one year and fatal over three.
# The gap from threshing to the next harvest is about twenty fortnights, which
# is most of what a settlement produces, so a council following it sets aside
# almost no seed, sows almost nothing, and starves next year while sitting on a
# full granary. It was tried; that is exactly what it did.
#
# The real order is the other way round and always was. Seed is set aside
# first, because a year without seed is not a hungry year, it is the end of the
# settlement. What protects the council from its own prudence is not a reserve:
# it is that seed corn is food. It can be eaten, `_consume` does eat it when the
# grain runs out, and the price of that decision arrives at the next sowing
# rather than being forbidden in advance.
SEED_RESERVE_FORTNIGHTS = 2

# Which moment of the farming year it is, as one integer an actor can hold as a
# claim. Codes rather than names because a claim carries a value, and 0 -- no
# field work owed this fortnight -- has to be sayable.
NO_SEASON = 0
SEASON_CODES: tuple[tuple[str, int, str], ...] = (
    ("sowing", 1, "sow"),
    ("growing", 2, "tend"),
    ("harvest", 3, "reap"),
    ("threshing", 4, "thresh"),
)
TASK_FOR = {code: task for _, code, task in SEASON_CODES}


def code_for(seasons, fortnight: int) -> int:
    """The season code an actor would hold this fortnight. First match wins.

    Overlapping spans are content errors, not something to resolve here; the
    first authored match is taken so that the result is at least stable if one
    slips through.
    """
    for name, code, _ in SEASON_CODES:
        if season(seasons, fortnight, name):
            return code
    return NO_SEASON

# Ordinal blocks, so that two steps minting lots at the same parent on the same
# turn cannot collide. 0-199 is left to the settlement phase's levy ordinals.
BLOCKS = {"sow": 200, "reap": 400, "thresh": 600, "fodder": 800, "seed": 1000}


# --- the calendar -------------------------------------------------------------

def season(seasons, fortnight: int, name: str) -> bool:
    """Whether this fortnight falls in an authored span. Absent span, never."""
    span = seasons.get(name)
    return bool(span) and in_range(fortnight, tuple(span))


def closing(seasons, fortnight: int, name: str) -> bool:
    """Whether this is the span's last fortnight -- the deadline, not the season.

    A 2-tuple is a range and its last fortnight is its second element, wrapping
    or not; anything else is an explicit list and its last is the largest.
    """
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
    """How much of an estate is sown, in qa of seed -- everybody's crop together.

    In seed rather than in expected grain, because that is the unit the ground
    is measured in and the unit the sowing decision is made in.
    """
    site = kernel.registry.sites.get(site_id)
    if site is None or site.capacity <= 0:
        return 0
    standing = sum(lot.quantity for lot in kernel.book.at(site_id)
                   if lot.good == STANDING)
    return standing * 1000 // site.capacity


def _draw(book, lots, quantity: int, reason: str, authority: EntityId = ""):
    """Take a quantity across an owner's lots, in id order.

    Returns what it got and which lots it came out of. The second is what makes
    a conversion traceable: the sheaves this threshing drew down are named on
    the grain it produced, so the chain from a household's ration back to the
    furrow is a walk over records rather than a guess from a shared turn.
    """
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
    """Deciders, in the order the allocator would serve them.

    Authority first, then id. Where the steps below have to ration something the
    allocator does not -- the extent of the ground -- this is the order they do
    it in, so that the same claimant wins the land as wins the labour.
    """
    def rank(actor: EntityId) -> tuple:
        org = kernel.registry.orgs.get(actor)
        return (-(org.authority if org else 0), actor)
    return tuple(sorted(kernel.deciders(), key=rank))


def _settlement_of(kernel, actor: EntityId) -> EntityId:
    org = kernel.registry.orgs.get(actor)
    return org.settlement if org else ""


# --- the four moments ---------------------------------------------------------

def sow(kernel, intents: tuple[Intent, ...], allocation: R.Allocation):
    """Seed goes into the ground. It is gone, and what stands there is a hope.

    Three things bound it and any of them can be the one that bites: the seed
    the actor kept, the days it was granted, and the ground still unsown. The
    third is why a settlement in a famine cannot simply plant more.
    """
    events: list = []
    if not season(kernel.seasons, kernel.date.fortnight, "sowing"):
        return kernel, events

    book = kernel.book.at_phase(kernel.date.absolute, "production")
    days = granted(intents, allocation)
    turn = kernel.date.absolute

    # Land left is recomputed per actor, in served order, so that what the first
    # claimant sows is genuinely unavailable to the second.
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

        seed = min(held(book, actor, SEED, settlement),
                   got * SOW_PER_DAY,
                   left[site_id])
        if seed <= 0:
            continue

        book, sown, from_lots = _draw(
            book, _lots(book, actor, SEED, settlement), seed, "sown",
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
    """The crop stands there. What happens to it is weather and attention.

    Nothing is added here -- a crop cannot exceed what was sown for it. A good
    year is one in which little is lost, which is what a good year is.
    """
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

        # The weather is the region's, not the world's. Two settlements in the
        # same fortnight can have different years, and that difference is what
        # makes a crossing worth making.
        region = kernel.region_of(_settlement_of(kernel, actor))
        climate = kernel.climate_at(kernel.date.absolute, region)
        weather = max(0, 100 - climate) * DROUGHT_PER_1000

        wanted = days_for(standing, TEND_PER_DAY)
        got = min(days.get((actor, "tend"), 0), wanted)
        neglect = (wanted - got) * 1000 // wanted if wanted else 0

        # Order pinned: neglect is assessed against the standing crop, then the
        # weather against the same figure, and both are taken together. Applying
        # one to the remainder of the other would make the pair non-commutative
        # for no reason anybody could defend.
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
    """Cut and stack it, inside the window, or lose it where it stands.

    This is the year's labour peak and the point of the whole chain: hands that
    are somewhere else in these four fortnights are not hands that can be spared
    later, they are grain that does not exist.
    """
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

    # The deadline. What is still standing when the window shuts is not stored
    # somewhere for later; it is lost in the field, and the ledger says so.
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
    """Grain set aside as next year's seed: food chosen against.

    Takes no labour and so takes no grant -- the decision is the whole of it,
    and the decision was made from belief in the policy. What the actor asked
    for is capped here by grain it actually has, which is the ordinary case of
    an actor intending more than the world will support.
    """
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


def keep(kernel):
    """What stored goods lose to the weather, the rats, and the waiting.

    The rates are authored per good and come in on the Kernel, so a good with
    no rate does not spoil and nothing here decides which those are. Standing
    crop is one of them: a crop in the field is not badly stored, it is exposed,
    and what it loses is `tend`'s business by name rather than a rate.

    Flooring is deliberate and is inherited from the authored table's own
    reading of it: a small stock does not spoil at all, because a jar either
    turns or it does not. It also means a granary is not bounded by this alone
    -- it is bounded by the point where the loss overtakes the surplus, which is
    a real equilibrium rather than a cap.
    """
    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    for lot_id in sorted(book.lots):
        lot = book.lots.get(lot_id)
        if lot is None:
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
    """One lot id, inside this step's reserved ordinal block.

    The block is what keeps two steps minting at the same parent on the same
    turn -- threshed grain and the straw off the same floor -- from claiming one
    id. The index within it comes from a sorted position at the call site, never
    from the order a loop happened to run in.
    """
    return mint(parent, turn, "lot", BLOCKS[block] + index)
