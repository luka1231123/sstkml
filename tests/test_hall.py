"""M11: the hall (D33, D34).

The hub, and the test of whether "state embodied as people" actually works —
so most of these assert on who is standing in the room and why, not on layout.
Headless throughout: `compose` returns a `Screen` and no toolkit is imported.
"""
from __future__ import annotations

import dataclasses

from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from tui import hall
from tui.grid import INDEX, plain_text, pure_ascii

SEED = 8814402919


def _with_group(world, key, group):
    """Swap one dependent group, which is a Mapping on the court."""
    dependents = dict(world.court.dependents)
    dependents[key] = group
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, dependents=dependents))


def _belief(turns: int = 6):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world, project(world)


# --- people, not counters ----------------------------------------------------

def test_an_unread_tablet_puts_a_courier_in_the_room():
    _, b = _belief(6)
    unread = [item for item in b["stack"] if not item["read"]]
    assert unread
    couriers = [p for p in hall.waiting(b) if p["who"].startswith("a courier")]
    assert len(couriers) == len(unread)


def test_reading_the_tablet_sends_the_courier_away():
    world, b = _belief(6)
    letter = next(item for item in b["stack"]
                  if not item["read"] and item["topic"] != "great_king_demand")
    before = len(hall.waiting(b))
    world, _ = apply(world, A.ReadLetter(letter["id"]))
    assert len(hall.waiting(project(world))) == before - 1


def test_reading_the_demand_replaces_the_courier_with_the_herald():
    """The summons is bound from the day the courier handed the tablet over and
    is hidden until it is read (D32). So opening this one tablet does not empty
    the hall -- it changes who is standing in it, which is the point."""
    world, b = _belief(6)
    demand = next(item for item in b["stack"]
                  if item["topic"] == "great_king_demand" and not item["read"])
    assert not [p for p in hall.waiting(b) if "herald" in p["who"]]
    world, _ = apply(world, A.ReadLetter(demand["id"]))
    after = hall.waiting(project(world))
    herald = next(p for p in after if "herald" in p["who"])
    assert herald["fact"] == "0 have gone"
    assert not [p for p in after
                if p["who"].startswith("a courier")
                and "Carchemish" in p["who"]]


def test_arrears_put_a_named_man_in_the_hall_and_he_is_named():
    """Spec 6.3's face of a cut. The group is a line in a ledger; the man who
    comes to stand in front of the king has a name."""
    world, _ = _belief(4)
    key = next(iter(world.court.dependents))
    group = world.court.dependents[key]
    starved = dataclasses.replace(
        group, arrears=5 * group.size * group.entitlement)
    b = project(_with_group(world, key, starved))
    assert next(g for g in b["groups"] if g["id"] == key)["arrears_weeks"] == 5
    him = next(p for p in hall.waiting(b) if p["who"] == starved.member_name)
    assert him["fact"] == "5 fortnights unpaid"
    assert him["for"] == starved.name
    assert him["tone"] == "blood"


def test_the_hall_states_the_fact_and_never_what_it_means():
    """D19 and D31. Nobody in this room advises, warns, or ranks."""
    world, _ = _belief(4)
    key = next(iter(world.court.dependents))
    hungry = dataclasses.replace(world.court.dependents[key], arrears=90_000)
    b = project(_with_group(world, key, hungry))
    blob = " ".join(f"{p['who']} {p['for']} {p['fact']}" for p in hall.waiting(b))
    for forbidden in ("should", "must", "urgent", "warning", "danger",
                      "recommend", "advise", "beware", "critical"):
        assert forbidden not in blob.lower(), forbidden


def test_nobody_waiting_is_a_sentence_not_a_blank():
    world, _ = _belief(1)
    court = dataclasses.replace(
        world.court,
        dependents={k: dataclasses.replace(g, arrears=0)
                    for k, g in world.court.dependents.items()})
    b = project(dataclasses.replace(world, court=court, inbox=()))
    assert hall.waiting(b) == []
    assert "the hall is empty" in plain_text(hall.compose(b))


def test_the_longest_wait_stands_nearest_and_ranking_is_by_time_only():
    _, b = _belief(8)
    weights = [p["weight"] for p in hall.waiting(b)]
    assert weights == sorted(weights, reverse=True)


# --- the screen --------------------------------------------------------------

def test_the_hall_says_who_you_are_and_what_the_date_is():
    _, b = _belief(6)
    text = plain_text(hall.compose(b))
    assert "AMMURAPI OF UGARIT" in text
    assert b["date"] in text


def test_the_lamp_burns_down_as_the_hours_go():
    """`hours_left` is the session's budget, not a fact about the world -- see
    the note on `compose`."""
    _, b = _belief(6)
    full = plain_text(hall.compose(b))
    assert f"{b['attention']} of {b['attention_base']} hours" in full
    half = plain_text(hall.compose(b, hours_left=4))
    assert f"4 of {b['attention_base']} hours" in half
    assert half.count("▓") < full.count("▓")
    out = plain_text(hall.compose(b, hours_left=0))
    assert "▓" not in out and f"0 of {b['attention_base']} hours" in out


def test_the_lamp_is_never_only_a_colour():
    """Spec 9.6: the bar is `flame` and the spent part `ash`, and the same fact
    is written in words for anyone who cannot tell those apart."""
    _, b = _belief(6)
    assert "of 10 hours" in plain_text(hall.compose(b))


def test_every_door_is_reachable_by_a_key():
    _, b = _belief(6)
    text = plain_text(hall.compose(b))
    for key, label, _target in hall.DOORS:
        assert f"[{key}]" in text and label in text
    assert "end the fortnight" in text


def test_the_hall_fits_its_surface_at_eighty_columns():
    """The M15 degrade path is a size, not a second renderer."""
    _, b = _belief(6)
    for width in (80, 92, 120):
        screen = hall.compose(b, width=width, height=30)
        assert len(screen) == 30
        assert all(len(row) == width for row in screen)
        for line in plain_text(screen).split("\n"):
            assert len(line) <= width


def test_the_columns_do_not_collide_at_eighty():
    """Three columns of a waiting row, sized off the surface. If they overlap
    the fact reads as part of the errand."""
    _, b = _belief(8)
    text = plain_text(hall.compose(b, width=80, height=30))
    assert "unread" in text
    for line in text.split("\n"):
        assert "…unread" not in line and "…the tablet" not in line


def test_the_hall_degrades_to_pure_ascii_intact():
    _, b = _belief(6)
    text = plain_text(pure_ascii(hall.compose(b)))
    assert all(ord(ch) < 128 for ch in text)
    assert "AMMURAPI OF UGARIT" in text and "WAITING ON YOU" in text


def test_the_hall_leaks_nothing_the_player_has_not_earned():
    """The interface reads Belief and only Belief. These are the keys the
    projection deliberately withholds (spec 8.9, D19)."""
    _, b = _belief(10)
    blob = plain_text(hall.compose(b)).lower()
    for hidden in ("liability", "replacement_rate", "cause_oath", "true_facts",
                   "collapse", "climate", "report_bias"):
        assert hidden not in blob


def test_the_granary_carries_a_shape_as_well_as_a_number():
    _, b = _belief(8)
    text = plain_text(hall.compose(b))
    assert "granary" in text
    assert any(block in text for block in "▁▂▃▄▅▆▇█")


def test_the_sea_is_stated_in_words():
    _, b = _belief(6)
    text = plain_text(hall.compose(b))
    assert ("the sea is shut" in text) or ("the sea is open" in text)


def test_compose_returns_cells_and_uses_named_colours_only():
    _, b = _belief(6)
    screen = hall.compose(b)
    palette = set(range(len(INDEX)))
    for row in screen:
        for glyph, fg, bg in row:
            assert len(glyph) == 1
            assert fg in palette and bg in palette
