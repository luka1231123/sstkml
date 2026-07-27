"""Content -> initial World (spec 1.2: outside engine/, may read files).

engine/ never touches the filesystem. This module reads authored TOML and
builds the frozen World tree, deriving anything non-authored (member names)
from a seeded stream so it is identical every run.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from engine.core import Date, in_range, stream
from engine.land import climate_series
from engine.state import (Clause, Correspondent, Court, DependentGroup,
                          Document, Estate, Formation, HouseMember, MetalState,
                          MisfortuneCard, Oath, Place, PlagueState, Relation,
                          Rite, Route, Workshop, World)

CONTENT = Path(__file__).parent / "content"

# How far ahead the climate is fixed (spec 6.4). Thirty years is far past any
# run, and the whole series must exist before turn 1 so divination can read it.
CLIMATE_YEARS = 30


def load_predecessor_archive(scenario: str) -> tuple[Document, ...]:
    """The documents that exist before turn 1 (spec 6.12, 6.17).

    Their `received_turn` is negative, so they sort to the top of every result
    set. A scenario with no predecessor archive -- Pylos, which discards its
    tablets every year and is the whole reason 7.4 is interesting -- simply has
    no file, and gets an empty one rather than an error.
    """
    path = CONTENT / "corpus" / "predecessor_archive" / f"{scenario}.toml"
    if not path.exists():
        return ()
    cfg = tomllib.loads(path.read_text())
    docs = tuple(
        Document(
            ref=d["ref"], kind=d["kind"], received_turn=int(d["received_turn"]),
            sender=d.get("sender"), dated_as=d.get("dated_as", ""),
            body=d["body"].strip(), title=d.get("title", ""),
            tags=tuple(d.get("tags", [])),
        )
        for d in cfg.get("documents", [])
    )
    return tuple(sorted(docs, key=lambda d: (d.received_turn, d.ref)))


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

    # Everyone starts susceptible (spec 6.12). There is no acquired immunity in
    # the opening state, because the last epidemic was two generations ago and
    # the people who survived it are the ones in the predecessor archive.
    places = {}
    for p in cfg.get("places", []):
        pop = int(p.get("population", 0))
        places[p["id"]] = Place(id=p["id"], name=p["name"],
                                population=pop, susceptible=pop)
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
            exaggerate=tuple(sorted(c.get("exaggerate", []))),
            understate=tuple(sorted(c.get("understate", []))),
            summons_oath=c.get("summons_oath", ""),
        )
        for c in cfg.get("correspondents", [])
    )
    actor_places = {c.actor: c.place for c in correspondents}
    # Estate overseers are not on a cadence -- their letters are generated from
    # the state of the fields (spec 6.4) -- but they are relations like any
    # other, and they live where their land is.
    actor_places.update({f"overseer_{e['id']}": e["place"]
                         for e in cfg.get("estates", [])})
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
            report_bias=int(r.get("report_bias", 0)),
        )
    oaths = tuple(
        Oath(
            id=o["id"], parties=tuple(o["parties"]),
            superior=o.get("superior") or None, gods=tuple(o.get("gods", [])),
            sworn_turn=int(o["sworn_turn"]), sworn_by=o["sworn_by"],
            clauses=tuple(
                Clause(c["kind"], tuple(sorted(
                    (k, v) for k, v in c.items() if k != "kind")))
                for c in o.get("clauses", [])
            ),
            dissolved=bool(o.get("dissolved", False)),
            # A vow to a god outlives the man who swore it (M10, spec 6.12).
            binds_house=bool(o.get("binds_house", False)),
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

    land_cfg = tomllib.loads((CONTENT / "land.toml").read_text())

    # Estates open the game with a crop already in the ground: the first harvest
    # is the predecessor's, sown before the player had any say in it. Only the
    # second year answers to his decisions, which is the lag the system is for.
    # The scenario opens partway through a growing season the predecessor began.
    # `opening_growing_turns` banks the labour and weather of the fortnights that
    # elapsed before turn 1, so year one is a normal year rather than a short one
    # -- otherwise the player's first harvest under-reports by the length of the
    # gap, and `last_harvest` (his one hard datum) misleads him all year two.
    banked = int(cfg.get("opening_growing_turns", 0))
    growing_span = tuple(cfg.get("season", {}).get("growing", ()))
    growing = sum(1 for f in range(1, 25)
                  if growing_span and in_range(f, growing_span)) or 1
    estates = {}
    for e in cfg.get("estates", []):
        area = int(e["area_iku"])
        need = area * int(e["labour_days_per_iku"])
        estates[e["id"]] = Estate(
            id=e["id"], name=e["name"], place=e["place"], area_iku=area,
            base_yield_per_iku=int(e["base_yield_per_iku"]),
            seed_per_iku=int(e["seed_per_iku"]),
            labour_days_per_iku=int(e["labour_days_per_iku"]),
            irrigated=bool(e.get("irrigated", False)),
            canal_condition=int(e.get("canal_condition", 1000)),
            seed_sown=area * int(e["seed_per_iku"])
            * int(e.get("opening_sown_permille", 1000)) // 1000,
            labour_days_supplied=need * banked // growing,
            climate_sum=100 * banked, climate_turns=banked,
        )

    workshops = tuple(
        Workshop(id=w["id"], name=w["name"], group_id=w["group_id"],
                 bronze_demand=int(w["bronze_demand"]))
        for w in cfg.get("workshops", []))
    formations = tuple(
        Formation(id=f["id"], name=f["name"], strength=int(f["strength"]),
                  equipment_floor=int(f.get(
                      "equipment_floor",
                      land_cfg["metal"]["default_equipment_floor"])),
                  replacement_rate=1000,
                  task=f.get("task", "garrison"),
                  place=f.get("place", cfg["seat"]))
        for f in cfg.get("formations", []))
    metal_cfg = cfg.get("metals", {})

    house_cfg = tomllib.loads((CONTENT / "house.toml").read_text())

    # The cast (spec 6.10). Ages are authored in YEARS and stored in fortnights,
    # because the engine has one time unit and the content should read like a
    # family rather than a table of counters.
    house = {}
    for person in cfg.get("house", []):
        house[person["id"]] = HouseMember(
            id=person["id"], name=person["name"], sex=person["sex"],
            age_turns=int(person["age_years"]) * 24,
            health=int(person.get("health", 700)),
            location=person.get("location", cfg["seat"]),
            spouse=person.get("spouse"),
            mother=person.get("mother"), father=person.get("father"),
            faction=person.get("faction", "house"),
            own_agenda=person.get("own_agenda", ""),
            married_to_court=person.get("married_to_court"),
            is_queen_mother=bool(person.get("is_queen_mother", False)),
        )
    diviner = cfg.get("diviner", {})

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
        estates=estates, workshops=workshops, formations=formations,
        last_harvest=int(cfg.get("last_harvest", 0)),
        previous_harvest=int(cfg.get("last_harvest", 0)),
        metals=MetalState(
            bronze_in_circulation=int(
                metal_cfg.get("bronze_in_circulation", 0)),
            melt_ledger=int(metal_cfg.get("melt_ledger", 0))),
        house=house, ruler=cfg["actor"],
        diviner_competence=int(diviner.get("competence", 600)),
        diviner_loyalty=int(diviner.get("loyalty", 700)),
        diviner_faction=diviner.get("faction", "temple"),
    )
    return World(
        seed=seed, scenario=cfg["scenario"],
        date=Date(year=1, fortnight=0, absolute=0),   # turn 1 begins with an advance
        court=court,
        places=places, routes=routes, correspondents=correspondents, season=season,
        relations=relations, oaths=oaths,
        plague=PlagueState(**{k: int(v) for k, v in cfg.get("plague", {}).items()}),
        documents=load_predecessor_archive(cfg["scenario"]),
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
        climate=climate_series(
            seed, CLIMATE_YEARS * 24,
            tuple((int(point[0]), int(point[1]))
                  for point in cfg.get("climate", {}).get("drought_curve", []))),
        land_tables={
            name: tuple((int(x), int(y)) for x, y in points)
            for name, points in land_cfg["tables"].items()},
        land_rules={
            **{k: int(v) for k, v in land_cfg["agriculture"].items()},
            **{k: int(v) for k, v in land_cfg["metal"].items()}},
        house_tables={
            name: tuple((int(x), int(y)) for x, y in points)
            for name, points in house_cfg["tables"].items()},
        house_rules={k: int(v) for k, v in house_cfg["rules"].items()},
        house_names_f=tuple(cfg.get("house_names_f", [])),
        house_names_m=tuple(cfg.get("house_names_m", [])),
    )
