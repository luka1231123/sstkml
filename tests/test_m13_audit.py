"""M13.0 conservation and causal-audit release gates."""
from __future__ import annotations

import dataclasses

from engine.tick import advance
from load import load_scenario
from tools import m13_audit

SEED = 8814402919


def test_the_audit_rejects_an_unexplained_store_mutation() -> None:
    world = load_scenario("ugarit", SEED)
    advanced, events = advance(world)
    stores = dict(advanced.court.stores)
    stores["grain"] = stores.get("grain", 0) + 17
    corrupted = dataclasses.replace(
        advanced, court=dataclasses.replace(advanced.court, stores=stores))
    findings = m13_audit.audit_transition(world, corrupted, events)
    assert any(
        finding.path == "stores.grain"
        and finding.actual - finding.explained == 17
        for finding in findings)


def test_every_place_keeps_population_accounted_for() -> None:
    world = load_scenario("ugarit", SEED)
    for _ in range(32):
        before = world
        world, events = advance(world)
        assert not [
            finding for finding in m13_audit.audit_transition(
                before, world, events)
            if finding.path.endswith((".accounting", ".negative"))
        ]
