# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive) · M4 (numeric guard + optional prose parser) · M5 (formulae + protocol grader + desk) · M6 (relations, gifts, status, unanswered decay, oaths, protocol consequences, misfortune) · M7 (persona cards, report bias, distorted asserted facts, background generation, prompt boundary) · M8 (climate series, agriculture, labour and corvee, canals, the bronze chain, the melt ledger, workshops) · M9 (the house, reproduction, child mortality, marriage abroad as an agent, the queen mother, succession and the oath reset, divination) · M10 (integer SIR, quarantine, the predecessor archive, `cause_oath_id`, expiation, the librarian) · D25 (troops: task, place, garrison strength, troops on the harvest, the `provide_troops` clause and its summons) · M12 (institutions, works, justice and precedent, revenue, appointments, placement, named heir) · TUI dashboard rework (Hall, Counsel, Inbox, clickable controls, retrieval-grounded Help). 338 tests green. Plays: `./run.sh` (windows) or `./run.sh --cli` (terminal).

**TUI dashboard rework complete.** The Hall is now the 104-column home
dashboard: realm state, Belief-only concerns and recommendations, people
waiting, Inbox summary, and grouped destinations. Counsel is the main
ordinary-language ordering interface and commits compound orders atomically
after preflight. The 108-column Inbox keeps triage and tablet reading in one
window. Clickable hit regions sit beside the same glyph grid used by keyboard,
terminal, and ASCII modes; shared contextual footers expose the live actions.
Outgoing correspondence remains parked in `docs/LETTERS_REDESIGN.md`.

**The Palace Tutor is live.** Help is now an always-ready conversation instead
of a static manual. Each question retrieves from `content/help_commands.toml`;
an optional model phrases only those passages and the current projected names,
while offline play answers directly from the same records. The corpus is
required to cover every legal parser verb and every built Hall door. Help and
follow-ups cost no hours and never enter the action log.

**M12 complete.** The `Institution` entity is in (spec 6.18): six of them
authored for Ugarit, layered over the existing dependent groups, which are
untouched. Condition decays every fortnight — faster where the post is vacant,
faster again where the upkeep goes unpaid — and **the head reports his own
condition**, flattering it in proportion to what he owes his men and never above
960, because a perfect thousand would become a tell. `inspect institution:<id>`
buys the truth for one hour and lapses with the fortnight. The CITY screen (`y`)
shows the reported figure **as a history**, so a level line of reassurance over
a building that is quietly going is the thing the player learns to read.
**Four of the six outputs are wired**, and each feeds a system that already
exists: the granary rides on grain spoilage *and nothing else in the cellar*,
the temple on how hard a missed festival lands, the tablet house on how many
hits a search returns (floor of two — a search returning nothing reads as a bug
rather than as neglect), and the forge on **how much new bronze can be smelted**.
The harbour and the walls are deliberately not wired: nothing imports by sea
until M13's trade and nothing attacks until M14, and a multiplier with no
consumer is a number pretending to be a mechanic.

The forge took two attempts and the first repeated the bronze inversion one
level up. Scaling *demand* by the forge's condition made a collapsing workshop
ask for less, melt less, and so **preserve** the army — chariotry ended 761–863
and the M8 target test went red. The chariots need their fittings whether or not
the roof leaks; what a ruined forge cannot do is smelt new metal to supply them,
so the shortfall goes to the melting pot. Condition caps what can be *made*,
never what the court *needs*.

Re-swept, 32 seeds x 96 turns, and it moved the metal story strictly the right
way: chariotry ends **32 / 512 / 578** (was 0 / 555 / 840) and melted-per-
thousand is **424 / 490 / 976** — there is no longer any seed where the melt
ledger stays at zero. 6.5 now fires on every seed rather than three quarters of
them. Granary and unrest are unmoved: 59 / 80 / 83, never maxed.

**Next:** M13 — **the world, the envoy, and the standing order** (D35, renumbered): foreign cities carrying the same institutions, seen only as far as the player has travelled. M14 Displacement, M15 scenarios, M16 epilogue.

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
never empties the granary or maxes unrest on any seed**, so competence is never
punished by weather alone. Under prudent play grain ends at 378,019 / 575,813 /
773,375 qa and unrest peaks at 338 / 401 / 547 (min / median / max).

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

## M12 #10 — building and repair (6.21), done

`Project`, `engine/works.py`, phase A7c, `content/works.toml`, THE WORKS window,
`[r]` on an institution, `build` / `repair` / `abandon` in command mode.

Days come out of `Court.corvee_days` through `Court.works_days`, which
`land.labour_supplied` subtracts — a wall raised in the sowing fortnights is a
wall raised out of next year's grain. Materials are what the men eat, charged
per thousand days worked. Work only happens in `low_water`, and out of season,
out of corvée and out of grain all look identical from the palace.

Measured, seed 8814402919, a ruler who commissions a circuit of walls at Ugarit
and calls up 6,000 days every year: **finished in the fifth regnal year**, two
and a half low-water seasons, at a cost of 20,000 qa of grain, 240 of copper,
and a visibly smaller harvest in the year he did the most of it.

### Two things found on the way, one fixed and one not

**Fixed: oil could stop a wall forever.** The first material rate included oil
at 40 a thousand — trivial on paper. But oil has no source in the game before
trade (M13), so every long run reached a fortnight where the project stopped
dead for want of a lamp and never restarted. A material cost the player cannot
resolve is not difficulty, it is a wall in the road. Grain and copper only now.

**Partly closed by 6.20: oil still trends down in a long run.** The customary
harbour due now brings a small in-kind oil stream from cleared cargo, but it
does not cover the harbour and temple's combined upkeep. The permanent answer
is still **M13 trade**; M12 only makes the customs house a real lever.

## M12 #11 — justice and precedent (6.19), done

Six authored disputes now enter the hall over the opening year. `Petition` keeps
the claim, counter-claim and truth in World; Belief gets only the names and kind
until `hear` buys both stories for an hour, and it never gets the truth. The king
may rule without hearing: `for`, `against`, `split`, or `defer`. Deferral keeps
the men waiting and compounds; a case still standing after six fortnights adds
eight unrest each turn.

Every substantive verdict becomes a `J-…` tablet in the archive. A later case of
the same kind cites the latest one, and a wrong contradiction costs twice the
ordinary legitimacy loss. There is no result on the judgement screen. A
deterministic correction is scheduled two to six fortnights later, when a local
witness's unread tablet reaches the Stack and the legitimacy change lands with
it. The tablet reports what was found, never “right” or “wrong.”

THE COURT OF JUSTICE (`[j]`) is a drawn room: two full standing litigants on the
king's floor, given equal visual weight. Number keys select a petition; `[h]`
hears it; `[f]`, `[a]`, `[s]`, and `[d]` give the four verdicts. The same system
is playable in command mode with `justice`, `hear`, and `rule`.

At the justice checkpoint, the 32-seed economic tails had not inverted. The
final post-revenue sweep is recorded below.

## M12 #12 — land and harbour dues (6.20), done

The land due opens at the customary 300 per thousand. Harvests are now recorded
as gross produce and `LandDueTaken` moves exactly `gross * rate // 1000` into
the crown granary. A rate above custom adds unrest every fortnight and drives a
cumulative share of the estate hands away; lowering the rate stops further
flight and does not restore those households.

The harbour due opens at 100 per thousand and collects a small oil render from
the cargo the harbour actually clears, so condition, staffing and traffic all
matter. Raising it schedules each merchant's response three to six fortnights
later. Until that decision arrives the higher due pays immediately; when it
does, esteem and persistent harbour traffic fall. Both rates are free orders in
THE HOUSE and are available as `landdue` / `harbourdue` in command mode.

## M12 #13 — appointments, placement, and the named heir (6.22), done

THE HOUSE is now an operating screen rather than only a genealogy. It exposes
the adult cast, their qualitative competence and loyalty, every institution
headship, and the succession. A placement can fill an institution, govern a
town, command a formation, or stand at a foreign court. The person moves,
retains the interests accumulated in every office, and an incumbent is visibly
displaced. Dismissal leaves the post vacant and therefore restores headless
decay.

Competence affects output and decay; loyalty affects the report. Commands move
their commander with the formation, and foreign placements become
correspondents with their own report bias. `NameHeir` favours the named son in
the deterministic succession score. Naming the younger over the elder costs 60
legitimacy and raises the elder prince's faction; naming the first son costs
nothing. The same system is available through `place`, `dismiss`, and `heir`.

Final M12 sweep: 32 seeds × 96 turns. Passive empties and maxes unrest on all
32. Prudent empties and maxes unrest on none; end grain is 378,019 / 575,813 /
773,375 and peak unrest 338 / 401 / 547. 338 tests are green.
