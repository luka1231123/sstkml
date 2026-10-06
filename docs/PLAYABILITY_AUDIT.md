# Economic playability audit — 6 October 2026

This is an ordinary engine progression exercise, not a human fun score or a test
suite. Root is separately playing the native palace windows. Numbers use seed
20261006, 24 fortnights, and the pre-repair opening (opening_rules_version=0).
The passive policy issues no orders. A simple policy reads public Belief, sets a
4-fortnight grain mandate with a 3,000-copper ceiling, sends palace dependents to
harvest, uses grain payments on cultural accounts, and rules affordable cases.
It does not know hidden events or optimise kernel state. Judgement options were
selected from one opening snapshot; later payments occasionally made an option
unaffordable. Those refusals are not evidence of an engine affordability bug.

| Court | Passive closing grain qa | Peak ration debt qa | Debt fortnights | Passive closing anger |
|---|---:|---:|---|---:|
| Ugarit | 3,366,397 | 65,290 | 7 | 22 |
| Byblos | 406,639 | 35,149 | 7 | 19 |
| Tyre | 340,668 | 7,440 | 7 | 19 |
| Carchemish | 7,246,414 | 157,754 | 7 | 19 |
| Alashiya | 0 | 751,663 | 6–8, 14–24 | 947 |
| Pylos | 2,410,266 | 193,131 | 7 | 29 |
| Pi-Ramesses | 43,840,012 | 6,319,649 | 3–12 | 30 |
| Hattusa | 7,378,343 | 6,509,423 | 2–13 | 31 |

## Demonstrated problems

Egypt and Hattusa started with only 2.47 and 1.77 actual payrolls respectively.
The authored household sizes are not their final enrolled population: the
registry retains actual settlement cohorts. Thus the nominal large granary is
small against the people the game actually feeds. Both eventually produce huge
harvest surpluses; the opening shortage mostly teaches players to endure a
setup mismatch. A conservative versioned repair is recorded in
[OPENING_BALANCE.md](OPENING_BALANCE.md).

Alashiya originally offers no local grain cargo before harvest closes. Its
90k-qa payroll, 530k opening grain and small harvest cause a persistent deficit.
The simple mandate policy still finishes with 704,592 qa debt and anger 887.
Plenty of copper is not an answer to unavailable cargo. A visible, paid opening
supply is needed; an instruction to buy grain alone is insufficient.

Troop harvest assignment is a false affordance. At turn 8, assigning chariotry
to harvest changes the formation task and removes defence, but does not change
public land labour: Ugarit stays at 837,480 days; Pylos at 1,969,680; legacy
Hattusa at 8,943,357. The function describing troop harvest hands is not wired
into kernel farm allocation. Use the real Roll field assignment or disable the
unsupported choice until it works.

The cultural accounts have shallow tradeoffs. Giving 12,000 qa every six
fortnights grants +24 standing/year instead of losing 48, for four court hours.
In late-year Egypt this payment is tiny against tens of millions of grain.
The Hittite muster counts three qualifying closures, even nonconsecutive, and
marks the account served permanently once that count is reached. Recalling the
formation before the deadline then retains the success. This contradicts a
reading of “keep” meaning continuous service. Either say explicitly that three
musters are required or implement a consecutive-service requirement.

## Limits

One seed and one year establish neither long-run balance nor replay value.
Court anger alone can understate suffering: cohorts migrate or shrink while
large royal harvests later clear debt. The five older campaigns have distinct
budgets but a shared opening turn-7 shortage. The public charter harvest aims
are usually already covered by enormous village labour, making additional
palace field assignment a weak choice. Human evaluation should separately judge
whether inspecting a record reveals a usable decision and whether reports show
its actual consequence. Headless progression cannot establish those qualities.
