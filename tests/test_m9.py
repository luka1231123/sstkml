"""M9 house and cult: cast, mortality, marriage, succession, and divination."""
from __future__ import annotations

import dataclasses
import json

from belief.project import project
from engine import actions as A
from engine import divine, house, relations
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from session import replay, save

SEED = 8814402919


def _run(turns: int, seed: int = SEED):
    world = load_scenario("ugarit", seed)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _kill(world, person_id: str):
    people = dict(world.court.house)
    people[person_id] = dataclasses.replace(
        people[person_id], alive=False, died_turn=world.date.absolute)
    return dataclasses.replace(
        world, court=dataclasses.replace(world.court, house=people))


# --- the cast (spec 6.10) ----------------------------------------------------

def test_the_house_is_a_cast_of_named_people_who_age():
    world = load_scenario("ugarit", SEED)
    assert world.court.ruler == world.court.actor == "ammurapi"
    assert world.court.house["ammurapi"].age_turns == 34 * 24
    assert any(p.is_queen_mother for p in world.court.house.values())
    later = _run(48)
    assert later.court.house["ammurapi"].age_turns == 34 * 24 + 48


def test_heirs_are_ranked_from_turn_one_and_daughters_are_not_in_the_line():
    """Ranked every turn rather than only on birth and death, so the ordering
    is right before anything has happened."""
    world = _run(1)
    ranked = {p.id: p.is_heir_rank for p in world.court.house.values()
              if p.is_heir_rank}
    assert ranked == {"niqmaddu": 1, "ibiranu": 2}, ranked
    assert world.court.house["pidray"].is_heir_rank is None


def test_child_mortality_is_high_enough_that_one_heir_is_none():
    """Spec 6.10: 'This is why heirs past the second are insurance.'

    The claim lives in the mortality tables, which are pure in (seed, turn,
    person). Simulate the mechanic itself -- a cohort of children followed to
    sixteen -- instead of waiting out whole dynasties: the old form ran twelve
    ten-year simulations (~300s) to watch the same arithmetic happen.
    """
    import dataclasses

    from engine import house

    world = load_scenario("ugarit", SEED)
    base = world.court.house["niqmaddu"]
    fort = house._rule(world, "mortality_fortnight", 6)
    died_young = 0
    for birth in range(240):
        child = dataclasses.replace(
            base, id=f"probe_{birth}", alive=True, health=800,
            age_turns=-(birth * 24))
        for age in range(1, 17):
            if house.will_die_on(
                    world, child, birth * 24 + age * 24 + fort):
                died_young += 1
                break
    assert died_young >= 10, (
        f"{died_young} children of 240 died before sixteen; "
        "the mortality table is too kind for the succession to matter")


def test_a_dead_woman_bears_no_child():
    world = _run(40)
    while not world.court.house["ehli_nikkalu"].pregnant_until:
        world, _ = advance(world)
        assert world.date.absolute < 400, "she never conceived"
    world = _kill(world, "ehli_nikkalu")
    before = len(world.court.house)
    for _ in range(25):
        world, _ = advance(world)
    assert len(world.court.house) == before


# --- succession and the oath reset (spec 6.9, 6.10) --------------------------

def test_re_swearing_is_refused_when_it_would_be_meaningless():
    world = _run(20)
    for bad in (A.SwearOath("no_such_oath"), A.SwearOath("oath_hatti_grain")):
        try:
            apply(world, bad)
            raise AssertionError(f"{bad} was accepted")
        except ValueError:
            pass


def test_a_house_with_no_heir_fails_rather_than_inventing_one():
    world = _run(20)
    for pid in ("niqmaddu", "ibiranu"):
        world = _kill(world, pid)
    world = house._rank_heirs(world)
    world = _kill(world, "ammurapi")
    world, events = house.succeed(world)
    assert any(isinstance(e, A.SuccessionFailed) for e in events)
    assert world.court.ruler == "ammurapi", "no successor was invented"


# --- marriage abroad (spec 6.10) ---------------------------------------------

def test_a_daughter_married_abroad_leaves_the_line_and_starts_writing():
    world = _run(4)
    world, events = apply(world, A.MarryAbroad("pidray", "pharaoh"))
    assert any(isinstance(e, A.MarriedAbroad) for e in events)
    pidray = world.court.house["pidray"]
    assert pidray.married_to_court == "pharaoh"
    assert pidray.location == world.relations["pharaoh"].place
    assert pidray.is_heir_rank is None
    # She is a correspondent in her own right now, with her own bias.
    assert world.relations["pidray"].report_bias > 0

    for _ in range(20):
        world, _ = advance(world)
    hers = [L for L in world.inbox if L.sender == "pidray"]
    assert hers, "she never wrote"
    # She is voiced by the shared card, not by an entry under her own name --
    # daughters born during play cannot be authored in advance.
    item = next(it for it in project(world)["stack"] if it["sender"] == "pidray")
    assert item["persona"] == "daughter_abroad"
    from ai.voicer import persona
    assert "two houses" in persona(item["persona"])["tone"]
    asserted, true = dict(hers[0].facts), dict(hers[0].true_facts)
    assert true, "she is family and still shades what she reports"
    assert asserted["regard"] >= true["regard"]


def test_marriage_abroad_refuses_the_cases_that_would_be_nonsense():
    world = _run(4)
    for bad, why in (
        (A.MarryAbroad("niqmaddu", "pharaoh"), "a son"),
        (A.MarryAbroad("ibiranu", "pharaoh"), "a child"),
        (A.MarryAbroad("pidray", "nobody_at_all"), "an unknown court"),
        (A.MarryAbroad("ehli_nikkalu", "pharaoh"), "already married"),
    ):
        try:
            apply(world, bad)
            raise AssertionError(f"{why} was accepted")
        except ValueError:
            pass
    world, _ = apply(world, A.MarryAbroad("pidray", "pharaoh"))
    try:
        apply(world, A.MarryAbroad("pidray", "hatti_king"))
        raise AssertionError("she was married twice")
    except ValueError:
        pass


# --- divination (M13.0: fallible forecast, never privileged future) ----------

def test_a_wrong_omen_is_a_plausible_neighbour_never_noise():
    world = _run(30)
    rng = type("R", (), {"chance": lambda self, n, d: False,
                         "pick": lambda self, seq: seq[0]})()
    for band in divine.HARVEST_BANDS:
        wrong = divine._neighbour("harvest", band, rng)
        index = divine.HARVEST_BANDS.index(band)
        assert abs(divine.HARVEST_BANDS.index(wrong) - index) == 1
    assert divine._neighbour("death", "yes", rng) == "no"
    assert divine._neighbour("route", "open", rng) == "shut"


def test_an_offering_buys_a_rite_not_better_access_to_tomorrow():
    world = _run(30)
    _, plain = divine.consult(world, "harvest", "", 0)
    _, rich = divine.consult(world, "harvest", "", 4000)
    assert plain[0].reported == rich[0].reported

    before = world.court.stores["wine"]
    world, _ = apply(world, A.ConsultDiviner("harvest", "", "wine", 40))
    assert world.court.stores["wine"] == before - 40

    # Nothing anywhere records whether the forecast later proved right.
    world, _ = apply(world, A.ConsultDiviner("harvest"))
    blob = json.dumps(project(world))
    for forbidden in ("accuracy", "true_answer", "correct", "was_true"):
        assert forbidden not in blob


def test_harvest_forecast_cannot_read_the_unobserved_climate_suffix():
    world = _run(30)
    now = world.date.absolute
    changed = dataclasses.replace(
        world, climate=world.climate[:now + 1]
        + tuple(0 for _ in world.climate[now + 1:]))
    assert divine.evidence_forecast(world, "harvest", "") == \
        divine.evidence_forecast(changed, "harvest", "")
    assert divine.consult(world, "harvest", "")[1][0].reported == \
        divine.consult(changed, "harvest", "")[1][0].reported


def _advanced(world, turns):
    for _ in range(turns):
        world, _ = advance(world)
        yield world


def test_defying_an_omen_costs_legitimacy_whether_or_not_it_was_right():
    world = _run(30)
    world, _ = apply(world, A.ConsultDiviner("harvest"))
    before = world.court.legitimacy
    world, events = apply(world, A.DefyOmen("O1"))
    defied = next(e for e in events if isinstance(e, A.OmenDefied))
    assert world.court.legitimacy == before + defied.legitimacy_delta < before
    assert world.omens[0].defied_turn is not None
    # An omen nobody heard cannot be defied.
    world, _ = apply(world, A.ConsultDiviner("route"))
    world, _ = apply(world, A.SuppressOmen("O2"))
    try:
        apply(world, A.DefyOmen("O2"))
        raise AssertionError("a suppressed omen was defied")
    except ValueError:
        pass


def test_an_offering_is_actually_paid_for():
    world = _run(30)
    before = world.court.stores["wine"]
    world, _ = apply(world, A.ConsultDiviner("harvest", "", "wine", 40))
    assert world.court.stores["wine"] == before - 40
    try:
        apply(world, A.ConsultDiviner("harvest", "", "wine", 10 ** 9))
        raise AssertionError("offered wine the storehouse did not hold")
    except ValueError:
        pass


# --- what the player may see -------------------------------------------------

def test_the_player_sees_health_as_a_word_and_never_the_future():
    world = _run(30)
    belief = project(world)
    member = belief["house"]["members"][0]
    assert isinstance(member["health"], str)
    house_blob = json.dumps(belief["house"])
    for hidden in ("fertility", "will_die", "pregnant_until", "age_turns",
                   "mortality", "diviner_competence", "diviner_loyalty"):
        assert hidden not in house_blob, f"{hidden} reached the player"


def test_a_successor_actors_toml_never_heard_of_is_still_named():
    """A ruler born in play has no entry in actors.toml, so the renderer falls
    back to the house rather than printing a person id at the player. Checked
    on a child born mid-run, since 'Niqmaddu' the name and 'niqmaddu' the id
    are the same word and would prove nothing."""
    from tui import render
    world = load_scenario("ugarit", SEED)
    born = None
    while born is None:
        world, events = advance(world)
        born = next((e.child_id for e in events if isinstance(e, A.ChildBorn)), None)
        assert world.date.absolute < 400, "no child was born to test with"

    belief = project(world)
    child = next(p for p in belief["house"]["members"] if p["id"] == born)
    assert child["name"] != born, "the child kept its identifier as a name"
    assert render.actor_name(born, belief["house"]) == child["name"]
    # And an id with no house entry and no actors.toml row degrades to itself.
    assert render.actor_name("nobody_at_all", belief["house"]) == "nobody_at_all"
    assert "THE HOUSE" in render.house_screen(belief)


# --- determinism -------------------------------------------------------------

