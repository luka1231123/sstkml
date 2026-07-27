# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive) · M4 (numeric guard + optional prose parser) · M5 (formulae + protocol grader + desk) · M6 (relations, gifts, status, unanswered decay, oaths, protocol consequences, misfortune) · M7 (persona cards, report bias, distorted asserted facts, background generation, prompt boundary) · M8 (climate series, agriculture, labour and corvee, canals, the bronze chain, the melt ledger, workshops) · M9 (the house, reproduction, child mortality, marriage abroad as an agent, the queen mother, succession and the oath reset, divination) · M10 (integer SIR, quarantine, the predecessor archive, `cause_oath_id`, expiation, the librarian) · D25 (troops: task, place, garrison strength, troops on the harvest, the `provide_troops` clause and its summons). 247 tests green. Plays: `./run.sh` (windows) or `./run.sh --cli` (terminal).

**Next:** M12 — **the city as a machine** (D39, D40; spec 6.18–6.22). Institutions layered over the existing dependent groups, heads who are people and who misreport, justice and precedent in the hall, the land due and the harbour due, `place` and the heir, and building as a long bet on which crisis is coming. Then M13 — **the world, the envoy, and the standing order** (D35, renumbered): foreign cities carrying the same institutions, seen only as far as the player has travelled. M14 Displacement, M15 scenarios, M16 epilogue.

**What has to be balanced in M12, and where it will fail.** These are the numbers to watch and the failure each one produces if it is wrong:

| number | too low | too high |
|---|---|---|
| institution `base_decay` (4–12/fortnight) | buildings are permanent; repair is never a decision | everything is always broken; the player learns to ignore condition |
| repair cost vs. build cost | building new is always right; the city sprawls | repair is always right; nothing is ever built and M12 has no long bet |
| project `days_needed` (granary 900, wall 4,000) | walls appear every few years and raids stop mattering | nothing is ever finished and the corvée is a tax with no product |
| corvée days vs. harvest need | building is free; the year-later bill never lands | one project starves the estates and the run is unwinnable at turn 20 |
| land due elasticity (flight per 100 points) | tax is free money and the granary stops mattering | one raise empties the estates permanently and there is no way back |
| harbour due lag (3–6 fortnights) | the punishment is instant and reads as a rule, not a consequence | the merchants leave so late the player never connects it |
| verdict legitimacy (±20 / −35) | judging is free and the hall is a chore | one wrong verdict ends a reign and the player stops hearing cases |
| precedent penalty (double) | precedent is flavour | the player is locked into year-2 mistakes forever |
| head misreport size | inspect is never worth an hour | every figure is a lie and the player trusts nothing, which is not tension |

**The two real failure points.** (1) **Attention inflation** — M12 adds hearing, inspecting, appointing and building to a fortnight that already cannot afford to read its post. If the hour budget is not re-tuned, everything new is dead content. The fix is that most of M12 is *free* actions on screens (appoint, name an heir, set a due, order the corvée) and only `hear` and `inspect` cost hours. (2) **Legibility** — a machine with two hidden multipliers, a head who lies about one of them, and a year-long build time can become a system the player cannot form a theory about. The CITY screen has to make condition and output visible *as a history*, not as a number, or the whole thing reads as random.

**Known gap, now measured (`tools/sweep.py`).** 32 seeds x 96 turns, both
policies. The deficit itself is sound: **passive empties the granary and maxes
unrest on all 32 seeds**, so there is no seed with no game in it, and **prudent
never maxes unrest on any seed**, so competence is never punished by weather
alone. Granary first empty under prudent: turn 59 (min), 80 (median), 83 (max),
and 4 seeds never. That spread is one year of runway and it is the right shape.

**The bronze chain is inverted, and one seed could never have shown it.**
Chariotry replacement at turn 96 ranges 0 to 1000 across seeds, and it is
perfectly correlated with whether the *smiths* were paid:

| smiths paid to turn 30–60 | tin runs dry | melted | chariotry ends |
|---|---|---|---|
| yes (mod 520–780) | yes | 13,884–21,864 | **118–562** |
| no (mod 80 by turn 30) | never | **0** | **1000** |

Starving the workshops *preserves* the army. Demand is scaled by the smiths'
`output_modifier` (`engine/metal.py`), so cutting the smiths — the obvious low-
risk cut, since smiths do not riot — collapses demand, nothing is smelted,
nothing is melted, and `bronze_in_circulation` stays at its starting 24,000
forever. That is the exact opposite of 6.5: the melt ledger is supposed to be
the invisible price of keeping the workshops running.

The canonical seed `8814402919` is one where the smiths happen to stay paid, so
every balance report before this sweep showed the mechanic working.

**The fix, not yet applied:** bronze in circulation must decay on its own —
wear, loss, burial — so replacement falls whether or not anything is melted, and
paying the smiths *slows* the fall instead of causing it. One attrition term in
`engine/metal.py`, then re-sweep; the melt ledger keeps its job and the
incentive points the right way.
