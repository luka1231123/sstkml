"""Content -> initial World (spec 1.2: outside engine/, may read files).

engine/ never touches the filesystem. This module reads authored TOML and
builds the frozen World tree, deriving anything non-authored (member names)
from a seeded stream so it is identical every run.
"""
from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

from engine import obligation as O
from engine import ownership as W
from engine.core import Date, lerp_table, stream
from engine.entity import Cohort as KernelCohort
from engine.entity import Leg as KernelLeg
from engine.entity import Organization as KernelOrganization
from engine.entity import Person as KernelPerson
from engine.entity import Polity as KernelPolity
from engine.entity import Region as KernelRegion
from engine.entity import Registry
from engine.entity import Route
from engine.entity import Settlement as KernelSettlement
from engine.entity import Site as KernelSite
from engine.entity import TENURES
from engine.entity import check as check_registry
from engine.entity import mint as mint_id
from engine.entity import parse as parse_id
from engine.kernel import farm
from engine.kernel import seat_goods
from engine.kernel.world import Kernel

# Where the court's goods sit in the kernel, and whose they are. The palace of
# the seat is the court: `Court.stores` is that org's granary and nobody
# else's, which is the fact a flat mapping could not state.
SEAT_SETTLEMENT = "settlement:seat"
SEAT_OWNER = "org:seat_palace"
from engine.climate import series as climate_series
from engine.state import (Clause, Correspondent, Court, DependentGroup,
                          Document, Formation,
                          HarbourCargoLot,
                          HouseMember, Institution, MetalState, Oath, Petition,
                          Place, PlagueState, Relation, Rite, Site,
                          Terrain, Workshop, World)

# The Alu where each imperial power sits. `power` authors overlordship, not
# ownership: every Alu has its own polity and king.
OVERLORD_SEATS = {
    "egypt": "egypt",
    "hatti": "hattusa",
    "ahhiyawa": "mycenae",
    "assyria": "assur",
    "karduniash": "babylon",
}

# Every site.function a scenario may author: the palace itself, or one of the
# capacities a holding can be classified as (spec 8.3). Closed so a typo in a
# scenario's capacity string fails to load rather than minting a site that
# nothing in the allocator recognizes.
SITE_FUNCTIONS = frozenset({
    "palace_centre", "food", "copper", "tin", "gold", "silver",
    "cedar", "horses", "lapis", "estate", "mine", "forest", "quarry",
    "pasture", "harbour", "oil", "wine",
})


def kernel_settlement(world_or_places, place_id: str) -> str:
    """The kernel settlement a court place answers to (Task 2 C1).

    One definition, because the loader enforces it and the audit checks it, and
    two readings of "which settlement is this place" is the kind of pair this
    whole task exists to stop. Every mark answers to one Alu (spec 8.3) and
    every Alu is a settlement, so the content already carries the answer: Mari
    is a mark of Dur Katlimmu, Argos of Mycenae, and the port quarter of the
    seat is the seat.

    Takes a World or a bare mapping of places, so the loader can call it before
    a World exists.
    """
    places = getattr(world_or_places, "places", world_or_places)
    place = places.get(place_id)
    if place is None:
        return ""
    alu = place_id if place.kind == "alu" else place.alu
    return f"settlement:{alu}"


def parse_places(cfg: dict) -> dict:
    """The scenario's map marks, checked (spec 8.3).

    Everyone starts susceptible (spec 6.12): there is no acquired immunity in
    the opening state, because the last epidemic was two generations ago and
    the people who survived it are the ones in the predecessor archive.
    """
    places = {}
    for p in cfg.get("places", []):
        pop = int(p.get("population", 0))
        # A column and a row into the authored terrain, plus what the place is
        # to the map: whose empire, what rank, which letter, and the one line
        # the tablet writes about it. None of it is read by a rule.
        kind = str(p.get("kind", "alu"))
        if kind not in ("alu", "palace_centre"):
            raise ValueError(f"{p['id']}: unknown place kind {kind!r}")
        places[p["id"]] = Place(id=p["id"], name=p["name"],
                                col=int(p.get("col", 0)),
                                row=int(p.get("row", 0)),
                                power=str(p.get("power", "")),
                                rank=str(p.get("rank", "town")),
                                glyph=str(p.get("glyph", "")),
                                role=str(p.get("role", "")),
                                kind=kind,
                                alu=str(p.get("alu", "")),
                                harbour=bool(p.get("harbour", False)),
                                population=pop, susceptible=pop)
    # Every mark answers to one Alu, and the answer is authored (spec 8.3).
    # Resolved here rather than at the tablet because a mark with no owner, or
    # an owner that is itself a holding, is a scenario fault and not a drawing
    # one: it is how a decorative site becomes a settlement nobody meant.
    alu_ids = {i for i, place in places.items() if place.kind == "alu"}
    for place in places.values():
        if place.kind != "palace_centre":
            if place.alu:
                raise ValueError(f"{place.id}: an Alu cannot belong to {place.alu}")
            continue
        if place.alu not in alu_ids:
            raise ValueError(f"{place.id}: palace centre of unknown Alu "
                             f"{place.alu!r}")
    return places


# Hold a crossing carries in a fortnight, in qa-of-grain equivalents, by how
# the goods travel. Nothing authored a route capacity, so every route took the
# `0 = unmodelled` default and the whole cargo system -- voyages, pools,
# loading, arrival -- ran but moved nothing, for every route in the world. A
# ship carries what a donkey train cannot, so the number belongs to the mode.
ROUTE_CAPACITY = {"sea": 6000, "river": 3000, "land": 800}


def _course(flat) -> tuple[tuple[int, int], ...]:
    """A route's `path = [col, row, col, row, ...]`, in pairs.

    Authored flat because a hundred nested pairs make the file unreadable, and
    an odd count is an authoring slip worth refusing rather than truncating.
    """
    numbers = [int(n) for n in flat]
    if len(numbers) % 2:
        raise ValueError(f"route path has {len(numbers)} numbers, "
                         "which is not a whole number of turns")
    return tuple(zip(numbers[::2], numbers[1::2]))


def parse_sites(cfg: dict, places: dict) -> tuple:
    """The holdings standing on the ground, each answering to one Alu."""
    alu_ids = {i for i, place in places.items() if place.kind == "alu"}
    sites = []
    for s in cfg.get("sites", []):
        role = str(s.get("role", ""))
        alu = str(s.get("alu", ""))
        if role not in ("palace_centre", "capacity"):
            raise ValueError(f"site at {s.get('col')},{s.get('row')}: "
                             f"unknown role {role!r}")
        if alu not in alu_ids:
            raise ValueError(f"site at {s.get('col')},{s.get('row')}: "
                             f"unknown Alu {alu!r}")
        capacity = str(s.get("capacity", ""))
        if role == "capacity" and not capacity:
            raise ValueError(f"site at {s.get('col')},{s.get('row')}: "
                             "a capacity must say what of")
        name = str(s.get("name", ""))
        if role == "palace_centre" and not name:
            raise ValueError(f"site at {s.get('col')},{s.get('row')}: "
                             "a palace centre must be named")
        if role == "capacity" and name:
            raise ValueError(f"site at {s.get('col')},{s.get('row')}: "
                             "a capacity is ground, not a place; it takes no name")
        sites.append(Site(kind=str(s.get("kind", "")), alu=alu, role=role,
                          capacity=capacity, name=name,
                          col=int(s.get("col", 0)),
                          row=int(s.get("row", 0))))
    return tuple(sites)


def mint_from_scenario(cfg: dict) -> Registry:
    """The registry a scenario file implies, without the detail file.

    `tools/gen_detail.py` writes that detail file, so it cannot go through
    `load_campaign`, which reads it.
    """
    places = parse_places(cfg)
    return mint_registry(places, parse_sites(cfg, places), cfg)


def mint_registry(places: dict, sites: tuple, cfg: dict) -> Registry:
    """The kernel Registry implied by a scenario's places and sites.

    Pure derivation from already-parsed content: no file access, no World
    field. Exercised and validated here so a scenario that cannot mint a sound
    registry fails to load, well before anything wires it into play.
    """
    regions = {
        f"region:{r['id']}": KernelRegion(id=f"region:{r['id']}", name=r["name"])
        for r in cfg.get("regions", [])
    }

    alus = {p.id: p for p in places.values() if p.kind == "alu"}
    place_region = {p["id"]: p.get("region", "") for p in cfg.get("places", [])}

    # How each polity's people come by their food (`entity.TENURES`). Authored
    # rather than derived: nothing about a place on a map says whether the crop
    # goes to a state granary or stays in the village, and guessing it from
    # anything else would be inventing a society.
    tenure_cfg = cfg.get("tenure", {})
    tenure_default = tenure_cfg.get("default", "pooled")
    tenure_by_polity = dict(tenure_cfg.get("polities", {}))
    for name in sorted({tenure_default, *tenure_by_polity.values()}):
        if name not in TENURES:
            raise ValueError(f"unknown tenure {name!r}; expected one of "
                             + ", ".join(TENURES))

    def tenure_for(pid: str) -> str:
        return tenure_by_polity.get(pid, tenure_default)

    polities: dict[str, KernelPolity] = {}
    persons: dict[str, KernelPerson] = {}
    ruler_cfg = dict(cfg.get("rulers", {}))
    for place in alus.values():
        settlement_id = f"settlement:{place.id}"
        pid = f"polity:{place.id}"
        authored_ruler = ruler_cfg.get(place.id, {})
        ruler_slug = str(authored_ruler.get("id", f"{place.id}_king"))
        ruler_id = f"person:{ruler_slug}"
        persons[ruler_id] = KernelPerson(
            id=ruler_id,
            name=str(authored_ruler.get("name", f"the king of {place.name}")))
        overlord_alu = OVERLORD_SEATS.get(place.power, "")
        overlord = (f"polity:{overlord_alu}"
                    if overlord_alu and overlord_alu != place.id else "")
        polities[pid] = KernelPolity(
            id=pid, name=place.name, ruler=ruler_id, seat=settlement_id,
            overlord=overlord, tenure=tenure_for(pid))

    reg_sites: dict[str, KernelSite] = {}
    settlement_sites: dict[str, list[str]] = {alu: [] for alu in alus}
    for s in sites:
        site_id = f"site:{s.alu}_{s.col}_{s.row}"
        settlement_id = f"settlement:{s.alu}"
        function = "palace_centre" if s.role == "palace_centre" else s.capacity
        reg_sites[site_id] = KernelSite(
            id=site_id, name=s.name if s.role == "palace_centre" else "",
            settlement=settlement_id, function=function,
            col=s.col, row=s.row, kind=s.kind)
        if s.role == "palace_centre":
            settlement_sites[s.alu].append(site_id)
        if function not in SITE_FUNCTIONS:
            raise ValueError(f"{site_id}: unknown site function {function!r}")

    # A palace centre authored as a `[[places]]` row rather than a `[[sites]]`
    # one is the same thing on the map and becomes a site too (C5). It keeps the
    # id the court knew it by, so a letter addressed to Gib'ala still lands.
    # Some are authored in both tables -- Gib'ala and Ma'hadu are a `[[places]]`
    # row and a `[[sites]]` row at the same cell. One mark, so the existing site
    # is renamed and made addressable rather than drawn again beside itself.
    at_cell = {(s.settlement, s.col, s.row): i for i, s in reg_sites.items()}
    for place in places.values():
        if place.kind != "palace_centre":
            continue
        settlement_id = f"settlement:{place.alu}"
        site_id = at_cell.get((settlement_id, place.col, place.row),
                              f"site:{place.id}")
        reg_sites[site_id] = KernelSite(
            id=site_id, name=place.name, settlement=settlement_id,
            function="palace_centre", col=place.col, row=place.row,
            kind="palace", glyph=place.glyph, role=place.role,
            harbour=place.harbour, population=place.population,
            addressable=True)
        if site_id not in settlement_sites[place.alu]:
            settlement_sites[place.alu].append(site_id)

    settlements = {}
    cohorts = {}
    for place in alus.values():
        settlement_id = f"settlement:{place.id}"
        settlements[settlement_id] = KernelSettlement(
            id=settlement_id, name=place.name,
            region=f"region:{place_region[place.id]}",
            owner=f"polity:{place.id}",
            sites=tuple(sorted(settlement_sites[place.id])),
            autonomous=place.id != cfg.get("seat", ""),
            col=place.col, row=place.row, power=place.power, rank=place.rank,
            glyph=place.glyph, role=place.role, harbour=place.harbour,
            population=place.population,
        )
        cohort_id = f"cohort:{place.id}_people"
        cohorts[cohort_id] = KernelCohort(
            id=cohort_id, settlement=settlement_id, kind="field_labour",
            households=max(1, place.population // 5), people=place.population,
            ethnicity=f"region:{place_region[place.id]}", status="household",
            institution=f"polity:{place.id}",
        )

    def route_settlement(place_id: str) -> str:
        # A route endpoint may name a holding (a harbour, say) rather than the
        # Alu itself; every mark answers to one Alu (spec 8.3), and that Alu is
        # the settlement a courier actually arrives at.
        place = places.get(place_id)
        alu_id = place_id if place is None or place.kind == "alu" else place.alu
        return f"settlement:{alu_id}"

    routes = {}
    for r in cfg.get("routes", []):
        route_id = f"route:{r['a']}_{r['b']}"
        routes[route_id] = Route(
            id=route_id, name=f"{r['a']}-{r['b']}",
            legs=(KernelLeg(
                origin=route_settlement(r["a"]), destination=route_settlement(r["b"]),
                mode=r["mode"], fortnights=int(r["legs"]),
                # A seasonal leg is shut outside the sailing window; the season
                # itself is the scenario's, so a run that renames it here would
                # silently open the sea all year. Only the sea shuts: the Nile
                # carries traffic all year, so a river leg keeps no span.
                season=("sailing_open"
                        if r.get("seasonal") and r["mode"] == "sea" else "")),),
            risk=int(r["risk"]),
            capacity=ROUTE_CAPACITY.get(r["mode"], 0),
            course=_course(r.get("path", ())),
            ends=(r["a"], r["b"]),
        )

    registry = Registry(regions=regions, polities=polities, persons=persons,
                        settlements=settlements, sites=reg_sites,
                        routes=routes, cohorts=cohorts)

    # No check that every mark answers to a settlement: `parse_places` already
    # refuses a palace centre of an unknown Alu, and every Alu becomes a
    # settlement here, so the property holds by construction. A second check
    # would be unreachable, and unreachable code that looks like enforcement is
    # worse than none -- it is the line somebody trusts when they change the
    # rule that actually holds.
    faults = check_registry(registry)
    if faults:
        raise ValueError("; ".join(faults))
    return registry

def load_detail(registry: Registry) -> tuple[Registry, W.Book, tuple, dict, dict, list]:
    """Fold `content/kernel/detail.toml` onto a minted registry.

    The scenario map says what exists and where; it cannot say how much ground
    a mark is, how a settlement's people divide, what is in the granary on day
    one, or what is owed to whom. That is this file, written by
    `tools/gen_detail.py`, and every row of it must name an entity the scenario
    already made -- a row that names anything else is a load error rather than
    a quietly ignored line.

    Returns (registry, book, obligations, seasons, region_climate, drought_curve).
    Seasons, climate, and drought curve are authored here as shared-world
    parameters, not campaign-specific.
    """
    cfg = tomllib.loads((CONTENT / "kernel" / "detail.toml").read_text())

    def known(where: str, field: str, value: str, table) -> None:
        if value not in table:
            raise ValueError(f"detail.toml: {where}: {field} names {value!r}, "
                             "which the scenario did not make")

    sites = dict(registry.sites)
    for row in cfg.get("sites", []):
        known("sites", "id", row["id"], sites)
        known(row["id"], "region", row["region"], registry.regions)
        if row["settlement"] != sites[row["id"]].settlement:
            raise ValueError(f"detail.toml: {row['id']} is not a site of "
                             f"{row['settlement']}")
        sites[row["id"]] = dataclasses.replace(
            sites[row["id"]], region=row["region"],
            capacity=int(row["capacity"]), extent=int(row["extent"]))

    # Authored cohorts replace the one cohort per Alu that minting made, and
    # must account for the same people: a split that loses a hundred heads on
    # the way through is a content bug that would otherwise show up as an
    # unexplained famine ten years in.
    detailed = {row["settlement"] for row in cfg.get("cohorts", [])}
    cohorts = {cid: c for cid, c in registry.cohorts.items()
               if c.settlement not in detailed}
    minted_people: dict[str, int] = {}
    for cohort in registry.cohorts.values():
        minted_people[cohort.settlement] = (
            minted_people.get(cohort.settlement, 0) + cohort.people)
    split_people: dict[str, int] = {}
    for row in cfg.get("cohorts", []):
        known("cohorts", "settlement", row["settlement"], registry.settlements)
        if row["id"] in cohorts:
            raise ValueError(f"detail.toml: two cohorts called {row['id']!r}")
        cohorts[row["id"]] = KernelCohort(
            id=row["id"], settlement=row["settlement"], kind=row["kind"],
            households=int(row["households"]), people=int(row["people"]),
            ethnicity=registry.settlements[row["settlement"]].region,
            status="household", tenure=str(row.get("tenure", "")),
            institution=registry.settlements[row["settlement"]].owner)
        split_people[row["settlement"]] = (
            split_people.get(row["settlement"], 0) + int(row["people"]))
    for settlement, people in sorted(split_people.items()):
        if people != minted_people.get(settlement, 0):
            raise ValueError(
                f"detail.toml: {settlement} is split into {people} people, "
                f"but the scenario authors {minted_people.get(settlement, 0)}")

    orgs = {}
    for row in cfg.get("orgs", []):
        known("orgs", "settlement", row["settlement"], registry.settlements)
        orgs[row["id"]] = KernelOrganization(
            id=row["id"], name=row["name"], settlement=row["settlement"],
            kind=row["kind"], policy=row.get("policy", "subsistence"),
            authority=int(row.get("authority", 0)))
    for site in sites.values():
        if site.holder and site.holder not in orgs:
            raise ValueError(f"detail.toml: {site.id} is held by "
                             f"{site.holder!r}, which is not an organization")

    settlements = {
        sid: dataclasses.replace(
            settlement,
            cohorts=tuple(sorted(c for c in cohorts
                                 if cohorts[c].settlement == sid)),
            orgs=tuple(sorted(o for o in orgs if orgs[o].settlement == sid)))
        for sid, settlement in registry.settlements.items()}

    registry = dataclasses.replace(
        registry, sites=sites, cohorts=cohorts, orgs=orgs,
        settlements=settlements)
    faults = check_registry(registry)
    if faults:
        raise ValueError("detail.toml: " + "; ".join(faults))

    # Opening stores, as lots. Ordinals come from the sorted (owner, good)
    # pairs at each location, so adding a good in one place cannot renumber
    # another's.
    holdings: dict[str, dict[tuple[str, str], int]] = {}
    for row in cfg.get("stores", []):
        settlement = row["settlement"]
        known("stores", "settlement", settlement, registry.settlements)
        owner = row.get("owner") or _controller(orgs, settlement) or settlement
        if (owner not in orgs and owner not in registry.settlements
                and owner not in cohorts):
            raise ValueError(f"detail.toml: {settlement}: stores owned by "
                             f"{owner!r}, which does not exist")
        location = row.get("site", settlement)
        if location not in sites and location not in registry.settlements:
            raise ValueError(f"detail.toml: {settlement}: stores at "
                             f"{location!r}, which does not exist")
        if int(row["quantity"]) <= 0:
            raise ValueError(f"detail.toml: {settlement}: the {row['good']} "
                             "store must be positive")
        key = (owner, row["good"])
        if key in holdings.get(location, {}):
            raise ValueError(f"detail.toml: {location}: {owner} has two "
                             f"opening stores of {row['good']}")
        holdings.setdefault(location, {})[key] = int(row["quantity"])

    book = W.Book(turn=0, phase="authored")
    for location in sorted(holdings):
        for i, (owner, good) in enumerate(sorted(holdings[location])):
            book = book.create(
                mint_id(location, 0, "lot", i), good,
                holdings[location][(owner, good)], owner=owner, holder=owner,
                location=location, reason="authored")

    obligations = []
    for row in cfg.get("obligations", []):
        parse_id(row["id"])
        obligations.append(O.Obligation(
            id=row["id"], party=row["party"], beneficiary=row["beneficiary"],
            clause=row["clause"], good=row.get("good", ""),
            quantity=int(row.get("quantity", 0)), rate=int(row.get("rate", 0)),
            authority=row.get("authority", ""),
            consequence=row.get("consequence", ""),
            due=O.Due(kind=row.get("due_kind", "never"),
                      span=row.get("due_span", ""),
                      every=int(row.get("due_every", 0)),
                      start=int(row.get("due_start", 0)),
                      trigger=row.get("due_trigger", ""))))
    obligation_faults = O.faults(tuple(obligations), exists=registry.exists)
    if obligation_faults:
        raise ValueError("detail.toml: " + "; ".join(obligation_faults))

    seasons = {k: tuple(int(v) for v in vals)
               for k, vals in cfg.get("season", {}).items()}
    climate_raw = cfg.get("climate", {})
    region_climate = {f"region:{name}": tuple(int(v) for v in series)
                      for name, series in climate_raw.get("series", {}).items()}
    for region_id in sorted(region_climate):
        if region_id not in registry.regions:
            raise ValueError(f"climate series for {region_id}, which is not a region")
    drought_curve = tuple(
        (int(p[0]), int(p[1])) for p in climate_raw.get("drought_curve", []))
    return registry, book, tuple(obligations), seasons, region_climate, drought_curve


def _with_drought(series: tuple[int, ...],
                  curve: tuple[tuple[int, int], ...],
                  seed: int, region: str) -> tuple[int, ...]:
    """Lay the authored weather over the authored drought, for thirty years.

    The per-region series are four years long and `climate_at` reads them with
    a modulo, so every region repeated the same four years forever and the
    drought curve -- the whole reason a Late Bronze Age court is interesting --
    reached nobody.

    The curve itself is authored once, so the seed says only when this reign
    met the dry years and how hard this ground took them. Without that every
    campaign died in the same year. The first two years are never shifted: a
    reign does not open in the middle of a drought.
    """
    if not series or not curve:
        return series
    rng = stream(seed, 0, "climate.drought", region)
    early = rng.int(9) - 4                 # the dry years come +/- 4 years
    bite = 850 + rng.int(301)              # and bite 85% to 115% as deep
    opening = lerp_table(curve, 0)

    def sink(turn: int) -> int:
        year = turn // 24
        if year < 2:
            return 0
        return (lerp_table(curve, max(0, year + early)) - opening) * bite // 1000

    # The curve is the authority on how dry it gets. Noise may make one
    # fortnight worse than the year, but never so much worse that the ground
    # stops being ground: below this the crop is not thin, it is absent, and a
    # decade of absent crop is not a game.
    floor = min(value for _year, value in curve) - 8
    return tuple(
        max(0, min(200, max(floor, series[turn % len(series)] + sink(turn))))
        for turn in range(CLIMATE_YEARS * 24))


def load_idmap(registry: Registry) -> dict[str, dict[str, str]]:
    """The court-to-kernel names no rule derives (Task 2 C1).

    Every value must name an entity the registry has. An id map is read at the
    moment a court record is handed to the kernel, which is deep inside a turn
    and a long way from the file; a name that resolves to nothing there fails as
    a missing estate or a correspondent nobody can answer, and the content that
    caused it is not in the traceback. So it is checked once, here, where the
    error can say which line of which section is wrong.

    An empty section is not an error. The sections fill up as the migration
    reaches them, and a section that is empty because its step has not run yet
    is a different thing from one that is wrong.
    """
    path = CONTENT / "kernel" / "idmap.toml"
    if not path.exists():
        return {}
    idmap = tomllib.loads(path.read_text())
    bad = sorted(
        f"[{section}] {court} -> {kernel}"
        for section, entries in idmap.items()
        for court, kernel in entries.items()
        if kernel and not registry.exists(kernel))
    if bad:
        raise ValueError("idmap.toml names entities that do not exist: "
                         + "; ".join(bad))
    return idmap


def _controller(orgs: dict, settlement: str) -> str:
    for org_id in sorted(orgs):
        org = orgs[org_id]
        if org.settlement == settlement and org.kind in ("council", "palace"):
            return org_id
    return ""


def load_spoilage() -> dict[str, int]:
    """Per-good spoilage per fortnight, scaled 1000, from the authored table.

    A good with no rate authored does not spoil, which is the table's own
    convention and is why this reads rather than defaults.
    """
    goods = tomllib.loads((CONTENT / "goods.toml").read_text())
    rates = {}
    for good, row in goods.items():
        rate = row.get("spoilage_per_1000", 0) if isinstance(row, dict) else 0
        if rate < 0:
            raise ValueError(f"goods.toml: {good}: a spoilage rate is not negative")
        if rate:
            rates[good] = rate
    return rates


CONTENT = Path(__file__).parent / "content"

# How far ahead the deterministic climate series is fixed. Thirty years is
# beyond any current run; only elapsed observations may reach divination.
CLIMATE_YEARS = 30


def load_predecessor_archive(chosen_alu: str) -> tuple[Document, ...]:
    """The documents that exist before turn 1 (spec 6.12, 6.17).

    Their `received_turn` is negative, so they sort to the top of every result
    set. A scenario with no predecessor archive -- Pylos, which discards its
    tablets every year and is the whole reason 7.4 is interesting -- simply has
    no file, and gets an empty one rather than an error.
    """
    path = CONTENT / "corpus" / "predecessor_archive" / f"{chosen_alu}.toml"
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


def playable_alus() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in (CONTENT / "courts").glob("*.toml")))


def load_campaign(chosen_alu: str, seed: int) -> World:
    world_cfg = tomllib.loads((CONTENT / "world.toml").read_text())
    alus = {row["id"] for row in world_cfg.get("places", [])
            if row.get("kind", "alu") == "alu"}
    if chosen_alu not in alus:
        raise ValueError(f"unknown Alu {chosen_alu!r}")
    court_path = CONTENT / "courts" / f"{chosen_alu}.toml"
    if not court_path.exists():
        raise ValueError(f"{chosen_alu!r} has no playable court")
    court_cfg = tomllib.loads(court_path.read_text())
    cfg = {**world_cfg, **court_cfg}
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
    places = parse_places(cfg)
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
    sites = parse_sites(cfg, places)
    registry = mint_registry(places, sites, cfg)
    kernel_registry, book, obligations, seasons, region_climate, drought_curve = load_detail(registry)
    # Read for its check. Nothing consumes the map yet -- the sections it will
    # carry belong to steps that have not run -- but a name that has gone stale
    # should fail on the run that broke it, not on the one that first needs it.
    load_idmap(kernel_registry)

    rulers = {polity.ruler for polity in kernel_registry.polities.values()}

    def actor_id(value: str) -> str:
        person = f"person:{value}"
        return person if person in rulers else value

    correspondents = tuple(
        Correspondent(
            actor=actor_id(c["actor"]), place=c["place"],
            cadence=int(c["cadence"]),
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
    relations = {}
    for r in cfg.get("relations", []):
        other = actor_id(r["other"])
        relations[other] = Relation(
            other=other, place=actor_places[other],
            status_claim=r["status_claim"],
            their_status_claim=r["their_status_claim"],
            esteem=int(r.get("esteem", 500)),
            obligation=int(r.get("obligation", 0)),
            last_gift_from_us=int(r.get("last_gift_from_us", 0)),
            last_gift_from_them=int(r.get("last_gift_from_them", 0)),
            best_known_rival_gift=int(r.get("best_known_rival_gift", 0)),
            known_rival_gift_source=actor_id(
                r.get("known_rival_gift_source", "")) or None,
            is_vassal=bool(r.get("is_vassal", False)),
            report_bias=int(r.get("report_bias", 0)),
        )
    oaths = tuple(
        Oath(
            id=o["id"], parties=tuple(actor_id(p) for p in o["parties"]),
            superior=actor_id(o.get("superior", "")) or None,
            gods=tuple(o.get("gods", [])),
            sworn_turn=int(o["sworn_turn"]), sworn_by=actor_id(o["sworn_by"]),
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
    land_cfg = tomllib.loads((CONTENT / "land.toml").read_text())

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
        rites=rites,
        scribe_competence=int(scribe.get("competence", 850)),
        scribe_fatigue=int(scribe.get("fatigue", 300)),
        workshops=workshops, formations=formations,
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
        last_land_due=0,
    )
    plague_cfg = cfg.get("plague", {})
    # The scenario may land infected travellers at a palace centre, because
    # that is where ships come in and the tablet says Ma'hadu. The people they
    # land among are the Alu's, so the seeding resolves to the Alu that holds
    # the harbour -- a palace centre keeps no compartments of its own.
    import_place = str(plague_cfg.get("import_place", ""))
    landed = places.get(import_place)
    if landed is not None and landed.kind == "palace_centre":
        import_place = landed.alu
    plague_state = PlagueState(
        beta=int(plague_cfg.get("beta", 0)),
        gamma=int(plague_cfg.get("gamma", 0)),
        mortality=int(plague_cfg.get("mortality", 0)),
        exposure=int(plague_cfg.get("exposure", 0)),
        import_place=import_place,
        import_turn=int(plague_cfg.get("import_turn", -1)),
        import_cases=int(plague_cfg.get("import_cases", 0)),
    )
    harbour_cargo = {
        lot["id"]: HarbourCargoLot(
            id=lot["id"], owner=lot["owner"], place=lot["place"],
            good=lot["good"], quantity=int(lot["quantity"]))
        for lot in cfg.get("harbour_cargo", [])
    }

    date = Date(year=1, fortnight=0, absolute=0)   # turn 1 begins with an advance

    # Task 2 C2: the court's flat figures cross into the Book as lots at the
    # seat, owned and held by the palace. `detail.toml` authors no granary for
    # the seat precisely so that this is the only one, and `seat_goods.in_hand`
    # reads them straight back -- the seam is a view, not a copy, so the court's
    # mapping and the Book's lots are the same quantities counted twice over
    # rather than two stocks that have to be kept level.
    book, seat_view = seat_goods.deposit(
        book, stores, seat=SEAT_SETTLEMENT, owner=SEAT_OWNER,
        authority=SEAT_OWNER)

    kernel = Kernel(
        seed=seed, date=date, registry=kernel_registry, book=book,
        obligations=obligations, seasons=seasons, seat_goods=seat_view,
        region_climate={region: _with_drought(series, drought_curve, seed, region)
                        for region, series in region_climate.items()},
        spoilage=load_spoilage())

    # The opening division. A settlement's authored granary is one heap, and
    # under subsistence tenure the households' part of it is theirs already --
    # the world does not begin the fortnight before its first harvest. Without
    # this every village in a subsistence country would own nothing until the
    # harvest came round and would starve on the calendar.
    kernel, _ = farm.divide(kernel)

    world = World(
        chosen_alu=chosen_alu,
        court=court,
        kernel=kernel,
        terrain=terrain,
        correspondents=correspondents, season=seasons,
        relations=relations, oaths=oaths,
        plague=plague_state,
        pressure_turn=(1 + seed % 3) * 24,
        documents=load_predecessor_archive(chosen_alu),
        gift_values={k: int(v) for k, v in relation_cfg["gifts"]["value_per_unit"].items()},
        gift_status_floors={
            k: int(v) for k, v in relation_cfg["gifts"]["status_floor"].items()},
        reciprocity_table=tuple(
            (int(point[0]), int(point[1]))
            for point in relation_cfg["gifts"]["reciprocity"]),
        god_ranks={k: int(v) for k, v in relation_cfg["gods"]["rank"].items()},
        protocol_rules={
            k: int(v) for k, v in relation_cfg["protocol"].items()},
        climate=climate_series(seed, CLIMATE_YEARS * 24, drought_curve),
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

    # The crown's payroll joins the registry; the kernel holds and feeds it.
    from engine import seat as seat_door
    world = seat_door.enrol(world, groups)
    # The authored pay-down order is a fact about those people, so it is
    # written on them (Task 2 C3). `enrol` has to have run first: the cohorts
    # it ranks are the ones enrolment just put in the registry.
    return seat_door.rank(world, tuple(cfg["priority"]))
