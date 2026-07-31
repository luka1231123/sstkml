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
from engine.kernel import farm as F
from engine.kernel import resolve as R
from engine.kernel import world as K
from load import load_scenario

SEAT = "settlement:seat"
ALASHIYA = "settlement:alashiya"
AMURRU = "settlement:amurru"
CARCHEMISH = "settlement:carchemish"
MUKISH = "settlement:mukish"


def _world() -> K.Kernel:
    return load_scenario("ugarit", seed=1).kernel


def _run(kernel: K.Kernel, turns: int = 24):
    events = []
    for _ in range(turns):
        kernel, produced = K.advance(kernel)
        events.extend(produced)
        faults = K.faults(kernel)
        assert not faults, faults
    return kernel, events


def _without_ugarit(kernel: K.Kernel) -> K.Kernel:
    """Ugarit deleted outright: settlement, sites, cohorts, stores, orgs, routes."""
    registry = kernel.registry
    gone_settlements = {SEAT}
    gone_sites = {s for s, site in registry.sites.items()
                  if site.settlement == SEAT}
    gone = gone_settlements | gone_sites
    registry = dataclasses.replace(
        registry,
        settlements={i: s for i, s in registry.settlements.items()
                     if i not in gone_settlements},
        sites={i: s for i, s in registry.sites.items() if s.settlement != SEAT},
        cohorts={i: c for i, c in registry.cohorts.items()
                 if c.settlement != SEAT},
        orgs={i: o for i, o in registry.orgs.items()
              if o.settlement != SEAT},
        routes={i: r for i, r in registry.routes.items()
                if not any(SEAT in (leg.origin, leg.destination)
                           for leg in r.legs)},
        polities={i: dataclasses.replace(
            p, seat="" if p.seat == SEAT else p.seat,
            controls=tuple(c for c in p.controls if c != SEAT))
            for i, p in registry.polities.items()})
    book = dataclasses.replace(
        kernel.book,
        lots={i: lot for i, lot in kernel.book.lots.items()
              if lot.location not in gone})
    obligations = tuple(o for o in kernel.obligations
                        if o.party not in gone_settlements
                        and o.beneficiary not in gone_settlements)
    return dataclasses.replace(kernel, registry=registry, book=book,
                               obligations=obligations)


def landlocked(kernel: K.Kernel) -> K.Kernel:
    registry = dataclasses.replace(kernel.registry, routes={})
    return dataclasses.replace(kernel, registry=registry, voyages=())


# --- the gate -----------------------------------------------------------------

def test_the_authored_kernel_world_loads_and_is_sound() -> None:
    kernel = _world()
    assert K.faults(kernel) == ()
    assert SEAT not in kernel.autonomous()
    assert not kernel.registry.settlements[SEAT].autonomous
    assert kernel.stores(ALASHIYA) == 960_000


def test_a_palace_controls_its_settlement_same_as_a_council() -> None:
    from engine.entity import Organization, Settlement

    kernel = _world()
    registry = kernel.registry
    town = "settlement:test_palace_town"
    org = "org:test_palace_town_palace"
    registry = dataclasses.replace(
        registry,
        settlements={**registry.settlements, town: Settlement(
            id=town, name="Test Palace Town", region="region:test",
            polity="polity:test", orgs=(org,), autonomous=True)},
        orgs={**registry.orgs, org: Organization(
            id=org, name="Test Palace", settlement=town, kind="palace")})
    kernel = dataclasses.replace(kernel, registry=registry)

    assert kernel.controller(town) == org
    assert town in kernel.autonomous()


def test_the_others_produce_consume_decide_and_change_with_ugarit_idle() -> None:
    kernel = _world()
    opening = {s: kernel.stores(s) for s in kernel.autonomous()}
    opening_people = {c: kernel.registry.cohorts[c]
                      for c in sorted(kernel.registry.cohorts)}

    kernel, events = _run(kernel, turns=48)
    kinds = {e[0] for e in events}

    assert {"reaped", "threshed", "set_aside", "sown"} <= kinds, "they produce"
    assert "hungry" in kinds or any(
        kernel.stores(s) != opening[s] for s in opening), "they consume"
    assert {"due", "rendered"} & kinds, "they decide what to render"
    assert any(kernel.stores(s) != opening[s] for s in opening), "they change"

    after = {c: kernel.registry.cohorts[c]
             for c in sorted(kernel.registry.cohorts)}
    assert after != opening_people, "and the change reaches the people"


def test_removing_ugarit_entirely_changes_nothing_for_the_others() -> None:
    with_seat, _ = _run(_world())
    without, _ = _run(_without_ugarit(_world()))

    assert SEAT not in without.registry.settlements
    for settlement in (ALASHIYA, AMURRU):
        assert without.stores(settlement) == with_seat.stores(settlement)
        assert without.people(settlement) == with_seat.people(settlement)

    without_obs = {(o.id, o.status, o.rendered) for o in without.obligations}
    with_obs = {(o.id, o.status, o.rendered) for o in with_seat.obligations
                if o.party != SEAT}
    assert without_obs == with_obs, "same obligations (excluding seat)"


def test_a_settlement_that_cannot_feed_itself_declines_without_anyone_deciding_it() -> None:
    kernel, _ = _run(landlocked(_world()), turns=40)
    thin = kernel.registry.cohorts["cohort:mukish_field_labour"]
    assert thin.hunger > 0 and thin.grievance > 0
    assert kernel.people(MUKISH) < 3000, "the shortfall reached the people"
    assert kernel.stores(ALASHIYA) > 800_000, "and the port that could feed itself did not"


def test_the_run_is_deterministic() -> None:
    first, _ = _run(_world(), turns=18)
    second, _ = _run(_world(), turns=18)
    assert [(i, first.book.lots[i]) for i in sorted(first.book.lots)] == \
           [(i, second.book.lots[i]) for i in sorted(second.book.lots)]
    assert first.registry.cohorts == second.registry.cohorts


def test_the_history_does_not_depend_on_registry_order() -> None:
    kernel = _world()
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

    straight, _ = _run(_world(), turns=16)
    tangled, _ = _run(jumbled, turns=16)
    for settlement in (ALASHIYA, AMURRU):
        assert tangled.stores(settlement) == straight.stores(settlement)
        assert tangled.people(settlement) == straight.people(settlement)


# --- the boundaries that make the gate mean something -------------------------

def test_a_policy_may_not_take_the_world() -> None:
    for name, policy in sorted(K.POLICIES.items()):
        parameters = list(inspect.signature(policy).parameters)
        assert parameters == ["actor", "belief"], f"{name} takes {parameters}"


def test_a_council_decides_only_from_what_it_holds() -> None:
    kernel, _ = _run(_world(), turns=3)
    for settlement in kernel.autonomous():
        actor = kernel.controller(settlement)
        belief = kernel.beliefs[actor]
        assert belief.holder == actor
        counted = {c.subject for c in belief.claims if c.source == "observed"}
        assert counted == {settlement}, \
            "a council counts its own place and no other"
        for claim in belief.claims:
            if claim.subject == settlement:
                continue
            assert claim.source in ("reported", "assumed"), claim
            assert claim.observed_turn < claim.received_turn, \
                "word from elsewhere is older than the day it arrives"


def test_belief_is_dated_sourced_and_never_overwritten() -> None:
    kernel, _ = _run(_world(), turns=5)
    belief = kernel.beliefs[kernel.controller(ALASHIYA)]
    grain = belief.about(ALASHIYA, "stores_grain")
    assert len(grain) == 5, "five countings, five claims -- none replaced"
    assert belief.best(ALASHIYA, "stores_grain").observed_turn == 5
    assert all(c.source == "observed" for c in grain)

    need = belief.about(ALASHIYA, "need")[0]
    assert need.source == "inferred" and need.basis, "an inference names its inputs"


def test_goods_are_conserved_across_a_run() -> None:
    kernel = _world()
    for _ in range(20):
        before = kernel.book
        kernel, _ = K.advance(kernel)
        sourced, sunk, unexplained = W.conservation(
            dataclasses.replace(before, transfers=()),
            dataclasses.replace(kernel.book,
                                transfers=kernel.book.transfers))["grain"]
        assert unexplained == 0, (sourced, sunk, unexplained)


def test_rendering_a_tribute_actually_moves_the_grain() -> None:
    kernel, _ = _run(_world(), turns=9)
    crown = "polity:egypt"
    theirs = [lot for lot in kernel.book.owned_by(crown) if lot.good == "grain"]
    assert theirs, "the crown owns grain it did not own before"

    later, _ = _run(kernel, turns=6)
    kept = sum(lot.quantity for lot in later.book.owned_by(crown)
               if lot.good == "grain")
    assert 0 < kept <= sum(l.quantity for l in theirs), "tribute nobody collects spoils"


def test_a_recurring_render_stands_again_next_year() -> None:
    kernel, events = _run(_world(), turns=30)
    tribute = kernel.obligations[0]
    assert "renewed" in " ".join(tribute.history)
    assert tribute.rendered == 0 and tribute.status in ("pending", "due")
    assert sum(1 for e in events if e[0] == "due") >= 1


def test_two_claimants_on_one_body_of_people_and_authority_decides() -> None:
    kernel = _world()
    assert "org:amurru_council" in kernel.deciders()

    while kernel.date.fortnight != 7:
        kernel, _ = K.advance(kernel)
    kernel, _, log = K.advance_logged(kernel)
    assert F.season(kernel.seasons, kernel.date.fortnight, "harvest")

    at_amurru = {g.actor: g for g in log.allocation.grants
                 if g.resource == f"{AMURRU}#labour"}
    assert set(at_amurru) == {"org:amurru_council"}


def test_the_allocation_inside_a_turn_never_exceeds_the_labour_that_exists() -> None:
    kernel = _world()
    for _ in range(8):
        capacity = K._capacity(kernel)
        snapshot = K.open_turn(kernel, kernel.date.absolute + 1)
        primed, _ = K._observe(kernel, snapshot)
        intents = K._intents(primed, K.open_turn(primed, snapshot.turn))
        allocation = R.allocate(intents, capacity)
        assert R.faults(allocation, capacity) == ()
        kernel, _ = K.advance(kernel)


def test_an_empty_world_is_a_world() -> None:
    kernel = K.Kernel(seed=1, date=K.Date(1, 1, 0), registry=Registry(),
                      book=W.Book())
    kernel, events = K.advance(kernel)
    assert events == [] and K.faults(kernel) == ()
