"""What an actor could have noticed (spec 5.8, 6.1 phase 3, 10.11).

Observation is bounded by presence. A settlement's controller counts its own
granary because it is standing next to it; it does not count anyone else's.
Anything an actor knows about elsewhere arrived as a report, from someone who
was there, at some remove in time -- and that is a `Claim` with a chain, not an
observation.

This module is the only place claims about the present are minted from World.
Keeping it small is the point: if an actor believes something, either it saw it
here, or it was told, and both paths are visible in one file.
"""
from __future__ import annotations

from engine.believe import Belief, Claim, Observation
from engine.entity import EntityId

# What a controller counts at home each fortnight. Attributes, not values: the
# values come from the world, and the list is what "looking around" means.
#
# The farming readings are here because they pass the same test as the granary:
# could this actor learn it by walking round its own place in a fortnight? The
# extent of the fields and how much of them is under crop, yes -- you can see a
# sown field from its edge. Its own seed, its own standing crop, and its own
# stacked sheaves, yes -- they are its property and it counts them. What the
# temple across the square is holding, no: that arrives as a report or not at
# all, and there is no attribute here that would let a policy help itself to it.
# The market readings pass it too, and it is worth saying why, because "the
# price of grain" sounds like the sort of thing only a market institution would
# know. There is no such institution and no posted price: what an actor sees is
# how full its own stores are against how many mouths it feeds, and what that
# has done to what people will give. Anyone standing in a small port for a
# fortnight knows all of it. What nobody standing there knows is the same
# figures for a port across the water -- those arrive by ship, as `report`
# below, or not at all.
LOCAL = ("stores_grain", "people", "labour",
         "extent", "under_crop",          # the ground, and how much of it is sown
         "own_grain", "own_seed", "own_standing", "own_sheaves",
         "own_copper",                    # the purse, counted like any other store
         "price_grain", "market_grain",   # what it costs, and what is on the quay
         "season",                        # which moment of the farming year
         "home")                          # and that this is where the actor is


def observe_local(observer: EntityId, place: EntityId, turn: int,
                  readings: dict[str, int]) -> tuple[Observation, ...]:
    """Everything the observer can count where it is standing.

    The place is part of the id because an actor is not always in one place. A
    merchant counts its own grain on a foreign quay the same way it counts the
    grain at home, and both are `own_grain` on the same turn: without the place
    the two observations would be one, and the second would silently be taken
    for the first.
    """
    return tuple(
        Observation(
            id=f"{observer}|{turn}|{place}|{attribute}", observer=observer,
            subject=place, attribute=attribute, value=readings[attribute],
            turn=turn, method="counted", place=place)
        for attribute in LOCAL if attribute in readings)


def as_claims(observations: tuple[Observation, ...],
              turn: int) -> tuple[Claim, ...]:
    """An observation the observer made itself, held as a claim it is sure of."""
    return tuple(
        Claim(id=f"c|{o.id}", holder=o.observer, subject=o.subject,
              attribute=o.attribute, value=o.value, source="observed",
              observed_turn=o.turn, received_turn=turn, confidence=1000)
        for o in observations)


def report(claim: Claim, to: EntityId, turn: int,
           carrier: EntityId, loss: int = 100) -> Claim:
    """Pass a claim on. It arrives later, through someone, and trusted less.

    The value does not change here. Distortion is a separate concern with its
    own boundary (`belief/distortion.py`); what this models is the plain fact
    that second-hand knowledge is older and weaker than first-hand, and that
    the chain is recorded so the recipient can weigh it.
    """
    return Claim(
        id=f"{claim.id}>{to}@{turn}", holder=to, subject=claim.subject,
        attribute=claim.attribute, value=claim.value, source="reported",
        observed_turn=claim.observed_turn, received_turn=turn,
        chain=claim.chain + (carrier,), basis=(claim.id,),
        confidence=max(0, claim.confidence - loss))


def project(belief: Belief, observations: tuple[Observation, ...],
            turn: int) -> Belief:
    """Fold this turn's observations into an actor's belief (phase 3)."""
    return belief.add(*as_claims(observations, turn))
