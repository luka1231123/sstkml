# After the interface pass: an AI-led execution plan

Assessment: 2026-09-16. Subordinate to `../SPEC.md`.
This is a plan, not a record of implemented changes.

Implementation update, 2026-09-16: the controls, decision previews, paged reviews,
assignment/purchase receipts and improved note capture are implemented. See
[the playtest handoff](PLAYTEST_DECISIONS.md) for delivered scope and the known
troop-harvest limitation. Human playtesting and balance measurement remain open;
the numbered sections below retain their acceptance criteria.

## Judgment

The interface pass was worthwhile: one home for judgements, consistent room
names, clearer quantities, shared window sizes and native grid dialogs remove
real friction. Keep those decisions. The next milestone should be **a player
can understand a costly choice and recognize its consequence later**.

Another broad cosmetic pass will not establish that. Finish the controls and
decision previews, observe a beginner, then measure whether different choices
create different recoverable situations. Expand content only after that loop
works. The existing returning shipwright and foreign grain request are enough
to exercise it; neither needs replacing with a new subsystem.

## Evidence and gaps

Reviewed `INTERFACE_PASS.md`, `PLAYABLE.md`, `FIRST_YEAR.md`, `GAMEPLAY_NEXT.md`,
the specification, relevant renderers/controller code and policy tools.
Fresh text renders used seed 8814402919, turn 6, at the real default sizes.
No native-window playtest, balance campaign or test suite was run for this review.
The interface pass's 632 passing tests are historical evidence, not a new result.

| Finding | Why it matters | Priority |
| --- | --- | --- |
| Muster's default render shows the formation artwork but omits `SEND THEM`, task, destination and `[t]`/`[l]` instructions present in its detail data. | The advertised assignment requires controls the player cannot see. Larger defaults did not finish the layout work. | P0 |
| Muster exposes the one-hour assignment cost, but no material or labour comparison in the room. | The player cannot weigh military duty against other uses of those people. Verify the actual engine coupling before promising a harvest penalty. | P1 |
| Storehouse shows “recent” counts and a grain delta without an explicit interval in this render. Trade mixes per-thousand prices with a one-talent purchase. | Arithmetic can be correct while its meaning and purchase scope remain unclear. | P1 |
| Counsel still reserves a fixed portrait column and keeps only the conversation tail. | Long answers and pending orders need usable space and a way to recover earlier context. | P1 |
| Storehouse and Muster still print bare `Enter` in shared instructions. Counsel contains `F1`/`F2` suggestions. | The claim that every control is standardized is broader than the current implementation. Function-key gameplay suggestions also conflict with SPEC §4. | P1 |
| Planning documents describe the removed guided Hall and already-delivered return claims as future work. | An AI following them can rebuild retired features or duplicate work. | P0 |
| Policy divergence and beginner comprehension remain unproven by this review. | Screen renders and deterministic checks cannot establish that decisions matter to a player. | P1 |

Survival at turn 82 is not by itself a balance defect: that is about 3.4 years,
whereas SPEC §6.4 targets unaided failure across seeds at 15–30 years. Investigate
whether waiting avoids meaningful tradeoffs or makes intervention irrelevant.
Do not turn this finding into a requirement to kill the player earlier.

## Execution order

### 1. Establish one current backlog and repair Muster's layout

Read `SPEC.md` first. Reconcile current-status sections of `PLAYABLE.md` and
`GAMEPLAY_NEXT.md`; label earlier measurements and retired designs as history.
Link this plan from the interface pass. Do not silently rewrite product rules.
Record specification conflicts separately: for example, F8 playtest notes versus
the blanket function-key prohibition, and old exception-docket wording versus
the newer Hall dashboard contract.

Fix Muster at default and minimum sizes. Preserve selection, task, destination,
action, refusal and cost before allocating space to art. Make overflow reachable;
do not solve this only by enlarging the window again. Check summons and threat
selections as well as ordinary formations.

Likely files: `tui/ledgers.py`, `tui/workbench.py`, `tui/desktop.py`,
`play_gui.py`, the planning documents.

Done when a player can choose a formation, task and destination, inspect the
order, cancel it, and give it using visible keyboard instructions at both sizes.
Cancellation must not spend time or mutate the world. Retain the existing
desktop tiling contract.

### 2. Finish the price of an order

Start with Muster, then Storehouse/Trade, then Counsel. Use one presentation
pattern, without building a new generic framework first:

- who receives or performs the order, how much, and when;
- immediate goods and attention costs;
- current commitment and proposed commitment;
- known competing demand and the resulting shortfall, where supported;
- the record's date, estimate assumptions and any unknowns;
- confirmation or a specific refusal, followed by a dated receipt.

For Muster, trace `AssignTroops` through the engine and Belief before writing
preview arithmetic. Distinguish reassigning an existing formation from calling
up new people. Show displaced work, food or equipment only where the simulation
actually accounts for it. Missing coupling is a separately scoped engine gap,
not permission to invent an impressive-looking number.

For Storehouse, explain counted, reserved and available goods, and label the
interval behind a change. For Trade, make local purchase, requisition and foreign
request distinct. A preview should identify the payment good/unit, obtainable
quantity and known limits. Foreign acceptance and arrival remain uncertain.
Inspect all Trade tabs, not only its opening Exchange view.

For Counsel, reduce art at small sizes, make useful conversation recoverable,
and keep the complete pending order available before confirmation. Preserve the
existing distinction between free Help and paid counsel. Normalize shared key
instructions and replace gameplay function-key suggestions with controls that
fit the specification.

Likely files: `tui/ledgers.py`, `tui/trade.py`, `tui/relief.py`,
`tui/counsel.py`, `tui/workbench.py`, relevant `belief/` projections,
`registry.py`, and the existing confirmation path in `play_gui.py`.

Done when the player can explain what is spent, who bears the cost, and what is
uncertain before committing. Unknown information must stay unknown. Exercise
insufficient goods, missing destination, stale records and long text, not just
the happy path. Add targeted checks only for meaningful behavior or boundaries.

### 3. Close one decision-to-consequence loop

Use the existing shipwright ruling and grain-relief correspondence as the two
examples. Trace review → confirmed action → receipt → next report → later
claim or delivery. Show the earlier decision where it helps interpret the new
situation, with its actual recipient, amount and date.

Keep “ordered,” “accepted,” “dispatched” and “received” separate. A paid claimant
does not imply a repaired ship. An accepted request does not imply stored grain.
Explain observed differences without attributing every change to the last order.
Check deferral, refusal, partial payment and unanswered correspondence as well
as payment and delivery. Preserve continuity across save/load.

Likely files: `tui/audience.py`, `tui/aftermath.py`, `tui/orders.py`,
`tui/reckoning.py`, relevant Belief records and `engine/justice.py` only where
an authoritative record is demonstrably missing.

Done when a player can find an earlier choice, identify its recorded result,
and understand why a returning matter still needs a decision. Do not expand
the justice system or implement a workshop commission to satisfy this slice.

### 4. Observe a beginner before tuning difficulty

Prepare a separate playtest campaign and a short observation sheet. Ask a
person unfamiliar with the interface to make a first ruling, find its receipt,
give one allocation order, request grain, and reach the next report. Then have
them play a year. Record hesitation, mistaken expectations, hidden controls and
whether they recognize a later consequence. Avoid coaching during the task.

Ask what they expect before confirmation and what they think happened afterward.
Ask what they want to do next at year end. F8 notes can capture seed, turn and
screen; a transcript of successful keypresses is not evidence of comprehension.

The AI can prepare and summarize this session. A human must supply the actual
experience. If nobody is available, record this gate as pending and continue
with measurements; do not claim that an AI playthrough proves fun or clarity.

### 5. Measure choices, then tune only demonstrated causes

Rerun first-year comparisons on seeds 8814402919, 42 and 1, using separate output
directories. Compare waiting, the existing generous recovery policy, and a
clearly described selective policy. Log actual actions and refusals, not just
policy names. Check attention budgets and that choices read only player Belief.

`tools/first_year.py` already provides a Belief-based starting point.
`tools/gameplay_probe.py` currently reads authoritative stores/groups in `_act`;
its policies are useful engine probes but are not automatically evidence of
what a player could know or legally do within a fortnight. Separate diagnostic
policies from player-feasible policies before interpreting their performance.

Compare peak arrears, shortage duration, goods spent, remaining stores, labour
conflicts, unresolved claims, court unrest, actual cargo received and recovery
time. For long runs, also compare population, whole-Alu unrest, foreign survival,
fall dates and causes. Court unrest and whole-Alu collapse are different measures.

Use 24 turns to diagnose the opening, an intermediate run to inspect recovery,
then up to 720 turns for the long-campaign target. Keep calm-world and campaign
runs separate. Publish revision, seeds, policy rules and measurements.

Tune one causal bottleneck at a time only after identifying it: timing of relief,
allocation competition, shock severity or recovery capacity. Preserve calm-world
stability. Do not require active play to dominate every metric; protecting one
group may reasonably cost another. The gate is a visible, explainable tradeoff
with a playable recovery path, not an arbitrary score difference.

## Later work, after this milestone

Continue the correspondence release boundary in SPEC §6.2 before expanding
justice or sensory polish. Inventory implemented letter kinds and obligation
lifecycles against the specification; choose the next complete end-to-end case
instead of adding several inert choices to a menu.

Standing orders and commissioned reports need a concrete repetition or
information problem demonstrated in play. Profile save/load on current code
before prioritizing persistence work. `session.py` still replays action logs;
the older proposal to replace this with snapshots conflicts with SPEC §5.3.
Any checkpoint design needs an explicit specification decision and replay
equivalence, compatibility and corruption handling.

`play_gui.py` is now 5,411 lines. Extract room handlers incrementally when working
on those rooms, preserving controller behavior; avoid a whole-controller rewrite
alongside gameplay changes. Aggregate noisy reports for readers while retaining
the authoritative events needed to reconstruct outcomes.

## Instructions for the implementing AI

Work through the numbered slices in order. Deliver small reviewable changes;
do not treat this plan as authorization to invent new mechanics or override
`SPEC.md`. Before each slice, inspect the current tree and verify that the gap
still exists. Keep simulation authority in the engine, player information in
Belief, and model output limited to grounded language.

For each delivery, report the user-visible change, touched files, evidence,
remaining uncertainty and next gate. Update current status without presenting
planned work as completed. For layout changes, render representative states at
default and minimum sizes and inspect them in native Tk before claiming visual
completion. For semantic changes, run the relevant focused checks and authority,
information and conservation gates; exercise save/replay when state changes.
Follow SPEC §5.5 for release verification. Do not rerun broad tests for prose edits.

**First assignment:** reconcile the backlog and make Muster's complete assignment
flow visible at default and minimum sizes. Show the before/after evidence, then
proceed to its grounded cost preview. This is the smallest useful next delivery.
