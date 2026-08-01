"""The seventeen phases, in the one order they may run (spec 6.1, 10.10)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

# Spec 6.1, verbatim in order.
PHASES: tuple[str, ...] = (
    "calendar",       # 1  advance the date, derive seasonal and climate conditions
    "arrivals",       # 2  scheduled legs, births, deaths, deadlines, committed effects
    "observe",        # 3  project each actor's local observations into its Belief
    "intents",        # 4  actors and standing orders submit intents
    "allocate",       # 5  resolve exclusive labour, asset, route, transport capacity
    "production",     # 6  production, maintenance, construction, institutional service
    "consumption",    # 7  household, organization, formation, journey consumption
    "market",         # 8  quotes, matching, reservation of goods and capacity
    "movement",       # 9  load, move, unload, lose, seize, reroute
    "settlement",     # 10 delivery, payment, tax, debt, tribute, obligation ledgers
    "health",         # 11 disease, fertility, migration, mortality from contacts
    "politics",       # 12 reactions, appointments, disputes, refusals, memory
    "upkeep",         # 13 degrade or repair institutions and assets
    "reports",        # 14 observations, reports, petitions, documents
    "project",        # 15 project the court's Belief and assemble the docket
    "player",         # 16 accept player actions, dispatch orders and journeys
    "close",          # 17 assert invariants, hash, autosave
)

_ORDER: Mapping[str, int] = {name: i for i, name in enumerate(PHASES)}


class PhaseError(RuntimeError):
    """A phase run out of its order, or one that does not exist."""


def index(phase: str) -> int:
    if phase not in _ORDER:
        raise PhaseError(f"no such phase: {phase!r}")
    return _ORDER[phase]


def before(phase: str, other: str) -> bool:
    return index(phase) < index(other)


@dataclasses.dataclass(frozen=True)
class Step:
    """One unit of work, and the phase whose causal position it occupies."""
    phase: str
    name: str
    run: object          # callable(state) -> (state, events)


@dataclasses.dataclass(frozen=True)
class Trace:
    """What ran, in what order. The inspector's spine and the order test's evidence."""
    entries: tuple[tuple[str, str, int], ...] = ()   # phase, name, event count

    def phases(self) -> tuple[str, ...]:
        seen: list[str] = []
        for phase, _, _ in self.entries:
            if not seen or seen[-1] != phase:
                seen.append(phase)
        return tuple(seen)


def run(state, steps: tuple[Step, ...]) -> tuple[object, list, Trace]:
    """Run the steps as given, refusing any that would run out of turn."""
    events: list = []
    entries: list[tuple[str, str, int]] = []
    reached = -1
    for step in steps:
        position = index(step.phase)
        if position < reached:
            raise PhaseError(
                f"{step.name} is in phase {step.phase!r}, which has already run")
        reached = position
        state, produced = step.run(state)
        produced = list(produced or [])
        events.extend(produced)
        entries.append((step.phase, step.name, len(produced)))
    return state, events, Trace(tuple(entries))
