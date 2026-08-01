from tui import style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


def compose(item: dict, width: int = 58, height: int = 22) -> InteractiveScreen:
    surface = Surface(width, height)
    title = str(item.get("name") or item.get("id") or "RECORD").upper()
    style.panel(surface, 0, 0, width, height, title=title, drop=False)
    y = 3
    for key, value in item.items():
        if key == "name" or isinstance(value, (dict, list, tuple)):
            continue
        surface.text(3, y, str(key).replace("_", " ")[:18], C["dim"], C["ink"])
        surface.text(23, y, str(value)[:max(0, width - 26)], C["clay"], C["ink"])
        y += 1
        if y >= height - 3:
            break
    style.footer(surface, (style.FooterAction("Esc", "close"),))
    return surface.interactive()
