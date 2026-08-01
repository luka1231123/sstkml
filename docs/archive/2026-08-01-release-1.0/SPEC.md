# SAY TO THE KING, MY LORD

## Release 1.0 product specification

- Status: **Done and dusted.** Superseded on 2026-08-01 by the root `SPEC.md`
  (Alpha 0.7). Kept for provenance. Adds no requirement.
- Former status: authoritative
- Revision: 2026-07-30
- Scope: the first complete release

This is the only current design specification. Code and tests describe
implementation detail; archived documents describe how the design evolved.
Neither may quietly expand the release beyond this document.

The full pre-consolidation specifications are preserved under
[`docs/archive/2026-07-30-pre-consolidation`](docs/archive/2026-07-30-pre-consolidation/README.md).
Ideas intentionally postponed until after 1.0 are listed under
[`docs/archive/post-1.0`](docs/archive/post-1.0/README.md).

Older source comments sometimes cite numbered sections of the archived
specifications. Those are historical implementation citations, not additional
requirements. New work should cite this specification by named contract rather
than revive the old milestone numbering.

---

## 1. The game

**SAY TO THE KING, MY LORD** is an information-constrained rulership
simulation set around Ugarit in the Late Bronze Age.

The player is not an omniscient cursor over a map. The player is a ruler at a
court. People, households, institutions, goods, labour, obligations, journeys,
disease, and foreign courts continue to act whether or not the player opens a
window. Knowledge reaches the court through dated, delayed, interested reports.

The aim is the causal richness of a deep simulation game without copying the
shape or identity of another game. The distinctive play is holding a social and
material system together through people, tablets, rooms, seals, routes, and
fallible interpretation.

The historical starting situation constrains the run. The historical outcome
does not. Ugarit may survive, submit, transform, fragment, or be destroyed
because of simulated causes and player choices, never because a script demands
the familiar ending.

### The fortnight

Each turn:

1. The world resolves production, consumption, labour, movement, obligations,
   disease, and actor decisions.
2. Actors observe only what they can encounter or learn.
3. Reports, tablets, visitors, accounts, and exceptions travel to court.
4. The Hall shows what has reached the king and what now demands attention.
5. The player reads, compares, writes, judges, allocates, delegates, or waits.
6. Confirmed orders enter institutions, missions, and routes.
7. Consequences continue everywhere, including places the player ignored.

The game does not reward clearing every notification. Attention is limited
court work, and deliberate inaction is a valid decision.

---

## 2. Non-negotiable laws

### 2.1 The simulated world causes the story

Letters, shortages, petitions, offers, prices, illness, conflict, and political
demands originate in persistent state and actor decisions. Routine cadences may
bundle accounts; they may not fabricate crises to keep the interface busy.

### 2.2 Material flows are accounted for

Consequential goods, labour, people, assets, and obligations have sources,
owners or authorities, locations, transfers, uses, and losses. The same grain
or person-days cannot be spent twice.

For conserved goods:

```text
opening + produced + imported + recovered
  = closing + consumed + exported + spoiled + destroyed
```

### 2.3 The outside world is autonomous

Included settlements and organizations persist without player contact. They
produce, consume, plan, trade, refuse, substitute, store, move, and react from
their own circumstances. Removing Ugarit from a headless simulation must not
freeze the rest of the network.

### 2.4 The player sees Belief, never World

`World` is authoritative state. Every actor has dated, sourced, possibly
conflicting beliefs. The player interface and language layer receive only the
court's projected Belief.

Unknown, stale, disputed, and interested testimony remain visible as such. A
clean interface may summarize a claim; it may not turn it into truth.

### 2.5 Orders act through people and institutions

Anything at distance or requiring judgement has authority, an executor, an
execution site, delay, and a report path. Interface parsing is exact; human
execution may be late, partial, self-interested, or incompetent.

### 2.6 Determinism is structural

The same version, content, seed, and confirmed action log produce the same
world. Randomness is content-addressed and named. Replay never depends on
iteration order, wall-clock time, network timing, or fresh model output.

### 2.7 The local model supplies language, not truth

The supported lightweight local model is required in normal windowed play. It
voices people, corrects player-written matter, interprets tablets, and
summarizes permitted records.

It may not:

- see hidden World state;
- invent an authoritative fact, number, person, promise, or obligation;
- calculate simulation outcomes;
- choose player or non-player policy;
- mutate state;
- be rerun during replay to recover accepted text.

The engine keeps facts and outcomes authoritative. Accepted model language is
validated and stored. Recovery text exists for service failure, not as a
separate full-featured AI-off mode.

The supported baseline is `qwen3:4b-instruct`.

### 2.8 Religion has human and institutional causality

Gods are real to the people, not hidden switches in the physics:

- disease spreads materially;
- weather and harvest arise from material systems;
- rites and offerings consume resources and affect legitimacy, factions,
  morale, obligations, and decisions;
- divination is a fallible human interpretation, not access to a secret future.

The game does not settle the player's theology.

### 2.9 History constrains mechanisms, not outcomes

Attested, reconstructed, and fictional content must not be presented as the
same kind of claim. Historical uncertainty is kept where it matters. Modern
market, bureaucratic, nationalist, and supernatural assumptions are not
silently projected backward.

### 2.10 There is one current path

There is one world grammar, one Belief boundary, one order pipeline, one
current room layout, and one release specification. Compatibility adapters are
temporary and tested. Replaced implementations belong in Git, not beside the
live path.

---

## 3. Release 1.0 pillars

### 3.1 A living, inspectable simulation

Release 1.0 includes interacting foundations for:

- named people, households, kinship, office, health, and movement;
- stores, lots, ownership, custody, consumption, and loss;
- land, harvest, workshops, labour, service, corvée, and maintenance;
- institutions, authority, legitimacy, succession, law, and obligation;
- routes, cargo, couriers, merchants, trade, tribute, gifts, and news;
- courts, status, patronage, diplomacy, oath, ritual, and memory;
- disease, disruption, scarcity, local conflict, submission, and political
  transformation;
- observation, claims, reports, letters, archives, and actor Belief.

“Simulate everything” means important causes interact and can be explained. It
does not mean every imagined subsystem, commodity, profession, or named person
must ship in 1.0.

Every strategic failure must be traceable through records: what was absent,
where it should have come from, what competed for it, who knew, who decided,
and what followed.

### 3.2 Correspondence is a principal game system

Letters are not event prose wrapped around menu choices. They are how distance,
status, ambiguity, commitment, and delay become playable.

Incoming tablets show:

- sender and known standing;
- date and route when known;
- concise matter and exact claims;
- original wording;
- related people, places, obligations, and older tablets;
- seal, copy, damage, translation, or provenance where relevant.

The writing table places the source tablet beside the wet reply. The outgoing
tablet has four visible pieces:

1. **Address** — rank and relationship.
2. **Recognition** — what the king acknowledges receiving or hearing.
3. **Matter** — one or two sentences written by the player.
4. **Seal** — the authority and dispatch form.

The player chooses among meaningful letter blocks; there is no abstract
“posture” menu and no exposed protocol score.

Yabninu may correct the player's matter while preserving its meaning, numbers,
names, conditions, uncertainty, negation, and commitments. The original words
remain recoverable. The model does not choose the king's position.

Material terms must be explicit structured attachments or clauses: quantities,
goods, people, destinations, deadlines, gifts, marriage proposals, oaths, and
other commitments are confirmed separately from decorative prose.

Sealing creates a stored document and dispatch record. Couriers and routes take
time. Silence, interception, receipt, copying, escalation, and later response
are state, not flavor text.

Marriage, gifts, foreign requests, counteroffers, and diplomatic warnings use
this correspondence path. Screens must not bypass it with unrelated instant
buttons.

Routine letters are compact. Repetition occurs only when something has changed
or a correspondent intentionally escalates.

### 3.3 The Palace Desktop is multi-window

Real, independently movable windows are a core feature. The player should be
able to keep a tablet beside a store account, route, person, or older record.
Consolidation means fewer duplicated rooms and clearer ownership, not replacing
the palace with one full-screen dashboard.

There are eight primary rooms:

1. **Hall** — matters, arrivals, audience, and passage.
2. **Court** — people, offices, household, audience, justice, and advisers.
3. **Scribes' Room** — Inbox, Filed, Sent, Records, reading, writing, and
   dispatch.
4. **Storehouse** — stores, labour roll, land, reserves, dues, and exact
   accounts.
5. **City** — institutions, sites, assets, damage, repair, and works.
6. **Muster Yard** — formations, commanders, equipment, watches, escorts, and
   service.
7. **Known World** — places, routes, journeys, foreign courts, trade, news, and
   disease layers.
8. **Shrine** — rites, offerings, oaths, divination, priests, and precedent.

Counsel belongs to named people in Court. Oaths belong to Shrine and linked
tablets. Works belongs to City and project objects. Sickness belongs to people,
routes, places, and a World layer. These may open focused object windows; they
do not require additional primary doors.

Supporting object windows use a small shared family:

- tablet or archive record;
- person or household;
- institution, site, or project;
- place, route, or journey;
- ledger, lot, obligation, oath, order, or mission.

Opening a door raises its existing room. Rooms remember useful geometry,
selection, drafts, and filters. Window management never costs court time.

### 3.4 A distinct Bronze Age visual identity

The interface is a precise character-cell instrument shaped like a working
palace, not a generic retro desktop and not a literal archaeological diorama.

Use:

- clay, limestone, timber, bronze, lapis, textile, lamplight, seals, shelves,
  vessels, figures, walls, and routes;
- cuneiform-inspired impressions, tablet edges, docket marks, seal fields, and
  compact angular ornament;
- room-specific stateful art that changes with vacancy, quantity, wear,
  congestion, damage, progress, presence, and movement;
- skeuomorphism where it communicates place, state, capacity, provenance, or
  relationship.

Use plain software controls for search, scrolling, save/load, settings,
accessibility, exact entry, sorting, and filtering.

Art contracts before evidence or controls. Decorative texture never runs
through important text.

The 1.0 type system requires:

- a compact angular display hand for headings, seals, dates, and labels;
- a narrow readable control and ledger face;
- a distinct but readable tablet hand;
- clear numerals and unit marks;
- scalable and pure-ASCII fallbacks.

It should feel inspired by Bronze Age writing without pretending modern
Unicode cuneiform is a readable body font.

### 3.5 Text is scarce and specific

Default budgets:

- ordinary event or action result: one line;
- adviser warning: one or two sentences, attributed;
- routine institutional report: three to six compact rows;
- ordinary letter: roughly 25–90 words;
- long legal, diplomatic, ritual, and archival documents: exceptional and
  scrollable.

The same warning does not return as new unless evidence, severity, deadline,
cause, or responsible person changes. The active Inbox is bounded by bundling
and resolution, never by deleting history.

Room controls speak plainly. Reports are administrative. Letters are formulaic
and personal. Advisers sound like named people. Help explains software without
role-play padding.

---

## 4. Shared interaction contract

Every room follows the same dependable rhythm:

```text
see state
-> select a person, object, place, or document
-> inspect evidence and relationships
-> choose a relevant action
-> set exact terms
-> preview costs, authority, and wording
-> confirm
-> receive a local result and persistent record
```

Required behavior:

- click selects; Enter or double-click opens;
- arrows move through the visible collection or focused pane;
- the printed key and actual key always agree;
- number keys can act only on rows currently visible;
- important disabled actions remain visible with a short reason;
- impossible or irrelevant actions are absent rather than active at zero;
- evidence appears before irreversible judgement;
- every refusal and success appears in the room that initiated it;
- important names, quantities, costs, and claims never truncate while
  decorative space remains;
- compact and minimum layouts retain every enabled action;
- mouse and keyboard have equivalent routes;
- closing a room never discards an unsealed draft without an explicit discard.

The Hall is an exception docket, not a second copy of every ledger. It answers:
who or what has reached the king, what changed, and where the evidence lives.

Rooms show working state. Object windows show detailed evidence and history.
Orders record what was asked, who should carry it out, what it costs, and what
happened.

---

## 5. Technical contract

### 5.1 Boundaries

- `engine/` owns authoritative simulation and actions.
- `belief/` is the only World-to-player projection boundary.
- `tui/` composes screens only from Belief, session UI state, and explicit
  permitted records.
- `ai/` receives flat, approved prompt data and returns non-authoritative
  language.
- `content/` owns authored scenario data, formulae, names, and prose.

The developer's causal inspector may read World. It is never player-facing.

### 5.2 State and resolution

- Strategic state uses integers and explicit units.
- A fortnight resolves in named phases.
- Exclusive labour, cargo, authority, and other scarce resources are allocated
  globally rather than first-come by iteration order.
- Ownership and custody are distinct.
- Goods transformations and transfers leave records.
- Obligations use closed, inspectable clause kinds.
- Actor policies read `(actor, belief)`, never raw World.

### 5.3 Saves and replay

- Saves are versioned, atomic, and replay-verified.
- Confirmed player actions and accepted generated text are persisted.
- Loading does not rerun the language model.
- Incompatible semantic versions fail with a direct explanation.
- UI-only state may be restored separately but cannot affect replay.

### 5.4 Performance and scale

The 1.0 simulation must complete a 96-fortnight reference run within the pinned
benchmark budget and remain deterministic under reordered iteration and
headless execution.

Scale is justified by decisions and causal interactions, not by a headline
agent count. Release content should be large enough that trade, delay,
substitution, disease, labour conflict, and foreign autonomy are real, while
small enough to inspect and balance.

### 5.5 Verification

The release remains covered by:

- unit and integration tests;
- deterministic replay and hash tests;
- conservation and labour-exclusivity audits;
- causal scenario tests;
- corpus and prompt-boundary lint;
- minimum/default/resized screen tests;
- mouse and keyboard action-path tests;
- required-model availability, guard, timeout, and stored-output tests;
- headless foreign-world and player-deletion tests;
- long balance sweeps and the pinned benchmark.

No release gate is satisfied by prose alone.

---

## 6. Path to 1.0

Only these workstreams may define pre-1.0 scope.

### 6.1 Finish the correspondence vertical slice

- foreign need or belief causes an incoming tablet;
- the player reads and cross-checks it;
- Address, Recognition, Matter, and Seal compose the reply;
- exact material terms and attachments are confirmed;
- Yabninu corrects only the player-written matter;
- seal, copy, scribe, courier, and route are recorded;
- dispatch, travel, receipt, silence, response, and consequence occur;
- gifts and marriage proposals use the same path;
- accepted text and structured meaning replay exactly.

### 6.2 Unify court and world state

- complete the legacy-court-to-kernel migration;
- remove duplicate sources of truth;
- make Ugarit use the same goods, labour, movement, obligation, and Belief
  grammar as foreign settlements;
- persist the unified entities and records in the current save version.

### 6.3 Complete the eight-room consolidation

- move advisers into Court;
- move oaths into Shrine;
- move Works into City;
- move sickness controls and evidence into people, routes, places, and World;
- keep focused object windows and multi-window comparison;
- remove obsolete primary doors only after their complete action paths have a
  visible replacement.

### 6.4 Complete release-critical UI work

- explicit person selection for delegation, marriage, succession, and office;
- only valid actions for the selected subject;
- responsive Counsel, World layers, Court, Land, and remaining object dossiers;
- exact quantities and units at minimum sizes;
- cuneiform/tablet decoration that is recognizable but never noisy;
- the compact angular release type system;
- final footer, naming, focus, and accessibility consistency.

### 6.5 Complete the release simulation

- a playable autonomous regional network;
- grain, labour, trade, transport, obligation, disease, politics, household,
  succession, justice, religion, and limited conflict interacting through the
  shared foundations;
- explainable survival, submission, transformation, and collapse outcomes;
- enough authored content for a full Ugarit campaign without fixed-cadence
  filler;
- balance families in which apparently sensible choices can fail and difficult
  choices can preserve some form of continuity.

### 6.6 Ship

- complete save migration and release packaging;
- pass all verification gates;
- perform keyboard, mouse, scaling, multi-window, setup, and accessibility
  usability reviews;
- provide a campaign epilogue generated from stored outcomes and archives, not
  a predetermined ending.

Work not required by these six workstreams is post-1.0 unless it fixes a
release-blocking defect.

---

## 7. Anti-goals

Release 1.0 will not:

- copy another game's interface, species, terminology, or progression;
- add mechanics merely because they are historically imaginable;
- expose an omniscient map, adviser, confidence score, or protocol score;
- use generated prose as authoritative simulation state;
- make the small model optional while silently degrading the intended product;
- turn every record or filter into a top-level window;
- replace culturally specific rooms with a generic dashboard;
- replace multi-window comparison with a single full-screen shell;
- add another primary room when an existing room or object naturally owns the
  mechanic;
- preserve duplicate legacy and replacement systems indefinitely;
- fill letters, reports, or chronicles with atmospheric padding;
- make objective supernatural causality;
- guarantee Ugarit's destruction or survival;
- chase a huge population count before the smaller world is causal, playable,
  and explainable.

---

## 8. Definition of 1.0

The game is ready when:

- the world continues and changes without waiting for the player;
- important material and political outcomes are conserved and explainable;
- the court knows only what its Belief permits;
- a complete correspondence chain can cause and resolve material action;
- letters are brief, expressive, socially meaningful, and materially exact;
- the required local model gives the court language without deciding truth;
- the eight rooms have distinct purposes and changing visual state;
- several windows support comparison without becoming window-management work;
- every enabled action has visible subject, evidence, terms, cost, and result;
- the Bronze Age identity is unmistakable without sacrificing readability;
- religion, justice, household, diplomacy, trade, and disease remain culturally
  specific and materially connected;
- a full campaign remains triageable rather than drowning in repeated text;
- saves replay, audits balance, and all release verification passes;
- outcomes emerge from the run and produce an honest archive and epilogue.

The final test for simplification is:

> Does it remove friction while preserving the court, the letters, the rooms,
> the culture, and the interacting simulation?

If it removes the game's identity along with the friction, it is the wrong
simplification.
