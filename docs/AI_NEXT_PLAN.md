# Make the game understandable and dependable before expanding it

Assessment: 2026-09-21, revision `6df0d04`, clean working tree before this review.
This replaces the previous execution plan. `SPEC.md` remains the product authority.
This document proposes work; it does not record that work as delivered.

## 1. Starting judgment

The owner reports that nothing feels intuitive or clear, features are hidden,
and supposedly working actions do not actually work. Treat that as a failed
playability gate, not as a request for a better manual. Do not answer it with
passing test counts or a list of implemented systems.

There is substantial machinery to reuse: Court, ledgers, correspondence,
reviews, receipts, return claims, reports, saves and a deterministic simulation.
Its presence does not establish that a player can use it. The next milestone is:

> Without coaching or memorized shortcuts, I can find a useful action, understand
> its immediate cost, do what I intended, tell whether it happened, and later
> recognize its result.

Hidden foreign information is intentional. Hidden controls, unexplained units,
unclear focus, ambiguous order status and silently ineffective intentions are
not the information constraint that makes this game interesting.

Work in this order: **trustworthy actions → discoverable workflows → recognizable
consequences → worthwhile choices → wider alpha scope.** Repair each workflow
through all three of the first steps before moving to the next room.

## 2. What this review actually established

Reviewed the specification, current and historical plans, saved playtest notes,
first-year output, controller, rendering, note capture, parser, letter terms,
save system and policy tools. Fresh headless renders examined turn-1 Court,
Hall, Storehouse and Muster. Small direct probes exercised letter parsing and
term validation. No native-window interaction, new balance campaign, full test
suite or human acceptance session was performed. No game code was changed.

| Evidence | Finding | What it means for work |
| --- | --- | --- |
| Owner's current report; earlier local notes | Replies and counsel have failed; navigation and wording remain confusing; the owner does not trust the interface. | Reproduce the actual interaction before choosing a fix. Earlier repair claims do not close these reports. |
| `ai/commitments.py`, fresh probe | `Send me 1000 qa of grain.` produces a request; `Please send 1000 qa of grain.` and `I need 1000 qa of grain.` produce no terms. | Ordinary intentions can become prose without the intended action. The current review labels unmatched text `unparsed`; that is not sufficient explanation or recovery. Do not claim all paraphrases should automatically have identical intent. Ask the player to resolve ambiguity. |
| Same parser and engine term validation, fresh probe | `I send two talents of copper.` produces a gift quantity of 2, which validation accepts. Copper is counted in shekels. | An unsupported unit is being discarded instead of converted or rejected. Fix before treating free-text orders as reliable. Do not invent a conversion without an approved unit rule. |
| Same probe | `I will send 1000 qa of grain.` creates a promise with due turn 0; validation refuses it because a future date is required. | The plain-language path does not collect information its engine requires. An explicit attached term may supply the date; that does not make the text-only workflow discoverable. |
| `play_gui.py:on_audience_key` | In Hall, Enter and Space both advance the turn; only Space is advertised for that action. | A familiar open/confirm key has a consequential, unadvertised meaning. Verify actual focus behavior and remove the accidental-turn path. |
| Fresh turn-1 render | Hall cuts a matter off as `The walls of ugarit is fa…`; Court prices a claim without showing the available copper alongside it. | Critical meaning and affordability still require inference or navigation. Presence of a quantity is not a complete decision. |
| Current docs and `belief/muster.py` | Assigning a troop formation to harvest supplies no additional kernel farm labour. | A selectable duty implies an effect it does not produce. A disclaimer is not the final repair. Provide the working labour path clearly; implement any coupling only as a separate conservation change. |
| Fresh screen-tool invocation | Rendering the desk at turn 1 raises `IndexError` because no incoming tablet exists. | This is a developer-tool failure, not proof that the native desk crashes. Repair empty-state coverage so review tools do not only inspect convenient states. |
| Local human note at turn 82 | After the opening food problem and first harvest, advancing time felt sufficient and nothing else mattered. | Investigate the post-harvest decision drought after basic interactions work. Survival at 3.4 years is not itself wrong under the 15–30-year collapse target. |
| Existing first-year comparison, historical | Passive play on the three recorded seeds ended with 3,366,397 qa and zero arrears; generous recovery spent more and cleared court claims. | Some outcomes differ, but this does not demonstrate engaging choices or a reason to keep playing. These figures were not rerun for this review. |

September 16 note files explicitly describe native smoke checks. They are not
new human approval. Earlier human notes exist and must not be replaced by the
incorrect blanket statement that no human feedback has been recorded.

## 3. Milestone A — capture failures and make one dependable route

### A1. Establish one small failure register

Import the existing human notes first. Keep original wording and references to
the local note file/line. Separate automated smoke notes from human feedback.
For each issue record:

- the player's goal, expected result, actual result, and impact;
- build, save version, seed, turn, originating screen and reproduction route;
- observed evidence, suspected cause, and what remains unknown;
- one next task, acceptance conditions and status.

Use statuses `reported`, `reproduced`, `implemented`, `interaction verified`,
`player accepted`. An agent may advance the middle statuses with evidence. Only
actual human feedback may establish player acceptance. Old reports can be
marked `not reproduced on this build`, never silently called fixed.

Start with failed letter replies, counsel failures, hidden actions, accidental
turn advancement, wrong letter quantities and unsupported troop harvest duty.
Repair campaign corruption or accidental spending first, blocked core actions
second, discoverability third, repetition and balance after that. Do not let a
large backlog obscure the one next delivery.

### A2. Strengthen the existing playtest capture, narrowly

Current F8 capture already saves the originating screen as text, seed, turn,
hours, action count and three recent confirmed orders. Ctrl-Enter writes
`notes.jsonl` beside the separate campaign autosave. Reuse it.

Add a small run manifest: revision/dirty indicator, save version, campaign,
seed, start time, configured model, and display/font settings. Add note IDs and
timestamps. Capture the active tab, selected object, pending review, last
refusal/error and operation status where available. Keep a bounded diagnostic
trail of attempts and results: failed clicks, refusals and model errors are not
represented by three successful orders.

At note time, preserve a diagnostic copy of the action-log save and relevant UI
state, with a reference from the note. The autosave will otherwise advance past
the failure. This is not a new snapshot save format. Do not call the model or
advance the simulation to capture a note. Preserve unsent drafts and pending
review context separately where needed to reproduce UI bugs. Keep developer
truth out of the player's display.

Provide one small local note-summary/export command, not an analytics dashboard.
It should group related reports, retain raw references, identify unknown build
information in older notes, and produce one proposed next task. Notes remain
local; no automatic external upload.

Keep this to small deliveries. Build identification and reproducible note context
come first; export convenience must not hold up a critical gameplay repair.
Do not turn playtest support into a telemetry project.

**Gate:** a note about a failed action contains enough evidence to investigate
without asking the owner to reconstruct the whole session. Note capture itself
does not spend attention, submit an order or alter campaign state.

### A3. Repair the first trustworthy workflow: read and reply

Correspondence is central to the game and has both human failure reports and
freshly reproduced semantic defects. Own the whole route:

`arrival → read → reply → edit → review → confirm → sent receipt → later status`

1. Reproduce the reported reply/seal-state problem from available saves. Track
   letter IDs across resorting and reading. Do not diagnose it from prose alone.
2. Make the current letter, read state, recipient and Reply action visible.
3. Keep free writing, but show exactly which action the engine understood. If
   a sentence asks for an unsupported or ambiguous action, explain that it will
   not request or transfer anything and offer a concrete correction route.
4. Validate quantities and units. Accept canonical units; reject unsupported
   ones explicitly until a conversion is defined. Never ignore a unit word.
5. If a promise lacks a due date, collect one visibly before confirmation.
6. Keep the correspondence blocks required by SPEC, with sensible existing
   defaults and recoverable detail. Do not make finding the Terms block a secret
   prerequisite for an otherwise ordinary request.
7. Show hours, immediate transfers, deferred commitments and uncertainty
   separately. “Request grain” must not look like “receive grain.”
8. Cancellation preserves the draft and costs nothing. Confirmation occurs once;
   repeat input must not double-send. A refusal leaves an editable draft and a
   specific reason. Model failure must leave a visible recovery path.
9. After sending, show the recipient, recorded request, cost and status beside
   a way to revisit that letter. Later, distinguish accepted, loaded, travelling
   and received only where the player's records establish them.

Likely seams: `ai/commitments.py`, `tui/composer.py`, desk/inbox handlers in
`play_gui.py`, `engine/letter_terms.py`, existing correspondence checks. Split
parser safety, missing-date recovery, reply state and visual workflow into
separate deliveries. Do not rewrite the entire controller.

**Gate:** native interaction can complete, cancel, reopen, fail and retry this
route; committed terms match the visible review; save/reload preserves them.
Then the owner can reply in their own words without a supplied magic sentence.
Successful scripted dispatch alone does not pass.

**Current delivery status — 2026-09-21.** **Implemented:** polite canonical
grain requests, unsupported-unit refusal, missing-promise-date recovery,
pre-send terms/cost/uncertainty review, cancelled-draft retention, and opening
the recorded sent copy after confirmation. **Interaction verified:** a separate
native playtest read a tablet, wrote and cancelled/reopened a request, sent it
once, and retained its outbox record across save/reload; unsupported units,
missing promise dates, and insufficient attention were shown as refusals.
**Human acceptance pending:** the owner has not yet played this repair.

**2026-09-22, from the 2026-09-21 playtest notes:** Hall Enter no longer ends
the fortnight (only Space); Court shows who each party speaks for and the
palace's holding of the claimed good; Hall matter titles wrap instead of
truncating; the desk says a wrong address may be too low or too high. Aid
is now a loan (`engine/aid.py`): each request delivered costs 40 esteem; grain
received opens a debt due in 12 fortnights, repaid by gift of the same good;
default costs 250 esteem and sends raiders from the creditor or a neighbour.

## 4. Milestone B — make the rest of the basic loop discoverable

### B1. Establish a screen contract through one real screen

Before coding a broad redesign, show one realistic Court/decision mockup or
running revision. It should answer, in a compact layout:

1. Where am I, and what or whom have I selected?
2. What is the current issue, and what information is known or dated?
3. What can I do here, in plain verbs?
4. What will this cost now, and what commitment or uncertainty remains?
5. Did the last action happen, fail, or remain a draft?

For the shipwright, show the amount claimed, counterclaim, available copper,
three actual payment options and the cost of waiting together. Do not fabricate
ship repairs or future rewards. Put names and evidence in optional detail when
they do not help the immediate choice. Explain a unit next to its use or in an
accessible detail, not with repeated paragraphs on every screen.

The design must work through visible controls with mouse or keyboard. Printed
shortcut letters supplement labelled actions. Show which control has focus;
show unavailable actions with a specific reason. Essential actions and costs
stay visible at minimum supported size; detail may page with a visible page
indicator. Artwork gets the remaining space.

Keep Court-first and the existing room architecture for the initial repair.
If the prototype shows that those rules obstruct use, propose a precise SPEC
change before implementing a larger structural change. Do not preserve a bad
layout merely because an earlier plan described it as complete.

### B2. Repair journeys, not all screens at once

| Order | Player goal | Required result |
| --- | --- | --- |
| 1 | Hear a claim and make or defer a ruling | Comparable costs beside the choice; receipt names who was paid; deferral is clearly unresolved. |
| 2 | Work out whether food will last and change its allocation | Food estimate, counted/reserved/available distinction, recipients and working labour controls are reachable without guessing room names. |
| 3 | Buy grain or request help abroad | The two actions expose their different payment, timing and uncertainty; actual purchase receipt is accessible immediately. |
| 4 | Move troops or contribute labour | Named source and destination, current/proposed duty, known defence change; no effective-looking harvest command without real labour effects. |
| 5 | Appoint an official or inspect a building | Selected office, existing holder, candidate and cost are visible; opening an object is distinct from spending an inspection hour. |
| 6 | End a fortnight and understand the report | Only the advertised end-turn input advances time; changed results and unresolved orders lead back to their evidence. |
| 7 | Ask for help or advice | Free controls/help and paid counsel are distinguishable; pending generation, failure, retained history and reviewed orders remain usable. |

Bring a concern directly to the relevant object/control, not merely to the
room's default tab. Keep a consistent way back. Do not duplicate the full
allocation system on the Hall or restore the retired flood of adviser prose.
Audit every visible control in each repaired route against its handler, including
empty data, low hours, unaffordable orders, long text and model failures.

**Gate per journey:** the owner finds it, can explain the immediate effect,
performs it, and recognizes the receipt without coaching. A user stumbling on
the same step reopens that issue even if all automated checks pass.

## 5. Milestone C — make consequences worth following

Use the existing shipwright and relief request first. Do not add characters to
conceal a weak connection between an order and its outcome.

For each, follow `decision → receipt → subsequent record → changed situation`.
A returning claim should identify the earlier payment and why this claim still
exists. A grain answer must be distinguished from a delivery. Reports should
separate what was ordered, what was observed to happen and what is still unknown.
Use actual records; do not explain every grain change as the effect of the last
order. Reduce report noise while preserving causal events for the developer.

Then inspect the post-harvest period highlighted in the turn-82 feedback:

- Which decisions become available, and does the player notice them?
- Does waiting avoid a real cost, or does it quietly harm something unreported?
- Are offices, trade, defences, obligations and relationships connected enough
  to make maintenance or preparation worth doing?
- If food is safe, what existing problem can the player reasonably choose next?
- Is there a recovery path after a bad choice, visible early enough to use?

Separate three diagnoses: the consequence exists but is hidden; the action has
no useful material coupling; the world currently offers no meaningful choice.
They require different changes. Repeating urgency text fixes none of them.
Add the smallest missing coupling or in-scope situation only after identifying
which case applies. No artificial emergency each turn, reward for clearing every
claim, automatic hostile court, or mandatory punishment for waiting.

**Gate:** the player can describe a consequence of an earlier choice and names
something they want to pursue next. A safe year is allowed; a year where nothing
seems worth doing is a failed engagement check.

## 6. Milestone D — measure choices, then tune balance

Existing first-year policies read Belief and account for action hours, but they
are headless scripts and bypass interface discovery. They do not prove UI
usability. `tools/gameplay_probe.py:_act` reads authoritative state and does not
enforce the player's attention budget. Keep those runs labelled engine
Diagnostics until player-feasible policies are supplied.

1. Add a selective policy alongside waiting and generous recovery. Document
   actual triggers, actions, information and tradeoffs. Check Court phase rules
   and information costs as well as action hours. Log skipped actions, refusals
   and purchases/deliveries, not only ending totals.
2. Compare seeds 8814402919, 42 and 1 for 24 turns, with separate output paths.
   Then run to 96 turns to cover the reported post-harvest boredom, followed by
   broader seeds and up to 720 turns when intermediate behavior warrants it.
3. Measure shortage duration, peak arrears, goods spent, actual cargo received,
   labour conflicts, unresolved claims, recovery time, and occasions when the
   policies faced a visible consequential choice. For long runs, include world
   population, whole-Alu unrest, foreign survival, player fall and cause.
4. Keep calm-world runs separate from shocked campaigns. Change one demonstrated
   cause at a time, rerun the same comparison and record revision and parameters.
5. Return the changed scenario to human play. Different numbers are not enough
   if the tradeoff still cannot be perceived or influenced.

Active policy need not win every metric. Feeding more people may cost reserves.
Do not tune to force an earlier death: SPEC targets unaided collapse across
seeds around years 15–30, with unshocked stability and survivable individual
shocks. Human readability and material policy comparison are separate gates.

## 7. Milestone E — finish alpha scope and release reliability

Only after the basic routes are accepted:

- Inventory every correspondence kind required by SPEC §6.2 against composing,
  deterministic meaning, review, dispatch, travel, response, consequences,
  player visibility and replay. The five current term kinds are not proof that
  every required interaction exists. Implement one complete case at a time.
- Trace the four required obligation families—goods, labour/troops, tribute,
  oaths—through due date, debtor, creditor, remedy and actual fulfillment/default.
  A stored record or a menu choice alone does not complete a lifecycle.
- Repair missing room interactions that matter to these cases. Keep justice
  and religion small; do not expand to more playable courts or a workshop saga
  before the one playable seat is dependable.
- Profile actual startup, model response, turn resolution and save/reload at
  representative campaign lengths. Show progress and recoverable errors where
  waits occur. Preserve the specified action-log replay; snapshots require a
  separate product decision, not a stealth performance fix.
- Run the small SPEC §5.5 release gates: authority, inventory, conservation,
  compilation, save/load smoke, representative runs and pinned benchmark.
  Also perform native interaction on the supported display sizes and runtime
  model failure/retry. Restore and continue a playtest campaign.

Standing orders, extra advisers, sound, decorative art and broad controller
refactoring wait for a demonstrated problem they solve. Extract a room handler
only when necessary for a bounded repair, without mixing that refactor with
unrelated mechanics or balance changes.

## 8. How the owner uses playtests to steer the work

Start with the existing separate campaign mode:

```sh
./run.sh --playtest seat 8814402919
```

Use F8 at the first confusion or unexpected result. A short note is enough:

> Trying to: reply asking for grain.
> Expected: a request for 1000 qa.
> Happened: I cannot tell whether I sent anything.

Ctrl-Enter saves. Escape closes while keeping the note draft in the session.
Current files are `saves/seat/playtest-<timestamp>/notes.jsonl`, beside autosave.
Current note context is useful but does not yet include the proposed manifest,
error trail or per-note save copy. Do not assume those additions already exist.

Use three kinds of session:

| Session | What the player receives | What it decides |
| --- | --- | --- |
| Short discovery, about 10–15 minutes | A goal, such as “reply to this letter asking for food”; no shortcut recipe. | Can the player discover and understand the route? Stop at a blocking failure. |
| Focused regression, about 5–10 minutes | The specific old failure and the repaired build. | Did the fix actually solve the problem, including cancel/retry/reload? |
| Free play, about 30–45 minutes initially | Freedom to choose what matters; no requirement to clear the docket or play optimally. | Are choices interesting, consequences recognizable, and another session appealing? |

These are suggested session sizes, not time-to-completion promises. Do not ask
for a full year while the first action remains broken. Later compare the same
seed with a different ruling or policy, then a different seed for robustness.
The existing key-by-key `PLAYTEST_DECISIONS.md` route is useful regression
coverage, not evidence of unaided discovery.

Before a commitment, ask what the player expects to spend and happen. Afterward,
ask what they think happened and where they would find the result. If a tester
needs a hint, record the intervention instead of erasing the difficulty by
coaching. Help may be used, but needing Help for every basic action is a design
failure. The LLM help tab must not become a replacement for a usable interface.

After a session the AI should return:

1. The three highest-impact failures, grounded in exact notes.
2. Which are reproduced, which are hypotheses and which need evidence.
3. One small proposed change and the observation that would show it worked.
4. The resulting task packet and, after implementation, the exact retest route.

No wall of speculative features. If an action is confusing, fix that action
before adding a tutorial for it. If it is understood but boring, inspect its
consequences. If it produces the wrong result, stop polishing and fix correctness.
If evidence contradicts a design assumption, update the plan and SPEC decision
where appropriate instead of defending the earlier implementation.

Proposed milestone acceptance: all core journeys above can be completed without
developer coaching; no known wrong-quantity, accidental-order, blocked-reply or
lost-save defect remains; the owner can identify an earlier consequence and a
reason to keep playing. An unfamiliar second player is useful confirmation when
available. AI playthroughs cannot award human acceptance.

## 9. Execution discipline for less capable development agents

Give one agent one bounded failure at a time. This plan is not a single prompt
to “finish the game.” Avoid concurrent controller, parser and balance edits.
The owner chooses what feels wrong and accepts the result; the AI investigates,
implements the narrow repair, supplies evidence and proposes the next task.

Each assignment needs:

```text
Task ID and one player-visible outcome:
Current revision / relevant note ID:
Reproduction: seed, save, turn, screen, inputs, expected vs actual.
Evidence already established; uncertainty still open:
Read first: named SPEC contract and relevant functions.
Allowed edit scope / likely files:
Required behavior, including cancel/refusal/empty-state cases:
Non-goals:
Verification: smallest useful checks plus the native interaction route.
Done when: observable conditions, with human acceptance left pending.
Stop/split if: new mechanic, spec conflict, save semantic change, or unrelated
controller rewrite is needed. Report the decision needed; do not improvise it.
Deliver: changed behavior, evidence, limitations and one next retest.
```

Aim for one behavior and a few files. File count is a signal to split work, not
a rule that justifies a bad patch. Start by reproducing; do not “fix” an issue
whose current behavior has not been checked. Preserve engine authority, Belief
boundaries, deterministic terms and replay. Runtime model language must never
supply authoritative quantities or decide whether an order succeeded.

Use existing focused checks for semantic defects and critical cancellation,
conservation, information and replay boundaries. Do not build a second test
implementation or run a huge suite after a wording change. A UI delivery needs
native interaction evidence; screenshots or synthetic event handlers alone are
insufficient. If native verification was not performed, state that plainly and
leave the status pending. Do not quote historical pass counts as fresh evidence.

Three ready-to-issue first packets:

- **A-01: Honest quantity parsing.** Reproduce the copper-unit example. Reject
  unsupported units with a recoverable explanation, or normalize only explicitly
  supported units. Keep canonical shekel/qa requests working. No broad NLP rewrite,
  model substitution, balance changes or new letter kinds. Evidence: parsed terms,
  visible review, actual dispatched quantity and cancel/refusal behavior.
- **A-02: No unadvertised end turn.** Trace Hall focus and Enter routing. Make
  only the advertised end-turn action advance the fortnight; preserve Enter's
  documented behavior in reviews and selected records. Evidence: native key route,
  unchanged turn for unrelated Enter, one advance for explicit end turn.
- **A-03: Reproduce the failed reply.** Read relevant local notes/save, identify
  the letter, read it, draft a response, cancel/reopen, confirm and inspect outbox.
  Capture refusal/model/focus state. Repair only the demonstrated cause. If it
  cannot be reproduced, deliver that result and improved diagnostics, not an
  invented fix or a claim of completion.

Between packets, retest the same player goal before expanding scope. The next
assignment is determined by what still blocks play, not by which subsystem is
most attractive for an agent to build.
