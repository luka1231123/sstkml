"""apply(state, action) -> (state, [event]). Pure. (spec 2.1)

Player intents translate to immediate state changes or Scheduled effects.
Allocation changes are stored now but only read by A8 next turn, so their
one-turn lag (spec D3) is structural, not special-cased.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import World, replace_court


def apply(world: World, action) -> tuple[World, list]:
    if isinstance(action, A.EndTurn):
        return world, []

    if isinstance(action, A.Allocate):
        if action.group_id not in world.court.dependents:
            raise ValueError(f"unknown group: {action.group_id}")
        qa = max(0, action.qa)
        allocations = dict(world.court.allocations)
        allocations[action.group_id] = qa
        return replace_court(world, allocations=allocations), [A.AllocationSet(action.group_id, qa)]

    if isinstance(action, A.SetPriority):
        for gid in action.order:
            if gid not in world.court.dependents:
                raise ValueError(f"unknown group in priority: {gid}")
        return replace_court(world, priority=tuple(action.order)), [A.PrioritySet(tuple(action.order))]

    if isinstance(action, A.EatSeed):
        stores = dict(world.court.stores)
        moved = min(max(0, action.qa), stores.get("seed_grain", 0))
        stores["seed_grain"] = stores.get("seed_grain", 0) - moved
        stores["grain"] = stores.get("grain", 0) + moved
        return replace_court(world, stores=stores), [A.SeedEaten(moved)]

    if isinstance(action, A.ReadLetter):
        inbox = tuple(
            dataclasses.replace(L, read=True) if L.id == action.letter_id else L
            for L in world.inbox
        )
        return dataclasses.replace(world, inbox=inbox), [A.LetterRead(action.letter_id)]

    if isinstance(action, A.InspectLedger):
        _LEDGERS = {"granary": "grain", "seed": "seed_grain"}
        good = _LEDGERS.get(action.ledger)
        if good is None:
            raise ValueError(f"no such ledger: {action.ledger}")
        inspected = tuple(sorted(set(world.court.inspected) | {action.ledger}))
        true_value = world.court.stores.get(good, 0)
        return replace_court(world, inspected=inspected), [A.LedgerInspected(action.ledger, true_value)]

    if isinstance(action, A.SendGift):
        from engine.relations import send_gift
        return send_gift(world, action)

    if isinstance(action, A.DictateReply):
        from engine import mail
        if action.profile and not 0 <= action.protocol_total <= 1000:
            raise ValueError("protocol score must be in 0..1000")
        letter = next((L for L in world.inbox if L.id == action.letter_id), None)
        if letter is None:
            raise ValueError(f"no such letter: {action.letter_id}")
        target_place = letter.path[0]      # where the sender is
        if letter.answered_turn is None:
            inbox = tuple(
                dataclasses.replace(item, answered_turn=world.date.absolute)
                if item.id == letter.id else item
                for item in world.inbox
            )
            world = dataclasses.replace(world, inbox=inbox)
        violations = tuple(action.protocol_violations)
        relation = world.relations.get(letter.sender)
        if (relation is not None
                and relation.status_claim != relation.their_status_claim
                and "my brother" in action.text.casefold()
                and "kinship_overreach" not in violations):
            violations += ("kinship_overreach",)
        return mail.dispatch_reply(world, letter.sender, target_place,
                                   "reply", (),
                                   action.profile, action.protocol_total,
                                   violations)

    raise TypeError(f"unhandled action: {type(action).__name__}")
