"""The Hall: resources, doors, and matters in motion."""
from tui import render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
DOORS = (
    ("s", "Scribes", "stack"),
    ("y", "Alu", "alu"),
    ("x", "Trade", "trade"),
    ("t", "Storehouse", "stores"),
    ("m", "Muster", "muster"),
    ("j", "Court", "palace"),
    ("v", "Shrine", "altar"),
    ("w", "World", "world"),
)
BUILT = frozenset(target for _key, _label, target in DOORS)


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"


def _counts(b: dict) -> dict[str, int]:
    plague = b.get("plague", {})
    return {
        "stack": sum(not item.get("read") for item in b.get("stack", ())),
        "alu": len(b.get("projects", ())) + sum(
            not item.get("head") for item in b.get("institutions", ())) + sum(
            c.get("status") in {"displaced", "petitioning"}
            for c in b.get("cohorts", ())),
        "trade": 0,
        "stores": sum(bool(g.get("arrears_weeks")) for g in b.get("groups", ())),
        "muster": len(b.get("troops", {}).get("summons", ())),
        "palace": len(b.get("justice", {}).get("petitions", ())),
        "altar": sum(bool(o.get("lapsed")) for o in b.get("oaths", ())),
        "world": int(bool(plague.get("sickness_at_seat"))),
    }


def _resource(surface: Surface, b: dict, good: str, y: int, width: int) -> None:
    values = b.get("store_history", {}).get(good, ())
    value = b.get("stores", {}).get(good, 0)
    before = (values[-1] if values and values[-1] != value else
              values[-2] if len(values) > 1 else value)
    delta = value - before
    sign = "+" if delta > 0 else ""
    surface.text(3, y, good.upper(), C["gold"], C["ink"])
    surface.text(3, y + 1, _fit(f"{value:,}  {sign}{delta:,}", width),
                 C["bone"], C["ink"])
    surface.text(3, y + 2, "storehouse roll", C["dim"], C["ink"])
    date = b["date"].replace(", former half", " I").replace(", latter half", " II")
    surface.text(3, y + 3, _fit(date, width),
                 C["dim"], C["ink"])


def _motion(b: dict) -> list[str]:
    rows = []
    for move in b.get("trade", {}).get("movements", ()):
        rows.append(f"{move['origin']} > {move['destination']} · due {move['arrives']}")
    for item in b.get("outbox", ()):
        if not item.get("answered"):
            place = item.get("at_node") or item.get("recipient") or "unknown"
            rows.append(f"{item.get('id', 'order')} · {place} · {item.get('status', 'sent')}")
    return rows


def compose(b: dict, width: int = 84, height: int = 28,
            hours_left: int | None = None, notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    hours = b["attention"] if hours_left is None else max(0, hours_left)
    style.bar(surface, 0, 0, width,
              _fit(f" {render.actor_name(b['actor'], b.get('house')).upper()} · {b['date']}", width - 2),
              fg=C["bone"], bg=C["lapis"])
    surface.text(3, 2, f"{hours} of {b['attention_base']} hours remain",
                 C["clay"], C["ink"])
    style.notice(surface, 3, 3, width - 6, notice)

    left = max(24, width // 3)
    centre = max(24, width // 3)
    cx, rx = left, min(width - 22, left + centre)
    for x in (cx, rx):
        for y in range(5, height - 3):
            surface.put(x, y, "│", C["faint"], C["ink"])

    surface.text(3, 5, "BELIEVED STANDING", C["gold"], C["ink"])
    for y, good in zip((7, 11, 15), ("grain", "copper", "tin")):
        _resource(surface, b, good, y, max(8, left - 6))

    surface.text(cx + 2, 5, "PASSAGES", C["gold"], C["ink"])
    counts = _counts(b)
    for row, (key, label, target) in enumerate(DOORS, 7):
        count = counts.get(target, 0)
        suffix = f"  {count}" if count else ""
        text = _fit(f"[{key}]  □  {label}{suffix}", rx - cx - 4)
        surface.text(cx + 2, row, text, C["bone"], C["ink"])
        surface.link(cx + 2, row, len(text), 1, key)

    surface.text(rx + 2, 5, "IN MOTION", C["gold"], C["ink"])
    motion = _motion(b)
    if not motion:
        surface.text(rx + 2, 7, "nothing reported", C["ash"], C["ink"])
    for row, line in enumerate(motion[:max(0, height - 11)], 7):
        surface.text(rx + 2, row, _fit(line, width - rx - 4), C["sky"], C["ink"])

    style.footer(surface, (style.FooterAction("Space", "end fortnight"),
                           style.FooterAction(":", "command"),
                           style.FooterAction("?", "help")))
    return surface.interactive()
