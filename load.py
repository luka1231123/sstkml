"""Content -> initial World (spec 1.2: outside engine/, may read files).

engine/ never touches the filesystem. This module reads authored TOML and
builds the frozen World tree, deriving anything non-authored (member names)
from a seeded stream so it is identical every run.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from engine.core import Date, stream
from engine.state import (Clause, Correspondent, Court, DependentGroup,
                          MisfortuneCard, Oath, Place, Relation, Rite, Route,
                          World)

CONTENT = Path(__file__).parent / "content"


def _requires(d: dict) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((k, int(v)) for k, v in d.items()))


def load_scenario(name: str, seed: int) -> World:
    cfg = tomllib.loads((CONTENT / "scenarios" / f"{name}.toml").read_text())
    relation_cfg = tomllib.loads((CONTENT / "relations.toml").read_text())
    deck_cfg = tomllib.loads(
        (CONTENT / "decks" / "misfortune.toml").read_text())
    names = cfg["names"]

    groups: dict[str, DependentGroup] = {}
    for g in cfg["groups"]:
        gid = g["id"]
        member = stream(seed, 0, "names", gid).pick(names)
        groups[gid] = DependentGroup(
            id=gid, name=g["name"], size=int(g["size"]),
            entitlement=int(g["entitlement"]), function=g["function"],
            place=g["place"], member_name=member,
        )

    rites = tuple(
        Rite(
            id=r["id"], fortnight=int(r["fortnight"]), hours=int(r["hours"]),
            requires=_requires(r["requires"]),
            skip_legitimacy=int(r["skip_legitimacy"]),
            skip_unrest=int(r["skip_unrest"]),
            skip_deck_weight=int(r["skip_deck_weight"]),
        )
        for r in cfg.get("rites", [])
    )

    stores = {k: int(v) for k, v in cfg["stores"].items()}

    places = {p["id"]: Place(id=p["id"], name=p["name"]) for p in cfg.get("places", [])}
    routes = tuple(
        Route(a=r["a"], b=r["b"], legs=int(r["legs"]), mode=r["mode"],
              seasonal=bool(r["seasonal"]), risk=int(r["risk"]))
        for r in cfg.get("routes", [])
    )
    correspondents = tuple(
        Correspondent(
            actor=c["actor"], place=c["place"], cadence=int(c["cadence"]),
            offset=int(c["offset"]), topic=c["topic"],
            facts=tuple(sorted(((k, v) for k, v in c.get("facts", {}).items()),
                               key=lambda kv: kv[0])),
        )
        for c in cfg.get("correspondents", [])
    )
    actor_places = {c.actor: c.place for c in correspondents}
    relations = {}
    for r in cfg.get("relations", []):
        other = r["other"]
        relations[other] = Relation(
            other=other, place=actor_places[other],
            status_claim=r["status_claim"],
            their_status_claim=r["their_status_claim"],
            esteem=int(r.get("esteem", 500)),
            obligation=int(r.get("obligation", 0)),
            last_gift_from_us=int(r.get("last_gift_from_us", 0)),
            last_gift_from_them=int(r.get("last_gift_from_them", 0)),
            best_known_rival_gift=int(r.get("best_known_rival_gift", 0)),
            known_rival_gift_source=r.get("known_rival_gift_source"),
            is_vassal=bool(r.get("is_vassal", False)),
        )
    oaths = tuple(
        Oath(
            id=o["id"], parties=tuple(o["parties"]),
            superior=o.get("superior"), gods=tuple(o.get("gods", [])),
            sworn_turn=int(o["sworn_turn"]), sworn_by=o["sworn_by"],
            clauses=tuple(
                Clause(c["kind"], tuple(sorted(
                    (k, v) for k, v in c.items() if k != "kind")))
                for c in o.get("clauses", [])
            ),
            dissolved=bool(o.get("dissolved", False)),
        )
        for o in cfg.get("oaths", [])
    )
    deck = tuple(
        MisfortuneCard(
            id=c["id"], weight=int(c["weight"]),
            liability_weight=int(c["liability_weight"]),
            good=c["good"], loss=int(c["loss"]),
            legitimacy_delta=int(c["legitimacy_delta"]),
            unrest_delta=int(c["unrest_delta"]),
        )
        for c in deck_cfg.get("cards", [])
    )
    season = {k: tuple(v) for k, v in cfg.get("season", {}).items()}

    scribe = cfg.get("scribe", {})
    court = Court(
        actor=cfg["actor"], seat=cfg["seat"],
        attention_base=int(cfg["attention_base"]),
        stores=stores, grain_income=int(cfg["grain_income"]),
        dependents=groups,
        allocations={},                       # default: pay full entitlement
        priority=tuple(cfg["priority"]),
        rites=rites,
        scribe_competence=int(scribe.get("competence", 850)),
        scribe_fatigue=int(scribe.get("fatigue", 300)),
        liability={o.id: 0 for o in oaths},
    )
    return World(
        seed=seed, scenario=cfg["scenario"],
        date=Date(year=1, fortnight=0, absolute=0),   # turn 1 begins with an advance
        court=court,
        places=places, routes=routes, correspondents=correspondents, season=season,
        relations=relations, oaths=oaths,
        gift_values={k: int(v) for k, v in relation_cfg["gifts"]["value_per_unit"].items()},
        gift_status_floors={
            k: int(v) for k, v in relation_cfg["gifts"]["status_floor"].items()},
        reciprocity_table=tuple(
            (int(point[0]), int(point[1]))
            for point in relation_cfg["gifts"]["reciprocity"]),
        god_ranks={k: int(v) for k, v in relation_cfg["gods"]["rank"].items()},
        protocol_rules={
            k: int(v) for k, v in relation_cfg["protocol"].items()},
        misfortune_deck=deck,
    )
