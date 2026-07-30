"""The grain year (spec 6.2, M13.2).

What is worth pinning here is not the numbers -- those are calibration and will
move -- but the claims the chain is built to make:

    the year has moments, and they are not interchangeable;
    every step conserves, and the ledger says where the losses went;
    seed is food, and eating it costs you the next harvest;
    the ground has an extent, so effort alone does not close a famine.

Each test below is one of those. Where a number appears it is because the claim
is quantitative -- that reaping is the year's labour peak is a statement about
rates, and a chain whose bottleneck drifted to threshing would still pass every
qualitative check while having quietly stopped modelling the thing it exists to
model.
"""
from __future__ import annotations

import dataclasses

from engine import ownership as W
from engine.kernel import farm as F
from engine.kernel import resolve as R
from engine.kernel import world as K
from load_kernel import load_kernel
from tests.test_kernel_world import landlocked

MAHADU = "settlement:mahadu"
ALASHIYA = "settlement:alashiya_port"
COUNCIL = "org:mahadu_council"
TEMPLE = "org:mahadu_temple"


def _to_fortnight(kernel: K.Kernel, fortnight: int, after: int = 0):
    """Advance to the next occurrence of a fortnight, past `after` turns."""
    for _ in range(after):
        kernel, _ = K.advance(kernel)
    while kernel.date.fortnight != fortnight:
        kernel, _ = K.advance(kernel)
        assert not K.faults(kernel), K.faults(kernel)
    return kernel


def _year(kernel: K.Kernel, turns: int = 24):
    events = []
    for _ in range(turns):
        kernel, produced = K.advance(kernel)
        events.extend(produced)
        assert not K.faults(kernel), K.faults(kernel)
    return kernel, events


# --- the year has moments -----------------------------------------------------

def test_each_task_happens_only_in_its_own_season() -> None:
    """The whole point of the chain. Field work is not a rate spread evenly.

    A year with no moments cannot be got wrong: moving labour costs the same
    whenever you move it. This is the test that says the moments exist.
    """
    kernel = load_kernel()
    seen: dict[str, set[int]] = {}
    for _ in range(24):
        kernel, events = K.advance(kernel)
        for event in events:
            if event[0] in ("sown", "reaped", "threshed"):
                seen.setdefault(event[0], set()).add(kernel.date.fortnight)

    assert seen["sown"] <= {19, 20, 21, 22}
    assert seen["reaped"] <= {8, 9, 10, 11}
    assert seen["threshed"] <= {12, 13}
    # And they are disjoint, which is what makes the harvest window a window.
    assert not seen["sown"] & seen["reaped"]
    assert not seen["reaped"] & seen["threshed"]


def test_nothing_is_sown_outside_the_sowing_season() -> None:
    """The gate is the season, not the presence of seed and hands."""
    kernel = _to_fortnight(load_kernel(), 15)      # low water: no field work
    assert not F.season(kernel.seasons, kernel.date.fortnight, "sowing")

    before = F.held(kernel.book, COUNCIL, F.SEED, MAHADU)
    assert before > 0, "it has seed in hand, and still does not sow it"
    kernel, events = K.advance(kernel)
    assert not any(e[0] == "sown" for e in events)


def test_reaping_is_the_years_labour_peak() -> None:
    """The claim the calibration exists to make.

    If cutting the crop were not the moment when hands run out, the harvest
    window would be a detail rather than a decision, and diverting labour would
    never cost a settlement its grain.
    """
    crop = 120_000
    demand = {task: F.days_for(crop, rate) for task, rate in (
        ("sow", F.SOW_PER_DAY * 7),      # sowing handles seed, not the crop it
        ("tend", F.TEND_PER_DAY),        # returns, so compare like with like
        ("reap", F.REAP_PER_DAY),
        ("thresh", F.THRESH_PER_DAY))}
    assert demand["reap"] == max(demand.values())
    assert demand["reap"] > demand["thresh"] > demand["tend"]


# --- everything conserves -----------------------------------------------------

def test_every_good_in_the_chain_is_conserved_across_a_full_year() -> None:
    """Seed, standing crop, sheaves, grain, and straw all account for themselves.

    Conservation per good is what makes the chain one quantity changing form
    rather than four stocks that happen to move together. A step that turned
    sheaves into grain without recording what the threshing floor took would
    balance the grain books and still be wrong.
    """
    kernel = load_kernel()
    for _ in range(24):
        before = dataclasses.replace(kernel.book, transfers=())
        kernel, _ = K.advance(kernel)
        report = W.conservation(before, kernel.book)
        for good in (F.GRAIN, F.SEED, F.STANDING, F.SHEAVES, F.FODDER):
            if good not in report:
                continue
            _sourced, _sunk, unexplained = report[good]
            assert unexplained == 0, (kernel.date.fortnight, good, report[good])


def test_the_losses_are_named_rather_than_rounded_away() -> None:
    """Every quantity that leaves has a reason the inspector can print."""
    kernel = load_kernel()
    reasons: set[str] = set()
    for _ in range(24):
        kernel, _ = K.advance(kernel)
        reasons |= {t.reason for t in kernel.book.transfers}

    assert "sown" in reasons, "seed leaves the world when it goes in the ground"
    assert "expended" in reasons, "and again at every conversion"
    assert "spoiled" in reasons, "what the weather and the store take"
    assert "consumed" in reasons, "and what the people eat"
    assert reasons <= W.REASONS, "nothing moves for an unregistered reason"


def test_threshing_does_not_return_all_of_what_was_cut() -> None:
    """A thousand qa of sheaves is not a thousand qa of bread."""
    kernel = _to_fortnight(load_kernel(), 11)
    sheaves = F.held(kernel.book, COUNCIL, F.SHEAVES, MAHADU)
    grain = F.held(kernel.book, COUNCIL, F.GRAIN, MAHADU)
    assert sheaves > 0

    kernel = _to_fortnight(kernel, 14)
    made = F.held(kernel.book, COUNCIL, F.GRAIN, MAHADU) - grain
    assert 0 < made < sheaves, "the floor and the wind take their share"
    assert F.held(kernel.book, COUNCIL, F.FODDER, MAHADU) > 0, "and straw is left"


# --- seed is food, and the ground has an extent -------------------------------

def test_a_settlement_that_eats_its_seed_sows_less_next_year() -> None:
    """The chain's sharpest consequence, and the reason seed is a separate good.

    Nothing forbids eating the seed corn. `_consume` reaches for it when the
    grain is gone, because households always have. The price is not paid then;
    it is paid at the sowing, and it is paid in the harvest after that.
    """
    # Just after the threshing: next year's seed is set aside and the sowing is
    # still five fortnights off. The gap is the whole of the test -- households
    # reach for the seed because it is there and the granary is not.
    kernel = _to_fortnight(load_kernel(), 14)
    seed = F.held(kernel.book, COUNCIL, F.SEED, MAHADU)
    assert seed > 0

    # Take the granary away and leave only the seed. The households will eat it,
    # because the alternative is starving beside it.
    stripped = kernel.book
    for lot in kernel.book.at(MAHADU):
        if lot.good == F.GRAIN and lot.owner == COUNCIL:
            stripped = stripped.consume(lot.id, lot.quantity, "lost")
    hungry = dataclasses.replace(kernel, book=stripped)

    hungry, events = _year(hungry, turns=10)      # through the sowing season
    assert any(e[0] == "ate_the_seed" for e in events), "they ate it"

    fed, _ = _year(kernel, turns=10)              # the same ten, granary intact
    site = kernel.field_site(MAHADU, COUNCIL)
    assert (F.held(hungry.book, COUNCIL, F.STANDING, site)
            < F.held(fed.book, COUNCIL, F.STANDING, site)), \
        "and there is less in the ground for it"


def test_the_ground_bounds_the_sowing_however_much_seed_there_is() -> None:
    """Effort does not close a famine. Land does, and there is only so much.

    This is the constraint that makes M13.2's ships necessary rather than
    decorative: a settlement short of grain cannot decide its way out locally.
    """
    kernel = _to_fortnight(load_kernel(), 18)
    site = kernel.registry.sites[kernel.field_site(MAHADU, COUNCIL)]

    # Ten times the seed it could possibly need, and nothing else changed.
    book = kernel.book.create(
        "settlement:mahadu/0/lot/900", F.SEED, site.extent * 10,
        owner=COUNCIL, holder=COUNCIL, location=MAHADU, reason="authored")
    rich = dataclasses.replace(kernel, book=book)

    rich, _ = _year(rich, turns=5)                # across the sowing window
    sown = F.under_crop(rich, site.id)
    assert sown <= site.extent, (sown, site.extent)


def test_the_god_s_land_and_the_towns_are_different_ground() -> None:
    """They compete for hands, not for furrows."""
    kernel = load_kernel()
    fields = kernel.field_site(MAHADU, COUNCIL)
    gods = kernel.field_site(MAHADU, TEMPLE)
    assert fields != gods
    assert kernel.registry.sites[fields].holder == COUNCIL
    assert kernel.registry.sites[gods].holder == TEMPLE

    # Each crop stands on its holder's ground and belongs to its holder.
    for site_id, holder in ((fields, COUNCIL), (gods, TEMPLE)):
        standing = [lot for lot in kernel.book.at(site_id)
                    if lot.good == F.STANDING]
        assert standing and all(lot.owner == holder for lot in standing)


# --- the weather --------------------------------------------------------------

def test_a_dry_year_takes_a_share_of_the_crop_and_a_wet_one_does_not() -> None:
    """Weather reaches the harvest, and reaches it through the standing crop.

    Authored as a season named `climate` rather than a top-level key, the
    series is silently ignored and every year of the world is identical. That
    is how it stood until M13.2, so this test checks the effect rather than the
    table: a run whose weather never varies fails it.
    """
    kernel = load_kernel()
    assert len(kernel.climate) >= 24, "more than one year of weather is authored"
    assert len(set(kernel.climate)) > 1, "and the years are not all the same"

    harvests = []
    for _ in range(4):
        kernel = _to_fortnight(kernel, 7)
        before = F.held(kernel.book, COUNCIL, F.STANDING,
                        kernel.field_site(MAHADU, COUNCIL))
        kernel = _to_fortnight(kernel, 14)
        harvests.append(before)

    assert len(set(harvests)) > 1, "the years differ in what stood in the field"


def test_an_untended_crop_is_lost_to_neglect() -> None:
    """Hands in the winter are not free either -- they are just cheaper."""
    kernel = _to_fortnight(load_kernel(), 1)      # growing
    site = kernel.field_site(MAHADU, COUNCIL)
    standing = F.held(kernel.book, COUNCIL, F.STANDING, site)

    # Nobody tends anything: no grants at all, which is what a settlement whose
    # hands are all somewhere else looks like to this phase.
    idle, events = F.tend(kernel, (), R.Allocation())
    assert any(e[0] == "withered" for e in events)
    assert F.held(idle.book, COUNCIL, F.STANDING, site) < standing


# --- the gate this has to keep ------------------------------------------------

def test_the_island_still_cannot_feed_itself_and_nothing_local_fixes_it() -> None:
    """Spec 11.2 scenario 1, and M13.2's reason for existing.

    Worked perfectly, in the best year on the calendar, the Alashiyan estate
    returns something over half of what the port eats. That gap is not a
    balance mistake to be tuned out: it is the statement that trade is
    necessary, made in the only place the world can make it.

    The first half of the claim is about the ground and is asked of the authored
    world unchanged -- no crossing alters how much an estate can grow. The
    second half is asked with the routes cut, because M13.2 answered it: the
    fix is real, and it is not local.
    """
    kernel = load_kernel()
    site = kernel.registry.sites[kernel.field_site(ALASHIYA, "org:alashiya_council")]
    best = max(kernel.climate)
    potential = site.extent * site.capacity // 1000 * F.GRAIN_PER_1000 // 1000
    eaten = sum(c.ration() for c in kernel.cohorts_of(ALASHIYA)) * 24

    assert best >= 100, "there is at least one ordinary year to fail in"
    assert potential < eaten, (potential, eaten)

    kernel, _ = _year(landlocked(kernel), turns=40)
    thin = kernel.registry.cohorts["cohort:alashiya_fields"]
    assert thin.hunger > 0 and thin.grievance > 0
    assert kernel.people(ALASHIYA) < 500, "the shortfall reached the people"
    assert kernel.people(MAHADU) > 500, "and the port that could feed itself did not"
