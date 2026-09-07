# What is left to make the game playable

- Status: working document, subordinate to `SPEC.md`
- Measured: 2026-09-07, at commit `dcc0fe8`
- Every number below comes from a run in this repository, not from reading code

## 1. Where it stands

The simulation is real, conserved, deterministic and inspectable. 630 tests
pass in 19 seconds. `tools/inventory.py` reports 33 player actions, 23 charged,
19 contexts, no faults. `authority_audit`, `information_audit` and
`corpus_lint` have no findings. All nine rooms of `SPEC.md` 3.3 exist and own
their verbs.

The gap is the game, not the simulation.

### The world does not hold

An idle 30-year campaign, no player action:

| Seed | Seat | Alu alive at year 30 |
|---|---|---|
| 1 | survives | 1 of 55 |
| 42 | falls year 16.1 | 18 of 55 |
| 7 | falls year 13.2 | 29 of 55 |

World population goes from 9.50M to 5.63M. Fall causes on seed 1: 23 maximum
unrest, 20 population collapse, 11 raids.

`SPEC.md` 6.4 sets two targets here. The seat's own fall is close to the first:
the band is year 15 to 30 unaided, seed 42 lands at 16.1, seed 7 is early at
13.2, and seed 1 does not fall at all. The second target, "an unshocked world
stays mostly stable", fails outright. Fifty-four of 55 Alu die on seed 1 with
no player and no authored catastrophe, so a player who does everything right
still inherits an empty map.

The cause is a food deficit that compounds. The seat's harvest falls from 4.9M
qa in year 1 to 0.2M by year 8 while consumption stays near 1.5M. Sowing is
capped by work days, and work days fall with hunger, so a bad year makes the
next year worse. `dcc0fe8` raised `HUNGER_FLOOR` from 200 to 600 and gave a fed
roll a way to shed grievance, which moved seed 1 from year 9.7 to surviving.
The remaining deficit is a balance job: yield per person-day, ration size, or
both.

### The player has verbs but no questions

Every allocation is reachable and nothing states its price at the point of
order. The player can set a ration order, but no screen says which cohort goes
to the bottom of the queue or what that costs next harvest. Until that is on
screen the 33 actions are a menu, not a set of decisions.

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

**Broken surfaces.** `tools/screens.py all` crashes with `ValueError: hands can
only be sent just before or during harvest`; the README advertises it as
`./run.sh --screens all`. Four screens print `[esc] close═╝` over the frame
border.

**`play_gui.py` is 4,944 lines** and grew again in the last two commits. One
`Game` class owns the desktop, every room's key handler, the writing desk, the
model threads, and save and load.

**Farm information still owed.** The loss record by cause, the exhaustion
fortnight, and the per-cohort allocation rows. Everything else in the farm
slice is drawn in the Hall, the Land ledger and the Alu, with Help topics
`grain_year`, `person_days`, `river_gauge` and `units`.

## 5. Order of work

1. Make an unaided world stay mostly stable, per `SPEC.md` 6.4. Nothing below
   is a decision until food is a constraint the player can lose to and then
   recover from.
2. Put the price beside every allocation: what it takes, what is left and for
   how many fortnights, and who does not get it.
3. Add `pay_arrears`, then `import_grain` through the letter path.
4. Ration priority as a visible queue with its harvest consequence.
5. Land due and harbour due shown as this year against next year.
6. Works with their payback arithmetic, competing with harvest labour.
7. Levy, corvée and escort priced against the harvest deadline at the order.
8. The remaining letter kinds from `SPEC.md` 6.2.
9. `standing_order`, then re-run `tools/gameplay_probe.py`. The policies must
   diverge further than they do now.
10. Save a state hash and snapshot instead of replaying the log.
11. Fold `hungry`, `spoiled`, `withered` and `news` into per-turn totals.
12. Fix `tools/screens.py all` and the footer overprint.
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
