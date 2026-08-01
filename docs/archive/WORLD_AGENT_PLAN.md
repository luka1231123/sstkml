# World continuation — agent execution plan

Status: **Done and dusted.** The correspondence chain below is built. Kept as a
record of how it was staged. Adds no requirement to `SPEC.md`.  
Baseline at the time of writing: 692 tests passing.

## 1. Goal

```text
foreign need/belief
-> World court
-> tablet + exact terms
-> seal + courier + route
-> transit
-> recipient Belief and decision
-> reply
-> material/political consequence
-> archive + replay
```

Ship Phase A before World expand.

## 2. Constraints

- Keep determinism, replay, integer state, World/Belief separation.
- Models write language only. Never make facts, terms, routes, decisions, outcomes.
- Store accepted text + structured terms. Replay never reruns model.
- Gifts, marriage proposals go by correspondence, not instant Palace actions.
- Promises make obligations or missions. No goods teleport.
- UI reads Belief only.
- No new primary rooms, no unrelated redesign.
- Isolated worktrees. Commit owned files only.
- Never weaken gate to merge.

## 3. Contract frozen by Agent 0

Add in `engine/actions.py`; serialize + round-trip before parallel work:

```python
@dataclass(frozen=True)
class LetterTerm:
    kind: str
    good: str = ""
    quantity: int = 0
    person_id: str = ""
    destination: str = ""
    due_turn: int = 0


@dataclass(frozen=True)
class DispatchLetter:
    recipient: str
    reply_to: str
    text: str
    profile: str
    terms: tuple[LetterTerm, ...]
    scribe_id: str
    seal: str
    courier_id: str
    path: tuple[str, ...]
```

Allowed `LetterTerm.kind`:

```text
gift
request_good
promise_good
service
marriage_proposal
```

Validation:

- good terms need known good + positive quantity;
- service needs positive person-days + destination;
- marriage needs selected, valid, living person;
- path starts at court, ends at recipient, uses existing edges;
- reply target exists or empty;
- text non-empty, stored exact.

No tone or prose in `LetterTerm`.

## 4. Worktrees and roles

| Agent | Worktree | Role |
|---|---|---|
| 0 | `world-contracts` | contracts, integration, gates |
| 1 | `world-transit` | dispatch and physical mail |
| 2 | `world-terms` | term effects and obligations |
| 3 | `world-desk` | World/Desk/Outbox UI |

Agent 0 integrates commits. Agents never reset, rebase, clean another worktree.

## 5. Phase A — playable letter consequence

Elapsed, four agents: **8–12 h**.  
Labour: **18–27 agent-hours**.

### A0 — contracts

Owner: Agent 0. Estimate: **1.5–2.5 h**.

Own:

- `engine/actions.py`
- `engine/state.py`
- serialization
- contract tests

Deliver:

1. Add frozen interfaces above.
2. Extend `Letter` with text, terms, scribe, seal, courier, route provenance; keep defaults for old fixtures.
3. Reject invalid terms and paths.
4. Pass full suite.

### A1 — transit

Owner: Agent 1. Estimate: **4–6 h**. Depends on A0.

Own:

- `engine/mail.py`
- mail tests

No UI or kernel file edits.

Deliver:

1. Apply `DispatchLetter`.
2. Validate recipient/path.
3. Make one outgoing `Letter`.
4. Mark `reply_to` answered only after successful dispatch.
5. Traverse route legs; respect season + quarantine.
6. Deliver immutable text/terms.
7. Emit sent, delayed, intercepted, delivered records.
8. Keep courier disease contact.

Tests: direct/multi-leg route, winter delay, quarantine, invalid path, one answer, reload dedup, replay hash.

### A2 — term effects

Owner: Agent 2. Estimate: **5–8 h**. Depends on A0.

Own:

- new `engine/letter_terms.py`
- `engine/obligation.py`
- minimal ownership/mission integration
- term tests

No mail or UI edits.

Deliver:

- `gift`: reserve at seal; move through shipment/mission; release on refusal;
- `promise_good`: make dated obligation, not goods;
- `request_good`: make recipient claim after delivery;
- `service`: make authorized service obligation/mission;
- `marriage_proposal`: make pending proposal; marry only after acceptance;
- record authority, source letter, beneficiary, due turn, history.

Tests: conservation, no double reservation, no promise faucet, request hits Belief only, marriage pending, replay equality.

### A3 — World-to-Desk UI

Owner: Agent 3. Estimate: **5–7 h**. Depends on A0.

Own:

- `tui/worldmap.py`
- `tui/composer.py`
- World/Desk parts of `play_gui.py`
- UI/controller tests

No engine file edits.

Deliver:

1. Enable World `Letter` for foreign court.
2. Keep `Envoy` disabled.
3. Remove direct World Gift/Marriage; label “by letter” or omit.
4. One Desk for new letters and replies.
5. Keep Address, Recognition, player Matter, Seal.
6. Add terms: kind, good/person, quantity/due turn, remove, summary.
7. Add scribe, courier, valid path, known travel time.
8. Dispatch one `DispatchLetter`.
9. Keep drafts on close; discard only explicit.

Tests: recipient from World, no self-letter, visible options only, Matter survives changes, Yabninu cannot alter terms, invalid seal disabled, minimum-size mouse/keyboard parity, Outbox route/terms.

### A4 — integration

Owner: Agent 0. Estimate: **2.5–4 h**.

Merge:

```text
A0 -> A1 -> A2 -> A3
```

Then:

- remove direct Palace gift/marriage execution;
- project only known/delivered terms + transit state;
- update Help + action inventory;
- resolve contracts, not tests.

Gate:

```sh
.venv/bin/pytest -q
.venv/bin/python tools/inventory.py
.venv/bin/python tools/corpus_lint.py
.venv/bin/python tools/m13_audit.py
.venv/bin/python tools/m13_benchmark.py
.venv/bin/python tools/screens.py world
.venv/bin/python tools/screens.py desk
git diff --check
```

Exit:

> A selected foreign court receives a physically routed immutable tablet. At
> least one delivered term causes a conserved or political state change.

Stop if not green.

## 6. Phase B — recipient decision and reply

Elapsed: **8–14 h**. Labour: **18–28 agent-hours**.

| Task | Owner | Files | Estimate | Required output |
|---|---|---|---:|---|
| B1 Belief | Agent 1 | `engine/observe.py`, `engine/believe.py` | 4–6 h | delivered terms become dated claims linked to letter ID |
| B2 policy | Agent 2 | `engine/kernel/intent.py`, new correspondence policy | 6–9 h | accept/refuse/counter/delay/ignore from `(actor, belief)` |
| B3 reply | Agent 3 | `ai/`, projection/rendering | 4–6 h | guarded stored prose, return transit, visible silence |
| B4 integrate | Agent 0 | cross-boundary only | 4–7 h | deterministic end-to-end scenario |

Scenario gate:

```text
Ugarit requests grain
-> foreign court knows shortage
-> court counteroffers
-> reply travels
-> Ugarit accepts/refuses
-> obligation/goods change
-> inspector explains chain
```

Exit: foreign decisions use Belief/capacity; replay never reruns models.

## 7. Phase C — unify Ugarit and kernel

Elapsed: **16–28 h**. Labour: **28–45 agent-hours**. Mostly sequential.

1. **C1 inventory — Agent 0, 2–3 h.** Map duplicate people, goods, labour, sites, routes, obligations, organizations, Belief, letters. Name one kernel authority + one deletion target each.
2. **C2 migration — Agent 1, 10–16 h.** Move Ugarit to kernel goods, labour, movement, ownership, obligations; migrate saves; add inspector chains.
3. **C3 projection — Agent 2, 6–10 h.** Keep room Belief shapes, uncertainty, provenance; leak no World object.
4. **C4 delete/integrate — Agent 0, 6–10 h.** Remove superseded court state; fail if duplicate authoritative quantities remain.

Exit: Ugarit + foreign settlements share one material, correspondence, Belief grammar.

## 8. Phase D — 1.0 World

Elapsed: **1–3 days**. Labour: **20–35 agent-hours**.

Parallel deliverables:

- World layers: journeys, trade, news, obligations, disease, limited conflict;
- place/court/route dossiers with dates, sources, uncertainty;
- explicit envoy missions after letters stabilize;
- responsive minimum/default layouts;
- 96-turn causal, balance, replay, performance gates.

No scenarios, giant population targets, coalition warfare, mass displacement, procedural dynasties, new primary rooms. Post-1.0.

Exit: autonomous, inspectable regional World supports full Ugarit campaign, no scripted letter cadence, no hidden shortcuts.

## 9. Estimate

| Deliverable | Labour | Parallel elapsed |
|---|---:|---:|
| A: letter consequence | 18–27 h | 8–12 h |
| B: foreign response | 18–28 h | 8–14 h |
| C: unification | 28–45 h | 16–28 h |
| D: World and balance | 20–35 h | 1–3 days |
| **Total** | **84–135 h** | **4–8 supervised days** |

Add 50% contingency if migration, conservation, or replay finds duplicate authority. Expected with contingency: **6–12 supervised days**.

## 10. Handoff schema

Every agent returns:

```text
STATUS: complete | blocked
COMMIT: <sha>
FILES: <owned files>
TESTS: <commands + results>
CONTRACT_CHANGES: none | exact list
RISKS: <remaining>
NEXT_MERGE: <dependency/action>
```

`complete` needs focused tests + clean `git diff --check`. Only Agent 0 declares phase complete.