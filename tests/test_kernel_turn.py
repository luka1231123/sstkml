"""The tick: phases, intents, and one global allocation (spec 6.1, 10.10)."""
from __future__ import annotations

import random

from engine import entity as E
from engine.kernel import intent as I
from engine.kernel import resolve as R
from engine.kernel import turn as T

UGARIT = E.authored("settlement", "ugarit")
MAHADU = E.authored("settlement", "mahadu")
ALASHIYA = E.authored("settlement", "alashiya_port")
LABOUR = E.authored("site", "ugarit_fields")


# --- phases (6.1) -------------------------------------------------------------

def test_the_phases_are_the_seventeen_the_spec_names_in_that_order() -> None:
    assert len(T.PHASES) == 17
    assert T.PHASES[0] == "calendar" and T.PHASES[-1] == "close"
    # The causal claims that matter most: you observe before you decide, decide
    # before you are allocated, and are allocated before anything is produced.
    for earlier, later in (("observe", "intents"), ("intents", "allocate"),
                           ("allocate", "production"), ("production", "consumption"),
                           ("movement", "settlement"), ("reports", "project")):
        assert T.before(earlier, later), f"{earlier} must precede {later}"


def test_a_step_out_of_its_phase_is_refused_not_quietly_reordered() -> None:
    def nothing(state):
        return state, []

    backwards = (T.Step("consumption", "eat", nothing),
                 T.Step("production", "reap", nothing))
    try:
        T.run(0, backwards)
    except T.PhaseError as exc:
        assert "reap" in str(exc)
        return
    raise AssertionError("running production after consumption must be refused")


def test_the_trace_records_what_ran_and_in_which_phase() -> None:
    def gain(state):
        return state + 1, ["counted"]

    state, events, trace = T.run(0, (
        T.Step("production", "reap", gain),
        T.Step("production", "forge", gain),
        T.Step("consumption", "eat", gain)))
    assert state == 3 and len(events) == 3
    assert trace.phases() == ("production", "consumption")
    assert trace.entries[0] == ("production", "reap", 1)


def test_an_unknown_phase_is_not_a_phase() -> None:
    try:
        T.index("harvesting")
    except T.PhaseError:
        return
    raise AssertionError("only the declared phases exist")


# --- intents (10.10) ----------------------------------------------------------

def _intent(name: str, actor: str, quantity: int, priority: int = 0,
            resource: str = LABOUR) -> I.Intent:
    return I.Intent(id=name, actor=actor, kind="work", turn=7,
                    resource=resource, quantity=quantity, priority=priority)


def test_an_intent_must_be_classifiable_and_attributable() -> None:
    for broken in (dict(kind="brood", actor=UGARIT), dict(kind="work", actor="")):
        try:
            I.Intent(id="x", turn=1, **broken)
        except I.IntentError:
            continue
        raise AssertionError(f"{broken} should not be a valid intent")


def test_an_intent_on_a_shared_pool_must_say_how_much() -> None:
    try:
        I.Intent(id="x", actor=UGARIT, kind="work", turn=1, resource=LABOUR)
    except I.IntentError:
        return
    raise AssertionError("a claim without a quantity cannot be allocated")


def test_a_snapshot_is_the_opening_state_and_says_which_turn_it_opened() -> None:
    snapshot = I.open_turn({"grain": 10}, turn=7)
    assert snapshot.turn == 7 and snapshot.world == {"grain": 10}


# --- allocation (6.1 phase 5) -------------------------------------------------

def test_scarcity_is_greedy_by_priority_then_authority_then_id() -> None:
    intents = (_intent("a", ALASHIYA, 600, priority=0),
               _intent("b", UGARIT, 600, priority=5),
               _intent("c", MAHADU, 600, priority=0))
    allocation = R.allocate(intents, {LABOUR: 1000})

    # The obligation with priority is served whole; the rest go short in id
    # order, and the last claimant gets nothing rather than everyone getting a
    # third of what they need.
    assert allocation.granted("b") == 600
    assert allocation.granted("a") == 400
    assert allocation.granted("c") == 0
    assert allocation.remaining[LABOUR] == 0
    assert {g.intent for g in allocation.unmet()} == {"a", "c"}


def test_authority_breaks_a_tie_of_priority() -> None:
    intents = (_intent("a", ALASHIYA, 800), _intent("b", UGARIT, 800))
    ranks = {ALASHIYA: 0, UGARIT: 9}
    allocation = R.allocate(intents, {LABOUR: 800},
                            authority_rank=lambda i: ranks[i.actor])
    assert allocation.granted("b") == 800 and allocation.granted("a") == 0


def test_the_result_does_not_depend_on_the_order_the_intents_arrived() -> None:
    """The load-bearing fairness claim of 6.1.

    No settlement may do better for appearing earlier in a registry, a dict, or
    a caller's loop. Shuffling the whole list must change nothing at all.
    """
    intents = tuple(_intent(f"i{n}", f"settlement:s{n % 7}", 130 + n, priority=n % 3)
                    for n in range(20))
    baseline = R.allocate(intents, {LABOUR: 900})
    expected = {g.intent: g.granted for g in baseline.grants}

    shuffler = random.Random(4)
    for _ in range(25):
        shuffled = list(intents)
        shuffler.shuffle(shuffled)
        again = R.allocate(tuple(shuffled), {LABOUR: 900})
        assert {g.intent: g.granted for g in again.grants} == expected
        assert again.remaining == baseline.remaining


def test_pools_are_settled_independently() -> None:
    sea = E.authored("route", "ugarit_alashiya")
    intents = (_intent("a", UGARIT, 900),
               _intent("b", MAHADU, 900, resource=sea))
    allocation = R.allocate(intents, {LABOUR: 400, sea: 900})
    assert allocation.granted("a") == 400 and allocation.granted("b") == 900


def test_an_intent_that_competes_for_nothing_is_not_allocated() -> None:
    free = I.Intent(id="q", actor=UGARIT, kind="quote", turn=7)
    allocation = R.allocate((free,), {LABOUR: 10})
    assert allocation.grants == ()
    assert allocation.remaining[LABOUR] == 10


def test_a_claim_on_a_pool_that_does_not_exist_is_refused() -> None:
    try:
        R.allocate((_intent("a", UGARIT, 5, resource=E.authored("site", "nowhere")),),
                   {LABOUR: 10})
    except R.AllocationError:
        return
    raise AssertionError("a claim must name a pool with a capacity")


def test_allocation_faults_catch_an_overspent_pool() -> None:
    capacity = {LABOUR: 1000}
    allocation = R.allocate((_intent("a", UGARIT, 600),
                             _intent("b", MAHADU, 600)), capacity)
    assert R.faults(allocation, capacity) == ()

    import dataclasses
    forged = dataclasses.replace(allocation, grants=(
        dataclasses.replace(allocation.grants[0], granted=1000),
        allocation.grants[1]))
    assert R.faults(forged, capacity)
