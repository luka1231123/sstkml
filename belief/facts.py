"""Facts: what the court knows, measured once and worded plainly (SPEC 3.4).

Reads Belief only, no model. Urgency 3: the king loses something within about
2 fortnights if he does nothing.
"""
from __future__ import annotations

from belief.harvest import plan as harvest_plan
from belief.project import GAUGE_WORDS
from tui import render

_DRY = tuple(word for _, word in GAUGE_WORDS[:2])      # a low or failing river


def _about(n: int) -> int:
    n = abs(n)
    return round(n, 2 - len(str(n))) if n > 99 else n


def _s(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _lasts(n: int) -> str:
    return ("less than 1 fortnight" if n < 1 else "more than a year" if n >= 24
            else "about " + _s(n, "fortnight"))


def _trend(series: list, floor: int = 0) -> str:
    if len(series) < 2:
        return "steady"
    step, slack = series[-1] - series[-2], max(floor, abs(series[-2]) // 100)
    return "rising" if step > slack else "falling" if step < -slack else "steady"


def _keeper(b: dict, kind: str) -> str:
    head = next((i["head"] for i in b["institutions"] if i["kind"] == kind), "")
    return render.actor_name(head, b["house"]) if head else "the scribe"


def _net(b: dict, good: str) -> int:
    """The tick's net movement of a store, without the king's orders since."""
    return sum(flow["qty"] for flow in b["flows"].get(good, ()))


def _moved(b: dict, good: str, rate: int = 0) -> list[str]:
    """The two largest movements of a store, as plain causes; grain in fortnights."""
    out = []
    for f in b["flows"].get(good, ())[:2]:
        qty = abs(f["qty"])
        if f["cause"] == "rations":
            out.append(f"{_s(len(b['groups']), 'group')} eat from the stores")
            continue
        size = (("a little" if qty < rate else f"about {_s(qty // rate, 'fortnight')} of grain")
                if rate else f"about {render.fmt_good(good, _about(qty))}")
        out.append(f"{f['cause']} {'added' if f['qty'] > 0 else 'took'} {size}")
    return out


def _fact(name, say, trend, why, urgency, source, sure, act, exact) -> dict:
    return {"id": name, "say": say, "trend": trend, "why": why[:3],
            "urgency": urgency, "source": source, "sure": sure, "act": act[:3],
            "exact": exact}


def _cover(b: dict) -> tuple[int, int, int, int]:
    """Ration a fortnight, fortnights the grain pays it, fortnights to harvest
    (0 if under way), fortnights of short ration before it. The harvest tick
    reaps before it feeds, so it is not counted."""
    rate = sum(min(g["allocated"], g["size"] * g["entitlement"]) for g in b["groups"])
    lasts = max(0, b["stores"]["grain"] - b["ration_reserved"]) // rate if rate else 24
    wheel, now = b["calendar"]["wheel"], b["fortnight"] - 1
    k = next((n for n in range(len(wheel))
              if wheel[(now + n) % len(wheel)] == "harvest"), 0)
    return rate, lasts, k, max(0, k - 1 - lasts)


def _grain(b: dict) -> dict:
    stores = b["stores"]
    rate, lasts, k, gap = _cover(b)
    urgency = (3 if lasts <= 1 else 2) if gap else 1 if lasts - k < 1 else 0
    river = b["land"]["gauge_says"]
    later = "harvest is under way" if not k else f"harvest comes in {_s(k, 'fortnight')}"
    if gap:
        later += f"; grain falls {_s(gap, 'fortnight')} short"
    if k and river in _DRY:
        later += f"; {river}, so the harvest may be thin"
    why = [later] + (_moved(b, "grain", rate)
                     or [f"{_s(len(b['groups']), 'group')} eat from the stores"])
    act = []
    if gap and rate:
        trade = b["trade"]
        quay = sum(c["available"] for c in trade["cargo"] if c["good"] == "grain")
        buy = (min(quay, stores.get("copper", 0) * 1000 // trade["grain_price"])
               if trade["grain_price"] else 0)
        if buy:
            act.append(f"buy {_lasts(buy // rate)} of grain in Trade [x]")
        act.append("cut rations in Storehouse [t]")
        if b["relations"]:
            act.append("ask a court for aid in Scribes [s]")
    return _fact("grain", f"grain lasts {_lasts(lasts)}",
                 _trend([stores["grain"] - _net(b, "grain"), stores["grain"]]),
                 why, urgency, _keeper(b, "granary"), "counted",
                 act, render.fmt_good("grain", stores["grain"]))


def _labour(b: dict) -> dict:
    groups = b["groups"]
    lph = max(1, next((c["labour_per_head"] for c in b["cohorts"]), 1))
    now, fed, nxt = (sum(g[key] for g in groups)
                     for key in ("labour_now", "labour_if_fed", "next_labour"))
    k, h = _cover(b)[2], harvest_plan(b)
    if k <= 1:
        nxt = fed                  # the harvest reaps before it feeds
    ticks = h["remaining"]         # harvest fortnights still to come, from next
    need = -(-(h["need"] or 0) // (ticks * lph)) if ticks else 0
    have = h["before"] // lph
    lost = sum(g["size"] for g in groups) - nxt // lph
    act = []
    if need > have:
        say = f"the harvest is short of about {_about(need - have):,} men"
        why = [f"the crop needs about {_about(need):,} men for {_s(ticks, 'fortnight')}",
               f"the city has about {_about(have):,}"]
        urgency = 3
        if any(not g["at_fields"] and g["function"] != "field_labour" for g in groups):
            act.append("send hands to the fields in Storehouse [t]")
        exact = f"{h['before'] * ticks:,} of {h['need']:,} days"
    elif lost > 0:
        say = f"hunger keeps about {_about(lost):,} men from work"
        short = sum(g["next_status"] != "full" for g in groups)
        why = [f"rations fall short for {_s(short, 'group')}"]
        urgency = 2 if nxt < now else 1
        cut = any(g["allocated"] < g["size"] * g["entitlement"] for g in groups)
        act = (["raise rations in Storehouse [t]"] if cut else
               ["buy grain in Trade [x]", "change who eats first in Storehouse [t]"])
        exact = f"{now:,} days"
    else:
        say = f"about {_about(now // lph):,} men work for the palace"
        why, urgency, exact = [], 0, f"{now:,} days"
    trend = "falling" if nxt < now else "rising" if nxt > now else "steady"
    return _fact("labour", say, trend, why, urgency, "the palace labour roll",
                 "counted", act, exact)


def _unrest(b: dict) -> dict:
    level, groups = b["unrest"], b["groups"]
    behind = [g for g in groups if g["arrears_qa"]]
    late = [p for p in b["justice"]["petitions"]
            if p["waiting"] > p["grace"] and p["waiting_unrest"]]
    why, act = [], []
    if any(g["revolting"] for g in groups):
        why.append(f"{_s(sum(g['revolting'] for g in groups), 'group')} in revolt")
    if behind:
        weeks = max(g["arrears_weeks"] for g in behind)
        why.append(f"{_s(len(behind), 'group')} behind on rations"
                   + (f", the longest by {_s(weeks, 'fortnight')}" if weeks else ""))
        act.append("pay the arrears in Storehouse [t]")
    if late:
        why.append(f"{_s(len(late), 'judgement')} left waiting too long")
        act.append("hear the judgements in Palace [j]")
    if b["revenue"]["land_rate"] > b["revenue"]["land_base"]:
        why.append("the land due is above custom")
        act.append("lower the land due in Storehouse [t]")
    if b["land"]["corvee_days"]:
        why.append(f"corvée of about {_about(b['land']['corvee_days']):,} days is called")
    trend = _trend(b["meter_history"].get("unrest", []), 10)
    urgency = min(3, sum(level >= floor for floor in (150, 350, 600))
                  + (trend == "rising"))
    rising = ", but unrest is rising" if trend == "rising" else ""
    return _fact("unrest", f"the city is {render.temper(level)}{rising}", trend, why,
                 urgency, "the scribe", "reported", act, f"{level} of 1000")


def _standing(b: dict) -> dict:
    legit, stores = b["legitimacy"], b["stores"]
    why, act = [], []
    for rite in b["rites"]:
        lacking = [g for g, q in sorted(rite["requires"].items()) if stores.get(g, 0) < q]
        if (rite["fortnight"] - b["fortnight"]) % 24 == 1 and lacking:
            why.append(f"the {rite['id'].replace('_', ' ')} rite falls next fortnight "
                       "and the stores cannot pay for it")
            act.append("buy grain in Trade [x]" if lacking[0] == "grain"
                       else f"ask a court for {lacking[0]} in Scribes [s]")
    trend = _trend(b["meter_history"].get("legitimacy", []), 10)
    urgency = 3 if why else min(3, (legit < 500) + (legit < 250) + (trend == "falling"))
    return _fact("standing", f"the king is {render.standing(legit)}", trend, why,
                 urgency, "the scribe", "reported", act, f"{legit} of 1000")


def _metal(b: dict, good: str) -> dict:
    stock, net = b["stores"].get(good, 0), _net(b, good)
    lasts = 0 if not stock else stock // -net if net < 0 else None
    urgency = (0 if lasts is None else 3 if lasts <= 2 else 2 if lasts <= 6
               else 1 if lasts <= 12 else 0)
    say = (f"no {good} is left" if not stock else
           f"{good} stands at about {render.fmt_good(good, _about(stock))}"
           if lasts is None else f"{good} lasts {_lasts(lasts)} at this pace")
    return _fact(good, say, _trend([stock - net, stock]), _moved(b, good), urgency,
                 "the scribe", "counted",
                 [f"ask a court for {good} in Scribes [s]"] if urgency >= 2 else [],
                 render.fmt_good(good, stock))


def facts(b: dict) -> list[dict]:
    """One record per topic, worst first; ties keep the order below."""
    found = [_grain(b), _labour(b), _unrest(b), _standing(b),
             _metal(b, "copper"), _metal(b, "tin")]
    return sorted(found, key=lambda fact: -fact["urgency"])
