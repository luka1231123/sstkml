from tui import style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def compose(b: dict, width: int = 72, height: int = 24,
            notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="TRADE", drop=False)
    trade = b.get("trade", {})
    surface.text(3, 3, f"grain price reported  {trade.get('grain_price', 0):,}",
                 C["barley"], C["ink"])
    surface.text(3, 5, "CARGO AT THE EXCHANGE", C["gold"], C["ink"])
    row = 7
    for cargo in trade.get("cargo", ())[:max(0, height - 14)]:
        surface.text(5, row, f"{cargo['good']:<18} {cargo['quantity']:>10,}",
                     C["clay"], C["ink"])
        row += 1
    route_x = max(34, width // 2)
    surface.text(route_x, 5, "KNOWN TRADE ROUTES", C["gold"], C["ink"])
    row = 7
    for route in trade.get("routes", ())[:max(0, height - 14)]:
        text = f"{route['name']} · {route['mode']} · {route['strength']}"
        surface.text(route_x, row, text[:max(0, width - route_x - 3)],
                     C["sky"], C["ink"])
        row += 1
    surface.text(3, height - 6, "MOVEMENTS KNOWN FROM THIS EXCHANGE",
                 C["gold"], C["ink"])
    if trade.get("movements"):
        move = trade["movements"][0]
        surface.text(5, height - 4,
                     f"{move['origin']} > {move['destination']} · due {move['arrives']}",
                     C["clay"], C["ink"])
    else:
        surface.text(5, height - 4, "none recorded", C["ash"], C["ink"])
    style.notice(surface, 3, height - 3, width - 6, notice)
    style.footer(surface, (style.FooterAction("f", "finance"),
                           style.FooterAction("r", "requisition"),
                           style.FooterAction("e", "exempt"),
                           style.FooterAction("c", "close"),
                           style.FooterAction(":", "command"),
                           style.FooterAction("Esc", "close")))
    return surface.interactive()
