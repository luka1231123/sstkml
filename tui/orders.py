"""The Orders workbench: what the king has actually ordered (UI/UX spec 13).

The audit's thirteenth problem in one line: *there is no persistent Orders
workbench despite the order-heavy design.* Every order the player gives is
already written down -- the session log is the replay record, so it is the
authoritative history of intent and there is no second history to invent. What
was missing was any way to read it back.

Reading it back is not a nicety. The game is built on giving orders into an
information gap and waiting, and a player who cannot answer *did I already
close that road?* is not playing the game the design describes; he is keeping
notes on paper. So this window answers three questions and no others:

* what did I order, and when;
* which of those orders is still in force;
* which of them can be taken back, and at what price.

The third is the honest one. Most orders cannot be unsaid: a tablet read is
read, a gift sent is gone. A few have a genuine inverse in the engine -- a
quarantine can be lifted, hands can be recalled from the fields, a filed tablet
can be restored, a man in a post can be dismissed -- and for those the window
offers the inverse *as its own order, at its own cost*, because that is what it
is. Nothing here rewinds the world.
"""
from __future__ import annotations

import dataclasses

import affordances
import registry
from engine import actions as A
from tui import workbench
from tui.grid import InteractiveScreen

# Orders that occupy a slot: a later order about the same subject replaces the
# earlier one, so only the last is still in force. The slot name is what the
# player would call the thing being decided, because "the succession" reads and
# `NameHeir` does not.
#
# `flag` names the field that says which way the order runs, where there is
# one, and `in_force` is the value that means it is still doing something.
# `undo` is the action id that reverses it -- an order in its own right, with
# its own cost, not an undo stack.


@dataclasses.dataclass(frozen=True)
class Slot:
    name: str
    subject: tuple[str, ...] = ()
    flag: str = ""
    in_force: bool = True
    undo: str = ""
    undo_label: str = ""
    off_label: str = ""     # what the flag-flipped order is called


SLOTS: dict[str, Slot] = {
    "ArchiveLetter": Slot(
        "this tablet", ("letter_id",), "archived", True,
        "file_letter", "restore it to the pile", "Restore"),
    "Quarantine": Slot(
        "this road", ("place_id",), "lift", False,
        "quarantine", "lift the closure", "Lift the closure"),
    "SendToHarvest": Slot(
        "these hands", ("group_id",), "to_fields", True,
        "send_to_harvest", "call them back", "Recall"),
    "PlacePerson": Slot(
        "this post", ("post",), undo="dismiss_person",
        undo_label="dismiss him from it"),
    "DismissPerson": Slot("this post", ("post",)),
    "AssignTroops": Slot("this formation", ("formation_id",)),
    "SetLandDue": Slot("the land due"),
    "SetHarbourDue": Slot("the harbour due"),
    "SetPriority": Slot("the ration order"),
    "NameHeir": Slot("the succession"),
}

# Which Belief domain each action field is drawn from is already stated once,
# in the registry. Orders reads it rather than keeping a second table.
STANDING, SUPERSEDED, GIVEN = "standing", "superseded", "given"

VIEWS = (("standing", "STILL IN FORCE"), ("fortnight", "THIS FORTNIGHT"),
         ("all", "EVERYTHING"))


@dataclasses.dataclass(frozen=True)
class Order:
    """One line of the log, read as an order rather than as a replay record."""

    index: int
    turn: int
    action: dict
    state: str

    @property
    def id(self) -> str:
        return f"order-{self.index}"

    @property
    def descriptor(self) -> registry.ActionDescriptor | None:
        kind = self.action.get("_t", "")
        found = getattr(A, kind, None)
        return registry.BY_TYPE.get(found) if found is not None else None

    @property
    def slot(self) -> Slot | None:
        return SLOTS.get(self.action.get("_t", ""))


def _subject(action: dict, slot: Slot) -> tuple:
    return tuple(action.get(field) for field in slot.subject)


def _in_force(action: dict, slot: Slot) -> bool:
    if not slot.flag:
        return True
    return bool(action.get(slot.flag)) is slot.in_force


def history(log: list[dict]) -> list[Order]:
    """Every order given, newest first, each knowing whether it still stands.

    Slot occupancy is computed from the log alone, which is the point: the log
    is what replay reads, so anything derived from it survives a save, a
    reload, and a session opened in the terminal instead of the window.
    """
    latest: dict[tuple, int] = {}
    for index, record in enumerate(log):
        action = record.get("action", {})
        slot = SLOTS.get(action.get("_t", ""))
        if slot is not None:
            latest[(slot.name, _subject(action, slot))] = index

    orders = []
    for index, record in enumerate(log):
        action = record.get("action", {})
        slot = SLOTS.get(action.get("_t", ""))
        if slot is None:
            state = GIVEN
        elif latest.get((slot.name, _subject(action, slot))) != index:
            state = SUPERSEDED
        elif _in_force(action, slot):
            state = STANDING
        else:
            state = SUPERSEDED
        orders.append(Order(index, int(record.get("turn", 0)), action, state))
    orders.reverse()
    return orders


def countermand(order: Order):
    """The order that reverses this one, or None if it cannot be unsaid."""
    slot = order.slot
    if slot is None or not slot.undo or order.state != STANDING:
        return None
    descriptor = registry.BY_ID.get(slot.undo)
    if descriptor is None:
        return None
    fields = {name: order.action.get(name)
              for name in _field_names(descriptor.action_type)
              if name in order.action}
    if slot.flag:
        fields[slot.flag] = not slot.in_force
    missing = [name for name in _field_names(descriptor.action_type)
               if name not in fields]
    if missing:
        return None
    return descriptor.action_type(**fields)


def _field_names(cls: type) -> tuple[str, ...]:
    return tuple(field.name for field in dataclasses.fields(cls))


# --- reading an order back ----------------------------------------------------

def phrase(order: Order, belief: dict) -> str:
    """What the order said, in the words the player used to give it.

    Built from the descriptor's own field list, so an action added to the
    registry reads correctly here without anybody remembering to come back.
    """
    descriptor = order.descriptor
    if descriptor is None:
        return str(order.action.get("_t", "an order"))
    names = registry.argument_names(descriptor)
    parts = []
    for field in descriptor.fields:
        value = order.action.get(names.get(field.name, field.name))
        if value in (None, "", ()) or isinstance(value, bool):
            continue
        if field.domain == "quantity":
            parts.append(f"{int(value):,}")
        elif isinstance(value, (list, tuple)):
            parts.append(" → ".join(
                affordances.name_in(field.domain, str(item), belief)
                for item in value))
        else:
            parts.append(affordances.name_in(field.domain, str(value), belief))
    # A flag-flipped order is a different order and must not borrow the name
    # of the one it undoes: "Close" and "Lift the closure" are not the same
    # thing to a player reading his own history back.
    slot = order.slot
    label = descriptor.label
    if slot is not None and slot.flag and not _in_force(order.action, slot):
        label = slot.off_label or label
    return f"{label}: {', '.join(parts)}" if parts else label


def when(order: Order, now: int) -> str:
    ago = now - order.turn
    if ago <= 0:
        return "this fortnight"
    return f"{ago} fn ago"


STATE_MARK = {STANDING: ("!", "gold"), SUPERSEDED: ("·", "ash"),
              GIVEN: (" ", "dim")}
STATE_WORD = {STANDING: "in force", SUPERSEDED: "overtaken", GIVEN: "done"}


def visible(orders: list[Order], view: str, now: int) -> list[Order]:
    if view == "standing":
        return [order for order in orders if order.state == STANDING]
    if view == "fortnight":
        return [order for order in orders if order.turn >= now]
    return list(orders)


def compose(belief: dict, log: list[dict], now: int, hours: int = 0,
            view: str = "standing", selected: str = "", scroll: int = 0,
            notice: str = "", width: int = 88,
            height: int = 30) -> InteractiveScreen:
    orders = visible(history(log), view, now)
    chosen = next((order for order in orders if order.id == selected),
                  orders[0] if orders else None)

    rows = []
    for order in orders:
        mark, tone = STATE_MARK[order.state]
        rows.append(workbench.Row(
            order.id,
            ((when(order, now), "dim"),
             (phrase(order, belief), tone if order.state == STANDING
              else "clay"),
             (STATE_WORD[order.state], tone)),
            mark=mark if order.state == STANDING else ""))

    detail: list[tuple[str, str]] = []
    controls: list[workbench.Control] = []
    if chosen is not None:
        detail.extend(_detail(chosen, belief, now))
        reversal = countermand(chosen)
        if reversal is not None:
            slot = chosen.slot
            controls.append(workbench.affordable(workbench.Control(
                slot.undo, "u", label=slot.undo_label), hours))
        if chosen.descriptor is not None:
            controls.append(workbench.Control(
                "open", "Enter", label="open where it was given"))
    if not any(control.key == "u" for control in controls):
        controls.append(workbench.Control(
            "countermand", "u", label="countermand", enabled=False,
            why="this one cannot be unsaid"))

    return workbench.compose(
        "ORDERS", ("when", "what was ordered", "state"), (14, 36, 10),
        rows, chosen.id if chosen else "", detail, controls, hours,
        width, height, scroll, notice,
        empty=_empty(view), views=VIEWS, view=view,
        note="Tab / Shift-Tab view   ↑↓ choose   Enter open")


def _empty(view: str) -> str:
    return {
        "standing": "no order of yours is still in force.",
        "fortnight": "you have given no order this fortnight.",
    }.get(view, "you have given no order yet.")


def _detail(order: Order, belief: dict, now: int) -> list[tuple[str, str]]:
    descriptor = order.descriptor
    if order.action.get("_t") == "SetPriority":
        names = [affordances.name_in("group", str(group), belief)
                 for group in order.action.get("order", ())]
        lines: list[tuple[str, str]] = [("RATION ORDER", "bone")]
        # Two ranks per line keep all seven visible in the real 72×24 window.
        for index in range(0, len(names), 2):
            left = f"{index + 1}  {names[index]}"
            right = (f"{index + 2}  {names[index + 1]}"
                     if index + 1 < len(names) else "")
            lines.append((f"{left:<32}{right}", "clay"))
        lines += [("", "clay"), (f"given {when(order, now)}", "sky")]
    else:
        lines = [
            (phrase(order, belief), "bone"),
            ("", "clay"),
            (f"given {when(order, now)}", "sky"),
        ]
    if descriptor is not None and descriptor.cost:
        unit = "hour" if descriptor.cost == 1 else "hours"
        lines.append((f"it cost {descriptor.cost} {unit}", "dim"))
    lines.append(("", "clay"))

    slot = order.slot
    if order.state == STANDING:
        lines.append(("This order still stands.", "gold"))
        if slot is not None and slot.undo:
            undone = registry.BY_ID.get(slot.undo)
            price = undone.cost if undone else 0
            unit = "hour" if price == 1 else "hours"
            lines.append((f"You may {slot.undo_label}, which is an order of "
                          f"its own", "clay"))
            lines.append((f"and costs {price} {unit}.", "clay"))
        else:
            lines.append(("Nothing in the engine reverses it. A later order "
                          "about", "ash"))
            lines.append((f"{slot.name if slot else 'the same matter'} would "
                          "replace it.", "ash"))
    elif order.state == SUPERSEDED:
        lines.append(("A later order about "
                      f"{slot.name if slot else 'this'} has replaced it.",
                      "ash"))
    else:
        lines.append(("It is done. An order given cannot be unsaid.", "ash"))
    return lines
