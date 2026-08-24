from tui import collection
from tui import dues as due_text
from tui import style, workbench
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
VIEWS = ("exchange", "cargo", "routes", "movements", "dues")


def _due(arrives: int | None, now: int) -> str:
    """A turn number is not a date to anyone sitting in the room."""
    if arrives is None:
        return "none due"
    away = arrives - now
    return ("this fortnight" if away <= 0 else "next fortnight" if away == 1
            else f"in {away} fortnights")


def _lots(count: int) -> str:
    return "nothing at the quay" if not count else (
        f"{count} lot{'s' if count != 1 else ''} at the quay")


def compose(b: dict, width: int = 72, height: int = 24,
            notice: str = "", view: str = "exchange",
            selected: str = "", due_draft: int | None = None,
            scroll: int = 0,
            ) -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="TRADE", drop=False)
    workbench.tabs(surface, 2, 2, width,
                   tuple((name, name.title()) for name in VIEWS), view)
    trade = b.get("trade", {})
    y = 5
    if view == "exchange":
        price = trade.get("grain_price", 0)
        surface.text(3, y, f"grain price  {price:,} copper shekels / 1,000 qa",
                     C["barley"], C["ink"])
        y += 1
        surface.text(3, y, f"             one talent buys up to "
                           f"{3000 * 1000 // max(1, price):,} qa of counted grain",
                     C["dim"], C["ink"])
        y += 1
        surface.text(3, y, "requisition: take cargo now; unrest rises with value",
                     C["flame"], C["ink"])
        y += 2
        movements = trade.get("movements", ())
        carrying = [m for m in movements if m.get("cargo")]
        soonest = min((m["arrives"] for m in movements), default=None)
        rows = [("sea", "open" if b.get("sea_open") else "shut, nothing sails"),
                ("on the water", f"{len(carrying)} cargoes, "
                                 f"{len(movements) - len(carrying)} couriers"
                                 if movements else "nothing is moving"),
                ("next arrival", _due(soonest, b.get("turn", 0))),
                ("routes you know", f"{len(trade.get('routes', ()))} usable"),
                ("cargo in hand", _lots(len(trade.get("cargo", ()))))]
    elif view == "cargo":
        rows = [(c["good"], f"{c['quantity']:,}") for c in trade.get("cargo", ())]
    elif view == "movements":
        rows = [(f"{m['origin']} > {m['destination']}",
                 f"{'cargo' if m.get('cargo') else 'news'} · due {m['arrives']}")
                for m in trade.get("movements", ())]
    elif view == "routes":
        rows = [(r["name"], f"{r['mode']} · {r['strength']}")
                for r in trade.get("routes", ())]
    else:
        rate = b.get("revenue", {}).get("harbour_rate", 0)
        shown = rate if due_draft is None else due_draft
        rows = due_text.facts(
            b, "harbour", shown, draft=due_draft is not None)
    source = {"cargo": trade.get("cargo", ()),
              "movements": trade.get("movements", ()),
              "routes": trade.get("routes", ())}.get(view, ())
    ids = [str(item.get("id") or f"{view}:{index}")
           for index, item in enumerate(source)]
    if ids and selected not in ids:
        selected = ids[0]
    visible = list(enumerate(rows))
    if view in {"cargo", "movements", "routes"}:
        chosen = ids.index(selected) if selected in ids else -1
        page = collection.page(
            len(rows), max(0, height - 10), scroll, chosen)
        visible = list(enumerate(
            page.slice(rows), start=page.start))
        if page.partial:
            label = page.label()
            surface.text(max(3, width - len(label) - 3), 4, label,
                         C["dim"], C["ink"])
    if not rows:
        surface.text(3, y, "none reported", C["ash"], C["ink"])
    for index, (name, value) in visible:
        ref = str(source[index].get("id") or f"{view}:{index}") if index < len(source) else ""
        surface.text(2, y, ">" if ref and ref == selected else " ", C["flame"], C["ink"])
        surface.text(3, y, str(name)[:max(8, width // 2 - 4)], C["clay"], C["ink"])
        surface.text(width // 2, y, str(value)[:max(0, width // 2 - 3)], C["sky"], C["ink"])
        if view in {"cargo", "movements", "routes"}:
            surface.link(2, y, width - 4, 1, f"trade:open:{view}:{index}")
        elif view == "exchange":
            jump = {"on the water": "movements", "next arrival": "movements",
                    "routes you know": "routes", "cargo in hand": "cargo"}.get(name)
            if jump:
                surface.link(2, y, width - 4, 1, f"tab:{jump}")
        y += 1
    style.notice(surface, 3, height - 4, width - 6, notice)
    nav = [style.FooterAction("Tab", "view")]
    if view in {"cargo", "movements", "routes"}:
        nav += [style.FooterAction("↑↓", "choose", command="trade:next"),
                style.FooterAction("Enter", "open")]
    actions = []
    if view in {"exchange", "cargo"}:
        actions += [style.FooterAction("f", "finance"),
                    style.FooterAction("r", "requisition"),
                    style.FooterAction("e", "exempt")]
    elif view == "movements":
        actions += [style.FooterAction("g", "escort"),
                    style.FooterAction("c", "close route")]
    elif view == "routes":
        actions.append(style.FooterAction("c", "close route"))
    elif view == "dues":
        nav += [style.FooterAction("<", "due−"),
                style.FooterAction(">", "due+"),
                    *([style.FooterAction("Enter", "give due")]
                  if due_draft is not None else [])]
        actions += [style.FooterAction("a", "permit"),
                    style.FooterAction("o", "offer"),
                    style.FooterAction("p", "guard")]
    style.footer(surface, nav, y=height - 3, x=2, width=width - 4)
    actions.append(style.FooterAction("Esc", "close"))
    style.footer(surface, actions, y=height - 2, x=2, width=width - 4)
    return surface.interactive(tuple(ids))
