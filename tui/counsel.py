"""ASK: one chat with Yabninu. He answers "what should I do" and "how do I" from the
facts and the help records (ai/counsel.py). Asking is free. A typed order is read back,
and a second Enter confirms it."""
from __future__ import annotations

import textwrap

from tui import style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def reading(said, width: int, height: int, pending=None):
    """(rows of conversation that fit, every wrapped line); a pending order lists its steps instead."""
    items = ([(f"{n}. {step}", "bone") for n, step in enumerate(pending, 1)] if pending else
             [(f"{'you' if who == 'king' else 'Yabninu'}: {what}", "clay" if who == "king" else "bone") for who, what in said])
    lines = []
    for text, tone in items:
        lines += [(line, tone) for line in textwrap.wrap(text, width - 6)] + [("", "clay")]
    return max(1, height - (8 if pending else 10)), lines


def page_count(said, width: int, height: int, pending=None) -> int:
    capacity, lines = reading(said, width, height, pending)
    return max(1, -(-len(lines) // capacity))


def compose(said, hours_left: int, typed: str = "", width: int = 62, height: int = 24,
            pending=None, page: int = 0, pending_cost: int = 0, thinking: bool = False) -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="ASK", drop=False)
    capacity, lines = reading(said, width, height, pending)
    lines += [("Yabninu is thinking...", "flame")] * thinking
    title = (f"ORDER REVIEW · {pending_cost}h · {hours_left}h left" if pending else
             f"Yabninu · {hours_left}h left · questions are free")
    surface.text(3, 2, title[:width - 6], C["sand"], C["ink"])
    pages = max(1, -(-len(lines) // capacity))
    current = max(0, min(page, pages - 1))
    if pending:
        visible = lines[current * capacity:(current + 1) * capacity]
    else:
        end = max(0, len(lines) - current * capacity)
        visible = lines[max(0, end - capacity):end]
    hint = textwrap.wrap("Ask what to do, how to do it, or who someone is. Type an order to give it.", width - 6)
    for offset, (line, tone) in enumerate(visible or [(line, "ash") for line in hint]):
        surface.text(3, 4 + offset, line[:width - 6], C[tone], C["ink"])
    if pages > 1:
        label = (f"[pgup/pgdn] order {current + 1}/{pages}" if pending else f"[pgup/pgdn] history {pages - current}/{pages}")
        surface.text(3, 4 + capacity, label[:width - 6], C["sand"], C["ink"])
        surface.link(3, 4 + capacity, min(len(label), width - 6), 1, "counsel:page")
    if pending:
        surface.text(3, height - 3, "Read every page; nothing ordered yet.", C["ash"], C["ink"])
    else:
        style.bar(surface, 2, height - 5, width - 4, " ASK, OR GIVE AN ORDER · [ctrl-u] clear", fg=C["bone"], bg=C["faint"])
        shown = typed[-(width - 9):]
        style.bar(surface, 3, height - 4, width - 6, " " + shown, fg=C["bone"], bg=C["faint"])
        surface.put(4 + len(shown), height - 4, "█", C["flame"], C["faint"])
    style.footer(surface, [
        style.FooterAction("enter", "confirm" if pending else "ask", enabled=not thinking),
        *([] if pending else [style.FooterAction("tab", "manual")]),
        style.FooterAction("esc", "cancel" if pending else "close"),
    ], y=height - 2, x=2, width=width - 4)
    return surface.interactive()
