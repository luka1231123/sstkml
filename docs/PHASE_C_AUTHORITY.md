# Phase C — one authority per fact

Status: executable; subordinate to root `SPEC.md` (§6.2) and
`docs/WORLD_AGENT_PLAN.md` §7. Retire when `tools/authority_audit.py` reports
no findings.

Phase C end state `content/kernel/world.toml` already name in own comment: "the legacy court still owns Ugarit". Today two systems each hold authoritative answer to same question. No test say which one true. This file name the one authority and one deletion target per duplicated fact — migration become list, not judgement call.

Read table thus: **authority** = where fact live at end of Phase C. **Deletion target** = what must be gone, not merely unused. Field surviving as cache of authority still second authoritative quantity first time someone write to it.

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

Two halves name same things differently. Court ids = bare authored strings (`seat`, `ma_hadu`, `hatti_king`); kernel ids minted and parsed with kind prefix (`settlement:ugarit`, `cohort:ugarit_fields`), `engine/entity.py` refuse anything else.

So migration need explicit authored map court id → kernel id, loaded not derived. Deriving would silently invent entity first time authored name miss pattern. Correspondents, places, routes, estates, institutions, dependent groups all need entry. Anything without one = fact nobody own; audit must say so, not guess.

## 3. What "done" means

`tools/authority_audit.py` report finding whenever both sides hold non-empty authoritative answer to one table row. Fail today on purpose: that the inventory. Phase C complete when it report none. `C4` may not close by narrowing table.

Two migration rules audit cannot check — reviewers must:

1. Deleted court field may not return as cache. Room needing figure fast get it through `belief/project.py`, which may precompute.
2. Ugarit become autonomous in kernel only when its decisions are player's orders. Council organization for Ugarit would make kernel decide what king decide — seat's intents come from player, and `autonomous = false` in `content/kernel/world.toml` stay until order pipeline behind it.