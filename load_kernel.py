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
        capacity=s.get("capacity", 0))
        for s in _rows(cfg, "sites")}

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

    seasons = {k: tuple(v) for k, v in cfg.get("seasons", {}).items()}
    for leg in (leg for route in routes.values() for leg in route.legs):
        if leg.season and leg.season not in seasons:
            raise ContentError(f"leg names season {leg.season!r}, which is not authored")

    # Opening stores, as lots. Ordinals come from the sorted goods at each
    # settlement, so adding a good to one settlement cannot renumber another's.
    book = W.Book(turn=0, phase="authored")
    holdings: dict[str, dict[str, int]] = {}
    for row in _rows(cfg, "stores"):
        holdings.setdefault(row["settlement"], {})[row["good"]] = row["quantity"]
    for settlement in sorted(holdings):
        if settlement not in settlements:
            raise ContentError(f"stores at {settlement!r}, which does not exist")
        owner = _controller(orgs, settlement) or settlement
        for i, good in enumerate(sorted(holdings[settlement])):
            quantity = holdings[settlement][good]
            if quantity <= 0:
                raise ContentError(f"{settlement}: {good} store must be positive")
            book = book.create(
                mint(settlement, 0, "lot", i), good, quantity, owner=owner,
                holder=owner, location=settlement, reason="authored")

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
        beliefs={}, seasons=seasons, climate=climate)


def _controller(orgs: dict, settlement: str) -> str:
    for org_id in sorted(orgs):
        org = orgs[org_id]
        if org.settlement == settlement and org.kind == "council":
            return org_id
    return ""
