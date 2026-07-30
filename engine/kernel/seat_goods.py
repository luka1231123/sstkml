"""The seat's stores, held in the Book (spec 2.2, 5.2, 6.2; Phase C row 1-3).

The court keeps one integer per good -- `Court.stores["grain"]` -- and that
integer is the only record of it. The kernel keeps lots, and a lot says four
things the integer cannot: whose it is, who has it, where it is, and how it got
there. `docs/PHASE_C_AUTHORITY.md` names the Book the authority for all three
of those facts, and this module is the seam that carries the court's figures
across without a unit going missing in the crossing.

The seam is a *view*, not a copy. `deposit` turns a flat mapping into lots;
`in_hand` reads lots back into a flat mapping. Round-tripping either way
returns what went in, including the goods the court counts none of -- a store
of zero says "the granary is empty and we count grain", which is not the same
statement as a good nobody in the world holds, and the Book cannot say the
first on its own because it drops empty lots. `SeatGoods.declared` is where
that survives.

Two readings, because the flat integer conflated them and this is the
capability Phase C buys:

`in_hand`  what the seat has in its own hands, whoever owns it
`owned`    what the seat owns at the seat, whoever holds it

They agree the moment goods are deposited and part company the first time
custody moves without ownership. A system that spends from the wrong one either
spends a temple's deposit or fails to spend its own grain, and nothing in a
flat mapping would have told it which.

`balance` is the proof obligation. Spec 2.2 requires

    opening + produced + imported + recovered
      = closing + consumed + exported + spoiled + destroyed

and the seam has to satisfy it under every Book operation -- split, merge,
reserve, release, give, hand, relocate -- because each of those is a way for a
seam to lose a quantity while both sides still look plausible. The identity is
computed from the transfer ledger, so a movement made without a record shows up
as an unexplained residual rather than as a balanced lie.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine import ownership as W
from engine.entity import EntityId, GoodId, mint, parse

# What a flat court figure is, as a reason. The court's stores came out of
# content, so `authored` is the honest source: nothing harvested them here, and
# claiming a harvest would put grain into a year's production that no field
# grew. The mark below is what keeps this distinguishable from the scenario's
# own opening stores.
REASON = "authored"

# How each sink lands in spec 2.2's identity. Closed and total over
# `ownership.SINKS`, because a sink this table does not name is a quantity the
# identity cannot place -- and an unplaceable quantity would surface as a
# residual, which is the signal reserved for a missing record.
SINK_TERMS: Mapping[str, str] = {
    "consumed": "consumed",
    "sown": "consumed",
    "expended": "consumed",
    "melted": "consumed",
    "spoiled": "spoiled",
    "lost": "destroyed",
    "died": "destroyed",
}


@dataclasses.dataclass(frozen=True)
class SeatGoods:
    """Which lots in the Book are the seat's stores, and what it counts.

    `declared` is every good the court keeps a figure for, in sorted order,
    including the ones it has none of. It is the only part of a flat mapping
    that lots cannot hold, so it is the only part this view has to carry.

    `lots` is what `deposit` minted, for an inspector that wants to start at
    the crossing rather than at a lot it happened to find.
    """
    seat: EntityId
    owner: EntityId
    holder: EntityId
    declared: tuple[GoodId, ...] = ()
    lots: tuple[EntityId, ...] = ()


@dataclasses.dataclass(frozen=True)
class Balance:
    """One good's accounts over one window, in spec 2.2's own terms."""
    good: GoodId
    opening: int = 0
    produced: int = 0
    imported: int = 0
    recovered: int = 0
    closing: int = 0
    consumed: int = 0
    exported: int = 0
    spoiled: int = 0
    destroyed: int = 0

    @property
    def unexplained(self) -> int:
        """The residual in spec 2.2's identity. Anything but zero is a defect.

        Not "the books disagree by this much": the closing stock is read off
        the lots and every other term off the ledger, so a residual means a
        quantity moved without leaving a record. That is a defect even when the
        arithmetic happens to come out (spec 10.8).
        """
        return ((self.opening + self.produced + self.imported + self.recovered)
                - (self.closing + self.consumed + self.exported
                   + self.spoiled + self.destroyed))


# --- crossing over ------------------------------------------------------------

def _taken(book: W.Book, seat: EntityId) -> frozenset[int]:
    """Lot ordinals already minted from this seat on this turn.

    Both the standing lots and this turn's transfers, because a lot emptied
    earlier in the turn has left `lots` while its record has not. Reusing its
    ordinal would give two different quantities of grain one identity, and the
    ledger would read as though the first had turned into the second.
    """
    prefix = f"{seat}/{book.turn}/lot/"
    seen = set()
    for lot_id in sorted(book.lots):
        seen.add(lot_id)
    for transfer in book.transfers:
        seen.add(transfer.lot)
    ordinals = set()
    for lot_id in sorted(seen):
        if lot_id.startswith(prefix):
            tail = lot_id[len(prefix):]
            if tail.isdigit():
                ordinals.add(int(tail))
    return frozenset(ordinals)


def deposit(book: W.Book, stores: Mapping[GoodId, int], *, seat: EntityId,
            owner: EntityId, holder: EntityId = "", quality: int = 1000,
            authority: EntityId = "") -> tuple[W.Book, SeatGoods]:
    """The court's flat figures become lots at the seat. One lot per good.

    Ids come from the goods in sorted order, offset past whatever the book has
    already minted from this seat this turn, so the seam can be applied to a
    loaded world rather than only to an empty book. A good the court counts
    none of still spends its ordinal: a granary that empties must not renumber
    the oil beside it, or every id downstream of it moves and the state hash
    with them (spec 2.6).
    """
    parse(seat)
    parse(owner)
    holder = holder or owner
    parse(holder)
    declared = tuple(sorted(stores))
    for good in declared:
        quantity = stores[good]
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise W.LedgerError(
                f"{good}: a store is an integer, not {quantity!r}")
        if quantity < 0:
            raise W.LedgerError(f"{good}: a store of {quantity} is not a store")

    taken = _taken(book, seat)
    base = max(taken) + 1 if taken else 0
    minted: list[EntityId] = []
    for offset, good in enumerate(declared):
        if stores[good] == 0:
            continue
        lot_id = mint(seat, book.turn, "lot", base + offset)
        book = book.create(
            lot_id, good, stores[good], owner=owner, holder=holder,
            location=seat, reason=REASON, quality=quality,
            authority=authority, marks=(mark(good, book.turn),))
        minted.append(lot_id)
    return book, SeatGoods(seat=seat, owner=owner, holder=holder,
                           declared=declared, lots=tuple(sorted(minted)))


def mark(good: GoodId, turn: int) -> str:
    """The provenance mark a lot that began life as a court figure carries.

    Named rather than inlined because it is what an inspector greps for. It is
    how "this grain was a number in a ledger before it was a lot" stays sayable
    after `Court.stores` is gone, and the answer to "where did this come from"
    for the oldest grain in the game is exactly that sentence.
    """
    return f"court_store:{good}@{turn}"


# --- reading back -------------------------------------------------------------

def in_hand(book: W.Book, view: SeatGoods, *,
            free_only: bool = False) -> dict[GoodId, int]:
    """What the seat holds at the seat, as the court's flat mapping.

    The inverse of `deposit`, and the reading the court's systems meant: rations
    are paid out of what is in the granary, not out of what the crown has a
    claim to somewhere else. `free_only` subtracts what is reserved against
    contracts, which is the figure a system about to spend should ask for --
    the whole quantity is what an inventory shows.
    """
    figures = {good: 0 for good in view.declared}
    for lot in book.at(view.seat):
        if lot.holder != view.holder:
            continue
        amount = lot.free if free_only else lot.quantity
        figures[lot.good] = figures.get(lot.good, 0) + amount
    return {good: figures[good] for good in sorted(figures)}


def owned(book: W.Book, view: SeatGoods) -> dict[GoodId, int]:
    """What the seat owns at the seat, whoever has hold of it.

    Scoped to the seat so that it differs from `in_hand` in exactly one respect
    -- owner against holder -- and the difference is readable. Grain the seat
    owns that is standing somewhere else entirely is `book.owned_by(owner)`,
    which is a different question and has a different answer.
    """
    figures = {good: 0 for good in view.declared}
    for lot in book.at(view.seat):
        if lot.owner != view.owner:
            continue
        figures[lot.good] = figures.get(lot.good, 0) + lot.quantity
    return {good: figures[good] for good in sorted(figures)}


def lots(book: W.Book, view: SeatGoods,
         good: GoodId = "") -> tuple[W.GoodsLot, ...]:
    """The seat's lots in id order. One good's, or all of them."""
    return tuple(lot for lot in book.at(view.seat)
                 if lot.holder == view.holder and good in ("", lot.good))


def reconcile(book: W.Book, view: SeatGoods,
              stores: Mapping[GoodId, int]) -> tuple[str, ...]:
    """Where the Book and a court mapping disagree, as sentences (spec 11.1).

    For the stretch where both records exist. The migration is sequenced in
    steps and other systems keep writing to `Court.stores` during them, so the
    two authorities overlap for a while; this is what makes that overlap a
    checkable state rather than a hope. It reports rather than raises, because
    a divergence is a finding for an audit and not an exception for a turn.
    """
    held = in_hand(book, view)
    found: list[str] = []
    for good in sorted(set(held) | set(stores)):
        if good not in held:
            found.append(f"{good}: the court counts {stores[good]}, "
                         f"the book has no such good at {view.seat}")
        elif good not in stores:
            found.append(f"{good}: the book holds {held[good]}, "
                         f"the court counts no {good} at all")
        elif held[good] != stores[good]:
            found.append(f"{good}: the court counts {stores[good]}, "
                         f"the book holds {held[good]}")
    return tuple(found)


# --- provenance ---------------------------------------------------------------

# The provenance marks that name another lot, and the prefix each uses. Reading
# them is how the trail walks backwards: the marks are the only link between a
# lot and the lots it came out of, since a split leaves no transfer joining the
# two halves after the turn's ledger is drained.
_ANCESTOR_PREFIXES = ("split:", "merged:", "from:")


def _ancestors(lot: W.GoodsLot) -> tuple[EntityId, ...]:
    found: list[EntityId] = []
    for mark_text in lot.provenance:
        for prefix in _ANCESTOR_PREFIXES:
            if mark_text.startswith(prefix):
                found.append(mark_text[len(prefix):].split("@")[0])
    return tuple(found)


def trail(book: W.Book, lot_id: EntityId, _seen: frozenset = frozenset(),
          _depth: int = 0) -> tuple[str, ...]:
    """"Where did this grain come from", answered for one lot (spec 5.2).

    The lot as it stands, every mark it carries, every transfer this turn that
    touched it, and then the same again for each lot it came out of that is
    still in the book. Earlier turns are not here and cannot be: the ledger is
    drained each turn into events and the archive, which is where a question
    about last year is asked. What survives in the book itself is the
    provenance, and a court figure's mark survives every split and merge, so
    the oldest line of the trail still says the grain was once a number.
    """
    lot = book.lots.get(lot_id)
    pad = "  " * _depth
    if lot is None:
        return (f"{pad}{lot_id}: no longer a lot in the book",)
    lines = [f"{pad}{lot_id}: {lot.quantity} {lot.good} at {lot.location}, "
             f"owned by {lot.owner}, held by {lot.holder}"]
    if lot.reserved:
        lines.append(f"{pad}  {lot.reserved} of it reserved")
    for mark_text in lot.provenance:
        lines.append(f"{pad}  mark {mark_text}")
    for transfer in book.transfers:
        if transfer.lot != lot_id:
            continue
        lines.append(
            f"{pad}  turn {transfer.turn} {transfer.phase}: "
            f"{transfer.reason} {transfer.quantity} "
            f"from {transfer.from_owner}/{transfer.from_holder} "
            f"to {transfer.to_owner}/{transfer.to_holder}"
            + (f" under {transfer.authority}" if transfer.authority else ""))
    seen = _seen | {lot_id}
    for ancestor in _ancestors(lot):
        if ancestor in seen:
            continue
        seen = seen | {ancestor}
        lines.extend(trail(book, ancestor, seen, _depth + 1))
    return tuple(lines)


# --- conservation -------------------------------------------------------------

def _place(book: W.Book, lot_id: EntityId) -> str:
    lot = book.lots.get(lot_id)
    return lot.location if lot is not None else ""


def _from_place(before: W.Book, after: W.Book, lot_id: EntityId) -> str:
    """Where a quantity was when it left. Before by preference, since that is
    the state the movement started from; after only for a lot that did not
    exist yet, which is a lot that was created inside the window."""
    return _place(before, lot_id) or _place(after, lot_id)


def _to_place(before: W.Book, after: W.Book, lot_id: EntityId) -> str:
    """Where it ended up. After by preference; before for a lot the window
    emptied, whose destination is wherever it was standing."""
    return _place(after, lot_id) or _place(before, lot_id)


def _totals(book: W.Book, view: SeatGoods, by: str) -> dict[GoodId, int]:
    party = view.holder if by == "holder" else view.owner
    totals: dict[GoodId, int] = {}
    for lot in book.at(view.seat):
        if getattr(lot, by) != party:
            continue
        totals[lot.good] = totals.get(lot.good, 0) + lot.quantity
    return totals


def balance(before: W.Book, after: W.Book, view: SeatGoods,
            by: str = "holder") -> dict[GoodId, Balance]:
    """Spec 2.2's identity for the seat, over one turn's transfers.

    `by` chooses which of the two readings is being audited. Under `holder`,
    handing grain to a ship's master is an export and selling it where it
    stands is not; under `owner` it is the other way round. Both identities
    hold at once over the same ledger, and that they do is the check that
    ownership and custody are genuinely separate rather than two names for one
    field (spec 5.2).

    Only transfers made since `before` count, and `before` must be a prefix of
    `after` -- the same rule as `ownership.conservation`, for the same reason.
    A window may not straddle a turn, because the ledger is drained on the
    turn's first phase stamp and the transfers that explained the change would
    be gone.

    `recovered` is always zero. No reason in `ownership.REASONS` means salvage;
    the term is here because spec 2.2 names it, and whoever adds a recovery
    reason has to classify it in `SINK_TERMS` or here, and will find this
    sentence when the residual tells them to look.
    """
    if by not in ("holder", "owner"):
        raise W.LedgerError(
            f"the seat is scoped by holder or owner, not {by!r}")
    prefix = len(before.transfers)
    if after.transfers[:prefix] != before.transfers:
        raise W.LedgerError("the later book did not grow out of the earlier one")
    since = after.transfers[prefix:]

    party = view.holder if by == "holder" else view.owner
    opening = _totals(before, view, by)
    closing = _totals(after, view, by)
    terms: dict[GoodId, dict[str, int]] = {}

    def add(good: GoodId, term: str, quantity: int) -> None:
        terms.setdefault(good, {})[term] = (
            terms.get(good, {}).get(term, 0) + quantity)

    for transfer in since:
        if by == "holder":
            came_from, went_to = transfer.from_holder, transfer.to_holder
        else:
            came_from, went_to = transfer.from_owner, transfer.to_owner
        left = (came_from == party
                and _from_place(before, after, transfer.lot) == view.seat)
        arrived = (went_to == party
                   and _to_place(before, after, transfer.lot) == view.seat)
        if transfer.reason in W.SOURCES:
            if arrived:
                add(transfer.good, "produced", transfer.quantity)
        elif transfer.reason in W.SINKS:
            if left:
                term = SINK_TERMS.get(transfer.reason)
                if term is None:
                    raise W.LedgerError(
                        f"{transfer.reason!r} is a sink the identity in spec "
                        f"2.2 has no term for")
                add(transfer.good, term, transfer.quantity)
        elif left and not arrived:
            add(transfer.good, "exported", transfer.quantity)
        elif arrived and not left:
            add(transfer.good, "imported", transfer.quantity)
        # Anything else moved within the seat's own scope: a split, a merge, a
        # reservation, a relocation that stayed at home. Those change the shape
        # of the store and not its size, so the identity must not see them.

    report: dict[GoodId, Balance] = {}
    for good in sorted(set(opening) | set(closing) | set(terms)):
        report[good] = Balance(
            good=good, opening=opening.get(good, 0),
            closing=closing.get(good, 0), **terms.get(good, {}))
    return report


def faults(before: W.Book, after: W.Book,
           view: SeatGoods) -> tuple[str, ...]:
    """Every way the seam failed over this window, as sentences (spec 11.1).

    Both readings, because a seam that conserves custody while inventing a
    claim has still broken spec 2.2, and the whole reason the Book holds two
    fields is that the two can be wrong independently.
    """
    found: list[str] = []
    for by in ("holder", "owner"):
        for good, accounts in sorted(balance(before, after, view, by).items()):
            if accounts.unexplained:
                found.append(
                    f"{view.seat}: {good} by {by} is short "
                    f"{accounts.unexplained} of the identity in spec 2.2")
    for good in sorted(view.declared):
        if good in in_hand(after, view):
            continue
        found.append(f"{view.seat}: {good} was declared and is not counted")
    return tuple(found)
