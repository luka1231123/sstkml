#!/usr/bin/env python3
"""The authoritative inventory of actions, rooms, controls, and costs.

UI/UX specification phase 0: this must fail on an orphan action, an unreachable
room, a duplicate mnemonic, or a cost that disagrees with itself between the
registry and the typed path. Those are exactly the faults that are invisible in
a screenshot and cheap to introduce -- an action added to the engine with no
route into the game looks fine until a player goes looking for it.

    python3 tools/inventory.py            report, and exit non-zero on a fault
    python3 tools/inventory.py --quiet    exit status only
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import registry                                   # noqa: E402
from engine import actions as A                   # noqa: E402
from tui import hall                              # noqa: E402

# Engine records that describe what happened rather than what the player asked
# for. They are logged and replayed but never chosen, so they need no route and
# no cost. Anything not in this set and not in the registry is an orphan.
EVENT_SUFFIXES = (
    "Arrived", "Sent", "Set", "Taken", "Read", "Archived", "Delegated",
    "Inspected", "Judged", "Due", "Withdrew", "Withdrawn", "Placed",
    "Dismissed", "Named", "Advanced", "Paid", "Departed", "Died", "Changed",
    "Performed", "Skipped", "Eaten", "Delivered", "Intercepted", "Began",
    "Spread", "Progressed", "Deaths", "Heard", "Ruled", "Sworn", "Lapsed",
    "Expiated", "Suppressed", "Leaked", "Defied", "Taken", "Born",
    "Succeeded", "Failed", "Abroad", "Assigned", "Received", "Smelted",
    "Worn", "Melted", "Met", "Decayed", "Consumed", "Begun", "Finished",
    "Abandoned", "Fled", "Sought", "Applied", "Violated", "Threshed",
    "Sown", "Harvested", "Dredged", "Raised", "Spoiled", "Grumbling",
    "Conceived", "Revolt",
)

# Events whose names do not end in a past participle the sweep recognises.
# Named rather than matched: `SentToHarvest` is the event and `SendToHarvest`
# is the order, and a suffix rule wide enough to catch the first would hide the
# second from the orphan check entirely.
EVENT_NAMES = frozenset({"SentToHarvest", "ArchiveSearched"})


def _player_action_types() -> list[type]:
    """Every dataclass in the action union that is player intent, not an event.

    The union in `engine.actions` mixes both because both are logged. Intent is
    what the registry must cover.
    """
    types = []
    for name, cls in vars(A).items():
        if not isinstance(cls, type) or not hasattr(cls, "__dataclass_fields__"):
            continue
        if name.startswith("_"):
            continue
        if name in EVENT_NAMES:
            continue
        if any(name.endswith(suffix) for suffix in EVENT_SUFFIXES):
            continue
        types.append(cls)
    return types


def faults() -> list[str]:
    found: list[str] = []

    # 1. Orphan actions: player intent with no descriptor, so no label, no
    #    cost, and no route into any window.
    for cls in _player_action_types():
        if cls not in registry.BY_TYPE:
            found.append(f"orphan action: {cls.__name__} has no descriptor")

    # 2. A descriptor pointing at something the engine does not have.
    for descriptor in registry.DESCRIPTORS:
        if not hasattr(A, descriptor.action_type.__name__):
            found.append(
                f"descriptor {descriptor.id} names a missing action type")

    # 3. Duplicate ids.
    seen: set[str] = set()
    for descriptor in registry.DESCRIPTORS:
        if descriptor.id in seen:
            found.append(f"duplicate descriptor id: {descriptor.id}")
        seen.add(descriptor.id)

    # 4. Duplicate mnemonics *within one context*. The same letter may mean
    #    different things in different windows -- that is normal and is why the
    #    check is per context rather than global -- but two actions competing
    #    for one key in one window means one of them is unreachable.
    for context in registry.contexts():
        used: dict[str, str] = {}
        for descriptor in registry.in_context(context):
            key = descriptor.mnemonic
            if not key:
                continue
            if key in used:
                found.append(
                    f"duplicate mnemonic '{key}' in {context}: "
                    f"{used[key]} and {descriptor.id}")
            used[key] = descriptor.id

    # 5. Cost divergence between the registry and the typed path. This is the
    #    fault the audit actually caught, so it gets a check of its own rather
    #    than trust.
    from ai import parser as ai_parser
    for descriptor in registry.DESCRIPTORS:
        sample = _sample(descriptor.action_type)
        if sample is None:
            continue
        typed = ai_parser.action_cost(sample)
        if typed != descriptor.cost:
            found.append(
                f"cost divergence for {descriptor.id}: registry says "
                f"{descriptor.cost}h, parser says {typed}h")

    # 6. Unreachable rooms: a door the hall advertises as built that no window
    #    opens, or a window with no door.
    built = {target for _k, _l, target in hall.DOORS if target in hall.BUILT}
    import play_gui
    openable = ({k for k, _t, _h in play_gui.TABLETS.values()}
                | {k for k, _t, _h in play_gui.ROOMS.values()} | {"desk"})
    for target in sorted(built - openable):
        found.append(f"unreachable room: hall advertises '{target}'")
    for target in sorted(openable - built):
        found.append(f"undocumented room: '{target}' has no hall door")

    return found


def _sample(cls: type):
    """A throwaway instance, for asking a cost function what it charges."""
    import dataclasses
    kwargs = {}
    for field in dataclasses.fields(cls):
        if field.default is not dataclasses.MISSING:
            continue
        annotation = str(field.type)
        if "int" in annotation:
            kwargs[field.name] = 0
        elif "bool" in annotation:
            kwargs[field.name] = False
        elif "tuple" in annotation:
            kwargs[field.name] = ()
        else:
            kwargs[field.name] = ""
    try:
        return cls(**kwargs)
    except Exception:
        return None


def report() -> int:
    problems = faults()
    actions = len(registry.DESCRIPTORS)
    charged = sum(1 for d in registry.DESCRIPTORS if d.cost)
    print(f"inventory · {actions} player actions, {charged} charged, "
          f"{len(registry.contexts())} contexts")
    if not problems:
        print("  no faults")
        return 0
    for problem in problems:
        print(f"  FAULT {problem}")
    return 1


if __name__ == "__main__":
    code = report() if "--quiet" not in sys.argv else (1 if faults() else 0)
    raise SystemExit(code)
