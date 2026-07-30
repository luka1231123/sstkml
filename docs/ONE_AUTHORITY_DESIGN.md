# One authority per fact — design pass for Alpha 0.7 Task 2

Status: design only. No code changes belong to this document.

Supersedes the plan in `docs/PHASE_C_AUTHORITY.md` where the two differ; that
file's table of duplicated facts still stands and is restated here with the Alu
model applied. Task 1's classification (`docs/ALU_CLASSIFICATION.md`) is the
input: the scenario now says what every place and every mark on the map is, so
the kernel can be built from it instead of being authored a second time.

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

One fact the audit does not report and that decides the shape of this task:
**nothing in the game loads the kernel.** `load_kernel` is imported by
`tools/authority_audit.py`, `tools/kernel_inspect.py`, and tests. `session.py`,
`play_cli.py`, and `play_gui.py` never touch it. So there is no live divergence
to reconcile — there is a second world that has never been played, and the work
is to make it the only one and then run the game on it.

That is why the migration below moves the court onto the kernel rather than
merging two running states. There is no save to convert: a save is a seed, a
scenario, and an action log (`session.py`), and replaying it through the new
loader produces the new state. Saves made before the change fail the
`state_hash_at_save` check and are dropped, which is correct — there is no
released version to be compatible with.

---

## 2. Final owner of every fact

`World` keeps a `kernel: Kernel` field. `Kernel` owns the world; `Court` keeps
only what is about the king's household and his correspondence.

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

Rules the audit cannot check:

1. A deleted court field may not return as a cache. Read-through is allowed
   only through `belief/project.py`, which may precompute.
2. Ugarit stays `autonomous = false` until player orders drive it (Task 3).
3. No court→kernel identifier is inferred at a call site. One authored map,
   loaded once, checked at load. See §4.

---

## 3. One authored world

Delete the duplicate geography in `content/kernel/world.toml`. The scenario is
the authored world; the kernel registry is built from it at load.

| Registry table | Built from |
|---|---|
| `Region` | new `[[regions]]` in the scenario; each Alu names one |
| `Polity` | the `power` vocabulary plus one polity per independent Alu |
| `Settlement` | one per Alu (42) |
| `Site` | one per authored site mark (187), plus the harbour of each coastal Alu |
| `Route` | the 78 authored routes |
| `Cohort` | `Place.population`, split by authored shares |
| `Organization` | one palace per Alu; temples and merchant houses where authored |

`content/kernel/world.toml` keeps only what the scenario cannot express and
becomes `content/kernel/detail.toml`: seasons, the climate series, per-site
`capacity` and `extent`, cohort composition for the settlements that have it
authored, opening stores, obligations. Every row in it names an entity the
scenario already created; a row naming anything else is a load error.

Palace centres do not become settlements. A palace centre is a `Site` of its
Alu with `function = "palace"`; `Place.harbour` becomes a `Site` with
`function = "harbour"`. This is what keeps the settlement count at 42 rather
than 48 and is the same rule Task 1 already enforces on the court side.

### 3.1 Site function vocabulary

Task 1 left this open. Closed here: the kernel's `Site.function` is the
authority, and the scenario's `capacity` values map onto it one-to-one.

| Scenario `kind` / `capacity` | `Site.function` |
|---|---|
| `grain` / `food` | `estate` |
| `copper`, `tin`, `silver`, `gold` / same | `mine` |
| `timber` | `forest` |
| `stone` | `quarry` |
| `pasture`, `horses` | `pasture` |
| `palace` (role `palace_centre`) | `palace` |
| harbour mark | `harbour` |

`forest` and `quarry` are new function names. `function` is a free string in
`engine/entity.py`, so this is content, not a spec change — but the loader must
reject a function outside the closed list, or the vocabulary drifts.

### 3.2 Cohorts for 42 Alu

Each Alu gets at least one cohort, minted from `Place.population`:

- `cohort:{alu}_fields`, `kind = "field_labour"` — the default, taking the whole
  authored population where nothing else is said.
- Where `detail.toml` authors a split (Ugarit, Ma'hadu's old cohorts, Alashiya,
  Ari), that split is used instead and must sum to `Place.population`.

The sum rule is the same conservation check Task 1 already has for demoted
towns, and it gets a test: total cohort people equals total authored population.

### 3.3 Autonomy

Autonomy moves from settlement to Alu, as `docs/ALU_CLASSIFICATION.md` §9
resolved:

| Settlement | Before | After |
|---|---|---|
| `settlement:ugarit` | not autonomous | not autonomous (until Task 3) |
| `settlement:mahadu` | autonomous | gone — a site of Ugarit |
| `settlement:ari` | autonomous | gone — a site of Ugarit |
| `settlement:alashiya_port` | autonomous | gone — the harbour of `settlement:alashiya` |
| the other 41 Alu | absent | autonomous |

The M13.1 exit gate — the world goes on when Ugarit is idle — is met by other
kings' cities instead of by Ugarit's own port. Its tests move to Alalakh,
Amurru, Carchemish, and Alashiya. The gate's assertion does not weaken: with
Ugarit removed the remaining settlements must still produce, consume, decide,
and change.

`Kernel.controller()` looks for `kind == "council"`. Every Alu has a king, so
the controlling organization is `kind = "palace"`. Widen `controller()` to
`("palace", "council")`, palace first, and keep the existing councils where the
authored place has no king (there are none left after the demotions, but the
kind stays legal).

---

## 4. The identifier map

Court ids are bare strings, kernel ids are `kind:name`. Task 1 made the
scenario the single place both are authored, so most of the map is one rule
applied at one site in the loader — which is authorship, not inference, because
the loader mints both ids from the same row:

| Court entity | Kernel id |
|---|---|
| `Place` with `kind = "alu"` | `settlement:{id}` |
| `Place` with `kind = "palace_centre"` | `site:{id}` under `settlement:{alu}` |
| authored site mark | `site:{alu}_{capacity}_{n}` |
| `Route(a, b)` | `route:{a}_{b}` |

What is *not* derivable, and needs an authored `content/kernel/idmap.toml`:

| Section | Entries | Why not derivable |
|---|---|---|
| `[places]` | `mahadu = "site:ma_hadu_harbour"`, `ari`, `alashiya_port` | the existing kernel names differ from the scenario's (`mahadu` vs `ma_hadu`), and two of the three stop being settlements |
| `[actors]` | 14 correspondents → `org:` ids | `hatti_king` → `org:hattusa_palace`; the name of the actor is not the name of the place |
| `[estates]` | 3 court estates → `site:` ids | court estate ids are their own vocabulary |
| `[institutions]` | court institutions → `org:` or `site:` | a harbour is a site, a temple is an org; the split is a judgement |
| `[groups]` | `DependentGroup` → `cohort:` ids | function names do not match cohort kinds |

The loader raises on any court entity of these kinds with no entry, and on any
entry naming an entity the registry does not have. `unmapped()` in the audit
stops guessing by string match and reads the map instead.

One case the map has to handle: `ura_merchant` is a correspondent at `ura`,
which Task 1 demoted to a palace centre of Tarhuntassa. Correspondent places
resolve through the owning Alu, the same way the plague import does today.

---

## 5. The turn

`engine/tick.py` becomes an assembly of `engine.kernel.turn.Step`s and stops
being a second turn pipeline. Court systems keep their code; they are declared
into the phase they occupy and run through `T.run`, which already refuses a
step out of order.

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

Two orderings change and both are deliberate:

- Plague moves from before the house step to phase 11 with it. Ordering within
  a phase is the implementer's, so plague still runs first inside it and the
  "the dead are not fed" property is preserved — rations are now in phase 7 and
  therefore *before* mortality. That inverts today's rule. Resolve by moving
  mortality's grain effect: a person who dies in phase 11 was fed in phase 7 and
  the ration is spent, which is the more defensible reading anyway.
- `foreign_belief` and `correspondence_policy` become kernel observation and
  kernel policy for the same actors, so they collapse into phases 3 and 4 as
  those actors' councils. Until they do (step C6 below) they run in 12.

---

## 6. Migration order

Each step ends green: full test run, `tools/authority_audit.py` with one fewer
finding, and no new field that caches a deleted one.

| Step | Does | Closes |
|---|---|---|
| C1 | build the registry from the scenario; `World.kernel`; `idmap.toml`; loader checks | unmapped (47) |
| C2 | goods: `Court.stores` → `Book` at the seat | stock of goods |
| C3 | people and labour: `dependents` → `Cohort` | ordinary people, labour |
| C4 | land: `Court.estates` → `Site` | land |
| C5 | places and routes: `World.places`/`routes` → registry; plague layer over settlements; `belief/project.py` reads the registry | places, routes |
| C6 | foreign courts and actor belief → orgs, cohorts, `Kernel.beliefs` | foreign standing, actor belief |
| C7 | one date and one seed | the date |
| C8 | `tick.py` as an assembly of kernel steps; `advance_court` deleted | the competing tick |

C5 is the largest and is where the rooms change: `belief/project.py` is the only
path from state to screen, so every room follows from that one file being
repointed. C8 is the completion criterion the spec names; it cannot be done
before C1–C7 because a step declared into a phase still needs its state to be in
one place.

---

## 7. What has to be true at the end

- `tools/authority_audit.py` reports no findings, without a row being narrowed
  or deleted to achieve it.
- `load_kernel` is gone as a separate entry point; `load_scenario` returns a
  `World` whose `kernel` is the world.
- No room reads a writable copy of a kernel fact. Grep for `court.stores`,
  `court.dependents`, `court.estates`, `world.places`, `world.routes` in `tui/`
  and `belief/` returns nothing.
- `engine/tick.py` contains no phase ordering of its own; every step is declared
  with its phase and run through `T.run`.
- Removing `settlement:ugarit` from the registry leaves a world that still
  advances 96 turns without a fault.
- Total cohort people equals total authored `Place.population`; total lots at
  the seat equal the authored opening stores.
- A save written before the change is refused with a clear message rather than
  replayed into a divergent hash.

## 8. Open

- **Regions.** 42 Alu need regions and none are authored. Provisional list:
  north Levant, south Levant, Nile, Anatolia, Aegean, upper Mesopotamia, lower
  Mesopotamia, Alashiya. Climate is per region and the series is currently one
  global array; C1 either authors eight series or accepts one until Task 4.
- **Polities vs `power`.** Task 1 left `power` as a taxonomy that should die
  when king-to-king overlordship arrives in Task 4. C1 mints polities from it;
  that mapping is temporary and should be marked so in the loader.
- **`Court.house`, oaths, omens, justice.** Court-side and untouched here. They
  reference places by court id and will need the id map at C5.
