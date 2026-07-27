"""The seventeen phases, in the one order they may run (spec 6.1, 10.10).

The rule this module exists to hold: the fortnight is not a walk through the
settlements, it is a walk through the phases, and every settlement crosses each
phase together. A tick that finished Ugarit before starting Ma'hadu would let
the first city spend labour, buy grain, and take route capacity that the second
never had the chance to bid for -- and no amount of care inside the systems
recovers the fairness that ordering threw away.

So phases are declared, ordered, and checked. A phase may read the opening
snapshot and the results of phases already run. It may not read a later phase's
output; a phase that needs one is mis-ordered, and the fix is to move it.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

# Spec 6.1, verbatim in order. The implementation may split a phase further; it
# may not reorder these without changing the specification and its tests.
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
    """Run the steps as given, refusing any that would run out of turn.

    Deliberately not sorted. Quietly reordering a mis-assembled turn would hide
    the mistake in the one place it must be visible, and the caller would go on
    believing its declared order is the order that ran. Within a single phase
    the given order stands: that is the implementer's business, and 6.1 permits
    splitting a phase further.
    """
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
