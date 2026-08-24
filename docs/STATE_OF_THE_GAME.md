# State of the game — 2026-08-05

Review of the working tree at `a267cdd` plus 33 modified files. Every number
below comes from a run recorded in this session, not from reading code.

## 1. What the game is

Information-constrained rulership simulation, Late Bronze Age, around 1200 BC.
One fortnight per turn. Character-cell multi-window Tk desktop. A local
`qwen3:4b-instruct` supplies language only.

Size: engine 13.3k lines, tui 11.2k, content 13.0k, tests 10.8k, root 7.5k,
tools 4.6k, ai 2.8k, belief 1.3k.

## 2. The loop, as it actually runs

1. The player lands in the Hall with 10 attention hours.
2. The Hall shows believed grain, copper, tin with deltas; eight doors with
   matter counts; the audience floor; what is in motion.
3. The player spends hours on 38 registered actions, each costing 0 to 2 hours.
4. `Space` then `Enter` ends the fortnight.
5. `engine.tick.advance` runs 17 named phases in a fixed order. `turn.run`
   raises `PhaseError` if a step runs out of order, so the order is structural.
6. A fortnight window lists the events. The campaign autosaves.

The binding scarcity is attention, not grain. Read a letter 2h, dictate 2h,
dispatch 2h. One complete letter exchange costs 6 of 10 hours, so the court
answers about one and a half tablets a fortnight.

## 3. Mechanics present and working

**Kernel world.** 55 settlements. Each farms, eats, trades, levies and decides
from its own Belief. Sow, tend, reap, set seed aside, share out by
tenure. Mining (new, uncommitted). Caravans, voyages, sea seasons, loss on road
and at sea. Spoilage, hunger, displacement, plague, 11 shock kinds, fall.

**Court.** Rations and payroll, arrears, unrest, legitimacy, resource petitions,
rites, omens, oaths, institutions with decay and upkeep, works
and construction, muster, corvée, levy, trade dues, finance, requisition,
exemption, household, succession, marriage.

**Correspondence.** All ten blocks of the spec are implemented
(`tui/composer.py:27`). 14 authored correspondents write on cadence.
`engine/correspondence_policy.py` answers from the foreign court's own Belief
with accept, counter, refuse, delay or ignore, and no chance draw. Routes,
couriers, latency, interception and archives all exist.

**Belief.** One projection boundary, 48 top-level keys. `source`, `as_of_turn`
and `certainty` are being added across every collection (uncommitted).

**Determinism.** SplitMix64 substreams keyed by seed, turn, domain. Canonical
JSON rejects floats and sets. A save is a seed plus an action log.

## 4. What passes

| Check | Result |
| --- | --- |
| `tools/authority_audit.py` | no findings |
| `tools/inventory.py` | 38 actions, 24 charged, 19 contexts, no faults |
| `tools/corpus_lint.py` | all exemplars above 900 |
| `tools/information_audit.py` | complete |
| `tools/gameplay_probe.py 4 180` | exit 0, no impossible state in 12 runs |
| `tools/m13_benchmark.py` | inside every pinned budget |
| `tools/screens.py all` | 20 screens render, no crash |

Collapse works. Seed 42, no player action, 720 turns: the campaign ends at turn
374, year 15.6, cause "maximum unrest". That is inside the spec target band of
year 15 to 30.

## 4a. What does not pass

`tools/run_tests.py` reports **568 passed, 62 failed** and takes about eight
minutes. Every failure also occurs at the released commit `a267cdd`, so none of
them is a regression from the uncommitted work.

Causes, counted from tracebacks:

| Count | Cause |
| --- | --- |
| 36 | bare `AssertionError` — screen layout and record content drift |
| 11 | `ValueError: unknown Alu 'ugarit'` — the playable Alu is `seat` now |
| 5 | unknown correspondent: `pharaoh`, `byblos_king`, `hatti_king`, `carchemish_viceroy` |
| 4 | missing attributes and keys (`focused_objects`, `palace`, `ended`) |
| 3 | real correspondence assertions (see 5.9a) |

Six test files still hard-code `"ugarit"`. `tests/test_window.py` alone
contributes 11 failures for that one reason. These tests do not track the
content rename and cannot pass.

The three failures in `tests/test_world_terms.py` are different: a delivered
promise, request or marriage proposal no longer records the letter's recipient
as its `beneficiary` or `party`. That is the obligation layer, not a stale
fixture, and it is worth a look before the missing letter kinds are added.

## 5. Problems, ranked

### 5.1 Austerity and passive give identical worlds

The probe prints the same population, seat ratio, grain, unrest, Alu count and
fall list for `passive` and `austerity` on all four seeds. Byte-identical.

SPEC.md 6.4 requires the opposite: "passive and austerity policies produce
meaningfully different material and network outcomes". The probe's own contract
fails. The cause is 5.2.

### 5.2 Grain stops being scarce around year 8

Seat granary at turn 6 is 1,429 parisu. At turn 180 it is 343,096 to 1,363,188
parisu depending on seed. Austerity's trigger is `kept < 6` fortnights, so it
never fires. Food, the central material decision, solves itself and then stays
solved.

`stewardship` banks more grain (802,860 to 1,822,951) and reaches *higher*
unrest (542 to 564, against 157 to 162 for passive). It banks by underpaying
rations, so arrears rise. The probe describes it as the competent policy; on
the numbers it is the one that angers the city.

### 5.3 The seat swells while the world dies

Seed 42, passive: seat population 80,000 at start, 212,530 by year 6, held to
the end. Across the probe the seat ends at 1,820 to 3,160 per thousand of its
opening size.

56 displaced cohorts settle at the seat by turn 144. `engine/displacement.py:104`
settles a distressed cohort as soon as its hunger drops below 3. The
`receive_cohort` action exists and costs 1 hour, but nothing routes through it.
The player never decides whether to take refugees in.

### 5.4 Shocks are weather, not events

897 `ShockLanded` across 12 runs of 180 turns is about 75 per run, one every
2.4 turns somewhere on the map. All 11 kinds fire in every seed. Nothing is
rare, so nothing reads as a crisis. The uncommitted change to
`engine/shocks.py:176` moved from one world roll to one roll per settlement,
which is why the count is now this high.

### 5.5 Falls cluster in one window

Every fall in every seed and every policy lands between turn 139 and turn 175.
Foreign Alus always fall by "population collapse"; the seat always ends by
"maximum unrest". Two causes, one window. The rule is ordinary, but the output
looks scheduled, which is what SPEC.md 7 lists as an anti-goal.

### 5.6 The event stream is unreadable

Late game, one turn produces 767 `hungry`, 122 `news`, 71 `spoiled`, 9
`PlagueProgressed`. Across the probe `kernel:spoiled` totals 368,882 against
`reaped` 12,715. The fortnight window and the developer inspector both read
this list.

### 5.7 Loading grows without bound

`session.load_session` replays every turn from the seed. At the benchmark's
144 ms per turn a year-10 campaign takes about 35 seconds to load, and it gets
worse every fortnight. No state hash is stored, so `play_gui.py:659`'s notice
"Loaded turn N from the verified autosave" is not backed by any verification.
`session.play` still returns an always-empty `hashes` list.

### 5.8 State size

Canonical state is 108 MiB and takes 2.4 seconds to hash at 240 turns. Both are
inside the pinned budget, but the budget was set at 2.5× headroom over a
journal that only ever grows.

### 5.9 Correspondence covers a third of its order kinds

`engine/letter_terms.py` implements `gift`, `request_good`, `promise_good`,
`service` and `marriage_proposal`. SPEC.md 6.2 fixes about 15 kinds from the
corpus. Missing: troops and escorts, raiding complaint, enemy movement report,
oath demand, detained messenger release, dispute referral, physician or
craftsman or scribe request, accession and death, threat to go to a third
court.

### 5.9a Ten percent of the suite is dead or broken

62 of 630 tests fail, and the suite takes eight minutes. The bulk is dead
weight that names an Alu and correspondents the content no longer has. Deleting
those files would cut the failure count by about a third and the run time with
it. The three `test_world_terms` failures are a genuine defect and should be
kept and fixed.

### 5.10 Trade is thin, and its door count is noise

The Exchange tab shows one line, the grain price. The Hall's Trade badge reads
16 at turn 6 because `tui/hall.py:44` counts every voyage as a trade matter,
and most voyages are couriers carrying letters. The badge is meaningless from
the first fortnight.

### 5.11 Rendering defects

- Counsel clips its own text at the frame: "an hour a questio".
- The Works and Orders footers overprint the border: `═[esc] close═╝`.
- The World map advertises "[e] Envoy · not yet wired" to the player.

### 5.12 `play_gui.py` is 4,629 lines

One `Game` class owns the desktop, every room's key handler, the writing desk,
the model threads, and save and load. It is the hardest file in the repository
to change, and it is the one CLAUDE.md's "write it short" rule most applies to.

## 6. Verdict

The simulation is real, conserved, deterministic and inspectable. The room
layer is complete against the spec's nine rooms. The correspondence spine
works end to end.

The gap is the game, not the simulation. Grain solves itself, refugees arrive
without a decision, shocks arrive constantly, and the probe proves the point:
doing nothing and running austerity produce the same world down to the digit.
Fix the material pressure first; everything else in this list is smaller.

## 7. Do now

1. Make the granary a live constraint. Either scale consumption with the
   swollen population or cap the surplus, so `thin` can fire and austerity can
   diverge from doing nothing.
2. Route displaced cohorts through `receive_cohort`. Refusing refugees should
   cost something and change the outcome.
3. Cut shock frequency by about five and raise severity, so a shock is an
   event rather than the weather.
4. Delete the six test files that still name `ugarit` and the retired
   correspondents. Keep and fix the three `test_world_terms` failures.

## 8. Do later

5. Store a state hash in the save and snapshot the world instead of replaying
   the whole log.
6. Fold `hungry` and `spoiled` into per-turn totals; trim the journal.
7. Add the missing letter order kinds from SPEC.md 6.2.
8. Split `play_gui.py` by room.
9. Fix the three rendering defects and either wire Envoy or remove it.
