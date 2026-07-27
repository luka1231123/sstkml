"""The M13.1 exit gate, and the boundaries that make it mean anything.

    With Ugarit idle or removed, the other settlements continue to produce,
    consume, decide, and change.

Idle is the weak form and removed is the strong one. A world that only passes
the idle test may still be reading the player's settlement for something --
prices, labour, a lookup that silently returns zero. Deleting Ugarit outright
and getting the same history from the others is the claim worth making.
"""
from __future__ import annotations

import dataclasses
import inspect
import random

from engine import believe as B
from engine import obligation as O
from engine import ownership as W
from engine.entity import Registry
from engine.kernel import resolve as R
from engine.kernel import world as K
from load_kernel import load_kernel

UGARIT = "settlement:ugarit"
MAHADU = "settlement:mahadu"
ALASHIYA = "settlement:alashiya_port"


def _run(kernel: K.Kernel, turns: int = 24):
    events = []
    for _ in range(turns):
        kernel, produced = K.advance(kernel)
        events.extend(produced)
        faults = K.faults(kernel)
        assert not faults, faults
    return kernel, events


def _without_ugarit(kernel: K.Kernel) -> K.Kernel:
    """Ugarit deleted outright: settlement, sites, cohorts, stores, and all."""
    registry = kernel.registry
    gone = {UGARIT} | {s for s, site in registry.sites.items()
                       if site.settlement == UGARIT}
    registry = dataclasses.replace(
        registry,
        settlements={i: s for i, s in registry.settlements.items()
                     if i != UGARIT},
        sites={i: s for i, s in registry.sites.items() if s.settlement != UGARIT},
        cohorts={i: c for i, c in registry.cohorts.items()
                 if c.settlement != UGARIT},
        polities={i: dataclasses.replace(
            p, seat="" if p.seat == UGARIT else p.seat,
            controls=tuple(c for c in p.controls if c != UGARIT))
            for i, p in registry.polities.items()})
    book = dataclasses.replace(
        kernel.book,
        lots={i: lot for i, lot in kernel.book.lots.items()
              if lot.location not in gone})
    return dataclasses.replace(kernel, registry=registry, book=book)


# --- the gate -----------------------------------------------------------------

def test_the_authored_kernel_world_loads_and_is_sound() -> None:
    kernel = load_kernel()
    assert K.faults(kernel) == ()
    assert kernel.autonomous() == (ALASHIYA, MAHADU)
    assert not kernel.registry.settlements[UGARIT].autonomous
    assert kernel.stores(MAHADU) == 9000


def test_the_others_produce_consume_decide_and_change_with_ugarit_idle() -> None:
    kernel = load_kernel()
    opening = {s: kernel.stores(s) for s in kernel.autonomous()}
    opening_people = {c: kernel.registry.cohorts[c].people
                      for c in sorted(kernel.registry.cohorts)}

    kernel, events = _run(kernel)
    kinds = {e[0] for e in events}

    assert "harvested" in kinds, "they produce"
    assert "hungry" in kinds or any(         # they consume, and it can fall short
        kernel.stores(s) != opening[s] for s in opening), "they consume"
    assert {"due", "rendered"} & kinds, "they decide what to render"
    assert any(kernel.stores(s) != opening[s] for s in opening), "they change"

    after = {c: kernel.registry.cohorts[c].people
             for c in sorted(kernel.registry.cohorts)}
    assert after != opening_people, "and the change reaches the people"


def test_removing_ugarit_entirely_changes_nothing_for_the_others() -> None:
    """The strong form. Same history, to the grain."""
    with_seat, _ = _run(load_kernel())
    without, _ = _run(_without_ugarit(load_kernel()))

    assert UGARIT not in without.registry.settlements
    for settlement in (MAHADU, ALASHIYA):
        assert without.stores(settlement) == with_seat.stores(settlement)
        assert without.people(settlement) == with_seat.people(settlement)

    assert ([(o.id, o.status, o.rendered) for o in without.obligations]
            == [(o.id, o.status, o.rendered) for o in with_seat.obligations])


def test_a_settlement_that_cannot_feed_itself_declines_without_anyone_deciding_it() -> None:
    """Spec 11.2 scenario 1: they sometimes fail, and no cadence made it happen."""
    kernel, _ = _run(load_kernel(), turns=40)
    thin = kernel.registry.cohorts["cohort:alashiya_fields"]
    assert thin.hunger > 0 and thin.grievance > 0
    assert kernel.people(ALASHIYA) < 500, "the shortfall reached the people"
    assert kernel.people(MAHADU) == 560, "and the port that could feed itself did not"


def test_the_run_is_deterministic() -> None:
    first, _ = _run(load_kernel(), turns=18)
    second, _ = _run(load_kernel(), turns=18)
    assert [(i, first.book.lots[i]) for i in sorted(first.book.lots)] == \
           [(i, second.book.lots[i]) for i in sorted(second.book.lots)]
    assert first.registry.cohorts == second.registry.cohorts


def test_the_history_does_not_depend_on_registry_order() -> None:
    """Spec 11.1: permuting the registries must not change the result."""
    kernel = load_kernel()
    shuffler = random.Random(11)

    def permuted(mapping):
        keys = list(mapping)
        shuffler.shuffle(keys)
        return {k: mapping[k] for k in keys}

    jumbled = dataclasses.replace(
        kernel,
        registry=dataclasses.replace(
            kernel.registry,
            settlements=permuted(kernel.registry.settlements),
            cohorts=permuted(kernel.registry.cohorts),
            sites=permuted(kernel.registry.sites),
            orgs=permuted(kernel.registry.orgs)),
        book=dataclasses.replace(kernel.book, lots=permuted(kernel.book.lots)))

    straight, _ = _run(load_kernel(), turns=16)
    tangled, _ = _run(jumbled, turns=16)
    for settlement in (MAHADU, ALASHIYA):
        assert tangled.stores(settlement) == straight.stores(settlement)
        assert tangled.people(settlement) == straight.people(settlement)


# --- the boundaries that make the gate mean something -------------------------

def test_a_policy_may_not_take_the_world() -> None:
    """Spec 10.11, enforced by signature rather than by good intentions.

    A policy handed the world could read another settlement's granary, and
    nothing in its output would show that it had.
    """
    for name, policy in sorted(K.POLICIES.items()):
        parameters = list(inspect.signature(policy).parameters)
        assert parameters == ["actor", "belief"], f"{name} takes {parameters}"


def test_a_council_decides_only_from_what_it_holds() -> None:
    kernel, _ = _run(load_kernel(), turns=3)
    for settlement in kernel.autonomous():
        actor = kernel.controller(settlement)
        belief = kernel.beliefs[actor]
        assert belief.holder == actor
        assert {c.subject for c in belief.claims} == {settlement}, \
            "a council holds claims about its own place and no other"


def test_belief_is_dated_sourced_and_never_overwritten() -> None:
    kernel, _ = _run(load_kernel(), turns=5)
    belief = kernel.beliefs[kernel.controller(MAHADU)]
    grain = belief.about(MAHADU, "stores_grain")
    assert len(grain) == 5, "five countings, five claims -- none replaced"
    assert belief.best(MAHADU, "stores_grain").observed_turn == 5
    assert all(c.source == "observed" for c in grain)

    need = belief.about(MAHADU, "need")[0]
    assert need.source == "inferred" and need.basis, "an inference names its inputs"


def test_goods_are_conserved_across_a_run() -> None:
    """The ledger accounts for every grain, or the run is not trustworthy."""
    kernel = load_kernel()
    for _ in range(20):
        before = kernel.book
        kernel, _ = K.advance(kernel)
        sourced, sunk, unexplained = W.conservation(
            dataclasses.replace(before, transfers=()),
            dataclasses.replace(kernel.book,
                                transfers=kernel.book.transfers))["grain"]
        assert unexplained == 0, (sourced, sunk, unexplained)


def test_rendering_a_tribute_actually_moves_the_grain() -> None:
    """Recording a payment is not making one.

    The first version of the settlement phase computed the levy and dropped the
    updated book on the floor: the obligation went to discharged while the
    grain never changed hands. Every ledger agreed, and nothing was paid.
    """
    kernel, _ = _run(load_kernel(), turns=10)
    crown = "polity:ugarit"
    theirs = [lot for lot in kernel.book.owned_by(crown) if lot.good == "grain"]
    assert theirs, "the crown owns grain it did not own before"
    assert sum(lot.quantity for lot in theirs) == 1800

    # Ownership moved; custody and place did not. Nothing has carried it yet,
    # and M13.1 has no transport -- so it is the crown's grain, in Ma'hadu.
    assert all(lot.location == MAHADU for lot in theirs)
    assert all(lot.holder != crown for lot in theirs)


def test_a_recurring_render_stands_again_next_year() -> None:
    kernel, events = _run(load_kernel(), turns=30)
    tribute = kernel.obligations[0]
    assert "renewed" in " ".join(tribute.history)
    assert tribute.rendered == 0 and tribute.status in ("pending", "due")
    assert sum(1 for e in events if e[0] == "due") >= 1


def test_two_claimants_on_one_body_of_people_and_authority_decides() -> None:
    """The allocator has to bind, or it is decoration.

    Ma'hadu's elders and its temple both want the fortnight's hands. Nothing
    splits them by hand: the temple outranks the elders, takes what it asked
    for, and the elders go short by exactly that much.
    """
    kernel = load_kernel()
    assert kernel.deciders() == ("org:alashiya_council", "org:mahadu_council",
                                 "org:mahadu_temple")

    kernel, _, log = K.advance_logged(kernel)
    at_mahadu = {g.actor: g for g in log.allocation.grants
                 if g.resource == f"{MAHADU}#labour"}
    assert set(at_mahadu) == {"org:mahadu_council", "org:mahadu_temple"}

    temple, elders = at_mahadu["org:mahadu_temple"], at_mahadu["org:mahadu_council"]
    assert temple.met, "the higher authority is served first, and in full"
    assert not elders.met
    assert elders.short == temple.granted
    assert temple.granted + elders.granted == kernel.labour(MAHADU)

    # And each keeps what its own hands made: a lot has one owner.
    owners = {lot.owner for lot in kernel.book.at(MAHADU) if lot.good == "grain"}
    assert {"org:mahadu_council", "org:mahadu_temple"} <= owners


def test_the_allocation_inside_a_turn_never_exceeds_the_labour_that_exists() -> None:
    kernel = load_kernel()
    for _ in range(8):
        capacity = K._capacity(kernel)
        snapshot = K.open_turn(kernel, kernel.date.absolute + 1)
        primed, _ = K._observe(kernel, snapshot)
        intents = K._intents(primed, K.open_turn(primed, snapshot.turn))
        allocation = R.allocate(intents, capacity)
        assert R.faults(allocation, capacity) == ()
        kernel, _ = K.advance(kernel)


def test_an_empty_world_is_a_world() -> None:
    """Nothing here assumes there is a player settlement, or any settlement."""
    kernel = K.Kernel(seed=1, date=K.Date(1, 1, 0), registry=Registry(),
                      book=W.Book())
    kernel, events = K.advance(kernel)
    assert events == [] and K.faults(kernel) == ()
