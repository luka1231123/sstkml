"""D25: the military entity. Task, place, garrison strength, troops on the
harvest, and the summons clause that M11's raid targeting is waiting on.

No combat is tested here because none exists and none is meant to (D25).
"""
from __future__ import annotations

import dataclasses

from ai.parser import preparse
from belief.project import project
from engine import actions as A
from engine import troops
from engine.core import state_hash
from engine.legacy.land import labour_supplied
from engine.reduce import apply
from engine.relations import audit_oaths
from engine.state import Summons
from engine.tick import advance
from load import load_scenario
from session import replay, save

SEED = 8814402919


def _run(turns: int, seed: int = SEED):
    world = load_scenario("ugarit", seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


# --- the entity (D25 items 1 and 3) ------------------------------------------

def test_every_formation_stands_somewhere_and_is_doing_something():
    world = load_scenario("ugarit", SEED)
    assert world.court.formations
    for formation in world.court.formations:
        assert formation.task in troops.TASKS
        assert formation.place in world.places


def test_ugarit_keeps_under_the_four_hundred_the_spec_allows_it():
    """Spec 7.2: `troops` total under 400, and there is no military solution to
    anything. The cap is thematic, so drifting past it is how the endgame starts
    feeling winnable by force (D25)."""
    world = load_scenario("ugarit", SEED)
    assert sum(f.strength for f in world.court.formations) < 400


def test_assigning_troops_moves_them_and_nothing_else():
    world = load_scenario("ugarit", SEED)
    before = {f.id: f.strength for f in world.court.formations}
    world, events = apply(
        world, A.AssignTroops("household_troops", "campaign", "carchemish"))
    moved = next(f for f in world.court.formations if f.id == "household_troops")
    assert (moved.task, moved.place) == ("campaign", "carchemish")
    assert events == [A.TroopsAssigned("household_troops", "campaign", "carchemish")]
    # Strengths are untouched: this is an order, not a battle.
    assert {f.id: f.strength for f in world.court.formations} == before
    # An empty place means the seat, so the common order is two words.
    world, _ = apply(world, A.AssignTroops("household_troops", "garrison"))
    moved = next(f for f in world.court.formations if f.id == "household_troops")
    assert (moved.task, moved.place) == ("garrison", world.court.seat)


def test_the_order_refuses_what_it_cannot_mean():
    world = load_scenario("ugarit", SEED)
    for bad in (A.AssignTroops("no_such_formation", "garrison"),
                A.AssignTroops("chariotry", "besiege"),
                A.AssignTroops("chariotry", "garrison", "atlantis")):
        try:
            apply(world, bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted an impossible order: {bad}")


def test_garrison_strength_counts_only_the_men_holding_the_place():
    """Spec 6.13's raid term. Men in the fields or at a muster in the north are
    defending nothing, which is the entire cost of ordering them there."""
    world = load_scenario("ugarit", SEED)
    seat = world.court.seat
    held = troops.garrison_strength(world.court, seat)
    assert held > 0

    world, _ = apply(world, A.AssignTroops("household_troops", "harvest"))
    after_harvest = troops.garrison_strength(world.court, seat)
    assert after_harvest < held

    world, _ = apply(
        world, A.AssignTroops("chariotry", "campaign", "carchemish"))
    assert troops.garrison_strength(world.court, seat) == 0
    assert troops.mustered_for(world.court, "carchemish") == 90
    # And they count at the place they were sent to, not the one they left.
    assert troops.garrison_strength(world.court, "carchemish") == 0


def test_a_watch_counts_half_because_a_watch_is_not_a_defence():
    world = load_scenario("ugarit", SEED)
    watch = next(f for f in world.court.formations if f.id == "coast_watch")
    assert watch.task == "watch"
    assert troops.garrison_strength(world.court, watch.place) == watch.ready // 4
    world, _ = apply(world, A.AssignTroops("coast_watch", "garrison", watch.place))
    assert troops.garrison_strength(world.court, watch.place) == watch.ready // 2


# --- troops as labour (D25 item 2, spec 6.4 line 566) ------------------------

def test_troops_on_the_harvest_supply_labour_days():
    world = _run(2)
    per_head = world.land_rules.get("labour_days_per_head", 12)
    before = labour_supplied(world.court, per_head)
    world, _ = apply(world, A.AssignTroops("household_troops", "harvest"))
    after = labour_supplied(world.court, per_head)
    strength = next(f for f in world.court.formations
                    if f.id == "household_troops").strength
    assert after - before == strength * per_head
    # Ordering them anywhere else takes the hands straight back off the land.
    world, _ = apply(world, A.AssignTroops("household_troops", "garrison"))
    assert labour_supplied(world.court, per_head) == before


def test_the_garrison_or_the_harvest_is_a_real_choice():
    """Both ends of it must bite at once: hands on the land go up exactly as the
    men holding the seat go down."""
    world = _run(2)
    per_head = world.land_rules.get("labour_days_per_head", 12)
    seat = world.court.seat
    labour_before = labour_supplied(world.court, per_head)
    held_before = troops.garrison_strength(world.court, seat)
    world, _ = apply(world, A.AssignTroops("household_troops", "harvest"))
    assert labour_supplied(world.court, per_head) > labour_before
    assert troops.garrison_strength(world.court, seat) < held_before


# --- the summons (D25 item 4) ------------------------------------------------

def _first_summons(max_turns: int = 30):
    world = load_scenario("ugarit", SEED)
    for _ in range(max_turns):
        world, events = advance(world)
        called = [e for e in events if isinstance(e, A.SummonsReceived)]
        if called:
            return world, called[0]
    raise AssertionError("no summons arrived in {max_turns} turns")


def test_the_summons_arrives_and_starts_its_clock():
    world, called = _first_summons()
    assert called.oath_id == "oath_hatti_grain"
    assert called.n == 200
    record = world.court.summons[0]
    assert record.due_turn == record.called_turn + 2
    assert world.date.absolute == record.called_turn


def test_the_clock_runs_on_a_tablet_nobody_has_read():
    """An unopened demand is still a demand delivered. This is the argument for
    reading the pile, and it is the only one the game makes."""
    world, _ = _first_summons()
    letter = next(item for item in world.inbox if item.summons_oath)
    assert not letter.read
    assert world.court.summons
    # ...and it is not on his troops page until somebody tells him.
    assert project(world)["troops"]["summons"] == []
    world, _ = apply(world, A.ReadLetter(letter.id))
    shown = project(world)["troops"]["summons"]
    assert len(shown) == 1
    assert shown[0]["required"] == 200 and shown[0]["mustered"] == 0


def test_the_viceroy_asks_for_more_men_than_the_oath_obliges():
    """The tablet is the trigger, never the figure (D25). He exaggerates
    `troops`, so a king who obeys the letter sends more than he owes and a king
    who checks the oath sends 200."""
    world, called = _first_summons()
    letter = next(item for item in world.inbox if item.summons_oath)
    asserted = dict(letter.facts)["troops"]
    assert asserted > called.n
    assert dict(letter.true_facts)["troops"] == called.n


def _due_now(world, mustered_at=None):
    """Put a summons of this oath exactly on its due date, so the audit judges
    it this turn."""
    now = world.date.absolute
    record = Summons(oath_id="oath_hatti_grain", place="carchemish", n=200,
                     called_turn=now - 2, due_turn=now)
    court = dataclasses.replace(world.court, summons=(record,))
    world = dataclasses.replace(world, court=court)
    if mustered_at:
        world, _ = apply(
            world, A.AssignTroops("household_troops", "campaign", mustered_at))
    return world


def test_a_muster_that_never_marched_is_a_violation():
    world = _run(3)
    assert world.date.fortnight != 24          # keep the grain clause out of it
    due = _due_now(world)
    audited, events = audit_oaths(due)
    violated = [e for e in events if isinstance(e, A.OathViolated)
                and e.clause_kind == "provide_troops"]
    assert len(violated) == 1
    assert audited == due


def test_men_standing_at_the_muster_place_answer_it():
    world = _run(3)
    audited, events = audit_oaths(_due_now(world, mustered_at="carchemish"))
    assert not [e for e in events if isinstance(e, A.OathViolated)
                and e.clause_kind == "provide_troops"]
    # Sent to the wrong place, they have not answered anything.
    audited, events = audit_oaths(_due_now(world, mustered_at="halab"))
    assert [e for e in events if isinstance(e, A.OathViolated)
            and e.clause_kind == "provide_troops"]


def test_it_is_judged_once_and_not_every_turn_after():
    """One failed muster is one breach, however long the overlord remembers
    it -- the same shape as the yearly grain clause."""
    world = _run(3)
    world = _due_now(world)
    audited, _ = audit_oaths(world)
    later = dataclasses.replace(
        audited, date=audited.date.advance())
    unchanged, events = audit_oaths(later)
    assert not [e for e in events if isinstance(e, A.OathViolated)
                and e.clause_kind == "provide_troops"]
    assert unchanged == later


def test_a_lapsed_oath_summons_nobody():
    """D22: when the man who swore is dead the demand dies with him, until
    somebody travels and swears again."""
    world, _ = _first_summons()
    oaths = tuple(
        dataclasses.replace(o, lapsed=True) if o.id == "oath_hatti_grain" else o
        for o in world.oaths)
    world = dataclasses.replace(world, oaths=oaths)
    before = len(world.court.summons)
    # A second demand arrives against a lapsed oath and raises nothing.
    for _ in range(6):
        world, _ = advance(world)
    assert len(world.court.summons) == before


# --- the seams ---------------------------------------------------------------

def test_the_order_round_trips_through_a_save():
    world = load_scenario("ugarit", SEED)
    script = [[A.AssignTroops("chariotry", "campaign", "carchemish")],
              [A.AssignTroops("household_troops", "harvest", "")]]
    log = []
    for turn_actions in script:
        world, _ = advance(world)
        turn = world.date.absolute
        for act in turn_actions:
            world, _ = apply(world, act)
            log.append({"turn": turn, "action": A.to_dict(act)})
    path = "/tmp/st_troops_test.json"
    save(path, SEED, "ugarit", len(script), log, world)
    assert state_hash(replay(path)) == state_hash(world)


def test_the_preparser_takes_the_order_in_plain_words():
    world = load_scenario("ugarit", SEED)
    belief = project(world)
    result = preparse("assign chariotry to campaign at carchemish", belief)
    assert result.actions == (A.AssignTroops("chariotry", "campaign", "carchemish"),)
    result = preparse("send the household_troops to harvest", belief)
    assert result.actions == (A.AssignTroops("household_troops", "harvest", ""),)
    assert preparse("assign nobody to campaign", belief) is None


def test_the_troops_page_tells_him_his_own_orders_and_nothing_else():
    world = _run(4)
    page = project(world)["troops"]
    assert {f["id"] for f in page["formations"]} == {
        f.id for f in world.court.formations}
    blob = repr(page)
    # No readiness, no assessment, and nobody else's strength.
    assert "replacement_rate" not in blob
    assert "equipment_floor" not in blob
