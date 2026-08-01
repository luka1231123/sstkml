"""The seat's stores, held in the Book (spec 2.2, 5.2, 6.2; Phase C row 1-3)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine import ownership as W
from engine.entity import EntityId, GoodId, mint, parse

# What a flat court figure is, as a reason.
REASON = "authored"

# How each sink lands in spec 2.2's identity.
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
    """Which lots in the Book are the seat's stores, and what it counts."""
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
        """The residual in spec 2.2's identity."""
        return ((self.opening + self.produced + self.imported + self.recovered)
                - (self.closing + self.consumed + self.exported
                   + self.spoiled + self.destroyed))


# --- crossing over ------------------------------------------------------------

def _taken(book: W.Book, seat: EntityId) -> frozenset[int]:
    """Lot ordinals already minted from this seat on this turn."""
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
    """The court's flat figures become lots at the seat."""
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
    """The provenance mark a lot that began life as a court figure carries."""
    return f"court_store:{good}@{turn}"


# --- reading back -------------------------------------------------------------

def in_hand(book: W.Book, view: SeatGoods, *,
            free_only: bool = False) -> dict[GoodId, int]:
    """What the seat holds at the seat, as the court's flat mapping."""
    figures = {good: 0 for good in view.declared}
    for lot in book.at(view.seat):
        if lot.holder != view.holder:
            continue
        amount = lot.free if free_only else lot.quantity
        figures[lot.good] = figures.get(lot.good, 0) + amount
    return {good: figures[good] for good in sorted(figures)}


def owned(book: W.Book, view: SeatGoods) -> dict[GoodId, int]:
    """What the seat owns at the seat, whoever has hold of it."""
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
    """Where the Book and a court mapping disagree, as sentences (spec 11.1)."""
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


def settle(book: W.Book, view: SeatGoods, stores: Mapping[GoodId, int], *,
           reason_down: str = "consumed", reason_up: str = "authored",
           authority: EntityId = "") -> tuple[W.Book, SeatGoods]:
    """Make the Book say what a system decided, good by good."""
    if reason_up not in W.SOURCES:
        raise W.LedgerError(f"{reason_up!r} does not bring goods into the world")
    held = in_hand(book, view)
    taken = _taken(book, view.seat)
    next_ordinal = max(taken) + 1 if taken else 0
    for good in sorted(set(held) | set(stores)):
        want = int(stores.get(good, 0))
        if want < 0:
            raise W.LedgerError(f"{good}: a store of {want} is not a store")
        delta = want - held.get(good, 0)
        if delta < 0:
            owed = -delta
            for lot in lots(book, view, good):
                if owed <= 0:
                    break
                spend = min(owed, lot.free)
                if spend <= 0:
                    continue
                book = book.consume(lot.id, spend, reason_down,
                                    authority=authority)
                owed -= spend
            if owed:
                raise W.LedgerError(
                    f"{good}: {owed} short of what the seat can spend")
        elif delta > 0:
            lot_id = mint(view.seat, book.turn, "lot", next_ordinal)
            next_ordinal += 1
            book = book.create(
                lot_id, good, delta, owner=view.owner, holder=view.holder,
                location=view.seat, reason=reason_up, authority=authority,
                marks=(mark(good, book.turn),))
    declared = tuple(sorted(set(view.declared) | set(stores)))
    return book, dataclasses.replace(view, declared=declared)


# --- provenance ---------------------------------------------------------------

# The provenance marks that name another lot, and the prefix each uses.
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
    """"Where did this grain come from", answered for one lot (spec 5.2)."""
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
    """Where a quantity was when it left."""
    return _place(before, lot_id) or _place(after, lot_id)


def _to_place(before: W.Book, after: W.Book, lot_id: EntityId) -> str:
    """Where it ended up."""
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
    """Spec 2.2's identity for the seat, over one turn's transfers."""
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
        # Anything else moved within the seat's own scope: split, merge, reservation.

    report: dict[GoodId, Balance] = {}
    for good in sorted(set(opening) | set(closing) | set(terms)):
        report[good] = Balance(
            good=good, opening=opening.get(good, 0),
            closing=closing.get(good, 0), **terms.get(good, {}))
    return report


def faults(before: W.Book, after: W.Book,
           view: SeatGoods) -> tuple[str, ...]:
    """Every way the seam failed over this window, as sentences (spec 11.1)."""
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
