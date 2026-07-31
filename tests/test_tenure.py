"""Which granary a household may open (Task 2 C3, spec 5.3, 6.3).

Before tenure existed, every settlement in the world pooled its stock and fed
everyone standing in it. That is Egypt's arrangement, and imposing it on the
whole Bronze Age had one consequence worth more than the anachronism: a hungry
village beside a full palace granary was not a state the world could reach. The
arithmetic fed them.

What these pin is that the four arrangements differ in the one way that matters
-- whose grain a body of people may eat -- and that the household's share is a
real holding rather than a label: it can be eaten down to nothing, and the seed
corn inside it can be eaten too, which is the decision a village in a bad year
actually had.
"""
import dataclasses

import pytest

from engine.entity import TENURES, Cohort, Organization, Polity, Registry
from engine.entity import Settlement
from engine.kernel import farm as F
from engine.kernel.world import _food_owners
from load import load_scenario

SEED = 8814402919


def _kernel():
    """A world of one settlement: a council, and the people who live there."""
    from engine.core import Date

    from engine.kernel.world import Kernel
    from engine.ownership import Book

    registry = Registry(
        polities={"polity:p": Polity(id="polity:p", name="p", seat="settlement:s",
                                     tenure="subsistence")},
        settlements={"settlement:s": Settlement(
            id="settlement:s", name="s", region="region:r", polity="polity:p")},
        orgs={"org:council": Organization(
            id="org:council", name="council", settlement="settlement:s",
            kind="council", policy="subsistence")},
        cohorts={"cohort:folk": Cohort(
            id="cohort:folk", settlement="settlement:s", kind="field_labour",
            households=20, people=100)},
    )
    book = Book(turn=0)
    book = book.create("settlement:s/0/lot/1", F.GRAIN, 1000,
                       owner="org:council", holder="org:council",
                       location="settlement:s", reason="authored")
    book = book.create("settlement:s/0/lot/2", F.SEED, 500,
                       owner="org:council", holder="org:council",
                       location="settlement:s", reason="authored")
    return Kernel(seed=1, date=Date(year=1, fortnight=0, absolute=0),
                  registry=registry, book=book)


def _with_tenure(kernel, name: str):
    cohort = dataclasses.replace(kernel.registry.cohorts["cohort:folk"],
                                 tenure=name)
    registry = dataclasses.replace(
        kernel.registry, cohorts={cohort.id: cohort})
    return dataclasses.replace(kernel, registry=registry)


def test_the_four_tenures_open_four_different_doors():
    """The whole of the difference, stated once."""
    kernel = _kernel()
    folk = kernel.registry.cohorts["cohort:folk"]
    seen = {}
    for name in TENURES:
        seen[name] = _food_owners(_with_tenure(kernel, name),
                                  dataclasses.replace(folk, tenure=name))
    assert seen["subsistence"] == {"cohort:folk"}
    assert seen["redistributive"] == {"org:council"}
    assert seen["prebendal"] == {"org:council"}     # no origin authored
    assert seen["pooled"] == {"settlement:s", "org:council"}
    # Four arrangements, and not four names for one arrangement.
    assert len({frozenset(v) for v in seen.values()}) > 1


def test_a_cohort_answers_for_itself_before_its_polity():
    """One household inside a country that lives another way (the court's own)."""
    kernel = _kernel()
    folk = kernel.registry.cohorts["cohort:folk"]
    assert kernel.tenure_of(folk) == "subsistence"       # the polity's
    assert kernel.tenure_of(
        dataclasses.replace(folk, tenure="redistributive")) == "redistributive"


def test_a_prebendary_is_fed_by_the_house_it_serves_not_the_place_it_lives():
    kernel = _kernel()
    folk = dataclasses.replace(kernel.registry.cohorts["cohort:folk"],
                               tenure="prebendal", origin="org:temple")
    assert _food_owners(kernel, folk) == {"org:temple"}


def test_the_division_hands_over_grain_and_the_seed_corn_with_it():
    """Seed corn is the last food in the house, and it has to be theirs.

    A household holding grain but no seed would starve the fortnight its grain
    ran out, with next year's sowing safe in a store it may not open. No village
    ever lived under that rule, and `_consume` reaching for seed is the whole of
    the mechanism it would have broken.
    """
    kernel = _kernel()
    kernel, events = F.divide(kernel)
    held = {}
    for lot in kernel.book.lots.values():
        if lot.owner == "cohort:folk":
            held[lot.good] = held.get(lot.good, 0) + lot.quantity
    assert held.get(F.GRAIN, 0) == 1000 * F.HOUSEHOLD_SHARE_PER_1000 // 1000
    assert held.get(F.SEED, 0) == 500 * F.HOUSEHOLD_SHARE_PER_1000 // 1000
    assert {e[0] for e in events} == {"shared_out"}


def test_the_council_keeps_the_rest_and_the_people_cannot_touch_it():
    """The state the pooled store could not represent."""
    kernel = _kernel()
    kernel, _ = F.divide(kernel)
    folk = kernel.registry.cohorts["cohort:folk"]
    reachable = {lot.id for lot in
                 __import__("engine.kernel.world", fromlist=["x"])._local_food(
                     kernel, kernel.book, folk)}
    council = {lot.id for lot in kernel.book.lots.values()
               if lot.owner == "org:council"}
    assert council, "the council rendered everything and kept nothing"
    assert not (reachable & council), "the household opened the council's store"


def test_nothing_is_created_or_destroyed_by_dividing_it():
    """Spec 2.2. A division moves grain; it does not make any."""
    kernel = _kernel()
    before = {good: sum(lot.quantity for lot in kernel.book.lots.values()
                        if lot.good == good) for good in (F.GRAIN, F.SEED)}
    kernel, _ = F.divide(kernel)
    after = {good: sum(lot.quantity for lot in kernel.book.lots.values()
                       if lot.good == good) for good in (F.GRAIN, F.SEED)}
    assert before == after


def test_an_unknown_tenure_fails_to_load():
    """A typo in one authored word is not something to discover ten years in."""
    import load

    cfg = {"places": [], "sites": [], "regions": [],
           "tenure": {"default": "feudal"}}
    with pytest.raises(ValueError, match="unknown tenure"):
        load.mint_registry({}, (), cfg)


def test_the_authored_world_says_what_it_means_by_egypt():
    """The one claim this table exists to make."""
    kernel = load_scenario("ugarit", SEED).kernel
    assert kernel.registry.polities["polity:egypt"].tenure == "redistributive"
    for polity in kernel.registry.polities.values():
        assert polity.tenure in TENURES
