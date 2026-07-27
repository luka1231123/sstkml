"""The house and the dynasty (spec 6.10). Graduated from systems.py (D1).

Not a stat block. A cast. Everyone in `Court.house` is a named person who ages,
sickens, marries, bears children, and dies on a schedule that was fixed the
moment the seed was chosen -- which is what lets divination (6.11) read a true
future value about them without the engine cheating.

Two rules here carry most of the weight.

**Child mortality is high**, because it was. This is why heirs past the second
are insurance and simultaneously factions: every spare son is a man with a
claim, and the queen mother has opinions about which of them she prefers.

**Succession resets every oath in the game.** Oaths are personal and
non-transitive (6.9): they are sworn by a named man to a named man before named
gods. When the man dies, the oath lapses. Nothing is broken and nobody is at
fault; the relationship simply no longer exists and somebody has to swear
again, and he will want something for it. The new ruler also begins a *new*
regnal year 1, which breaks every date correlation the player had built up.
That is not cruelty, it is the historical condition.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import Date, lerp_table, stream
from engine.state import Court, HouseMember, World

YEAR = 24


def _table(world: World, name: str, x: int, default: int = 0) -> int:
    points = world.house_tables.get(name)
    return default if not points else lerp_table(points, x)


def _rule(world: World, name: str, default: int = 0) -> int:
    return world.house_rules.get(name, default)


def living(court: Court) -> list[HouseMember]:
    return [p for p in sorted(court.house.values(), key=lambda p: p.id)
            if p.alive]


def fertility(world: World, person: HouseMember) -> int:
    """Age-curved, then dragged down by poor health."""
    table = "fertility_female" if person.sex == "f" else "fertility_male"
    base = _table(world, table, person.age_turns)
    return base * person.health // 1000


def will_die_on(world: World, person: HouseMember, turn: int) -> bool:
    """Would this person's yearly mortality check kill them on `turn`?

    Pure in (seed, turn, person), so it can be asked about the FUTURE without
    advancing anything. That is the whole reason divination can be honest: the
    engine reads a fact that is already true rather than deciding one and then
    pretending it was fated.
    """
    if not person.alive or turn % YEAR != _rule(world, "mortality_fortnight", 6):
        return False
    age = person.age_turns + (turn - world.date.absolute)
    if age < 0:
        return False
    chance = _table(world, "mortality_by_age", age)
    chance = chance * _table(world, "mortality_by_health", person.health, 1000) // 1000
    return stream(world.seed, turn, "house.mortality", person.id).chance(chance, 1000)


def dies_within(world: World, person_id: str, turns: int) -> bool:
    """True if this person's death is already written in the next `turns`."""
    person = world.court.house.get(person_id)
    if person is None or not person.alive:
        return False
    now = world.date.absolute
    return any(will_die_on(world, person, t)
               for t in range(now + 1, now + turns + 1))


# --- A5: aging, health, conception, births, deaths ---------------------------
def step(world: World) -> tuple[World, list]:
    court = world.court
    if not court.house:
        return world, []
    now = world.date.absolute
    events: list = []
    people = {pid: dataclasses.replace(p, age_turns=p.age_turns + 1)
              if p.alive else p
              for pid, p in court.house.items()}

    # Conception: co-located, married-within-the-house, fertile pairs. A
    # daughter married abroad is not co-located with anyone here, which is
    # exactly the point of having sent her.
    scheduled = list(world.schedule)
    seen: set[tuple[str, str]] = set()
    for pid in sorted(people):
        person = people[pid]
        if not (person.alive and person.spouse and person.sex == "f"):
            continue
        if person.pregnant_until is not None:
            continue                  # already carrying one
        spouse = people.get(person.spouse)
        if not (spouse and spouse.alive and spouse.location == person.location):
            continue
        pair = tuple(sorted((pid, spouse.id)))
        if pair in seen:
            continue
        seen.add(pair)
        mean = (fertility(world, person) + fertility(world, spouse)) // 2
        chance = _table(world, "conception", mean)
        if not chance:
            continue
        if stream(world.seed, now, "house.conception", "|".join(pair)).chance(chance, 1000):
            born = now + _rule(world, "gestation_turns", 20)
            scheduled.append(_scheduled(born, A.ChildBorn(
                child_id="", mother=pid, father=spouse.id, sex="")))
            people[pid] = dataclasses.replace(person, pregnant_until=born)
            events.append(A.Conceived(pid, spouse.id, born))

    court = dataclasses.replace(court, house=people)
    world = dataclasses.replace(
        world, court=court,
        schedule=tuple(sorted(scheduled, key=_schedule_key)))
    # Re-rank every turn rather than only on birth and death: it is cheap, it
    # is idempotent, and it means the ranking is right on turn one without load
    # having to reach into the engine to arrange it.
    world = _rank_heirs(world)

    # Yearly mortality, once a year, on an authored fortnight so that births,
    # deaths and the turn of the year are not all on one tick.
    if now % YEAR == _rule(world, "mortality_fortnight", 6):
        world, dead = _mortality(world)
        events += dead

    return world, events


def _schedule_key(item):
    from engine.core import canonical_json
    return (item.at, canonical_json(item.payload))


def _scheduled(at: int, payload):
    from engine.state import Scheduled
    return Scheduled(at=at, payload=payload)


def _mortality(world: World) -> tuple[World, list]:
    now = world.date.absolute
    people = dict(world.court.house)
    events: list = []
    for pid in sorted(people):
        person = people[pid]
        if not person.alive or not will_die_on(world, person, now):
            continue
        people[pid] = dataclasses.replace(
            person, alive=False, died_turn=now, is_heir_rank=None)
        events.append(A.HouseMemberDied(pid, person.name, person.age_turns // YEAR))
    if not events:
        return world, []
    world = dataclasses.replace(
        world, court=dataclasses.replace(world.court, house=people))
    # The ruler among them is a different kind of event entirely.
    if not people[world.court.ruler].alive:
        world, succession = succeed(world)
        events += succession
    return world, events


def bear_child(world: World, event) -> tuple[World, list]:
    """A scheduled birth arrives (A3). Sex and health are drawn here, not at
    conception, so nothing about the child exists before it is born."""
    court = world.court
    mother = court.house.get(event.mother)
    if mother is None or not mother.alive:
        return world, []          # she did not live to bear it
    now = world.date.absolute
    seq = sum(1 for p in court.house.values() if p.father == event.father) + 1
    child_id = f"{event.father}_c{seq}"
    rng = stream(world.seed, now, "house.sex", child_id)
    sex = "f" if rng.chance(1, 2) else "m"
    name = _child_name(world, child_id, sex)
    people = dict(court.house)
    people[mother.id] = dataclasses.replace(mother, pregnant_until=None)
    people[child_id] = HouseMember(
        id=child_id, name=name, sex=sex, age_turns=0,
        health=600 + rng.int(300), location=mother.location,
        mother=mother.id, father=event.father, faction="house")
    world = dataclasses.replace(
        world, court=dataclasses.replace(court, house=people))
    world = _rank_heirs(world)
    return world, [A.ChildBorn(child_id, mother.id, event.father, sex)]


def _child_name(world: World, child_id: str, sex: str) -> str:
    pool = world.house_names_f if sex == "f" else world.house_names_m
    if not pool:
        return child_id
    # Keyed on the child id, so the same child is the same person on replay.
    return stream(world.seed, 0, "names", child_id).pick(pool)


# --- heirs and succession (spec 6.10) ----------------------------------------
def _rank_heirs(world: World) -> World:
    """Rank the living sons of the ruler by age, eldest first.

    Daughters married abroad are deliberately not ranked: they are an
    instrument of foreign policy, not a line of succession, and the moment they
    leave they belong to another house.
    """
    court = world.court
    ruler = court.house.get(court.ruler)
    if ruler is None:
        return world
    candidates = [p for p in living(court)
                  if p.father == ruler.id and p.sex == "m"
                  and p.married_to_court is None]
    candidates.sort(key=lambda p: (-p.age_turns, p.id))
    people = dict(court.house)
    for pid, person in people.items():
        if person.is_heir_rank is not None:
            people[pid] = dataclasses.replace(person, is_heir_rank=None)
    for rank, person in enumerate(candidates, 1):
        people[person.id] = dataclasses.replace(
            people[person.id], is_heir_rank=rank)
    return dataclasses.replace(
        world, court=dataclasses.replace(court, house=people))


def succession_score(world: World, person: HouseMember) -> int:
    """Deterministic resolution over heir rank, faction backing, legitimacy,
    and who is physically at the seat when it matters (spec 6.10)."""
    score = 1000 - (person.is_heir_rank or 9) * 120
    if person.location == world.court.seat:
        score += 200                     # possession, nine tenths of it
    if person.age_turns >= _rule(world, "majority_turns", 360):
        score += 150
    else:
        score -= 200                     # a child king is a regency and a quarrel
    # The queen mother's backing is worth having, and she has her own view.
    mother = next((p for p in living(world.court) if p.is_queen_mother), None)
    if mother is not None and person.mother == mother.id:
        score += 180
    score += world.court.legitimacy // 10
    return score


def succeed(world: World) -> tuple[World, list]:
    """The ruler is dead. Resolve, reset every oath, and start regnal year 1."""
    court = world.court
    candidates = [p for p in living(court) if p.is_heir_rank is not None]
    if not candidates:
        # No heir in the house. The line ends here; the seat does not.
        return world, [A.SuccessionFailed(court.ruler)]

    ranked = sorted(candidates,
                    key=lambda p: (-succession_score(world, p), p.id))
    heir = ranked[0]
    contested = (len(ranked) > 1
                 and succession_score(world, ranked[1])
                 > succession_score(world, heir) - 150)

    legitimacy = max(_rule(world, "succession_legitimacy_floor", 400),
                     court.legitimacy)
    if contested:
        legitimacy = max(0, legitimacy
                         + _rule(world, "contested_legitimacy_penalty", -160))

    # Spec 6.9: every oath lapses. Not broken -- lapsed. The man who swore is
    # dead, and nobody owes anybody anything until somebody swears again.
    # ...except a vow to a god, which binds the house and not the man (M10).
    # The new king inherits his predecessor's debts to heaven and none of his
    # debts to other kings, which is exactly the wrong way round for him.
    oaths = tuple(
        dataclasses.replace(o, lapsed=True)
        if not o.dissolved and not o.binds_house else o
        for o in world.oaths)

    court = dataclasses.replace(
        court, ruler=heir.id, legitimacy=legitimacy,
        reigns=court.reigns + 1,
        # A new man's own liability starts at nothing. He did not swear it --
        # except where the debt is to a god, which is owed by the house and not
        # by the man, and which he therefore inherits in full without ever being
        # told it exists (M10, D26). It is the oldest thing he owns.
        liability={oath.id: (court.liability.get(oath.id, 0)
                             if oath.binds_house else 0)
                   for oath in oaths},
        actor=heir.id)
    # A NEW regnal year 1. Every date correlation the player built is now void,
    # which is the historical condition and not a punishment.
    world = dataclasses.replace(
        world, court=court,
        date=Date(year=1, fortnight=world.date.fortnight,
                  absolute=world.date.absolute),
        oaths=oaths)
    world = _rank_heirs(world)
    return world, [A.RulerSucceeded(heir.id, heir.name, contested,
                                    len(ranked) - 1)]


# --- marriage abroad (spec 6.10) ---------------------------------------------
def marry_abroad(world: World, person_id: str,
                 actor: str) -> tuple[World, list]:
    """Send a daughter to a foreign court. She stays in the house list because
    she is still family; she stops being co-located, stops being an heir, and
    starts writing home with information you cannot get any other way -- with
    her own agenda, which is not yours."""
    court = world.court
    person = court.house.get(person_id)
    if person is None or not person.alive:
        raise ValueError(f"no such living person: {person_id}")
    if person.married_to_court:
        raise ValueError(f"{person.name} is already married abroad")
    if person.spouse:
        raise ValueError(f"{person.name} is already married")
    if person.sex != "f":
        raise ValueError("a son is not an instrument of foreign policy here")
    if person.age_turns < _rule(world, "majority_turns", 360):
        raise ValueError(f"{person.name} is too young")
    relation = world.relations.get(actor)
    if relation is None:
        raise ValueError(f"no such correspondent: {actor}")

    people = dict(court.house)
    people[person_id] = dataclasses.replace(
        person, married_to_court=actor, location=relation.place,
        is_heir_rank=None,
        own_agenda=person.own_agenda or "secure her own position abroad")
    # She becomes a correspondent in her own right, with her own report bias.
    # She is family, so she starts well regarded; she is abroad and building a
    # position there, so what she writes home is shaded to serve it.
    from engine.state import Relation
    relations = dict(world.relations)
    relations[person_id] = Relation(
        other=person_id, place=relation.place,
        status_claim="daughter", their_status_claim="daughter",
        esteem=800, obligation=0,
        last_gift_from_us=0, last_gift_from_them=0,
        best_known_rival_gift=0, known_rival_gift_source=None,
        report_bias=500)

    world = dataclasses.replace(
        world, court=dataclasses.replace(court, house=people),
        relations=relations)
    world = _rank_heirs(world)
    return world, [A.MarriedAbroad(person_id, person.name, actor)]
