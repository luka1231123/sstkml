"""What Yabninu can reasonably put before the king on the Hall dashboard.

This module reads Belief dictionaries only. It may interpret visible trends and
deadlines, but it must never receive World or recover a hidden truth. Advice is
therefore fallible in exactly the same places as the reports it is based on.
"""
from __future__ import annotations

import dataclasses

from tui import render


@dataclasses.dataclass(frozen=True)
class Concern:
    id: str
    severity: int
    title: str
    reason: str
    suggestion: str
    destination: str
    order_prompt: str = ""


def _unread(b: dict) -> Concern | None:
    unread = [item for item in b.get("stack", []) if not item["read"]]
    if not unread:
        return None
    oldest = max(unread, key=lambda item: (item["age"], item["received_turn"]))
    age = oldest["age"]
    who = render.actor_name(oldest["sender"], b.get("house"))
    waited = ("just arrived" if age == 0 else
              f"has waited {age} fortnight{'s' if age != 1 else ''}")
    return Concern(
        "unread", min(9, 4 + age), f"{len(unread)} unread tablets",
        f"The oldest, from {who}, {waited}.",
        "Open the Inbox and read what has waited longest.", "stack")


def _summons(b: dict) -> Concern | None:
    summonses = b.get("troops", {}).get("summons", [])
    if not summonses:
        return None
    summons = min(summonses, key=lambda item: item.get("due_turn", 10**9))
    required = summons["required"]
    short = max(0, required - summons["mustered"])
    formation = max(
        b.get("troops", {}).get("formations", []),
        key=lambda item: item["strength"], default=None)
    prompt = (
        f"Assign {formation['id']} to campaign at {summons['place']}."
        if formation else "Which men should answer the muster?")
    return Concern(
        "summons", 10, "A muster is not answered",
        f"{short} of the requested {required} men have not gone.",
        "Order Yabninu to assign the formation before the summons falls due.",
        "counsel", prompt)


def _petitions(b: dict) -> Concern | None:
    petitions = b.get("justice", {}).get("petitions", [])
    if not petitions:
        return None
    oldest = max(petitions, key=lambda item: item["waiting"])
    waiting = oldest["waiting"]
    return Concern(
        "justice", min(9, 3 + waiting), f"{len(petitions)} judgements wait",
        f"The oldest case has stood for {waiting} fortnights.",
        "Hear the oldest claim or give judgement.", "justice")


def _arrears(b: dict) -> Concern | None:
    owing = [group for group in b.get("groups", [])
             if group.get("arrears_weeks", 0) > 0]
    if not owing:
        return None
    worst = max(owing, key=lambda group: group["arrears_weeks"])
    weeks = worst["arrears_weeks"]
    return Concern(
        "arrears", min(9, 4 + weeks), f"{len(owing)} groups are unpaid",
        f"{worst['name']} have waited {weeks} fortnights.",
        "Tell Yabninu how the grain should be allocated.", "counsel",
        "Who is in arrears, and how should the grain allocations change?")


def _grain(b: dict) -> Concern | None:
    history = b.get("store_history", {}).get("grain", [])
    if len(history) < 4 or history[-1] >= history[-4]:
        return None
    fall = history[-4] - history[-1]
    if fall * 8 < max(1, history[-4]):
        return None
    return Concern(
        "grain", 6, "The granary is falling",
        f"It has lost {render.fmt_good('grain', fall)} in three fortnights.",
        "Ask Yabninu to review rations, allocations, and the coming harvest.",
        "counsel", "How should our grain allocations change?")


def _offices(b: dict) -> Concern | None:
    vacant = [inst for inst in b.get("institutions", []) if not inst.get("head")]
    if not vacant:
        return None
    named = vacant[0]["name"]
    return Concern(
        "offices", 5, f"{len(vacant)} offices stand vacant",
        f"{named.capitalize()} has nobody in charge.",
        "Go to the City to inspect the post and its condition.", "city")


def _institutions(b: dict) -> Concern | None:
    weak = [inst for inst in b.get("institutions", [])
            if inst.get("condition", 1000) < 700]
    if not weak:
        return None
    worst = min(weak, key=lambda inst: inst["condition"])
    qualifier = "" if worst.get("inspected") else " according to its keeper"
    return Concern(
        "institutions", 5, f"{worst['name'].capitalize()} is failing",
        f"Its condition is {worst['condition']}{qualifier}.",
        "Inspect it in the City and decide whether to repair it.", "city")


def _oaths(b: dict) -> Concern | None:
    lapsed = [oath for oath in b.get("oaths", []) if oath.get("lapsed")]
    if not lapsed:
        return None
    return Concern(
        "oaths", 8, f"{len(lapsed)} oaths have lapsed",
        "The succession left their parties unbound.",
        "Read the clauses, then order Yabninu to re-swear what is needed.",
        "oaths")


def _plague(b: dict) -> Concern | None:
    plague = b.get("plague", {})
    if not plague.get("sickness_at_seat"):
        return None
    buried = plague.get("burials_at_seat", 0)
    fact = f"{buried} have been buried at the seat." if buried else (
        "The physician will not yet say how many are sick.")
    return Concern(
        "plague", 10, "Sickness is in the lower town", fact,
        "Ask Yabninu which roads or harbours should be closed.", "counsel",
        "Which roads or harbours should be quarantined?")


RULES = (
    _plague, _summons, _arrears, _petitions, _unread, _grain, _oaths,
    _offices, _institutions,
)


def concerns(b: dict, limit: int = 4) -> list[Concern]:
    """Rank known concerns; stable rule order breaks equal severities."""
    found = [concern for rule in RULES if (concern := rule(b)) is not None]
    found.sort(key=lambda concern: -concern.severity)
    return found[:limit]
