"""The Scribes' Room: triage, read, file, and answer correspondence.

The old screen treated a letter as one large paragraph beside a cramped pile,
then opened a second window to compare it and a third to answer it.  This room
keeps the pile and the clay together.  It separates provenance, matter, claims,
and wording so a ruler can read the important parts before reading every word.
"""
from __future__ import annotations

import textwrap

from ai import replier
from tui import document, render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

VIEWS = (
    ("all", "INBOX"),
    ("archived", "FILED"),
    ("outbox", "SENT"),
    ("records", "RECORDS"),
)


def ordered_items(b: dict, order: list[str] | None = None,
                  filter_name: str = "all") -> list[dict]:
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
    if filter_name == "unread":       # compatibility for older callers
        items = [item for item in items if not item["read"]]
    return items


def _trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def draw_views(surface: Surface, chosen: str, width: int, y: int = 2,
               x: int = 2) -> None:
    """Draw the four stations shared by correspondence and archive views."""
    column = x
    for number, (key, label) in enumerate(VIEWS, 1):
        caption = f" {number} {label} "
        if column + len(caption) >= width - 2:
            break
        here = key == chosen
        surface.text(
            column, y, caption,
            C["ink"] if here else C["clay"],
            C["sand"] if here else C["faint"])
        surface.link(column, y, len(caption), 1, f"view:{key}")
        column += len(caption) + 1


def _shown_fact(key: str, value) -> str:
    label = key.replace("_", " ")
    shown = f"{value:,}" if isinstance(value, int) else str(value)
    return f"{label} {shown}"


def _fact_lines(item: dict, width: int) -> list[str]:
    facts = item.get("facts") or {}
    if not facts:
        return ["no quantity or named term is impressed here"]
    lines: list[str] = []
    current = ""
    for key, value in facts.items():
        part = _shown_fact(str(key), value)
        joined = part if not current else current + "  ·  " + part
        if current and len(joined) > width:
            lines.append(current)
            current = part
        else:
            current = joined
    if current:
        lines.append(current)
    return lines


def _sections(body: str, width: int) -> list[tuple[str, str]]:
    """Return labelled clay lines without pretending the labels are in-world.

    Diplomatic formulae are useful but visually loud.  The first written line
    is shown as the address, the last as the seal/close, and the substance in
    between as the message.  Short notes remain one message rather than being
    over-analysed into empty parts.
    """
    raw = [line.strip() for line in body.splitlines() if line.strip()]
    if not raw:
        return [("MESSAGE", "No legible words survive.")]
    if len(raw) < 3:
        joined = " ".join(raw)
        wrapped = textwrap.wrap(joined, width) or [""]
        return [
            ("MESSAGE" if index == 0 else "", line)
            for index, line in enumerate(wrapped)
        ]

    groups = (
        ("ADDRESS", raw[:1]),
        ("MESSAGE", raw[1:-1]),
        ("SEAL", raw[-1:]),
    )
    lines: list[tuple[str, str]] = []
    for label, source in groups:
        wrapped = textwrap.wrap(" ".join(source), width) or [""]
        lines.extend((label if index == 0 else "", line)
                     for index, line in enumerate(wrapped))
    return lines


def _subject(item: dict) -> str:
    """The one-line matter of a tablet, whoever wrote it.

    A foreign court's answer has no authored summary and must not be given one:
    its subject is the decision it carries, and that is only known once the
    tablet has been read (`tui/document.py`).
    """
    if document.is_answer(item):
        return document.answer_subject(item)
    return render.letter_summary(str(item.get("topic", "message")))


def _dispatch_lines(item: dict, width: int) -> list[tuple[str, str]]:
    """What is known about one sent tablet: its road, and its answer or silence.

    Silence has rows of its own. A tablet that has outlived its expected round
    trip says so here, beside the date it went and the road it went by, because
    that is the whole of what the court knows: an ignored letter and a drowned
    courier read the same from this side (spec 3.2).
    """
    room = max(12, width)
    rows: list[tuple[str, str]] = []
    if item.get("silent"):
        rows.append(("NO ANSWER", "blood"))
        rows += [
            (line, "ash")
            for line in textwrap.wrap(
                "an answer was looked for by turn "
                f"{item.get('expected_reply_turn')}; none has come", room)]
    elif item.get("reply_turn") is not None:
        from tui.composer import term_summary

        rows.append((
            f"an answer reached your hand, turn {item['reply_turn']}", "sand"))
        # Terms offered back, beside the tablet they answer. Wrapped, never
        # summarised: this is the figure the king has to answer next.
        for term in item.get("counter_terms") or ():
            rows += [(line, "bone")
                     for line in textwrap.wrap(term_summary(term), room)]
    travel = int(item.get("travel_turns", 0) or 0)
    if travel:
        rows.append((f"{travel} fortnight(s) each way by this road", "dim"))
    # The road, unless the glance already carries it as an impressed mark.
    route = " › ".join(
        str(place).replace("_", " ") for place in item.get("path") or ())
    if route and "route" not in (item.get("facts") or {}):
        rows += [(line, "sky")
                 for line in textwrap.wrap("by " + route, room)]
    return rows


def _list_state(item: dict, outbound: bool) -> str:
    if outbound:
        if item.get("reply_turn") is not None:
            return "✓"
        # Waiting past its round trip. The mark is the point: the rack shows
        # that the king is waiting, rather than showing nothing at all.
        return "…" if item.get("silent") else "→"
    if item.get("answered_turn") is not None:
        return "✓"
    if item.get("archived"):
        return "§"
    return "◆" if not item.get("read") else "·"


def compose(b: dict, width: int = 100, height: int = 32,
            order: list[str] | None = None, selected: str = "",
            filter_name: str = "all", scroll: int = 0,
            hours_left: int | None = None,
            delegate_to: str = "",
            answered: dict[str, int] | None = None,
            notice: str = "", body_scroll: int = 0,
            focus: str = "rack") -> InteractiveScreen:
    """Compose the pile and a structured reading of the selected tablet."""
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    active_items = ordered_items(b, order, "all")
    archived_items = ordered_items(b, order, "archived")
    inbound_items = active_items + archived_items
    outbox_items = ordered_items(b, order, "outbox")
    unread_count = sum(not item["read"] for item in active_items)
    in_transit = sum(item.get("in_transit", False) for item in outbox_items)
    # Tablets that have outlived their round trip. Counted in the title because
    # waiting is a state the king should be able to see without opening the rack.
    silent = sum(bool(item.get("silent")) for item in outbox_items)
    style.panel(
        surface, 0, 0, width, height,
        title=(
            f"SCRIBES' ROOM — {unread_count} UNREAD · "
            f"{len(archived_items)} FILED · {in_transit} ON THE ROAD"
            + (f" · {silent} UNANSWERED" if silent else "")),
        note="[esc] return to the Hall", drop=False)
    draw_views(surface, filter_name, width)

    list_width = min(36, max(27, width // 3))
    divider = list_width + 1
    for row in range(4, height - 3):
        surface.put(divider, row, "│", C["faint"], C["ink"])

    items = ordered_items(b, order, filter_name)
    selectable = outbox_items if filter_name == "outbox" else inbound_items
    selected_item = next(
        (item for item in selectable if item["id"] == selected), None)
    if selected_item is None:
        selected_item = items[0] if items else None
        selected = selected_item["id"] if selected_item else ""

    rack_focused = focus != "clay"
    style.bar(
        surface, 2, 4, list_width - 2,
        " RACK — ◆ UNREAD  ✓ ANSWERED",
        fg=C["ink"] if rack_focused else C["bone"],
        bg=C["sand"] if rack_focused else C["faint"])
    surface.link(2, 4, list_width - 2, 1, "focus:rack")
    pitch = 2
    room = max(1, (height - 10) // pitch)
    scroll = max(0, min(scroll, max(0, len(items) - room)))
    if not items:
        surface.text(4, 7, "Nothing rests on this rack.",
                     C["ash"], C["ink"])
    for offset, item in enumerate(items[scroll:scroll + room]):
        row = 6 + offset * pitch
        chosen = item["id"] == selected
        outbound = filter_name == "outbox"
        actor = item.get("recipient") if outbound else item.get("sender")
        who = render.actor_name(actor or "unknown hand", b.get("house"))
        age = "" if outbound else (
            "new" if int(item.get("age", 0)) == 0
            else f"{int(item.get('age', 0))}f")
        mark = _list_state(item, outbound)
        surface.text(2, row, ">" if chosen else " ",
                     C["flame"] if chosen else C["ash"], C["ink"])
        surface.text(4, row, mark,
                     C["flame"] if mark == "◆" else C["sky"], C["ink"])
        who_room = list_width - 9 - len(age)
        surface.text(6, row, _trunc(who, who_room),
                     C["bone"] if chosen else C["clay"], C["ink"])
        if age:
            surface.text(divider - len(age) - 2, row, age,
                         C["sky"], C["ink"])
        surface.text(6, row + 1, _trunc(_subject(item), list_width - 8),
                     C["dim"], C["ink"])
        surface.link(2, row, list_width - 1, pitch,
                     f"select:{item['id']}")

    right = divider + 3
    right_width = width - right - 3
    # A shallow field of stylus impressions makes the reading surface clay
    # without putting texture through the words themselves.
    surface.text(right, 3, style.wedge_band(right_width, phase=4),
                 C["shadow"], C["ink"])
    surface.link(right, 4, right_width, max(1, height - 9),
                 "focus:clay")
    style.notice(surface, right, 3, right_width, notice)
    if selected_item is None:
        surface.text(right, 6, "Choose a tablet from the rack.",
                     C["ash"], C["ink"])
    else:
        outbound = filter_name == "outbox"
        actor = (selected_item.get("recipient") if outbound
                 else selected_item.get("sender"))
        who = render.actor_name(actor or "unknown hand", b.get("house"))
        heading = ("TO " if outbound else "FROM ") + who.upper()
        surface.put(right - 2, 4, "▶" if not rack_focused else "·",
                    C["flame"] if not rack_focused else C["ash"], C["ink"])
        surface.text(right, 4, _trunc(heading, right_width),
                     C["bone"], C["ink"])
        surface.text(right, 5, _trunc(_subject(selected_item), right_width),
                     C["sand"], C["ink"])

        if outbound:
            meta = f"sent turn {selected_item.get('sent_turn', '?')}"
            second_meta = str(selected_item.get("status", "no receipt"))
        else:
            standing = str(
                selected_item.get("sender_status") or "standing unknown")
            peers = [
                item for item in inbound_items
                if item.get("sender") == selected_item.get("sender")
                and item.get("topic") == selected_item.get("topic")
            ]
            age = int(selected_item.get("age", 0))
            meta = (
                f"reached your hand, turn "
                f"{selected_item.get('received_turn', '?')}  ·  "
                f"{'newly come' if age == 0 else f'{age} fortnights old'}")
            second_meta = (
                f"{standing.replace('_', ' ')}"
                f"  ·  {len(peers)} in this exchange")
            if selected_item.get("answered_turn") is not None:
                second_meta += (
                    f"  ·  answered, turn "
                    f"{selected_item['answered_turn']}")
        surface.text(right, 6, _trunc(meta, right_width),
                     C["sky"], C["ink"])
        surface.text(right, 7, _trunc(second_meta, right_width),
                     C["dim"], C["ink"])
        style.rule(surface, right, 8, right_width)

        available = b["attention"] if hours_left is None else hours_left
        if not outbound and not selected_item.get("read"):
            seal_width = min(right_width, 44)
            surface.box(right, 10, seal_width, 7, style="single",
                        fg=C["sand"], title="UNBROKEN SEAL")
            surface.text(right + 3, 12, "◆ THE TABLET IS UNREAD",
                         C["flame"], C["ink"])
            surface.text(right + 3, 14,
                         f"[enter] read · 2 hours · {available} remain",
                         C["clay"], C["ink"])
            if available < 2:
                surface.text(right + 3, 15, "Not enough court time remains.",
                             C["ash"], C["ink"])
        else:
            # Three kinds of tablet, three glances. An answer is read for its
            # decision and its terms, a sent copy for its road and whether
            # anything came back, and everything else for the figures on it.
            if document.is_answer(selected_item):
                heading = "THE ANSWER"
                glance = document.answer_lines(
                    selected_item, right_width - 2)
            elif outbound:
                heading = "THE DISPATCH"
                glance = [
                    ("• " + line, "gold")
                    for line in _fact_lines(
                        selected_item, right_width - 2)[:3]
                    if selected_item.get("facts")
                ] + _dispatch_lines(selected_item, right_width - 2)
            else:
                heading = "AT A GLANCE"
                glance = [
                    ("• " + line, "gold")
                    for line in _fact_lines(
                        selected_item, right_width - 2)[:3]]
            surface.text(right, 10, heading, C["bone"], C["ink"])
            fact_y = 11
            for line, tone in glance:
                # The reading of the clay yields room before a term does: a
                # counter the king cannot read in full he cannot answer.
                if fact_y >= height - 6:
                    break
                surface.text(right + 2, fact_y,
                             _trunc(line, right_width - 2), C[tone], C["ink"])
                fact_y += 1
            style.rule(surface, right, fact_y, right_width)
            words_y = fact_y + 1
            surface.text(right, words_y, "WORDS ON CLAY",
                         C["bone"], C["ink"])
            words_y += 2
            # Stored or voiced words if there are any. A foreign court's answer
            # has no authored template, so its recovery reading is built from
            # the decision the engine wrote (`ai/replier.py`).
            body = str(selected_item.get("body") or "")
            if not body and document.is_answer(selected_item):
                body = replier.recovery_text(
                    selected_item, max(24, right_width - 12))
            elif not body:
                body = render.letter_body(
                    selected_item.get("sender", ""),
                    selected_item.get("topic", ""),
                    selected_item.get("facts") or {})
            lines = _sections(body, max(12, right_width - 12))
            reading_room = max(1, height - words_y - 5)
            body_scroll = max(
                0, min(body_scroll, max(0, len(lines) - reading_room)))
            for offset, (label, line) in enumerate(
                    lines[body_scroll:body_scroll + reading_room]):
                y = words_y + offset
                if label:
                    surface.text(right, y, label[:9],
                                 C["dim"], C["ink"])
                surface.text(right + 10, y,
                             _trunc(line, right_width - 10),
                             C["clay"], C["ink"])
            if len(lines) > reading_room:
                shown_to = min(len(lines), body_scroll + reading_room)
                surface.text(
                    right, height - 4,
                    f"↑↓ clay lines "
                    f"{body_scroll + 1}–{shown_to} of {len(lines)}",
                    C["ash"], C["ink"])

            delegated_to = selected_item.get("delegated_to")
            if delegated_to:
                delegate_name = render.actor_name(
                    delegated_to, b.get("house"))
                surface.text(
                    right, height - 5,
                    _trunc(f"entrusted to {delegate_name}", right_width),
                    C["sky"], C["ink"])

    available = b["attention"] if hours_left is None else hours_left
    is_outbox = filter_name == "outbox"
    can_read = bool(
        selected_item and not is_outbox
        and not selected_item.get("read") and available >= 2)
    can_answer = bool(
        selected_item and not is_outbox and selected_item.get("read")
        and selected_item.get("answered_turn") is None and available >= 2)
    can_work = bool(
        selected_item and not is_outbox and selected_item.get("read"))
    is_archived = bool(can_work and selected_item.get("archived"))
    can_delegate = bool(
        can_work and delegate_to
        and selected_item.get("delegated_to") != delegate_to
        and available >= 1)
    delegate_name = (
        render.actor_name(delegate_to, b.get("house"))
        if delegate_to else "nobody")
    delegate_label = "to " + _trunc(delegate_name, 12)
    move_label = "read clay" if not rack_focused else "choose tablet"
    style.footer(surface, [
        style.FooterAction(
            "tab", "focus rack" if not rack_focused else "focus tablet",
            command="focus:toggle"),
        style.FooterAction("↑", move_label, command="nav:up"),
        style.FooterAction("↓", move_label, command="nav:down"),
        style.FooterAction("enter", "break seal", enabled=can_read),
    ], y=height - 3, x=2, width=width - 4)
    style.footer(surface, [
        style.FooterAction(
            "r", "answer here", enabled=can_answer,
            command=f"reply:{selected_item['id']}" if selected_item else ""),
        style.FooterAction(
            "p", "pin beside", enabled=can_work,
            command=f"compare:{selected_item['id']}" if selected_item else ""),
        style.FooterAction(
            "g", delegate_label, enabled=can_delegate,
            command=(
                f"delegate:{selected_item['id']}:{delegate_to}"
                if selected_item else "")),
        style.FooterAction(
            "x", "restore" if is_archived else "file",
            enabled=can_work,
            command=(
                f"{'restore' if is_archived else 'archive'}:"
                f"{selected_item['id']}" if selected_item else "")),
    ], y=height - 2, x=2, width=width - 4)
    return surface.interactive()
