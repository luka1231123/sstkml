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

    if isinstance(action, A.SendToHarvest):
        if action.group_id not in world.court.dependents:
            raise ValueError(f"unknown group: {action.group_id}")
        at_harvest = set(world.court.at_harvest)
        if action.to_fields:
            at_harvest.add(action.group_id)
        else:
            at_harvest.discard(action.group_id)
        return (replace_court(world, at_harvest=tuple(sorted(at_harvest))),
                [A.SentToHarvest(action.group_id, action.to_fields)])

    if isinstance(action, A.AssignTroops):
        from engine.troops import assign
        return assign(world, action)

    if isinstance(action, A.RaiseCorvee):
        rules = world.land_rules
        cap = rules.get("corvee_max_days", 6000)
        days = max(0, min(action.days, cap - world.court.corvee_days))
        if days <= 0:
            raise ValueError("no more corvee can be raised this season")
        # Levied labour is paid for in unrest, immediately and visibly. This is
        # the one lever in the game that converts legitimacy straight into grain.
        delta = days * rules.get("corvee_unrest_per_1000_days", 40) // 1000
        unrest = min(1000, world.court.unrest + delta)
        return (replace_court(world, corvee_days=world.court.corvee_days + days,
                              unrest=unrest),
                [A.CorveeRaised(days, unrest - world.court.unrest)])

    if isinstance(action, A.DredgeCanal):
        from engine.core import in_range
        estate = world.court.estates.get(action.estate_id)
        if estate is None:
            raise ValueError(f"unknown estate: {action.estate_id}")
        if not estate.irrigated:
            raise ValueError(f"{action.estate_id} has no canal to dredge")
        span = world.season.get("low_water")
        if not span or not in_range(world.date.fortnight, tuple(span)):
            raise ValueError("the water is too high to dredge")
        days = max(0, action.days)
        gain = days * world.land_rules.get("canal_dredge_per_1000_days", 90) // 1000
        condition = min(1000, estate.canal_condition + gain)
        estates = dict(world.court.estates)
        estates[action.estate_id] = dataclasses.replace(
            estate, canal_condition=condition)
        return (replace_court(world, estates=estates),
                [A.CanalDredged(action.estate_id, days, condition)])

    if isinstance(action, A.MarryAbroad):
        from engine.house import marry_abroad
        return marry_abroad(world, action.person_id, action.actor)

    if isinstance(action, A.ConsultDiviner):
        from engine.divine import consult
        stores = dict(world.court.stores)
        value = 0
        if action.offering_good:
            have = stores.get(action.offering_good, 0)
            quantity = max(0, action.offering_quantity)
            if quantity > have:
                raise ValueError(
                    f"the storehouse holds only {have} {action.offering_good}")
            stores[action.offering_good] = have - quantity
            value = quantity * world.gift_values.get(action.offering_good, 0)
            world = replace_court(world, stores=stores)
        return consult(world, action.question, action.subject, value)

    if isinstance(action, A.SuppressOmen):
        from engine.divine import suppress
        return suppress(world, action.omen_id)

    if isinstance(action, A.DefyOmen):
        from engine.divine import defy
        return defy(world, action.omen_id)

    if isinstance(action, A.SwearOath):
        oath = next((o for o in world.oaths if o.id == action.oath_id), None)
        if oath is None:
            raise ValueError(f"no such oath: {action.oath_id}")
        if oath.dissolved:
            raise ValueError("a dissolved oath cannot be re-sworn")
        if not oath.lapsed:
            raise ValueError("that oath already binds")
        ruler = world.court.ruler
        oaths = tuple(
            dataclasses.replace(o, lapsed=False, sworn_by=ruler,
                                sworn_turn=world.date.absolute)
            if o.id == action.oath_id else o
            for o in world.oaths)
        return (dataclasses.replace(world, oaths=oaths),
                [A.OathSworn(action.oath_id, ruler)])

    if isinstance(action, A.Quarantine):
        place = world.places.get(action.place_id)
        if place is None:
            raise ValueError(f"no such place: {action.place_id}")
        if action.place_id == world.court.seat:
            raise ValueError("a city cannot be quarantined against itself")
        closed = set(world.court.quarantined)
        if action.lift:
            closed.discard(action.place_id)
        else:
            closed.add(action.place_id)
        world = replace_court(world, quarantined=tuple(sorted(closed)))
        # Spec 6.12: it costs esteem with the correspondent. Nobody accepts that
        # his own city is the reason, and the letter saying so arrives later.
        relations = dict(world.relations)
        for actor, relation in relations.items():
            if relation.place != action.place_id:
                continue
            delta = 40 if action.lift else -70
            relations[actor] = dataclasses.replace(
                relation, esteem=max(0, min(1000, relation.esteem + delta)))
        world = dataclasses.replace(world, relations=relations)
        return world, [A.QuarantineSet(action.place_id, action.lift)]

    if isinstance(action, A.Expiate):
        from engine import plague
        oath = next((o for o in world.oaths if o.id == action.oath_id), None)
        if oath is None:
            raise ValueError(f"no such oath: {action.oath_id}")
        offering = max(0, action.offering)
        if offering > world.court.stores.get("grain", 0):
            raise ValueError("the granary does not hold that much")
        return plague.expiate(world, action.oath_id, offering)

    if isinstance(action, A.SearchArchive):
        # The hit list is Belief's business (the TUI re-runs the same query);
        # World records only that the hour was spent, which is what makes the
        # search cost real and replayable.
        from engine import archive
        hits = archive.search(world, action.query)
        searched = tuple(sorted(set(world.court.searched) | {action.query}))
        return (replace_court(world, searched=searched),
                [A.ArchiveSearched(action.query, len(hits))])

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
