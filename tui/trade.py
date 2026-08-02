from tui import style, workbench
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
VIEWS = ("exchange", "cargo", "routes", "movements", "dues")


def compose(b: dict, width: int = 72, height: int = 24,
            notice: str = "", view: str = "exchange",
            selected: str = "") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="TRADE", drop=False)
    workbench.tabs(surface, 2, 2, width,
                   tuple((name, name.title()) for name in VIEWS), view)
    trade = b.get("trade", {})
    y = 5
    if view == "exchange":
        surface.text(3, y, f"grain price  {trade.get('grain_price', 0):,}", C["barley"], C["ink"])
        y += 2
        rows = [("cargoes recorded", str(len(trade.get("cargo", ())))),
                ("routes recorded", str(len(trade.get("routes", ())))),
                ("movements due", str(len(trade.get("movements", ()))))]
    elif view == "cargo":
        rows = [(c["good"], f"{c['quantity']:,}") for c in trade.get("cargo", ())]
    elif view == "movements":
        rows = [(f"{m['origin']} > {m['destination']}", f"due {m['arrives']}")
                for m in trade.get("movements", ())]
    elif view == "routes":
        rows = [(r["name"], f"{r['mode']} · {r['strength']}")
                for r in trade.get("routes", ())]
    else:
        rate = b.get("revenue", {}).get("harbour_rate", 0)
        rows = [("harbour due", f"{rate}/1000"),
                ("finance / requisition", "crown cargo"),
                ("authorize / offer / protect", "written tablet"),
                ("escort / close", "formation / route")]
    if not rows:
        surface.text(3, y, "none reported", C["ash"], C["ink"])
    for index, (name, value) in enumerate(rows[:max(0, height - 10)]):
        source = {"cargo": trade.get("cargo", ()),
                  "movements": trade.get("movements", ()),
                  "routes": trade.get("routes", ())}.get(view, ())
        ref = str(source[index].get("id") or f"{view}:{index}") if index < len(source) else ""
        surface.text(2, y, ">" if ref == selected else " ", C["flame"], C["ink"])
        surface.text(3, y, str(name)[:max(8, width // 2 - 4)], C["clay"], C["ink"])
        surface.text(width // 2, y, str(value)[:max(0, width // 2 - 3)], C["sky"], C["ink"])
        if view in {"cargo", "movements", "routes"}:
            surface.link(2, y, width - 4, 1, f"trade:open:{view}:{index}")
        y += 1
    style.notice(surface, 3, height - 4, width - 6, notice)
    nav = [style.FooterAction("Tab", "view")]
    if view in {"cargo", "movements", "routes"}:
        nav += [style.FooterAction("↑↓", "choose", command="trade:next"),
                style.FooterAction("Enter", "open")]
    style.footer(surface, nav, y=height - 3, x=2, width=width - 4)
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
        actions += [style.FooterAction("<", "due−"),
                    style.FooterAction(">", "due+"),
                    style.FooterAction("a", "permit"),
                    style.FooterAction("o", "offer"),
                    style.FooterAction("p", "guard")]
    actions.append(style.FooterAction("Esc", "close"))
    style.footer(surface, actions, y=height - 2, x=2, width=width - 4)
    return surface.interactive()
