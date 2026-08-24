"""Court petitions with immediate, visible stakes.

A case is one decision, not a knowledge tax followed by a hidden correctness
test. The petitioner names the crown good at stake; the Court shows the award
and unrest consequence of every verdict before the player spends the hour.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat
from engine.state import Petition, World

VERDICTS = ("for", "against", "split")


def _amount(values: tuple[tuple[str, int], ...]) -> int:
    return int(dict(values).get("amount", 0))


def consequence(petition: Petition, verdict: str) -> tuple[str, int, int]:
    """Return ``(good, award, unrest_delta)`` for one visible verdict."""
    if verdict not in VERDICTS:
        raise ValueError("verdict must be for, against, or split")
    claim = _amount(petition.claim)
    counter = _amount(petition.counterclaim)
    if verdict == "for":
        return petition.good, claim, petition.unrest_for
    if verdict == "against":
        return petition.good, counter, petition.unrest_against
    if verdict == "split":
        return petition.good, (claim + counter) // 2, petition.unrest_split
    raise AssertionError("unreachable verdict")


def rule(world: World, petition_id: str, verdict: str) -> tuple[World, list]:
    petition = world.court.petitions.get(petition_id)
    if petition is None:
        raise ValueError(f"no such petition: {petition_id}")
    good, amount, unrest_delta = consequence(petition, verdict)
    if amount > seat.available(world).get(good, 0):
        raise ValueError(f"the crown does not hold {amount:,} {good}")

    petitions = dict(world.court.petitions)
    petitions.pop(petition.id)
    if amount:
        world = seat.pay(
            world, good, amount, petition.petitioner,
            authority=world.court.actor)

    before = world.court.unrest
    unrest = max(0, min(1000, before + unrest_delta))
    court = dataclasses.replace(
        world.court, petitions=petitions, unrest=unrest)
    world = dataclasses.replace(world, court=court)
    events: list = [A.PetitionRuled(
        petition.id, verdict, petition.petitioner, good, amount,
        unrest - before)]
    if unrest != before:
        events.append(A.UnrestChanged(
            unrest - before, f"judgement in {petition.kind}"))
    return world, events


def step(world: World) -> tuple[World, list]:
    """Bring authored cases into the hall and age the visible queue."""
    now = world.date.absolute
    petitions = {
        key: dataclasses.replace(value, waiting=value.waiting + 1)
        for key, value in world.court.petitions.items()}
    events: list = []
    arrival_unrest = 0
    for case in world.justice_cases:
        if case.arrived_turn != now or case.id in petitions:
            continue
        petitions[case.id] = case
        arrival_unrest += case.unrest_arrival
        events.append(A.PetitionArrived(
            case.id, case.petitioner, case.against, case.kind))
    before = world.court.unrest
    unrest = max(0, min(1000, before + arrival_unrest))
    court = dataclasses.replace(
        world.court, petitions=petitions, unrest=unrest)
    if unrest != before:
        events.append(A.UnrestChanged(
            unrest - before, "an unresolved petition reaches Court"))
    return dataclasses.replace(world, court=court), events
