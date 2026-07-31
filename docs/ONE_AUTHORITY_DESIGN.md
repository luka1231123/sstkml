# One authority per fact — design pass for Alpha 0.7 Task 2

Status: design only. No code changes in this document.

Supersedes `docs/PHASE_C_AUTHORITY.md` where they differ; that file's duplicated-facts table restated here with Alu model applied. Task 1's classification (`docs/ALU_CLASSIFICATION.md`) is input: scenario now says what every place and mark is, so kernel built from it, not authored twice.

---

## 1. Where the two worlds actually stand

`tools/authority_audit.py` today:

| Fact | Court | Kernel |
|---|---|---|
| stock of goods at the seat | 799,100 | 25,896 |
| ordinary people at the seat | 1,010 | 1,300 |
| labour at the seat | 1,010 | 15,600 |
| land under the seat | 8,400 iku | 46,000 qa of seed |
| places | 48 | 4 |
| routes | 78 | 2 |
| foreign court standing | 6 | 3 |
| actor belief | 6 | 5 |
| the date | turn 2 | turn 2 |
| court places with no kernel settlement | 47 | — |

Audit misses one fact that decides task shape: **nothing in game loads kernel.** `load_kernel` imported by `tools/authority_audit.py`, `tools/kernel_inspect.py`, tests. `session.py`, `play_cli.py`, `play_gui.py` never touch it. No live divergence to reconcile — second world never played. Work: make it the only one, then run game on it.

So migration moves court onto kernel, not merges two running states. No save to convert: save is seed, scenario, action log (`session.py`); replay through new loader produces new state. Pre-change saves fail `state_hash_at_save` check and drop — correct, no released version to stay compatible with.

---

## 2. Final owner of every fact

`World` keeps `kernel: Kernel` field. `Kernel` owns world; `Court` keeps only king's household and correspondence.

| Fact | Owner after Task 2 | Deleted |
|---|---|---|
| Stock of a good | `Book` lots at `settlement:seat` | `Court.stores` |
| Goods provenance | `Book.transfers` | `Court.store_history` (becomes projection) |
| Ordinary people | `Cohort` | `Court.dependents`, `allocations`, `priority` |
| Labour | `Cohort.labour()` + allocator | `corvee_days`, `corvee_sources`, `at_harvest` |
| Hunger, grievance | `Cohort.hunger`, `Cohort.grievance` | `DependentGroup.arrears` |
| Land | `Site(function="estate")` | `Court.estates`, `last_harvest`, `previous_harvest` |
| Places | `Settlement` + `Site` + `Region` | `World.places` |
| Routes | `entity.Route` + `Leg` | `World.routes`, `state.Route` |
| Plague compartments | `PlagueState.sir: Mapping[EntityId, SIR]` | `Place.susceptible/infected/recovered/dead` |
| Institutions | `Organization` + `Site` | `Court.institutions` |
| Works | `Site.condition` + work intents | `Court.projects`, `works_days` |
| Foreign court standing | `Cohort` + `Book` + `Organization` per Alu | `World.foreign_courts`, `ForeignCourt` |
| Actor belief | `Kernel.beliefs` | `World.foreign_beliefs` |
| Date and seed | `Kernel.date`, `Kernel.seed` | `World.date`, `World.seed` (accessors only) |
| Named household | `Court.house` | — |
| Correspondence | `World.inbox`, `letters_in_transit`, `correspondence` | — (ids become kernel ids) |
| Oaths, omens, justice, relations | court-side | — |
| Court's own belief | `belief/project.py` | — |

Rules audit cannot check:

1. Deleted court field may not return as cache. Read-through only through `belief/project.py`, which may precompute.
2. Ugarit stays `autonomous = false` until player orders drive it (Task 3).
3. No court→kernel identifier inferred at call site. One authored map, loaded once, checked at load. See §4.

---

## 3. One authored world

Delete duplicate geography in `content/kernel/world.toml`. Scenario is authored world; kernel registry built from it at load.

| Registry table | Built from |
|---|---|
| `Region` | new `[[regions]]` in the scenario; each Alu names one |
| `Polity` | the `power` vocabulary plus one polity per independent Alu |
| `Settlement` | one per Alu (42) |
| `Site` | one per authored site mark (187), plus the harbour of each coastal Alu |
| `Route` | the 78 authored routes |
| `Cohort` | `Place.population`, split by authored shares |
| `Organization` | one palace per Alu; temples and merchant houses where authored |

`content/kernel/world.toml` keeps only what scenario cannot express, becomes `content/kernel/detail.toml`: seasons, climate series, per-site `capacity` and `extent`, cohort composition where authored, opening stores, obligations. Every row names entity scenario already created; row naming anything else is load error.

Palace centres do not become settlements. Palace centre is `Site` of its Alu with `function = "palace"`; `Place.harbour` becomes `Site` with `function = "harbour"`. Keeps settlement count at 42, not 48 — same rule Task 1 enforces court-side.

### 3.1 Site function vocabulary

Task 1 left open. Closed here: kernel's `Site.function` is authority; scenario's `capacity` values map onto it one-to-one.

| Scenario `kind` / `capacity` | `Site.function` |
|---|---|
| `grain` / `food` | `estate` |
| `copper`, `tin`, `silver`, `gold` / same | `mine` |
| `timber` | `forest` |
| `stone` | `quarry` |
| `pasture`, `horses` | `pasture` |
| `palace` (role `palace_centre`) | `palace` |
| harbour mark | `harbour` |

`forest` and `quarry` are new function names. `function` is free string in `engine/entity.py`, so content, not spec change — but loader must reject function outside closed list, or vocabulary drifts.

### 3.2 Cohorts for 42 Alu

Each Alu gets at least one cohort, minted from `Place.population`:

- `cohort:{alu}_fields`, `kind = "field_labour"` — default, takes whole authored population where nothing else said.
- Where `detail.toml` authors a split (Ugarit, Ma'hadu's old cohorts, Alashiya, Ari), that split used instead and must sum to `Place.population`.

Sum rule is same conservation check Task 1 has for demoted towns; gets a test: total cohort people equals total authored population.

### 3.3 Autonomy

Autonomy moves from settlement to Alu, per `docs/ALU_CLASSIFICATION.md` §9:

| Settlement | Before | After |
|---|---|---|
| `settlement:ugarit` | not autonomous | not autonomous (until Task 3) |
| `settlement:mahadu` | autonomous | gone — a site of Ugarit |
| `settlement:ari` | autonomous | gone — a site of Ugarit |
| `settlement:alashiya_port` | autonomous | gone — the harbour of `settlement:alashiya` |
| the other 41 Alu | absent | autonomous |

M13.1 exit gate — world goes on when Ugarit idle — met by other kings' cities, not Ugarit's own port. Tests move to Alalakh, Amurru, Carchemish, Alashiya. Gate assertion does not weaken: with Ugarit removed, remaining settlements must still produce, consume, decide, change.

`Kernel.controller()` looks for `kind == "council"`. Every Alu has king, so controlling organization is `kind = "palace"`. Widen `controller()` to `("palace", "council")`, palace first, keep existing councils where authored place has no king (none left after demotions, but kind stays legal).

---

## 4. The identifier map

Court ids are bare strings, kernel ids are `kind:name`. Task 1 made scenario the single place both authored, so most of map is one rule applied at one site in loader — authorship, not inference, because loader mints both ids from same row:

| Court entity | Kernel id |
|---|---|
| `Place` with `kind = "alu"` | `settlement:{id}` |
| `Place` with `kind = "palace_centre"` | `site:{id}` under `settlement:{alu}` |
| authored site mark | `site:{alu}_{capacity}_{n}` |
| `Route(a, b)` | `route:{a}_{b}` |

Not derivable, needs authored `content/kernel/idmap.toml`:

| Section | Entries | Why not derivable |
|---|---|---|
| ~~`[places]`~~ | none — dropped in C1 | derivable after all: a mark names its Alu and every Alu is a settlement, so `load.kernel_settlement` reads the join off the content. The three legacy names this row was written for stopped being settlements, which removed the case it existed to handle |
| `[actors]` | 14 correspondents → `org:` ids | `hatti_king` → `org:hattusa_palace`; actor name is not place name |
| `[estates]` | 3 court estates → `site:` ids | court estate ids are own vocabulary |
| `[institutions]` | court institutions → `org:` or `site:` | harbour is site, temple is org; split is judgement |
| `[groups]` | `DependentGroup` → `cohort:` ids | function names do not match cohort kinds |

Loader raises on any court entity of these kinds with no entry, and on any entry naming entity registry lacks. `unmapped()` in audit stops guessing by string match, reads map instead.

One case map must handle: `ura_merchant` is correspondent at `ura`, which Task 1 demoted to palace centre of Tarhuntassa. Correspondent places resolve through owning Alu, same way plague import does today.

---

## 5. The turn

`engine/tick.py` becomes assembly of `engine.kernel.turn.Step`s, stops being second turn pipeline. Court systems keep code; declared into phase they occupy, run through `T.run`, which already refuses step out of order.

| Phase | Steps |
|---|---|
| 1 calendar | date advance, lapse inspections |
| 2 arrivals | schedule drain, relations/justice/revenue scheduled, births, letter movement, summons |
| 3 observe | kernel `_observe` |
| 4 intents | kernel `_intents` |
| 5 allocate | `R.allocate` |
| 6 production | farm steps, metal, institution decay, harbour dues, works |
| 7 consumption | kernel `_consume`, spoilage, rites, rations |
| 8 market | kernel market |
| 9 movement | sailings |
| 10 settlement | obligations, land dues |
| 11 health | plague step, house step |
| 12 politics | unrest, justice queue, oath audit, foreign belief, correspondence policy |
| 13 upkeep | — (institution decay stays in 6 with the fabric) |
| 14 reports | mail generation, archive filing |
| 15 project | store readings, docket |
| 16 player | `reduce.apply`, driven by the game loop |
| 17 close | `faults()`, `state_hash` |

Two orderings change, both deliberate:

- Plague moves from before house step to phase 11 with it. Ordering within phase is implementer's, so plague still runs first inside it and "dead are not fed" property preserved — rations now in phase 7, therefore *before* mortality. Inverts today's rule. Resolve by moving mortality's grain effect: person who dies in phase 11 was fed in phase 7 and ration is spent — more defensible reading anyway.
- `foreign_belief` and `correspondence_policy` become kernel observation and kernel policy for same actors, so collapse into phases 3 and 4 as those actors' councils. Until then (step C6 below) they run in 12.

---

## 6. Migration order

Each step ends green: full test run, `tools/authority_audit.py` with one fewer finding, no new field caching a deleted one.

| Step | Does | Closes |
|---|---|---|
| C1 | build the registry from the scenario; `World.kernel`; `idmap.toml`; loader checks | unmapped (26, all false) |
| C2 | goods: `Court.stores` → `Book` at the seat | stock of goods |
| C3 | people and labour: `dependents` → `Cohort` | ordinary people, labour |
| C4 | land: `Court.estates` → `Site` | land |
| C5 | places and routes: `World.places`/`routes` → registry; plague layer over settlements; `belief/project.py` reads the registry | places, routes |
| C6 | foreign courts and actor belief → orgs, cohorts, `Kernel.beliefs` | foreign standing, actor belief |
| C7 | one date and one seed | the date |
| C8 | `tick.py` as an assembly of kernel steps; `advance_court` deleted | the competing tick |

C5 is largest, is where rooms change: `belief/project.py` is only path from state to screen, so every room follows from that one file being repointed. C8 is completion criterion spec names; cannot be done before C1–C7 because step declared into phase still needs its state in one place.

---

## 7. What has to be true at the end

- `tools/authority_audit.py` reports no findings, without narrowing or deleting a row to achieve it.
- `load_kernel` gone as separate entry point; `load_scenario` returns `World` whose `kernel` is the world.
- No room reads writable copy of kernel fact. Grep for `court.stores`, `court.dependents`, `court.estates`, `world.places`, `world.routes` in `tui/` and `belief/` returns nothing.
- `engine/tick.py` contains no phase ordering of its own; every step declared with its phase, run through `T.run`.
- Removing `settlement:ugarit` from registry leaves world that still advances 96 turns without fault.
- Total cohort people equals total authored `Place.population`; total lots at seat equal authored opening stores.
- Save written before change is refused with clear message, not replayed into divergent hash.

## 8. Decided since

- **Archiving.** Replaced court modules move by `git mv` into `engine/legacy/`, unedited, drop out of turn. Nothing commented out in place.
- **Regions and climate.** Eight regions — north Levant, south Levant, Nile, Anatolia, Aegean, upper Mesopotamia, lower Mesopotamia, Alashiya — each with own 96-entry climate series. Nile series is flood, not rainfall.
- **Palace names.** All 66 unnamed palace marks get name (C0). Stay sites, not settlements: named on map and in hinterland panel, not addressable by courier, plague, or correspondent.

## 9. Open

- **Polities vs `power`.** Task 1 left `power` as taxonomy that should die when king-to-king overlordship arrives in Task 4. C1 mints polities from it; mapping temporary, should be marked so in loader.
- **`Court.house`, oaths, omens, justice.** Court-side, untouched here. Reference places by court id, will need id map at C5.