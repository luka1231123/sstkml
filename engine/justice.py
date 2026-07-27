"""Petitions, verdicts, delayed correction, and precedent (spec 6.19).

The important boundary is the same one used everywhere else in the game:
World knows what happened; Belief knows what people said.  Hearing a case
reveals both claims and never the truth.  A verdict schedules a witness tablet
two to six fortnights out, and the legitimacy consequence lands with that
tablet.  There is no immediate success sound and no field in Belief called
`correct`.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import stream
from engine.state import Document, Petition, Precedent, World

VERDICTS = ("for", "against", "split", "defer")


def _clamp(value: int, low: int = 0, high: int = 1000) -> int:
    return low if value < low else high if value > high else value


def _amount(values: tuple[tuple[str, int], ...]) -> int:
    return int(dict(values).get("amount", 0))


def amount_for(petition: Petition, verdict: str) -> int:
    """The quantity a verdict awards, used to compare it with hidden truth."""
    claim = _amount(petition.claim)
    counter = _amount(petition.counterclaim)
    if verdict == "for":
        return claim
    if verdict == "against":
        return counter
    if verdict == "split":
        return (claim + counter) // 2
    raise ValueError(f"{verdict!r} is not a ruling on the claim")


def true_verdict(petition: Petition) -> str:
    """Which substantive verdict lies closest to what was actually so."""
    truth = _amount(petition.truth)
    order = ("for", "against", "split")
    return min(order, key=lambda verdict: (
        abs(amount_for(petition, verdict) - truth), order.index(verdict)))


def latest_precedent(world: World, kind: str) -> Precedent | None:
    return next(
        (record for record in reversed(world.court.precedents)
         if record.kind == kind),
        None)


def hear(world: World, petition_id: str) -> tuple[World, list]:
    petition = world.court.petitions.get(petition_id)
    if petition is None:
        raise ValueError(f"no such petition: {petition_id}")
    if petition.heard:
        raise ValueError("both men have already been heard")
    petitions = dict(world.court.petitions)
    petitions[petition_id] = dataclasses.replace(petition, heard=True)
    court = dataclasses.replace(world.court, petitions=petitions)
    return dataclasses.replace(world, court=court), [A.PetitionHeard(petition_id)]


def _shift_mood(world: World, petition: Petition, verdict: str) -> World:
    rules = world.justice_rules
    if verdict == "for":
        petitioner_delta = rules.get("favoured_mood", 60)
        against_delta = rules.get("refused_mood", -60)
    elif verdict == "against":
        petitioner_delta = rules.get("refused_mood", -60)
        against_delta = rules.get("favoured_mood", 60)
    elif verdict == "split":
        petitioner_delta = against_delta = rules.get("split_mood", -20)
    else:
        petitioner_delta = against_delta = rules.get("defer_mood", -30)
    mood = dict(world.court.faction_mood)
    mood[petition.faction] = _clamp(
        mood.get(petition.faction, 0) + petitioner_delta, -1000, 1000)
    mood[petition.against_faction] = _clamp(
        mood.get(petition.against_faction, 0) + against_delta, -1000, 1000)
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, faction_mood=mood))


def _file_verdict(world: World, petition: Petition, precedent: Precedent) -> World:
    from engine import archive

    words = {
        "for": "for the petitioner",
        "against": "against the petitioner",
        "split": "that the claim be divided",
    }
    body = (
        f"In the petition of {petition.petitioner} against "
        f"{petition.against}, concerning {petition.kind}, the king ruled "
        f"{words[precedent.verdict]}.")
    return archive.add(world, Document(
        ref=precedent.document_ref,
        kind="verdict",
        received_turn=world.date.absolute,
        sender=world.court.actor,
        dated_as=f"year {world.date.year}, fortnight {world.date.fortnight}",
        body=body,
        title=f"Verdict: {petition.kind}, {petition.id}",
        tags=("justice", "verdict", petition.kind, petition.id),
    ))


def rule(world: World, petition_id: str, verdict: str) -> tuple[World, list]:
    if verdict not in VERDICTS:
        raise ValueError("verdict must be for, against, split, or defer")
    petition = world.court.petitions.get(petition_id)
    if petition is None:
        raise ValueError(f"no such petition: {petition_id}")

    world = _shift_mood(world, petition, verdict)
    petitions = dict(world.court.petitions)
    if verdict == "defer":
        petitions[petition.id] = dataclasses.replace(
            petition, waiting=petition.waiting + 1)
        world = dataclasses.replace(
            world, court=dataclasses.replace(world.court, petitions=petitions))
        return world, [A.PetitionRuled(petition.id, verdict)]

    previous = latest_precedent(world, petition.kind)
    conflicts = previous is not None and previous.verdict != verdict
    correct = verdict == true_verdict(petition)
    delta = world.justice_rules.get(
        "correct_legitimacy" if correct else "wrong_legitimacy",
        20 if correct else -35)
    # A court forgives an old bad rule being corrected. It does not forgive a
    # new bad rule that contradicts the king's own tablet: that costs double.
    if conflicts and delta < 0:
        delta *= 2

    seq = len(world.court.precedents) + 1
    doc_ref = f"J-{petition.id}"
    precedent = Precedent(
        id=f"precedent{seq}", petition_id=petition.id, kind=petition.kind,
        verdict=verdict, turn=world.date.absolute,
        petitioner=petition.petitioner, against=petition.against,
        document_ref=doc_ref)
    petitions.pop(petition.id)
    court = dataclasses.replace(
        world.court, petitions=petitions,
        precedents=world.court.precedents + (precedent,))
    world = dataclasses.replace(world, court=court)
    world = _file_verdict(world, petition, precedent)

    low = world.justice_rules.get("correction_min", 2)
    high = max(low, world.justice_rules.get("correction_max", 6))
    delay = low + stream(
        world.seed, world.date.absolute, "justice.correction",
        petition.id).int(high - low + 1)
    from engine.relations import schedule
    world = schedule(world, world.date.absolute + delay, A.JusticeCorrectionDue(
        petition.id, petition.witness, petition.correction, delta))
    return world, [A.PetitionRuled(petition.id, verdict, doc_ref)]


def step(world: World) -> tuple[World, list]:
    """Bring authored cases into the hall, age the queue, and price neglect."""
    now = world.date.absolute
    petitions = {
        key: dataclasses.replace(value, waiting=value.waiting + 1)
        for key, value in world.court.petitions.items()}
    events: list = []
    for case in world.justice_cases:
        if (case.arrived_turn != now or case.id in petitions
                or any(record.petition_id == case.id
                       for record in world.court.precedents)):
            continue
        petitions[case.id] = case
        events.append(A.PetitionArrived(
            case.id, case.petitioner, case.against, case.kind))

    threshold = world.justice_rules.get("waiting_unrest_after", 6)
    overdue = sum(1 for petition in petitions.values()
                  if petition.waiting >= threshold)
    unrest_delta = overdue * world.justice_rules.get("waiting_unrest", 8)
    unrest = _clamp(world.court.unrest + unrest_delta)
    court = dataclasses.replace(
        world.court, petitions=petitions, unrest=unrest)
    if unrest != world.court.unrest:
        events.append(A.UnrestChanged(
            unrest - world.court.unrest, "petitions left waiting"))
    return dataclasses.replace(world, court=court), events


def resolve_scheduled(world: World, payloads: list) -> tuple[World, list]:
    """Turn a hidden correction into the only public thing: a witness tablet."""
    events: list = []
    for payload in payloads:
        if not isinstance(payload, A.JusticeCorrectionDue):
            events.append(payload)
            continue
        before_seq = world.letter_seq
        legitimacy = _clamp(
            world.court.legitimacy + payload.legitimacy_delta)
        world = dataclasses.replace(
            world, court=dataclasses.replace(
                world.court, legitimacy=legitimacy))
        from engine import mail
        world = mail.inject_incoming(
            world, payload.witness, world.court.seat, "justice_correction",
            (("case", payload.petition_id), ("finding", payload.finding)))
        # The witness is local, so the tablet reaches the Stack now.
        if world.letter_seq > before_seq:
            events.append(A.LetterArrived(
                f"L{world.letter_seq}", payload.witness,
                "justice_correction"))
    return world, events
