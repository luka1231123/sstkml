"""Complete typed dossiers opened from rooms and the Known World."""
from __future__ import annotations

from belief import catalog
from tui import style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

TITLES = {"cohort": "COHORT", "formation": "FORMATION", "site": "SITE",
          "place": "PLACE", "route": "ROUTE", "movement": "JOURNEY",
          "exchange": "CARGO", "cargo": "CARGO", "person": "PERSON",
          "institution": "INSTITUTION", "petition": "PETITION",
          "project": "WORK", "obligation": "OBLIGATION", "good": "STORE"}


def _shown(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, dict):
        return "; ".join(f"{catalog.label(str(k))} {_shown(v)}"
                         for k, v in value.items()) or "none recorded"
    if isinstance(value, (tuple, list)):
        return "; ".join(_shown(v) for v in value) or "none recorded"
    if value == "":
        return "none recorded"
    return str(value).replace("_", " ")


def _facts(kind: str, item: dict):
    for key in catalog.order(kind, item):
        if key not in item or key in {"name", "source", "as_of_turn", "certainty"}:
            continue
        value = item[key]
        if isinstance(value, dict):
            if not value:
                yield key, catalog.label(key), value
            for subkey, subvalue in value.items():
                yield key, f"{catalog.label(key)} · {catalog.label(str(subkey))}", subvalue
        elif isinstance(value, (tuple, list)):
            if not value:
                yield key, catalog.label(key), value
            for index, subvalue in enumerate(value, 1):
                yield key, f"{catalog.label(key)} · {index}", subvalue
        else:
            yield key, catalog.label(key), value


def compose(item: dict, width: int = 58, height: int = 22,
            kind: str = "record", scroll: int = 0) -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    name = str(item.get("name") or item.get("id") or TITLES.get(kind, "RECORD"))
    style.panel(surface, 0, 0, width, height,
                title=f"{TITLES.get(kind, kind.upper())} — {name.upper()}",
                note="[esc] close", drop=False)
    facts = list(_facts(kind, item))
    room = max(1, height - 8)
    scroll = max(0, min(scroll, max(0, len(facts) - room)))
    y = 3
    for key, label, value in facts[scroll:scroll + room]:
        unit = catalog.UNITS.get(key, "")
        absent = {"arrives": "not travelling", "until": "not assigned",
                  "allowance": "not set"}.get(key, "unknown")
        shown = absent if value is None else _shown(value) + (f" {unit}" if unit else "")
        if key != "id" and isinstance(value, str) and ":" in value:
            shown = value.split(":", 1)[-1].replace("_", " ")
        surface.text(3, y, label[:20], C["dim"], C["ink"])
        surface.text(25, y, shown[:max(0, width - 28)],
                     C["bone"] if isinstance(value, int) else C["clay"], C["ink"])
        y += 1
    source = item.get("source")
    dated = item.get("as_of_turn")
    certainty = item.get("certainty", "")
    provenance = " · ".join(str(v) for v in
                            (source, f"turn {dated}" if dated is not None else "", certainty)
                            if v)
    if provenance:
        surface.text(3, height - 4, provenance[:width - 6], C["sky"], C["ink"])
    style.footer(surface, (style.FooterAction("↑↓", "all facts"),
                           style.FooterAction("Esc", "close")))
    return surface.interactive()
