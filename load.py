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
                          Document, Estate, ForeignCourt, Formation,
                          HarbourCargoLot,
                          HouseMember, Institution, MetalState, Oath, Petition,
                          Place, PlagueState, Relation, Rite, Route, Site,
                          Terrain, Workshop, World)

CONTENT = Path(__file__).parent / "content"

# How far ahead the deterministic climate series is fixed. Thirty years is
# beyond any current run; only elapsed observations may reach divination.
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
        # A column and a row into the authored terrain, plus what the place is
        # to the map: whose empire, what rank, which letter, and the one line
        # the tablet writes about it. None of it is read by a rule.
        places[p["id"]] = Place(id=p["id"], name=p["name"],
                                col=int(p.get("col", 0)),
                                row=int(p.get("row", 0)),
                                power=str(p.get("power", "")),
                                rank=str(p.get("rank", "town")),
                                glyph=str(p.get("glyph", "")),
                                role=str(p.get("role", "")),
                                population=pop, susceptible=pop)
    routes = tuple(
        Route(a=r["a"], b=r["b"], legs=int(r["legs"]), mode=r["mode"],
              seasonal=bool(r["seasonal"]), risk=int(r["risk"]))
        for r in cfg.get("routes", [])
    )
    # The ground, and the holdings standing on it. Scenery on the same terms as
    # the coordinates above: authored in `content/`, carried through Belief,
    # read by nobody but the tablet that draws it. Degrees are authored as
    # decimals and carried in hundredths, because engine/ holds no floats.
    ground = cfg.get("terrain", {})
    terrain = Terrain(
        rows=tuple(str(row) for row in ground.get("rows", [])),
        west=round(float(ground.get("west", 0)) * 100),
        north=round(float(ground.get("north", 0)) * 100),
        step_lon=round(float(ground.get("step_lon", 0)) * 100),
        step_lat=round(float(ground.get("step_lat", 0)) * 100),
        legend=str(ground.get("legend", "")))
    sites = tuple(
        Site(kind=str(s.get("kind", "")), hub=str(s.get("hub", "")),
             col=int(s.get("col", 0)), row=int(s.get("row", 0)))
        for s in cfg.get("sites", [])
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
    # The material standing of the courts on the far side of the letters. Their
    # place is the one they already write from: a court cannot be somewhere else
    # for the purpose of deciding than it is for the purpose of posting.
    foreign_courts = {}
    for row in cfg.get("foreign_courts", []):
        actor = row["actor"]
        if actor not in actor_places:
            raise ValueError(
                f"foreign court {actor!r} is not a known correspondent")
        foreign_courts[actor] = ForeignCourt(
            actor=actor, place=actor_places[actor],
            stores={k: int(v) for k, v in row.get("stores", {}).items()},
            need={k: int(v) for k, v in row.get("need", {}).items()},
            floor={k: int(v) for k, v in row.get("floor", {}).items()},
            people=int(row.get("people", 0)),
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
                  ready=int(f["strength"]),
                  task=f.get("task", "garrison"),
                  place=f.get("place", cfg["seat"]),
                  commander=f.get("commander", ""))
        for f in cfg.get("formations", []))
    metal_cfg = cfg.get("metals", {})

    house_cfg = tomllib.loads((CONTENT / "house.toml").read_text())
    works_cfg = tomllib.loads((CONTENT / "works.toml").read_text())
    justice_cfg = tomllib.loads((CONTENT / "justice.toml").read_text())
    revenue_cfg = tomllib.loads((CONTENT / "revenue.toml").read_text())
    justice_cases = tuple(
        Petition(
            id=case["id"], petitioner=case["petitioner"],
            against=case["against"], kind=case["kind"],
            claim=(("amount", int(case["claim"])),),
            counterclaim=(("amount", int(case["counterclaim"])),),
            truth=(("amount", int(case["truth"])),),
            unit=case["unit"], claim_text=case["claim_text"].strip(),
            counter_text=case["counter_text"].strip(),
            correction=case["correction"].strip(),
            witness=case["witness"], faction=case["faction"],
            against_faction=case["against_faction"],
            arrived_turn=int(case["arrived_turn"]),
        )
        for case in justice_cfg.get("cases", []))

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
            competence=int(person.get("competence", 500)),
            loyalty=int(person.get("loyalty", 700)),
            post=person.get("post", ""),
            interests=tuple(person.get("interests", [])),
        )
    diviner = cfg.get("diviner", {})

    scribe = cfg.get("scribe", {})
    court = Court(
        actor=cfg["actor"], seat=cfg["seat"],
        attention_base=int(cfg["attention_base"]),
        stores=stores,
        dependents=groups,
        allocations={},                       # default: pay full entitlement
        priority=tuple(cfg["priority"]),
        rites=rites,
        scribe_competence=int(scribe.get("competence", 850)),
        scribe_fatigue=int(scribe.get("fatigue", 300)),
        estates=estates, workshops=workshops, formations=formations,
        last_harvest=int(cfg.get("last_harvest", 0)),
        previous_harvest=int(cfg.get("last_harvest", 0)),
        institutions={
            inst["id"]: Institution(
                id=inst["id"], name=inst["name"], kind=inst["kind"],
                place=inst["place"], group=inst.get("group", ""),
                head=inst.get("head", ""),
                condition=int(inst.get("condition", 1000)),
                capacity=int(inst.get("capacity", 0)),
                upkeep=tuple(sorted(
                    (good, int(qty))
                    for good, qty in (inst.get("upkeep") or {}).items())))
            for inst in cfg.get("institutions", [])},
        metals=MetalState(
            bronze_in_circulation=int(
                metal_cfg.get("bronze_in_circulation", 0)),
            melt_ledger=int(metal_cfg.get("melt_ledger", 0)),
            # The court starts fully equipped, so what it holds on day one is
            # what it has hands and uses for. A working forge maintains that
            # stock and never exceeds it (6.5).
            in_service_ceiling=int(metal_cfg.get(
                "in_service_ceiling",
                metal_cfg.get("bronze_in_circulation", 0)))),
        house=house, ruler=cfg["actor"],
        diviner_competence=int(diviner.get("competence", 600)),
        diviner_loyalty=int(diviner.get("loyalty", 700)),
        diviner_faction=diviner.get("faction", "temple"),
        land_due_rate=int(revenue_cfg["land"]["initial_rate"]),
        land_due_base=int(revenue_cfg["land"]["base_rate"]),
        harbour_due_rate=int(revenue_cfg["harbour"]["initial_rate"]),
        harbour_due_customary=int(revenue_cfg["harbour"]["customary_rate"]),
        last_land_due=(int(cfg.get("last_harvest", 0))
                       * int(revenue_cfg["land"]["initial_rate"]) // 1000),
    )
    plague_cfg = cfg.get("plague", {})
    plague_state = PlagueState(
        beta=int(plague_cfg.get("beta", 0)),
        gamma=int(plague_cfg.get("gamma", 0)),
        mortality=int(plague_cfg.get("mortality", 0)),
        exposure=int(plague_cfg.get("exposure", 0)),
        import_place=str(plague_cfg.get("import_place", "")),
        import_turn=int(plague_cfg.get("import_turn", -1)),
        import_cases=int(plague_cfg.get("import_cases", 0)),
    )
    harbour_cargo = {
        lot["id"]: HarbourCargoLot(
            id=lot["id"], owner=lot["owner"], place=lot["place"],
            good=lot["good"], quantity=int(lot["quantity"]))
        for lot in cfg.get("harbour_cargo", [])
    }

    return World(
        seed=seed, scenario=cfg["scenario"],
        date=Date(year=1, fortnight=0, absolute=0),   # turn 1 begins with an advance
        court=court,
        places=places, routes=routes, terrain=terrain, sites=sites,
        correspondents=correspondents, season=season,
        relations=relations, oaths=oaths, foreign_courts=foreign_courts,
        plague=plague_state,
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
        works_rules={k: int(v) for k, v in works_cfg["rules"].items()
                     if k not in ("per_1000_days", "season")},
        works_season=works_cfg["rules"].get("season", ""),
        works_materials={k: int(v) for k, v
                         in works_cfg["rules"]["per_1000_days"].items()},
        works_plans={kind: {**plan, "days": int(plan["days"]),
                            "condition": int(plan["condition"]),
                            "capacity": int(plan["capacity"])}
                     for kind, plan in works_cfg.get("build", {}).items()},
        justice_cases=justice_cases,
        justice_rules={
            key: int(value)
            for key, value in justice_cfg.get("rules", {}).items()},
        revenue_rules={
            **{key: int(value)
               for key, value in revenue_cfg.get("land", {}).items()
               if key not in ("initial_rate", "base_rate")},
            **{key: int(value)
               for key, value in revenue_cfg.get("harbour", {}).items()
               if key not in ("initial_rate", "customary_rate",
                              "cargo_good", "merchants")},
        },
        revenue_good=revenue_cfg["harbour"]["cargo_good"],
        revenue_merchants=tuple(revenue_cfg["harbour"]["merchants"]),
        harbour_cargo=harbour_cargo,
        house_names_f=tuple(cfg.get("house_names_f", [])),
        house_names_m=tuple(cfg.get("house_names_m", [])),
    )
