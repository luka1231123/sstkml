"""Asked-for aid is a loan: delivery opens a debt and repayment repairs trust.

Default leaves an enforceable balance. A king who survives a creditor's raid
can still repay what he owes and reopen the relationship.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import AidDebt


def _court(world, actor: str) -> str:
    for key in (actor, f"person:{actor}"):
        if key in world.relations:
            return key
    return ""


def _rule(world, key: str, default: int) -> int:
    return world.protocol_rules.get(key, default)


def _esteem(world, court: str, delta: int):
    relation = world.relations[court]
    relations = dict(world.relations)
    relations[court] = dataclasses.replace(
        relation, esteem=max(0, min(1000, relation.esteem + delta)))
    return dataclasses.replace(world, relations=relations)


def asked(world, actor: str):
    court = _court(world, actor)
    return _esteem(world, court, _rule(world, "aid_request", -40)) if court else world


def received(world, actor: str, good: str, quantity: int,
             *, request_letter: str | None = None):
    court = _court(world, actor)
    if not court or not any(
            _court(world, claim.party) == court and claim.good == good
            and (request_letter is None or claim.source_letter == request_letter)
            for claim in world.letter_claims):
        return world
    due = world.date.absolute + _rule(world, "aid_repay_turns", 12)
    debts = list(world.aid_debts)
    for index, debt in enumerate(debts):
        if debt.creditor == court and debt.good == good and debt.status == "open":
            debts[index] = dataclasses.replace(
                debt, owed=debt.owed + quantity, due_turn=due)
            break
    else:
        debts.append(AidDebt(court, good, quantity, due))
    return dataclasses.replace(world, aid_debts=tuple(debts))


def repaid(world, actor: str, good: str, quantity: int):
    court, debts = _court(world, actor), []
    for debt in world.aid_debts:
        if (quantity and debt.creditor == court and debt.good == good
                and debt.status in {"open", "defaulted"}):
            pay = min(quantity, debt.owed)
            quantity -= pay
            previous_status = debt.status
            debt = dataclasses.replace(
                debt, owed=debt.owed - pay,
                status="paid" if pay == debt.owed else debt.status)
            if debt.status == "paid" and court:
                world = _esteem(world, court, _rule(
                    world, "aid_default_repaid" if previous_status == "defaulted"
                    else "aid_repaid", 120 if previous_status == "defaulted" else 50))
        debts.append(debt)
    return dataclasses.replace(world, aid_debts=tuple(debts))


def _intervene(world, court: str):
    from engine import defence
    from engine.kernel import travel
    target = f"settlement:{world.chosen_alu}"
    near = sorted(edge.destination for edge in travel.adjacency(
        world.kernel.registry.routes).get(target, ()))
    for origin in [f"settlement:{world.relations[court].place}", *near]:
        try:
            world, events = defence.start_raid(world, origin, target, occupy=False)
            return world, origin, events
        except ValueError:
            continue
    return world, "", []


def step(world):
    events, debts = [], []
    for debt in world.aid_debts:
        if debt.status == "open" and world.date.absolute > debt.due_turn:
            debt = dataclasses.replace(debt, status="defaulted")
            world = _esteem(world, debt.creditor, _rule(world, "aid_default", -250))
            world, origin, raid = _intervene(world, debt.creditor)
            events += [A.AidDefaulted(debt.creditor, debt.good, debt.owed, origin), *raid]
        debts.append(debt)
    return dataclasses.replace(world, aid_debts=tuple(debts)), events
