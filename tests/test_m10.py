"""M10: plague and the archive puzzle (spec 6.12, 6.17, 8.8)."""
from __future__ import annotations

import dataclasses

from ai import librarian
from ai.client import FORBIDDEN_KEYS, PromptLeak, safe_fields
from belief.project import project
from engine import actions as A
from engine import archive, plague, relations
from engine.core import Date
from engine.reduce import apply
from engine.state import Place
from engine.tick import advance
from load import load_campaign

SEED = 8814402919


def _run(turns: int, seed: int = SEED):
    world = load_campaign("seat", seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _isolated(turns: int = 0, seed: int = SEED):
    """A unit-test world with the authored campaign import disabled."""
    world = load_campaign("seat", seed)
    world = dataclasses.replace(
        world, plague=dataclasses.replace(
            world.plague, import_place="", import_turn=-1, import_cases=0))
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
    world = _run(0)
    assert plague.seed_cases(world.places["seat"]) >= plague.SEED_FLOOR
    seeded = plague.seed_place(world, "seat")
    assert seeded.places["seat"].infected == plague.seed_cases(world.places["seat"])
    assert plague.step_place(seeded.places["seat"], 520, 180, 90).infected > \
        seeded.places["seat"].infected


def test_quarantine_closes_the_road_and_costs_the_correspondent():
    world = _run(0)
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
    world = _run(0)
    try:
        apply(world, A.Quarantine(world.court.seat))
    except ValueError:
        return
    raise AssertionError("quarantining the seat must be refused")


# --- ritual interpretation without supernatural physics ---------------------
def test_the_vows_of_the_predecessors_do_not_lapse_and_two_of_them_are_broken():
    """The archive can preserve obligations without making them pathogens."""
    world = _run(0)
    vows = {o.id: o for o in world.oaths if o.binds_house}
    assert set(vows) == {"vow_first_rain", "vow_dead_at_the_gate",
                         "vow_threshing_floor"}
    assert not any(v.lapsed for v in vows.values())
    assert all(v.sworn_by != world.court.ruler for v in vows.values()), (
        "these were sworn by men Ammurapi never met")
    expected = {
        4: A.OathViolated("vow_first_rain", "maintain_rite"),
        13: A.OathViolated("vow_dead_at_the_gate", "maintain_rite"),
    }
    for fortnight, breach in expected.items():
        dated = dataclasses.replace(world, kernel=dataclasses.replace(
            world.kernel, date=Date(
                world.date.year, fortnight, world.date.absolute)))
        unchanged, events = relations.audit_oaths(dated)
        assert unchanged == dated and breach in events
    dated = dataclasses.replace(world, kernel=dataclasses.replace(
        world.kernel, date=Date(world.date.year, 9, world.date.absolute)))
    _, events = relations.audit_oaths(dated)
    assert A.OathViolated(
        "vow_threshing_floor", "maintain_rite") not in events
    assert any(r.id == "first_fruits" for r in world.court.rites)


def test_plague_state_has_no_objective_oath_cause_or_correct_ritual():
    names = {field.name for field in dataclasses.fields(type(
        load_campaign("seat", SEED).plague))}
    assert "cause_oath_id" not in names
    assert "expiated_correctly_turn" not in names


def test_hidden_divine_liability_and_misfortune_state_are_gone():
    world = load_campaign("seat", SEED)
    court_fields = {
        field.name for field in dataclasses.fields(type(world.court))}
    world_fields = {
        field.name for field in dataclasses.fields(type(world))}
    assert "liability" not in court_fields
    assert "misfortune_weight" not in court_fields
    assert "misfortune_deck" not in world_fields


# --- the archive --------------------------------------------------------------
def test_the_predecessor_archive_is_there_before_turn_one():
    world = load_campaign("seat", SEED)
    assert len(world.documents) >= 20, "spec 6.12 asks for 20 to 40 documents"
    assert all(d.received_turn < 0 for d in world.documents)
    # The three vows have tablets, and the tablets say which festival and when.
    refs = {d.ref for d in world.documents}
    assert {"PA-UG-003", "PA-UG-011", "PA-UG-019"} <= refs


def test_the_archive_sorts_by_received_turn_and_nothing_else():
    world = _run(0)
    hits = archive.search(world, "the")
    turns = [d.received_turn for d in hits]
    assert turns == sorted(turns)
    # `dated_as` is the sender's own calendar and is deliberately not sortable.
    dates = [d.dated_as for d in world.documents if d.dated_as]
    assert dates != sorted(dates), (
        "if the senders' dates happened to sort, 6.17 would be toothless here")


def test_search_is_and_not_or_and_costs_an_hour():
    world = _run(0)
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
    world = _run(4)
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


def test_the_reader_can_find_neglected_rites_without_finding_a_divine_answer():
    world = _run(0)
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
    world = _run(0)
    world, _ = plague.begin(world, "seat")
    world, _ = apply(world, A.SearchArchive("vow"))
    hits = _hits(world, "vow")
    assert len(hits) >= librarian.MIN_HITS
    prompt = "\n".join(m["content"] for m in librarian.build_prompt("vow", hits))
    for key in ("cause_oath_id", "liability", "beta", "infected"):
        assert key not in prompt
    assert "cause_oath_id" not in {
        field.name for field in dataclasses.fields(type(world.plague))}
    assert "cause_oath_id" in FORBIDDEN_KEYS


def test_safe_fields_still_refuses_the_plague_internals():
    for key in ("cause_oath_id", "beta", "infected", "expiated_correctly_turn"):
        try:
            safe_fields({key: 1})
        except PromptLeak:
            continue
        raise AssertionError(f"{key} must not be prompt-safe")


def test_the_librarian_falls_back_to_a_finding_aid_with_no_model():
    world = _run(0)
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

    world = _run(0)
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
    world, _ = plague.begin(_isolated(), "seat")
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


def test_an_offering_is_reported_only_as_a_ritual_act():
    from tui import render
    world, _ = plague.begin(_isolated(), "seat")
    world, events = plague.expiate(world, world.oaths[0].id, 200)
    lines = " ".join(render.events_lines(events, world.court))
    assert "offering is made" in lines
    for word in ("correct", "right", "accepted", "worked", "heard"):
        assert word not in lines.lower()
