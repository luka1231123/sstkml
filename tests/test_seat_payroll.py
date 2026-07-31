"""The crown's payroll, once the kernel owns it (Task 2 C3, spec 6.3).

`systems.pay_rations` fed 1,010 people out of a flat mapping while the kernel
held cohorts standing in the same town. Both records were true and neither knew
about the other, which is the duplication Phase C exists to end.

What these pin is the shape of the answer rather than its numbers: the heads are
cohorts, they eat out of lots somebody owns, the two figures cannot disagree
because there is only one, and the orders the player gives still reach the
grain. That last one is not decoration -- retiring the old system left `Allocate`
attached to nothing, and a lever that moves and does nothing is worse than one
that is gone.
"""
import dataclasses

from engine import actions as A
from engine import seat
from engine.kernel import seat_people as SP
from engine.kernel import world as K
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario

SEED = 8814402919


def _world():
    return load_scenario("ugarit", SEED)


def test_every_group_on_the_roll_is_a_cohort_in_the_registry():
    world = _world()
    for entry in SP.PLACEMENTS:
        if entry.group not in world.court.dependents:
            continue
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        assert cohort is not None, f"{entry.group} never reached the registry"
        assert cohort.people == world.court.dependents[entry.group].size


def test_the_payroll_eats_grain_that_belongs_to_somebody():
    """Not a figure going down. A lot, with an owner, getting smaller."""
    world = _world()
    crown = world.kernel.controller(SP.SEAT)
    before = sum(lot.quantity for lot in world.kernel.book.at(SP.SEAT)
                 if lot.good == "grain" and lot.owner == crown)
    world, _ = advance(world)
    after = sum(lot.quantity for lot in world.kernel.book.at(SP.SEAT)
                if lot.good == "grain" and lot.owner == crown)
    assert after < before


def test_the_court_and_the_kernel_cannot_disagree_about_the_heads():
    """The audit's row, asked of a running world rather than a loaded one."""
    world = _world()
    for _ in range(6):
        world, _ = advance(world)
    for entry in SP.PLACEMENTS:
        group = world.court.dependents.get(entry.group)
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        if group is None or cohort is None:
            continue
        assert group.size == cohort.people


def test_nobody_is_placed_at_a_settlement_the_map_does_not_have():
    """`PLACEMENTS` still names `settlement:mahadu`; the live map has no port.

    The same stale id the `SEAT` constant was, from an authored world the
    scenario stopped building from. A cohort standing at a settlement that does
    not exist is not an error anything raises -- it is simply never found by
    anything -- so the garrison stands with the rest of the crown's people and
    `kernel.faults` stays quiet, which is what says it.
    """
    world = _world()
    for cohort in world.kernel.registry.cohorts.values():
        assert cohort.settlement in world.kernel.registry.settlements
    assert (world.kernel.registry.cohorts["cohort:mahadu_garrison"].settlement
            == SP.SEAT)


def test_a_body_kept_by_a_house_elsewhere_reaches_that_houses_store():
    """What `prebendal` is for, held against the day the map has a Ma'hadu."""
    world = _world()
    crown = world.kernel.controller(SP.SEAT)
    garrison = dataclasses.replace(
        world.kernel.registry.cohorts["cohort:mahadu_garrison"],
        settlement=SP.SEAT, tenure="prebendal", origin=crown)
    assert world.kernel.tenure_of(garrison) == "prebendal"
    reach = {lot.owner for lot
             in K._local_food(world.kernel, world.kernel.book, garrison)}
    assert reach == {crown}, "a prebendary ate something that was not its house's"


def test_cutting_a_ration_reaches_the_grain():
    """The lever the migration nearly broke. `test_m8` found it; this holds it."""
    world = _world()
    world, _ = apply(world, A.Allocate("weavers", 0))
    cohort = world.kernel.registry.cohorts["cohort:ugarit_weavers"]
    assert cohort.allowance == 0
    world, _ = advance(world)
    assert world.court.dependents["weavers"].arrears > 0


def test_paying_more_than_a_fortnight_pays_down_the_debt():
    """A cut that cannot be undone is a debt sentence, not a decision."""
    world = _world()
    world, _ = apply(world, A.Allocate("weavers", 0))
    for _ in range(3):
        world, _ = advance(world)
    owing = world.court.dependents["weavers"].arrears
    assert owing > 0
    world, _ = apply(world, A.Allocate("weavers", owing * 2))
    world, _ = advance(world)
    assert world.court.dependents["weavers"].arrears < owing


def test_priority_decides_who_the_empty_store_reaches_last():
    world = _world()
    order = ("smiths_palace", "weavers")
    world, _ = apply(world, A.SetPriority(order))
    ranked = [world.kernel.registry.cohorts[SP.placement(g).cohort]
              for g in order]
    assert ranked[0].precedence > ranked[1].precedence
    served = [c.id for c in K.kept_mouths(world.kernel)]
    assert served.index(ranked[0].id) < served.index(ranked[1].id)


def test_the_seats_own_households_are_not_fed_out_of_the_crowns_store():
    """The exemption C4 lifts, stated so that lifting it is a deliberate act."""
    world = _world()
    fed = {c.id for c in K.kept_mouths(world.kernel)}
    fed |= {c.id for s in world.kernel.autonomous()
            for c in world.kernel.cohorts_of(s)}
    own = [c for c in world.kernel.cohorts_of(SP.SEAT)
           if c.id not in {e.cohort for e in SP.PLACEMENTS}]
    assert own, "the seat has no households of its own to speak of"
    assert not any(c.id in fed for c in own)


def test_a_hungry_payroll_loses_people_once_and_not_twice():
    """Spec 2.2 for heads. Two consequence models used to be one too many."""
    world = _world()
    book = world.kernel.book
    for lot_id, lot in list(book.lots.items()):
        if lot.location == SP.SEAT and lot.good in ("grain", "seed_grain"):
            book = book.consume(lot_id, lot.free, "consumed")
    world = dataclasses.replace(
        world, kernel=dataclasses.replace(world.kernel, book=book))
    for _ in range(8):
        world, _ = advance(world)
    for entry in SP.PLACEMENTS:
        group = world.court.dependents.get(entry.group)
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        if group is None or cohort is None:
            continue
        assert group.size == cohort.people
    weavers = world.court.dependents["weavers"]
    assert weavers.arrears > 0 and weavers.size < 210


def test_the_mirror_holds_no_figure_the_cohorts_have_lost():
    """What makes it a mirror rather than a second record.

    Not idempotence -- `mirror` runs a fortnight of spec 6.3 and running it
    twice runs the fortnight twice. The claim is narrower and it is the one
    that matters for deleting the mapping in C5: every number the court is
    still showing can be read back off the cohort it came from.
    """
    world = _world()
    for _ in range(4):
        world, _ = advance(world)
    for entry in SP.PLACEMENTS:
        group = world.court.dependents.get(entry.group)
        cohort = world.kernel.registry.cohorts.get(entry.cohort)
        if group is None or cohort is None:
            continue
        assert group.size == cohort.people
        assert group.entitlement == cohort.ration_per_head
        assert group.arrears == cohort.shortfall
        assert group.loyalty == SP.loyalty_of(cohort.grievance)
