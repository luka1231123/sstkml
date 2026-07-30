# Alu classification — design pass for Alpha 0.7 Task 1

- Status: implemented; see §12 for what the build changed about the design
- Revision: 2026-07-30
- Covers: `BASE_GAME_SPEC_DRAFT.md` §2.4, §8.2, §8.3, Task 1
- Input data: `content/scenarios/ugarit.toml` (37 places, 146 site marks, 56 routes)

Task 1 asks for one documented classification and one owning Alu for every map
mark, a map that renders from that classification, and no decorative site
silently treated as an autonomous settlement. This document is that
classification. It changes authored data, three small render tables, and the
loader; it does not move any authority between `World` and `Kernel` — that is
Task 2.

---

## 1. Vocabulary

Three verdicts, and every mark on the map takes exactly one.

**Alu** — a major city or regional centre with its hinterland. Has a king
(§8.2), a Seat, cohorts, and its own decisions. Full settlement-level entity.

**Dependent palace centre** — a located, owned subordinate centre. No king, no
autonomous simulation (§8.3). It is a real object because rules need one: it
can be raided, garrisoned, stripped, or lost without the Seat falling, and it
is where corvée detachments and stores sit outside the walls.

**Capacity** — not an object. Folds into the owning Alu's numbers: food and
extent for grain ground, production for a metal or timber or horse source. The
mark stays on the map as detail; it names no settlement and runs no simulation.

Alu are the only entities that gain population, decisions, or a king.

---

## 2. Data shape

Classification is carried in the authored scenario, one explicit field per
mark, resolved through authored ids and never inferred from a string.

### 2.1 `[[places]]`

Two new keys:

```toml
kind = "alu"            # "alu" | "palace_centre"
alu  = ""               # owning Alu id; required when kind = "palace_centre"
```

An `alu` place keeps `rank` (`seat`/`imperial`/`royal`/`town`) — that is the
map bracket and the standing line, and it stays authored. A `palace_centre`
place takes `rank = "centre"`, keeps its name, glyph, and coordinates, and
carries `population = 0` because its people are folded into its owner (§6).

### 2.2 `[[sites]]`

`hub` is renamed to `alu` — §2.4 of the spec names `hub` as legacy vocabulary,
and the rename is three call sites plus tests. Two new keys:

```toml
role     = "capacity"   # "palace_centre" | "capacity"
capacity = "food"       # only when role = "capacity": food|copper|tin|silver|gold|cedar|horses|lapis
```

### 2.3 Code touched

| File | Change |
|---|---|
| `load.py:86-121` | read `kind`/`alu` on places, `role`/`capacity`/`alu` on sites; reject a `palace_centre` whose `alu` is unknown, and any site whose `alu` is unknown |
| `engine/state.py:398` `Place` | add `kind: str = "alu"`, `alu: PlaceId = ""` |
| `engine/state.py:523` `Site` | rename `hub` → `alu`; add `role: str`, `capacity: str = ""` |
| `belief/project.py:734-791` | project the new fields; sites emit `alu`/`role`/`capacity` |
| `tui/atlas.py:59` `BRACKET` | add `"centre": ("", "")` |
| `tui/worldmap.py:54` `RANK_WORD` | add `"centre"`; the standing line reads "a palace centre of {owner name}" |
| `tui/worldmap.py:723-726` | hinterland count reads `site["alu"]`, and counts palace centres and capacities apart |

Validation is the point of the loader change: after Task 1 it is impossible to
author a mark with no classification or an owner that does not exist. That is
the mechanical half of "no decorative site is silently treated as an autonomous
settlement".

---

## 3. Table A — the 37 existing places

32 stay Alu. 5 are demoted to dependent palace centres. Nothing is deleted, no
coordinate moves.

### 3.1 Demoted to dependent palace centre

| Place | Pop | Owning Alu | Why |
|---|---|---|---|
| `ma_hadu` (Ma'hadu) | 2500 | `seat` (Ugarit) | Ugarit's own harbour, 4 km from the Seat. §8.3 makes the harbour a capacity of the Alu, not a second settlement. Also the kernel conflict in §9. |
| `gibala` (Gib'ala) | 1200 | `seat` (Ugarit) | Border town inside the kingdom of Ugarit, no king of its own. |
| `gla` (Gla) | 2000 | `thebes_gr` (Thebes) | Boeotian fortress of the Theban polity, no dynasty. |
| `tiryns` (Tiryns) | 5000 | `mycenae` (Mycenae) | Argolid citadel subordinate to Mycenae. The largest demotion, and the one most open to revision — see §11. |
| `ura` (Ura) | 3000 | `tarhuntassa` (Tarhuntassa) | The Hittite grain landing in Cilicia. Its merchants are famous; its politics are Hittite. |

### 3.2 The 32 Alu

Every remaining place is an Alu, with its authored king (Task 4 gives that king
a record). Listed with the classification-relevant fields only.

| Alu | Rank | Power | Pop |
|---|---|---|---|
| `seat` Ugarit | seat | hatti | 11700 (folded) |
| `egypt` Pi-Ramesses | imperial | egypt | 25000 |
| `hattusa` Hattusa | imperial | hatti | 12000 |
| `babylon` Babylon | imperial | karduniash | 20000 |
| `assur` Assur | imperial | assyria | 9000 |
| `waset` Waset | royal | egypt | 40000 |
| `memphis` Memphis | royal | egypt | 30000 |
| `mycenae` Mycenae | royal | ahhiyawa | 15000 (folded) |
| `halab` Halab | royal | hatti | 9000 |
| `thebes_gr` Thebes | royal | ahhiyawa | 9000 (folded) |
| `tarhuntassa` Tarhuntassa | royal | hatti | 9000 (folded) |
| `carchemish` Carchemish | royal | hatti | 8000 |
| `knossos` Knossos | royal | ahhiyawa | 8000 |
| `pylos` Pylos | royal | ahhiyawa | 6000 |
| `alashiya` Alashiya | royal | free | 6000 |
| `byblos` Gubla | royal | egypt | 5000 |
| `apasa` Apasa | royal | free | 5000 |
| `athens` Athens | royal | ahhiyawa | 4000 |
| `wilusa` Wilusa | royal | hatti | 4000 |
| `iolcos` Iolcos | royal | ahhiyawa | 3000 |
| `mukish` Alalakh | royal | hatti | 3000 |
| `ashkelon` Ashkelon | town | egypt | 4000 |
| `kydonia` Kydonia | town | ahhiyawa | 4000 |
| `amurru` Sumur | town | hatti | 4000 |
| `mira` Mira | town | hatti | 4000 |
| `lachish` Lachish | town | egypt | 3500 |
| `gaza` Gaza | town | egypt | 3000 |
| `megiddo` Megiddo | town | egypt | 3000 |
| `tyre` Tyre | town | egypt | 3000 |
| `sidon` Sidon | town | egypt | 3000 |
| `emar` Emar | town | hatti | 3000 |
| `millawanda` Millawanda | town | ahhiyawa | 3000 |

The Canaanite towns (Gaza, Ashkelon, Lachish, Megiddo, Tyre, Sidon) stay Alu
despite Egyptian garrisons: each has its own king in the correspondence, which
is exactly the §8.2 model — a king under an overlord, not a place without one.

---

## 4. Table B — the 146 site marks

The authored marks are formulaic, not per-city: a place gets 2 palace + 3 grain
if it is large, 1 palace + 2 grain if it is a town, plus a resource mark where
the region has one. So classification is by rule, not case by case.

**Rule 1** — every `palace` mark is a **dependent palace centre** of its Alu.
51 marks. Unnamed, as authored; the map already draws them without names. The
Seat itself is the place mark, never a site mark.

**Rule 2** — every `grain` mark is a **capacity** (`capacity = "food"`) of its
Alu: hinterland extent and food-producing ground. 83 marks. Not a farm object,
not a village.

**Rule 3** — every resource mark is a **capacity** named by its good. 12 marks:

| Good | Owning Alu |
|---|---|
| copper ×2 | `alashiya` |
| tin | `assur`, `emar` |
| silver | `athens`, `mira` |
| cedar | `byblos`, `tarhuntassa` |
| horses | `hattusa`, `wilusa` |
| gold | `waset` |
| lapis | `babylon` |

**Rule 4** — the 15 marks that hung off the five demoted places re-point to the
owning Alu. Ugarit gains Ma'hadu's and Gib'ala's 6 marks, Thebes gains Gla's 3,
Mycenae gains Tiryns's 3, Tarhuntassa gains Ura's 3.

After re-pointing, the existing 146 marks distribute as:

| Alu | palace | grain | other |
|---|---|---|---|
| `seat` | 4 | 7 | — |
| `tarhuntassa` | 3 | 4 | cedar |
| `mycenae` | 3 | 5 | — |
| `thebes_gr` | 3 | 4 | — |
| `waset` | 2 | 3 | gold |
| `hattusa` | 2 | 3 | horses |
| `alashiya` | 2 | 2 | copper ×2 |
| `assur` | 2 | 3 | tin |
| `babylon` | 2 | 3 | lapis |
| `egypt`, `memphis`, `halab`, `carchemish`, `knossos` | 2 | 3 | — |
| `pylos` | 2 | 2 | — |
| `byblos`, `emar`, `mira`, `wilusa`, `athens` | 1 | 2 | one resource each |
| `gaza`, `ashkelon`, `lachish`, `megiddo`, `tyre`, `sidon`, `amurru`, `apasa`, `millawanda`, `iolcos`, `kydonia` | 1 | 2 | — |

Total 146, every mark owned, nothing promoted.

**Additionally**, `ma_hadu` becomes Ugarit's **harbour** capacity as well as a
palace centre — Ugarit is a coastal Alu (§8.3) and Ma'hadu is where that is
true. Same for `ura` and Tarhuntassa.

---

## 5. Table C — new Alu

The map is thin east of the Euphrates, in central Anatolia, and up the Nile.
Ten additions, all inside the authored terrain grid (300 × 119 cells; col =
`(lon − 21.00) / 0.08`, row = `(41.00 − lat) / 0.135`), all on non-sea ground,
none within 4 cells of an existing mark. Total after Task 1: **42 Alu**.

### 5.1 Mesopotamia (4)

| id | Name | col,row | lat/lon | Rank | Power | Pop | Glyph |
|---|---|---|---|---|---|---|---|
| `nineveh` | Ninua | 277,34 | 36.36N 43.15E | royal | assyria | 7000 | N |
| `dur_kurigalzu` | Dur-Kurigalzu | 290,57 | 33.35N 44.20E | royal | karduniash | 8000 | K |
| `dur_katlimmu` | Dur-Katlimmu | 247,40 | 35.65N 40.75E | town | assyria | 3000 | D |
| `nuzi` | Nuzi | 291,42 | 35.38N 44.30E | town | assyria | 2500 | n |

Roles, in the voice of the existing entries:

- `nineveh` — "Ishtar's own city, and where the northern road turns west"
- `dur_kurigalzu` — "the Kassite king's new foundation, and hungry as new
  cities are"
- `dur_katlimmu` — "the Assyrian hand on the Habur, counting the western road"
- `nuzi` — "eastern ground, and tablets full of other men's debts"

`sippar` is deliberately **not** an Alu: it becomes a named dependent palace
centre of Babylon (33.06N 44.24E → col 290, row 59), which is what the category
is for.

### 5.2 Anatolia (2)

| id | Name | col,row | lat/lon | Rank | Power | Pop | Glyph |
|---|---|---|---|---|---|---|---|
| `tarsa` | Tarsa | 174,30 | 36.92N 34.90E | town | hatti | 4000 | R |
| `kanesh` | Kanesh | 183,16 | 38.85N 35.63E | town | hatti | 3500 | k |

- `tarsa` — "the Cilician gate, where Hatti's grain comes ashore"
- `kanesh` — "old Nesa, whose tongue the kings still write in"

Kanesh carries a `silver` capacity — the third silver source on the map, and
the only one in the Anatolian interior.

### 5.3 Egypt (4)

| id | Name | col,row | lat/lon | Rank | Power | Pop | Glyph |
|---|---|---|---|---|---|---|---|
| `khemenu` | Khemenu | 122,98 | 27.78N 30.80E | royal | egypt | 6000 | X |
| `abdju` | Abdju | 137,110 | 26.18N 31.92E | royal | egypt | 5000 | O |
| `sau` | Sau | 122,74 | 30.97N 30.77E | royal | egypt | 5000 | S |
| `tjaru` | Tjaru | 142,75 | 30.89N 32.36E | town | egypt | 3000 | J |

- `khemenu` — "Thoth's city, and the granary of the middle river"
- `abdju` — "Osiris' burial ground, and a cult the whole land pays for"
- `sau` — "Neith's city in the western Delta, with the Libyan wind at its back"
- `tjaru` — "the fortress gate of the Ways of Horus, where Asia begins"

Glyph letters repeat across the map already (`M` ×5, `A` ×5 as authored), so
the new letters are chosen for legibility, not uniqueness.

---

### 5.4 Site marks for the new Alu

41 new marks, authored on the same formula the existing map uses: royal rank
takes 2 palace centres and 3 food capacities, town rank takes 1 and 2. Every
coordinate is non-sea ground, 2–4 cells from its Alu, at least 2 cells from any
other mark. `sippar` is a named palace centre of Babylon, not a site mark.

| Alu | Dependent palace centres | Food capacities | Other |
|---|---|---|---|
| `nineveh` | (277,32) (279,34) | (277,36) (275,34) (279,32) | — |
| `dur_kurigalzu` | (290,55) (292,57) | (292,59) (288,57) (292,55) | — |
| `dur_katlimmu` | (247,38) | (249,40) (247,42) | — |
| `nuzi` | (291,40) | (293,42) (291,44) | — |
| `tarsa` | (174,28) | (176,30) (172,30) | — |
| `kanesh` | (183,14) | (185,16) (183,18) | silver (181,16) |
| `khemenu` | (122,96) (124,98) | (122,100) (124,96) (124,100) | — |
| `abdju` | (137,108) (139,110) | (139,108) (135,108) (141,110) | — |
| `sau` | (122,72) (124,74) | (122,76) (120,74) (124,72) | — |
| `tjaru` | (142,73) | (144,75) (142,77) | — |

Sippar's own cell (290,59) is taken out of Dur-Kurigalzu's food capacities,
which move to (292,59); no two marks in the world then share a cell.

Map totals after Task 1:

- **48 place records** — 42 Alu, plus 6 named dependent palace centres
  (Ma'hadu, Gib'ala, Gla, Tiryns, Ura, Sippar).
- **187 site marks** — 66 unnamed dependent palace centres (51 authored + 15
  new), 121 capacities (108 food, 13 resource).

Every one of the 235 marks has a verdict and an owning Alu.

---

## 6. Population

Demotion folds people into the owner. No population is invented or lost.

| Alu | Was | Folds in | Becomes |
|---|---|---|---|
| `seat` Ugarit | 8000 | Ma'hadu 2500, Gib'ala 1200 | 11700 |
| `mycenae` | 10000 | Tiryns 5000 | 15000 |
| `thebes_gr` | 7000 | Gla 2000 | 9000 |
| `tarhuntassa` | 6000 | Ura 3000 | 9000 |

Demoted places take `population = 0`.

**This moves plague numbers.** `Place.susceptible` is seeded from `population`
(`load.py:88-99`, `state.py:425-429`), so folding changes the SIR compartments
of four places and removes four separate compartments. Two consequences to pin
in tests: the region's total susceptible population is unchanged, and an
epidemic seeded at Ugarit now runs over 11700 rather than 8000. Cohorts become
the authoritative population in Task 6; until then `population` remains the
seed and this is the honest arithmetic for it.

---

## 7. Power vocabulary

`power` is the overlord label the map draws (`atlas.POWER_TONE`,
`worldmap.POWER_WORD`), and `free` currently reads "under no overlord". That is
right for Alashiya and Apasa, and wrong for four Assyrian and Kassite cities.
Two values added:

| Value | Word | Tone | Places |
|---|---|---|---|
| `assyria` | "under Assyria" | `wine` | `assur`, `nineveh`, `dur_katlimmu`, `nuzi` |
| `karduniash` | "under Babylon" | `sand` | `babylon`, `dur_kurigalzu` |

`assur` and `babylon` move off `free`, following the existing convention where
a capital carries its own power (`hattusa` is `hatti`, `egypt` is `egypt`).

Both tones already exist in `content/palette.toml`, and no colour is added: the
four authored powers hold `gold`, `flame`, `lapis`, and `verdigris`, and `wine`
is used by no map table at all. `sand` is also the dry-ground tone, which is
drawn faint behind the marks, so a lettered mark in brackets still reads apart
from it.

This is a map label only. Overlordship as an obligation between two kings is
Task 4, and this document deliberately does not encode `power` as ownership.

---

## 8. Routes for the new Alu

Nothing unreachable. Legs and risk follow the conventions the authored table
already obeys — `risk = 40 + km/3` by land, `40 + km/6` by sea and river; about
98 km per land leg, about 170 km per sea or river leg — with a 1.25 detour
factor on straight-line land distance.

```toml
# Assyria and Karduniash
assur–nineveh            legs=1 land  risk=82    # 126 km
assur–nuzi               legs=1 land  risk=79    # 118 km
nineveh–nuzi             legs=2 land  risk=103   # 188 km
nineveh–dur_katlimmu     legs=3 land  risk=136   # 287 km
dur_katlimmu–assur       legs=3 land  risk=135   # 285 km
dur_katlimmu–emar        legs=3 land  risk=143   # 308 km
babylon–dur_kurigalzu    legs=1 land  risk=78    # 115 km
dur_kurigalzu–nuzi       legs=3 land  risk=134   # 282 km

# Anatolia
tarsa–ura                legs=1 land  risk=85    # 134 km
tarsa–tarhuntassa        legs=1 land  risk=88    # 145 km
tarsa–kanesh             legs=3 land  risk=133   # 280 km
tarsa–carchemish         legs=4 land  risk=156   # 347 km
tarsa–alashiya           legs=1 sea   risk=82    # 253 km, seasonal
kanesh–hattusa           legs=2 land  risk=105   # 195 km

# Egypt
egypt–tjaru              legs=1 land  risk=61    # 64 km
tjaru–gaza               legs=3 land  risk=128   # 263 km
sau–egypt                legs=1 land  risk=83    # 129 km
sau–memphis              legs=1 river risk=62    # 133 km
memphis–khemenu          legs=1 river risk=79    # 234 km
khemenu–abdju            legs=1 river risk=75    # 210 km
abdju–waset              legs=1 river risk=55    # 90 km
```

`ma_hadu–seat` (4 km) survives as a route to a palace centre — the loader must
accept a route endpoint that is not an Alu, or the leg is dropped and Ugarit
loses its harbour connection. Existing `egypt–gaza` stays alongside the new
Ways of Horus pair; a caravan may take either.

New route count: 22, giving 78 total.

---

## 9. Kernel reconciliation

The kernel's four settlements map onto the Alu model like this:

| Kernel entity | Verdict |
|---|---|
| `settlement:ugarit` | Alu `seat` |
| `settlement:mahadu` | dependent palace centre + harbour capacity of `seat` |
| `settlement:ari` | hinterland capacity of `seat` (a village, no palace) |
| `settlement:alashiya_port` | harbour capacity of Alu `alashiya` |

**This contradicts the M13.1 exit gate.** `content/kernel/world.toml:129` gives
Ma'hadu `autonomous` (default true), and the gate is that Ma'hadu and the
Alashiyan port go on producing, consuming, and deciding when Ugarit is idle or
removed. §8.3 forbids autonomous simulation for a dependent palace centre.
Ten test files reference `mahadu`.

Per §9 of the spec the contradiction is resolved before code is added.
Resolution: **autonomy moves from the settlement to the Alu.** Ma'hadu, Ari,
and the Alashiyan port stop being autonomous deciders; Alashiya, Alalakh,
Amurru, and Carchemish — real Alu with real kings — become them. The gate's
intent (the world does not stop when the player stops) is preserved and
strengthened: it is then demonstrated by other kings' cities rather than by
Ugarit's own port deciding against Ugarit.

That kernel edit is Task 2's work. Task 1 owns only the classification it
implies, recorded here.

---

## 10. What Task 1 delivers, checked against the spec

| Completion criterion | Delivered by |
|---|---|
| every map mark has one documented classification | §3 (places), §4 (marks), §5 (new places), enforced by the loader in §2.3 |
| and one owning Alu | `alu` on every `palace_centre` place and every site |
| the map renders from that classification | `BRACKET`/`RANK_WORD`/hinterland-count changes in §2.3; palace centres and capacities draw and read apart |
| no decorative site silently treated as an autonomous settlement | no mark is promoted; the loader rejects an unclassified or unowned mark; §9 removes the two kernel settlements that were the real instance of this |

Tests, causal rather than smoke, in `tests/test_alu_classification.py`:

1. `test_every_mark_has_a_classification_and_an_owning_alu` — 42 Alu, 6 palace
   centres, 187 marks, every `alu` reference resolving to a place with
   `kind = "alu"`.
2. `test_an_unowned_or_unclassified_mark_is_a_load_error` — the fault the
   classification exists to prevent, driven through the real loader on an
   edited copy of the scenario.
3. `test_demoted_towns_keep_their_people_and_are_counted_once` — palace centres
   hold nobody, the four owners hold exactly the folded sums, and the living
   population equals the authored population with nothing double-counted.
4. `test_ugarit_still_reaches_the_sea_through_its_own_harbour` — Ma'hadu is
   `seat`'s harbour, and a route may still end at a palace centre.
5. `test_the_authored_import_sickens_the_alu_that_holds_the_harbour` — the
   tablet still says Ma'hadu, the sickness begins at Ugarit, and it runs on
   11700 people.
6. `test_every_alu_is_reachable_from_the_seat` — no Alu a courier cannot reach.
7. `test_the_tablet_draws_holdings_as_holdings` — no `hub` survives in Belief,
   `seat` counts 4 palace centres and 7 grain estates, its named centres are
   listed, and a selected palace centre says whose it is instead of claiming a
   rank.

---

## 11. As built

Four things the implementation settled that the design left open or wrong.

**The authored plague import.** `[plague] import_place = "ma_hadu"` seeded a
compartment on a place that no longer has one, so the disease simply never
began. The scenario still names Ma'hadu — travellers do land at the harbour —
and `load.py` resolves the seeding to the Alu that holds it. A palace centre
never carries SIR compartments; the people the travellers land among are
Ugarit's. `tests/test_m13_material_causality.py` pinned Ma'hadu as a second
infectable settlement one leg from the seat, and now uses Alalakh (`mukish`),
which is an Alu, one land leg away, and open all year.

**`Place.harbour`.** A boolean on the palace-centre record, because Task 1 has
to be able to answer "is this Alu coastal" without inventing the harbour system
that §8.3 gives to Task 5. Ma'hadu and Ura carry it.

**The standing line does not mention the harbour.** "a palace centre of Ugarit,
and its harbour" runs past the panel width and is cut mid-word; the authored
`role` line already says what Ma'hadu is. The line reads "a palace centre of
Ugarit" and stops.

**`SITE_WORD["palace"]`** changed from "small palaces" to "palace centres", so
the map's words and the data's words are the same word.

The authority audit's missing-mapping finding moved from 36 legacy places to 47
— the new Alu are real places with no kernel settlement behind them. That number
is Task 2's to drive to zero, and it is now honest about the whole map rather
than about part of it.

---

## 12. Open, and deliberately not decided here

- **Tiryns.** Demoted to a palace centre of Mycenae. It is the one demotion
  with a live argument for its own wanax, and if it becomes an Alu again the
  count moves to 43 with no other change.
- **Naming the 51 palace centres.** They are unnamed, as authored. Where
  history supplies a name (Sippar under Babylon, Ma'hadu under Ugarit) it is
  used; the rest can be named later without touching this classification.
- **`power` as a taxonomy.** Two values added for honesty on the map. The real
  model of overlordship is king-to-king in Task 4, and `power` should die there.
- **Kernel `Site.function` vocabulary.** `estate`/`harbour`/`mine` versus this
  document's `capacity` names. They must be reconciled when the kernel becomes
  the one authority; §4's `capacity` values are chosen to map onto them
  one-to-one.
