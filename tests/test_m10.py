"""M10: plague and the archive puzzle (spec 6.12, 6.17, 8.8)."""
from __future__ import annotations

import dataclasses

from ai import librarian
from ai.client import FORBIDDEN_KEYS, PromptLeak, safe_fields
from belief.project import project
from engine import actions as A
from engine import archive, plague
from engine.reduce import apply
from engine.state import Place
from engine.tick import advance
from load import load_scenario

SEED = 8814402919


def _run(turns: int, seed: int = SEED):
    world = load_scenario("ugarit", seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


# --- the compartment model ---------------------------------------------------
def test_a_single_case_cannot_start_an_epidemic_so_we_do_not_seed_one():
    """The integer floor makes I=1 a fixed point: S*I*beta // (pop*1000) is 0,
    and so are recoveries and deaths. The sickness would sit there for ever."""
    stuck = Place(id="x", name="X", population=7000, susceptible=6999, infected=1)
    assert plague.step_place(stuck, 520, 180, 90) == stuck
    # So introduction seeds an outbreak, not a patient.
    world = _run(4)
    assert plague.seed_cases(world.places["seat"]) >= plague.SEED_FLOOR
    seeded = plague.seed_place(world, "seat")
    assert seeded.places["seat"].infected == plague.seed_cases(world.places["seat"])
    assert plague.step_place(seeded.places["seat"], 520, 180, 90).infected > \
        seeded.places["seat"].infected


def test_the_epidemic_grows_burns_out_and_leaves_the_dead_behind():
    world, _ = plague.begin(_run(52), "seat")
    peak = 0
    for _ in range(70):
        world, _ = advance(world)
        peak = max(peak, world.places["seat"].infected)
    seat = world.places["seat"]
    assert peak > 500, "an epidemic that never grows is not an epidemic"
    assert seat.infected < peak // 10, "it must burn out, not plateau"
    # Nobody is lost from the accounting: the living plus the dead is the city.
    assert plague.living(seat) + seat.dead == seat.population
    assert seat.dead > 0 and seat.recovered > seat.dead


def test_the_dead_come_off_the_ration_lists():
    world = _run(52)
    before = sum(g.size for g in world.court.dependents.values()
                 if g.place == world.court.seat)
    world, _ = plague.begin(world, "seat")
    for _ in range(40):
        world, _ = advance(world)
    after = sum(g.size for g in world.court.dependents.values()
                if g.place == world.court.seat)
    assert after < before, "a plague at the seat must reach the ration lists"
    assert all(g.size >= 1 for g in world.court.dependents.values()), (
        "a group is never wiped out entirely; there is always somebody left")


def test_quarantine_closes_the_road_and_costs_the_correspondent():
    world = _run(20)
    other = next(actor for actor, r in sorted(world.relations.items())
                 if r.place != world.court.seat)
    place = world.relations[other].place
    before = world.relations[other].esteem
    world, _ = apply(world, A.Quarantine(place))
    assert place in world.court.quarantined
    assert world.relations[other].esteem < before, (
        "nobody accepts that his own city is the reason")
    assert plague.route_is_quarantined(world.court, place, world.court.seat)
    world, _ = apply(world, A.Quarantine(place, lift=True))
    assert place not in world.court.quarantined


def test_a_city_cannot_be_quarantined_against_itself():
    world = _run(4)
    try:
        apply(world, A.Quarantine(world.court.seat))
    except ValueError:
        return
    raise AssertionError("quarantining the seat must be refused")


# --- the theological layer ----------------------------------------------------
def test_the_vows_of_the_predecessors_do_not_lapse_and_two_of_them_are_broken():
    """Spec 6.12 wants a cause that may have been sworn by a predecessor. Since
    M9 every oath lapses when the man who swore it dies -- so the archive puzzle
    only exists because a vow to a GOD binds the house, not the man (D26)."""
    world = _run(52)
    vows = {o.id: o for o in world.oaths if o.binds_house}
    assert set(vows) == {"vow_first_rain", "vow_dead_at_the_gate",
                         "vow_threshing_floor"}
    assert not any(v.lapsed for v in vows.values())
    assert all(v.sworn_by != world.court.ruler for v in vows.values()), (
        "these were sworn by men Ammurapi never met")
    liability = world.court.liability
    # The two that name festivals no longer on the calendar are in violation,
    # every year, silently, and have been since before turn 1.
    assert liability["vow_first_rain"] > 0
    assert liability["vow_dead_at_the_gate"] > 0
    # The third names `first_fruits`, which IS kept -- so it can be eliminated
    # by a reader who checks the rite list, and can never be the cause.
    assert liability["vow_threshing_floor"] == 0
    assert any(r.id == "first_fruits" for r in world.court.rites)


def test_the_cause_is_a_genuinely_violated_oath_and_the_field_is_three():
    world = _run(52)
    cause = plague.designate_cause(world)
    assert world.court.liability.get(cause, 0) > 0, (
        "the gods are never angry about an oath that was kept")
    candidates = sorted(k for k, v in world.court.liability.items() if v > 0)
    assert len(candidates) == 3, (
        "spec 6.12: a careful reader narrows the field to three, not to one")
    assert cause in candidates


def test_the_cause_draw_is_uniform_and_not_dominated_by_the_worst_breach():
    """An earlier version weighted the draw by liability, which made Ugarit's
    Hatti grain oath the answer in about three runs in four."""
    world = _run(52)
    liability = world.court.liability
    worst = max(liability, key=lambda k: liability[k])
    seen = set()
    for n in range(40):
        probe = dataclasses.replace(
            world, seed=world.seed + n * 7919,
            court=dataclasses.replace(world.court, liability=liability))
        seen.add(plague.designate_cause(probe))
    assert len(seen) == 3, f"every candidate must be reachable; got {seen}"
    assert worst in seen


def test_expiation_tells_the_player_nothing_either_way():
    world, _ = plague.begin(_run(52), "seat")
    cause = world.plague.cause_oath_id
    wrong = next(o.id for o in world.oaths if o.id != cause)

    bad, bad_events = plague.expiate(world, wrong, offering=500)
    good, good_events = plague.expiate(world, cause, offering=500)
    # The event carries the oath and the offering, and no verdict.
    assert [type(e).__name__ for e in bad_events] == ["OathExpiated"]
    assert bad_events[0].oath_id == wrong
    assert not any(f.name == "correct" for f in dataclasses.fields(A.OathExpiated))
    # Nor does Belief, on either branch. Note that Belief DOES name the oaths he
    # made offerings against, including the right one -- he remembers what he
    # did. What is absent is any word about how it was received.
    assert project(bad)["plague"]["offerings_made"] == [wrong]
    assert project(good)["plague"]["offerings_made"] == [cause]
    for w in (bad, good):
        text = repr(project(w))
        assert "correct" not in text and "expiated_correctly" not in text
    # The only difference anywhere is the curve.
    assert plague.effective_beta(bad) == world.plague.beta
    assert plague.effective_beta(good) < world.plague.beta


def test_the_right_offering_actually_bends_the_curve():
    begun, _ = plague.begin(_run(52), "seat")
    cause = begun.plague.cause_oath_id
    wrong = next(o.id for o in begun.oaths if o.id != cause)

    def dead_after(world, turns):
        for _ in range(turns):
            world, _ = advance(world)
        return world.places["seat"].dead

    right, _ = plague.expiate(begun, cause, 0)
    other, _ = plague.expiate(begun, wrong, 0)
    assert dead_after(right, 40) < dead_after(other, 40)
    # ...and expiating the right oath twice does not compound.
    twice, _ = plague.expiate(right, cause, 0)
    assert twice.plague.expiated_correctly_turn == \
        right.plague.expiated_correctly_turn


def test_a_new_king_inherits_the_debts_to_heaven_and_none_of_the_others():
    from engine import house
    world = _run(120)
    world = dataclasses.replace(world, court=dataclasses.replace(
        world.court, house={
            k: (dataclasses.replace(v, alive=False, died_turn=world.date.absolute)
                if k == world.court.ruler else v)
            for k, v in world.court.house.items()}))
    world, _ = house.succeed(world)
    assert world.court.liability["oath_hatti_grain"] == 0
    assert world.court.liability["vow_dead_at_the_gate"] > 0, (
        "the oldest thing the new king owns is a debt he has not heard of")


# --- the archive --------------------------------------------------------------
def test_the_predecessor_archive_is_there_before_turn_one():
    world = load_scenario("ugarit", SEED)
    assert len(world.documents) >= 20, "spec 6.12 asks for 20 to 40 documents"
    assert all(d.received_turn < 0 for d in world.documents)
    # The three vows have tablets, and the tablets say which festival and when.
    refs = {d.ref for d in world.documents}
    assert {"PA-UG-003", "PA-UG-011", "PA-UG-019"} <= refs


def test_the_archive_sorts_by_received_turn_and_nothing_else():
    world = _run(30)
    hits = archive.search(world, "the")
    turns = [d.received_turn for d in hits]
    assert turns == sorted(turns)
    # `dated_as` is the sender's own calendar and is deliberately not sortable.
    dates = [d.dated_as for d in world.documents if d.dated_as]
    assert dates != sorted(dates), (
        "if the senders' dates happened to sort, 6.17 would be toothless here")


def test_search_is_and_not_or_and_costs_an_hour():
    world = _run(30)
    both = archive.search(world, "vow festival")
    assert both and all(
        "vow" in archive._haystack(d) and "festival" in archive._haystack(d)
        for d in both)
    assert len(both) < len(archive.search(world, "vow")) + \
        len(archive.search(world, "festival"))
    world2, events = apply(world, A.SearchArchive("vow"))
    assert "vow" in world2.court.searched
    assert isinstance(events[0], A.ArchiveSearched) and events[0].hits > 0
    # The hour lapses with the fortnight, like a ledger inspection.
    world3, _ = advance(world2)
    assert world3.court.searched == ()


def test_letters_are_filed_as_they_arrive():
    world = _run(30)
    # Filed during play, as against the predecessor archive -- which is also
    # full of letters, and whose refs are authored rather than generated.
    letters = [d for d in world.documents if d.received_turn >= 0]
    assert letters, "the archive must grow during play, not only at load"
    assert all(d.ref.startswith("L-") for d in letters)
    assert all(d.kind in ("letter_in", "letter_out") for d in letters)
    # Filing is idempotent: replay must not double up the record.
    before = len(world.documents)
    for letter in world.inbox:
        world = archive.file_letter(world, letter)
    assert len(world.documents) == before


def test_the_reader_can_reach_the_puzzle_from_a_plain_search():
    """The one deduction the archive fully rewards: two of the three vows name a
    festival that is not on the calendar, and the third names one that is."""
    world = _run(30)
    hits = archive.search(world, "vow")
    bodies = " ".join(d.body for d in hits)
    kept = {r.id for r in world.court.rites}
    assert "first rain" in bodies and "gate of the city" in bodies
    assert "festival_first_rain" not in kept and "bread_at_the_gate" not in kept
    assert "first_fruits" in kept
    # And the temple has been writing about it for two generations.
    complaints = archive.search(world, "festival first rain")
    assert len(complaints) >= 2


# --- the librarian (spec 8.8) -------------------------------------------------
def _hits(world, query):
    return (project(world).get("archive_index") or {}).get("hits", {}).get(query, [])


def test_the_librarian_prompt_carries_no_answer_and_no_world():
    world = _run(30)
    world, _ = plague.begin(world, "seat")
    world, _ = apply(world, A.SearchArchive("vow"))
    hits = _hits(world, "vow")
    assert len(hits) >= librarian.MIN_HITS
    prompt = "\n".join(m["content"] for m in librarian.build_prompt("vow", hits))
    assert world.plague.cause_oath_id not in prompt
    for key in ("cause_oath_id", "liability", "beta", "infected"):
        assert key not in prompt
    assert "cause_oath_id" in FORBIDDEN_KEYS


def test_safe_fields_still_refuses_the_plague_internals():
    for key in ("cause_oath_id", "beta", "infected", "expiated_correctly_turn"):
        try:
            safe_fields({key: 1})
        except PromptLeak:
            continue
        raise AssertionError(f"{key} must not be prompt-safe")


def test_the_librarian_falls_back_to_a_finding_aid_with_no_model():
    world = _run(30)
    world, _ = apply(world, A.SearchArchive("vow"))
    hits = _hits(world, "vow")
    text, source = librarian.summarize("vow", hits, SEED, 30, client=None)
    assert source == "fallback"
    for hit in hits:
        assert hit["ref"] in text, "a finding aid must cite everything it found"


def test_the_librarian_rejects_an_invented_citation():
    class Inventing:
        def __init__(self):
            self.calls = 0

        def call(self, *a, **k):
            self.calls += 1
            return "Three tablets, my lord. [PA-UG-003] and also [PA-UG-999]."

    world = _run(30)
    world, _ = apply(world, A.SearchArchive("vow"))
    hits = _hits(world, "vow")
    client = Inventing()
    text, source = librarian.summarize("vow", hits, SEED, 30, client=client)
    assert client.calls == 2, "it must be given exactly one chance to correct"
    assert source == "fallback", (
        "a citation the archive does not contain would send the king looking "
        "for a tablet that was never there")
    assert "PA-UG-999" not in text


# --- belief boundary ----------------------------------------------------------
def test_belief_gives_graves_and_never_the_compartments():
    world, _ = plague.begin(_run(52), "seat")
    for _ in range(24):
        world, _ = advance(world)
    b = project(world)["plague"]
    assert b["sickness_at_seat"] is True
    assert b["burials_at_seat"] > 0
    seat = world.places["seat"]
    assert set(b) == {"sickness_at_seat", "burials_at_seat", "quarantined",
                      "offerings_made"}
    # The count is the scribe's copy of the gravediggers', not the true total.
    assert isinstance(b["burials_at_seat"], int)
    text = repr(project(world))
    for value in (seat.infected, seat.susceptible, seat.recovered):
        assert f"'infected': {value}" not in text
    assert "beta" not in text and "cause_oath_id" not in text


def test_nothing_announces_whether_the_offering_was_right():
    from tui import render
    world, _ = plague.begin(_run(52), "seat")
    cause = world.plague.cause_oath_id
    world, events = plague.expiate(world, cause, 200)
    lines = " ".join(render.events_lines(events, world.court))
    assert "offering is made" in lines
    for word in ("correct", "right", "accepted", "worked", "heard"):
        assert word not in lines.lower(), (
            "the epidemic curve is the only feedback there is (spec 6.12)")


def test_the_state_hash_still_covers_a_plague_run():
    from engine.core import state_hash
    a, _ = plague.begin(_run(52), "seat")
    b, _ = plague.begin(_run(52), "seat")
    for _ in range(10):
        a, _ = advance(a)
        b, _ = advance(b)
    assert state_hash(a) == state_hash(b)
    c, _ = plague.expiate(a, a.plague.cause_oath_id, 100)
    assert state_hash(c) != state_hash(a)
