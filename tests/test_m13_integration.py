"""M13.0 integration gates shared by the simulation, UI, and session layers."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from belief.project import project
from engine import archive
from engine.tick import advance
from load import load_campaign
from session import SAVE_VERSION, load_session, save
from tools.m13_benchmark import DEFAULT_TURNS, measure, over_budget
from tui import document, palace, plague as plague_page
from tui.grid import plain_text

SEED = 8814402919


def _world(turns: int = 8):
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _events = advance(world)
    return world


def test_archive_batch_is_idempotent_and_keeps_inbox_order() -> None:
    world = _world()
    before = tuple(document.ref for document in world.documents)
    filed = archive.file_letters(world, world.inbox)
    again = archive.file_letters(filed, world.inbox)
    assert filed.documents == again.documents
    assert tuple(document.ref for document in filed.documents[:len(before)]) == before
    refs = [document.ref for document in filed.documents]
    assert len(refs) == len(set(refs))


def test_m13_save_boundary_is_versioned_and_round_trips() -> None:
    world = _world(4)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "nested" / "campaign.json"
        save(path, SEED, "seat", world.date.absolute, [], world,
             hours_left=7)
        payload = json.loads(path.read_text())
        assert payload["version"] == SAVE_VERSION == 17
        loaded, metadata = load_session(path)
        assert loaded == world
        assert metadata["chosen_alu"] == "seat"
        assert metadata["hours_left"] == 7
        assert not path.with_suffix(".json.tmp").exists()


def test_existing_belief_has_intentional_relations_and_plague_pages() -> None:
    b = project(_world())
    relation_text = plain_text(palace.compose(b, view="relations",
                                              width=98, height=36))
    plague_text = plain_text(plague_page.compose(b))
    assert "RELATIONS" in relation_text
    assert "obligation on the tablets" in relation_text
    assert "SICKNESS AND CLOSURES" in plague_text
    assert "burials reported" in plague_text


def test_stores_and_muster_do_not_drop_their_decision_records() -> None:
    b = project(_world())
    stores = plain_text(document.stores(b))
    muster = plain_text(document.muster(b))
    assert "bronze in use" in stores
    assert "melt ledger" in stores
    assert "formation / summons" in muster
