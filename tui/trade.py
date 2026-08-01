from tui import style, workbench
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
VIEWS = ("exchange", "movements", "routes", "orders")


def compose(b: dict, width: int = 72, height: int = 24,
            notice: str = "", view: str = "exchange") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="TRADE", drop=False)
    workbench.tabs(surface, 2, 2, width,
                   tuple((name, name.title()) for name in VIEWS), view)
    trade = b.get("trade", {})
    y = 5
    if view == "exchange":
        surface.text(3, y, f"grain price  {trade.get('grain_price', 0):,}", C["barley"], C["ink"])
        y += 2
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
        surface.text(3, y, str(name)[:max(8, width // 2 - 4)], C["clay"], C["ink"])
        surface.text(width // 2, y, str(value)[:max(0, width // 2 - 3)], C["sky"], C["ink"])
        if view in {"exchange", "movements", "routes"}:
            surface.link(2, y, width - 4, 1, f"trade:open:{view}:{index}")
        y += 1
    style.notice(surface, 3, height - 3, width - 6, notice)
    style.footer(surface, (
        style.FooterAction("Tab", "view"), style.FooterAction("f", "finance"),
        style.FooterAction("r", "requisition"), style.FooterAction("e", "exempt"),
        style.FooterAction("<>", "tax"), style.FooterAction("g", "escort"),
        style.FooterAction("c", "close"), style.FooterAction("a/o/p", "write"),
        style.FooterAction("Esc", "close")))
    return surface.interactive()
