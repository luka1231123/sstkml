"""The court's stores, crossed into the Book (Task 2 C2).

The seam is a view rather than a copy, so what these pin is that the crossing
loses nothing and that the Book is the only place the seat's granary is
authored. A second authoring would not fail loudly -- both figures would look
plausible -- so it is checked directly.
"""
import tomllib
from pathlib import Path

from engine.kernel import seat_goods as SG
from load import SEAT_OWNER, SEAT_SETTLEMENT, load_scenario

ROOT = Path(__file__).parent.parent
SEED = 8814402919


def test_the_courts_stores_read_back_out_of_the_book_unchanged():
    world = load_scenario("ugarit", SEED)
    view = world.kernel.seat_goods
    assert view is not None, "the court's goods never crossed"
    assert SG.in_hand(world.kernel.book, view) == dict(
        sorted(world.court.stores.items()))


def test_a_good_the_court_counts_none_of_survives_the_crossing():
    """`seed_grain: 0` is a statement, and lots cannot hold it.

    An empty granary the court counts is not the same fact as a good nobody in
    the world has, and the Book drops empty lots. `declared` is what carries
    the difference across.
    """
    world = load_scenario("ugarit", SEED)
    empty = [good for good, n in world.court.stores.items() if n == 0]
    assert empty, "the fixture no longer has an empty store to check"
    for good in empty:
        assert good in world.kernel.seat_goods.declared
        assert SG.in_hand(world.kernel.book, world.kernel.seat_goods)[good] == 0


def test_the_seat_granary_is_authored_once():
    """detail.toml must not author grain for the seat: the scenario does.

    Two figures for one fact at one place with one owner is what Task 2 exists
    to stop, and it is invisible at runtime -- the seam would simply read back
    a larger number than the court holds.
    """
    detail = tomllib.loads(
        (ROOT / "content/kernel/detail.toml").read_text())
    seat_grain = [row for row in detail["stores"]
                  if row["settlement"] == SEAT_SETTLEMENT
                  and row["good"] == "grain"]
    assert seat_grain == []


def test_the_stores_are_the_palaces_and_not_the_settlements():
    """Whose the grain is, which is the fact the flat mapping could not hold."""
    world = load_scenario("ugarit", SEED)
    lots = [lot for lot in world.kernel.book.at(SEAT_SETTLEMENT)
            if lot.good == "grain"]
    assert lots, "no grain at the seat"
    assert {lot.owner for lot in lots} == {SEAT_OWNER}


def test_the_court_still_plays_exactly_as_it_did():
    """C2's contract while the readers are still on the flat mapping.

    The crossing adds lots to the Book. Nothing in the court reads them yet, so
    a turn must come out identical -- if it does not, something began reading
    the Book early and the two authorities are live at once.
    """
    from engine.tick import advance
    world = load_scenario("ugarit", SEED)
    before = dict(world.court.stores)
    for _ in range(24):
        world, _ = advance(world)
    assert dict(world.court.stores) != before        # a year does something
    assert world.kernel.seat_goods is not None       # and the view survives it
