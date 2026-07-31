#!/usr/bin/env python3
"""Sort out which places are Alu and which answer to one.

Task 1 authored 42 Alu against a rule: an Alu is a place with its own king,
its own Seat and its own decisions; everything else is a dependent palace
centre of the Alu whose king it answers to (`docs/ALU_CLASSIFICATION.md` §1).
Thirty-nine places were added afterwards, and most of them break that rule --
Hittite cult cities with no king, Kassite provincial towns, Egyptian nome
seats, Argolid citadels a morning's walk from Mycenae. They were drawn as
kingdoms, they were wired into the road network as kingdoms, and in the
Argolid five of them sat inside thirty kilometres of each other.

This does three things and writes them back into `content/world.toml`:

  1. Demotes those places to dependent palace centres, each under the Alu whose
     king it actually answered to. Its people go with it: the population folds
     into the owner, so the map holds the same number of people afterwards.
  2. Drops the invented and the duplicated palace-centre marks -- six of them
     name a place that is also on the map as its own record, and Agade has not
     been found on the ground or occupied since the second millennium began.
  3. Puts sixteen places back where they are. Several were a hundred
     kilometres out, which is most of why the Levant looked so crowded: Akko
     and Hazor stood seven kilometres apart on a map where they are fifty.

Run `tools/route_geography.py` and `tools/gen_detail.py` after this: the road
network is built over the Alu, and there are fewer of them now.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/world.toml"

# Alu that had no king of their own, and the Alu whose king they answered to.
# The reason is in the third column because it is the whole argument.
DEMOTIONS = {
    # Hatti's core. Cult cities and royal residences, all the Great King's.
    "arinna": ("hattusa", "the sun goddess's city, and the queen's own cult"),
    "nerik": ("hattusa", "the storm god's city in the north"),
    "sapinuwa": ("hattusa", "a royal residence, and an arsenal"),
    "samuha": ("hattusa", "the upper river city, and a second court in war"),
    "ankura": ("hattusa", "Ankuwa, on the road east"),
    "lawazantiya": ("kanesh", "a Kizzuwatnan cult town, Hatti's since"),
    # The Argolid, where five marks stood inside thirty kilometres.
    "tiryns": ("mycenae", "the lower citadel, and Mycenae's harbour"),
    "argos": ("mycenae", "the plain below the citadels"),
    "lerna": ("mycenae", "an old town on the gulf, no palace by now"),
    "korinthos": ("mycenae", "the isthmus, and the crossing of it"),
    "sparta": ("pylos", "the Eurotas, and one hall above it"),
    "dimini": ("iolcos", "the harbour town below Iolcos, if not Iolcos"),
    # Egypt. One king, and he is at Pi-Ramesses.
    "iunu": ("memphis", "Ra's city, and the oldest priesthood in the land"),
    "per_bastet": ("egypt", "Bastet's city, and the eastern delta's cattle"),
    "hut_herib": ("egypt", "the delta's middle ground"),
    "djanet": ("egypt", "the northern shore of the delta"),
    "hut_nesut": ("khemenu", "the middle river's granary towns"),
    "per_medjed": ("khemenu", "the canal mouth into the oasis road"),
    "abw": ("waset", "Elephantine, the gate of the cataract"),
    # Karduniash. Babylon's provinces, governed, not ruled.
    "kish": ("babylon", "the old kingship, an hour from Babylon's wall"),
    "isin": ("nippur", "Gula's city, and a governor's seat"),
    "larsa": ("uruk", "Shamash's city on the same canal"),
    "lagash": ("ur", "Girsu's ground, long past its own kings"),
    # Assyria's west, and the ruins in it.
    "harran": ("carchemish", "Sin's city, and the crossing of the Balikh"),
    "mari": ("dur_katlimmu", "a garrison on a ruin four centuries old"),
    "shubat_enlil": ("nagar", "the Habur triangle, held from Nagar"),
    # Egypt's garrison towns in Canaan.
    "yafa": ("gezer", "the harbour, and a granary under Egyptian guard"),
}

# Palace-centre marks to drop. Six name a place that is on the map already as
# its own record; Agade has never been located and was not occupied.
DROP_SITES = {
    ("babylon", "Kish"), ("memphis", "Iunu"), ("mycenae", "Argos"),
    ("hattusa", "Nerik"), ("hattusa", "Sapinuwa"),
    ("thebes_gr", "Orchomenos"), ("dur_kurigalzu", "Agade"),
}

# Places whose mark was in the wrong place, and where the site actually is.
# Only sites whose identification is settled are moved; Tarhuntassa, which
# nobody has found, stays where it was authored.
MOVES = {
    "damascus": (36.29, 33.51),
    "kadesh": (36.52, 34.57),
    "shechem": (35.28, 32.21),
    "gezer": (34.92, 31.86),
    "jerusalem": (35.23, 31.78),
    "akko": (35.07, 32.93),
    "alashiya": (33.99, 35.16),        # Enkomi, the island's own harbour
    "tabetu": (40.65, 36.02),          # Tell Taban
    "korinthos": (22.88, 37.91),
    "argos": (22.72, 37.63),
    "nerik": (35.29, 40.94),           # Oymaagac, held to the map's north edge
    "arinna": (34.70, 40.23),          # Alacahoyuk
    "sapinuwa": (35.25, 40.45),        # Ortakoy
    "samuha": (37.55, 39.72),          # Kayalipinar
    "lawazantiya": (37.20, 38.30),     # the Elbistan plain
    "yafa": (34.75, 32.05),
}

# Gla is Orchomenos's fortress round Orchomenos's drained lake, and it was
# authored under Thebes.
REPARENT = {"gla": "orchomenos"}


def block_of(text, header, key, value):
    """The span of the `header` block whose `key` is `value`."""
    pattern = re.compile(
        rf'^\[\[{header}\]\]\n(?:(?!^\[).*\n?)*', re.MULTILINE)
    for match in pattern.finditer(text):
        if re.search(rf'^{key} = "{re.escape(value)}"$', match.group(0),
                     re.MULTILINE):
            return match
    return None


def set_key(block, key, line):
    """Replace a key's line, or add it after `name`."""
    if re.search(rf'^{key} = ', block, re.MULTILINE):
        return re.sub(rf'^{key} = .*$', line, block, count=1, flags=re.MULTILINE)
    return re.sub(r'^(name = .*)$', rf'\1\n{line}', block, count=1,
                  flags=re.MULTILINE)


def main():
    text = SRC.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    terrain = data["terrain"]
    west, north = terrain["west"], terrain["north"]
    step_lon, step_lat = terrain["step_lon"], terrain["step_lat"]
    places = {p["id"]: p for p in data["places"]}

    for child, (parent, _) in DEMOTIONS.items():
        if child not in places:
            raise SystemExit(f"{child}: no such place")
        if parent not in places or places[parent].get("kind") != "alu":
            raise SystemExit(f"{child}: {parent} is not an Alu")

    # ── 1. Move the misplaced ────────────────────────────────────────────
    for pid, (lon, lat) in MOVES.items():
        col = int(round((lon - west) / step_lon))
        row = int(round((north - lat) / step_lat))
        if not (0 <= col < len(terrain["rows"][0])
                and 0 <= row < len(terrain["rows"])):
            raise SystemExit(f"{pid}: {lon},{lat} is off the map")
        match = block_of(text, "places", "id", pid)
        block = re.sub(r'^col = \d+$', f"col = {col}", match.group(0),
                       count=1, flags=re.MULTILINE)
        block = re.sub(r'^row = \d+.*$', f"row = {row}    "
                       f"# {lat:.2f}N {lon:.2f}E", block, count=1,
                       flags=re.MULTILINE)
        text = text[:match.start()] + block + text[match.end():]
    print(f"Moved: {len(MOVES)} places")

    # ── 2. Demote, and fold the people into the owner ────────────────────
    gained: dict[str, int] = {}
    for child, (parent, why) in DEMOTIONS.items():
        gained[parent] = gained.get(parent, 0) + places[child]["population"]
        match = block_of(text, "places", "id", child)
        block = match.group(0)
        block = set_key(block, "population", "population = 0")
        block = set_key(block, "rank", 'rank = "centre"')
        block = set_key(block, "kind", 'kind = "palace_centre"')
        block = set_key(block, "alu", f'alu = "{parent}"')
        block = set_key(block, "role", f'role = "{why}"')
        text = text[:match.start()] + block + text[match.end():]

    for parent, people in gained.items():
        match = block_of(text, "places", "id", parent)
        total = places[parent]["population"] + people
        block = re.sub(r'^population = \d+$', f"population = {total}",
                       match.group(0), count=1, flags=re.MULTILINE)
        text = text[:match.start()] + block + text[match.end():]
    print(f"Demoted: {len(DEMOTIONS)} places; "
          f"{sum(gained.values()):,} people folded into {len(gained)} Alu")

    # ── 3. Reparent ──────────────────────────────────────────────────────
    for child, parent in REPARENT.items():
        match = block_of(text, "places", "id", child)
        block = set_key(match.group(0), "alu", f'alu = "{parent}"')
        text = text[:match.start()] + block + text[match.end():]

    # ── 4. Drop the duplicated and the invented marks ────────────────────
    dropped = 0
    for alu, name in sorted(DROP_SITES):
        pattern = re.compile(r'^\[\[sites\]\]\n(?:(?!^\[).*\n?)*',
                             re.MULTILINE)
        for match in pattern.finditer(text):
            body = match.group(0)
            if (re.search(rf'^name = "{re.escape(name)}"$', body, re.MULTILINE)
                    and re.search(rf'^alu = "{alu}"$', body, re.MULTILINE)):
                text = text[:match.start()] + text[match.end():]
                dropped += 1
                break
        else:
            raise SystemExit(f"no site {name!r} under {alu}")
    print(f"Dropped: {dropped} palace-centre marks")

    # ── 5. Every mark of a demoted Alu now answers to its new owner ──────
    moved = 0
    for match in list(re.finditer(r'^\[\[sites\]\]\n(?:(?!^\[).*\n?)*',
                                  text, re.MULTILINE))[::-1]:
        body = match.group(0)
        owner = re.search(r'^alu = "(.*)"$', body, re.MULTILINE)
        if owner and owner.group(1) in DEMOTIONS:
            parent = DEMOTIONS[owner.group(1)][0]
            text = (text[:match.start()]
                    + body.replace(f'alu = "{owner.group(1)}"',
                                   f'alu = "{parent}"')
                    + text[match.end():])
            moved += 1
    print(f"Reassigned: {moved} marks to a new owner")

    SRC.write_text(text, encoding="utf-8")

    after = tomllib.loads(text)
    kinds = [p.get("kind") for p in after["places"]]
    print(f"Alu: {kinds.count('alu')}  palace centres: "
          f"{kinds.count('palace_centre')}")
    print(f"People: {sum(p['population'] for p in after['places']):,}")


if __name__ == "__main__":
    main()
