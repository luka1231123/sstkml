"""Kernel identity: who and where things are (spec 5.1, 5.2, 10.7).

Two kinds of identifier, and the difference is the whole point.

*Authored* IDs come from content and are namespaced by kind -- `polity:ugarit`,
`site:mahadu_harbour`. They are written by a person and never change.

*Runtime* IDs are minted during play from a stable parent, the turn, a
registered domain, and an ordinal local to that triple. They deliberately do
not come from a world-wide counter. The current game's `letter_seq`,
`omen_seq`, and `gift_seq` are exactly such counters, and they mean that
inserting one letter renumbers every later document and moves the state hash --
so a change to one system silently perturbs another, which spec 10.2 forbids
for random draws and spec 5 forbids for identity.

Everything here is frozen and integer-only. Registries are plain mappings and
every iteration over them is over `sorted()` keys: nothing in the kernel may
depend on mapping order.
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping

EntityId = str
GoodId = str

# The kinds an authored ID may name. Closed: adding one is a spec change.
KINDS = frozenset({
    "region",
    "polity",
    "settlement",
    "site",
    "org",
    "person",
    "household",
    "cohort",
    "route",
})

# The domains a runtime ID may be minted in. Separate from the rng domains in
# engine.core: an ID domain says what kind of thing is being created, an rng
# domain says which draw stream it came from, and conflating them would tie
# identity to whether a system happened to roll dice.
ID_DOMAINS = frozenset({
    "shipment",
    "journey",
    "lot",
    "obligation",
    "contract",
    "debt",
    "claim",
    "observation",
    "report",
    "document",
    "order",
    "mission",
    "petition",
    "person",
    "household",
})

_AUTHORED = re.compile(r"^([a-z]+):([a-z0-9_]+)$")
_SEGMENT = re.compile(r"^[a-z0-9_]+$")


class BadId(ValueError):
    """An identifier that would not survive a replay."""


def authored(kind: str, name: str) -> EntityId:
    """`authored("site", "mahadu_harbour") -> "site:mahadu_harbour"`."""
    if kind not in KINDS:
        raise BadId(f"unregistered entity kind: {kind!r}")
    if not _SEGMENT.match(name):
        raise BadId(f"authored name must be [a-z0-9_]: {name!r}")
    return f"{kind}:{name}"


def kind_of(entity_id: EntityId) -> str:
    """The kind an ID names, following a runtime ID back to its parent."""
    root = entity_id.split("/", 1)[0]
    match = _AUTHORED.match(root)
    if not match:
        raise BadId(f"not an entity id: {entity_id!r}")
    return match.group(1)


def is_valid(entity_id: EntityId) -> bool:
    try:
        parse(entity_id)
    except BadId:
        return False
    return True


def parse(entity_id: EntityId) -> tuple[str, str, tuple[str, ...]]:
    """`(kind, name, runtime_suffix)`. Raises `BadId` on anything else."""
    if not isinstance(entity_id, str) or not entity_id:
        raise BadId(f"not an entity id: {entity_id!r}")
    root, *rest = entity_id.split("/")
    match = _AUTHORED.match(root)
    if not match:
        raise BadId(f"not an entity id: {entity_id!r}")
    if rest:
        if len(rest) != 3:
            raise BadId(
                f"runtime id must be parent/turn/domain/ordinal: {entity_id!r}")
        turn, domain, ordinal = rest
        if not turn.isdigit() or not ordinal.isdigit():
            raise BadId(f"turn and ordinal must be digits: {entity_id!r}")
        if domain not in ID_DOMAINS:
            raise BadId(f"unregistered id domain: {domain!r}")
    return match.group(1), match.group(2), tuple(rest)


def mint(parent: EntityId, turn: int, domain: str, ordinal: int) -> EntityId:
    """One runtime ID. Prefer `mint_all`, which fixes the ordinals for you."""
    parse(parent)
    if domain not in ID_DOMAINS:
        raise BadId(f"unregistered id domain: {domain!r}")
    if turn < 0 or ordinal < 0:
        raise BadId("turn and ordinal are non-negative")
    if parent.count("/"):
        # Runtime IDs do not nest. A shipment's cargo hangs off the site, not
        # off the shipment, or the ID grows without bound over a long game.
        raise BadId(f"cannot mint from a runtime id: {parent!r}")
    return f"{parent}/{turn}/{domain}/{ordinal}"


def mint_all(parent: EntityId, turn: int, domain: str,
             keys: tuple[str, ...]) -> dict[str, EntityId]:
    """IDs for a batch, ordinals assigned in sorted key order.

    This is the form to use. Passing the natural keys of whatever is being
    created -- and letting the sort fix the ordinals -- is what makes the
    result independent of the order the caller's loop happened to run in.
    """
    unique = sorted(set(keys))
    if len(unique) != len(keys):
        raise BadId("mint_all needs distinct keys")
    return {key: mint(parent, turn, domain, i)
            for i, key in enumerate(unique)}


# --- geography and political structure (spec 5.1) -----------------------------

@dataclasses.dataclass(frozen=True)
class Region:
    """A broad ecological area. Not a government and not a market."""
    id: EntityId
    name: str
    climate_bias: int = 0        # added to the climate index, 0 = none
    travel_modifier: int = 1000  # scaled 1000 = ordinary going


@dataclasses.dataclass(frozen=True)
class Polity:
    """A political authority, which is not the same thing as a place."""
    id: EntityId
    name: str
    ruler: EntityId = ""
    seat: EntityId = ""                      # settlement id
    controls: tuple[EntityId, ...] = ()      # settlements held
    claims: tuple[EntityId, ...] = ()        # settlements asserted, not held


@dataclasses.dataclass(frozen=True)
class Settlement:
    """A persistent inhabited node under some governing authority."""
    id: EntityId
    name: str
    region: EntityId
    polity: EntityId
    sites: tuple[EntityId, ...] = ()
    cohorts: tuple[EntityId, ...] = ()
    orgs: tuple[EntityId, ...] = ()
    # Whether this settlement runs its own decisions. The player's seat is
    # False during M13.1: its intents come from the player and the legacy
    # adapter, not from a policy.
    autonomous: bool = True


@dataclasses.dataclass(frozen=True)
class Site:
    """A productive or strategic place that need not be a city."""
    id: EntityId
    name: str
    settlement: EntityId
    function: str                # "harbour" | "estate" | "mine" | "pasture" ...
    region: EntityId = ""
    capacity: int = 0            # meaning is the function's; 0 = unmodelled
    # How much the place will take, as opposed to how well it repays. For an
    # estate: qa of seed the ground holds in a year, which is the land itself
    # and the reason a settlement cannot sow its way out of a famine. Two
    # numbers rather than one because good ground and much ground are different
    # things, and a settlement can be short of either.
    extent: int = 0              # 0 = unmodelled
    # The organization that works this place, where one does. A temple estate
    # and the town's fields are different ground with different owners, which
    # is how the records have them; modelling them as one field would invent a
    # scramble for furrows that nobody in the period was having. What the two
    # do compete for is hands, and that contest is the allocator's.
    holder: EntityId = ""


@dataclasses.dataclass(frozen=True)
class Leg:
    """One stage of a route, between two sites or settlements."""
    origin: EntityId
    destination: EntityId
    mode: str                    # "sea" | "river" | "road" | "track"
    fortnights: int = 1
    season: str = ""             # named span it is open in; "" = all year


@dataclasses.dataclass(frozen=True)
class Route:
    """A connection that carries journeys, cargo, people, news, and disease.

    Distinct from `engine.state.Route`, which is the pre-kernel letter edge and
    is retired with the legacy adapter (spec 9, migration table).
    """
    id: EntityId
    name: str
    legs: tuple[Leg, ...] = ()
    capacity: int = 0            # units of cargo per fortnight; 0 = unmodelled
    toll_jurisdictions: tuple[EntityId, ...] = ()
    risk: int = 0                # scaled 1000

    @property
    def origin(self) -> EntityId:
        return self.legs[0].origin if self.legs else ""

    @property
    def destination(self) -> EntityId:
        return self.legs[-1].destination if self.legs else ""

    def fortnights(self) -> int:
        return sum(leg.fortnights for leg in self.legs)


# --- people and organizations (spec 5.2, 5.3) ---------------------------------

@dataclasses.dataclass(frozen=True)
class Cohort:
    """Ordinary population, persistent and counted (spec 5.3).

    A cohort is not a number of people in a settlement's ledger: it has an
    origin, a residence, a memory of going hungry, and it can be split or
    merged without losing either. Splitting and merging must conserve people.
    """
    id: EntityId
    settlement: EntityId
    kind: str                    # "field_labour" | "craft" | "carrier" | ...
    households: int
    people: int
    origin: EntityId = ""        # where they are from, if not where they live
    labour_per_head: int = 12    # person-days per fortnight
    ration_per_head: int = 10    # units of grain per person per fortnight
    hunger: int = 0              # fortnights of shortfall; the cohort's memory
    grievance: int = 0           # scaled 1000

    def labour(self) -> int:
        # Hunger takes the strength before it takes the numbers.
        able = max(0, 1000 - self.hunger * 100)
        return self.people * self.labour_per_head * min(1000, able) // 1000

    def ration(self) -> int:
        return self.people * self.ration_per_head


@dataclasses.dataclass(frozen=True)
class Organization:
    """An enduring actor: palace, temple, merchant house, village council."""
    id: EntityId
    name: str
    settlement: EntityId
    kind: str                    # "council" | "palace" | "temple" | "merchant"
    policy: str = "subsistence"  # which deterministic policy it decides by
    authority: int = 0           # rank, used to break allocation ties


# --- registries ---------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Registry:
    """The kernel's flat entity tables. One mapping per kind, keyed by ID."""
    regions: Mapping[EntityId, Region] = dataclasses.field(default_factory=dict)
    polities: Mapping[EntityId, Polity] = dataclasses.field(default_factory=dict)
    settlements: Mapping[EntityId, Settlement] = dataclasses.field(
        default_factory=dict)
    sites: Mapping[EntityId, Site] = dataclasses.field(default_factory=dict)
    routes: Mapping[EntityId, Route] = dataclasses.field(default_factory=dict)
    cohorts: Mapping[EntityId, Cohort] = dataclasses.field(default_factory=dict)
    orgs: Mapping[EntityId, Organization] = dataclasses.field(
        default_factory=dict)

    def tables(self) -> tuple[tuple[str, Mapping], ...]:
        return (
            ("regions", self.regions),
            ("polities", self.polities),
            ("settlements", self.settlements),
            ("sites", self.sites),
            ("routes", self.routes),
            ("cohorts", self.cohorts),
            ("orgs", self.orgs),
        )

    def exists(self, entity_id: EntityId) -> bool:
        return any(entity_id in table for _, table in self.tables())

    def ids(self) -> tuple[EntityId, ...]:
        found: list[EntityId] = []
        for _, table in self.tables():
            found.extend(sorted(table))
        return tuple(found)


def check(registry: Registry) -> tuple[str, ...]:
    """Referential faults, as sentences. Empty means the registry is sound."""
    faults: list[str] = []

    def require(where: str, field: str, value: EntityId, table: Mapping) -> None:
        if value and value not in table:
            faults.append(f"{where}: {field} names {value!r}, which does not exist")

    for sid in sorted(registry.settlements):
        settlement = registry.settlements[sid]
        require(sid, "region", settlement.region, registry.regions)
        require(sid, "polity", settlement.polity, registry.polities)
        for site_id in settlement.sites:
            require(sid, "site", site_id, registry.sites)

    for site_id in sorted(registry.sites):
        site = registry.sites[site_id]
        require(site_id, "settlement", site.settlement, registry.settlements)
        require(site_id, "region", site.region, registry.regions)

    for pid in sorted(registry.polities):
        polity = registry.polities[pid]
        require(pid, "seat", polity.seat, registry.settlements)
        for held in polity.controls:
            require(pid, "controls", held, registry.settlements)

    for cid in sorted(registry.cohorts):
        cohort = registry.cohorts[cid]
        require(cid, "settlement", cohort.settlement, registry.settlements)
        if cohort.people < 0 or cohort.households < 0:
            faults.append(f"{cid}: negative population")
        if cohort.households > cohort.people:
            faults.append(
                f"{cid}: {cohort.households} households among {cohort.people} people")

    for oid in sorted(registry.orgs):
        org = registry.orgs[oid]
        require(oid, "settlement", org.settlement, registry.settlements)

    for rid in sorted(registry.routes):
        route = registry.routes[rid]
        for leg in route.legs:
            for field, value in (("origin", leg.origin),
                                 ("destination", leg.destination)):
                if not registry.exists(value):
                    faults.append(
                        f"{rid}: leg {field} names {value!r}, which does not exist")

    for entity_id in registry.ids():
        if not is_valid(entity_id):
            faults.append(f"{entity_id!r} is not a well-formed entity id")

    return tuple(faults)
