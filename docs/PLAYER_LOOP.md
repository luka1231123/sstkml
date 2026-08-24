# The player loop

Being king in 1200 BC is one economic problem and one political problem, and
they are the same problem. There is not enough grain, metal, or labour. Every
allocation takes from somebody who will remember it.

The game is: decide who gets what, through orders and letters, under bad
information, before a deadline.

## 1. The two verbs

Everything the player allocates goes through one of two verbs. There is no
third.

**ORDER** — inside the realm. Grain, seed, hands, men, metal, land, works.
An order names a quantity, a recipient, an executor, and a date. It is carried
out by an VEZIER (official) who has his own interests and may perform it badly, partly,
or late.

**LETTER** — outside the realm. Imports, tribute, troops, marriage, oaths,
complaints, requests. A letter costs a ENVOY (courier) and fortnights, and returns an
answer the player does not control.

Everything else in the game is either information that feeds these two, or a
consequence of them. No screen mutates anything. No button allocates.

That is the whole interface contract: **the king writes.**

## 2. The fortnight

1. **What arrived** — tablets, reports, and dilemmas that need a decision.
2. **What must be decided this fortnight** — a short list with deadlines. Some
   items expire; expiry is a decision with a cost.
3. **Orders** — the allocations, written as orders to named officials.
4. **Letters** — what leaves the realm.
5. **End** — the world resolves; the report shows what was expected against
   what happened, and who caused the gap.

Attention limits how many decisions are made well, not how many are made. An
undecided dilemma resolves against the player by default, and it says so.

## 3. The dilemmas

A dilemma is a decision with no free option. Each arrives as a card: what
happened, who asks, two to four answers, the cost of each in real units, who
bears the cost, and the deadline. This is the mini-game — a small, repeated,
legible choice, not a menu of abilities.

### 3.1 Food — the standing problem

Four decisions, on different clocks.

**How much to take.** The land due is a rate on the harvest. High: grain now,
grievance, and less seed left in the villages for next year's sowing. Low:
thin granary, but the countryside sows fully and the harvest is bigger.
The dilemma is this year against next year, and it must be visible as such:
*this rate takes 12,000 qa now and leaves the villages 2,000 qa short of full
sowing.*

[can you write more clearly what rates you're talking about?]

**Who eats.** The ration is not one number, it is a queue. Field cohorts,
palace staff, troops, temple, and the poor cannot all be fed at full ration
when stores are thin. Feeding decides:

- field cohorts — labour per head, so next harvest;
- troops — readiness, so what a levy is worth;
- palace and officials — how well orders are carried out;
- temple — legitimacy;
- the rest — grievance, and unrest is what ends the campaign.

The productivity effect stays small and the political effect stays large.
Hunger should not be a damage number; it should be a queue the player has to
put somebody at the bottom of.

**Whether to import.** Grain for metal, through a letter, at a foreign price,
over a route that takes fortnights and can be lost. The dilemma is metal that
cannot then buy bronze, timber, or an ally, plus the risk that the cargo does
not arrive before the shortfall does.

**How many hands to the fields.** Worth stating exactly, because the engine
already answers it (`engine/kernel/farm.py`):

- land caps the sown extent — hands beyond capacity do nothing;
- seed caps what can be sown in the sowing window at 3 qa a person-day;
- **harvest is the bottleneck at 12 qa a person-day**, and standing crop not
  cut by the last harvest fortnight is destroyed.

[explain exactly what extent is and what otehr mechanics like person days, explain to a casual gamer]

So "more men on the fields" is not a growth lever. It is a deadline problem,
and it collides directly with §3.3. That collision is the good dilemma; the
growth framing is not.

**Delete `eat_seed`.** It is a button that asks the player to do something
obviously stupid, and it hides the real decision. Seed is a consequence: if
the due is too high or the ration too generous, the villages have no seed and
next year's sowing is short. The player should learn that from the sowing
report, not from a menu item labelled "eat the seed corn".

### 3.2 Build or spend

The investment dilemma, and the one that gives the campaign a shape. Metal,
grain, and person-days spent on a work are not available for food, troops, or
gifts, and the work pays back only after it finishes.

Every work is offered with its arithmetic:

| Work | Costs | Returns | Pays back in |
|---|---|---|---|
| Granary | timber, days | less spoilage per fortnight | fortnights, computed |
| Canal or ditch | days, seasonal | more sown capacity | next sowing |
| Wall | stone, days, metal | defence, refuge for cohorts | when raided |
| Workshop | metal, days | bronze, tools, repairs | continuous |
| Road or quay | days | shorter route, more cargo | per movement |

The payback figure must be derived from the player's own believed numbers and
shown before confirmation. The dilemma is legible only if "eight fortnights of
spoilage saved" sits beside "four hundred person-days you will not have at
harvest."

Repair competes with build. A decayed institution is a work that pays back
immediately and gets ignored because it is boring; that is a real choice and
the numbers should make it a real one.

### 3.3 Men

Every man committed is a man not reaping. Levy, escort, garrison, and corvée
all draw the same pool at the same time the harvest does.

- A neighbour asks for troops against raiders. Send them and the harvest is
  short; refuse and the oath is broken, and other courts hear.
- Raiders on a route. Escort the caravan or lose the cargo. [escorts are important in this factor]
- A work needs corvée in the fortnight sowing opens.

Show the conflict at the point of the order: *this levy takes 300 person-days
from a harvest that is already 1,100 short.*

### 3.4 Politics

Politics is the same allocation seen from the other side: every grain has a
claimant, and the claimant remembers.

- **Factions** — palace, temple, landholders, merchants, the countryside. Each
  asks; a grant to one is a refusal to another. No score, only what they asked
  for and what they got, dated. [NOOOO FUCK THIS]
- **Officials** — appointment is an allocation of authority. A competent
  official executes orders closer to what was written. An interested one skims
  or reports what flatters him.
- **Justice** — one ruling spends visible grain or copper and immediately
  changes unrest. Both arguments and all three outcomes are on screen first.
- **Kin and succession** — an heir named, a daughter married abroad, a brother
  given an office or denied one.
- **Temple** — rites cost grain and days and buy legitimacy; skipping them is
  free until it is not. [not until 0.7 is complete]

### 3.5 Abroad

All of it through letters. A foreign court asks for grain, troops, a gift, a
bride, or an oath, and offers, threatens, or goes silent.

- Pay tribute or withhold it.
- Answer a request or refuse it.
- Give a gift now to be owed a favour later.
- Swear an oath — a promise that costs more when broken than it gained.
- Threaten to go to a third court.

Each is a wager on delivery, priced by the tone it was made in
(`SPEC.md` 3.2.2). The expectation is recorded when the letter is sealed and
scored when the answer arrives.

## 4. What each fortnight asks

**Always, and refusing is [not, why are you so obsessed with this idiotic complexity]an answer:**

1. Feed: the ration queue against the stores.
2. Hands: person-days to the season's task, against every other claim on them.
3. One tablet: accept, counter, refuse, or stay silent.

**Each season:**

4. The land due and the harbour due.
5. One work: begin, continue, repair, or abandon.
6. One appointment, against the holder's record.

**When forced:**

7. Refugees arrive: take, refuse, or settle elsewhere.
8. Plague on a route: close it and lose what it carried.
9. Shock: reallocate, or take the loss publicly.

**Once a campaign:**

10. Name an heir. Break an oath. Abandon a settlement.

## 5. What the interface must show

Only what decides these. Beside every allocation, three things:

1. what it takes, in its own unit, from a named store or pool;
2. what is left afterwards, and for how many fortnights;
3. who does not get it.

Beside every projection, its age and whether it is old enough to have changed.
Everything else belongs in a dossier or the archive, per
`PLAYER_INFORMATION_ACCESS_FIX.md`.

## 6. Changes this implies

**Delete:** `eat_seed`. The Trade door count until it counts trade.

**Rewire as orders, not screen buttons:** `allocate`, `set_priority`,
`send_to_harvest`, `raise_corvee`, `levy_cohort` — each becomes an order with
a named executor, a quantity, and a date, and each can be carried out badly.

**Route:** `receive_cohort` — refugees settle themselves today
(`engine/displacement.py:104`), so the dilemma never reaches the player.

**Add:**

| Action | Why |
|---|---|
| `set_ration_priority` | The queue of §3.1. The central food decision, and there is no verb for it. |
| `import_grain` | Buy grain abroad through the letter path, at a foreign price, over a route. |
| `standing_order` | A persistent instruction with a condition and an executor. The king decides what he stops looking at, and delegation becomes a bet. |
| `pay_arrears` | Arrears drive grievance and nothing clears them. |
| `commission_report` | Buy a fact about a place from a messenger, without the six-hour letter path. |

**Fix first:** grain is not scarce after year 8 (`STATE_OF_THE_GAME.md` 5.2).
Until it is, none of §3.1 is a dilemma, and the probe will keep proving that
doing nothing and running austerity produce the same world.

## 7. Order of work

1. Make grain scarce. Nothing below is a decision until this is true.
2. Ration priority as an order, with the queue and the hunger consequence.
3. Land due and harbour due shown as this-year-against-next-year.
4. Works with their payback arithmetic, competing with harvest labour.
5. Levy and corvée priced against the harvest deadline at the point of order.
6. `import_grain` through the letter path.
7. Dilemma cards: deadline, options, costs, who bears it, default on expiry.
8. Standing orders, then re-run the probe. The policies must diverge.
