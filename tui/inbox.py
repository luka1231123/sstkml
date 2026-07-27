"""The bronze-age Inbox: pile, selected tablet, and reading in one window."""
from __future__ import annotations

import textwrap

from tui import render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def ordered_items(b: dict, order: list[str] | None = None,
                  filter_name: str = "unread") -> list[dict]:
    if filter_name == "outbox":
        return list(b.get("outbox", []))
    if filter_name == "archived":
        source = list(b.get("correspondence_archive", []))
    else:
        source = list(b.get("stack", []))
    by_id = {item["id"]: item for item in source}
    ids = list(order or ())
    ids += [item["id"] for item in source if item["id"] not in ids]
    items = [by_id[letter_id] for letter_id in ids if letter_id in by_id]
    if filter_name == "unread":
        items = [item for item in items if not item["read"]]
    return items


def _trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def compose(b: dict, width: int = 108, height: int = 36,
            order: list[str] | None = None, selected: str = "",
            filter_name: str = "unread", scroll: int = 0,
            hours_left: int | None = None,
            delegate_to: str = "",
            answered: dict[str, int] | None = None,
            notice: str = "") -> InteractiveScreen:
    """Compose the pile and the selected tablet.

    ``selected`` is resolved against the whole pile, not only the active
    filter.  Reading the selected tablet removes it from the Unread list, but
    it must not also replace the body with the next tablet before the player
    has had a chance to read it.

    Reply, filing, and delegation state all comes from Belief, so it survives
    saving and replay. The Outbox is the court's sent-copy record; its delivery
    wording deliberately does not reveal whether a courier was intercepted.

    ``answered`` is accepted for compatibility with older callers; reply state
    is now canonical in the projected letter and the sidecar is ignored.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    active_items = ordered_items(b, order, "all")
    archived_items = ordered_items(b, order, "archived")
    inbound_items = active_items + archived_items
    outbox_items = ordered_items(b, order, "outbox")
    unread_count = sum(not item["read"] for item in active_items)
    in_transit = sum(item.get("in_transit", False) for item in outbox_items)
    style.panel(
        surface, 0, 0, width, height,
        title=(
            f"CORRESPONDENCE — {unread_count} UNREAD · "
            f"{len(archived_items)} FILED · {len(outbox_items)} SENT · "
            f"{in_transit} IN TRANSIT"),
        drop=False)

    list_width = min(45, max(32, width * 2 // 5))
    divider = list_width
    for row in range(2, height - 1):
        surface.put(divider, row, "│", C["faint"], C["ink"])

    items = ordered_items(b, order, filter_name)
    selectable = (
        outbox_items if filter_name == "outbox" else inbound_items)
    selected_item = next(
        (item for item in selectable if item["id"] == selected), None)
    if selected_item is None:
        selected_item = items[0] if items else None
        selected = selected_item["id"] if selected_item else ""

    view_names = {
        "unread": "UNREAD",
        "all": "ACTIVE",
        "archived": "FILED",
        "outbox": "OUTBOX",
    }
    style.bar(surface, 2, 2, list_width - 3,
              f" {view_names.get(filter_name, filter_name.upper())}",
              fg=C["bone"], bg=C["faint"])
    room = max(0, height - 6)
    scroll = max(0, min(scroll, max(0, len(items) - room)))
    if not items:
        surface.text(4, 5, "No tablets in this view.", C["ash"], C["ink"])
    for offset, item in enumerate(items[scroll:scroll + room]):
        row = 4 + offset
        chosen = item["id"] == selected
        marker = ">" if chosen else " "
        outbound = filter_name == "outbox"
        state = (
            "→" if outbound
            else "✓" if item.get("answered_turn") is not None
            else "§" if item.get("archived")
            else "*" if not item["read"] else "·")
        surface.text(2, row, marker, C["flame"] if chosen else C["ash"], C["ink"])
        surface.text(4, row, state, C["flame"] if not item["read"] else C["ash"],
                     C["ink"])
        actor = item.get("recipient") if outbound else item["sender"]
        who = render.actor_name(actor, b.get("house"))
        sender_width = min(19, max(12, list_width // 2 - 3))
        surface.text(6, row, _trunc(who, sender_width),
                     C["bone"] if chosen else C["clay"], C["ink"])
        subject_x = 7 + sender_width
        subject = render.letter_summary(item["topic"])
        surface.text(subject_x, row,
                     _trunc(subject, max(0, list_width - subject_x - 1)),
                     C["dim"], C["ink"])
        surface.link(2, row, list_width - 3, 1,
                     f"select:{item['id']}")

    right = divider + 3
    right_width = width - right - 3
    if selected_item is None:
        surface.text(right, 3, "Select a tablet from the pile.",
                     C["ash"], C["ink"])
    elif filter_name == "outbox":
        who = render.actor_name(
            selected_item.get("recipient", "unknown court"), b.get("house"))
        surface.text(right, 2, _trunc(("TO " + who).upper(), right_width),
                     C["bone"], C["ink"])
        subject = render.letter_summary(selected_item["topic"])
        surface.text(right, 3, _trunc(subject, right_width), C["dim"], C["ink"])
        surface.text(
            right, 4, f"sent, turn {selected_item['sent_turn']}",
            C["ash"], C["ink"])
        status = str(selected_item.get("status", "sent — no receipt"))
        surface.text(
            right + max(0, right_width - len(status)), 4,
            status, C["sky"], C["ink"])
        style.rule(surface, right, 6, right_width)
        y = 9 if notice else 8
        body = str(selected_item.get("body") or "No sent copy survives.")
        paragraphs = [" ".join(block.split())
                      for block in body.split("\n\n") if block.strip()]
        for paragraph in paragraphs:
            for line in textwrap.wrap(paragraph, right_width):
                if y >= height - 6:
                    break
                surface.text(right, y, line, C["clay"], C["ink"])
                y += 1
            y += 1
    else:
        who = render.actor_name(selected_item["sender"], b.get("house"))
        surface.text(right, 2, _trunc(who.upper(), right_width),
                     C["bone"], C["ink"])
        subject = render.letter_summary(selected_item["topic"])
        surface.text(right, 3, _trunc(subject, right_width), C["dim"], C["ink"])
        arrival = f"reached your hand, turn {selected_item['received_turn']}"
        surface.text(right, 4, arrival, C["ash"], C["ink"])
        if selected_item.get("answered_turn") is not None:
            turn = selected_item["answered_turn"]
            surface.text(
                right + max(0, right_width - len(f"answered, turn {turn}")),
                4, f"answered, turn {turn}", C["sky"], C["ink"])
        delegated_to = selected_item.get("delegated_to")
        if delegated_to:
            delegate_name = render.actor_name(delegated_to, b.get("house"))
            delegated = f"entrusted to {delegate_name}"
            if selected_item.get("delegated_turn") is not None:
                delegated += f", turn {selected_item['delegated_turn']}"
            surface.text(right, 5, _trunc(delegated, right_width),
                         C["sky"], C["ink"])
        elif selected_item["read"] and delegate_to:
            delegate_name = render.actor_name(delegate_to, b.get("house"))
            surface.text(
                right, 5,
                _trunc(f"[tab] delegate choice: {delegate_name}", right_width),
                C["ash"], C["ink"])
        style.rule(surface, right, 6, right_width)

        if not selected_item["read"]:
            surface.text(right, 9, "THE TABLET IS UNREAD", C["flame"], C["ink"])
            surface.text(right, 11,
                         "Reading it takes two hours of the fortnight.",
                         C["clay"], C["ink"])
            available = b["attention"] if hours_left is None else hours_left
            if available < 2:
                surface.text(right, 13, "There is not light enough left today.",
                             C["ash"], C["ink"])
        else:
            body = render.letter_body(
                selected_item["sender"], selected_item["topic"],
                selected_item["facts"])
            y = 9 if notice else 8
            paragraphs = [" ".join(block.split())
                          for block in body.split("\n\n") if block.strip()]
            for paragraph in paragraphs:
                for line in textwrap.wrap(paragraph, right_width):
                    if y >= height - 8:
                        break
                    surface.text(right, y, line, C["clay"], C["ink"])
                    y += 1
                y += 1
            facts = selected_item.get("facts") or {}
            if facts:
                y = max(y, height - 5 - len(facts))
                style.rule(surface, right, y, right_width)
                y += 1
                for key, value in facts.items():
                    if y >= height - 2:
                        break
                    label = "it says " + key.replace("_", " ")
                    shown = f"{value:,}" if isinstance(value, int) else str(value)
                    surface.text(right, y, _trunc(label, right_width // 2),
                                 C["dim"], C["ink"])
                    surface.text(right + right_width - len(shown), y, shown,
                                 C["bone"], C["ink"])
                    y += 1

    if notice:
        surface.text(right, 7, _trunc(notice, right_width),
                     C["flame"], C["ink"])

    available = b["attention"] if hours_left is None else hours_left
    is_outbox = filter_name == "outbox"
    can_read = bool(
        selected_item and not is_outbox
        and not selected_item["read"] and available >= 2)
    can_answer = bool(
        selected_item and not is_outbox and selected_item["read"]
        and selected_item.get("answered_turn") is None and available >= 2)
    can_work = bool(selected_item and not is_outbox and selected_item["read"])
    is_archived = bool(can_work and selected_item.get("archived"))
    can_delegate = bool(
        can_work and delegate_to
        and selected_item.get("delegated_to") != delegate_to
        and available >= 1)
    style.footer(surface, [
        style.FooterAction("↑", "up", command="Up"),
        style.FooterAction("↓", "down", command="Down"),
        style.FooterAction("u", "unread", enabled=filter_name != "unread",
                           command="view:unread"),
        style.FooterAction("a", "active", enabled=filter_name != "all",
                           command="view:all"),
        style.FooterAction("v", "filed", enabled=filter_name != "archived",
                           command="view:archived"),
        style.FooterAction("o", "outbox", enabled=filter_name != "outbox",
                           command="view:outbox"),
    ], y=height - 3, x=2, width=width - 4)
    style.footer(surface, [
        style.FooterAction("enter", "read", enabled=can_read),
        style.FooterAction(
            "r", "answer", enabled=can_answer,
            command=f"reply:{selected_item['id']}" if selected_item else ""),
        style.FooterAction(
            "c", "compare", enabled=can_work,
            command=f"compare:{selected_item['id']}" if selected_item else ""),
        style.FooterAction(
            "d", "delegate", enabled=can_delegate,
            command=(
                f"delegate:{selected_item['id']}:{delegate_to}"
                if selected_item else "")),
        style.FooterAction(
            "x", "restore" if is_archived else "archive",
            enabled=can_work,
            command=(
                f"{'restore' if is_archived else 'archive'}:"
                f"{selected_item['id']}" if selected_item else "")),
        style.FooterAction("esc", "Hall"),
    ], y=height - 2, x=2, width=width - 4)
    return surface.interactive()
