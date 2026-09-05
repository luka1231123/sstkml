"""Explicit changes of political authority."""
from __future__ import annotations

import dataclasses

from engine.entity import EntityId, Registry


def succeed(registry: Registry, polity_id: EntityId,
            ruler_id: EntityId) -> Registry:
    """Put a named person on a polity's seat."""
    if polity_id not in registry.polities:
        raise KeyError(f"unknown polity {polity_id!r}")
    if ruler_id not in registry.persons:
        raise KeyError(f"unknown person {ruler_id!r}")
    polities = dict(registry.polities)
    polities[polity_id] = dataclasses.replace(
        polities[polity_id], ruler=ruler_id)
    return dataclasses.replace(registry, polities=polities)


def capture(registry: Registry, settlement_id: EntityId,
            polity_id: EntityId, turn: int = -1) -> Registry:
    """Transfer an Alu to another polity. Its dependent sites follow it."""
    if settlement_id not in registry.settlements:
        raise KeyError(f"unknown settlement {settlement_id!r}")
    if polity_id not in registry.polities:
        raise KeyError(f"unknown polity {polity_id!r}")
    if registry.settlements[settlement_id].fallen:
        raise ValueError("a burned Alu cannot be occupied")
    settlements = dict(registry.settlements)
    settlements[settlement_id] = dataclasses.replace(
        settlements[settlement_id], owner=polity_id, occupied_turn=turn)
    return dataclasses.replace(registry, settlements=settlements)
