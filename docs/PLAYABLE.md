# What is left to make the game playable

- Status: working document, subordinate to `SPEC.md`
- Measured: 2026-09-07; original campaign figures at `dcc0fe8`, calm-world
  verification and screen repairs after `d382965`
- Every number below comes from a run in this repository, not from reading code

## 1. Where it stands

The simulation is real, conserved, deterministic and inspectable. At `dcc0fe8`,
630 tests passed in 19 seconds. `tools/inventory.py` reports 33 player actions, 23 charged,
19 contexts, no faults. `authority_audit`, `information_audit` and
`corpus_lint` have no findings. All nine rooms of `SPEC.md` 3.3 exist and own
their verbs.

The gap is the game, not the simulation.

### The calm world holds; the campaign collapses

An idle campaign, up to thirty years, with authored climate and shocks,
after the population-health repairs below:

| Seed | Seat | Alu alive when the run stops |
|---|---|---|
| 1 | survives | 1 of 55 |
| 42 | falls turn 341, year 14.2 | 31 of 55 |
| 7 | falls turn 532, year 22.2 | 5 of 55 |

World population on seed 1 goes from 9,495,000 to 5,709,857. All three runs
pass the final cohort, fallen-ruler, map and terminal-state checks.

`SPEC.md` 6.4 sets two targets here. The seat's own fall is close to the first:
the band is year 15 to 30 unaided, seed 7 lands at 22.2, seed 42 is early at
14.2, and seed 1 does not fall at all. The second target needs a separate
calm-world run: an idle player does not disable climate, shocks, plague or
raids.

The calm-world probe now keeps ordinary population and unrest falls enabled.
Previously `baseline=True` suppressed those falls along with the shocks, so
counting surviving settlement marks alone could hide a failed economy.

`tools/gameplay_probe.py 3 720 --baseline --policy passive` reports the same
result for seeds 1, 7 and 42: all 55 Alu survive thirty years, world population
grows from 9,495,000 to 9,781,914, no settlement drops below its opening
population, and peak whole-Alu unrest is 43/1000. Seat grain ends at 6,678,565 qa,
with zero whole-Alu unrest. No impossible states are reported. The unshocked
stability requirement is met on these seeds without changing yields or rations.

In the campaign, a food deficit compounds. The seat's harvest falls from 4.9M
qa in year 1 to 0.2M by year 8 while consumption stays near 1.5M. Sowing is
capped by work days, and work days fall with hunger, so a bad year makes the
next year worse. `dcc0fe8` raised `HUNGER_FLOOR` from 200 to 600 and gave a fed
roll a way to shed grievance, which moved seed 1 from year 9.7 to surviving.
The remaining balance work is shock severity, recovery and the unaided fall
window. The calm-world measurement does not justify raising yields or cutting
rations across the whole world.

The stricter cohort audit also found negative populations hidden by positive
settlement totals: starvation, battle losses and desertion left disease counts
larger than their surviving cohorts, and later plague deaths subtracted those
already lost. Casualties and departures now reduce disease compartments;
splits allocate recovered people only into space left by infected people.
The probe checks population and health bounds, and terminal cause/date. Losing
an occupied town does not require its distant occupying ruler to die.
These simulation changes advance the save format to 27; older logs are rejected
instead of replaying with different outcomes.

Current validation: targeted kernel, seat, conflict, plague, save and screen
checks pass; authority, inventory, information and corpus audits are clean.
The 96-turn benchmark took 8.55 seconds, with a 44.48 MB canonical state and
0.78-second hash. A turn-by-turn cohort audit passed 240 campaign turns on seed 1.

### Ration orders show their price; other allocations still need it

The ration queue now shows before/after payments, each group's shortfall in qa,
old and resulting arrears, work capacity with the same people, grain spent and
remaining, and the arithmetic for full-roll food coverage. All are estimates
from the dated granary and payroll records; coverage excludes arrivals,
spoilage and other uses. Oversized allowances stop at the engine's actual
claim, including at most one old ration. Zero rations can be drafted and
confirmed; Escape cancels, and Enter gives the displayed order.

Allocation and queue drafts are reviewed separately so an unconfirmed change
cannot affect the price of another order. The standalone Roll now has the same
minimum space as Storehouse so its confirmation figures remain visible.
Costs for other allocations and the harvest deadline comparison still need work.

## 2. The loop

Two verbs, and there is no third.

**Order** — inside the realm. Grain, seed, hands, men, metal, land, works. An
order names a quantity, a recipient, an executor, and a date. An official
carries it out, and he has his own interests, so he may perform it badly,
partly, or late.

**Letter** — outside the realm. Imports, tribute, troops, marriage, oaths,
complaints. A letter costs a courier and fortnights and returns an answer the
player does not control.

Everything else is information that feeds these two, or a consequence of them.
No screen mutates anything. The king writes.

The fortnight: what arrived, what must be decided, orders, letters, end. The
world resolves and the report shows what was expected against what happened.

## 3. The decisions that need a price on screen

### Food

**How much to take.** The land due is a share of the harvest. Take a high
share and the granary is full now, the villages keep less seed, and next year's
sowing is short. Take a low share and the granary is thin while the countryside
sows fully. The screen must show both halves in qa: *this rate takes 12,000 qa
now and leaves the villages 2,000 qa short of full sowing.*

**Who eats.** The ration is a queue, not a number. When stores are thin the
field cohorts, palace staff, troops, temple and the poor cannot all be fed.
Feeding field cohorts protects the next harvest, troops protect what a levy is
worth, palace staff protect how well orders are carried out, temple protects
legitimacy, and everyone left over turns into grievance. The productivity
effect stays small and the political effect stays large. `set_priority` already
exists as an action; what is missing is the screen that shows who goes last.

**Whether to import.** Grain for metal, through a letter, at a foreign price,
over a route that takes fortnights and can be lost. There is no `import_grain`
verb, so this decision does not exist yet.

**How many hands to the fields.** Land caps the sown extent, so hands beyond
capacity do nothing. Seed caps what can be sown in the sowing window at 3 qa a
person-day. Harvest is the bottleneck at 12 qa a person-day, and standing crop
not cut by the last harvest fortnight is destroyed. So more men on the fields
is a deadline problem, not a growth lever, and it collides with every other
claim on the same men.

### Build or spend

Metal, grain and person-days spent on a work are not available for food,
troops or gifts, and the work pays back only after it finishes.

| Work | Costs | Returns |
|---|---|---|
| Granary | timber, days | less spoilage a fortnight |
| Canal or ditch | days, seasonal | more sown capacity |
| Wall | stone, days, metal | defence, refuge for cohorts |
| Workshop | metal, days | bronze, tools, repairs |
| Road or quay | days | shorter route, more cargo |

The payback figure must come from the player's own believed numbers and appear
before confirmation. Repair competes with build: a decayed institution pays
back immediately and gets ignored because it is dull.

### Men

Every man committed is a man not reaping. Levy, escort, garrison and corvée all
draw the same pool at the same time the harvest does. Escorts matter most,
because an unescorted caravan on a route with reported raiders is the clearest
version of the trade: 300 person-days now against the cargo. Show the conflict
at the point of the order: *this levy takes 300 person-days from a harvest that
is already 1,100 short.*

### Court and abroad

Appointment is an allocation of authority, and a competent official executes
orders closer to what was written. One ruling spends visible grain or copper
and changes unrest, with both arguments on screen first. Kin and succession is
an heir named, a daughter married abroad, a brother given an office or refused
one.

Abroad is all letters: pay tribute or withhold it, answer a request or refuse
it, give a gift now to be owed a favour later, swear an oath, threaten to go to
a third court.

There are no factions and no faction scores. Rites and legitimacy wait until
0.7 is otherwise complete.

## 4. What is missing, in evidence

**Verbs that do not exist.** `import_grain`, `pay_arrears`, `standing_order`,
`commission_report`. Arrears drive the unrest that ends the campaign and there
is no way to clear them. Without standing orders the king re-decides the same
thing every fortnight, so attention goes on repetition instead of judgement.

**Letter kinds.** `engine/letter_terms.py` implements `gift`, `request_good`,
`promise_good`, `service` and `marriage_proposal`. `SPEC.md` 6.2 fixes about
15. Missing: troops and escorts, raiding complaint, enemy movement report, oath
demand, detained messenger release, dispute referral, physician or craftsman or
scribe request, accession and death, threat to go to a third court.

**Loading is a full replay.** `session.play` still returns an empty `hashes`
list. At 151 ms a turn a year-10 campaign takes about 36 seconds to load and
gets worse every fortnight. Canonical state is 100 MiB and takes 1.95 seconds
to hash at 240 turns.

**The journal is unreadable.** Over six runs of 120 turns: `kernel:news`
113,957, `kernel:spoiled` 97,238 against `kernel:reaped` 5,466, and
`kernel:withered` 14,580 against `kernel:sown` 4,195. The fortnight window and
the developer inspector both read this list.

**Trade is one price line.** The Exchange shows the grain price and nothing
else. The Hall's trade badge now counts cargo rather than every courier, which
was the older defect.

**Screen repairs completed.** `tools/screens.py all` now prepares harvest
orders only when they are legal. Its documented space-separated `--seed` and
`--turns` options work, as do `--seed=...` and `--turns=...`. Panel close
controls occupy a status bar instead of overprinting the frame border. All
screens rendered at the default turn 6 and at seed 42, turn 12 during harvest.

**`play_gui.py` is 4,944 lines** and grew again in the last two commits. One
`Game` class owns the desktop, every room's key handler, the writing desk, the
model threads, and save and load.

**Farm information still owed.** The loss record by cause, the exhaustion
fortnight, and the per-cohort allocation rows. Everything else in the farm
slice is drawn in the Hall, the Land ledger and the Alu, with Help topics
`grain_year`, `person_days`, `river_gauge` and `units`.

## 5. Order of work

1. Calm-world stability verified for three seeds over thirty years, per
   `SPEC.md` 6.4. Keep this separate from campaign shock and recovery tuning.
2. Ration allocation prices completed: what is spent and left, full-roll food
   coverage, who goes short and by how much. Extend this to other allocations.
3. Add `pay_arrears`, then `import_grain` through the letter path.
4. Ration queue and immediate work-capacity consequences completed. Compare
   field capacity against the seasonal harvest deadline with item 7.
5. Land due and harbour due shown as this year against next year.
6. Works with their payback arithmetic, competing with harvest labour.
7. Levy, corvée and escort priced against the harvest deadline at the order.
8. The remaining letter kinds from `SPEC.md` 6.2.
9. `standing_order`, then re-run `tools/gameplay_probe.py`. The policies must
   diverge further than they do now.
10. Save a state hash and snapshot instead of replaying the log.
11. Fold `hungry`, `spoiled`, `withered` and `news` into per-turn totals.
12. Done: fix `tools/screens.py all` and the footer overprint.
13. Split `play_gui.py` by room.

## 6. Units

- **qa** — the grain measure. Everything about food is counted in qa.
- **parisu** — the larger grain measure used for granary totals.
- **person-day** — one person working for one day. A cohort of 1,000 people at
  12 person-days a head supplies 12,000 person-days a fortnight. Hunger takes
  strength before it takes numbers, so a starving cohort supplies fewer.
- **extent** — how much ground an estate can take, measured as the qa of seed
  it would swallow if sown full. Land capped at 7,920,000 qa of extent cannot
  be sown past that however many hands turn up.
- **under crop** — how much of that extent currently has something growing in
  it.
- **shekel** — the metal measure, for copper, tin, silver and gold.
- **fortnight** — one turn. Twenty-four to a year.
