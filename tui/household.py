"""The working house: people to place, offices to fill, and the succession."""
from __future__ import annotations

from tui import render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX
POST_KEYS = "abcdefghijklmnopqrstuvwxyz"


def compose(b: dict, picked: str = "", width: int = 86,
            height: int = 34, notice: str = "") -> InteractiveScreen:
    surface = Surface(width, height)
    style.panel(surface, 1, 1, width - 3, height - 3,
                "THE HOUSE", "an office gives a man interests", focus=True)
    style.notice(surface, 3, 2, width - 7, notice)
    house = b.get("house", {})
    members = [p for p in house.get("members", [])
               if p["alive"] and p["id"] != house.get("ruler")]
    members.sort(key=lambda p: (-p["age_years"], p["id"]))
    surface.text(4, 3, "Choose a person, then an office.", C["dim"])
    surface.text(4, 4, "PEOPLE", C["gold"])
    left_width = max(38, width // 2 + 2)
    for index, person in enumerate(members[:9], 1):
        selected = person["id"] == picked
        mark = ">" if selected else " "
        y = 4 + index
        surface.text(
            4, y,
            f"{mark}[{index}] {person['name'][:20]:<20} "
            f"{person['competence'][:14]:<14}",
            C["flame"] if selected else C["clay"])
        surface.link(4, y, left_width - 5, 1, f"person:{person['id']}")

    institutions = b.get("institutions", [])
    right = left_width + 2
    surface.text(right, 4, "POSTS / THE OFFICES", C["gold"])
    for index, inst in enumerate(institutions[:len(POST_KEYS)]):
        key = POST_KEYS[index]
        head = (render.actor_name(inst["head"], house)
                if inst["head"] else "vacant")
        head = head.replace("_", " ")
        surface.text(
            right, 5 + index,
            f"[{key}] {inst['name'][:20]:<20} {head[:18]}",
            C["clay"] if inst["head"] else C["blood"])
        surface.link(right, 5 + index, width - right - 4, 1,
                     f"office:{key}")

    selected = next((person for person in members if person["id"] == picked),
                    members[0] if members else None)
    detail_top = 15
    surface.text(4, detail_top, "THE SELECTED PERSON", C["gold"])
    if selected is None:
        surface.text(4, detail_top + 2, "No adult is available.",
                     C["ash"])
    else:
        claims = []
        if selected.get("heir_rank"):
            claims.append(f"heir {selected['heir_rank']}")
        if selected.get("named_heir"):
            claims.append("NAMED HEIR")
        if selected.get("expecting"):
            claims.append("with child")
        surface.text(
            4, detail_top + 1,
            (f"{selected['name']} · {selected['health']} · "
             f"{selected['loyalty']}")[:left_width - 5],
            C["bone"])
        surface.text(
            4, detail_top + 2,
            (f"at {selected['location'].replace('_', ' ')} · "
             f"{(selected.get('post') or 'at court').replace('_', ' ')}")
            [:left_width - 5],
            C["sky"])
        surface.text(
            4, detail_top + 3,
            (", ".join(claims) or selected.get("agenda") or
             "no special claim is recorded")[:left_width - 5],
            C["dim"])
        interests = ", ".join(selected.get("interests", [])) or "none recorded"
        surface.text(4, detail_top + 4,
                     f"interests: {interests}"[:left_width - 5], C["dim"])

    revenue = b.get("revenue", {})
    omens = house.get("omens", [])
    surface.text(right, 15, "RECENT OMENS", C["gold"])
    if not omens:
        surface.text(right, 17, "none recorded", C["ash"])
    for offset, omen in enumerate(omens[-4:]):
        state = "defied" if omen["defied"] else (
            "published" if omen["published"] else "held")
        surface.text(
            right, 17 + offset,
            f"{omen['id']} · {omen['question']} · {state}"[:width - right - 4],
            C["wine"] if not omen["defied"] else C["ash"])

    surface.text(
        4, height - 4,
        f"[[ / ]] land due {revenue.get('land_rate', 0)}/1000     "
        f"[< / >] harbour due {revenue.get('harbour_rate', 0)}/1000",
        C["barley"])
    style.footer(surface, (
        style.FooterAction("1-9", "choose"),
        style.FooterAction("a-z", "appoint"),
        style.FooterAction("n", "name heir"),
        style.FooterAction("d", "dismiss"),
        style.FooterAction("esc", "close"),
    ), y=height - 2, x=2, width=width - 5)
    return surface.interactive()
