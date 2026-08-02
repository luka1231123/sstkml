"""Small typed dossiers opened from rooms and the Known World."""
from __future__ import annotations

from tui import style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

SCHEMAS = {
    "cohort": (("people", "size"), ("status", "status"),
               ("at", "place"), ("people", "ethnicity"),
               ("task", "task"), ("until", "until")),
    "formation": (("strength", "strength"), ("can replace", "replacement_rate"),
                  ("at", "place"), ("assigned", "assigned"),
                  ("rationed by", "ration_source")),
    "site": (("at", "place"), ("kind", "kind"), ("role", "role"),
             ("capacity", "capacity"), ("condition", "condition"),
             ("kept by", "group_name"), ("in charge", "head")),
    "place": (("standing", "power"), ("rank", "rank"), ("known as", "role"),
              ("harbour", "harbour"), ("certainty", "certainty"),
              ("record dated", "as_of_turn")),
    "route": (("from", "a"), ("to", "b"), ("way", "mode"),
              ("journey", "legs"), ("season", "seasonal"),
              ("open", "availability"), ("strength", "strength")),
    "movement": (("from", "origin"), ("to", "destination"),
                 ("arrives", "arrives"), ("way", "mode"),
                 ("cargo lots", "cargo")),
    "exchange": (("good", "good"), ("quantity", "quantity"),
                 ("price", "price"), ("at", "place")),
    "cargo": (("good", "good"), ("quantity", "quantity"),
              ("from", "origin"), ("to", "destination"),
              ("owner", "owner")),
    "person": (("age", "age_years"), ("health", "health"),
               ("at", "location"), ("office", "post"),
               ("house", "faction"), ("loyalty", "loyalty")),
    "institution": (("at", "place"), ("kind", "kind"),
                    ("condition", "condition"), ("effective", "effective"),
                    ("kept by", "group_name"), ("in charge", "head")),
    "petition": (("kind", "kind"), ("petitioner", "petitioner"),
                 ("against", "against"), ("waiting", "waiting"),
                 ("heard", "heard"), ("present", "present")),
}
TITLES = {"cohort": "COHORT", "formation": "FORMATION", "site": "SITE",
          "place": "PLACE", "route": "ROUTE", "movement": "JOURNEY",
          "exchange": "CARGO", "cargo": "CARGO", "person": "PERSON",
          "institution": "INSTITUTION", "petition": "PETITION"}


def _shown(value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value).replace("_", " ")


def compose(item: dict, width: int = 58, height: int = 22,
            kind: str = "record") -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    name = str(item.get("name") or item.get("id") or TITLES.get(kind, "RECORD"))
    style.panel(surface, 0, 0, width, height,
                title=f"{TITLES.get(kind, kind.upper())} — {name.upper()}",
                note="[esc] close", drop=False)
    schema = SCHEMAS.get(kind, (("status", "status"), ("at", "place"),
                                ("source", "source"), ("dated", "as_of_turn")))
    y = 3
    for label, key in schema:
        if key not in item or item[key] in (None, "", (), []):
            continue
        surface.text(3, y, label[:18], C["dim"], C["ink"])
        surface.text(23, y, _shown(item[key])[:max(0, width - 26)],
                     C["bone"] if isinstance(item[key], int) else C["clay"], C["ink"])
        y += 1
        if y >= height - 5:
            break
    source = item.get("source")
    if source and y < height - 3:
        style.rule(surface, 3, y, width - 6)
        y += 1
        age = item.get("age_turns")
        dated = f" · {age} fortnights old" if isinstance(age, int) else ""
        surface.text(3, y, (f"from {source}{dated}")[:width - 6],
                     C["sky"], C["ink"])
    style.footer(surface, (style.FooterAction("Esc", "close"),))
    return surface.interactive()
