"""Goods, ownership, and custody (spec 5.4, 10.8).

A `GoodsLot` is the only place a quantity of a good exists. Two fields carry
the distinction the rest of the economy is built on:

`owner`  whose it is
`holder` who has it

They differ constantly and neither implies the other. Grain on deposit belongs
to a household and is held by a temple. Cargo under sail belongs to a merchant
house and is held by a ship's master. A contract moves ownership; loading moves
custody. A system that changes one and assumes the other has just invented or
destroyed a claim.

Every change passes through this module and leaves a `Transfer`. That record --
not the arithmetic inside any system -- is what conservation checking and the
causal inspector read. Goods entering the world (a harvest) and leaving it
(eaten, spoiled) are transfers too, from and to the reserved endpoint `WORLD`,
so that "where did this quantity go" always has an answer.

The `Book` here holds one turn's lots and that turn's transfers. The tick
drains the transfer ledger each turn into events and the archive; it is not an
ever-growing log inside World.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from engine.entity import BadId, EntityId, GoodId, parse

# The endpoint on the far side of a source or a sink. Not an entity: it is the
# admission that production and consumption cross the boundary of the model.
WORLD: EntityId = "world:outside"

# Why a quantity moved. Closed, because an unregistered reason is a transfer
# the audit cannot classify as source, sink, or circulation.
SOURCES = frozenset({"harvested", "produced", "mined", "born", "captured",
                     "authored"})
SINKS = frozenset({"consumed", "spoiled", "sown", "melted", "expended",
                   "lost", "died"})
MOVES = frozenset({"sold", "paid", "delivered", "levied", "gifted", "lent",
                   "repaid", "seized", "loaded", "unloaded", "carried",
                   "stored", "split", "merged", "reserved", "released"})
REASONS = SOURCES | SINKS | MOVES


class LedgerError(ValueError):
    """A change that would break conservation, custody, or existence."""


@dataclasses.dataclass(frozen=True)
class GoodsLot:
    id: EntityId
    good: GoodId
    quantity: int                # in the good's declared unit, never negative
    owner: EntityId
    holder: EntityId
    location: EntityId
    quality: int = 1000          # scaled band, 1000 = ordinary
    reserved: int = 0            # committed to contracts, never above quantity
    provenance: tuple[str, ...] = ()

    @property
    def free(self) -> int:
        return self.quantity - self.reserved


@dataclasses.dataclass(frozen=True)
class Transfer:
    """One movement of a quantity. The unit of causal explanation."""
    turn: int
    phase: str
    lot: EntityId
    good: GoodId
    quantity: int
    from_owner: EntityId
    to_owner: EntityId
    from_holder: EntityId
    to_holder: EntityId
    reason: str
    authority: EntityId = ""     # the office or obligation relied on


@dataclasses.dataclass(frozen=True)
class Book:
    """The turn's lots and the turn's transfers."""
    lots: Mapping[EntityId, GoodsLot] = dataclasses.field(default_factory=dict)
    transfers: tuple[Transfer, ...] = ()
    turn: int = 0
    phase: str = ""

    # --- reading ------------------------------------------------------------

    def at(self, location: EntityId) -> tuple[GoodsLot, ...]:
        return tuple(self.lots[i] for i in sorted(self.lots)
                     if self.lots[i].location == location)

    def owned_by(self, owner: EntityId) -> tuple[GoodsLot, ...]:
        return tuple(self.lots[i] for i in sorted(self.lots)
                     if self.lots[i].owner == owner)

    def total(self, good: GoodId) -> int:
        return sum(lot.quantity for lot in self.lots.values()
                   if lot.good == good)

    def goods(self) -> tuple[GoodId, ...]:
        return tuple(sorted({lot.good for lot in self.lots.values()}))

    # --- internals ----------------------------------------------------------

    def _require(self, lot_id: EntityId) -> GoodsLot:
        if lot_id not in self.lots:
            raise LedgerError(f"no such lot: {lot_id!r}")
        return self.lots[lot_id]

    def _with(self, lots: dict, transfer: Transfer | None) -> "Book":
        # A lot emptied by the change it just underwent leaves; its history
        # rides along in the provenance of whatever received the goods.
        lots = {i: lot for i, lot in lots.items() if lot.quantity > 0}
        return dataclasses.replace(
            self, lots=lots,
            transfers=self.transfers + ((transfer,) if transfer else ()))

    def _record(self, lot: GoodsLot, quantity: int, reason: str,
                to_owner: EntityId, to_holder: EntityId,
                authority: EntityId, from_owner: EntityId | None = None,
                from_holder: EntityId | None = None) -> Transfer:
        if reason not in REASONS:
            raise LedgerError(f"unregistered transfer reason: {reason!r}")
        return Transfer(
            turn=self.turn, phase=self.phase, lot=lot.id, good=lot.good,
            quantity=quantity,
            from_owner=lot.owner if from_owner is None else from_owner,
            to_owner=to_owner,
            from_holder=lot.holder if from_holder is None else from_holder,
            to_holder=to_holder, reason=reason, authority=authority)

    def at_phase(self, turn: int, phase: str) -> "Book":
        """Stamp subsequent transfers, and drop the previous turn's ledger."""
        drained = self.transfers if turn == self.turn else ()
        return dataclasses.replace(
            self, turn=turn, phase=phase, transfers=drained)

    def drain(self) -> tuple["Book", tuple[Transfer, ...]]:
        return dataclasses.replace(self, transfers=()), self.transfers

    # --- writing ------------------------------------------------------------

    def create(self, lot_id: EntityId, good: GoodId, quantity: int,
               owner: EntityId, holder: EntityId, location: EntityId,
               reason: str, quality: int = 1000,
               authority: EntityId = "") -> "Book":
        """Goods enter the world: a harvest, a smelt, a scenario's opening store."""
        if reason not in SOURCES:
            raise LedgerError(f"{reason!r} does not bring goods into the world")
        if quantity <= 0:
            raise LedgerError("a lot is created with a positive quantity")
        if lot_id in self.lots:
            raise LedgerError(f"lot already exists: {lot_id!r}")
        parse(lot_id)
        lot = GoodsLot(id=lot_id, good=good, quantity=quantity, owner=owner,
                       holder=holder, location=location, quality=quality,
                       provenance=(f"{reason}@{self.turn}",))
        lots = dict(self.lots)
        lots[lot_id] = lot
        return self._with(lots, self._record(
            lot, quantity, reason, owner, holder, authority,
            from_owner=WORLD, from_holder=WORLD))

    def consume(self, lot_id: EntityId, quantity: int, reason: str,
                authority: EntityId = "") -> "Book":
        """Goods leave the world: eaten, sown, spoiled, melted, lost."""
        if reason not in SINKS:
            raise LedgerError(f"{reason!r} does not take goods out of the world")
        lot = self._require(lot_id)
        if quantity <= 0:
            raise LedgerError("consume needs a positive quantity")
        if quantity > lot.free:
            raise LedgerError(
                f"{lot_id}: {quantity} exceeds the {lot.free} not reserved")
        lots = dict(self.lots)
        lots[lot_id] = dataclasses.replace(lot, quantity=lot.quantity - quantity)
        return self._with(lots, self._record(
            lot, quantity, reason, WORLD, WORLD, authority))

    def split(self, lot_id: EntityId, quantity: int,
              new_id: EntityId) -> "Book":
        """Take part of a lot into a lot of its own. Conserves and copies history."""
        lot = self._require(lot_id)
        if new_id in self.lots:
            raise LedgerError(f"lot already exists: {new_id!r}")
        parse(new_id)
        if quantity <= 0 or quantity > lot.free:
            raise LedgerError(
                f"{lot_id}: cannot split {quantity} of {lot.free} free")
        lots = dict(self.lots)
        lots[lot_id] = dataclasses.replace(lot, quantity=lot.quantity - quantity)
        lots[new_id] = dataclasses.replace(
            lot, id=new_id, quantity=quantity, reserved=0,
            provenance=lot.provenance + (f"split:{lot_id}@{self.turn}",))
        return self._with(lots, self._record(
            lots[new_id], quantity, "split", lot.owner, lot.holder, ""))

    def merge(self, into_id: EntityId, lot_id: EntityId) -> "Book":
        """Fold one lot into another. Everything that identifies them must match."""
        into, lot = self._require(into_id), self._require(lot_id)
        if into_id == lot_id:
            raise LedgerError("a lot does not merge with itself")
        for field in ("good", "quality", "owner", "holder", "location"):
            if getattr(into, field) != getattr(lot, field):
                raise LedgerError(
                    f"cannot merge {lot_id} into {into_id}: {field} differs")
        if lot.reserved:
            raise LedgerError(f"{lot_id} is reserved and cannot be merged away")
        lots = dict(self.lots)
        lots[into_id] = dataclasses.replace(
            into, quantity=into.quantity + lot.quantity,
            provenance=into.provenance + lot.provenance)
        lots[lot_id] = dataclasses.replace(lot, quantity=0)
        return self._with(lots, self._record(
            lot, lot.quantity, "merged", into.owner, into.holder, ""))

    def give(self, lot_id: EntityId, quantity: int, to_owner: EntityId,
             reason: str, authority: EntityId = "",
             new_id: EntityId | None = None) -> "Book":
        """Ownership moves. Custody does not, unless something else moves it."""
        lot = self._require(lot_id)
        if reason not in MOVES:
            raise LedgerError(f"{reason!r} is not an ownership move")
        if quantity <= 0 or quantity > lot.free:
            raise LedgerError(
                f"{lot_id}: cannot give {quantity} of {lot.free} free")
        if to_owner == lot.owner:
            raise LedgerError(f"{lot_id} is already owned by {to_owner!r}")
        book = self
        target = lot_id
        if quantity < lot.quantity:
            if new_id is None:
                raise LedgerError("a partial give needs a new_id for the part")
            book = book.split(lot_id, quantity, new_id)
            target = new_id
        moved = book._require(target)
        lots = dict(book.lots)
        lots[target] = dataclasses.replace(moved, owner=to_owner)
        return book._with(lots, book._record(
            moved, quantity, reason, to_owner, moved.holder, authority))

    def hand(self, lot_id: EntityId, to_holder: EntityId, reason: str,
             authority: EntityId = "") -> "Book":
        """Custody moves. Ownership does not."""
        lot = self._require(lot_id)
        if reason not in MOVES:
            raise LedgerError(f"{reason!r} is not a custody move")
        if to_holder == lot.holder:
            raise LedgerError(f"{lot_id} is already held by {to_holder!r}")
        lots = dict(self.lots)
        lots[lot_id] = dataclasses.replace(lot, holder=to_holder)
        return self._with(lots, self._record(
            lot, lot.quantity, reason, lot.owner, to_holder, authority))

    def relocate(self, lot_id: EntityId, location: EntityId, reason: str,
                 authority: EntityId = "") -> "Book":
        """The goods are somewhere else now. Whose and whose-hands are unchanged."""
        lot = self._require(lot_id)
        if reason not in MOVES:
            raise LedgerError(f"{reason!r} is not a movement")
        lots = dict(self.lots)
        lots[lot_id] = dataclasses.replace(lot, location=location)
        return self._with(lots, self._record(
            lot, lot.quantity, reason, lot.owner, lot.holder, authority))

    def reserve(self, lot_id: EntityId, quantity: int,
                authority: EntityId = "") -> "Book":
        lot = self._require(lot_id)
        if quantity <= 0 or quantity > lot.free:
            raise LedgerError(
                f"{lot_id}: cannot reserve {quantity} of {lot.free} free")
        lots = dict(self.lots)
        lots[lot_id] = dataclasses.replace(lot, reserved=lot.reserved + quantity)
        return self._with(lots, self._record(
            lot, quantity, "reserved", lot.owner, lot.holder, authority))

    def release(self, lot_id: EntityId, quantity: int,
                authority: EntityId = "") -> "Book":
        lot = self._require(lot_id)
        if quantity <= 0 or quantity > lot.reserved:
            raise LedgerError(
                f"{lot_id}: cannot release {quantity} of {lot.reserved} reserved")
        lots = dict(self.lots)
        lots[lot_id] = dataclasses.replace(lot, reserved=lot.reserved - quantity)
        return self._with(lots, self._record(
            lot, quantity, "released", lot.owner, lot.holder, authority))


# --- checking -----------------------------------------------------------------

def faults(book: Book, exists=lambda entity_id: True) -> tuple[str, ...]:
    """Everything wrong with the book, as sentences (spec 11.1)."""
    found: list[str] = []
    for lot_id in sorted(book.lots):
        lot = book.lots[lot_id]
        if lot.quantity < 0:
            found.append(f"{lot_id}: negative quantity {lot.quantity}")
        if lot.reserved < 0 or lot.reserved > lot.quantity:
            found.append(
                f"{lot_id}: {lot.reserved} reserved of {lot.quantity}")
        for field in ("owner", "holder", "location"):
            value = getattr(lot, field)
            if value != WORLD and not exists(value):
                found.append(
                    f"{lot_id}: {field} names {value!r}, which does not exist")
        try:
            parse(lot_id)
        except BadId as exc:
            found.append(f"{lot_id}: {exc}")
    return tuple(found)


def conservation(before: Book, after: Book) -> dict[GoodId, tuple[int, int, int]]:
    """Per good: `(sourced, sunk, unexplained)` over `after`'s transfer ledger.

    `unexplained` is the residual after the ledger is asked to account for the
    change in world total. It must be zero. Anything else means a system moved
    a quantity without leaving a record, which is a defect even when the books
    happen to balance (spec 10.8).

    Only the transfers made *since* `before` are counted. The ledger is
    append-only within a turn, so `before`'s own transfers are its prefix --
    counting them again would charge the opening state against the change.
    """
    prefix = len(before.transfers)
    if after.transfers[:prefix] != before.transfers:
        raise LedgerError("the later book did not grow out of the earlier one")
    since = after.transfers[prefix:]

    report: dict[GoodId, tuple[int, int, int]] = {}
    goods = sorted(set(before.goods()) | set(after.goods()))
    for good in goods:
        sourced = sum(t.quantity for t in since
                      if t.good == good and t.reason in SOURCES)
        sunk = sum(t.quantity for t in since
                   if t.good == good and t.reason in SINKS)
        delta = after.total(good) - before.total(good)
        report[good] = (sourced, sunk, delta - (sourced - sunk))
    return report
