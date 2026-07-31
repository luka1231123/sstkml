"""Write content/kernel/detail.toml from the scenario-minted registry.

Every row names an entity mint_registry already made. Re-run after the
scenario map changes. Numbers come from the tables below, not from the
old content/kernel/world.toml, which authored four stand-in places.

Anchors from the retired world.toml, whose four places are the only ones that
were ever played, so the scale here is theirs. Ari fed 560 people off ground of
capacity 7500 and extent 60000 with 200,000 qa in the granary; Ma'hadu fed 560
off 31000 of extent with 80,000 in hand. Per head that is 55-107 qa of extent
and 143-357 qa of grain, against a ration of 10 qa a fortnight.

The two numbers mean different things and getting them the wrong way round is
the mistake this comment exists to prevent. `extent` is how much seed the ground
takes in a year, in qa. `capacity` is what it gives back, per 1000 qa sown -- a
rate, not a total. Ground of capacity 7000 returns seven qa for every one.
"""

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from load import mint_from_scenario  # noqa: E402

SCENARIO, SEED = "ugarit", 1
SRC = ROOT / "content/world.toml"
OUT = ROOT / "content/kernel/detail.toml"

# Grain yield per head, by region. The Nile flood and the southern canals
# carry a surplus; the Anatolian plateau does not feed itself and the
# Aegean feeds itself on oil and wine rather than cereal.
YIELD = {
    "nile": 1.60,
    "lower_mesopotamia": 1.50,
    "upper_mesopotamia": 1.10,
    "north_levant": 1.00,
    "south_levant": 0.90,
    "alashiya": 0.80,
    "anatolia": 0.70,
    "aegean": 0.65,
}

# What ground of a middling north Levantine year returns, per 1000 qa sown.
# Multiplied by the region's yield.
RETURN_PER_1000 = 7000

# Qa of seed the ground takes in a year, per head, and what is in the granary
# on the opening day: twenty fortnights of ration, which is the year with a
# margin and not a year and a half.
#
# Divided by the region's yield, which is the correction that matters. Held
# flat, a man on the Anatolian plateau sowed the same ground as a man in the
# Delta and ate two thirds as much every year of his life, so the plateau
# emptied and the Delta filled without one bad harvest anywhere. That is not
# what poor country does to the people farming it. They work more of it: the
# yield decides how much ground a household needs to feed itself, not whether
# it is fed. So the poor regions carry more land per head and every region
# sits near subsistence, and what separates them is not the average year but
# how far a bad one drops -- which is the drought series, region by region,
# and is where the difference belongs.
EXTENT_PER_HEAD = 66
GRAIN_PER_HEAD = 200

# How much ground a household can actually get onto, as a share of what the
# division above says it wants. The correction has a limit and the limit is
# the ground itself: working more of it only answers poor land where there is
# more of it to work. On Cyprus there is a coast and then a mountain, in the
# Aegean a plain the size of a valley floor and then rock, and on the plateau
# distance does the same job -- ground a day's walk past the last house feeds
# nobody, whatever the survey says is arable.
#
# So these three cannot farm their way level, and that is the whole point of
# them. They eat oil, wine, copper and other people's grain, and in a bad year
# they have nothing to fall back on but what they can buy. The Aegean is the
# thinnest of the three, which is why it goes first.
#
# The numbers are close to one and the margin they leave is thin on purpose,
# because the model has no slow decline in it. A settlement either covers its
# ration or it does not, and one that does not loses people, loses the hands
# that work the ground, and comes apart inside a few years. Between a ceiling
# of 0.90 and 0.91 the Aegean goes from gone to standing; there is no setting
# that makes it dwindle picturesquely. So these are set one notch above the
# cliff: the Aegean holds level and never builds a reserve while the Delta
# doubles, which is the difference that matters and is as near the edge as the
# rules can be made to sit.
ARABLE_CEILING = {
    "aegean": 0.91,
    "alashiya": 0.94,
    "anatolia": 0.96,
}

# Play does not begin at the beginning of a story. It opens in the growing
# season, so the predecessor's crop is already standing on the ground: the
# whole extent sown, at what that ground returns.
OPENING_SOWN_PER_1000 = 1000

# A palace centre holds and redistributes; it does not grow. Neither number is
# read by the field rules -- only ground with a food function is sown -- and
# they stand here so a palace is not a site with nothing said about it.
PALACE_CAPACITY_PER_HEAD = 0.10
PALACE_EXTENT_PER_HEAD = 0.50

# Yearly output of a working site, by what it draws. Tin is the scarce one
# and the scarcity is the point: there is no western source, it comes
# overland from beyond Mesopotamia, and bronze depends on it.
SITE_OUTPUT = {
    "copper": 12000,
    "cedar": 5000,
    "horses": 300,
    "silver": 600,
    "gold": 400,
    "lapis": 200,
    "tin": 800,
}

# Opening store of the good a site draws, as a share of its yearly output.
METAL_STORE_SHARE = 0.5

# How a settlement's people divide. Palaces and workshops sit in the big
# seats; a small town is nearly all field labour.
SPLITS = {
    "imperial": (("field_labour", 60), ("craft", 25), ("palace", 15)),
    "royal": (("field_labour", 70), ("craft", 20), ("palace", 10)),
    "seat": (("field_labour", 65), ("craft", 23), ("palace", 12)),
    "town": (("field_labour", 85), ("craft", 12), ("palace", 3)),
}

# A council speaks for a town, a palace for a seat.
ORG_KIND = {
    "imperial": "palace",
    "royal": "palace",
    "seat": "palace",
    "town": "council",
}
ORG_AUTHORITY = {"imperial": 900, "royal": 600, "seat": 700, "town": 300}
# Every controlling org farms and feeds its own town. A palace that hoards
# against its neighbours would be a fourth policy and there is not one yet;
# authoring a name the kernel does not know would leave that Alu deciding
# nothing at all, which is worse than a palace behaving like a council.
ORG_POLICY = {rank: "subsistence" for rank in ORG_KIND}

# The merchant houses, at the ports. `carry.trade` was written and never run:
# every org the generator minted decided by `subsistence`, and a subsistence
# council can only buy what is already standing in its own harbour. Nothing put
# it there, so no qa of grain had ever crossed between two settlements. The
# Delta filled and the islands emptied and there was no mechanism by which the
# one could answer the other.
#
# A house sits where a sea route touches, which is what being a port consists
# of. It is not the controlling org: it decides for itself, holds its own
# purse, and its authority is low because a merchant commands nobody's labour.
#
# The purse is sized off the line it works, not off the town: a house buys at
# most LINE_CARGO in a fortnight, at roughly BASE_PRICE the thousand, so a few
# thousand shekels of copper is several voyages of working capital and an
# empty strongbox is a house that has to sell before it can buy again. Which
# is the interesting failure and the reason not to size this generously.
MERCHANT_KIND = "merchant"
MERCHANT_AUTHORITY = 200
MERCHANT_COPPER = 3000

# Grain owed to the overlord each harvest, per head. A place that answers
# to no one owes nothing.
# Ma'hadu rendered 1800 qa for 560 people, which is where this comes from.
TRIBUTE_PER_HEAD = 3
FREE = "free"


def _split(total, shares):
    """Divide total by percentage shares, giving the remainder to the first."""
    out = [total * pct // 100 for _, pct in shares]
    out[0] += total - sum(out)
    return [(name, n) for (name, _), n in zip(shares, out)]


def build():
    with open(SRC, "rb") as fh:
        raw = tomllib.load(fh)
    reg = mint_from_scenario(raw)
    places = {p["id"]: p for p in raw["places"] if p.get("kind") == "alu"}
    # A port is a place a sea route reaches. Taken off the routes rather than
    # authored again, so a map that gains a crossing gains the house with it.
    ports = {end for route in raw.get("routes", []) if route.get("mode") == "sea"
             for end in (route["a"], route["b"]) if end in places}

    sites, cohorts, stores, orgs, obligations = [], [], [], [], []

    for sid in sorted(reg.settlements):
        slug = sid.split(":", 1)[1]
        place = places[slug]
        pop = int(place["population"])
        region = place["region"]
        rank = place.get("rank", "town")
        power = place.get("power", FREE)
        yld = YIELD[region]

        mine = [reg.sites[i] for i in sorted(reg.sites) if reg.sites[i].settlement == sid]
        food = [s for s in mine if s.function == "food"]
        palaces = [s for s in mine if s.function == "palace_centre"]
        draws = [s for s in mine if s.function in SITE_OUTPUT]

        # A settlement's food land is one estate, standing on the first of its
        # food marks. The others are the same plain drawn in another place on
        # the tablet and carry no extent of their own -- an actor sows the
        # ground it can see, and what it can see is one estate, so extent
        # spread over three marks would leave two thirds of the crop untended
        # by a council that never knew it was there.
        if food:
            cap = int(RETURN_PER_1000 * yld)
            for i, site in enumerate(food):
                per_head = EXTENT_PER_HEAD / yld * ARABLE_CEILING.get(region, 1.0)
                extent = int(pop * per_head) if i == 0 else 0
                sites.append({
                    "id": site.id, "settlement": sid, "region": f"region:{region}",
                    "function": "food", "capacity": cap, "extent": extent,
                })
                # The predecessor's crop, already in the ground on day one.
                standing = extent * OPENING_SOWN_PER_1000 // 1000 * cap // 1000
                if standing:
                    stores.append({
                        "settlement": sid, "site": site.id,
                        "good": "standing_grain", "quantity": standing,
                    })

        for site in palaces:
            sites.append({
                "id": site.id, "settlement": sid, "region": f"region:{region}",
                "function": "palace_centre",
                "capacity": int(pop * PALACE_CAPACITY_PER_HEAD / len(palaces)),
                "extent": int(pop * PALACE_EXTENT_PER_HEAD / len(palaces)),
            })

        # Two copper marks are two workings of one metal, so the yearly output
        # divides between them and the opening store is one heap, not two: a
        # settlement keeps one pile of copper however many diggings feed it.
        drawn: dict[str, int] = {}
        for site in draws:
            out = SITE_OUTPUT[site.function] // max(
                1, sum(1 for s in draws if s.function == site.function))
            sites.append({
                "id": site.id, "settlement": sid, "region": f"region:{region}",
                "function": site.function, "capacity": out, "extent": 0,
            })
            drawn[site.function] = drawn.get(site.function, 0) + out
        for good in sorted(drawn):
            stores.append({"settlement": sid, "good": good,
                           "quantity": int(drawn[good] * METAL_STORE_SHARE)})

        # The one minted cohort becomes three.
        base = reg.cohorts[f"cohort:{slug}_people"]
        for kind, people in _split(base.people, SPLITS[rank]):
            if not people:
                continue
            cohorts.append({
                "id": f"cohort:{slug}_{kind}", "settlement": sid, "kind": kind,
                "households": people // 5, "people": people,
            })

        # No opening seed: the crop is in the ground already, and next year's
        # seed is what the threshing floor sets aside out of it. A settlement
        # that eats its seed has made that decision itself.
        stores.append({"settlement": sid, "good": "grain",
                       "quantity": int(pop * GRAIN_PER_HEAD * yld)})

        orgs.append({
            "id": f"org:{slug}_{ORG_KIND[rank]}", "name": f"the {ORG_KIND[rank]} of {place['name']}"
            if place.get("name") else f"the {ORG_KIND[rank]} of {slug}",
            "settlement": sid, "kind": ORG_KIND[rank],
            "policy": ORG_POLICY[rank], "authority": ORG_AUTHORITY[rank],
        })

        # The house at the quay, and the copper it works with. Its own org, so
        # it decides by its own policy and its purse is not the palace's.
        if slug in ports:
            where = place.get("name") or slug
            orgs.append({
                "id": f"org:{slug}_merchants",
                "name": f"the merchants of {where}",
                "settlement": sid, "kind": MERCHANT_KIND,
                "policy": "trade", "authority": MERCHANT_AUTHORITY,
            })
            stores.append({
                "settlement": sid, "owner": f"org:{slug}_merchants",
                "good": "copper", "quantity": MERCHANT_COPPER,
            })

        if power != FREE and f"polity:{power}" in reg.polities:
            obligations.append({
                "id": f"{sid}/0/obligation/0", "party": sid,
                "beneficiary": f"polity:{power}", "clause": "fixed_quantity",
                "good": "grain", "quantity": int(pop * TRIBUTE_PER_HEAD * yld),
                "due_kind": "season", "due_span": "harvest",
                "authority": f"polity:{power}",
                "consequence": "the overlord would send for the elders",
            })

    seasons = {k: tuple(int(v) for v in vals)
               for k, vals in raw.get("season", {}).items()}
    climate_raw = raw.get("climate", {})
    climate_series = {
        name: tuple(int(v) for v in series)
        for name, series in climate_raw.get("series", {}).items()}
    drought_curve = tuple(
        tuple(int(v) for v in p) for p in climate_raw.get("drought_curve", []))

    return {"sites": sites, "cohorts": cohorts, "stores": stores,
            "orgs": orgs, "obligations": obligations,
            "season": seasons, "climate_series": climate_series,
            "drought_curve": drought_curve}


def _even(total, n):
    """Split total into n parts, remainder onto the first."""
    parts = [total // n] * n
    parts[0] += total - sum(parts)
    return parts


def _val(v):
    if isinstance(v, str):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return str(v)


def _inline(key, vals):
    """TOML inline array, e.g. sailing_open = [7, 21]"""
    return f"{key} = [{', '.join(str(v) for v in vals)}]"

def dump(data):
    """Write the tables as TOML. Only strings and ints appear here."""
    lines = ["# Written by tools/gen_detail.py. Do not edit by hand; edit the",
             "# rates at the top of that file and run it again.", ""]
    if data.get("season"):
        lines.append("[season]")
        for name, span in sorted(data["season"].items()):
            lines.append(_inline(name, span))
        lines.append("")
    if data.get("drought_curve"):
        lines.append("[climate]")
        pts = ", ".join(f"[{a}, {b}]" for a, b in data["drought_curve"])
        lines.append(f"drought_curve = [{pts}]")
        lines.append("")
    if data.get("climate_series"):
        lines.append("[climate.series]")
        for name, series in sorted(data["climate_series"].items()):
            lines.append(_inline(name, series))
        lines.append("")
    for table in ("sites", "cohorts", "stores", "orgs", "obligations"):
        for row in data[table]:
            lines.append(f"[[{table}]]")
            lines += [f"{k} = {_val(v)}" for k, v in row.items()]
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    data = build()
    with open(OUT, "w") as fh:
        fh.write(dump(data))
    for k, v in data.items():
        if isinstance(v, (list, tuple)):
            print(f"{k}: {len(v)}")
        elif isinstance(v, dict):
            print(f"{k}: {len(v)} keys")
        else:
            print(f"{k}: {v}")
