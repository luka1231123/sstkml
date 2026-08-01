# Alu classification — design pass for Alpha 0.7 Task 1

- Status: **Done and dusted.** Task 1 is implemented; this file is now the
  record of the verdicts, not a plan. §12 holds what the build changed about
  the design. Adds no requirement to `SPEC.md`.
- Revision: 2026-07-30
- Covers: `SPEC.md` §2.4, §8.2, §8.3, Task 1
- Input data: `content/scenarios/ugarit.toml` (37 places, 146 site marks, 56 routes)

Task 1 want: one documented classification + one owning Alu per map mark, map render from classification, no decorative site silently treated as autonomous settlement. This doc = that classification. Change authored data, three small render tables, loader. Move no authority between `World` and `Kernel` — that Task 2.

---

## 1. Vocabulary

Three verdicts. Every mark take exactly one.

**Alu** — major city or regional centre with hinterland. Has king (§8.2), Seat, cohorts, own decisions. Full settlement-level entity.

**Dependent palace centre** — located, owned subordinate centre. No king, no autonomous simulation (§8.3). Real object because rules need one: raid, garrison, strip, lose it without Seat falling. Where corvée detachments and stores sit outside walls.

**Capacity** — not object. Fold into owning Alu numbers: food + extent for grain ground, production for metal/timber/horse source. Mark stay on map as detail. Names no settlement, runs no simulation.

Alu only entities that gain population, decisions, king.

---

## 2. Data shape

Classification carried in authored scenario. One explicit field per mark, resolved through authored ids, never inferred from string.

### 2.1 `[[places]]`

Two new keys:

```toml
kind = "alu"            # "alu" | "palace_centre"
alu  = ""               # owning Alu id; required when kind = "palace_centre"
```

`alu` place keep `rank` (`seat`/`imperial`/`royal`/`town`) — that map bracket + standing line, stay authored. `palace_centre` place take `rank = "centre"`, keep name, glyph, coordinates, carry `population = 0` because people folded into owner (§6).

### 2.2 `[[sites]]`

`hub` renamed to `alu` — spec §2.4 name `hub` legacy vocabulary. Rename = three call sites plus tests. Two new keys:

```toml
role     = "capacity"   # "palace_centre" | "capacity"
capacity = "food"       # only when role = "capacity": food|copper|tin|silver|gold|cedar|horses|lapis
```

### 2.3 Code touched

| File | Change |
|---|---|
| `load.py:86-121` | read `kind`/`alu` on places, `role`/`capacity`/`alu` on sites; reject `palace_centre` whose `alu` unknown, and any site whose `alu` unknown |
| `engine/state.py:398` `Place` | add `kind: str = "alu"`, `alu: PlaceId = ""` |
| `engine/state.py:523` `Site` | rename `hub` → `alu`; add `role: str`, `capacity: str = ""` |
| `belief/project.py:734-791` | project new fields; sites emit `alu`/`role`/`capacity` |
| `tui/atlas.py:59` `BRACKET` | add `"centre": ("", "")` |
| `tui/worldmap.py:54` `RANK_WORD` | add `"centre"`; standing line read "a palace centre of {owner name}" |
| `tui/worldmap.py:723-726` | hinterland count read `site["alu"]`, count palace centres and capacities apart |

Validation = point of loader change: after Task 1, impossible to author mark with no classification or owner that not exist. That mechanical half of "no decorative site silently treated as autonomous settlement".

---

## 3. Table A — the 37 existing places

32 stay Alu. 5 demoted to dependent palace centres. Nothing deleted, no coordinate moves.

### 3.1 Demoted to dependent palace centre

| Place | Pop | Owning Alu | Why |
|---|---|---|---|
| `ma_hadu` (Ma'hadu) | 2500 | `seat` (Ugarit) | Ugarit own harbour, 4 km from Seat. §8.3 make harbour capacity of Alu, not second settlement. Also kernel conflict in §9. |
| `gibala` (Gib'ala) | 1200 | `seat` (Ugarit) | Border town inside kingdom of Ugarit, no own king. |
| `gla` (Gla) | 2000 | `thebes_gr` (Thebes) | Boeotian fortress of Theban polity, no dynasty. |
| `tiryns` (Tiryns) | 5000 | `mycenae` (Mycenae) | Argolid citadel subordinate to Mycenae. Largest demotion, most open to revision — see §11. |
| `ura` (Ura) | 3000 | `tarhuntassa` (Tarhuntassa) | Hittite grain landing in Cilicia. Merchants famous; politics Hittite. |

### 3.2 The 32 Alu

Every remaining place = Alu, with authored king (Task 4 give that king record). Listed with classification-relevant fields only.

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

Canaanite towns (Gaza, Ashkelon, Lachish, Megiddo, Tyre, Sidon) stay Alu despite Egyptian garrisons: each has own king in correspondence — exactly §8.2 model, king under overlord, not place without one.

---

## 4. Table B — the 146 site marks

Authored marks formulaic, not per-city: place get 2 palace + 3 grain if large, 1 palace + 2 grain if town, plus resource mark where region has one. So classification by rule, not case by case.

**Rule 1** — every `palace` mark = **dependent palace centre** of its Alu. 51 marks, all named. Seat itself = place mark, never site mark.

**Rule 2** — every `grain` mark = **capacity** (`capacity = "food"`) of its Alu: hinterland extent + food-producing ground. 83 marks. Not farm object, not village.

**Rule 3** — every resource mark = **capacity** named by its good. 12 marks:

| Good | Owning Alu |
|---|---|
| copper ×2 | `alashiya` |
| tin | `assur`, `emar` |
| silver | `athens`, `mira` |
| cedar | `byblos`, `tarhuntassa` |
| horses | `hattusa`, `wilusa` |
| gold | `waset` |
| lapis | `babylon` |

**Rule 4** — 15 marks that hung off five demoted places re-point to owning Alu. Ugarit gain Ma'hadu + Gib'ala 6 marks, Thebes gain Gla 3, Mycenae gain Tiryns 3, Tarhuntassa gain Ura 3.

After re-point, existing 146 marks distribute as:

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

**Additionally**, `ma_hadu` become Ugarit **harbour** capacity as well as palace centre — Ugarit coastal Alu (§8.3), Ma'hadu where that true. Same for `ura` and Tarhuntassa.

---

## 5. Table C — new Alu

Map thin east of Euphrates, central Anatolia, up the Nile. Ten additions, all inside authored terrain grid (300 × 119 cells; col = `(lon − 21.00) / 0.08`, row = `(41.00 − lat) / 0.135`), all non-sea ground, none within 4 cells of existing mark. Total after Task 1: **42 Alu**.

### 5.1 Mesopotamia (4)

| id | Name | col,row | lat/lon | Rank | Power | Pop | Glyph |
|---|---|---|---|---|---|---|---|
| `nineveh` | Ninua | 277,34 | 36.36N 43.15E | royal | assyria | 7000 | N |
| `dur_kurigalzu` | Dur-Kurigalzu | 290,57 | 33.35N 44.20E | royal | karduniash | 8000 | K |
| `dur_katlimmu` | Dur-Katlimmu | 247,40 | 35.65N 40.75E | town | assyria | 3000 | D |
| `nuzi` | Nuzi | 291,42 | 35.38N 44.30E | town | assyria | 2500 | n |

Roles, in voice of existing entries:

- `nineveh` — "Ishtar's own city, and where the northern road turns west"
- `dur_kurigalzu` — "the Kassite king's new foundation, and hungry as new
  cities are"
- `dur_katlimmu` — "the Assyrian hand on the Habur, counting the western road"
- `nuzi` — "eastern ground, and tablets full of other men's debts"

`sippar` deliberately **not** Alu: become named dependent palace centre of Babylon (33.06N 44.24E → col 290, row 59) — what category for.

### 5.2 Anatolia (2)

| id | Name | col,row | lat/lon | Rank | Power | Pop | Glyph |
|---|---|---|---|---|---|---|---|
| `tarsa` | Tarsa | 174,30 | 36.92N 34.90E | town | hatti | 4000 | R |
| `kanesh` | Kanesh | 183,16 | 38.85N 35.63E | town | hatti | 3500 | k |

- `tarsa` — "the Cilician gate, where Hatti's grain comes ashore"
- `kanesh` — "old Nesa, whose tongue the kings still write in"

Kanesh carry `silver` capacity — third silver source on map, only one in Anatolian interior.

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

Glyph letters repeat across map already (`M` ×5, `A` ×5 as authored), so new letters chosen for legibility, not uniqueness.

---

### 5.4 Site marks for the new Alu

41 new marks, authored on same formula existing map uses: royal rank take 2 palace centres + 3 food capacities, town rank take 1 and 2. Every coordinate non-sea ground, 2–4 cells from its Alu, at least 2 cells from any other mark. `sippar` = named palace centre of Babylon, not site mark.

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

Sippar own cell (290,59) taken out of Dur-Kurigalzu food capacities, which move to (292,59); no two marks in world then share cell.

Map totals after Task 1:

- **48 place records** — 42 Alu, plus 6 named dependent palace centres
  (Ma'hadu, Gib'ala, Gla, Tiryns, Ura, Sippar).
- **187 site marks** — 66 named dependent palace centres (51 authored + 15
  new), 121 capacities (108 food, 13 resource).

Every one of 235 marks has verdict + owning Alu.

---

## 6. Population

Demotion fold people into owner. No population invented or lost.

| Alu | Was | Folds in | Becomes |
|---|---|---|---|
| `seat` Ugarit | 8000 | Ma'hadu 2500, Gib'ala 1200 | 11700 |
| `mycenae` | 10000 | Tiryns 5000 | 15000 |
| `thebes_gr` | 7000 | Gla 2000 | 9000 |
| `tarhuntassa` | 6000 | Ura 3000 | 9000 |

Demoted places take `population = 0`.

**This move plague numbers.** `Place.susceptible` seeded from `population` (`load.py:88-99`, `state.py:425-429`), so folding change SIR compartments of four places, remove four separate compartments. Two consequences to pin in tests: region total susceptible population unchanged, and epidemic seeded at Ugarit now run over 11700 not 8000. Cohorts become authoritative population in Task 6; until then `population` stay seed and this honest arithmetic for it.

---

## 7. Power vocabulary

`power` = overlord label map draw (`atlas.POWER_TONE`, `worldmap.POWER_WORD`), and `free` currently read "under no overlord". Right for Alashiya and Apasa, wrong for four Assyrian and Kassite cities. Two values added:

| Value | Word | Tone | Places |
|---|---|---|---|
| `assyria` | "under Assyria" | `wine` | `assur`, `nineveh`, `dur_katlimmu`, `nuzi` |
| `karduniash` | "under Babylon" | `sand` | `babylon`, `dur_kurigalzu` |

`assur` and `babylon` move off `free`, following existing convention where capital carry own power (`hattusa` is `hatti`, `egypt` is `egypt`).

Both tones already exist in `content/palette.toml`, no colour added: four authored powers hold `gold`, `flame`, `lapis`, `verdigris`, and `wine` used by no map table at all. `sand` also dry-ground tone, drawn faint behind marks, so lettered mark in brackets still read apart from it.

Map label only. Overlordship as obligation between two kings = Task 4. This doc deliberately not encode `power` as ownership.

---

## 8. Routes for the new Alu

Nothing unreachable. Legs + risk follow conventions authored table already obey — `risk = 40 + km/3` by land, `40 + km/6` by sea and river; about 98 km per land leg, about 170 km per sea or river leg — with 1.25 detour factor on straight-line land distance.

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

`ma_hadu–seat` (4 km) survive as route to palace centre — loader must accept route endpoint that not Alu, else leg dropped and Ugarit lose harbour connection. Existing `egypt–gaza` stay alongside new Ways of Horus pair; caravan may take either.

New route count: 22, giving 78 total.

---

## 9. Kernel reconciliation

Kernel four settlements map onto Alu model like this:

| Kernel entity | Verdict |
|---|---|
| `settlement:ugarit` | Alu `seat` |
| `settlement:mahadu` | dependent palace centre + harbour capacity of `seat` |
| `settlement:ari` | hinterland capacity of `seat` (village, no palace) |
| `settlement:alashiya_port` | harbour capacity of Alu `alashiya` |

**This contradict M13.1 exit gate.** `content/kernel/world.toml:129` give Ma'hadu `autonomous` (default true), and gate = Ma'hadu + Alashiyan port go on producing, consuming, deciding when Ugarit idle or removed. §8.3 forbid autonomous simulation for dependent palace centre. Ten test files reference `mahadu`.

Per spec §9, contradiction resolved before code added. Resolution: **autonomy move from settlement to Alu.** Ma'hadu, Ari, Alashiyan port stop being autonomous deciders; Alashiya, Alalakh, Amurru, Carchemish — real Alu with real kings — become them. Gate intent (world not stop when player stop) preserved and strengthened: then demonstrated by other kings' cities rather than Ugarit own port deciding against Ugarit.

That kernel edit = Task 2 work. Task 1 own only classification it implies, recorded here.

---

## 10. What Task 1 delivers, checked against the spec

| Completion criterion | Delivered by |
|---|---|
| every map mark has one documented classification | §3 (places), §4 (marks), §5 (new places), enforced by loader in §2.3 |
| and one owning Alu | `alu` on every `palace_centre` place and every site |
| the map renders from that classification | `BRACKET`/`RANK_WORD`/hinterland-count changes in §2.3; palace centres and capacities draw and read apart |
| no decorative site silently treated as an autonomous settlement | no mark promoted; loader reject unclassified or unowned mark; §9 remove two kernel settlements that were real instance of this |

Tests, causal not smoke, in `tests/test_alu_classification.py`:

1. `test_every_mark_has_a_classification_and_an_owning_alu` — 42 Alu, 6 palace
   centres, 187 marks, every `alu` reference resolve to place with
   `kind = "alu"`.
2. `test_an_unowned_or_unclassified_mark_is_a_load_error` — fault classification
   exist to prevent, driven through real loader on edited copy of scenario.
3. `test_demoted_towns_keep_their_people_and_are_counted_once` — palace centres
   hold nobody, four owners hold exactly folded sums, living population equal
   authored population with nothing double-counted.
4. `test_ugarit_still_reaches_the_sea_through_its_own_harbour` — Ma'hadu is
   `seat` harbour, route may still end at palace centre.
5. `test_the_authored_import_sickens_the_alu_that_holds_the_harbour` — tablet
   still say Ma'hadu, sickness begin at Ugarit, run on 11700 people.
6. `test_every_alu_is_reachable_from_the_seat` — no Alu courier cannot reach.
7. `test_the_tablet_draws_holdings_as_holdings` — no `hub` survive in Belief,
   `seat` count 4 palace centres and 7 grain estates, named centres listed,
   selected palace centre say whose it is instead of claiming rank.

---

## 11. As built

Four things implementation settled that design left open or wrong.

**Authored plague import.** `[plague] import_place = "ma_hadu"` seeded compartment on place that no longer has one, so disease never began. Scenario still name Ma'hadu — travellers do land at harbour — and `load.py` resolve seeding to Alu that hold it. Palace centre never carry SIR compartments; people travellers land among are Ugarit's. `tests/test_m13_material_causality.py` pinned Ma'hadu as second infectable settlement one leg from seat, now use Alalakh (`mukish`) — Alu, one land leg away, open all year.

**`Place.harbour`.** Boolean on palace-centre record, because Task 1 must answer "is this Alu coastal" without inventing harbour system §8.3 give to Task 5. Ma'hadu and Ura carry it.

**Standing line not mention harbour.** "a palace centre of Ugarit, and its harbour" run past panel width, cut mid-word; authored `role` line already say what Ma'hadu is. Line read "a palace centre of Ugarit" and stop.

**`SITE_WORD["palace"]`** changed from "small palaces" to "palace centres", so map words and data words same word.

Authority audit missing-mapping finding moved from 36 legacy places to 47 — new Alu are real places with no kernel settlement behind them. That number Task 2 to drive to zero, now honest about whole map rather than part.

---

## 12. Open, and deliberately not decided here

- **Tiryns.** Demoted to palace centre of Mycenae. One demotion with live
  argument for own wanax; if it become Alu again, count move to 43 with no
  other change.
- **Naming the 66 palace centres.** All named now. Where history supply name
  (Sippar under Babylon, Ma'hadu under Ugarit) it used; rest take plausible
  Bronze Age toponym for that Alu territory.
- **`power` as taxonomy.** Two values added for honesty on map. Real model of
  overlordship king-to-king in Task 4, and `power` should die there.
- **Kernel `Site.function` vocabulary.** `estate`/`harbour`/`mine` versus this
  doc `capacity` names. Must reconcile when kernel become one authority; §4
  `capacity` values chosen to map onto them one-to-one.