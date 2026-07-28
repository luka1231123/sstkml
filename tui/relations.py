"""Foreign relations as an inspectable, scrollable ledger.

This page contains only what the court presently believes.  A relationship is
not a live view of a foreign court: the words and figures here are the latest
claims that have reached Ugarit.
"""
from __future__ import annotations

from tui import render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def compose(b: dict, selected: str = "", scroll: int = 0,
            width: int = 92, height: int = 32,
            notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="RELATIONS",
                note="[esc] close", drop=False)
    style.notice(surface, 2, 1, width - 4, notice)
    relations = list(b.get("relations", []))
    if not any(item["other"] == selected for item in relations):
        selected = relations[0]["other"] if relations else ""
    chosen = next(
        (item for item in relations if item["other"] == selected), None)

    list_width = min(48, max(38, width // 2))
    for y in range(2, height - 2):
        surface.put(list_width, y, "│", C["faint"], C["ink"])
    surface.text(2, 2, "court / correspondent", C["gold"], C["ink"])
    surface.text(28, 2, "regard", C["gold"], C["ink"])
    surface.text(39, 2, "unanswered", C["gold"], C["ink"])

    room = max(1, height - 6)
    scroll = max(0, min(scroll, max(0, len(relations) - room)))
    for offset, relation in enumerate(relations[scroll:scroll + room]):
        y = 4 + offset
        active = relation["other"] == selected
        marker = ">" if active else " "
        name = render.actor_name(relation["other"], b.get("house"))[:23]
        surface.text(2, y, marker, C["flame"] if active else C["ash"], C["ink"])
        surface.text(4, y, name, C["bone"] if active else C["clay"], C["ink"])
        surface.text(28, y, relation["esteem"][:10],
                     C["flame"] if active else C["dim"], C["ink"])
        surface.text(42, y, str(relation["unanswered"]),
                     C["blood"] if relation["unanswered"] else C["ash"],
                     C["ink"])
        surface.link(2, y, list_width - 3, 1,
                     f"select:{relation['other']}")

    right = list_width + 3
    available = width - right - 3
    if chosen is None:
        surface.text(right, 3, "No foreign relationship is recorded.",
                     C["ash"], C["ink"])
    else:
        name = render.actor_name(chosen["other"], b.get("house"))
        surface.text(right, 2, name.upper()[:available], C["bone"], C["ink"])
        surface.text(right, 3,
                     f"at {chosen['place'].replace('_', ' ')}"[:available],
                     C["sky"], C["ink"])
        style.rule(surface, right, 5, available)
        rows = (
            ("their regard", chosen["esteem"]),
            ("our standing claim", chosen["status_claim"]),
            ("their claimed standing", chosen["their_status_claim"]),
            ("obligation on the tablets", f"{chosen['obligation']:,}"),
            ("last gift from us", f"{chosen['last_gift_from_us']:,}"),
            ("last gift from them", f"{chosen['last_gift_from_them']:,}"),
            ("best rival gift reported",
             f"{chosen['best_known_rival_gift']:,}"),
            ("letters awaiting answer", str(chosen["unanswered"])),
        )
        y = 7
        for label, value in rows:
            surface.text(right, y, label[:available], C["dim"], C["ink"])
            y += 1
            surface.text(right + 2, y, str(value)[:max(0, available - 2)],
                         C["clay"], C["ink"])
            y += 2
        patron = chosen.get("seeking_patron")
        if patron is not None and y < height - 3:
            state = "seeking another patron" if patron else "not seeking a patron"
            surface.text(right, y, state[:available],
                         C["blood"] if patron else C["ash"], C["ink"])

    style.footer(surface, (
        style.FooterAction("↑", "previous"),
        style.FooterAction("↓", "next"),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 4)
    return surface.interactive()
