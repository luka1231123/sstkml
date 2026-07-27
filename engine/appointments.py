"""Appointments, dismissals, placements, and the named heir (spec 6.22)."""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.state import Relation, World


def _ranked(world: World) -> World:
    # Ranking is an engine invariant; actions may be issued before the first
    # A5 step in tests and replay tools, so establish it here as well.
    from engine.house import _rank_heirs
    return _rank_heirs(world)


def _canonical(world: World, post: str) -> str:
    post = post.strip()
    if post.startswith("institution:"):
        post = post.split(":", 1)[1]
    if post in world.court.institutions:
        return post
    if ":" not in post:
        raise ValueError(f"no such post: {post}")
    kind, target = post.split(":", 1)
    if kind == "governor" and target in world.places:
        return post
    if kind == "command" and any(
            formation.id == target for formation in world.court.formations):
        return post
    if kind == "court" and target in world.relations:
        return post
    raise ValueError(f"no such post: {post}")


def _holder(world: World, post: str) -> str:
    if post in world.court.institutions:
        return world.court.institutions[post].head
    if post.startswith("command:"):
        target = post.split(":", 1)[1]
        return next((f.commander for f in world.court.formations
                     if f.id == target), "")
    return next((p.id for p in world.court.house.values()
                 if p.alive and p.post == post), "")


def _clear_post(world: World, post: str) -> World:
    court = world.court
    people = dict(court.house)
    holder = _holder(world, post)
    if holder in people:
        people[holder] = dataclasses.replace(
            people[holder], post="", location=court.seat)
    institutions = dict(court.institutions)
    if post in institutions:
        institutions[post] = dataclasses.replace(institutions[post], head="")
    formations = tuple(
        dataclasses.replace(f, commander="")
        if post == f"command:{f.id}" else f
        for f in court.formations)
    return dataclasses.replace(
        world, court=dataclasses.replace(
            court, house=people, institutions=institutions,
            formations=formations))


def place(world: World, person_id: str, post: str) -> tuple[World, list]:
    post = _canonical(world, post)
    court = world.court
    person = court.house.get(person_id)
    if person is None or not person.alive:
        raise ValueError(f"no such living person: {person_id}")
    if person_id == court.ruler:
        raise ValueError("the ruler cannot be sent to hold his own office")
    if person.age_turns < world.house_rules.get("majority_turns", 360):
        raise ValueError(f"{person.name} is too young to hold a post")
    if person.married_to_court:
        raise ValueError(f"{person.name} belongs to another court now")
    if person.post == post:
        raise ValueError(f"{person.name} already holds that post")

    displaced = _holder(world, post)
    if displaced:
        world = _clear_post(world, post)
    # One person cannot hold two offices. The old interest remains even when
    # the old office does not.
    person = world.court.house[person_id]
    if person.post:
        world = _clear_post(world, person.post)
        person = world.court.house[person_id]

    court = world.court
    people = dict(court.house)
    location = court.seat
    institutions = dict(court.institutions)
    formations = court.formations
    relations = dict(world.relations)
    if post in institutions:
        location = institutions[post].place
        institutions[post] = dataclasses.replace(
            institutions[post], head=person_id)
    elif post.startswith("governor:"):
        location = post.split(":", 1)[1]
    elif post.startswith("command:"):
        target = post.split(":", 1)[1]
        formations = tuple(
            dataclasses.replace(f, commander=person_id)
            if f.id == target else f for f in formations)
        location = next(f.place for f in formations if f.id == target)
    elif post.startswith("court:"):
        actor = post.split(":", 1)[1]
        location = relations[actor].place
        relations[person_id] = Relation(
            other=person_id, place=location,
            status_claim="kinsman", their_status_claim="kinsman",
            esteem=person.loyalty, obligation=0,
            last_gift_from_us=0, last_gift_from_them=0,
            best_known_rival_gift=0, known_rival_gift_source=None,
            report_bias=max(0, 1000 - person.loyalty))

    interests = tuple(dict.fromkeys(person.interests + (post,)))
    people[person_id] = dataclasses.replace(
        person, post=post, location=location, interests=interests)
    court = dataclasses.replace(
        court, house=people, institutions=institutions,
        formations=formations)
    world = dataclasses.replace(world, court=court, relations=relations)
    return world, [A.PersonPlaced(person_id, post, displaced)]


def dismiss(world: World, post: str) -> tuple[World, list]:
    post = _canonical(world, post)
    holder = _holder(world, post)
    if not holder:
        raise ValueError("that post is already vacant")
    world = _clear_post(world, post)
    return world, [A.PersonDismissed(holder, post)]


def name_heir(world: World, person_id: str) -> tuple[World, list]:
    world = _ranked(world)
    court = world.court
    person = court.house.get(person_id)
    if person is None or not person.alive or person.is_heir_rank is None:
        raise ValueError("the named heir must be a living son in the succession")
    if court.named_heir == person_id:
        raise ValueError(f"{person.name} is already the named heir")

    displaced_rank = person.is_heir_rank
    legitimacy = court.legitimacy
    mood = dict(court.faction_mood)
    if displaced_rank > 1:
        first = next(p for p in court.house.values()
                     if p.is_heir_rank == 1)
        legitimacy = max(0, legitimacy - 60)
        mood[first.faction] = mood.get(first.faction, 0) + 60
    court = dataclasses.replace(
        court, named_heir=person_id, legitimacy=legitimacy,
        faction_mood=mood)
    return dataclasses.replace(world, court=court), [
        A.HeirNamed(person_id, displaced_rank)]
