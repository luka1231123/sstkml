"""Authored content -> the kernel world (spec 10.1: loaders live outside engine/).

`engine/` never touches the filesystem, so this is where the TOML becomes
frozen entities. It validates as it goes: kinds, ids, references, and the
authored ranges. A world that will not load is better than one that loads
wrong and produces a plausible-looking history from bad numbers.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from engine import obligation as O
from engine import ownership as W
from engine.core import Date
from engine.entity import (Cohort, Leg, Organization, Polity, Region, Registry,
                           Route, Settlement, Site, check, mint, parse)
from engine.kernel.world import Kernel

CONTENT = Path(__file__).parent / "content"


class ContentError(ValueError):
    """Authored content that does not describe a world that could exist."""


def _rows(cfg: dict, key: str) -> list[dict]:
    rows = cfg.get(key, [])
    if not isinstance(rows, list):
        raise ContentError(f"{key} must be a list of tables")
    return rows


def load_kernel(name: str = "world", seed: int = 1) -> Kernel:
    path = CONTENT / "kernel" / f"{name}.toml"
    if not path.exists():
        raise ContentError(f"no such kernel world: {path}")
    cfg = tomllib.loads(path.read_text())

    regions = {r["id"]: Region(
        id=r["id"], name=r["name"],
        climate_bias=r.get("climate_bias", 0),
        travel_modifier=r.get("travel_modifier", 1000))
        for r in _rows(cfg, "regions")}

    polities = {p["id"]: Polity(
        id=p["id"], name=p["name"], ruler=p.get("ruler", ""),
        seat=p.get("seat", ""), controls=tuple(p.get("controls", ())),
        claims=tuple(p.get("claims", ())))
        for p in _rows(cfg, "polities")}

    settlements = {s["id"]: Settlement(
        id=s["id"], name=s["name"], region=s["region"], polity=s["polity"],
        sites=tuple(s.get("sites", ())), autonomous=s.get("autonomous", True))
        for s in _rows(cfg, "settlements")}

    sites = {s["id"]: Site(
        id=s["id"], name=s["name"], settlement=s["settlement"],
        function=s["function"], region=s.get("region", ""),
        capacity=s.get("capacity", 0), extent=s.get("extent", 0),
        holder=s.get("holder", ""))
        for s in _rows(cfg, "sites")}
    for site in sites.values():
        if site.function == "estate" and (site.capacity <= 0 or site.extent <= 0):
            raise ContentError(
                f"{site.id}: an estate needs both a seed-return capacity and an "
                f"extent, or nothing can be sown on it")

    cohorts = {c["id"]: Cohort(
        id=c["id"], settlement=c["settlement"], kind=c["kind"],
        households=c["households"], people=c["people"],
        origin=c.get("origin", ""),
        labour_per_head=c.get("labour_per_head", 12),
        ration_per_head=c.get("ration_per_head", 10))
        for c in _rows(cfg, "cohorts")}

    orgs = {o["id"]: Organization(
        id=o["id"], name=o["name"], settlement=o["settlement"],
        kind=o["kind"], policy=o.get("policy", "subsistence"),
        authority=o.get("authority", 0))
        for o in _rows(cfg, "orgs")}
    for site in sites.values():
        if site.holder and site.holder not in orgs:
            raise ContentError(
                f"{site.id}: held by {site.holder!r}, which is not an organization")

    routes = {}
    for r in _rows(cfg, "routes"):
        legs = tuple(Leg(origin=l["origin"], destination=l["destination"],
                         mode=l["mode"], fortnights=l.get("fortnights", 1),
                         season=l.get("season", ""))
                     for l in r.get("legs", ()))
        routes[r["id"]] = Route(
            id=r["id"], name=r["name"], legs=legs,
            capacity=r.get("capacity", 0), risk=r.get("risk", 0),
            toll_jurisdictions=tuple(r.get("toll_jurisdictions", ())))

    registry = Registry(regions=regions, polities=polities,
                        settlements=settlements, sites=sites, routes=routes,
                        cohorts=cohorts, orgs=orgs)
    faults = check(registry)
    if faults:
        raise ContentError(
            f"{path.name}: " + "; ".join(faults))

    # A season is a span of fortnights: a [first, last] range, or an explicit
    # list of them. Checked rather than trusted, because the one thing that can
    # be written into this table by accident is a long array of something else
    # -- the climate series belongs above the header and reads as a season named
    # "climate" if it is written below it. That mistake is silent otherwise: the
    # world loads, and every year has identical weather.
    seasons = {k: tuple(v) for k, v in cfg.get("seasons", {}).items()}
    for name, span in sorted(seasons.items()):
        if not span or len(span) > 24:
            raise ContentError(
                f"season {name!r} is not a fortnight span: {len(span)} entries")
        if any(not isinstance(f, int) or not 1 <= f <= 24 for f in span):
            raise ContentError(
                f"season {name!r} names something that is not a fortnight")
    for leg in (leg for route in routes.values() for leg in route.legs):
        if leg.season and leg.season not in seasons:
            raise ContentError(f"leg names season {leg.season!r}, which is not authored")

    # Opening stores, as lots. Ordinals come from the sorted (owner, good) pairs
    # at each location, so adding a good in one place cannot renumber another's.
    #
    # A row may name a `site` and an `owner`. Both exist for the same reason:
    # the world does not begin at the beginning of a story. There is already a
    # crop in the ground when play starts, it is standing on a named estate
    # rather than in the town, and some of it belongs to the temple. A scenario
    # that could only author grain in a granary would have to start every game
    # in the one fortnight of the year when that is the whole truth.
    book = W.Book(turn=0, phase="authored")
    holdings: dict[str, dict[tuple[str, str], int]] = {}
    for row in _rows(cfg, "stores"):
        settlement = row["settlement"]
        if settlement not in settlements:
            raise ContentError(f"stores at {settlement!r}, which does not exist")
        owner = row.get("owner") or _controller(orgs, settlement) or settlement
        if owner not in orgs and owner not in settlements:
            raise ContentError(
                f"{settlement}: stores owned by {owner!r}, which does not exist")
        location = row.get("site", settlement)
        if location not in sites and location not in settlements:
            raise ContentError(
                f"{settlement}: stores at {location!r}, which does not exist")
        if location in sites and sites[location].settlement != settlement:
            raise ContentError(
                f"{location} is not a site of {settlement}")
        if row["quantity"] <= 0:
            raise ContentError(
                f"{settlement}: the {row['good']} store must be positive")
        key = (owner, row["good"])
        if key in holdings.get(location, {}):
            raise ContentError(
                f"{location}: {owner} has two opening stores of {row['good']}")
        holdings.setdefault(location, {})[key] = row["quantity"]

    for location in sorted(holdings):
        for i, (owner, good) in enumerate(sorted(holdings[location])):
            book = book.create(
                mint(location, 0, "lot", i), good, holdings[location][(owner, good)],
                owner=owner, holder=owner, location=location, reason="authored")

    obligations = []
    for row in _rows(cfg, "obligations"):
        parse(row["id"])
        obligations.append(O.Obligation(
            id=row["id"], party=row["party"], beneficiary=row["beneficiary"],
            clause=row["clause"], good=row.get("good", ""),
            quantity=row.get("quantity", 0), rate=row.get("rate", 0),
            authority=row.get("authority", ""),
            consequence=row.get("consequence", ""),
            due=O.Due(kind=row.get("due_kind", "never"),
                      span=row.get("due_span", ""),
                      every=row.get("due_every", 0),
                      start=row.get("due_start", 0),
                      trigger=row.get("due_trigger", ""))))

    obligation_faults = O.faults(tuple(obligations), exists=registry.exists)
    if obligation_faults:
        raise ContentError(f"{path.name}: " + "; ".join(obligation_faults))

    climate = tuple(cfg.get("climate", ()))
    if any(c < 0 for c in climate):
        raise ContentError("climate indices are non-negative")

    return Kernel(
        seed=seed, date=Date(year=1, fortnight=1, absolute=0),
        registry=registry, book=book, obligations=tuple(obligations),
        beliefs={}, seasons=seasons, climate=climate, spoilage=_spoilage())


def _spoilage() -> dict[str, int]:
    """Per-good spoilage per fortnight, scaled 1000, from the authored table.

    One source of truth for a rate the kernel and the single-city systems both
    apply. A good with no rate authored does not spoil, which is the table's own
    convention and is why this reads rather than defaults.
    """
    path = CONTENT / "goods.toml"
    if not path.exists():
        raise ContentError(f"no goods table: {path}")
    goods = tomllib.loads(path.read_text())
    rates = {}
    for good, row in goods.items():
        rate = row.get("spoilage_per_1000", 0) if isinstance(row, dict) else 0
        if rate < 0:
            raise ContentError(f"{good}: a spoilage rate is not negative")
        if rate:
            rates[good] = rate
    return rates


def _controller(orgs: dict, settlement: str) -> str:
    for org_id in sorted(orgs):
        org = orgs[org_id]
        if org.settlement == settlement and org.kind == "council":
            return org_id
    return ""
