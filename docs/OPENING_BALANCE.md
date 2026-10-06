# Opening balance repair — 6 October 2026

New campaigns use opening_rules_version=1. Saves persist that field; missing
fields load as version 0 and retain original stores, merchant supply and replay.
This does not change saved campaigns retroactively or grant recurring grain.

The opening reserve is declared after payroll enrolment, using actual living
cohorts through engine.seat.groups, rather than the authored group sizes.
Egypt, Hattusa and Alashiya start with at least (first harvest turn + 2) payrolls.
The current calendar starts harvest on turn 8, so this is ten payrolls: eight
accounts before its first yield and two for spoilage, awards and forecast error.
Other courts retain their existing opening stocks.

| Court | Actual opening payroll qa/fortnight | Legacy crown grain qa | New crown grain qa |
|---|---:|---:|---:|
| Pi-Ramesses | 1,457,220 | 3,600,000 | 14,572,200 |
| Hattusa | 1,359,500 | 2,400,000 | 13,595,000 |
| Alashiya | 89,870 | 530,000 | 898,700 |

Alashiya also starts with 1,258,180 qa (14 payrolls) of landed grain belonging to
a named grain factor. The factor holds it for local sale rather than exporting
it through the general merchant policy. It is not royal grain: ordinary Trade
or the standing mandate must pay real copper to take title and possession.
Requisition remains possible at its existing unrest cost. All new initial goods
are declared in the conserved Book as authored opening inventory, not created
by an action or invented on shortage. The grain factor is a valid merchant
organization at the player's seat with a holding policy and no autonomous
shipment orders. The factor's stock spoils normally and does not replenish.

## Ordinary first-year progression

Seed 20261006, 24 fortnights, no court judgements or cultural payments. Mandate
runs seal the instruction once before the first advance. These are comparative
engine exercises, not a test suite or evidence of sustained enjoyment.

| Court / policy | Version | Closing grain qa | Peak debt qa | Closing debt qa | Closing copper |
|---|---:|---:|---:|---:|---:|
| Egypt / wait | 0 | 43,840,012 | 6,319,649 | 0 | 105,680 |
| Egypt / wait | 1 | 55,704,654 | 0 | 0 | 104,060 |
| Hattusa / wait | 0 | 7,378,343 | 6,509,423 | 0 | 80,373 |
| Hattusa / wait | 1 | 14,129,722 | 0 | 0 | 78,546 |
| Alashiya / wait | 0 | 0 | 751,663 | 751,663 | 151,140 |
| Alashiya / wait | 1 | 0 | 519,940 | 519,940 | 151,140 |
| Alashiya / mandate 4 payrolls, 3,000 copper | 1 | 0 | 336,402 | 336,402 | 121,391 |
| Alashiya / mandate 4 payrolls, 12,000 copper | 1 | 76,592 | 0 | 0 | 52,551 |

The 12,000-ceiling instruction buys 669,959 qa for 98,589 copper across the year;
533,338 qa remains offered at year-end. Alashiya remains a harder import court:
waiting still fails and an undersized purse still fails. The new supply makes
spending its copper an effective, inspectable decision. The first-year success
does not establish perpetual self-sufficiency. Subsequent years still require
foreign supply, policy changes or renewed trade, and deserve further human play.

Both a two-turn version-1 save and a two-turn legacy-format save without the new
field were saved and resumed. Turn, held stores and complete goods Book matched
before and after replay in each case. The registry checker reported no findings
for either opening. No save-format bump was made.

## Cultural account costs and military service

For opening-rules version 1, the cultural grain award is the larger of 12,000 qa,
the legacy configured quota, and three full ration allowances for its actual
recipient cohort. Pylos uses the palace craft cohort; Egypt the temple cohort;
Hattusa the garrison cohort. The ordinary seed-20261006 opening costs are 15,120,
35,100 and 12,000 qa respectively. This makes the household payment proportional
to the people it feeds, but it remains small beside Egypt's entire royal
payroll: this adjustment alone does not create deep temple politics. Bronze
costs and standing outcomes remain unchanged.

Egypt's assessment description, public progress denominator and completion
threshold use that same temple-based quota. The assessment is measured against
current living temple households, so a change in their population can change
the displayed target while collection is pending. Version 0 retains its old
fixed configured costs and completion thresholds.

New Hittite accounts require three consecutive qualifying closing musters.
Missing a muster before completion resets the count. Once all three are
recorded, service is fulfilled and troops may be recalled before the account's
six-fortnight deadline. The option and public progress explicitly say this.
An ordinary interrupted sequence (campaign, recall, campaign, campaign,
campaign) produced counts 1,0,1,2,3 in version 1 and 1,1,2,3,3 under the legacy
rule; the account was marked served only after its required third muster.

## Departing ration households

Native play revealed another material version-1 food error: cutting the Pylos
palace-dependent allowance to 138,750 qa caused 4,070 of its 18,500 people to
leave on turn 5. Cohort splitting copied the entire allowance and entire ration
debt into both records. The travelling child retained redistributive tenure and
its palace affiliation, so it drew home grain remotely while disappearing from
the canonical ration roll. At turn 6 the public budget was 178,210 qa but actual
royal ration consumption was 259,610 qa.

New version-1 displacement splits allowance and accumulated debt proportionally
by heads, conserving the debt exactly. Departing households leave the palace
roll and institution; their subsistence food entitlement is to their own grain,
not the home granary. Their unpaid claim remains on their cohort instead of
being erased. Version 0 retains the original split and remote feeding semantics.
The general split helper's default also remains unchanged for legacy callers.

With the same cut, turn-5 accounts close before departure at 178,210 qa. After
the departure the remaining 14,430 households' members have a 108,225-qa
allowance, and the next royal budget is 147,685 qa. Turn-6 actual consumption
is exactly 147,685 qa. The 185,000-qa debt at departure divides into 144,300 qa
remaining on the royal roll and 40,700 qa belonging to the departing cohort.

The version-1 local playtest saves made during this development replay with the
corrected departure semantics; their historic reconstructed state therefore
changes. Previously existing user saves are version 0 and retain the old rule.
Departing claims are preserved as cohort debt, but the current palace arrears
payment control addresses households still on its roll. A special workflow to
pay emigrants abroad is not added by this repair. Cohort-owned grain reserves
also remain with their existing owners; this patch does not invent portable
migration cargo or transport grain across the route.

An ordinary 24-fortnight cut-and-recovery run (cut on turn 1, restore the full
remaining-head allowance on turn 6, pay affordable remaining-roll arrears on
turn 9) closed with 3,095,574 qa royal grain, 873 qa canonical debt and 63,583 qa
debt on the departed cohort. The small new canonical debt follows annual births
under a fixed numeric allowance: restoring a full allowance once is not an
automatically growing per-head commitment. Public rolls show the added people.
Latest local version-1 native playtest (turn 8) and older version-0 local
playtest (turn 4) both resumed without action refusals after this repair.
