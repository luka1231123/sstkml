"""M12 6.19: petitions, four verdicts, delayed correction, and precedent."""
from __future__ import annotations

import dataclasses

from belief.project import project
from engine import actions as A
from engine import archive, justice
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import play, replay, save

SEED = 8814402919


def _world(turns: int = 1):
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _first(world):
    return next(iter(world.court.petitions.values()))


def test_an_authored_petition_enters_the_hall_on_its_turn() -> None:
    world = _world()
    petition = _first(world)
    assert petition.id == "boundary_ashiranu"
    assert petition.waiting == 0
    assert petition.petitioner != petition.against


def test_belief_never_contains_the_truth_before_or_after_a_hearing() -> None:
    world = _world()
    before = project(world)["justice"]["petitions"][0]
    assert before["claim"] == {} and before["counterclaim"] == {}
    assert "truth" not in before
    world, _ = apply(world, A.HearPetition(before["id"]))
    after = project(world)["justice"]["petitions"][0]
    assert after["claim"] and after["counterclaim"]
    assert after["claim_text"] and after["counter_text"]
    assert "truth" not in after
    assert "correct" not in after


def test_hearing_is_idempotently_refused() -> None:
    world = _world()
    petition = _first(world)
    world, events = apply(world, A.HearPetition(petition.id))
    assert any(isinstance(event, A.PetitionHeard) for event in events)
    try:
        apply(world, A.HearPetition(petition.id))
    except ValueError:
        return
    raise AssertionError("a second hearing must not buy the same knowledge twice")


def test_the_king_may_rule_without_hearing() -> None:
    world = _world()
    petition = _first(world)
    world, events = apply(world, A.RulePetition(petition.id, "against"))
    assert petition.id not in world.court.petitions
    assert any(isinstance(event, A.PetitionRuled) for event in events)


def test_a_verdict_has_no_immediate_correctness_signal() -> None:
    world = _world()
    petition = _first(world)
    before = world.court.legitimacy
    world, events = apply(
        world, A.RulePetition(petition.id, justice.true_verdict(petition)))
    assert world.court.legitimacy == before
    assert len(events) == 1 and isinstance(events[0], A.PetitionRuled)
    correction = next(
        scheduled.payload for scheduled in world.schedule
        if isinstance(scheduled.payload, A.JusticeCorrectionDue))
    assert correction.legitimacy_delta == 20


def test_the_correction_arrives_later_as_a_witness_tablet() -> None:
    world = _world()
    petition = _first(world)
    world, _ = apply(world, A.RulePetition(petition.id, "for"))
    before = world.court.legitimacy
    for _ in range(6):
        world, _ = advance(world)
        letters = [
            letter for letter in world.inbox
            if letter.topic == "justice_correction"]
        if letters:
            break
    assert letters, "the witness never wrote"
    assert world.court.legitimacy == before + 20
    assert dict(letters[0].facts)["finding"] == petition.correction
    assert "correct" not in dict(letters[0].facts)


def test_each_substantive_ruling_becomes_a_searchable_precedent() -> None:
    world = _world()
    petition = _first(world)
    world, _ = apply(world, A.RulePetition(petition.id, "split"))
    precedent = world.court.precedents[-1]
    assert precedent.document_ref == f"J-{petition.id}"
    hits = archive.search(world, "justice boundary")
    assert any(document.ref == precedent.document_ref for document in hits)


def test_a_later_case_quotes_the_latest_ruling_of_its_kind() -> None:
    world = _world()
    first = _first(world)
    world, _ = apply(world, A.RulePetition(first.id, "for"))
    later = next(case for case in world.justice_cases
                 if case.id == "boundary_siyannu")
    petitions = dict(world.court.petitions)
    petitions[later.id] = later
    world = dataclasses.replace(
        world, court=dataclasses.replace(world.court, petitions=petitions))
    shown = next(item for item in project(world)["justice"]["petitions"]
                 if item["id"] == later.id)
    assert shown["precedent"]["document_ref"] == f"J-{first.id}"
    assert shown["precedent"]["verdict"] == "for"


def test_a_wrong_contradiction_costs_double_legitimacy() -> None:
    world = _world()
    first = _first(world)
    # Establish "against", then rule "for" in the next boundary case. The
    # later truth is also against, so this is both wrong and contradictory.
    world, _ = apply(world, A.RulePetition(first.id, "against"))
    later = next(case for case in world.justice_cases
                 if case.id == "boundary_siyannu")
    world = dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, petitions={later.id: later}))
    world, _ = apply(world, A.RulePetition(later.id, "for"))
    correction = [
        scheduled.payload for scheduled in world.schedule
        if isinstance(scheduled.payload, A.JusticeCorrectionDue)
        and scheduled.payload.petition_id == later.id
    ][0]
    assert correction.legitimacy_delta == -70


def test_the_four_verdicts_move_the_two_factions_differently() -> None:
    for verdict, expected in {
            "for": (60, -60), "against": (-60, 60),
            "split": (-20, -20), "defer": (-30, -30)}.items():
        world = _world()
        petition = _first(world)
        world, _ = apply(world, A.RulePetition(petition.id, verdict))
        mood = world.court.faction_mood
        assert (mood[petition.faction], mood[petition.against_faction]) == expected


def test_deferring_compounds_and_a_six_fortnight_queue_adds_unrest() -> None:
    world = _world()
    petition = dataclasses.replace(_first(world), waiting=5)
    world = dataclasses.replace(
        world, court=dataclasses.replace(
            world.court, petitions={petition.id: petition}))
    world, _ = apply(world, A.RulePetition(petition.id, "defer"))
    assert world.court.petitions[petition.id].waiting == 6
    before = world.court.unrest
    world, _ = justice.step(world)
    assert world.court.petitions[petition.id].waiting == 7
    assert world.court.unrest == before + 8


def test_justice_actions_save_and_replay_through_a_correction() -> None:
    petition_id = "boundary_ashiranu"
    script = [[A.HearPetition(petition_id),
               A.RulePetition(petition_id, "for")]] + [[] for _ in range(6)]
    world, log, _ = play(SEED, "seat", script)
    path = "/tmp/m12_justice_replay.json"
    save(path, SEED, "seat", len(script), log, world)
    assert state_hash(replay(path)) == state_hash(world)
