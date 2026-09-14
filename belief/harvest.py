"""Deadline estimates from the calendar, field count and labour roll."""


def plan(b: dict, group_id: str = "", to_fields: bool = True) -> dict:
    land = b.get("land", {})
    wheel = b.get("calendar", {}).get("wheel", ())
    now = b.get("fortnight", 0)
    remaining = 0
    if len(wheel) == 24:
        for offset in range(24):
            if wheel[(now + offset) % 24] != "harvest":
                break
            remaining += 1
    group = next((g for g in b.get("groups", ()) if g["id"] == group_id), {})
    days = group.get("labour_now", 0)
    contributes = group.get("function") == "field_labour"
    change = (0 if contributes or bool(group.get("at_fields")) == to_fields
              else days if to_fields else -days)
    before = land.get("labour_days_this_turn", 0)
    after = max(0, before + change)
    standing = land.get("harvest_pool_standing")
    rate = land.get("rates", {}).get("reap", 0)
    need = (-(-standing // rate) if standing is not None and rate > 0 else None)
    return {"remaining": remaining, "before": before, "after": after,
            "change": change, "standing": standing, "rate": rate,
            "need": need,
            "short_before": max(0, need - before * remaining) if need is not None else None,
            "short_after": max(0, need - after * remaining) if need is not None else None,
            "refusal": ("choose a group" if group_id and not group else
                        "hands can only be sent just before or during harvest"
                        if to_fields and not remaining else "")}


def lines(b: dict, group_id: str = "", to_fields: bool = True) -> list[str]:
    p = plan(b, group_id, to_fields)
    if p["refusal"]:
        return [p["refusal"]]
    if not p["remaining"]:
        return ["No harvest work remains before the next fortnight."]
    if p["need"] is None:
        return ["Harvest capacity unknown: field count or reaping rate missing."]
    return [
        f"Harvest: {p['remaining']} working fortnights remain after today.",
        f"Shared fields: {p['standing']:,} qa / {p['rate']} = {p['need']:,} days (rounded up).",
        f"Labour/fortnight {p['before']:,}→{p['after']:,} person-days.",
        f"Deadline shortfall {p['short_before']:,}→{p['short_after']:,} person-days.",
        f"Estimate · field count + labour roll · turn {b.get('turn', '?')}.",
        "Same crop and strength; hunger, losses and competing claims can change it.",
    ]
