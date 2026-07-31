"""Rescale world.toml populations and add historical settlements.

Regional targets (from user):
  Egypt (nile): ~3M     Mesopotamia (lower+upper): ~2.25M
  Anatolia: ~1.75M      Aegean: ~1.25M             Levant: ~1.25M
"""

import sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/world.toml"

# ── New population for every existing alu ──
RESCALE = {
    # nile
    "egypt": 550000, "memphis": 400000, "waset": 500000,
    "khemenu": 180000, "abdju": 150000, "sau": 180000, "tjaru": 80000,
    # lower_mesopotamia
    "babylon": 400000, "dur_kurigalzu": 120000,
    # upper_mesopotamia
    "assur": 250000, "nineveh": 200000, "dur_katlimmu": 60000,
    "emar": 60000, "nuzi": 50000,
    # anatolia
    "hattusa": 400000, "kanesh": 200000, "tarhuntassa": 200000,
    "wilusa": 180000, "apasa": 130000, "tarsa": 100000, "mira": 90000,
    # aegean
    "mycenae": 200000, "knossos": 160000, "pylos": 130000,
    "thebes_gr": 110000, "athens": 90000, "kydonia": 55000,
    "iolcos": 55000, "millawanda": 45000,
    # levant
    "carchemish": 140000, "halab": 120000, "seat": 80000,
    "byblos": 80000, "amurru": 50000, "tyre": 60000, "sidon": 50000,
    "mukish": 30000, "gaza": 60000, "ashkelon": 50000, "lachish": 50000,
    "megiddo": 50000, "alashiya": 80000,
}

# ── New alu places ──
NEW = [
    # (id, region, name, pop, col, row, power, rank, glyph, role)
    # --- nile ---
    ("iunu", "nile", "Iunu", 200000, 129, 81, "egypt", "royal", "I",
     "Heliopolis: the sun-city whose priests are the most learned in the Two Lands"),
    ("djanet", "nile", "Djanet", 150000, 136, 74, "egypt", "royal", "T",
     "Tanis: the eastern Delta's anchorage, where the river meets the sea"),
    ("hut_herib", "nile", "Hut-herib", 120000, 127, 78, "egypt", "town", "H",
     "Athribis: grain levied off the central Delta for the king's granaries"),
    ("per_bastet", "nile", "Per-Bastet", 110000, 131, 77, "egypt", "royal", "B",
     "Bubastis: Bastet's temple town, and a market the whole Delta walks to"),
    ("per_medjed", "nile", "Per-Medjed", 100000, 121, 92, "egypt", "town", "O",
     "Oxyrhynchus: the fish-canal of the middle river, and its richest ground"),
    ("hut_nesut", "nile", "Hut-nesut", 100000, 122, 94, "egypt", "town", "N",
     "a walled town on the bend of the Nile, where the desert comes close"),
    ("abw", "nile", "Abw", 70000, 148, 125, "egypt", "town", "E",
     "Elephantine: the frontier of Egypt, and the gate of the Nubian trade"),
    # --- lower_mesopotamia ---
    ("nippur", "lower_mesopotamia", "Nippur", 150000, 303, 66, "karduniash", "royal", "N",
     "Enlil's seat: no king rules Mesopotamia without the assent of its temple"),
    ("uruk", "lower_mesopotamia", "Uruk", 200000, 308, 72, "karduniash", "royal", "U",
     "the oldest walled city, and still a weight in Sumer's reckoning"),
    ("ur", "lower_mesopotamia", "Ur", 120000, 314, 74, "karduniash", "royal", "R",
     "the moon-god's city, and the harbour that opens to the sea"),
    ("lagash", "lower_mesopotamia", "Lagash", 80000, 318, 71, "karduniash", "town", "G",
     "the canals of Lagash water the best barley in the south"),
    ("kish", "lower_mesopotamia", "Kish", 80000, 295, 63, "karduniash", "royal", "K",
     "the first dynasty, and the city that gave its name to the whole land"),
    ("isin", "lower_mesopotamia", "Isin", 60000, 304, 67, "karduniash", "town", "I",
     "a city of scribes and canals, between the two rivers"),
    ("larsa", "lower_mesopotamia", "Larsa", 60000, 311, 72, "karduniash", "town", "L",
     "the sun-god's southern seat, and the rival of every neighbour"),
    # --- upper_mesopotamia ---
    ("mari", "upper_mesopotamia", "Mari", 120000, 249, 48, "assyria", "royal", "M",
     "the Euphrates palace that commanded the river road until it fell"),
    ("harran", "upper_mesopotamia", "Harran", 100000, 225, 31, "assyria", "royal", "H",
     "the crossroads: every road from Anatolia to Mesopotamia passes here"),
    ("nagar", "upper_mesopotamia", "Nagar", 60000, 251, 32, "assyria", "town", "N",
     "Tell Brak: the oldest town of the Habur, and its granary"),
    ("shubat_enlil", "upper_mesopotamia", "Shubat-Enlil", 60000, 257, 30, "assyria", "town", "S",
     "Tell Leilan: the wheat plain of the Khabur, where empires are fed"),
    ("tabetu", "upper_mesopotamia", "Tabetu", 50000, 248, 42, "assyria", "town", "T",
     "the Habur river port, and the ferry to the eastern road"),
    # --- anatolia ---
    ("samuha", "anatolia", "Samuha", 130000, 191, 9, "hatti", "royal", "S",
     "the Hittite cult city on the upper Halys, where the king prays in war"),
    ("arinna", "anatolia", "Arinna", 110000, 173, 7, "hatti", "royal", "A",
     "the sun-goddess's own city, and the holiest ground in Hatti"),
    ("nerik", "anatolia", "Nerik", 90000, 181, 1, "hatti", "town", "N",
     "the storm-god's northern city, lost to the Kashka and prayed for yearly"),
    ("sapinuwa", "anatolia", "Sapinuwa", 80000, 184, 6, "hatti", "town", "S",
     "the Hittite palace town hidden in the mountains above Hattusa"),
    ("ankura", "anatolia", "Ankura", 70000, 148, 8, "hatti", "town", "A",
     "a Phrygian hill-fort on the road from the coast to the plateau"),
    ("lawazantiya", "anatolia", "Lawazantiya", 70000, 188, 21, "hatti", "town", "L",
     "the temple city of Cilicia, where the goddess of the rock is served"),
    # --- aegean ---
    ("tiryns", "aegean", "Tiryns", 80000, 23, 25, "ahhiyawa", "royal", "T",
     "the cyclopean fortress of the Argolid, and Mycenae's right arm"),
    ("argos", "aegean", "Argos", 70000, 24, 24, "ahhiyawa", "town", "A",
     "the plain that grows the men who man the Argolid's fleets"),
    ("orchomenos", "aegean", "Orchomenos", 70000, 26, 18, "ahhiyawa", "town", "O",
     "the Boeotian palace on the drained lake, rich in grain and horses"),
    ("sparta", "aegean", "Sparta", 55000, 18, 30, "ahhiyawa", "town", "S",
     "Lacedaemon: the Eurotas valley, and a warrior people not yet named"),
    ("korinthos", "aegean", "Korinthos", 60000, 28, 23, "ahhiyawa", "town", "C",
     "the isthmus that joins two seas, and the port that taxes both"),
    ("dimini", "aegean", "Dimini", 20000, 23, 11, "ahhiyawa", "town", "D",
     "a Mycenaean town on the gulf of Iolcos, growing wheat for the north"),
    ("lerna", "aegean", "Lerna", 25000, 22, 26, "ahhiyawa", "town", "L",
     "the spring of the Danaids, and a port the Argolid ships from"),
    # --- levant ---
    ("hazor", "north_levant", "Hazor", 60000, 180, 55, "egypt", "royal", "H",
     "the head of all those kingdoms: the richest Canaanite city, and the most watched"),
    ("jerusalem", "south_levant", "Jerusalem", 40000, 175, 70, "egypt", "town", "J",
     "a highland stronghold that owes Egypt a heavy tribute and pays it late"),
    ("damascus", "north_levant", "Damascus", 60000, 197, 46, "free", "royal", "D",
     "the oasis at the foot of the Anti-Lebanon, and the road north"),
    ("gezer", "south_levant", "Gezer", 40000, 173, 63, "egypt", "town", "G",
     "a Canaanite city on the coastal road, with a gate Pharaoh's men garrison"),
    ("shechem", "south_levant", "Shechem", 40000, 175, 59, "egypt", "town", "S",
     "the mountain pass between Ebal and Gerizim, and Labayu's old seat"),
    ("kadesh", "north_levant", "Kadesh", 50000, 197, 41, "hatti", "royal", "K",
     "the Orontes fortress: Egypt and Hatti have bled here, and will again"),
    ("akko", "north_levant", "Akko", 30000, 181, 59, "egypt", "town", "A",
     "the best harbour on the Levantine coast, and the gate of the Via Maris"),
    ("yafa", "south_levant", "Yafa", 30000, 172, 66, "egypt", "town", "Y",
     "Joppa: the port that brings Egyptian grain into Canaan"),
]


def main():
    text = SRC.read_text()

    # 1. Rescale existing alu populations
    pop_re = re.compile(
        r'^id = "(' + '|'.join(re.escape(k) for k in RESCALE) + r')"\n'
        r'(?:(?!^\[|^id = ).*\n)*?'
        r'^population = \d+',
        re.MULTILINE,
    )

    def replace_pop(m):
        block = m.group(0)
        pid = m.group(1)
        new_pop = RESCALE[pid]
        return re.sub(r'^population = \d+', f'population = {new_pop}', block)

    text = pop_re.sub(replace_pop, text)

    # 2. Promote Tiryns from palace_centre to alu
    old_tiryns = (
        '[[places]]\n'
        'id = "tiryns"\n'
        'region = "aegean"\n'
        'name = "Tiryns"\n'
        'population = 0\n'
        'col = 23\n'
        'row = 25    # 37.60N 22.80E\n'
        'power = "ahhiyawa"\n'
        'rank = "centre"\n'
        'kind = "palace_centre"\n'
        'alu = "mycenae"\n'
        'glyph = "T"\n'
        'role = "cyclopean walls, and the Argolid\'s own shore"\n'
    )
    new_tiryns = (
        '[[places]]\n'
        'id = "tiryns"\n'
        'region = "aegean"\n'
        'name = "Tiryns"\n'
        'population = 80000\n'
        'col = 23\n'
        'row = 25    # 37.60N 22.80E\n'
        'power = "ahhiyawa"\n'
        'rank = "royal"\n'
        'kind = "alu"\n'
        'glyph = "T"\n'
        'role = "the cyclopean fortress of the Argolid, and Mycenae\'s right arm"\n'
    )
    if old_tiryns not in text:
        print("WARN: tiryns block not found as expected", file=sys.stderr)
    else:
        text = text.replace(old_tiryns, new_tiryns)

    # 3. Insert new places before [[routes]]
    routes_marker = "\n\n[[routes]]"
    new_block = "\n\n" + "\n\n".join(
        _place_toml(*p) for p in NEW
    )
    text = text.replace(routes_marker, new_block + "\n\n[[routes]]", 1)

    SRC.write_text(text)
    print("world.toml updated.")

    # Validate
    for pid, pop in RESCALE.items():
        if f'population = {pop}' not in text:
            print(f"  WARN: {pid} population={pop} not confirmed in output", file=sys.stderr)
    for p in NEW:
        if f'id = "{p[0]}"' not in text:
            print(f"  WARN: new place {p[0]} not found in output", file=sys.stderr)
    print("Validation done.")


def _place_toml(pid, region, name, pop, col, row, power, rank, glyph, role):
    return (
        f'[[places]]\n'
        f'id = "{pid}"\n'
        f'region = "{region}"\n'
        f'name = "{name}"\n'
        f'population = {pop}\n'
        f'col = {col}\n'
        f'row = {row}\n'
        f'power = "{power}"\n'
        f'rank = "{rank}"\n'
        f'kind = "alu"\n'
        f'glyph = "{glyph}"\n'
        f'role = "{role}"'
    )


if __name__ == "__main__":
    main()
