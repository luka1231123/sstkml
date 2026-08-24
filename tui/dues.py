"""Shared, compact wording for land and harbour due drafts."""
from __future__ import annotations

from belief import dues as due_math


def _change(value: int | None, unit: str = "") -> str:
    if value is None:
        return "unknown"
    if value > 0:
        out = f"+{value:,}"
    elif value < 0:
        out = f"−{abs(value):,}"
    else:
        out = "no change"
    return f"{out} {unit}".rstrip()


def facts(b: dict, target: str, rate: int,
          draft: bool = False) -> list[tuple[str, str]]:
    """Label/value rows used by both rooms that can set a due."""
    quote = due_math.forecast(b, target, rate)
    revenue = b.get("revenue", {})
    status = "DRAFT" if draft else "IN FORCE"
    live = quote["live_rate"]
    shown_rate = (f"{live} → {rate} / 1,000" if draft
                  else f"{rate} / 1,000")

    if target == "land":
        customary = revenue.get(
            "land_base", b.get("land", {}).get("land_due_base", 0))
        rows = [(f"land due · {status}", shown_rate),
                ("customary", f"{customary} / 1,000")]
        if quote["take"] is None:
            rows += [
                ("at harvest", _change(
                    quote["delta_per_1000"], "grain / 1,000 assessed")),
                ("harvest total", "unknown · no crop standing"),
            ]
        else:
            rows += [
                ("this harvest", f"~{quote['harvest_total']:,} grain  "
                                  f"({_change(quote['delta'])})"),
                ("granary after", f"~{quote['grain_after']:,} / roof "
                                  f"{quote['roof_capacity']:,}"),
                ("storage risk", (f"~{quote['unroofed']:,} unroofed"
                                  if quote["unroofed"] else "fits under roof")),
            ]
        pressure = quote["pressure"]
        rows.append(("each fortnight", f"unrest +{pressure}" if pressure
                     else "no due-driven unrest"))
        return rows

    good = revenue.get("harbour_good", "oil")
    customary = revenue.get("harbour_customary", 0)
    low, high = quote["delay_min"], quote["delay_max"]
    mark = "~" if quote["approximate"] else ""
    rows = [
        (f"harbour due · {status}", shown_rate),
        ("customary", f"{customary} / 1,000"),
        ("next clearance", f"{mark}{quote['take']:,} {good}  "
                           f"({_change(quote['delta'])})"),
        ("cargo", f"{mark}{quote['clearable']:,} of "
                  f"{quote['waiting']:,} clears"),
    ]
    if quote["esteem_loss_each"]:
        rows += [
            ("merchants", f"{quote['affected_merchants']} merchants take "
                          "offence"),
            ("new trade loss", (f"up to −{quote['traffic_loss']} in "
                                f"{low}–{high} fortnights"
                                if quote["traffic_loss"] else
                                "none left after pending answers")),
        ]
    else:
        rows += [
            ("merchants", "past offence remains" if rate < live
                          else "no new offence"),
            ("trade traffic", "no new loss"),
        ]
    if quote["pending"]:
        rows.append(("already pending", f"up to −{quote['pending_traffic_loss']} "
                    f"from {quote['pending']} answers"))
    if quote["traffic_loss"] or quote["pending_traffic_loss"]:
        rows.append(("traffic after", f"~{quote['traffic_after']} / 1,000"))
    return rows


def detail(b: dict, target: str, rate: int,
           draft: bool = False) -> list[tuple[str, str]]:
    """Workbench detail lines with the same facts as the Trade room."""
    rows = facts(b, target, rate, draft)
    out = [(rows[0][0].upper(), "gold"),
           (rows[0][1], "flame" if draft else "sky")]
    out += [(f"{label:<16} {value}", "ash") for label, value in rows[1:]]
    out += [("", "ink"),
            (("Enter gives one order" if draft
              else "[< >] drafts by 25"), "flame" if draft else "dim")]
    return out
