"""The crown's direct bargains with cargo already counted at its quay."""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.entity import mint
from engine.kernel import carry, farm


def _next_lot(book, seat: str) -> str:
    ordinal = 9000
    while mint(seat, book.turn, "lot", ordinal) in book.lots:
        ordinal += 1
    return mint(seat, book.turn, "lot", ordinal)


def _give(book, lot_id: str, quantity: int, owner: str, reason: str,
          authority: str, seat: str):
    lot = book.lots[lot_id]
    new_id = None if quantity == lot.quantity else _next_lot(book, seat)
    book = book.give(
        lot_id, quantity, owner, reason, authority, new_id=new_id)
    moved = new_id or lot_id
    if book.lots[moved].holder != owner:
        book = book.hand(moved, owner, reason, authority)
    return book


def _available(book, seat: str, good: str, owner: str = "",
               *, exclude: str = ""):
    return tuple(
        lot for lot in book.at(seat)
        if lot.good == good and lot.free
        and (not owner or lot.owner == owner)
        and (not exclude or lot.owner != exclude)
    )


def _finance(world, action: A.FinanceTrade):
    """Spend at most this much copper on reported grain cargo."""
    if action.good != carry.COPPER:
        raise ValueError("grain trade is financed with copper")
    if action.quantity <= 0:
        raise ValueError("a trade purse must be positive")

    seat = f"settlement:{world.chosen_alu}"
    crown = world.kernel.controller(seat)
    book = world.kernel.book
    purse = sum(lot.free for lot in _available(
        book, seat, carry.COPPER, crown))
    if purse < action.quantity:
        raise ValueError(f"only {purse} copper is available")

    cargo = _available(book, seat, farm.GRAIN, exclude=crown)
    available = sum(lot.free for lot in cargo)
    if available <= 0:
        raise ValueError("no grain cargo is available at the quay")
    price = max(1, carry.readings(world.kernel, seat)["price_grain"])
    bought = min(available, action.quantity * 1000 // price)
    if bought <= 0:
        raise ValueError("that purse will not buy even one qa of grain")

    moved = 0
    paid = 0
    for lot in cargo:
        if moved >= bought:
            break
        quantity = min(bought - moved, lot.free)
        seller = lot.owner
        payment = ((moved + quantity) * price + 999) // 1000 - paid
        book = _give(book, lot.id, quantity, crown, "sold", crown, seat)
        if payment:
            left = payment
            for copper in _available(book, seat, carry.COPPER, crown):
                take = min(left, copper.free)
                book = _give(
                    book, copper.id, take, seller, "paid", crown, seat)
                left -= take
                if not left:
                    break
        moved += quantity
        paid += payment

    kernel = dataclasses.replace(world.kernel, book=book)
    return (dataclasses.replace(world, kernel=kernel),
            [A.TradeFinanced(carry.COPPER, paid, farm.GRAIN, moved)])


def _requisition(world, action: A.RequisitionTrade):
    """Take visible cargo, with a public-order cost proportional to its value."""
    if action.quantity <= 0:
        raise ValueError("a requisition must be positive")
    seat = f"settlement:{world.chosen_alu}"
    crown = world.kernel.controller(seat)
    book = world.kernel.book
    cargo = _available(book, seat, action.good, exclude=crown)
    available = sum(lot.free for lot in cargo)
    if available < action.quantity:
        raise ValueError(f"only {available} {action.good} is available")

    left = action.quantity
    for lot in cargo:
        take = min(left, lot.free)
        book = _give(book, lot.id, take, crown, "seized", crown, seat)
        left -= take
        if not left:
            break

    price = (carry.readings(world.kernel, seat)["price_grain"]
             if action.good == farm.GRAIN else 1000)
    value = action.quantity * price // 1000
    unrest = max(5, min(200, value // 50))
    court = dataclasses.replace(
        world.court, unrest=min(1000, world.court.unrest + unrest))
    actual = court.unrest - world.court.unrest
    kernel = dataclasses.replace(world.kernel, book=book)
    events = [A.TradeRequisitioned(action.good, action.quantity)]
    if actual:
        events.append(A.UnrestChanged(actual, "the requisitioned cargo"))
    return dataclasses.replace(world, court=court, kernel=kernel), events


def apply(world, action):
    if isinstance(action, A.FinanceTrade):
        return _finance(world, action)
    if isinstance(action, A.RequisitionTrade):
        return _requisition(world, action)
    raise TypeError(f"not a trade policy action: {type(action).__name__}")
