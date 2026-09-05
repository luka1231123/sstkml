"""What the king's officers can reasonably put before him (UI/UX spec 20).

This module reads Belief dictionaries only. It may interpret visible trends and
deadlines, but it must never receive World or recover a hidden truth. Advice is
therefore fallible in exactly the same places as the reports it is based on.

Two kinds of thing appear here, and the specification treats them differently.
A **concern** is an exception -- a figure that moved, a docket that is long, a
post nobody holds -- and the Hall may state one every fortnight, because it is
a fact. A **suggestion** is advice, and advice may only appear attributed to a
named person who is allowed to be wrong. `Do: send grain` printed in the
palace's own voice made the game sound like it knew the answer, which is the
one thing it must never claim (Law 4, D19).

So every concern names its speaker, and the speaker is the officer whose post
the matter belongs to: the granary's keeper on the grain, the physician on the
sickness. When the post is vacant the advice comes from the king's scribe
instead, and says the post is empty -- which is not a caveat but the most
useful thing on the row.
"""
from __future__ import annotations

import dataclasses

from tui import render


# The king's own scribe. He speaks for anything that has no other officer, and
# he is a person with a name rather than the interface clearing its throat.
SCRIBE = "Yabninu"


@dataclasses.dataclass(frozen=True)
class Concern:
    id: str
    severity: int
    title: str
    reason: str
    suggestion: str
    destination: str
    order_prompt: str = ""
    # Who says the suggestion, and what he is going on. Never blank on a
    # concern that carries a suggestion: see `concerns` below, which asserts it.
    speaker: str = SCRIBE
    basis: str = ""

    def said(self) -> str:
        """The suggestion as a line that names its author.

        The specification forbids an unattributed imperative. This is the only
        form the Hall prints, so there is nowhere for one to come back.
        """
        if not self.suggestion:
            return ""
        return f"{self.speaker}: {self.suggestion}"


def speaker_for(b: dict, kind: str) -> tuple[str, bool]:
    """The head of the institution of this kind, and whether the post is held.

    Belief carries the head's id, not his name, and a post can stand empty --
    which is exactly when the player most needs to know who is not watching it.
    """
    for inst in b.get("institutions", []):
        if inst.get("kind") != kind:
            continue
        head = inst.get("head")
        if not head:
            return SCRIBE, False
        return render.actor_name(head, b.get("house")), True
    return SCRIBE, False


def _from(b: dict, kind: str, held: str, vacant: str) -> tuple[str, str]:
    """Speaker and basis, worded for whether anyone holds the post."""
    who, filled = speaker_for(b, kind)
    return who, (held if filled else vacant)


def _unread(b: dict) -> Concern | None:
    unread = [item for item in b.get("stack", []) if not item["read"]]
    if not unread:
        return None
    oldest = max(unread, key=lambda item: (item["age"], item["received_turn"]))
    age = oldest["age"]
    who = render.actor_name(oldest["sender"], b.get("house"))
    waited = ("just arrived" if age == 0 else
              f"has waited {age} fortnight{'s' if age != 1 else ''}")
    speaker, basis = _from(
        b, "archive",
        "he keeps the tablets and knows what is on the pile",
        "no one keeps the tablet house; the scribe counted the pile himself")
    return Concern(
        "unread", min(9, 4 + age), f"{len(unread)} unread tablets",
        f"The oldest, from {who}, {waited}.",
        "open the Inbox and read what has waited longest.", "stack",
        speaker=speaker, basis=basis)


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
    speaker, basis = _from(
        b, "garrison",
        "he counted the men who went",
        "no one holds the garrison; the count is the summons' own")
    return Concern(
        "summons", 10, "A muster is not answered",
        f"{short} of the requested {required} men have not gone.",
        "assign a formation in the Muster before the summons falls due.",
        "counsel", prompt, speaker=speaker, basis=basis)


def _raids(b: dict) -> Concern | None:
    threats = list(b.get("threats", ()))
    if not threats:
        return None
    threat = min(threats, key=lambda item: (
        item.get("remaining", 10**9), item.get("id", "")))
    remaining = threat.get("remaining", 0)
    due = ("next fortnight" if remaining == 1 else
           "now" if remaining <= 0 else f"in {remaining} fortnights")
    formation = max(
        b.get("troops", {}).get("formations", []),
        key=lambda item: item["strength"], default=None)
    target = threat.get("target", b.get("seat", "seat"))
    own_gate = target == b.get("seat", "seat")
    occupying = threat.get("intent") == "occupy"
    task = "garrison" if own_gate else "campaign"
    prompt = (
        f"Assign {formation['id']} to {task} at {target}."
        if formation else "Which men can hold the gate?")
    speaker, basis = _from(
        b, "garrison",
        "his watch counted the band on the road",
        "no one holds the garrison; the road watch brought the count")
    return Concern(
        "raid", 10, "An occupying force is coming" if occupying else
        "Raiders are coming",
        f"About {threat.get('people', 0):,} from "
        f"{threat.get('origin', 'abroad')} are due at {target} {due}.",
        ("put a formation on garrison duty before they arrive." if own_gate
         else f"send a formation on campaign to {target} before they arrive."),
        "muster", prompt, speaker=speaker, basis=basis)


def _petitions(b: dict) -> Concern | None:
    petitions = b.get("justice", {}).get("petitions", [])
    if not petitions:
        return None
    oldest = max(petitions, key=lambda item: item["waiting"])
    waiting = oldest["waiting"]
    return Concern(
        "justice", min(9, 3 + waiting), f"{len(petitions)} judgements wait",
        f"The oldest case has stood for {waiting} fortnights.",
        "hear the oldest claim, or give judgement on what is known.",
        "palace", speaker=SCRIBE,
        basis="he keeps the docket and reads the waiting off it")


def _arrears(b: dict) -> Concern | None:
    owing = [group for group in b.get("groups", [])
             if group.get("arrears_weeks", 0) > 0]
    if not owing:
        return None
    worst = max(owing, key=lambda group: group["arrears_weeks"])
    weeks = worst["arrears_weeks"]
    speaker, basis = _from(
        b, "granary",
        "the arrears are his own record of what he did not give out",
        "no one keeps the granary; these are the groups' complaints")
    return Concern(
        "arrears", min(9, 4 + weeks), f"{len(owing)} groups are unpaid",
        f"{worst['name']} have waited {weeks} fortnights.",
        "change an allocation in the Roll.", "counsel",
        "Who is in arrears, and how should the grain allocations change?",
        speaker=speaker, basis=basis)


def _grain(b: dict) -> Concern | None:
    history = b.get("store_history", {}).get("grain", [])
    if len(history) < 4 or history[-1] >= history[-4]:
        return None
    fall = history[-4] - history[-1]
    if fall * 8 < max(1, history[-4]):
        return None
    speaker, basis = _from(
        b, "granary",
        "the figures are his, and he has not been made to count them",
        "no one keeps the granary; the figures are three fortnights of report")
    return Concern(
        "grain", 6, "The granary is falling",
        f"It has lost {render.fmt_good('grain', fall)} in three fortnights.",
        "look at the Stores, and change a ration in the Roll.",
        "counsel", "How should our grain allocations change?",
        speaker=speaker, basis=basis)


def _offices(b: dict) -> Concern | None:
    vacant = [inst for inst in b.get("institutions", []) if not inst.get("head")]
    if not vacant:
        return None
    named = vacant[0]["name"]
    return Concern(
        "offices", 5, f"{len(vacant)} offices stand vacant",
        f"{named.capitalize()} has nobody in charge.",
        "appoint someone in the House, or look at the post in the Alu.",
        "alu", speaker=SCRIBE,
        basis="the posts are on his own roll of the household")


def _institutions(b: dict) -> Concern | None:
    weak = [inst for inst in b.get("institutions", [])
            if inst.get("condition", 1000) < 700]
    if not weak:
        return None
    worst = min(weak, key=lambda inst: inst["condition"])
    qualifier = "" if worst.get("inspected") else " according to its keeper"
    keeper = worst.get("head")
    speaker = (render.actor_name(keeper, b.get("house")) if keeper else SCRIBE)
    basis = (
        "you walked down and saw it yourself" if worst.get("inspected")
        else f"this is what {speaker} reports, and nobody has been to look")
    return Concern(
        "institutions", 5, f"{worst['name'].capitalize()} is failing",
        f"Its condition is {worst['condition']}{qualifier}.",
        "inspect it in the Alu, then decide whether to repair it.", "alu",
        speaker=speaker, basis=basis)


def _oaths(b: dict) -> Concern | None:
    lapsed = [oath for oath in b.get("oaths", []) if oath.get("lapsed")]
    if not lapsed:
        return None
    speaker, basis = _from(
        b, "temple",
        "the oaths were sworn before him and he keeps their terms",
        "no one keeps the temple; the clauses are the tablets' own")
    return Concern(
        "oaths", 8, f"{len(lapsed)} oaths have lapsed",
        "The succession left their parties unbound.",
        "read the clauses in the Oaths, and re-swear what is needed.",
        "oaths", speaker=speaker, basis=basis)


def _plague(b: dict) -> Concern | None:
    plague = b.get("plague", {})
    if not plague.get("sickness_at_seat"):
        return None
    buried = plague.get("burials_at_seat", 0)
    fact = f"{buried} have been buried at the seat." if buried else (
        "The physician will not yet say how many are sick.")
    speaker, basis = _from(
        b, "temple",
        "the burials are counted where the rites are said",
        "no one keeps the temple; these are the burials the quarter reports")
    return Concern(
        "plague", 10, "Sickness is in the lower town", fact,
        "close a road or a harbour from Sickness, or from the World.",
        "counsel", "Which roads or harbours should be quarantined?",
        speaker=speaker, basis=basis)


RULES = (
    _raids, _plague, _summons, _arrears, _petitions, _unread, _grain, _oaths,
    _offices, _institutions,
)


def concerns(b: dict, limit: int = 4) -> list[Concern]:
    """Rank known concerns; stable rule order breaks equal severities.

    The assertion is the specification's rule made structural: a suggestion
    without a speaker cannot leave this function, so no unattributed imperative
    can reach a screen even if a new rule forgets to name one.
    """
    found = [concern for rule in RULES if (concern := rule(b)) is not None]
    for concern in found:
        assert not concern.suggestion or concern.speaker, concern.id
    found.sort(key=lambda concern: -concern.severity)
    return found[:limit]
