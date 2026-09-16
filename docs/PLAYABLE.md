# What is left to make the game playable

- Status: working document, subordinate to `SPEC.md`
- Measured: 2026-09-07; original campaign figures at `dcc0fe8`, calm-world
  verification and screen repairs after `d382965`
- Every number below comes from a run in this repository, not from reading code

## Current handoff — 2026-09-16

The decision-review implementation is ready for a human playtest. See
[the route and note instructions](PLAYTEST_DECISIONS.md). Muster's controls,
grounded defence comparison and confirmation are implemented; local purchases
show estimates and actual receipts; Stores, Orders, Counsel and long reviews
have reachable overflow. Hall O opens Orders. F8 notes attach the originating
screen and wrap long text. Help describes the new controls.

The earlier dated sections below are historical measurements and proposals.
In particular, the guided Hall is retired and the returning shipwright is already
implemented. Neither should be rebuilt from those paragraphs. The current work
queue is [AI_NEXT_PLAN.md](AI_NEXT_PLAN.md). Human comprehension, long-run policy
divergence and campaign balance remain open. Troop harvest duty currently adds
no kernel farm labour; use the working Land/Rations allocation path.

## Court first, then the Hall — playtest revision

The primary screen is now Court. Each fortnight brings a single petition,
messenger or urgent matter forward. Judgements and letter reading happen in
place; reply drafting returns to Court when sealed. Deferring hides a matter
for the current audience only; it returns next fortnight, with normal engine
consequences. Tab ends Court and opens the Hall, which is a dashboard of the
year, stores, standing, rations and labour, waiting matters and motion, plus the
doors. SPACE in the Hall ends the fortnight. Last report is reached with L.
Help is drawn as a game screen with Manual and Ask halves, not a Tk notebook.
The order review, the officeholder picker and the playtest note are grid
windows too; no Tk widget is left in the game.

The palace's judgement view is deleted. Claims are heard in Court and nowhere
else, and the room is named the Palace. Default window sizes were measured
against what each screen actually draws: the Palace shows five rows of people
instead of one, the Shrine opens at the size it was drawn for, and two windows
still fit side by side. Contracted notation is gone: the Shrine says what
skipping a rite costs, the Land says a due in qa per thousand, and the Roll
prints one number where it used to print an arrow between two equal ones.

Removed the guided briefing module, unsolicited adviser lines, duplicate
Audience/Advice tabs in the people workbench, and redundant report prose.
Institution details are free to open; inspection is explicit. They have an
appointment picker, existing officeholders appear alongside the household,
and the overview leaves staffing and history details to the selected building.

Order reviews use a modal Confirm/Cancel window, preventing an unrelated
Escape from cancelling a lingering draft. Works and institution windows now
recompose on resize. Open letters with no structured verdict are no longer
called sealed. New outgoing letters omit reply acknowledgement and empty
terms by default; the optional Terms section can be removed. Help has Ask and
Controls tabs, reads player-visible records and costs no court hours.

Validation: 107 targeted checks passed, authority/information/inventory gates
passed, all screen renderers completed. A native Tk smoke run checked Court,
modal cancellation and confirmation, next-fortnight return, appointment picker
and Help tabs. Save version remains 29: this revision changes interaction and
presentation, not simulation balance. The turn-82 passive-play finding remains
an open gameplay problem; the new structure is not evidence that it is solved.

## Returning characters and playtest — 2026-09-15

Rulings now retain the actual award, recipient and turn in authoritative state.
Three fortnights after the shipwright's first ruling, he returns either over the
unpaid copper balance or with a separate household grain request after full
settlement. Both allow zero-payment refusal. No repaired ship or workshop
output is fabricated. Some waiting claims add a disclosed, small unrest cost
after two fortnights; this remains court pressure, not whole-Alu collapse.

The Hall gives the granary steward and master smith competing priorities.
The year-end report names actual awards and outstanding claims; it does not
declare victory. The opening reserve is 700,000 qa. Relief prompts now consider
known route time plus a handling/cargo margin, still without guaranteeing help.

Six complete first-year runs (waiting and recovery policies on seeds 8814402919,
42 and 1) reached turn 24 without action refusals. Waiting incurred 65,290 qa
peak arrears on turn 7, then recovered at harvest; it left three claims and
court unrest 19. The generous recovery policy incurred 83,075 qa peak arrears,
resolved four claims and ended at court unrest zero. Its grain request received
an accepted answer on two seeds; seed 42 remained unanswered. Paying everyone
is not an optimal food policy. Both policies ended without ration debt; the
post-harvest economy remains forgiving and needs human feedback.

Targeted engine, replay, controller, compact-screen and desktop checks passed,
as did authority, information, inventory and corpus gates. A real Tk smoke run
opened the Hall and saved a multiline F8 note with seed, turn and screen while
preserving the world hash. Save version 29 reflects changed court behavior and
opening goods. `--playtest` creates a separate autosave folder; notes remain
local and ignored by Git. Human fun/clarity feedback is the next gate.

## Beginner's opening — 2026-09-15

New campaigns open a guided Hall with the ruler's identity, food coverage,
plain units, the next seasonal change and three visible matters at a time.
All remaining matters are reachable with arrows. Each selection names a
speaker, the known facts, the competing cost and a direct route to a record.
Enter opens the correct ledger or tablet without giving an order. Tab returns
to the full palace; the choice survives saves without changing replay.

The first inspection leads into a named, state-backed court dispute. Court
payments and unrest are written out separately, and a confirmed judgement
returns a receipt naming its recipient. The Hall explains the last action's
result and makes clear that matters may wait. No new crisis or tutorial reward
is fabricated. Reopening received post preserves an unfinished letter draft.

The next fortnight carries named judgement receipts and still-waiting claimants
forward. Recent ration, repayment and field orders appear beside the new roll.
Receipts are not repeated on subsequent turns. The report distinguishes these
records from a causal explanation of every change.

Validation: 120 distinct targeted checks passed (119 in the broader run, then
15 focused checks including one new continuity check). Authority and information
audits are clean, all standard screens render, and the startup check finds Tk,
the display and the supported model ready. A human beginner playtest remains.
See [the comparison and remaining work](GAMEPLAY_NEXT.md) for the next milestone:
a returning character whose situation materially depends on an earlier ruling.

## First-year slice — 2026-09-13

Arrears payment is now connected to the Roll: R drafts, brackets adjust, Enter
pays once and Escape cancels. The preview excludes reserved grain and shows
remaining debt and the next queue. A payment does not instantly erase grievance.

Trade's Relief view prepares a grain request to a known court, with quantity,
route and reply-time estimate. The normal Scribes workflow edits and seals it.
It is a request, not a priced purchase or guaranteed import. Parsed written
requests now become dispatched terms; conflicting attached quantities stop
sealing. Reopening the same draft preserves the writing.

Foreign replies had been looking up local counts under place names instead of
settlement IDs, causing repeated delay. The policy now uses the corresponding
settlement's believed own goods and food requirement. Acceptance still passes
through the real granary and physical cargo path. This semantic repair advances
saves to version 28; version 27 logs cannot replay under the changed rules.

Harvest orders now require review of the future working fortnights, shared
standing crop, labour capacity and deadline shortfall. Estimates hold crop and
strength fixed; they do not promise allocation or yield. Orders retain a dated
receipt. The fortnight report compares queue estimates with recorded arrears,
compares standing crop counts, reports cargo receipts and changes in letter
status. All report lines scroll, and the last report survives save/load.

`tools/first_year.py` compares a passive year with a simple policy whose choices
read only player Belief. On seed 8814402919, both reach turn 24 with zero ration
arrears. Reported closing grain is 3,664,173 qa for waiting and 3,720,566 qa for
recovery. Recovery gives three orders (request, field assignment, reading the
reply); its request is accepted. Neither run has an action refusal. This is a
reproducible end-to-end exercise, not evidence that campaign balance is finished
or that the policy is optimal. The original long campaign figures below remain
historical measurements and need a new run before release.

Validation: 127 targeted regression checks pass, including controller flows,
physical relief cargo, ration conservation, save/replay and unread-answer
boundaries. Authority, information, inventory and corpus audits are clean.
All standard screens render; the new flows were inspected at minimum sizes.
The existing 240-turn benchmark passes at 149.316 ms per turn, with a
1.899-second state hash and 101,507.7 KiB canonical state. Tk, display, Ollama
and the supported local model pass the startup check. No human playtest has
been recorded for this slice.

See `docs/FIRST_YEAR.md` for the playable route through these decisions.

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

**Remaining verbs.** `standing_order` and `commission_report`. `pay_arrears`
now clears ration debt, and the Relief view uses existing goods-request letters
for foreign grain. There is no separate instant-import action. Without standing orders the king re-decides the same
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

**Trade.** Exchange shows grain and tin prices and local grain purchasing.
Relief now exposes foreign grain requests and reply estimates. Priced bilateral
barter and richer negotiation remain outside this first-year slice.

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
3. Done in the first-year slice: `pay_arrears` and grain requests through letters.
4. Ration queue and immediate work-capacity consequences completed. Compare
   field capacity against the seasonal harvest deadline with item 7.
5. Land due and harbour due shown as this year against next year.
6. Works with their payback arithmetic, competing with harvest labour.
7. Harvest send/recall now shows deadline arithmetic. Levy, corvée and escort
   still need their own comparisons where they compete with field work.
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
