"""Writing the court's decisions back through the seam (Task 2 C2).

`in_hand` was half a seam: the systems could read the Book and had nowhere to
put the answer. What these pin is the half that closes it -- that a figure the
court arrives at lands on the lots without a unit going missing, that spending
draws the oldest grain first, and that a store spoken for cannot be spent by a
system that does not know it was.
"""
import pytest

from engine import ownership as W
from engine.kernel import seat_goods as SG

SEAT = "settlement:seat"
OWNER = "org:seat_palace"


def _opened(stores):
    return SG.deposit(W.Book(turn=0), stores, seat=SEAT, owner=OWNER)


def test_what_a_system_decides_is_what_the_book_then_holds():
    book, view = _opened({"grain": 1000, "oil": 40})
    book, view = SG.settle(book, view, {"grain": 700, "oil": 40})
    assert SG.in_hand(book, view) == {"grain": 700, "oil": 40}


def test_a_good_the_seat_never_had_can_arrive():
    """A harvest, a cargo, a smelt: the flat mapping simply grew a key."""
    book, view = _opened({"grain": 100})
    book, view = SG.settle(book, view, {"grain": 100, "tin": 20},
                           reason_up="produced")
    assert SG.in_hand(book, view)["tin"] == 20
    assert "tin" in view.declared


def test_spending_takes_the_oldest_grain_first():
    """Which lot goes is a fact the flat integer could not have.

    It decides whose grain was eaten and what provenance the remainder carries,
    and a granary that ate its newest delivery first would be a granary nobody
    has ever run.
    """
    book, view = _opened({"grain": 100})
    old = view.lots[0]
    book = book.create("settlement:seat/0/lot/9", "grain", 100, owner=OWNER,
                       holder=OWNER, location=SEAT, reason="harvested")
    book, view = SG.settle(book, view, {"grain": 150})
    assert book.lots[old].quantity == 50                        # drawn on
    assert book.lots["settlement:seat/0/lot/9"].quantity == 100  # untouched


def test_a_reserved_store_is_not_spendable():
    """The capability the migration is for.

    Grain promised against a letter is still in the granary, and under the flat
    mapping a system spending "what is there" spent it. Here it cannot, and it
    says so rather than quietly serving the wrong claimant.
    """
    book, view = _opened({"grain": 100})
    book = book.reserve(view.lots[0], 80, "letter:1")
    with pytest.raises(W.LedgerError):
        SG.settle(book, view, {"grain": 0})


def test_the_ledger_explains_every_unit_that_moved():
    """Spec 2.2's identity, over one settle. A residual is a missing record."""
    book, view = _opened({"grain": 1000})
    after, view = SG.settle(book, view, {"grain": 600}, reason_down="consumed")
    balance = SG.balance(book, after, view)["grain"]
    assert balance.consumed == 400
    assert balance.unexplained == 0


def test_a_negative_store_is_refused():
    book, view = _opened({"grain": 10})
    with pytest.raises(W.LedgerError):
        SG.settle(book, view, {"grain": -1})
