"""Player-known prices and costs for a drafted due.

The forecast never runs the future simulation. It applies a candidate rate to
the crop and cargo already reported in Belief, and keeps delayed responses at
their known range rather than revealing their seeded date.
"""
from __future__ import annotations


def _rate(value: int) -> int:
    return max(0, min(1000, int(value)))


def forecast(belief: dict, target: str, rate: int) -> dict:
    """Return the known bargain behind a candidate land or harbour rate."""
    rate = _rate(rate)
    revenue = belief.get("revenue", {})
    basis = belief.get("forecast_basis", {}).get(target, {})

    if target == "land":
        live = _rate(revenue.get(
            "land_rate", belief.get("land", {}).get("land_due_rate", 0)))
        base = _rate(revenue.get(
            "land_base", belief.get("land", {}).get("land_due_base", 0)))
        divisor = max(1, int(basis.get("unrest_divisor", 4)))
        assessable = basis.get("assessable")
        # Households take their share first and the crown keeps the remainder.
        # This mirrors farm.divide's rounding; `assessable * rate // 1000` can
        # underquote the crown by one even before household apportionment.
        take = (None if assessable is None else max(0, assessable)
                - max(0, assessable) * (1000 - rate) // 1000)
        live_take = (None if assessable is None else max(0, assessable)
                     - max(0, assessable) * (1000 - live) // 1000)
        grain = max(0, int(basis.get(
            "grain", belief.get("stores", {}).get("grain", 0))))
        roof = basis.get("roof_capacity")
        unroofed = (None if take is None or roof is None else
                    max(0, grain + take - max(0, int(roof))))
        already = max(0, int(basis.get("already_taken", 0)))
        return {
            "target": target,
            "rate": rate,
            "live_rate": live,
            "take": take,
            "harvest_total": None if take is None else already + take,
            "delta": None if take is None else take - live_take,
            "delta_per_1000": rate - live,
            "pressure": max(0, rate - base) // divisor,
            "unroofed": unroofed,
            "roof_capacity": roof,
            "grain_after": None if take is None else grain + take,
            "already_taken": already,
            "approximate": True,
        }

    if target != "harbour":
        raise ValueError(f"unknown due account: {target}")

    live = _rate(revenue.get("harbour_rate", 0))
    customary = _rate(revenue.get("harbour_customary", 0))
    assessment = tuple(
        (str(item[0]), max(0, int(item[1])))
        for item in basis.get("assessment", ()))

    def take(at: int) -> int:
        return sum(quantity * at // 1000 for _lot, quantity in assessment)

    old_excess = max(0, live - customary)
    new_excess = max(0, rate - customary)
    esteem = max(0, new_excess // 20 - old_excess // 20)
    merchants = max(0, int(basis.get("merchant_count", 0)))
    affected = merchants if esteem else 0
    traffic_each = max(0, int(basis.get("traffic_loss_per_esteem", 3)))
    traffic = max(0, min(1000, int(revenue.get("harbour_traffic", 0))))
    pending_nominal = max(0, int(basis.get("pending_traffic_loss", 0)))
    new_nominal = esteem * traffic_each * affected
    pending_loss = min(traffic, pending_nominal)
    total_loss = min(traffic, pending_nominal + new_nominal)
    return {
        "target": target,
        "rate": rate,
        "live_rate": live,
        "take": take(rate),
        "delta": take(rate) - take(live),
        "delta_per_1000": rate - live,
        "clearable": sum(quantity for _lot, quantity in assessment),
        "waiting": max(0, int(basis.get("waiting", 0))),
        "esteem_loss_each": esteem,
        "affected_merchants": affected,
        "traffic_loss": total_loss - pending_loss,
        "pending_traffic_loss": pending_loss,
        "total_traffic_loss": total_loss,
        "traffic": traffic,
        "traffic_after": traffic - total_loss,
        "delay_min": max(0, int(basis.get("delay_min", 3))),
        "delay_max": max(0, int(basis.get("delay_max", 6))),
        "pending": max(0, int(basis.get("pending", 0))),
        # Cargo and staffing can change before the next clearance even after a
        # royal inspection. The arithmetic is exact on today's report; the
        # future take never is.
        "approximate": True,
    }
