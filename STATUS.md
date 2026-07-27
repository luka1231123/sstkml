# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive) · M4 (numeric guard + optional prose parser) · M5 (formulae + protocol grader + desk) · M6 (relations, gifts, status, unanswered decay, oaths, protocol consequences, misfortune) · M7 (persona cards, report bias, distorted asserted facts, background generation, prompt boundary) · M8 (climate series, agriculture, labour and corvee, canals, the bronze chain, the melt ledger, workshops) · M9 (the house, reproduction, child mortality, marriage abroad as an agent, the queen mother, succession and the oath reset, divination) · M10 (integer SIR, quarantine, the predecessor archive, `cause_oath_id`, expiation, the librarian) · D25 (troops: task, place, garrison strength, troops on the harvest, the `provide_troops` clause and its summons). 247 tests green. Plays: `./run.sh` (windows) or `./run.sh --cli` (terminal).

**In progress: M12.** The `Institution` entity is in (spec 6.18): six of them
authored for Ugarit, layered over the existing dependent groups, which are
untouched. Condition decays every fortnight — faster where the post is vacant,
faster again where the upkeep goes unpaid — and **the head reports his own
condition**, flattering it in proportion to what he owes his men and never above
960, because a perfect thousand would become a tell. `inspect institution:<id>`
buys the truth for one hour and lapses with the fortnight. The CITY screen (`y`)
shows the reported figure **as a history**, so a level line of reassurance over
a building that is quietly going is the thing the player learns to read.
**Not yet wired: the outputs.** Condition multiplies nothing yet — the harbour
does not gate cargoes, the granary does not gate spoilage. That is the next
commit, and it needs a re-sweep because it touches the tuned economy.

**Next:** the rest of M12 (D39, D40; spec 6.18–6.22). Institutions layered over the existing dependent groups, heads who are people and who misreport, justice and precedent in the hall, the land due and the harbour due, `place` and the heir, and building as a long bet on which crisis is coming. Then M13 — **the world, the envoy, and the standing order** (D35, renumbered): foreign cities carrying the same institutions, seen only as far as the player has travelled. M14 Displacement, M15 scenarios, M16 epilogue.

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

**Known gap, now measured and one inversion fixed (`tools/sweep.py`).** 32 seeds
x 96 turns, both policies. The deficit is sound: **passive empties the granary
and maxes unrest on all 32 seeds**, so no seed has no game in it, and **prudent
never maxes unrest on any seed**, so competence is never punished by weather
alone. Granary first empty under prudent: 59 / 80 / 83 (min / median / max), and
4 seeds never — one year of runway, which is the right shape.

**The bronze chain was inverted and one seed could never have shown it.** Demand
is scaled by the smiths' `output_modifier`, so starving the forge — the obvious
low-risk cut, since smiths do not riot — collapsed demand to nothing, nothing
was smelted, nothing melted, and `bronze_in_circulation` sat at its opening
24,000 for the whole run. Chariotry ended at a **perfect 1000 on exactly the
seeds where the forge went unpaid**. Starving the workshops preserved the army.

Fixed with two terms in `engine/metal.py`: bronze in service **wears** at
`bronze_attrition_per_10000 = 100` (1% a fortnight) whether or not anyone works,
and what the forge **actually makes goes back into service**, capped at
`in_service_ceiling` so it maintains the kit rather than building a hoard. The
rate was swept: at 60 four seeds still ended whole, at 180 the army is gone by
turn 60 everywhere, at 100 no seed ends at 1000 and none ends at 0.

After: chariotry ends 0 / 555 / 840 across seeds. A fed forge holds the kit
while tin lasts and then eats it (melt 16,140, chariotry 130 on the canonical
seed); a starved forge melts nothing and bleeds slowly to ~770. Both lose the
army, for different reasons, at different speeds.

**Still open, and it is a sequencing fact rather than a tuning one:** over 96
turns the payer still ends *worse* than the miser, because tin always runs out
around turn 51 and cannot be replaced. Paying the forge cannot be made the
better play until tin can be **bought** — which is M13's trade network. Do not
re-tune attrition to paper over this; the chain is meant to be closed by trade.
