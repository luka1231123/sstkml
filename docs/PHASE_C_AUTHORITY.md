# Phase C — one authority per fact

Status: executable; subordinate to root `SPEC.md` (§6.2) and
`docs/WORLD_AGENT_PLAN.md` §7. Retire when `tools/authority_audit.py` reports
no findings.

Phase C ends the state of affairs `content/kernel/world.toml` already names in
its own comment: "the legacy court still owns Ugarit". Today two systems each
hold an authoritative answer to the same question, and no test says which one is
the truth. This file names the one authority and the one deletion target for
every duplicated fact, so the migration is a list rather than a judgement call.

The rule for reading the table: **authority** is where the fact will live at the
end of Phase C. **Deletion target** is what must be gone, not merely unused. A
field that survives as a cache of the authority is still a second authoritative
quantity the first time someone writes to it.

## 1. The duplicate table

| Fact | Court authority (today) | Kernel authority (after C) | Deletion target |
|---|---|---|---|
| Stock of a good | `Court.stores` (flat mapping) | `ownership.Book` lots at `settlement:ugarit` | `Court.stores` |
| Custody vs ownership | not modelled | `GoodsLot.owner` / `GoodsLot.holder` | — (capability gained) |
| Goods provenance | `Court.store_history` readings | `Book` transfers | `store_history` becomes projection only |
| Ordinary people | `Court.dependents` (`DependentGroup`) | `entity.Cohort` | `Court.dependents`, `allocations`, `priority` |
| Labour supply | `Court.corvee_days`, `corvee_sources`, `at_harvest` | `Cohort.labour()` + `work` intents through the allocator | the three court fields |
| Hunger and grievance | `DependentGroup` arrears | `Cohort.hunger`, `Cohort.grievance` | arrears bookkeeping |
| Named household | `Court.house` (`HouseMember`) | stays court-side | — (persons are not cohorts) |
| Land | `Court.estates`, `last_harvest`, `previous_harvest` | `entity.Site` (`function="estate"`) + `kernel/farm.py` | `Court.estates` |
| Places | `World.places` (`Place`, incl. plague S/I/R) | `entity.Settlement` + `Region` | `World.places`; the plague layer moves to a World layer over settlements |
| Routes | `World.routes` (`Route(a, b, legs, mode, seasonal, risk)`) | `entity.Route` + `Leg` (capacity, tolls, season) | `World.routes` |
| Institutions | `Court.institutions` | `entity.Organization` + `Site` | `Court.institutions` |
| Works in hand | `Court.projects`, `works_days` | `Site` condition + `work` intents | court project bookkeeping |
| Obligations (material) | `World.letter_obligations`, `letter_claims`, `oaths` clauses | `obligation.Obligation` (closed clause kinds) | material clause duplication; oath tablets stay as documents |
| Foreign court standing | `World.foreign_courts` (Phase B interim) | `Cohort` + `Book` + `Organization` per settlement | `World.foreign_courts`, `ForeignCourt` |
| Actor belief | `World.foreign_beliefs` | `Kernel.beliefs` | `World.foreign_beliefs` |
| Court's own belief | `belief/project.py` over World | unchanged — one projection boundary | — |
| Turn order | `engine/tick.py` A-phases | `kernel/turn.py` seventeen phases | `tick.py` becomes an assembly of kernel steps |
| Date and seed | `World.date`, `World.seed` | `Kernel.date`, `Kernel.seed` | one of the two, not both |
| Correspondence | `World.inbox`, `letters_in_transit`, `correspondence` | stays court-side | — (but ids must become kernel ids) |

## 2. The identifier problem

The two halves do not name the same things the same way. Court ids are bare
authored strings (`seat`, `ma_hadu`, `hatti_king`); kernel ids are minted and
parsed with a kind prefix (`settlement:ugarit`, `cohort:ugarit_fields`) and
`engine/entity.py` refuses anything else.

So the migration needs an explicit, authored map from court id to kernel id,
loaded rather than derived: deriving it would silently invent an entity the first
time an authored name did not match a pattern. Correspondents, places, routes,
estates, institutions, and dependent groups all need an entry. Anything without
one is a fact nobody owns, and the audit should say so rather than guess.

## 3. What "done" means

`tools/authority_audit.py` reports a finding whenever two sides both hold a
non-empty authoritative answer to one row of the table. It fails today, on
purpose: that is the inventory. Phase C is complete when it reports none, and
`C4` may not close by narrowing the table.

Two rules for the migration that the audit cannot check, and reviewers must:

1. A deleted court field may not come back as a cache. If a room needs a figure
   fast, it comes through `belief/project.py`, which is allowed to precompute.
2. Ugarit becomes autonomous in the kernel only when its decisions are the
   player's orders. A council organization for Ugarit would make the kernel
   decide what the king decides — the seat's intents come from the player, and
   `autonomous = false` in `content/kernel/world.toml` stays until there is an
   order pipeline behind it.
