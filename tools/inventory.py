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
    "Conceived", "Revolt", "Landed",
    "Detached", "Returned", "Displaced", "Defended", "Fell", "Recovered",
    "Financed", "Requisitioned",
)

# Events whose names do not end in a past participle the sweep recognises.
# Named rather than matched: `SentToHarvest` is the event and `SendToHarvest`
# is the order, and a suffix rule wide enough to catch the first would hide the
# second from the orphan check entirely.
EVENT_NAMES = frozenset({"SentToHarvest", "ArchiveSearched",
                         # Not intent: it records that an accepted reading of a
                         # foreign court's answer was kept, so replay reads text
                         # instead of asking a model again (spec 2.6). It has no
                         # cost, no room, and no grammar, so a descriptor would
                         # put a phantom order in the palace.
                         "RecordReplyText"})

# Intent that is deliberately not offered (C4): the canal is gone, and the
# action survives only so the typed and voiced paths can be refused honestly
# ("there is no canal to dredge") instead of never having heard of the verb.
UNOFFERED = frozenset({"DredgeCanal"})


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
        if getattr(cls, "_registry_value", False):
            continue
        if name in EVENT_NAMES:
            continue
        if name in UNOFFERED:
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
                | {k for k, _t, _h in play_gui.LEDGERS.values()}
                | {k for k, _t, _h in play_gui.ROOMS.values()})
    for target in sorted(built - openable):
        found.append(f"unreachable room: hall advertises '{target}'")
    for target in sorted(openable - built):
        found.append(f"undocumented room: '{target}' has no hall door")

    # 7. Counsel is human-language interpretation, never the sole mechanical
    #    route. Every implemented action also belongs beside its evidence on a
    #    direct structured screen; the required model does not become an
    #    authority merely because it is part of the product.
    for descriptor in registry.DESCRIPTORS:
        routes = [context for context in descriptor.contexts
                  if context != "counsel"]
        if not routes:
            found.append(
                f"only through Counsel: {descriptor.id} has no direct screen")
            continue
        if not any(context in DIRECT_CONTEXTS for context in routes):
            found.append(
                f"no direct route: {descriptor.id} is offered in "
                f"{', '.join(routes)}, none of which handles keys")

    # 8. Every workbench must actually print the controls its context claims.
    #    The registry saying an action belongs to the Roll means nothing if the
    #    Roll does not draw it, and that gap is invisible in a screenshot of a
    #    screen where the row happens to be unselected.
    found.extend(_workbench_gaps())

    return found


# Contexts with a key handler behind them: a screen the player can open and
# give this order on. `counsel` is deliberately absent -- it is the thing every
# action must not depend on.
DIRECT_CONTEXTS = frozenset({
    "hall", "stack", "letter", "desk", "stores", "roll", "land", "muster",
    "oaths", "works", "alu", "institution", "justice", "house", "altar",
    "archive", "relations", "world", "plague", "trade",
})


def _workbench_gaps() -> list[str]:
    """Compose each ledger and check it offers every action of its context."""
    from belief.project import project
    from engine.tick import advance
    from load import load_campaign
    from tui import ledgers, palace

    world = load_campaign("seat", 8814402919)
    for _ in range(8):
        world, _ = advance(world)
    belief = project(world)

    gaps = []
    # The palace states the orders it offers rather than drawing them into a
    # command string, because several of its controls are not `do:<id>` -- four
    # verdicts are one action. So it is checked against its own declaration and
    # a second test checks that declaration is printed.
    for view, context in palace.CONTEXT_OF.items():
        offered = {control.action_id
                   for control in palace.controls_for(belief, view, hours=8)}
        for descriptor in registry.in_context(context):
            if descriptor.id not in offered:
                gaps.append(
                    f"the palace's {view} does not offer {descriptor.id}, "
                    f"which the registry says belongs to {context}")

    land_data = belief.get("land") or {}
    estates = list(land_data.get("estates", []))
    audit_land = {
        **belief,
        "land": {
            **land_data,
            # Conditional controls need a useful order phase in this synthetic
            # audit; the live projection keeps them hidden when calling crews
            # would buy no work.
            "corvee_call_open": True,
            "corvee_usable_days": 400,
            "estates": (
                [{**estates[0], "irrigated": True,
                  "canal_condition": 500}] + estates[1:]
                if estates else []),
        },
    }
    oaths = list(belief.get("oaths", []))
    audit_oaths = {
        **belief,
        "oaths": (
            [{**oaths[0], "lapsed": True}] + oaths[1:]
            if oaths else []),
    }
    groups = list(belief.get("groups", []))
    screens = {
        "roll": ledgers.roll(
            belief, amount=50, hours=8, width=88, height=28),
        "land": ledgers.land(
            audit_land, days=5,
            group=groups[0]["id"] if groups else "",
            hours=8, width=84, height=28),
        "oaths": ledgers.oaths(
            audit_oaths, amount=50, hours=8, width=82, height=28),
    }
    store_screens = (
        ledgers.stores(
            belief, selected="grain", hours=8, width=80, height=28),
        ledgers.stores(
            belief, selected="seed_grain", amount=50,
            hours=8, width=80, height=28),
    )
    offered_stores = {
        hit.command.split(":", 1)[1]
        for screen in store_screens for hit in screen.hits
        if hit.command.startswith("do:")
    }
    for descriptor in registry.in_context("stores"):
        if descriptor.id not in offered_stores:
            gaps.append(
                f"stores does not offer {descriptor.id}, which the "
                "registry says belongs to it")
    offered_muster = {
        hit.command.split(":", 1)[1]
        for view, _label in ledgers.MUSTER_VIEWS
        for hit in ledgers.muster(
            belief, hours=8, width=84, height=28, view=view).hits
        if hit.command.startswith("do:")
    }
    for descriptor in registry.in_context("muster"):
        if descriptor.id not in offered_muster:
            gaps.append(
                f"muster does not offer {descriptor.id}, which the "
                "registry says belongs to it")
    for context, screen in screens.items():
        offered = {hit.command.split(":", 1)[1] for hit in screen.hits
                   if hit.command.startswith("do:")}
        for descriptor in registry.in_context(context):
            if descriptor.id not in offered:
                gaps.append(
                    f"{context} does not offer {descriptor.id}, which the "
                    f"registry says belongs to it")
    # And the printed key must be the registry's own mnemonic. `ledgers.key_for`
    # is the only source the screens use, so this checks the source rather than
    # every call site.
    for descriptor in registry.DESCRIPTORS:
        if not descriptor.mnemonic:
            continue
        if ledgers.key_for(descriptor.id) != descriptor.mnemonic:
            gaps.append(
                f"the workbenches print [{ledgers.key_for(descriptor.id)}] "
                f"for {descriptor.id}, not [{descriptor.mnemonic}]")
    return gaps


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
