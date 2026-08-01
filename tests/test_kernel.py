"""M13.1 kernel data layer: identity, custody, and clauses (spec 10.7-10.9)."""
from __future__ import annotations

from engine import entity as E
from engine import obligation as O
from engine import ownership as W
from engine.core import Date

UGARIT = E.authored("settlement", "ugarit")
HARBOUR = E.authored("site", "mahadu_harbour")
PALACE = E.authored("org", "palace_ugarit")
HOUSE = E.authored("household", "yabninu")


# --- identity (10.7) ----------------------------------------------------------

def test_authored_ids_are_namespaced_and_checked() -> None:
    assert UGARIT == "settlement:ugarit"
    assert E.kind_of(UGARIT) == "settlement"
    for bad in (("kingdom", "ugarit"), ("site", "Mahadu"), ("site", "ma hadu")):
        try:
            E.authored(*bad)
        except E.BadId:
            continue
        raise AssertionError(f"{bad} should not be a valid id")


def test_runtime_ids_carry_their_whole_derivation() -> None:
    lot = E.mint(HARBOUR, 57, "lot", 3)
    assert lot == "site:mahadu_harbour/57/lot/3"
    kind, name, suffix = E.parse(lot)
    assert (kind, name) == ("site", "mahadu_harbour")
    assert suffix == ("57", "lot", "3")
    # The kind of a runtime id is still the kind of the thing that minted it.
    assert E.kind_of(lot) == "site"


def test_a_runtime_id_will_not_come_from_an_unregistered_domain() -> None:
    try:
        E.mint(HARBOUR, 1, "vibes", 0)
    except E.BadId:
        return
    raise AssertionError("an unregistered id domain must be refused")


def test_runtime_ids_do_not_nest() -> None:
    """Or a long game grows identifiers without bound."""
    shipment = E.mint(HARBOUR, 12, "shipment", 0)
    try:
        E.mint(shipment, 12, "lot", 0)
    except E.BadId:
        return
    raise AssertionError("minting from a runtime id must be refused")


def test_ordinals_follow_the_sorted_keys_not_the_callers_loop() -> None:
    """The load-bearing claim of 10.7: identity is independent of iteration order.

    This is what `letter_seq` and friends could not promise. Two callers that
    create the same things in different orders must agree on every id, or one
    inserted document renumbers the rest and the state hash moves with it.
    """
    keys = ("tin", "copper", "grain")
    forward = E.mint_all(HARBOUR, 40, "lot", keys)
    backward = E.mint_all(HARBOUR, 40, "lot", tuple(reversed(keys)))
    assert forward == backward
    assert forward["copper"].endswith("/0")   # sorted, not first-seen
    assert forward["grain"].endswith("/1")
    assert forward["tin"].endswith("/2")


def test_the_registry_reports_what_it_cannot_resolve() -> None:
    region = E.Region(id=E.authored("region", "north_levant"), name="north")
    good = E.Registry(
        regions={region.id: region},
        polities={E.authored("polity", "ugarit"):
                  E.Polity(id=E.authored("polity", "ugarit"), name="Ugarit",
                           ruler="person:king", seat=UGARIT)},
        persons={"person:king": E.Person(id="person:king", name="king")},
        settlements={UGARIT: E.Settlement(
            id=UGARIT, name="Ugarit", region=region.id,
            owner=E.authored("polity", "ugarit"), sites=(HARBOUR,))},
        sites={HARBOUR: E.Site(id=HARBOUR, name="Ma'hadu", settlement=UGARIT,
                               function="harbour", region=region.id)})
    assert E.check(good) == ()

    orphan = E.Registry(
        regions=good.regions, polities=good.polities,
        settlements=good.settlements, sites={})
    faults = E.check(orphan)
    assert any(HARBOUR in fault for fault in faults), faults


# --- ownership and custody (10.8) ---------------------------------------------

def _book() -> W.Book:
    book = W.Book(turn=10, phase="production")
    return book.create(E.mint(HARBOUR, 10, "lot", 0), "grain", 1000,
                       owner=HOUSE, holder=HOUSE, location=HARBOUR,
                       reason="harvested")


def test_goods_enter_and_leave_the_world_through_a_named_endpoint() -> None:
    book = _book()
    lot = next(iter(book.lots))
    assert book.total("grain") == 1000
    assert book.transfers[0].from_owner == W.WORLD
    assert book.transfers[0].reason == "harvested"

    book = book.consume(lot, 250, "consumed")
    assert book.total("grain") == 750
    assert book.transfers[-1].to_owner == W.WORLD


def test_owning_and_holding_are_not_the_same_move() -> None:
    """The distinction the whole economy rests on (10.8)."""
    book = _book()
    lot = next(iter(book.lots))

    book = book.hand(lot, PALACE, "stored")
    assert book.lots[lot].holder == PALACE
    assert book.lots[lot].owner == HOUSE, "storing grain does not surrender it"

    book = book.give(lot, 1000, PALACE, "levied")
    assert book.lots[lot].owner == PALACE


def test_a_partial_give_splits_and_conserves() -> None:
    book = _book()
    lot = next(iter(book.lots))
    part = E.mint(HARBOUR, 10, "lot", 1)
    book = book.give(lot, 400, PALACE, "sold", new_id=part)

    assert book.total("grain") == 1000, "selling does not create or destroy grain"
    assert book.lots[lot].quantity == 600 and book.lots[lot].owner == HOUSE
    assert book.lots[part].quantity == 400 and book.lots[part].owner == PALACE
    assert any("split" in mark for mark in book.lots[part].provenance)


def test_reserved_goods_are_not_available_and_cannot_be_spent() -> None:
    book = _book()
    lot = next(iter(book.lots))
    book = book.reserve(lot, 800)
    assert book.lots[lot].free == 200

    for attempt in (lambda: book.consume(lot, 500, "consumed"),
                    lambda: book.give(lot, 500, PALACE, "sold",
                                      new_id=E.mint(HARBOUR, 10, "lot", 2))):
        try:
            attempt()
        except W.LedgerError:
            continue
        raise AssertionError("reserved goods must not be spendable")

    assert book.release(lot, 800).lots[lot].free == 1000


def test_an_emptied_lot_leaves_and_its_history_rides_along() -> None:
    book = _book()
    lot = next(iter(book.lots))
    book = book.consume(lot, 1000, "sown")
    assert lot not in book.lots
    assert book.total("grain") == 0


def test_lots_merge_only_when_everything_identifying_them_matches() -> None:
    book = _book()
    lot = next(iter(book.lots))
    other = E.mint(HARBOUR, 10, "lot", 5)
    book = book.create(other, "grain", 300, owner=PALACE, holder=PALACE,
                       location=HARBOUR, reason="harvested")
    try:
        book.merge(lot, other)
    except W.LedgerError:
        pass
    else:
        raise AssertionError("differently owned grain is not one lot")

    book = book.give(other, 300, HOUSE, "gifted").hand(other, HOUSE, "carried")
    book = book.merge(lot, other)
    assert book.lots[lot].quantity == 1300
    assert other not in book.lots


def test_an_unregistered_reason_is_refused() -> None:
    book = _book()
    lot = next(iter(book.lots))
    try:
        book.give(lot, 100, PALACE, "vanished",
                  new_id=E.mint(HARBOUR, 10, "lot", 9))
    except W.LedgerError:
        return
    raise AssertionError("an unclassifiable transfer must be refused")


def test_the_ledger_alone_accounts_for_every_change_in_the_total() -> None:
    """Conservation as 10.8 defines it: the residual must be zero."""
    before = _book()
    lot = next(iter(before.lots))
    after = (before
             .consume(lot, 100, "consumed")
             .give(lot, 200, PALACE, "levied",
                   new_id=E.mint(HARBOUR, 10, "lot", 3))
             .create(E.mint(HARBOUR, 10, "lot", 4), "grain", 50, owner=PALACE,
                     holder=PALACE, location=HARBOUR, reason="harvested"))
    sourced, sunk, unexplained = W.conservation(before, after)["grain"]
    assert (sourced, sunk) == (50, 100)     # only what happened since `before`
    assert unexplained == 0
    assert after.total("grain") == before.total("grain") + sourced - sunk


def test_a_quantity_moved_without_a_record_is_caught() -> None:
    """The check has teeth: balanced arithmetic is not the same as an account.

    A system reaching past `engine.ownership` and editing a lot is the failure
    this exists to find, so simulate exactly that.
    """
    import dataclasses

    before = _book()
    lot = next(iter(before.lots))
    smuggled = dataclasses.replace(
        before,
        lots={lot: dataclasses.replace(before.lots[lot], quantity=400)})
    _, _, unexplained = W.conservation(before, smuggled)["grain"]
    assert unexplained == -600


def test_faults_name_owners_and_places_that_do_not_exist() -> None:
    book = _book()
    assert W.faults(book, exists=lambda i: True) == ()
    reported = W.faults(book, exists=lambda i: i != HOUSE)
    assert len(reported) == 2, reported     # owner and holder, not location


# --- obligations (10.9) -------------------------------------------------------

def _tribute() -> O.Obligation:
    return O.Obligation(
        id=E.mint(UGARIT, 4, "obligation", 0), party=UGARIT,
        beneficiary=E.authored("polity", "hatti"), clause="fixed_quantity",
        due=O.Due(kind="season", span="harvest"), good="grain", quantity=500,
        consequence="the Sun would hear of it")


def test_a_clause_must_say_what_it_requires() -> None:
    for broken in (
        dict(clause="fixed_quantity", quantity=0),
        dict(clause="share_of_yield", rate=0),
        dict(clause="service_days", quantity=0),
    ):
        try:
            O.Obligation(id=E.mint(UGARIT, 1, "obligation", 0), party=UGARIT,
                         beneficiary=PALACE, due=O.Due(kind="on_date", start=3),
                         **broken)
        except O.ClauseError:
            continue
        raise AssertionError(f"{broken} should not be a valid clause")


def test_an_on_demand_clause_has_no_calendar() -> None:
    summons = O.Obligation(
        id=E.mint(UGARIT, 1, "obligation", 1), party=HOUSE, beneficiary=PALACE,
        clause="on_demand", due=O.Due(kind="never"), quantity=1)
    assert not O.falls_due(summons, Date(1, 8, 20), {"harvest": (8, 11)})
    try:
        O.Obligation(id=E.mint(UGARIT, 1, "obligation", 2), party=HOUSE,
                     beneficiary=PALACE, clause="on_demand",
                     due=O.Due(kind="season", span="harvest"), quantity=1)
    except O.ClauseError:
        return
    raise AssertionError("an on_demand clause must not carry a due rule")


def test_a_share_scales_against_what_it_is_a_share_of() -> None:
    tenth = O.Obligation(
        id=E.mint(UGARIT, 1, "obligation", 3), party=HOUSE, beneficiary=PALACE,
        clause="share_of_yield", due=O.Due(kind="season", span="threshing"),
        good="grain", rate=100)
    assert tenth.owed(measure=8000) == 800
    assert tenth.outstanding(measure=8000) == 800


def test_the_calendar_decides_when_a_clause_falls_due() -> None:
    seasons = {"harvest": (8, 11)}
    tribute = _tribute()
    assert O.falls_due(tribute, Date(2, 9, 33), seasons)
    assert not O.falls_due(tribute, Date(2, 14, 38), seasons)

    twice = dataclasses_replace_due(tribute, O.Due(kind="every", every=6, start=10))
    assert O.falls_due(twice, Date(1, 1, 16), seasons)
    assert not O.falls_due(twice, Date(1, 1, 17), seasons)
    assert not O.falls_due(twice, Date(1, 1, 4), seasons), "not before it starts"


def dataclasses_replace_due(obligation: O.Obligation, due: O.Due) -> O.Obligation:
    import dataclasses
    return dataclasses.replace(obligation, due=due)


def test_the_lifecycle_refuses_a_step_it_does_not_allow() -> None:
    tribute = O.move(_tribute(), "due")
    assert tribute.status == "due"
    try:
        O.move(O.move(tribute, "discharged"), "due")
    except O.ClauseError:
        pass
    else:
        raise AssertionError("a discharged obligation does not fall due again")
    assert O.move(tribute, "defaulted").status == "defaulted"


def test_rendering_settles_the_status_and_records_the_history() -> None:
    tribute = O.move(_tribute(), "due")
    part = O.render(tribute, 200)
    assert part.status == "part_paid" and part.outstanding() == 300

    whole = O.render(part, 300)
    assert whole.status == "discharged" and whole.outstanding() == 0
    assert len(whole.history) >= 4     # due, rendered, part_paid, rendered...


def test_default_is_a_belief_about_consequences_not_an_effect() -> None:
    """Law 5: the engine does not punish; a party with a right acts, or does not."""
    lapsed = O.move(O.move(_tribute(), "due"), "defaulted")
    assert lapsed.consequence == "the Sun would hear of it"
    assert lapsed.rendered == 0
    # And a defaulted obligation can still be settled late, because the world
    # did not close the book on it -- only the calendar did.
    assert O.render(lapsed, 500).status == "discharged"


def test_obligation_faults_name_parties_that_do_not_exist() -> None:
    tribute = _tribute()
    assert O.faults((tribute,), exists=lambda i: True) == ()
    assert O.faults((tribute,), exists=lambda i: i != UGARIT)
