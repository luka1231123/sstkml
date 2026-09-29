"""Grain requests begin with a known correspondent and a route."""

from tui import render, workbench, worldmap, collection, style
from tui.grid import INDEX as C, Surface


def courts(b: dict) -> list[dict]:
    routes = worldmap.routes_of(b)
    found = []
    for relation in b.get("relations", ()):
        place, actor = relation.get("place", ""), relation.get("other", "")
        if not place or not actor or place == b.get("seat"):
            continue
        path = worldmap.route_path(b, b.get("seat", ""), place)
        if len(path) == 1:
            continue
        travel = sum(min(max(1, int(r.get("legs", 1))) for r in routes
                         if {r.get("a"), r.get("b")} == {a, z})
                     for a, z in zip(path, path[1:])) if path else None
        found.append({"id": actor, "name": render.actor_name(actor, b.get("house")),
                      "place": place, "path": path, "travel": travel})
    return sorted(found, key=lambda c: (c["travel"] is None, c["travel"] or 0, c["id"]))


def ration(b: dict) -> int:
    return sum(g["size"] * g["entitlement"] for g in b.get("groups", ()))


def horizon(b: dict) -> int:
    """Planning reserve includes court handling and a margin for cargo."""
    route = next((court for court in courts(b) if court['travel'] is not None), None)
    return 2 * route['travel'] + 4 if route else 6


def compose(b: dict, width: int, height: int, selected: str, quantity: int,
            scroll: int, notice, hours: int, views, labels=None):
    known = courts(b)
    chosen = next((c for c in known if c["id"] == selected), next(iter(known), None))
    surface = Surface(width, height)
    style.panel(surface, 0, 0, width, height, title="TRADE — GRAIN RELIEF", drop=False)
    workbench.tabs(surface, 2, 2, width, tuple((v, (labels or {}).get(v, v.title()))
                                              for v in views), "relief")
    def line(y, text, tone="clay"):
        surface.text(3, y, text[:max(1, width - 6)], C[tone], C["ink"])
    meals = quantity / max(1, ration(b))
    duration = f"{meals:g} fortnight" + ('' if meals == 1 else 's')
    line(4, f"Ask: {duration} of palace rations · {quantity:,} qa grain", "gold")
    line(5, "[ ] adds/removes one fortnight · choose a court below", "dim")
    room = max(1, height - 20)
    pick = known.index(chosen) if chosen else -1
    page = collection.page(len(known), room, scroll, pick)
    for row, item in enumerate(page.slice(known), 6):
        delay = f"{2 * item['travel'] + 1} fn" if item["travel"] is not None else "no route"
        label = ("> " if item == chosen else "  ") + item["name"]
        line(row, label[:max(1, width - 18)] + " · " + delay)
        surface.link(2, row, width - 4, 1, "pick:" + item["id"])
    if not known:
        line(6, "No foreign correspondent is known.")
    y = 6 + room
    line(y, page.label() if page.partial else "Known court and route tablets", "dim")
    if chosen and chosen["travel"] is not None:
        due = b.get("turn", 0) + 2 * chosen["travel"] + 1
        line(y + 1, f"Reply ~turn {due}: {chosen['travel']} out + 1 at court + {chosen['travel']} back.", "sky")
        line(y + 2, "Route: " + " > ".join(chosen["path"]), "dim")
    else:
        line(y + 1, "No known courier route. Consult the World route tablet.", "sky")
    line(y + 3, "Asking lowers their esteem. Grain sent is a loan:", "flame")
    line(y + 4, "repay in 12 fortnights by gift, or they send raiders.")
    line(y + 5, "Want to pay? Market buys local grain with copper.", "dim")
    line(y + 6, "Enter prepares a letter. Edit and seal it in Scribes.", "sand")
    import registry
    cost = registry.BY_ID["dispatch_letter"].cost
    line(y + 7, f"Draft: free · sealing: {cost} hours · you have {hours}.", "dim")
    style.notice(surface, 3, height - 4, width - 6, notice)
    style.footer(surface, [style.FooterAction("tab", "view"),
                           style.FooterAction("↑↓", "court"),
                           style.FooterAction("[ ]", "amount")],
                 y=height - 3, x=2, width=width - 4)
    style.footer(surface, [style.FooterAction("enter", "draft grain request",
                            command="relief:draft", enabled=bool(chosen and chosen["path"] and quantity > 0)),
                           style.FooterAction("esc", "close")],
                 y=height - 2, x=2, width=width - 4)
    return surface.interactive(tuple(c["id"] for c in known))
