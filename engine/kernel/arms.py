"""Bronze in the hands that carry it (spec 6.5, kernel side).

The mines ran with nothing to feed. Copper piled up on Cyprus, tin sat at Assur
and Emar, and neither ever met the other or an army: world copper went from 205
thousand shekels to 758 thousand in twenty years on a dead straight line, and
nothing anywhere consumed a shekel of it.

Bronze is the sink. A palace keeps its own people armed, the kit wears out --
lost, broken, buried with its owner, gone out as a gift and not come back --
and replacing it takes nine parts copper to one of tin. Copper is near, at
Alashiya. Tin comes down the long eastern road. A palace with copper and no tin
disarms slowly and has nothing to tell it so.
"""
from __future__ import annotations

import dataclasses

from engine.entity import EntityId

BRONZE = "bronze"
COPPER = "copper"
TIN = "tin"

# Shekels of bronze a palace keeps for every thousand of its own people.
KIT_PER_1000 = 45
# What a fortnight takes off bronze in service.
WEAR_PER_1000 = 33
# Nine parts copper to one of tin, by weight, and ten of bronze off the pair.
COPPER_PER_TIN = 9
PER_BATCH = 10

# Which of a settlement's people carry metal. The field hands do not.
ARMED = ("palace", "garrison")

# Gold and silver are not worn out; they are buried with the dead, cut up for a
# bride, and sent abroad as gifts that are not returned. Nothing in the game
# consumes them, so without this the mines minted precious metal on a straight
# line forever. The rate settles the world's gold near five thousand shekels
# and its silver near twenty thousand, which is what the mines can keep up.
PRECIOUS = ("gold", "silver")
PRECIOUS_LEAK_PER_1000 = 10


def kit(kernel, settlement: EntityId) -> int:
    """Shekels of bronze this place keeps its people in, whole and equipped."""
    return sum(c.people for c in kernel.cohorts_of(settlement)
               if c.kind in ARMED) * KIT_PER_1000 // 1000


def _held(book, owner: EntityId, good: str, place: EntityId) -> list:
    return [book.lots[i] for i in sorted(book.lots)
            if book.lots[i].owner == owner and book.lots[i].good == good
            and book.lots[i].location == place and book.lots[i].free > 0]


def _sourced(kernel, book, settlement: EntityId, good: str) -> list:
    """The local ruler's metal at this forge.

    A road is not a transfer of ownership. Remote metal enters only through a
    trade or obligation that moves the lot; otherwise one ruler's forge could
    silently consume another ruler's stores, including the player's.
    """
    return _held(book, kernel.controller(settlement), good, settlement)


def step(kernel):
    """Phase: the kit wears, and the forge replaces what the metal allows."""
    from engine.kernel.farm import _draw, _mint

    events: list = []
    book = kernel.book.at_phase(kernel.date.absolute, "production")
    turn = kernel.date.absolute
    # The seat is the court's, and the court has its own bronze chain in
    # `engine.metal` -- the one that drives formation capability and the slow
    # disarming the campaign is about. Two forges drawing on one pile of copper
    # would starve that one without saying so.
    crown = getattr(kernel.seat_goods, "seat", "")
    for i, settlement in enumerate(sorted(kernel.registry.settlements)):
        if kernel.registry.settlements[settlement].fallen or settlement == crown:
            continue
        owner = kernel.controller(settlement)
        if not owner:
            continue

        for good in PRECIOUS:
            hoard = _held(book, owner, good, settlement)
            leak = sum(lot.free for lot in hoard) * PRECIOUS_LEAK_PER_1000 // 1000
            if leak > 0:
                book, gone, _ = _draw(book, hoard, leak, "lost", authority=owner)
                if gone:
                    events.append(("buried", owner, good, gone))

        want = kit(kernel, settlement)
        if want <= 0:
            continue
        lots = _held(book, owner, BRONZE, settlement)
        carried = sum(lot.free for lot in lots)
        worn = carried * WEAR_PER_1000 // 1000
        if worn > 0:
            book, gone, _ = _draw(book, lots, worn, "lost", authority=owner)
            carried -= gone
            if gone:
                events.append(("bronze_worn", owner, settlement, gone))

        short = want - carried
        if short <= 0:
            continue
        copper = _sourced(kernel, book, settlement, COPPER)
        tin = _sourced(kernel, book, settlement, TIN)
        batches = min(sum(lot.free for lot in copper) // COPPER_PER_TIN,
                      sum(lot.free for lot in tin),
                      -(-short // PER_BATCH))
        if batches <= 0:
            continue
        book, took_c, from_c = _draw(book, copper, batches * COPPER_PER_TIN,
                                     "melted", authority=owner)
        book, took_t, from_t = _draw(book, tin, batches, "melted",
                                     authority=owner)
        made = min(took_c // COPPER_PER_TIN, took_t) * PER_BATCH
        if made <= 0:
            continue
        book = book.create(_mint(settlement, turn, "forge", i), BRONZE, made,
                           owner=owner, holder=owner, location=settlement,
                           reason="produced", from_lots=from_c + from_t)
        events.append(("smelted", owner, settlement, made, took_c, took_t))
    return dataclasses.replace(kernel, book=book), events
