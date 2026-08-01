import dataclasses

from engine import actions as A
from engine.entity import mint


def apply(world, action):
    seat = f"settlement:{world.chosen_alu}"
    crown = world.kernel.controller(seat)
    merchants = next((o.id for o in world.kernel.registry.orgs.values()
                      if o.settlement == seat and o.kind == "merchant"), "")
    finance = isinstance(action, A.FinanceTrade)
    source, target = (crown, merchants) if finance else (merchants, crown)
    if not source or not target or action.quantity <= 0:
        raise ValueError("that trade order has no executor or cargo")
    book = world.kernel.book
    lots = [lot for lot in book.at(seat)
            if lot.owner == source and lot.good == action.good and lot.free]
    if sum(lot.free for lot in lots) < action.quantity:
        raise ValueError(f"only {sum(lot.free for lot in lots)} {action.good} is available")
    left = action.quantity
    for lot in lots:
        take = min(left, lot.free)
        ordinal = 9000
        new_id = None
        if take < lot.quantity:
            while mint(seat, book.turn, "lot", ordinal) in book.lots:
                ordinal += 1
            new_id = mint(seat, book.turn, "lot", ordinal)
        book = book.give(lot.id, take, target,
                         "lent" if finance else "seized", crown, new_id)
        moved = new_id or lot.id
        if book.lots[moved].holder != target:
            book = book.hand(moved, target,
                             "lent" if finance else "seized", crown)
        left -= take
        if not left:
            break
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    event = (A.TradeFinanced if finance else A.TradeRequisitioned)
    return world, [event(action.good, action.quantity)]
