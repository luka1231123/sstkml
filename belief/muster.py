"""Assignment comparisons from the dated muster roll, never hidden World."""


def defence(formation: dict, task: str) -> int:
    ready = max(0, min(formation.get("strength", 0), formation.get("ready", 0)))
    return ready if task == "garrison" else ready // 2 if task == "watch" else 0


def lines(b: dict, formation_id: str, task: str, place: str) -> list[str]:
    formation = next((f for f in b.get("troops", {}).get("formations", ())
                      if f["id"] == formation_id), None)
    if formation is None:
        return ["Choose a formation from the muster roll."]
    place = place or b.get("seat", "seat")
    name = lambda value: str(value).replace("_", " ")
    ready = max(0, min(formation["strength"], formation.get("ready", 0)))
    old = defence(formation, formation["task"])
    new = defence(formation, task)
    out = [
        f"{formation['name']}: {formation['strength']:,} men; {ready:,} equipped for duty.",
        f"Now: {name(formation['task'])} at {name(formation['place'])}.",
        f"Order: {name(task)} at {name(place)}.",
        "Reassign these men; no new levy or immediate goods payment.",
    ]
    if formation["place"] == place:
        out.append(f"Their defence contribution at {name(place)}: {old:,} → {new:,}.")
    else:
        out.append(f"Their defence contribution: {name(formation['place'])} loses {old:,}; "
                   f"{name(place)} gains {new:,}.")
    out.append("Defence figures are before walls and quarters; watch counts half.")
    for summons in b.get("troops", {}).get("summons", ()):
        target = summons["place"]
        before = summons["mustered"]
        after = before - (ready if formation["task"] == "campaign" and
                          formation["place"] == target else 0)
        after += ready if task == "campaign" and place == target else 0
        if before != after:
            out.append(f"Summons at {name(target)}: {before:,} → {after:,} of "
                       f"{summons['required']:,} men; due turn {summons['due_turn']}.")
    if "harvest" in (formation["task"], task):
        out.append("No additional harvest labour is recorded for this assignment. "
                   "Use the Land roll to send hands to the fields.")
    out.append(f"Muster roll · turn {formation.get('as_of_turn', b.get('turn', '?'))}.")
    return out
