# Task 2 — to do, in order

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
- [ ] `content/kernel/idmap.toml`: legacy kernel names, 14 correspondent actors,
      3 estates, institutions, dependent groups. Loader raise on any unmapped
      entity and on any entry naming nonexistent one.
- [ ] `World.kernel: Kernel`. Nothing read it yet.
- [ ] Delete `load_kernel.py`; point `tools/` at `load_scenario(...).kernel`.
- [ ] `authority_audit.unmapped()` read id map instead of string matching.
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
      spoils once, in the place that knows about the roof.
- [x] `store_history` become projection only.

## C3 — people and labour

- [ ] `Court.dependents` -> `Cohort`; arrears -> `hunger`/`grievance`.
- [ ] `pay_rations` to legacy; kernel `_consume` feed seat.
- [ ] `recompute_unrest` stay, read cohort grievance.
- [ ] Delete `allocations`, `priority`, `corvee_days`, `corvee_sources`,
      `at_harvest`.

## C4 — land

- [ ] `Court.estates` -> `Site(function="estate")`.
- [ ] `git mv engine/land.py engine/legacy/`; `kernel/farm.py` is harvest.
- [ ] Delete `last_harvest`, `previous_harvest`.

## C5 — places, routes, and the rooms

- [ ] `World.places` -> `Settlement`/`Site`; `World.routes` -> `entity.Route`.
- [ ] Plague compartments off `Place` onto layer keyed by settlement.
- [ ] `mail.py` walk kernel routes.
- [ ] `belief/project.py` read registry. Projection keys unchanged, so `tui/`
      get no edit — verify by grepping `tui/` for `court.`/`world.`.

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