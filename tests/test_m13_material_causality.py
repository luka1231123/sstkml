"""M13.0 semantic checks for material disease and human divination."""
from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

from engine import actions as A
from engine import divine, mail, plague
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign

SEED = 8814402919


def _without_authored_import(seed: int = SEED):
    world = load_campaign("seat", seed)
    return dataclasses.replace(
        world, plague=dataclasses.replace(
            world.plague, import_place="", import_turn=-1, import_cases=0))


# The sick place is a neighbouring Alu one land leg away, because only an Alu
# has people (docs/ALU_CLASSIFICATION.md §4). Ma'hadu, which used to stand here,
# is Ugarit's own harbour and keeps no compartments of its own.
SOURCE = "mukish"


def _infected_source(exposure: int = 1000):
    world = _without_authored_import()
    world = dataclasses.replace(
        world, plague=dataclasses.replace(world.plague, exposure=exposure))
    world, _ = plague.begin(world, SOURCE, 8)
    return world


def test_only_an_exposed_modeled_journey_can_seed_another_place():
    no_journey = _infected_source()
    no_journey, _ = advance(no_journey)
    assert no_journey.places["seat"].infected == 0

    journey = _infected_source()
    journey = mail.inject_incoming(
        journey, "sinaranu", SOURCE, "warning", ())
    journey, events = advance(journey)
    assert journey.places["seat"].infected > 0
    assert any(isinstance(event, A.PlagueSpread)
               and event.place_id == "seat" for event in events)


def test_quarantine_holds_the_courier_and_contact_then_lifting_resumes_both():
    world = _infected_source()
    world = mail.inject_incoming(
        world, "sinaranu", SOURCE, "warning", ())
    courier_id = world.letters_in_transit[-1].id
    world, _ = apply(world, A.Quarantine(SOURCE))

    world, events = advance(world)
    held = next(letter for letter in world.letters_in_transit
                if letter.id == courier_id)
    assert held.at_node == SOURCE and held.edge_index == 0
    assert held.disease_exposed is True
    assert world.places["seat"].infected == 0
    assert not any(isinstance(event, A.PlagueSpread) for event in events)

    world, _ = apply(world, A.Quarantine(SOURCE, lift=True))
    world, events = advance(world)
    assert not any(letter.id == courier_id
                   for letter in world.letters_in_transit)
    assert world.places["seat"].infected > 0
    assert any(isinstance(event, A.PlagueSpread)
               and event.place_id == "seat" for event in events)


def test_plague_progress_event_reconciles_every_nonfatal_sir_change():
    world = _infected_source()
    before = world.places[SOURCE]
    world, events = plague.step(world)
    after = world.places[SOURCE]
    progressed = next(
        event for event in events
        if isinstance(event, A.PlagueProgressed)
        and event.place_id == SOURCE)
    assert progressed.new_infections == before.susceptible - after.susceptible
    assert progressed.recovered == after.recovered - before.recovered
    assert A.from_dict(A.to_dict(progressed)) == progressed


def test_competence_changes_evidence_interpretation_not_future_access():
    low_matches = high_matches = 0
    for seed in range(SEED, SEED + 8):
        world = load_campaign("seat", seed)
        evidence = divine.evidence_forecast(world, "harvest", "")
        court = dataclasses.replace(
            world.court, diviner_faction="court", diviner_loyalty=1000)
        low = dataclasses.replace(
            world, court=dataclasses.replace(court, diviner_competence=0))
        high = dataclasses.replace(
            world, court=dataclasses.replace(court, diviner_competence=1000))
        low_matches += (
            divine.consult(low, "harvest", "")[1][0].reported == evidence)
        high_matches += (
            divine.consult(high, "harvest", "")[1][0].reported == evidence)
    assert high_matches > low_matches


def test_retired_offering_accuracy_content_cannot_silently_reactivate():
    path = Path(__file__).parent.parent / "content" / "house.toml"
    tables = tomllib.loads(path.read_text())["tables"]
    assert "divination_accuracy" in tables
    assert "offering_bonus" not in tables
