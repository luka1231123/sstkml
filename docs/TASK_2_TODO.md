# Task 2 — to do, in order

Status: **live.** The open boxes below are the remaining work of `SPEC.md`
Task 2. Six duplicated facts left.

Design: `docs/ONE_AUTHORITY_DESIGN.md`. Each step end green: full test run, one fewer finding from `tools/authority_audit.py`, no new field caching deleted one.

Decisions: archive by `git mv` into `engine/legacy/` (no comment-out in place); eight climate series, one per region; every palace centre get name.

## C0 — names and regions (content only, no code)

- [x] Name all 66 unnamed palace marks, confirm 6 named ones.
      Subagent, Sonnet 5, one pass: each mark get historical or plausible
      Bronze Age toponym for that Alu's territory, no invention where real
      site known. Output table keyed by `(alu, col, row)`.
- [x] Add `name` to `[[sites]]` with `role = "palace_centre"`; loader read it;
      `_hinterland` may name them.
- [x] Author 8 `[[regions]]`: north Levant, south Levant, Nile, Anatolia,
      Aegean, upper Mesopotamia, lower Mesopotamia, Alashiya.
- [x] Every `[[places]]` row get `region`.
- [x] Eight climate series, one per region, 96 entries each (4 years x 24).
      Nile is Nile flood, not rainfall; keep dry year in Levant series so
      M13.2 shortfall still bite.
- [x] Fix `docs/ALU_CLASSIFICATION.md` §12: 51 palace centres wrong, is 66.

## C1 — one authored world

- [x] `load.py` mint registry from scenario rows: settlements from Alu, sites
      from palace centres and marks, routes from routes, cohorts from
      `Place.population`, polities from `power`.
- [x] Closed `Site.function` vocabulary; loader reject anything outside it.
- [x] `content/kernel/world.toml` -> `detail.toml`: seasons, per-region climate,
      capacity/extent, cohort splits, opening stores, obligations. Every row
      must name entity scenario already made. Written by
      `tools/gen_detail.py`; seasons and eight climate series come straight
      off scenario. `Kernel.region_climate` new: eight series need eight
      places to sit. Settlement food ground is one estate on first of its
      food marks — actor sow estate it can see, extent spread over three
      marks leave two thirds of crop untended.
- [x] `content/kernel/idmap.toml`: loader raises on any entry naming a
      nonexistent entity (`load_idmap`). The `[places]` section is gone: a mark
      answers to its Alu and every Alu is a settlement, so `kernel_settlement`
      derives the join and `parse_places` already refuses a mark whose Alu does
      not exist. The old section had six entries, four derivable and one wrong.
      The 14 correspondent actors, 3 estates, institutions and dependent groups
      are still to author, and land with C6, C4 and C3 respectively.
- [x] `World.kernel: Kernel`. Read by the court's goods systems since C2, and
      advanced every turn by `tick.step_kernel`.
- [x] Delete `load_kernel.py`; point `tools/` at `load_scenario(...).kernel`.
- [x] `authority_audit.unmapped()` resolves through the Alu instead of string
      matching. Closes 26 findings that were never defects -- Mari answers to
      Dur Katlimmu, and comparing the two names was never going to say so.
- [x] Autonomy: drop `settlement:mahadu`, `ari`, `alashiya_port`; other 41
      Alu autonomous; Ugarit stay false. `Kernel.controller()` accept
      `("palace", "council")`.
- [x] Repoint M13.1 gate tests to Alalakh, Amurru, Carchemish, Alashiya.

Closes: 47 unmapped places.

## C2 — goods

- [x] `Court.stores` -> `Book` lots at `settlement:seat`.
- [x] `metal.py`, `revenue.py`, `works.py`, `institution.py`, `letter_terms.py`
      read book. Also `land.py`, `plague.py`, `relations.py`, `reduce.py` and
      the `systems.py` block in `tick`: a writer left on the flat mapping would
      have put the two records out of step inside the turn, which is worse than
      either being wrong on its own. `engine/seat.py` is the doorway; the
      court's mapping is written as a mirror until C5 moves its readers.
- [ ] `git mv engine/systems.py` spoilage into legacy; `Book` spoilage stand.
      Blocked on C4. The Book spoils at a flat authored rate; the court's rate
      moves with the state of the granary (6.18), and the institution does not
      cross until then. For now `farm.keep` skips the seat's lots, so the seat
      spoils once, in the place that knows about the roof. C3 does not lift
      this: the exemption is about the granary's roof, not about who eats.
- [x] `store_history` become projection only.

## C3 — people and labour

The payroll has crossed. `Court.dependents` is a mirror, the way `Court.stores`
has been since C2, and the mirror is deleted with its readers in C5.

- [x] Tenure: `Polity.tenure` / `Cohort.tenure`, `Kernel.tenure_of`,
      `world._food_owners`, `farm.share_out` / `divide` / `_sowable`.
      A dependent group is a redistributive body by definition -- it owns no
      grain and is owed a ration -- and `seat_people.as_cohort` now says so, so
      the converted groups land beside the seat's own households instead of
      into one pooled granary with them.
- [x] `seat_people.SEAT` was `settlement:ugarit`, which the live scenario does
      not have. Every placement silently matched nothing. Now `settlement:seat`.
      The audit had the same constant and the same bug; its goods, people,
      labour and land rows counted zero on the kernel side and reported a false
      all-clear. Fixed, and the audit is 5 findings -> 8 as a result.
- [x] `Court.dependents` -> `Cohort`. `seat.enrol` puts the six groups in the
      registry at load; `seat.mirror` writes the court's mapping back from them
      every turn. The garrison at Ma'hadu is `prebendal` rather than
      `redistributive`, because it stands in a place that does not owe it
      dinner -- and `world._within_reach` is what lets it eat from the seat.
- [x] `pay_rations` -> `engine/legacy/rations.py`; `seat.feed` calls
      `kernel.world.feed` at A8, where the roll used to stand. The moment
      matters: the same grain leaving before the rot and the rites instead of
      after is a different fortnight (spec 6.1).
- [x] Two consequence models, not one. The kernel says how much was not
      delivered (`Cohort.shortfall`, in qa, because `hunger` counts fortnights
      and rounds a part-paid ration up to a whole one). Spec 6.3's band table
      says what the debt costs, still in `systems._BANDS`, still the court's,
      applied in `mirror` and handed back to the cohort. `feed(starve=False)`
      is what stops the kernel's own hunger rule taking the same people twice.
- [x] The ration lever kept working. `pay_rations` retiring left `Allocate` and
      `SetPriority` attached to nothing, which `test_m8` caught. They are
      `Cohort.allowance` and `Cohort.precedence` now -- both facts about a
      redistributive arrangement, which is what a palace deciding who eats
      first is. `allowance` is deliberately not capped at the fortnight's
      ration: a store that hands over more is paying down a debt.
- [x] The payroll's heads come out of the seat's own cohorts rather than on top
      of them (`seat._make_room`). The crown's 1,010 already lived in that town;
      naming them is not arriving.
- [x] The ration is grain only (`world._foods`). A household eats its own seed
      rather than starve and nobody asks it; a body being issued a ration does
      not choose what is in it, and issuing the sowing as bread is `A.EatSeed`,
      an order the player gives. The roll reaching the seed on its own deleted
      that order and spent the crown's sowing every hungry fortnight.
- [x] `plague._kill_dependents` goes through `seat.bury`. It took the dead off
      the court's mapping only, and the mirror handed them their places back on
      the same turn -- 128 of the m13 audit's findings.
- [x] `SP.PLACEMENTS` still names `settlement:mahadu`, which the live map does
      not have -- the third stale id out of the retired
      `content/kernel/world.toml`, after `seat_people.SEAT` and the audit's copy
      of it. `seat.enrol` stands the garrison at the seat rather than nowhere,
      and `kernel.faults` is what caught it. Content decides whether the map
      gets a port or the table loses the row.
- [ ] The seat's other 80,000. Its own households are `pooled` and still eat
      nothing here, so `world._consume` keeps a seat exemption. Not people --
      land: the palace owns every lot standing there, so feeding them would be
      the crown's store, and they get a holding of their own when the seat's
      fields become the kernel's (C4).
- [ ] `recompute_unrest` still reads the mirror's arrears. Reads cohort
      grievance when the mirror goes (C5).
- [ ] Delete `allocations`, `priority`, `corvee_days`, `corvee_sources`,
      `at_harvest`. The first two are mirrors now; the last three are labour
      and wait on C4.

## C4 — land

- [x] `Court.estates` -> `Site(function="estate")`.
- [x] `git mv engine/land.py engine/legacy/`; `kernel/farm.py` is harvest.
- [x] Delete `last_harvest`, `previous_harvest`.

## C5 — places, routes, and the rooms

- [x] `World.places` -> `Settlement`/`Site`; `World.routes` -> `entity.Route`.
      The fields are gone; both are properties over the registry, memoised on
      the identity of the records they read. `Settlement`/`Site` carry the
      column, row, glyph, rank, role, harbour and population the tablet draws,
      and `Route` carries its course and the two marks it was authored between.
- [x] The 32 palace centres authored as `[[places]]` rows are sites too, marked
      `addressable`: a courier, a correspondent or the sickness reaches those by
      name and reaches the 59 `[[sites]]` marks not at all.
- [x] `World.sites` deleted; the hinterland is `registry.sites`.
- [x] Plague compartments off `Place` onto `PlagueState.sir`, keyed by place.
      Absent means wholly susceptible at the authored size; `plague._record` is
      the only writer.
- [x] `belief/project.py` reads the registry. Projection keys unchanged and
      `tui/` took no edit.
- [x] `mail.py` walk kernel routes. `state.Route` is gone: `World.routes` and
      `lines` hand out `entity.Route` itself, and mail, `divine` and
      `project` read `ends` and the legs. Two rules the shim used to flatten
      are named where they are applied: `mail.crossing` is the fortnights to
      cross, and `mail.sea_entry` is the seasonal-entry rule, which is about
      the first leg because a courier stopped by winter is stopped before he
      sets out. `with_routes` keys on `Route.id` and puts the record back
      whole.

Closes: places, routes. The audit is 8 findings -> 6.

## C6 — foreign courts and actor belief

- [ ] `ForeignCourt` -> `Organization` + `Cohort` + `Book` per Alu.
- [ ] `World.foreign_beliefs` -> `Kernel.beliefs`.
- [ ] `git mv engine/foreign_belief.py engine/correspondence_policy.py
      engine/legacy/`; their behaviour become kernel observe plus
      correspondence policy.

## C7 — date and seed

- [ ] `Kernel.date`, `Kernel.seed` only ones; `World.date`/`seed` become
      read-only accessors or go.

## C8 — one turn

- [ ] `engine/tick.py` declare every step with its phase, run them through
      `engine.kernel.turn.run`.
- [ ] Plague and house into phase 11; rations in 7 now precede mortality —
      ration spent by whoever die later that turn.
- [ ] `advance_court` gone.
- [ ] `tools/authority_audit.py` report no findings.

## Then

- [ ] Save format: refuse pre-change save with clear message rather than
      replay into divergent hash.
- [ ] Retire `docs/PHASE_C_AUTHORITY.md`.