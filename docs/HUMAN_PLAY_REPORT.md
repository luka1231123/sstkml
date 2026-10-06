# Observed play and fast simulation — 6 October 2026

## Verdict

Promising court simulation, still uneven. My subjective assessment is **6/10**:
real allocations, delayed consequences and returning households make some
decisions interesting. Too many routine claims and cheap recurring cultural
payments can become administration. These are my observations as the coding
agent, not independent player feedback or evidence of commercial demand.

The original movable-window interface is preserved. Research recommendations
and sources are in MARKET_RESEARCH.md; opening measurements and compatibility
details are in OPENING_BALANCE.md and PLAYABILITY_AUDIT.md.

## Actual interface play

I operated the native game through its visible controls, with seed 20261006,
in isolated playtest saves. I did not use an omniscient console to make these
decisions. Three sessions reached Pylos fortnight 4, revised Pylos fortnight 8,
and Alashiya fortnight 4. This is a small opening sample, not a full campaign.

In the first Pylos session I awarded 6,000 copper on a disputed 9,000 claim,
cut palace rations by a quarter, issued workshop bronze, read a grain offer
and saw the unpaid claimant return. The game remembered the earlier award.
However, its food target called the opening covered even though grain would
run out before harvest; its ration display barely explained the benefit of
my cut. Navigating to the payroll took several window changes.

In revised Pylos I paid the full claim, used the Hall's direct action to cut
rations, issued bronze tools, sent a reply through the visible composer and
deferred two grain claims until harvest. At fortnight 8 I paid 190,550 grain
to a ration claimant and 60,000 to injured mason households. Stores actually
fell. The earlier paid creditor had returned with a different household need.
This offers a more convincing story than an isolated bonus notification.
Writing and sealing a letter still takes substantial navigation.

That session exposed a serious defect: a departing group duplicated payroll
and debt, and could consume grain from its old palace while missing the
displayed roll. The engine now apportions debt and allowances and detaches
departing households in new campaigns. A headless reproduction verified
forecast and consumption agree after this repair. The native Pylos session
was **before** this repair; I have not replayed its eight turns in the UI.

In Alashiya I paid the smelter dispute, inspected a finite merchant grain
stock and its price, and sealed a four-payroll purchasing mandate with a
12,000-copper ceiling. The next account showed its effects. A short authored
letter subsequently displayed an actual 4,790-grain offer and 708-copper
quotation, addressed to Alashiya. The tax screen showed what reducing harbour
dues would cost. An unsupported individual toll exemption request was changed
to a request to lower the existing general harbour toll; that final wording
was changed after the native session.

## Changes prompted by play and research

- Hall Enter opens the relevant account; G opens cultural government.
- Rations show the chosen queue's endurance and the closes before harvest.
  Food advice recognises actual available sellers.
- New Egyptian, Hittite and island openings have reserves based on their
  enrolled payroll. Alashiya has finite, merchant-owned supply purchased with
  existing copper, rather than a recurring free stock refill.
- Ordinary incoming letters show authored facts, without background model
  paraphrases hiding quantities or repeating filler. Cultural salutations,
  public names, claim summaries and closing receipts are clearer.
- Cultural grain obligations scale to their recipients. Hittite service
  requires three consecutive closing musters.
- Non-Ugaritic courts use a neutral numbered fortnight calendar rather than
  pretending that Ugaritic month names are their attested local calendars.

## Faster play from here

Run `.venv/bin/python tools/quick_play.py --turns 72` for all eight courts,
or add `--court alashiya` for one. It uses the real engine without Tk or a
language model, public accounts and interface action costs. Results are in
output/quick-play.json. It never writes normal campaign saves.

Its deliberately simple policy buys grain, pays affordable claims and meets
affordable cultural accounts. It does not negotiate foreign imports, manage
succession or optimise the economy. A surviving run is not proof of fun;
a failed run is not proof that a skilled human could not recover. Headless
play is useful for economic consequences; visible play remains necessary
for controls, comprehension and engagement.

Remaining concerns: sustainable island supply after finite opening stocks,
large regional differences in food surpluses, repetitive claims, shallow
recurring government costs, numeric allowances lagging population changes,
and limited visibility of emigrant debt. Long-term enjoyment is unproven.

## Completed three-year headless run

Seed 20261006, current new-campaign rules, four parallel processes: **574
fortnights in 16.59 seconds**. Each court was requested to play 72 fortnights;
Byblos ended at 70 through population collapse. No UI or model was started.

| Court | Fortnights played | First empty granary | Peak ration debt qa | Closing anger |
|---|---:|---:|---:|---:|
| Ugarit | 72 | 7 | 83,075 | 0 |
| Byblos | 70 | 7 | 729,717 | 968 |
| Tyre | 72 | 7 | 178,375 | 1,000 |
| Carchemish | 72 | 7 | 175,539 | 0 |
| Alashiya | 72 | 26 | 1,177,043 | 883 |
| Pylos | 72 | 7 | 643,986 | 49 |
| Egypt | 72 | never | 0 | 0 |
| Hattusa | 72 | 29 | 10,266,989 | 143 |

Five runs recorded one refused grain judgement at fortnight 7: an earlier
judgement had used stocks counted as affordable at the start of the docket.
The engine correctly refused overspending; this simple policy does not retry
that same judgement within the turn. These refusals are retained in the JSON.
The run also exposed and repaired a report crash after a capital disappears:
public salutations and dates now fall back to its retained settlement record.
The complete rerun finished after that repair.

Egypt's enormous closing surplus (71,014,743 qa) and the deficits elsewhere
show that eight supported courts are not eight equally balanced campaigns.
Alashiya's opening purchasing decision works for the first year, but this
policy exhausts copper and supply later. Foreign negotiation is not exercised.
This evidence does **not** justify calling the game finished or sustainably
engaging for many years. It does establish a much faster way to inspect those
problems than operating hundreds of native windows.
