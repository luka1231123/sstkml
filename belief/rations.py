"""Ration arithmetic from the court's records, without advancing the world."""


def plan(b: dict, selected: str = "", amount: int | None = None,
         priority: tuple = ()) -> dict:
    by_id = {g["id"]: dict(g) for g in b.get("groups", ())}
    order = tuple(gid for gid in (priority or b.get("priority", ())) if gid in by_id)
    order += tuple(gid for gid in by_id if gid not in order)
    grain = opening = max(0, b.get("stores", {}).get("grain", 0))
    need = 0
    for rank, gid in enumerate(order, 1):
        group = by_id[gid]
        owed = group["size"] * group["entitlement"]
        arrears = group.get("arrears_qa", 0)
        allowance = amount if gid == selected and amount is not None else group["allocated"]
        paid = min(grain, max(0, allowance), owed + min(arrears, owed))
        grain -= paid
        need += owed
        group.update(priority=rank, next_paid=paid,
                     next_short=max(0, owed - paid),
                     next_arrears=max(0, arrears + owed - paid),
                     next_labour=group.get("labour_if_fed" if paid >= owed else "labour_if_short"),
                     next_status="full" if paid >= owed else "none" if not paid else "short")
    return {"groups": [by_id[gid] for gid in order], "remaining": grain,
            "spent": opening - grain, "need": need,
            "coverage": grain // need if need else None}
