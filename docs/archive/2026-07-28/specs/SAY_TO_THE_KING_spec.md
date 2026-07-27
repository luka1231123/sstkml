# SAY TO THE KING, MY LORD
## Implementation specification for Claude Code

A terminal game about ruling a Late Bronze Age kingdom through its archive. No map. No units on a battlefield. You read letters, allocate grain and men, perform rites, dictate replies, and try to work out what is actually happening from documents written by people with reasons to lie.

Target: a fortnight-per-turn management sim with a fully deterministic simulation core and a local language model (`qwen3:14b` via Ollama) used strictly as an interpretation and prose layer on top.

---

# PART 0. THE TWO LAWS

Everything in this document follows from two rules. If a design decision is ambiguous, resolve it with these.

**LAW 1. The model never touches state.**
The language model may read a curated, deliberately incomplete view of the world. It may emit text, and it may emit a structured action from a closed vocabulary. It may not compute a number, decide an outcome, roll a die, or mutate anything. Every number that reaches the player was computed by deterministic code. Every number in model output was present verbatim in the model's prompt.

**LAW 2. The game must be complete and fun with the model switched off.**
Build the whole simulation first, driven by slash commands. `--no-ai` must remain a supported, playable, shippable mode for the life of the project. The model adds prose, personality, and natural-language input. It adds no mechanics. If the game is not good in `--no-ai` mode, no amount of model output will save it, and if you ever find yourself wanting the model to decide something, that is a signal the simulation is missing a system.
---

# PART 1. STACK AND SETUP

## 1.1 Choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | fast iteration, best Ollama and TUI ecosystem |
| TUI | Textual (>=0.80) | tabs, focus, scrolling, key bindings, and it renders raw ASCII inside `Static` widgets without fighting you |
| Data model | `pydantic` v2 for content files, plain frozen `dataclasses` for runtime state | pydantic for validating authored TOML, dataclasses for speed and hashability in the hot loop |
| Content authoring | TOML | comments, trailing commas, human diffable |
| Model runtime | Ollama HTTP API, `qwen3:14b` | user's existing setup; structured output via `format` JSON schema |
| Serialization | canonical JSON (sorted keys, integer-only) | exact save hashing |
| Testing | pytest + `hypothesis` for property tests | determinism harness needs both golden and generative tests |

Do not use an ORM. Do not use a database. State is an in-memory tree serialized to canonical JSON.

## 1.2 Hard dependency rules

- No dependency may be imported inside `engine/`. `engine/` uses only the standard library. This is enforced by a test that walks the AST of every file under `engine/` and asserts all imports resolve to stdlib or to `engine.*`.
- `ai/` may import `belief/` but never `engine/state` internals. It receives plain dicts.
- `tui/` may import `belief/` and `ai/`, never `engine/systems/`.

The purpose of this rule is that the simulation stays testable, replayable, and portable, and that it is structurally impossible for an AI code path to reach into world truth.

## 1.3 Repo layout

```
sttkml/
  pyproject.toml
  README.md
  SPEC.md                      <- this file, keep it updated as you build
  DECISIONS.md                 <- append-only log of design choices and why

  engine/                      stdlib only
    __init__.py
    ids.py                     typed ID newtypes
    rng.py                     substream RNG
    calendar.py
    state.py                   the World dataclass tree
    actions.py                 closed Action union
    events.py                  closed Event union
    reduce.py                  apply(state, action) -> (state, [event])
    tick.py                    the turn pipeline
    hashing.py                 canonical state hash
    systems/
      attention.py
      stores.py
      rations.py
      agriculture.py
      metals.py
      routes.py
      letters.py
      relations.py
      gifts.py
      oaths.py
      personnel.py
      household.py
      divination.py
      plague.py
      displacement.py
      unrest.py
      rites.py
      collapse.py
      archive.py
      scoring.py
      rivals.py                deterministic policy for the three non-player courts
      decks.py                 event deck drawing

  belief/
    claims.py                  Claim, ClaimStore
    project.py                 World -> Belief for one ruler
    distortion.py              scribe bias, transcription error, actor report bias
    stack.py                   builds the morning Stack

  ai/
    client.py                  Ollama transport, caching, timeouts, seeding
    roles/
      parser.py
      composer.py
      voicer.py
      librarian.py             archive search summarizer
      epilogue.py
    schemas/*.json             JSON schemas for structured output
    prompts/*.jinja            prompt templates
    grader.py                  DETERMINISTIC protocol grader
    numeric_guard.py           DETERMINISTIC number whitelist validator
    fallback.py                template-based generation when model unavailable
    cache.py

  tui/
    app.py
    theme.py
    ascii/                     box drawing, sparklines, gauges, node graph
    tabs/
      stack.py archive.py stores.py lists.py house.py world.py rites.py desk.py
    widgets/
      command_line.py stack_list.py ledger.py sparkline.py known_world.py

  content/
    goods.toml
    routes.toml
    months.toml
    formulae.toml              epistolary protocol rules, per culture
    gods.toml
    scenarios/
      pharaoh.toml
      ugarit.toml
      amurru.toml
      pylos.toml
    decks/
      misfortune.toml court.toml trade.toml weather.toml
    corpus/
      letters/*.txt            authored exemplars for few-shot and for fallback
      predecessor_archive/*.toml   documents that exist before turn 1

  tests/
    golden/                    seed + action script -> expected state hash
    unit/
    property/
    fixtures/

  tools/
    replay.py
    balance.py                 headless N-run sweep, prints distributions
    corpus_lint.py             checks authored letters against the grader
    ascii_preview.py
```

---

# PART 2. THE DETERMINISM CONTRACT

This is the rigid centre the whole design rests on. Get it right before writing any gameplay.

## 2.1 State is a fold over events

```python
# engine/reduce.py
def apply(state: World, action: Action) -> tuple[World, list[Event]]: ...
def integrate(state: World, event: Event) -> World: ...
```

`apply` validates and translates an `Action` into `Event`s. `integrate` is the only function permitted to produce a new `World`. Both are pure. Neither reads the clock, the filesystem, the network, or a global RNG.

A save file is:

```json
{
  "version": 3,
  "seed": 8814402919,
  "scenario": "ugarit",
  "log": [ {"turn": 1, "action": {...}}, ... ],
  "ai_log": [ {"call_id": "...", "role": "parser", "prompt_sha": "...", "raw": "..."} ],
  "state_hash_at_save": "b3:1f4c..."
}
```

Loading replays the log. If the resulting hash differs from `state_hash_at_save`, refuse to load and report which turn diverged. This catches every determinism regression in the field, not just in tests.

## 2.2 RNG: substreams, never a sequence

The single most common way a project like this loses determinism is a global RNG whose consumption order shifts when you reorder code or when an async call returns late. Do not have one.

```python
# engine/rng.py
def stream(seed: int, turn: int, domain: str, key: str = "") -> Rng:
    h = blake2b(f"{seed}|{turn}|{domain}|{key}".encode(), digest_size=8).digest()
    return Rng(int.from_bytes(h, "big"))
```

`Rng` is a small PCG64 or SplitMix64 with `.int(n)`, `.pick(seq)`, `.weighted(pairs)`, `.chance(num, den)`. Rules:

- Every draw names its domain and its key. `stream(seed, t, "plague.transmission", settlement_id)`.
- Never store an `Rng` in state. Always derive fresh from `(seed, turn, domain, key)`.
- Because streams are content-addressed, adding a new system, changing evaluation order, or skipping a draw cannot perturb any other system. This is what lets you refactor for months without breaking golden tests.
- Reserve `domain` strings in a module-level registry (`engine/rng.py: DOMAINS: frozenset`) and assert membership, so typos do not silently create a new stream.

## 2.3 Integers only

No floats in `World`, ever. Not for trust, not for yields, not for anything.

- Quantities: integers in a defined smallest unit (grain in *qa*, metal in *shekels*, land in *iku*).
- Ratios and 0..1 scalars: integers scaled by 1000. `esteem: int  # 0..1000`.
- Where you want a curve, use an authored integer lookup table with linear interpolation in integer arithmetic, not `math.pow`. Tables live in `content/` and are therefore tunable without touching code.

```python
def lerp_table(table: tuple[tuple[int,int], ...], x: int) -> int:
    # table sorted by x, both axes integer, result integer, floor division
```

Rationale beyond determinism: every curve becomes data a designer can see and edit, and every balance conversation becomes a diff.

## 2.4 Canonical ordering

- All collections in state are either tuples (ordered by construction, order is meaningful) or dicts that are **always iterated via `sorted(d.items())`**. Add a lint test that greps `engine/` for `for .* in .*\.items()` not wrapped in `sorted`.
- IDs are stable strings authored in content, never generated from counters that depend on evaluation order. When you must generate an ID at runtime, derive it: `f"letter:{turn}:{sender}:{n}"` where `n` is a per-sender-per-turn counter held in state.

## 2.5 State hashing

```python
def state_hash(w: World) -> str:
    return "b3:" + blake2b(canonical_json(w).encode(), digest_size=16).hexdigest()
```

`canonical_json` sorts keys, rejects floats (raises), rejects sets, and emits no whitespace. Hash after every turn boundary and store the last 32 hashes in a ring for divergence bisection.

## 2.6 Where the model fits without breaking any of this

The model is called during the interactive player phase only, and its outputs are recorded into `ai_log` as data. Two consequences:

1. Replay never invokes the model. It reads `ai_log` by `call_id`.
2. Parser output is an `Action`, which goes into `log` like any other. The prose that produced it is incidental.

Composer and Voicer text is *display only*, with one exception: the deterministic grader's score derived from the text is a real input to the simulation. So the text must be logged, because the score must be reproducible. Log the text, recompute the score at replay time from the logged text. Never log the score alone.

---

# PART 3. CALENDAR AND TIME

## 3.1 One engine calendar, four costumes

The engine has exactly one time unit: the fortnight. 24 per year. This is roughly one lunar half-month and, more importantly, roughly one courier leg on a medium route.

```python
@dataclass(frozen=True)
class Date:
    year: int        # regnal year of the current ruler
    fortnight: int   # 1..24
    absolute: int    # turns since scenario start, the only field systems should use
```

Cultures never get their own calendar logic. They get their own *labels*, in `content/months.toml`:

```toml
[ugarit]
months = ["Ittabnu","Hiyaru","Nisanu",...]     # 12 entries
halves = ["former half","latter half"]

[egypt]
# civil calendar: 3 seasons x 4 months
months = ["Akhet I","Akhet II",...]
halves = ["first fifteen days","second fifteen days"]

[pylos]
months = ["po-ro-wi-to","me-tu-wo ne-wo",...]
halves = ["waxing","waning"]
```

Regnal-year dating is what the *documents* use. Letters are stamped with the sender's regnal year and month name. There is no shared epoch. Correlating two correspondents' timelines is a player skill; the UI must not offer a unified timeline view. The `Date.absolute` field exists for the engine and must never be rendered.

## 3.2 Seasonal flags

Derived from `fortnight`, authored per scenario:

```toml
[season]
sailing_open       = [7,21]    # inclusive fortnight range; outside this, sea legs do not move
sowing             = [19,22]
growing            = [23,24,1,2,3,4,5,6,7]
harvest            = [8,11]
threshing          = [12,13]
low_water          = [14,18]   # canal dredging window, Mesopotamia
```

The closed sea is a headline mechanic, not a detail. Nine consecutive turns in which no overseas letter moves in either direction. Design intent: the player enters winter with a belief state and cannot refresh it, makes nine turns of decisions on frozen information, and then spring delivers a flood of correspondence, all of it four months stale, much of it answering letters since made irrelevant. The Stack on the first open turn should routinely be 30 to 45 items against a 10 hour budget. Do not soften this.

## 3.3 Scheduling

One mechanism for all delayed effects:

```python
@dataclass(frozen=True)
class Scheduled:
    at: int            # absolute turn
    payload: Event     # already-decided event
```

Held in `World.schedule: tuple[Scheduled, ...]`, sorted by `(at, canonical_json(payload))` so the order is total and stable. Step 3 of the pipeline drains everything with `at == now`.

Anything that "arrives later" is a `Scheduled`: letters, caravans, pregnancies, plague incubation, oath deadlines, a promised shipment. Do not invent per-system timers.

---

# PART 4. STATE MODEL

Sketch, not exhaustive. Fill in as systems land, but keep the shape.

```python
@dataclass(frozen=True)
class World:
    seed: int
    scenario: str
    date: Date
    schedule: tuple[Scheduled, ...]

    # the player's court
    court: Court
    # the other three courts, simulated by deterministic policy
    rivals: tuple[Court, ...]

    places: Mapping[PlaceId, Place]
    routes: tuple[Route, ...]
    letters_in_transit: tuple[Letter, ...]
    relations: Mapping[ActorId, Relation]
    oaths: tuple[Oath, ...]
    displaced: tuple[DisplacedGroup, ...]
    coalition: Coalition
    climate: ClimateSeries          # precomputed at scenario start from seed
    collapse: CollapseState
    archive: Archive                # every document ever received or sent
    rng_ledger: tuple[str, ...]     # debug only, excluded from hash

@dataclass(frozen=True)
class Court:
    actor: ActorId
    seat: PlaceId
    attention_base: int             # hours per fortnight, typically 10
    stores: Mapping[GoodId, int]
    ration_lists: tuple[RationList, ...]
    dependents: Mapping[GroupId, DependentGroup]
    personnel: tuple[Person, ...]   # scribes, diviners, officials
    household: Household
    troops: tuple[Formation, ...]
    workshops: tuple[Workshop, ...]
    land: tuple[Estate, ...]
    seals: tuple[Seal, ...]
    liability: Mapping[OathId, int] # divine liability, hidden from player
    legitimacy: int                 # 0..1000
    treasury_gifts_sent: tuple[GiftRecord, ...]
```

## 4.1 The Belief split, which is the architectural heart

There are two knowledge stores and they must never be conflated.

- `World` is truth. Only `engine/` sees it.
- `Belief` is what one ruler thinks is true. `belief/project.py` builds it from `World` plus the ruler's `Archive` plus arriving claims. **The TUI reads only `Belief`. The AI layer reads only `Belief`.**

```python
@dataclass(frozen=True)
class Claim:
    fact_key: str          # "granary.ma_hadu.qa" or "hatti.grain_exhausted"
    value: int | str
    source: ActorId
    received_turn: int
    channel: str           # "sealed_letter" | "verbal" | "rumour" | "own_ledger"
    corroborations: tuple[ActorId, ...]
```

Rules:

- Conflicting claims coexist. There is no reconciliation step. The UI shows both, with source and age.
- Freshness is rendered, never resolved: `●` under 3 turns, `○` 3 to 8 turns, `·` over 8, and dim the row.
- `own_ledger` claims are true-but-possibly-mistranscribed, see 6.7.
- The player's own stores are the only fact class where Belief is nearly truth, and even then the *count* passes through a scribe.

Enforcement: `belief/project.py` returns plain dicts of primitives. A test asserts no `World` object is reachable from a `Belief`. A second test asserts every string sent to the model appears in some `Belief` projection.

---

# PART 5. THE TURN PIPELINE

Exact order. Write it once, in `engine/tick.py`, and never reorder without updating golden hashes deliberately.

```
BEGIN TURN T

  PHASE A: WORLD ADVANCE (no player input)
   A1  date advance, recompute seasonal flags
   A2  climate index for T read from precomputed series
   A3  drain schedule where at == T  (arrivals: letters, caravans, births, deadlines)
   A4  plague step per settlement, then mortality
   A5  household: aging, health checks, conception checks, pregnancies
   A6  agriculture phase step (sowing / growth accumulation / harvest / threshing)
   A7  workshops: consume inputs, emit outputs, metals melt if tin short
   A8  rations paid per standing allocation; arrears updated
   A9  unrest and loyalty recomputed from arrears, events, rites, garrisons
   A10 oath clause audit -> divine liability accrual
   A11 collapse index recomputed
   A12 event deck draws (weights from collapse, unrest, liability, season)
   A13 rival courts act (deterministic policy, engine/systems/rivals.py)
   A14 displacement: generate displaced groups, resolve court receptions,
       update coalition, evaluate raid triggers
   A15 NPC intents computed: who writes to the player this turn, about what,
       with what bias. Produces LetterIntent records, not text.

  PHASE B: PERCEPTION
   B1  distortion pass: actor report bias applied to the facts each NPC will assert
   B2  scribe pass: transcription errors applied to numbers in incoming documents
   B3  belief projection built
   B4  Stack assembled and ordered by the scribe's perceived importance
   B5  attention budget set: attention_base - ritual obligations - illness - unrest tax

  PHASE C: PLAYER  (interactive, one action at a time, each logged immediately)
   C*  actions apply through reduce.apply; effects that are immediate are immediate,
       effects that are delayed become Scheduled. Attention decremented per action.
       Ends on explicit end-turn, or when attention hits 0 and no free actions remain.

  PHASE D: DISPATCH
   D1  outgoing letters routed: legs computed, arrival scheduled, interception checked
   D2  troop movement orders committed
   D3  allocation changes take effect from T+1
   D4  snapshot state_hash, autosave

END TURN
```

Notes that matter:

- Player actions in phase C see the world as of B3. They do not see A-phase truths. If the player's own action reveals something (opening a granary, interrogating a captain), that produces a *new Claim* immediately, which is the only mid-phase belief mutation permitted.
- Ration allocation changes take effect next turn (D3). This lag is load-bearing: it means you cannot micro-correct a famine on the turn you notice it.
- A15 produces *intents*, not prose. Prose generation happens lazily in phase C when the player chooses to read, or in a background worker during phase C. See 8.7.

---

# PART 6. SYSTEMS

Each subsection gives: the state, the update rule, the numbers, and what the player can and cannot see. All formulas are integer arithmetic. `T(name, x)` means "look up authored table `name` at `x`".

## 6.1 Attention (the audience economy)

The scarcest resource in the game. Tighter than grain.

```python
attention_available = attention_base            # 10 for most rulers
                    - sum(rite.hours for rite in obligatory_rites_this_turn)
                    - illness_penalty(ruler.health)      # T("illness_hours", health)
                    - unrest_tax(seat_unrest)            # 1 hour per 250 unrest, capped 3
```

Costs, authored in `content/scenarios/*.toml` so they are tunable per ruler:

| Action | Hours |
|---|---|
| Read a summary of an item | 1 |
| Read a document in full | 2 (short) or 3 (long, multi-topic) |
| Hold audience with a petitioner | 2 |
| Inspect a ledger in detail (reveals true count, bypasses scribe error) | 1 |
| Dictate a letter via scribe | 1 to 3 by length |
| Write a letter yourself (raw text entry) | 2 |
| Verify a seal | 1 |
| Commission divination | 2 |
| Supervise a workshop or granary personally | 2 |
| Reorder the Stack manually | 1 |
| Search the archive | 1 per query |
| Change a ration allocation | 0 (free, but takes effect T+1) |
| End turn | 0 |

Design intent: full reading is expensive and true, summary is cheap and filtered through a scribe with relatives. That single trade is the spine of the game. Never make full reading free, and never make the summary reliable.

Free actions (deliberately, so the player is never stuck at 0 hours with nothing to do): change allocations, end turn, browse stores, browse ration lists, view the Known World, view the rites calendar.

## 6.2 Stores and goods

`content/goods.toml`:

```toml
[grain]
unit = "qa"; display_unit = "parisu"; per_display = 60
spoilage_per_1000_per_turn = 4          # granary loss
is_seed_capable = true

[copper]  unit = "shekel"; display_unit = "talent"; per_display = 3600
[tin]     unit = "shekel"; display_unit = "talent"; per_display = 3600
[bronze]  unit = "shekel"; display_unit = "talent"; per_display = 3600
[oil]     unit = "log";    display_unit = "jar"
[wine] [wool] [linen] [timber] [gold] [silver] [lapis] [ivory] [honey] [salt]
```

Spoilage runs in A8, integer, `loss = stock * rate // 1000`, floor. Small numbers therefore never spoil, which is fine and true.

Display always in the large unit with a remainder, because that is how the tablets do it: `1,204 parisu 18 qa`.

**Seed grain is a separate stock**, not a fraction of the granary. `stores["grain"]` and `stores["seed_grain"]`. Eating the seed is a single free action with no cost this turn and a catastrophic cost at sowing, which is 19 turns away. This is the purest collapse mechanic in the game and it should be one keystroke.

## 6.3 Rations, dependents, arrears

The economy is redistribution, not exchange. There is no market and no money in the player's court. Grain arrives from crown and temple estates and leaves as named rations to named groups.

```python
@dataclass(frozen=True)
class DependentGroup:
    id: GroupId
    name: str                 # "smiths of the palace quarter", "garrison at Ma'hadu"
    size: int                 # heads
    entitlement: int          # qa per head per fortnight, authored by status
    function: str             # "bronze_working" | "garrison" | "weaving" | "cult" | "household"
    place: PlaceId
    arrears: int              # cumulative unpaid qa, THE memory of the system
    loyalty: int              # 0..1000
    output_modifier: int      # 0..1000, derived, cached
```

Each turn in A8, for each group, in sorted order:

```
owed  = size * entitlement
paid  = min(owed, allocation[group], available_grain)
arrears += owed - paid
if paid > owed:  arrears -= min(arrears, paid - owed)   # overpayment repays memory
satisfaction = 1000 * paid // max(1, owed)
```

Effects are driven by **arrears expressed in fortnights of entitlement**, not by instantaneous satisfaction. This is what gives famine its characteristic lag and momentum.

```
debt_weeks = arrears // max(1, size * entitlement)

debt_weeks  loyalty delta   output_modifier   other
0                +8            1000           -
1                -20            920           grumbling petitions appear in the Stack
2                -60            780           a named figure from the group writes to you
4               -140            520           desertion begins: size decays 3% per turn
6               -260            300           the group's function begins to fail outright
8               -400             80           flight or revolt event enters the deck at high weight
```

Cut a ration line and you are cutting specific people who appear in later correspondence by name. That is the whole point: payroll is a good game system because every cut has a face. When a group crosses `debt_weeks == 2`, the engine must generate a `LetterIntent` from a named member of that group. Generate and persist the name once, at scenario load, from `stream(seed, 0, "names", group_id)`, so it is the same person every time.

Priority ordering: the player sets an ordered priority list. If grain runs short mid-turn, allocation is paid down the list. The list is the single most important screen in the game and it should be one keypress from the Stack.

## 6.4 Agriculture

Deterministic and opaque. The player never sees the yield formula's inputs, only proxies.

```python
climate_index[t]    # 0..200, 100 = normal. PRECOMPUTED at scenario start.
```

Precompute the whole climate series at scenario start from `stream(seed, 0, "climate")` plus an authored drought curve per scenario, so that the future is fixed the moment the game begins. This matters for divination (6.11) which must be able to read a true future value.

```
# per estate, evaluated at harvest fortnight
water   = T("water_response", climate_index_mean_over_growing_season)     # 0..1000
labour  = T("labour_response", 1000 * labour_days_supplied // labour_days_needed)
seed    = T("seed_response", 1000 * seed_sown // seed_recommended)
canal   = T("canal_response", canal_condition)     # Mesopotamia only, else 1000
pest    = event-driven modifier, default 1000

yield_qa = area_iku * base_yield_per_iku
         * water // 1000 * labour // 1000 * seed // 1000 * canal // 1000 * pest // 1000
```

Do the multiplications and divisions in that exact left-to-right order and document it, because integer floor division is not associative and reordering changes results.

Labour comes from `troops` assigned to `HARVEST`, from dependent groups with function `field_labour`, and from corvee raised via an action that costs unrest. Assigning the garrison to the harvest is the classic Bronze Age dilemma and must be a one-line action.

Canal condition (Mesopotamian scenarios): decays 60 per turn, restored by dredging during the `low_water` window at a cost of labour-days. Neglect for one year is recoverable, two years is not, because `T("canal_response")` falls off a cliff below 300.

Proxies visible to the player, and only these:
- a river gauge or well depth reading, delivered by an official, subject to transcription error
- estate overseers' letters, subject to their report bias (they inflate need, conceal failure)
- the priest's assessment, biased by his faction's policy preference
- last year's actual harvest, which is true, and which is the only hard datum

## 6.5 Metals: the bronze chain and the melt ledger

The slow-motion structural failure that the player will not notice until it is done.

```
bronze_produced = min(copper // 9, tin) * 10      # 9:1 by weight
```

Tin is the chokepoint. It travels the longest and most fragile route (the eastern overland caravan through Mesopotamian middlemen). Copper is comparatively near (Alashiya). Losing tin does nothing visible for a long time.

```python
@dataclass(frozen=True)
class MetalState:
    bronze_in_circulation: int    # total bronze existing as tools, weapons, chariot fittings
    melt_ledger: int              # CUMULATIVE shekels recycled. Only ever increases.
```

Workshops have a per-turn bronze demand for maintenance and replacement. Resolution order in A7:

1. Meet demand from `stores["bronze"]`.
2. If short, meet the remainder by melting: `stores["bronze"] += melted`, `bronze_in_circulation -= melted`, `melt_ledger += melted`.
3. If `bronze_in_circulation` falls below a formation's `equipment_floor`, that formation's `replacement_rate` drops.

The crucial consequence: **army strength does not fall. Replacement falls.** Combat losses stop being replaceable. The player loses the army without ever losing a battle, and the only warning was a monotonically increasing number on a ledger page that nobody reads, labelled *melted to date*.

Nothing announces this. No warning, no alert, no colour change. The number is visible on tab 3 if the player looks.

## 6.6 Routes, couriers, letters

```python
@dataclass(frozen=True)
class Route:
    a: PlaceId; b: PlaceId
    legs: int                   # fortnights
    mode: str                   # "sea" | "land" | "river"
    seasonal: bool              # if sea and seasonal, closed outside sailing_open
    risk: int                   # base 0..1000 interception/loss weight

@dataclass(frozen=True)
class Letter:
    id: LetterId
    sender: ActorId; recipient: ActorId
    sent_turn: int; arrive_turn: int
    path: tuple[PlaceId, ...]
    at_node: PlaceId            # where it currently is
    seal: SealId | None
    body_ref: DocRef            # into Archive
    asserted: tuple[Claim, ...] # what the letter claims, engine-computed, possibly false
    protocol: ProtocolScore
    courier: str                # "royal" | "merchant" | "runner"
    intercepted_by: ActorId | None
```

Routing: shortest path by legs over open edges, computed at dispatch. **If a leg closes while the letter is in transit, the letter stops at its current node and waits.** Do not reroute, do not fail it. It sits in a harbour all winter and lands in the spring flood, still dated the previous autumn. This single rule produces most of the game's best moments for free.

Interception: `stream(seed, t, "letters.interception", letter_id)` against `risk` modified by region unrest and courier type. An intercepted letter is *delivered to someone else*, whose Belief now contains its claims. The sender never learns. Verify-by-reply is the only detection, and it costs two more turns.

Courier types: royal (slow, low risk, high status, costs a seal), merchant (fast, medium risk, and the merchant reads it), runner (fast overland only, high risk, no seal, deniable).

## 6.7 Personnel: scribes, literacy, and the corruption of the information layer

```python
@dataclass(frozen=True)
class Person:
    id: PersonId; name: str; role: str      # "scribe" | "diviner" | "overseer" | "official"
    age: int
    scripts: Mapping[str, int]              # {"akkadian": 70, "hurrian": 20, "linear_b": 0}
    competence: int                         # 0..1000
    fatigue: int                            # 0..1000
    faction: FactionId
    kin_interests: tuple[str, ...]          # e.g. ("trade.copper", "estate.rakba")
    loyalty: int
```

Three mechanics hang off scribes.

**(a) Stack ordering bias.** In B4:

```
perceived = base_importance
for interest in scribe.kin_interests:
    if item touches interest: perceived += 300
perceived = perceived * (1000 + faction_alignment_bonus) // 1000
sort descending by (perceived, item_id)     # item_id for total order
```

And the UI *tells the player the bias exists* without telling them its magnitude: a one-line note under the Stack, `Yabninu has placed Alashiya on top. His wife's brother trades copper.` The information is there; the inference is the player's.

**(b) Transcription error.** In B2, for each number appearing in each incoming document:

```
p_error = T("scribe_error", fatigue) * (1000 - competence) // 1000
if stream(seed, t, "scribe.error", f"{doc_id}:{field}").chance(p_error, 1000):
    apply a REALISTIC corruption: digit transposition, order-of-magnitude slip
    on the sexagesimal boundary (x60 or /60), or omission of a whole line
```

**This corrupts Belief, never World.** The granary really holds what it holds. The document says otherwise. Recovering truth costs one hour of attention (`inspect ledger`). This is the correct place to put unreliability: in the player's information, not in the world's physics. A game where the world is random is frustrating; a game where the *reports* are unreliable and the world is rigid is a detective story.

**(c) Literacy as a wall.** Per scenario, `ruler.scripts`. If the ruler cannot read a script, the document must be read *to* him, meaning:
- summary is the default and it is the scribe's summary
- full reading still costs full hours and still passes through the scribe's voice
- `dictate it myself` is unavailable for that script
- commissioning a second scribe to cross-check costs attention and inflicts a loyalty penalty on the first

Egypt: rich, eleven scribes, deep archive, ruler cannot read any of it. Ugarit: small, literate ruler, two scribes. Pylos: see 7.4.

Scribes take five years (120 turns) to train, per script. Losing one to plague or purge is a decade of institutional capability. Training more costs grain and attention now for literacy after the crisis, which is a bet almost no player makes on their first run.

## 6.8 Relations, gift exchange, and gossip

Diplomacy is not treaties with modifiers. It is a running exchange of objects that carries obligation.

```python
@dataclass(frozen=True)
class Relation:
    other: ActorId
    status_claim: str            # "brother" | "father" | "son" | "servant" | "lord"
    their_status_claim: str      # what THEY think the relationship is. May differ. This is a bug you can be in.
    esteem: int                  # 0..1000
    obligation: int              # signed. positive = they owe you
    last_gift_from_us: int       # value in silver-equivalent
    last_gift_from_them: int
    best_known_rival_gift: int   # the largest gift they are known to have received from anyone else
    known_rival_gift_source: ActorId | None
    unanswered_letters_from_them: int
```

Gift adequacy, evaluated when a gift arrives:

```
expected = max(
    last_gift_from_them * T("reciprocity", esteem) // 1000,
    best_known_rival_gift * 900 // 1000,
    status_floor[their_status_claim]
)
adequacy = 1000 * gift_value // max(1, expected)

adequacy < 700   : INSULT. esteem -150. They complain, in a letter, in detail, citing the weight.
700..899         : esteem -40, obligation unchanged
900..1099        : esteem +30, obligation +gift_value//4
1100..1499       : esteem +70, obligation +gift_value//3
>= 1500          : esteem +90 (diminishing), obligation +gift_value//3, and
                   your OTHER correspondents' best_known_rival_gift updates upward
```

That last clause is the trap. Overpaying one king raises the price of every other king, after gossip latency. The historical texture here is exact: kings wrote furious letters complaining that the gold received was underweight, and they compared it against what their rivals got.

**Gossip propagation.** Every gift, every insult, every marriage is a public fact. It enters a `Rumour` queue and reaches each other court after route latency, updating their `best_known_rival_gift` and their opinion of your reliability. Nothing you do diplomatically is private. Nothing.

**Status claim mismatch.** If `status_claim != their_status_claim`, using brotherhood language ("my brother") toward someone who considers you a servant is a protocol violation with a hard esteem penalty, detected by the grader (8.5). The player finds this out by doing it. Their reply will be memorable.

**Unanswered letters.** `unanswered_letters_from_them` increments each turn a letter sits unread or unanswered. At 3, esteem decays 30/turn. At 6, a vassal begins seeking another patron; you find out two to four turns after it happens, if at all. This is the mechanical version of the historical pattern: a vassal writes dozens of increasingly frantic letters about a neighbour swallowing his territory while the great king does nothing. His letters were true. They were on the pile. The pile was long.

## 6.9 Oaths

Oaths are explicit, clause-level, and readable by the player as documents.

```python
@dataclass(frozen=True)
class Oath:
    id: OathId
    parties: tuple[ActorId, ActorId]
    superior: ActorId | None
    gods: tuple[GodId, ...]
    sworn_turn: int
    sworn_by: PersonId          # WHO swore it. Personal, not institutional.
    clauses: tuple[Clause, ...]
    dissolved: bool
```

Clause types, each with a deterministic `check(world) -> bool`:

- `provide_troops(n, within_turns_of_summons)`
- `provide_goods(good, qty, per_year)`
- `no_contact_with(actor)`
- `extradite_fugitives_from(actor)`
- `recognise_succession_of(actor)`
- `do_not_shelter(group)`
- `open_route(route_id)`

A10 audits every clause every turn. A violation adds to `liability[oath_id]`, weighted by the number and rank of gods invoked. **Liability is invisible to the player and produces no direct penalty.** It raises the draw weight of entries in `content/decks/misfortune.toml`: crop failure, illness in the household, a fire, a stillbirth, a plague introduction. The player experiences misfortune and must *interpret* it.

**Oaths are personal and non-transitive.** They are sworn by a named man to a named man before named gods. Every succession anywhere, including the player's own, resets the relationship and requires re-swearing. There is never a province that is loyal. There is always a named man who is, or is not. When a vassal's father dies, the son owes you nothing until he swears, and he will want something for it.

Dissolution requires a ritual, a cost, and the consent of the superior party, or it does not happen at all. There is no "break treaty" button. The Amurru scenario (7.3) is built entirely on the fact that its two oaths are mutually unsatisfiable and neither can be dissolved.

## 6.10 Household, dynasty, reproduction

Not a stat block. A cast.

```python
@dataclass(frozen=True)
class HouseMember:
    id: PersonId; name: str; sex: str
    age_turns: int
    health: int                 # 0..1000
    fertility: int              # 0..1000, age-curved via T("fertility", age, sex)
    location: PlaceId           # may be a foreign court
    spouse: PersonId | None
    mother: PersonId | None; father: PersonId | None
    faction: FactionId
    own_agenda: str             # drives their LetterIntents
    is_heir_rank: int | None
```

- **Conception**: A5, for each co-located fertile married pair, `chance(f(fertility_a, fertility_b, health), 1000)` from `stream(seed, t, "house.conception", pair_id)`. Pregnancy is a `Scheduled` birth 20 fortnights out. Not a slider. You receive outcomes and adapt.
- **Child mortality**: age-banded table, checked yearly. It is high. This is why heirs past the second are insurance, and simultaneously factions.
- **The queen mother is an institution**, not a stat: her own household, her own revenues from her own estates, her own correspondence, her own faction, and the power to make your succession difficult. She has a tab entry.
- **Marriage abroad is the primary instrument of foreign policy.** A daughter sent to a foreign court becomes a permanent asset who is also an independent agent with her own `own_agenda`, writing you letters, sometimes against your interest, always with information you cannot get any other way. She is the best intelligence source in the game and she is not on your side.
- **The Egyptian exception**: Pharaoh may receive foreign daughters and may never send one. It is a card he holds and cannot play. Implement it as a hard rule in the Pharaoh scenario, not a soft penalty.
- **Succession**: on the ruler's death, run a deterministic succession resolution over heir rank, faction backing, legitimacy, and who is physically present at the seat. Then reset every oath in the game. Then continue play as the successor, with a *new* regnal year 1, which breaks every date correlation the player had built. That is not cruelty, it is the historical condition.

## 6.11 Divination

The only legitimate way to reduce uncertainty, and it is a political act.

```
1. Engine selects a TRUE future fact from the precomputed future:
   next harvest band, whether a named person dies within 8 turns,
   whether a route closes, whether an arrival is hostile.
2. accuracy = T("divination_accuracy", diviner.competence)
            + T("offering_bonus", offering_value)          # capped
3. if stream(seed, t, "divination", query_id).chance(accuracy, 1000):
       reported = true_value
   else:
       reported = a plausible neighbouring value (band +-1, or negated boolean)
4. faction bias: if the diviner's faction has a policy preference,
   shift reported one band toward the answer that supports it, with probability
   T("diviner_bias", loyalty)
```

The player is never told the accuracy. Bad omens carry a legitimacy cost if defied: acting against a published omen costs `legitimacy -80` whether or not the omen was correct. Suppressing an omen costs attention and risks a leak.

## 6.12 Plague

Integer SIR per settlement, and a theological puzzle bolted on top.

```
per settlement:  S, I, R, dead
new_infections = S * I * beta // (pop * 1000)
recoveries     = I * gamma // 1000
deaths         = I * mortality // 1000
```

Introduction: any arrival (letter courier, caravan, troop return, refugee group) from a node with `I > 0` carries a `chance(exposure, 1000)` of seeding. Quarantine is an available action: it closes a route, costs trade, costs esteem with the correspondent, and works.

**The theological layer, which is the good part.** When a plague begins, the engine deterministically designates a `cause_oath_id`: a genuinely violated oath, possibly sworn by the player's *predecessor* and present in the archive from turn 1. The player must find it.

- `expiation(oath_id)` is an action. Correct oath: `beta` drops by 40 percent for the duration and legitimacy rises. Wrong oath: costs the offering, costs attention, and nothing else happens. No feedback distinguishing "wrong oath" from "correct oath, slow effect", except the epidemic curve itself.
- This turns an epidemic into an archive search. Tab 2 becomes the most important screen in the game for ten turns. It is accurate to the period: a Hittite king did exactly this, searching his predecessors' records for the broken oath that had angered the gods, and left prayers about it.
- Populate `content/corpus/predecessor_archive/` with 20 to 40 authored documents per scenario, of which several record oaths, of which one or two are quietly violable. Author them so that a careful reader can narrow the field to three candidates but not to one.

## 6.13 Displacement, and where the Sea Peoples come from

The crown mechanic. There is no invader faction in the content files. There is no scripted invasion.

All four courts are simulated every game. The three the player is not running are driven by `engine/systems/rivals.py`, a deterministic policy table, with no model involvement.

```python
@dataclass(frozen=True)
class DisplacedGroup:
    id: GroupId
    size: int
    origin: PlaceId
    cause: str                       # "famine" | "plague" | "raid" | "flight_from_debt"
    skills: tuple[str, ...]          # "sailing" | "metalworking" | "archery" | "farming"
    coastal_knowledge: Mapping[PlaceId, int]   # 0..1000 per place they have seen
    refused_by: tuple[ActorId, ...]
    settled_at: PlaceId | None
```

A14 each turn:

1. Generate displacement from real pressures: settlements with `debt_weeks >= 4`, harvest failures, plague deaths above threshold, raided places. Size proportional to the pressure. No random spawning.
2. Groups travel to the nearest reachable court.
3. Each court receives them and chooses per policy: **settle** (labour gained, mouths gained, unrest with existing dependents), **arm** (troops gained cheaply, and they now know your dispositions), **refuse** (nothing gained, they move on and remember), **enslave** (labour gained, high unrest, maximum grievance).
4. Refused and enslaved groups accumulate into the `Coalition`.

```python
@dataclass(frozen=True)
class Coalition:
    members: tuple[GroupId, ...]
    strength: int                    # sum of sizes, decayed by attrition
    grievance: Mapping[ActorId, int] # who refused them, weighted by size and treatment
    knowledge: Mapping[PlaceId, int] # union of coastal_knowledge, max per place
```

Raid triggers: when `strength` crosses an authored threshold and the sailing season is open, the coalition raids. Target selection is `weight = grievance[owner] * knowledge[place] * (1000 - garrison_strength[place]) // 1_000_000`, argmax with deterministic tiebreak. Raids reduce stores, kill dependents, and produce more displacement, which feeds the coalition. It is a positive feedback loop with real inputs.

The result is that the coalition which eventually burns the palaces is *assembled out of the people the four courts collectively refused*. It is the aggregate of several hundred small decisions about hospitality, each made by someone with good reasons. Make sure the epilogue says so, by name, citing the turns.

## 6.14 The collapse index

A derived world value. **Never displayed. No doom clock. No progress bar.**

```
collapse = 1000
  - T("trade_volume", total_intercourt_trade_last_year) // 4
  - T("archives", count_of_functioning_archives) // 8
  - aggregate_arrears_across_all_courts // K
  - coalition.strength // K2
  - total_plague_load // K3
```

It gates event deck weights and nothing else. The player perceives it only through diegetic proxies:

- letters from a correspondent simply stop arriving, and the Known World node dims, and then dims further
- merchant petitions start quoting worse terms
- the range of goods offered in trade contracts narrows
- more items in the Stack are internal and fewer are foreign
- an entire correspondent disappears with no event, no notification, no explanation

Do not add a notification. The absence is the mechanic.

## 6.15 Rites and legitimacy

`content/scenarios/*.toml` authors a fixed rite calendar. Rites are non-negotiable calendar obligations that pre-deduct attention and consume goods.

```toml
[[rites]]
id = "akitu"; fortnight = 1; hours = 4
requires = {grain = 400, wine = 60, oil = 20}
skip_penalty = {legitimacy = -180, unrest = 120}
skip_generates_deck_weight = {misfortune = 200}
```

Skipping the festival to fund a campaign is always available and always expensive. Offering *less* than required is a partial-credit path with its own penalty curve, and the temple writes to you about it either way.

`legitimacy` gates: whether vassals answer a summons, whether the succession is contested, whether officials obey an unpopular allocation order, whether a suppressed omen leaks.

## 6.16 Seals and forgery

Cylinder seals authenticate. `Seal` objects are held by named people. A lost or stolen seal is a genuine emergency: forged letters bearing your seal begin arriving at other courts and *you find out through gossip latency*.

Incoming letters have a `seal` field. `verify_seal` costs one hour and returns truth. Forged letters exist (the engine generates them from rival intents), and paranoid verification of everything consumes the entire attention budget, which is exactly the trade the mechanic is for.

## 6.17 Archive

Every document ever sent or received, plus the authored predecessor archive, plus internal records.

```python
@dataclass(frozen=True)
class Document:
    ref: DocRef
    kind: str            # "letter_in" | "letter_out" | "oath" | "ration_record" | "inventory" | "omen"
    received_turn: int
    sender: ActorId | None
    dated_as: str        # THE SENDER'S regnal date string, e.g. "yr 4, Hiyaru, latter half"
    body: str
    asserted: tuple[Claim, ...]
    tags: tuple[str, ...]
```

**Sorting is by `received_turn` only.** The Archive cannot sort by the sender's date, because the sender's dates are in a different calendar with a different epoch, which is the historical truth and a deliberate design constraint. The player will act on a letter written before one they already answered.

Search: keyword and tag, one hour per query. `librarian` AI role (8.6) summarizes result sets, and must cite `DocRef`s so the player can open the real document, which is authoritative.

For Pylos, tab 2 is greyed out permanently. See 7.4.

---

## 6.18 Institutions: the household as a machine (M12)

**A dependent group is not a payroll row. It is an institution with a building, a head, a condition and an output.** This is one change, and it is the change that turns rationing from a number you regret into a machine you can watch break.

```python
@dataclass(frozen=True)
class Institution:
    id: InstitutionId
    name: str                 # "the harbour of Ma'hadu", "the workshops of the palace"
    kind: str                 # harbour | granary | walls | workshop | temple
                              # | archive | canal | road | household | garrison
    place: PlaceId
    head: PersonId | None     # a real person, with competence and loyalty
    group: GroupId            # the people it feeds -- the old DependentGroup, unchanged
    condition: int            # 0..1000, decays; the fabric of the thing
    capacity: int             # what it could do if whole and fed
    upkeep: dict[str, int]    # goods per fortnight beyond rations
```

`DependentGroup` (6.3) is **not replaced**. It stays exactly as it is and becomes the institution's staff, so arrears, loyalty, desertion and the named petitioner all keep working untouched. The institution is a new layer over it, and every number below is derived, never stored twice:

```
effective = capacity * condition // 1000 * output_modifier // 1000
```

Starve the staff and `output_modifier` falls (6.3, unchanged). Neglect the fabric and `condition` falls. Both multiply. Neither is announced.

### What each kind actually does

| kind | effective output feeds | what failure looks like |
|---|---|---|
| `harbour` | ships cleared per fortnight; cap on goods moved by sea | your tin does not arrive and no letter says why |
| `granary` | storage capacity; spoilage divisor (6.2) | the surplus you were counting on rots |
| `walls` | defence weight in raid resolution (6.13) | a raid that would have bounced does not |
| `workshop` | bronze output, chariot replacement (6.5) | the melt ledger climbs faster |
| `temple` | rite capacity; a skipped rite costs double if the temple is failing | legitimacy bleeds and the omens sour |
| `archive` | hits returned per search (6.17); search cost rises to 2h below 400 | the puzzle gets harder without being told it did |
| `canal` | irrigation multiplier per estate (6.4) | yield falls a year later, on a curve nobody drew |
| `road` | courier days to one neighbour (6.6) | everything from that direction arrives a fortnight stale |

### Decay

```
condition -= base_decay[kind]                        # 4..12 per fortnight, authored
condition -= 20 if upkeep unpaid this fortnight
condition -= 40 if head is None                      # nobody is minding it
condition = clamp(0, 1000, condition)
```

Nothing warns. The condition is on the CITY screen for anyone who looks, in the same way the melt ledger is on STORES (D19).

### Heads, appointment and dismissal

Every institution wants a head. A head is a `Person` — from the house (6.10), or a named commoner the player has corresponded with. Competence and loyalty come from the same authored ranges the diviner and the officials already use.

```
head competence -> condition decay is halved at 800+, doubled below 300
head loyalty    -> skim: a disloyal head reports condition higher than it is
```

**This is where the three layers of number (D11) reach the city.** The condition on the screen is what the head reported. `inspect <institution>` costs an hour and returns the true figure. A head who has been unpaid for six fortnights reports a granary fuller than it is, and the player finds out at the threshing.

`appoint <person> <institution>` and `dismiss <institution>` are free actions taken on the HOUSEHOLD screen; the consequence is not free, because a dismissed head has a family and they write.

### Foreign institutions

**Every city in the world has the same shape and the player cannot see any of it.** A foreign `Institution` carries the same fields and is projected into Belief only where the player has been:

```
knowledge[place] = "never" | "hearsay" | "visited"
```

`never` shows the place and nothing else. `hearsay` shows kind and a distorted capacity, from letters and from what merchants say. `visited` shows the reported figure, once an envoy has stood in it — which is still the *head's* figure, not the truth.

That is what makes trade a thing you do with people rather than with a price table: Gubla has a great harbour and no granary; Carchemish has walls and no port. You learn it by going.

---

## 6.19 Justice: the petition and the verdict (M12)

The hall already queues the people waiting on the king. They must become rulable, because judging disputes is the single largest thing a Late Bronze Age king actually did with his day, and the game has no representation of it at all.

```python
@dataclass(frozen=True)
class Petition:
    id: PetitionId
    petitioner: PersonId
    against: PersonId | None
    kind: str          # debt | inheritance | boundary | theft | exemption
                       # | conscription | injury | precedence
    claim: dict[str, int]      # what is asked for, in goods or men or land
    truth: dict[str, int]      # what is actually so -- never projected
    waiting: int               # fortnights stood in the hall
    faction: str               # whose side of the court he is
```

`hear` costs an hour and reveals the claim in full and the *counter*-claim. It does not reveal `truth`. Ruling without hearing is allowed and is often correct: a king who hears every case hears nothing else.

The verdict is one of four:

```
for       -- grant the claim
against   -- refuse it
split     -- a compromise; costs nothing extra and satisfies nobody fully
defer     -- send them away to come back. waiting += 1, and it compounds
```

Effects, all deterministic:

```
legitimacy   += 20 if the verdict matches truth, -35 if it contradicts truth
             (the court finds out eventually; the correction lands 2-6 turns later)
faction mood += 60 for the side favoured, -60 for the other
unrest       += 8 per petition still waiting at 6 fortnights
precedent    -- the ruling is stored and cited back at you by a later petitioner
```

**Precedent is the mechanic worth building.** A ruling on a boundary case in year 2 is quoted in a petition in year 9, and ruling the other way costs double legitimacy. The archive stores your own verdicts and they are searchable (6.17), which means the player can look up what he did and usually will not.

Nothing marks a petitioner as honest. Nothing tells the player which verdict matched the truth. The correction arrives as a letter from someone who was there.

---

## 6.20 Revenue: dues, and the harbour (M12)

The game currently has income from the threshing floor and nothing else, which makes the granary the only dial in the economy. Two more, both real, both a squeeze:

**The land due.** A share of the harvest taken at threshing, authored per scenario at a base of 300 (30%).

```
take        = harvest * due_rate // 1000
unrest     += (due_rate - base_rate) // 4      per fortnight it stands raised
flight      = estates lose 2% of hands per 100 points above base, cumulative
```

Raise it before a bad year and you eat. Raise it twice and the fields empty, and hands do not come back when you lower it again.

**Harbour dues.** A levy on every cargo cleared, in kind. It scales with the harbour's `effective` output (6.18), which is why starving the harbourmaster costs you twice.

```
income      = cleared_cargoes * due_rate // 1000
merchant esteem -= (due_rate - customary) // 20     for every merchant who trades here
```

Merchants respond by trading elsewhere, and the response is *slow* — three to six fortnights — so the player sees the income before he sees the cost. That lag is the whole design.

---

## 6.21 Building, and the corvée's second use (M12)

The **corvée** keeps its name. It is unpaid labour owed to the crown, called up in days, and it is the only source of hands the player controls directly. It already exists (6.4) for canals; it now has somewhere to go.

```python
@dataclass(frozen=True)
class Project:
    id: ProjectId
    institution: InstitutionId    # what it repairs, or "" on a build
    kind: str                     # what is going up
    place: PlaceId
    name: str
    days_needed: int
    days_done: int
    condition_target: int         # what it stands at when finished
    capacity: int                 # on a build only
    started_turn: int
    spent: tuple[tuple[GoodId, int], ...]   # eaten so far; never returned
```

Materials are not a per-project bill of quantities. They are **what the men
eat**: one rate in `content/works.toml`, charged per thousand days worked,
whatever is being built. A building site is four hundred men who have to be fed,
so the material cost of a wall is grain — the same grain the granary is holding
against the year the harvest fails.

The working season is one named span (`low_water` at Ugarit) and it is checked
per fortnight, not per project. A repair is priced at `(1000 - condition) *
repair_days_per_point` **when the order is given** and never revised: the fabric
goes on decaying while the men work, so a repair commissioned at 400 does not
arrive at 1000, and the difference is what it cost to have left it so long.

```
build   <kind> <place>     a new institution, or an expansion of one
repair  <institution>      cheaper than building, and nothing reminds you
```

Rules that make it a decision rather than a purchase:

* **Materials are consumed as work proceeds.** An abandoned project is a loss, not a refund.
* **Work only happens in the right season.** Mudbrick does not go up in the rains.
* **The corvée is the same hands as the harvest.** Days spent on a wall in the sowing fortnights are days the estates did not get, and the bill lands a year later (6.4).
* **Nothing is instant.** A granary is 900 days. A wall is 4,000. At 400 days a fortnight you are committing a year and a half of your labour and finding out whether you needed it in year 11.

That last line is the point of the whole system: **building is a bet on which crisis is coming**, made with the same hands that feed you, resolved long after you have forgotten you made it.

---

## 6.22 Succession, appointment, and the house as a supply of men (M12)

6.10 already has the house, reproduction and succession. What it lacks is a use for the people in it.

```
place <person> <post>
```

where a post is an institution headship, a governorship of a town, a command, or a foreign court (which is the existing `marry_abroad`, generalised). A placed person:

* stops being a claimant at home and starts being an agent abroad, with the M9 agency machinery unchanged
* reports on what he heads — with his own competence and loyalty (6.18)
* accumulates his own interests, and a son governing a rich town is a son with an army

`name_heir <person>` is a free action on the HOUSE screen, and it is contestable: naming a second son over a first raises the first's faction and lowers legitimacy by 60. Not naming anyone at all is the default and costs nothing until you die.

**The tension the system exists to create:** every trustworthy man is a member of your house, every member of your house you place is a rival you have armed, and every post you leave empty decays at 40 a fortnight.

---

# PART 7. THE FOUR RULERS

Asymmetry lives in `content/scenarios/*.toml`, not in code branches. If a scenario needs a code branch, that is a signal the system is underspecified. The one permitted exception is capability gating (which tabs exist), which is a declared list in the scenario file that the TUI reads.

```toml
[capabilities]
tabs = ["stack","archive","stores","lists","house","world","rites","desk"]
can_write_letters = true
scripts_ruler_can_read = ["akkadian","ugaritic"]
archive_is_persistent = true
```

## 7.1 Pharaoh (Egypt)

- **Constraint: attention and ritual.** You have more grain than any problem requires and no way to get it there in time.
- `attention_base = 12` but obligatory rites consume 4 to 6 of it most turns.
- 11 scribes, deep persistent archive going back 40 regnal years, and `scripts_ruler_can_read = []`. Everything is read to you.
- Enormous gold reserves. Every foreign king wants gold and will accept it, so `esteem` is cheap to buy and `obligation` is easy to accumulate. The trap is that gold does not solve grain logistics and does not shorten a courier route.
- Levantine vassals write repeatedly and truthfully and stay on the pile. The Stack is 25 to 40 items every turn against a badly depleted budget. Triage is the entire game.
- Hard rule: may receive foreign brides, may never send an Egyptian one.
- Failure mode to design toward: nothing feels urgent until it is finished.

## 7.2 Ammurapi of Ugarit

- **Constraint: sworn to Hatti, wealthy because of everyone else, militarily hopeless.**
- `attention_base = 10`, few rites, literate ruler, 2 scribes. The tightest, cleanest ruleset. Make this the default and the tutorial.
- Oath to Hatti with `provide_goods(grain, N, per_year)` and `provide_troops(n, within=2)`. Your grain ships and your troops go north while your own coast is watched by four men in a tower.
- Your real asset is that you hear things first, because every merchant passes through. `Rumour` arrival latency to Ugarit is the shortest in the game. The gameplay question is therefore not what you know but **who you tell**, and telling is how you buy esteem without gold.
- Tiny military. `troops` total under 400. There is no military solution to anything.
- Should end in fire in nearly every run. The variance is in the archive.

## 7.3 The king of Amurru, vassal of Hatti

- **Constraint: two overlords whose territories touch at your border, two oaths, and no survival path that is not perjury.**
- Two `Oath` objects with mutually unsatisfiable clauses: `no_contact_with(egypt)` sworn to Hatti, and a standing obligation to Egypt from your father's reign that Egypt has not forgotten. Neither can be dissolved without the superior's consent, which neither will give.
- `liability` therefore accrues from turn 1 no matter what the player does, which means misfortune arrives and the player must interpret whether it is punishment, and for which oath, and there is no way to know.
- The oath documents are readable in full, with clauses and god-lists, from turn 1. The player can and should read the trap. Reading it does not help.
- This is the scenario where 6.9 and 6.12 combine: divine liability, unfalsifiable misfortune, and an archive search for a cause that has three plausible answers.

## 7.4 The wanax at Pylos

The cool one, and the one that justifies the whole architecture. It works because of a real fact about the period.

Akkadian cuneiform is the international diplomatic language. Linear B is not a writing system in that sense. It is an accounting notation. It records sheep, bronze issued to smiths by weight, women and children by trade, ration allotments. **It cannot write a letter to a foreign king**, and no Mycenaean palace has produced an archive of international correspondence, because there was not one.

So this scenario deletes two tabs:

```toml
[capabilities]
tabs = ["stack","stores","lists","house","world","rites"]     # no archive, no desk
can_write_letters = false
scripts_ruler_can_read = ["linear_b"]
archive_is_persistent = false
```

- **No desk.** You cannot write to anyone. Diplomacy happens by sending a man, physically, who costs attention and travel time and may be lying when he returns.
- **No archive.** Linear B tablets are unfired clay, a single fiscal year's working record, discarded and rewritten. Every turn, last turn's records are gone. The Stack is the only memory the game gives you, and it does not persist. You cannot re-read a rumour. You cannot look up what the captain said in the spring. **Take notes on paper. That is the intended experience.**
- Everything arrives as **speech**: captains, the lawagetas, a smith of the damos with no tin and a temper, a priest. `hear` costs 1 to 2 hours and produces a Claim with a `verbal` channel and heavy decay.
- Records that *do* exist: `ta-ra-si-ja`, the bronze issued to named smiths and not yet returned. Track it exactly. It is the one place Pylos has better information than anyone.
- The damos owns land you do not control. A separate `Estate` owner type with its own consent mechanic for corvee.
- The palace is unwalled. `o-ka` coastal watch posts, authored from the actual tablet series, are your only warning system, and manning them takes men from the harvest.
- No `provide_troops` oath to anyone, no patron, no help coming.

Alternative if you want a Greek court that *can* write: Millawanda/Miletus, an Ahhiyawan foothold in the Hittite sphere, corresponding in Akkadian through a Hittite intermediary who reads everything. Keep it as a stretch scenario. Pylos first, because the deleted tabs are the strongest statement the game can make.

---

# PART 8. THE AI LAYER

Read Part 0 again before writing any of this.

`qwen3:14b` is capable but not clever. It is good at: rewriting intent into register, maintaining a persona over a few hundred tokens, filling a schema, and pattern-matching a sentence to one of thirty verbs. It is bad at: arithmetic, multi-step consequence reasoning, keeping quiet about things it was told, and staying in scope over long context. The role split below is drawn along exactly that line.

## 8.1 Transport

```python
# ai/client.py
OLLAMA = "http://127.0.0.1:11434/api/chat"

def call(role: str, messages: list[dict], schema: dict | None,
         seed: int, max_tokens: int, timeout_s: float) -> str:
    payload = {
        "model": "qwen3:14b",
        "messages": messages,
        "stream": False,
        "think": False,                 # REQUIRED. Qwen3 hybrid reasoning must be off.
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "top_k": 1,
            "top_p": 1,
            "repeat_penalty": 1.05,
            "seed": seed,
            "num_ctx": 8192,
            "num_predict": max_tokens,
        },
    }
    if schema: payload["format"] = schema      # Ollama structured output
```

Notes specific to this model and runtime:

- `"think": False` is mandatory. Qwen3's thinking mode burns hundreds of tokens and wrecks latency. If the installed Ollama build ignores the flag, append `/no_think` to the system prompt as a fallback and strip any `<think>...</think>` block from the response before parsing.
- `temperature: 0, top_k: 1` for every role including prose. You want reproducibility over variety. Variety comes from the fact that the *prompt* differs every time, because the world state differs.
- Budget with real numbers: Q4_K_M is about 9 GB of VRAM. On a 24 GB consumer card expect 30 to 55 tokens per second. Therefore: parser calls (max 80 output tokens) land in 1 to 3 seconds and are acceptable synchronously. A letter (250 to 350 tokens) is 6 to 12 seconds and is **not** acceptable synchronously more than once per player action.
- **Prompt prefix caching.** Structure every prompt as `[stable system block][stable world primer][variable tail]`. Keep the stable part byte-identical across calls within a session so the KV cache is reused. This is worth several seconds per call. Put persona cards in the stable block per correspondent and cache per (role, correspondent).
- Keep total prompt under 2000 tokens. Persona cards 120 to 180 tokens. Two few-shot examples maximum, three only for the composer.
- Timeouts: parser 8 s, composer 25 s, voicer 25 s. On timeout, fall through to `ai/fallback.py` and do not block the turn.

## 8.2 Caching and the run log

```python
key = sha256(role + "|" + model + "|" + canonical_json(messages) + "|" + str(seed))
```

Cache in memory for the session and on disk under `saves/<slug>/ai_cache/`. Every call, hit or miss, appends to `ai_log`:

```json
{"call_id": "c0417", "turn": 47, "role": "composer", "prompt_sha": "...",
 "raw": "To the Sun, Great King, my lord: thus says Ammurapi...", "cached": false}
```

`tools/replay.py` runs with the model unreachable and must complete. If it needs a `call_id` not in the log, that is a bug in whichever code path called the model outside phase C.

## 8.3 Role A: Parser (prose to Action)

The player types English. Output is a JSON object matching a **closed schema generated from the currently legal action set**.

Engine provides an affordance list. This is the single most important input and it must be built from Belief, per turn, per tab:

```
LEGAL ACTIONS THIS TURN (tab: stack, hours left: 6)
  READ_FULL      item=i|ii|iii|iv|v            cost 2-3
  READ_SUMMARY   item=i..xiv                   cost 1
  HEAR           petitioner=capt_alkidas|lawagetas|smith_wito
  INSPECT_LEDGER  ledger=granary_mahadu|granary_seat|tarasija
  ALLOCATE       group=<id> qa=<int>           cost 0, effect next turn
  SET_PRIORITY   order=<list of group ids>     cost 0
  DICTATE        to=<actor id> intent=<free text>
  VERIFY_SEAL    item=i|ii
  COMMISSION_DIVINATION  question=harvest|arrival|health
  ASSIGN_TROOPS  formation=<id> task=garrison|harvest|campaign|watch place=<id>
  EXPIATE        oath=<oath id>
  SEARCH_ARCHIVE query=<free text>
  END_TURN

ENTITIES IN SCOPE
  groups:   smiths_palace(140 heads, arrears 2 wks) | garrison_mahadu(60) | weavers(210)
  actors:   hatti_king | alashiya_gov | sinaranu_merchant | temple_baal
  places:   ma_hadu | rakba | seat
  oaths:    oath_hatti_1 | oath_father_egypt
```

Schema:

```json
{
  "type": "object",
  "oneOf": [
    {"properties": {"kind":{"const":"actions"},
                    "actions":{"type":"array","maxItems":4,
                      "items":{"type":"object","required":["verb"],
                        "properties":{"verb":{"enum":["READ_FULL","READ_SUMMARY","HEAR","INSPECT_LEDGER","ALLOCATE","SET_PRIORITY","DICTATE","VERIFY_SEAL","COMMISSION_DIVINATION","ASSIGN_TROOPS","EXPIATE","SEARCH_ARCHIVE","END_TURN"]},
                                      "args":{"type":"object"}}}}},
     "required":["kind","actions"]},
    {"properties": {"kind":{"const":"clarify"},
                    "question":{"type":"string","maxLength":160}},
     "required":["kind","question"]}
  ]
}
```

Rules, all enforced in code after the model returns:

1. Every `args` value must be an ID present in the affordance list, or an integer. Anything else is rejected and becomes a clarify.
2. `maxItems: 4`. A player line cannot become a turn's worth of actions.
3. **Ambiguity never produces an error message.** It produces `clarify`, which the TUI renders as the scribe asking, in character, and asking costs one hour. `Yabninu: my lord. Which Abdi? The one at Rakba, or your brother's man?`
4. Total cost of the parsed actions is computed by the engine and confirmed before applying if it exceeds 3 hours: `That is 5 hours of the 6 you have. Proceed?`
5. The parser is **never on the critical path**. `:` opens a command mode with exact syntax (`:alloc smiths_palace 8400`, `:read ii full`, `:end`). Everything reachable by prose is reachable by command. If the model is down, the game plays.
6. A deterministic pre-parser runs first: if the line matches a high-confidence regex or a fuzzy match above threshold against a verb plus known entity, skip the model entirely. This handles maybe 40 percent of input for free and makes the game feel fast.

## 8.4 Role B: Composer (intent to letter)

Input: sender persona card, recipient persona card, relation state **expressed in words, not numbers**, the intent tuple, the required formula list from `content/formulae.toml`, and two authored exemplars from `content/corpus/letters/`.

```
YOU ARE the scribe Yabninu, writing at the dictation of Ammurapi, king of Ugarit.
Write the tablet. Output the letter text only. No commentary. 10 to 18 lines.

RECIPIENT: the Great King of Hatti. He regards Ammurapi as his SERVANT.
Ammurapi must address him as lord and must not use kinship language.
RELATION: he is displeased. Grain owed under oath is late. He has written twice.
INTENT: excuse the late grain ships, blaming the closed sea.
REQUIRED FORMULAE (use exactly):
  opening: "To the Sun, Great King, my lord: thus says {SENDER}, your servant."
  prostration: "At the feet of my lord, seven times and seven times I fall."
FACTS YOU MAY CITE (use no other numbers):
  ships promised: 4
  ships sailed: 1
  the sea closed in the latter half of Ittabnu
EXEMPLARS:
  <two authored letters>
```

Then the letter is graded by code, and the grade feeds the simulation.

## 8.5 The Protocol Grader (deterministic, and this is why the AI cannot cheat)

`ai/grader.py`. No model. Pure functions over text plus `content/formulae.toml`.

```toml
[hatti.servant_to_lord]
opening_regex = '^To the Sun,? Great King, my lord'
requires_self_designation = 'your servant'
prostration_regex = 'seven times and seven times'
forbidden_terms = ["my brother", "we are equals", "I ask in return"]
max_topics = 1
forbidden_pattern_excuse_and_request = true
gods_required_if_oath_mentioned = ["storm_god_of_hatti", "sun_goddess_of_arinna"]
```

```python
@dataclass(frozen=True)
class ProtocolScore:
    address_ok: bool
    prostration_ok: bool
    self_designation_ok: bool
    topic_count: int
    violations: tuple[str, ...]
    total: int          # 0..1000, from an authored weight table
```

`total` feeds `esteem` delta and the recipient's reply intent. Concrete violation types with teeth:

- **Kinship overreach**: using "my brother" toward someone whose `their_status_claim` for you is `servant`. Hard `esteem -200`, and their reply is a lecture.
- **Excuse plus request in one tablet**: this reads as a bargain, and he does not bargain with servants. `esteem -90`, and the request is simply not answered. The scribe should warn about this *before* sending: `Yabninu: my lord. Two tablets. Two couriers. Two fortnights.` Splitting is a real, correct, costly solution.
- **Multi-topic**: each topic past the first has a declining chance of being answered at all.
- **Missing prostration to a superior**: `esteem -120`.
- **Wrong god invoked when citing an oath**: `liability` note, and the recipient's diviner is consulted, which delays the reply by two turns.

Desk buttons: `[send] [split in two] [dictate it myself] [burn]`.

`dictate it myself` drops the player into raw text entry with no scribal assistance, and the grader applies to their text identically. A player who learns the actual formulae outperforms the scribe, because the scribe will occasionally miss a clause and never innovates. That is the skill ceiling of the game and it is a real one.

`tools/corpus_lint.py` runs the grader over every authored exemplar and asserts they all score above 900. If your exemplars fail your own grader, the grader is wrong.

## 8.6 Role C: Voicer (NPCs), and the numeric guard

**The engine decides what is said. The model decides how.**

For each `LetterIntent` from A15, the engine has already computed: which facts the actor asserts, whether each is true or distorted, what they want, and their tone band. The model receives only the final, already-distorted facts.

```
YOU ARE Abdi-milki, governor at Alashiya. You are frightened and you exaggerate.
You have written twice and had no reply. This is your third asking.
TONE: formal, increasingly desperate, not yet insolent.
WRITE: 8 to 14 lines. Output the letter only.
FACTS YOU ASSERT (you may use no numbers other than these):
  ships seen off the coast: 20
  men you have under arms: 30
  grain remaining: 12 days
  you have written: 3 times
WHAT YOU WANT: troops, and an answer.
```

The true figures were 7 ships and 45 days of grain. The engine distorted them via `Relation.report_bias` and `distortion.py`. The model never saw the truth and cannot leak it.

**`ai/numeric_guard.py`** runs on every generated string:

```python
def guard(text: str, allowed: set[str]) -> tuple[bool, list[str]]:
    found = extract_numerals_and_number_words(text)   # digits AND "seven", "twenty", "a hundred"
    stray = [n for n in found if normalise(n) not in allowed]
    return (not stray, stray)
```

Allowed set = the fact list, plus formulaic numbers declared in `content/formulae.toml` (the "seven times and seven times" of the prostration, "thousand" in blessings). On failure: one regeneration with the stray numbers named in a corrective line, then fall back to the template in `ai/fallback.py`. Log every failure to `ai_log` with a `guard_fail` flag so you can tune prompts against real data.

This one validator is what makes Law 1 enforceable rather than aspirational. Build it in milestone M4, before you build the composer.

## 8.7 Generation scheduling

Never generate 30 letters synchronously at turn start. The turn would take four minutes.

- A15 produces intents. No text.
- On entering phase C, a background worker begins generating bodies **in Stack order**, top item first.
- Reading an item whose text is not ready shows the fallback template immediately, and swaps in the model text if it arrives while the player is still on the item. Never make the player wait on a spinner.
- Summaries are generated from the intent, not from the body, so a summary is always instantly available and is *not* a summary of the text the player would read in full. Which is correct, since the summary is the scribe's, and this is exactly where scribal filtering lives.
- Cap generation at 8 bodies per turn. Items past that use templates. Nobody will notice, because the interesting items are at the top by construction.

## 8.8 Role D: Librarian and Epilogue

**Librarian**: given 3 to 12 archive hits (title, date, 200 char snippet), write a 3-line orienting summary and cite every `DocRef`. It may not assert anything not in the snippets. The player opens the real document, which is authoritative. Cheap, low stakes, high value.

**Epilogue**: given a deterministic fact list assembled by `engine/systems/scoring.py` (stratigraphy, tablet count, which documents survived, the last unsent letter, continuity score components), write the excavation report prose. Everything factual is engine-supplied. If the model is unavailable, the templated version is still good, because the facts are the content.

## 8.9 The model must never see

Enforce with a test that asserts these keys never appear in any prompt string:

- true stock quantities the player has not verified
- the climate series or any future value
- `liability`, `collapse`, `cause_oath_id`
- `coalition.knowledge`, raid targeting weights
- any `World` field, ever
- another court's private state
- accuracy values for divination

Implementation: `ai/client.py` accepts only a `dict[str, str | int]` of pre-approved fields, built by `belief/project.py`, and raises on anything else. Make the boundary a type, not a convention.

---

# PART 9. THE INTERFACE

## 9.1 Frame

Target 100 x 36. Degrade to 80 x 24 by dropping the side rail and shortening item lines. Box drawing by default, `--pure-ascii` swaps to `+ - |`.

```
┌─ SAY TO THE KING ────────────────────────────────────────────────────────┐
│ AMMURAPI OF UGARIT · yr 3 · Ittabnu, latter half · sea: OPEN · turn 47   │
├──────────────────────────────────────────────────────────────────────────┤
│ [1]STACK  2 archive  3 stores  4 lists  5 house  6 world  7 rites  8 desk│
├──────────────────────────────────────────────────────────────────────────┤
│  audience remaining  ▓▓▓▓▓▓░░░░  6 / 10                                  │
│                                                                          │
│  THE STACK, as ordered by Yabninu the scribe                             │
│                                                                          │
│  ●  i.   Alashiya. Sealed, governor. Third asking.              [full 2] │
│  ●  ii.  Hattusa. Royal seal. Concerning grain. Not warm.       [full 3] │
│  ○  iii. Sinaranu, merchant. Unsealed. Wants his exemption.     [full 1] │
│  ○  iv.  Coast watch at Ma'hadu. Verbal, transcribed. Ships.    [full 1] │
│  ·   v-xiv.  Nine estate accounts.                           [summary 1] │
│                                                                          │
│  Yabninu has placed Alashiya on top. His wife's brother trades copper.   │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ > read me the one from Hattusa. all of it.                               │
└──────────────────────────────────────────────────────────────────────────┘
```

## 9.2 Conventions

- Freshness glyphs everywhere a claim is shown: `●` under 3 turns, `○` 3 to 8, `·` over 8. Dim the row with the glyph.
- Palette: amber and clay monochrome, three accents only. Red for arrears and unrest. Pale blue for the sea and for anything seasonal. Dim grey for stale. Never use colour as the sole carrier of information.
- The `>` line takes prose. `:` switches to command mode with a different prompt character and a hint bar. Tab completes IDs in command mode.
- Numbers always in display units with remainder: `1,204 parisu 18 qa`.
- Any number that came through a scribe is shown plainly. There is **no marker for possibly-mistranscribed**. The player learns to cross-check or does not.
- Every screen has a one-line diegetic footer in a named voice. Never a tooltip, never a help hint.

## 9.3 Tabs

1. **STACK** as above. Manual reorder costs 1 hour.
2. **ARCHIVE** search box, results with `DocRef`, sender's own date string, received turn. Sorted by received turn only. Full document view.
3. **STORES** every good, current stock, delta since last turn as a 24-turn ASCII sparkline, spoilage, and the melt ledger sitting quietly among the metals with no emphasis.
4. **LISTS** the ration priority list, drag-reorderable with `J`/`K`. Per group: name, heads, entitlement, allocated, arrears in fortnights, loyalty band as a word, function. This is the most important screen in the game and it should look like a payroll, because it is one.
5. **HOUSE** the family as a small ASCII tree, ages, health as words, locations including foreign courts, marriages, the queen mother's separate block.
6. **WORLD** the Known World: hand-authored node positions per scenario, edges drawn only where a route is known, node brightness from freshness, unverified rumour nodes drawn with `?`. No coordinates, no scale, no distances. It is a correspondence graph, not a map.
7. **RITES** the 24-fortnight calendar as a ring or a strip, obligations marked, hour cost shown, goods required, what happens if skipped.
8. **DESK** compose. Recipient, intent line, generated draft, the grader panel with pass and fail marks, scribe's advisory line, and the four buttons.

## 9.4 Sparkline

```python
BLOCKS = " ▁▂▃▄▅▆▇█"          # or ".:-=+*#%@" under --pure-ascii
```

24 turns wide, one column per fortnight, with the sailing-closed span shaded. Use it for stores, arrears, coalition sightings, and nothing else. Restraint here matters: a game about information scarcity should not have a dashboard.

## 9.5 The last screen

```
  TRENCH IV, PALACE OF UGARIT · destruction layer, 1190±30 BC

  ═══════════════════════════════════════════  topsoil
  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  collapse, roof tile
  ███████████████████████████████████████████  ASH  0.4 m
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  floor, occupation

  Recovered: 138 tablets, baked hard. The fire preserved them.

  Among them, in a kiln, unfired and unsent:

    "My father, behold, the enemy's ships came. My cities were burned,
     and they did evil things in my country."

  You dictated this on turn 61. It never left the building.
```

The unsent letter is real: `letters_in_transit` filtered to `at_node == seat and sent_turn == last_turn`. If there is none, the epilogue picks the last document the player dictated. The fires that destroyed these cities are the only reason we can read them, which is a bargain no player would accept and every one of these kings made. Say so.

## 9.6 The cell grid and its backends (M11)

The renderer's output type is a `Screen`: a rectangle of cells, each cell a
character, a foreground index, and a background index. Nothing above the grid
knows what draws it.

```python
Cell   = tuple[str, int, int]        # glyph, fg, bg -- one character, always
Screen = tuple[tuple[Cell, ...], ...]
```

Two backends consume a `Screen` and nothing else:

- **terminal** — ANSI to stdout. Development, `ssh`, and the degrade path. Must
  stay working; it is how the game is tested and how it is played by the sort of
  person who would rather play it in a terminal.
- **window** — Tk. This is what ships. A real operating-system window per
  surface: title bar, taskbar entry, moved and closed independently, and no
  console behind it.

The rule that makes this worth doing: **a screen is asserted, never a
screenshot.** Tests index cells and check glyphs and colours. No GUI is started,
nothing is compared by eye, and every panel is testable in the same headless run
as the engine.

Colour is a palette of at most sixteen entries, authored in content, and it is
**never the sole carrier of meaning** (Part 0's information rules do not stop
being true because the terminal got nicer). Every colour distinction has a glyph
or a word saying the same thing. `--pure-ascii` and monochrome are supported
paths, not afterthoughts.

**Windows are operating-system windows.** The hub is a small window, roughly the
size of a terminal, and it stays that size. Opening the archive, the map, the
desk or a letter opens *another OS window* — its own title bar, its own entry in
the taskbar, moved and closed on its own. The player arranges his own table.

This is the interface's organising idea and not a rendering detail. A king's
table has several tablets open on it at once, and the reason to pay for real
windows is that the player can put the granary beside the letter that makes a
claim about the granary and read both at the same time. Cross-checking a number
is the game's central act (Part 0, M3's target) and a single-surface interface
makes it a matter of memory. Here it is a matter of moving a window.

Consequences, accepted deliberately: no exclusive fullscreen, and no launcher
overlay, since those hook a graphics context this does not have. The hub owns
the session; closing it closes the game, and closing any other window is free.
Every window is reachable from the hub by keyboard alone, because a player who
has closed a window must never be stranded.

## 9.7 Scoring: continuity, not survival

No victory condition of survival, because that would be a lie about the period. Every ruler falls. The score is what outlives you, and it is presented as an excavation report, not a number.

```
continuity = w1 * dependent_groups_whose_named_members_have_descendants_still_on_a_list
           + w2 * turns_the_treaty_held_past_your_death
           + w3 * documents_of_yours_recovered
           + w4 * scribes_trained_who_outlived_you
           + w5 * displaced_groups_you_settled_who_did_not_join_the_coalition
           - w6 * arrears_outstanding_at_the_end
```

Report each component as a sentence with names and turn numbers, and cite the coalition's composition against the turns on which each group was refused, by whom. Including the turns where it was the player.

---

# PART 10. TESTING

## 10.1 Golden determinism tests

`tests/golden/<name>/{seed,scenario,actions.jsonl,expected_hash}`. The runner replays and asserts the hash. Twenty of these, covering: an empty 200-turn run per scenario, a famine run, a plague run with correct expiation, a plague run with wrong expiation, a coalition raid, a succession, a full winter, and a run where every letter is read in full.

`make golden-update` regenerates hashes and **prints a diff of which tests changed**, so a deliberate balance change is a reviewable commit and an accidental one is caught.

## 10.2 Property tests

- `apply` is pure: same `(state, action)` gives byte-identical output twice.
- No float ever reaches `canonical_json`.
- `arrears` is monotone under zero allocation.
- `melt_ledger` never decreases.
- Total grain is conserved: `in - consumed - spoiled - out == delta_stock`, exactly, every turn, every scenario. Run this as an invariant assertion in debug builds, on every turn. Conservation bugs in this genre are silent and fatal.
- Every `Rng` domain string used at runtime is in `DOMAINS`.
- `belief/project.py` output is JSON-serializable primitives only.

## 10.3 AI layer tests

- Parser: 200 authored prose lines with expected `Action` output, run against the live model as a **separate, non-blocking** test suite. Report accuracy as a percentage, fail the suite below 85 percent, and keep the failures in a file you read.
- Numeric guard: unit tests with adversarial strings including number words, sexagesimal forms, and numbers inside authored formulae.
- Grader: unit tests over authored good and bad letters. `corpus_lint` in CI.
- Replay-without-model: the full golden suite must pass with `OLLAMA_HOST` pointed at nothing.

## 10.4 Balance harness

`tools/balance.py --scenario ugarit --runs 200 --policy naive|greedy|triage`. Headless, no model, scripted policies. Prints: median turn of first famine, median turn of first raid, distribution of survival length, distribution of continuity score, and how often the melt ledger crosses the replacement cliff before the player could have noticed. Use it to tune tables, not vibes.

---

# PART 11. BUILD ORDER

Do these in order. Each milestone ends in something playable or measurable. **Do not start the AI layer before M4 is reached, and do not start M4 until M1 through M3 are fun.**

- **M0. Skeleton and the contract.** `rng`, `calendar`, `state`, `actions`, `events`, `reduce`, `tick` with empty phases, `hashing`, canonical JSON, save/load/replay, one golden test on an empty 100-turn run. No gameplay. This milestone is the whole project's insurance policy.
- **M1. The core loop, no AI, no letters.** Attention, stores, rations, arrears, dependents, unrest, rites, the LISTS and STORES tabs, command mode only. **Target: a 60-turn famine that is interesting to lose.** If it is not interesting here, stop and fix the tables before adding anything.
- **M2. Letters and latency.** Routes, couriers, transit, the closed sea, the schedule, incoming letters from templates, the STACK tab, the DESK with template-only composition. Target: the spring flood lands and hurts.
- **M3. Belief and distortion.** Claim store, projection, scribe bias, transcription error, `inspect ledger`, freshness glyphs, the ARCHIVE tab. Target: the player cross-checks a number and finds it wrong.
- **M4. Numeric guard and parser.** Guard first, with tests. Then the Ollama client, cache, `ai_log`, the pre-parser, the parser role, clarify handling. Target: prose input works and the game still plays with the model off.
- **M5. Composer and grader.** `formulae.toml`, the grader, the desk panel, `dictate it myself`, `corpus_lint`. Target: a player who learns the formulae beats the scribe.
- **M6. Relations.** Esteem, obligation, gifts, adequacy, gossip propagation, status claims, unanswered-letter decay, oaths and clause audit, liability, the misfortune deck.
- **M7. Voicer.** Persona cards, report bias, distortion of asserted facts, background generation scheduling, fallback templates.
- **M8. Land and metal.** Agriculture, climate series, labour allocation, canals, the bronze chain, the melt ledger, workshops. Target: a run where the army becomes unreplaceable and the player never noticed.
- **M9. House and cult.** Household, reproduction, child mortality, marriage abroad as an agent, queen mother, succession and the oath reset, divination.
- **M10. Plague and the archive puzzle.** SIR, introduction, quarantine, `cause_oath_id`, the predecessor archive corpus, expiation, the librarian role.
- **M11. The interface.** The cell grid and its two backends, the hub, panel windows, the WORLD node map, sparklines and the house tree in colour, the two advisors, and a double-clickable build. Target: a stranger who has never read the spec opens the executable and knows what a fortnight costs him. Part 9 was written at M0 and is still mostly unbuilt; this milestone is Part 9.
- **M12. The city as a machine.** Institutions over the existing dependent groups (6.18), heads who are people and who misreport, the corvée given somewhere to go, building and repair as a long bet (6.21), justice and precedent (6.19), the land due and the harbour due (6.20), placing your own house and naming an heir (6.22). Target: a run lost because the harbourmaster went unpaid for a year and the tin stopped, and the player can point at the fortnight it started.
- **M13. The world, the envoy, and the standing order.** Foreign cities carrying the same institutions the player's own does, seen only as far as he has travelled (6.18); a trade network with prices you can only learn by asking; the envoy as the verb for reaching it; agency for the persons and cities in it; and free-text standing orders delegated to fallible people. Target: a run in which the player's grain arrives late because the man he sent to buy it did what he was told rather than what was meant.
- **M14. Displacement.** Rival courts, displaced groups, reception policy, the coalition, raid targeting. Target: a coalition assembled entirely from refusals, verifiable in the log.
- **M15. Four scenarios.** Pharaoh, Ugarit, Amurru, Pylos, including capability gating and the Pylos tab deletion.
- **M16. Epilogue, scoring, polish.** Stratigraphy screen, continuity report, the unsent letter, balance passes, the 80-column degrade path.

---

# PART 12. ANTI-GOALS

Things that will occur to you or to a contributor, and must not happen.

- **No LLM arithmetic, ever.** Not "estimate the harvest", not "how much grain is that". If you want a character to estimate, the engine computes the estimate and the character reads it out.
- **No LLM-authored world facts.** No generated place names at runtime, no invented characters, no improvised events. Everything nameable is either authored in `content/` or derived from a seeded stream at scenario load.
- **No progress gated on a model response.** Every action must be reachable via command mode. Every generated body must have a template fallback. A player with no GPU plays the same game with plainer prose.
- **No floats in state.** No exceptions for "just this one ratio".
- **No global RNG.** No `random.random()` anywhere in `engine/`. Lint for it.
- **No doom clock, no collapse meter, no notification of decline.** The absence of a letter is the mechanic.
- **No mid-turn revelation of A-phase truth.** The player acts on B3's belief.
- **No unified timeline view** reconciling correspondents' dates. That is the puzzle.
- **No "break oath" button.** Ritual, consent, cost, or nothing.
- **No warning before the melt ledger cliff.** It is a number on a page.
- **No dashboard.** One sparkline widget, used sparingly. A game about information scarcity must not hand the player an analytics suite.
- **No survivable ending presented as a win.** The collapse can be delayed, locally mitigated, and survived by individuals. The kingdom falls. The score is the archive.

---

# PART 13. THE DESIGN PROBLEM, STATED HONESTLY

If the collapse is unavoidable, the player feels cheated. If it is preventable, the game is bad history.

The resolution is that the collapse never arrives as an event and is never given a cause. It arrives as a bad harvest, then a silence from a trade partner, then a garrison that does not answer, and the player must decide which of those is noise. The game's real subject is decision-making under an information regime, and there is no honest version of that where you get to see the map.

Everything in this specification is downstream of that sentence. When a decision is unclear, ask which option produces a more interesting inference problem for a player who cannot see the world, and choose that one.
