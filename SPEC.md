# SAY TO THE KING, MY LORD

## 0.7 alpha product specification

- Status: authoritative
- Revision: 2026-08-02
- Current release: 0.5.2

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

Questions this document had to answer are marked **Decision:**. A decision is
a default that works, not a final word; change it here first, then in code.

---

## 1. The game

**SAY TO THE KING, MY LORD** is an information-constrained rulership
simulation set around 1200 BC, at the end of the Late Bronze Age.

The player is not an omniscient cursor over a map. The player is a ruler at a
court. The distinctive play is holding a social and material system together
through letters, officials, and institutions.

The historical starting situation constrains the run. The historical outcome
does not. The world is on a course to destruction: shocks cascade, routes
fail, and cities empty. The player uses the tools of a king to delay that
failure, survive it, or be buried by it.

**Decision — how long the world lasts.** No script and no doom counter. The
seed sets the timing and severity of shocks; the ordinary rules turn those
shocks into collapse. Balance targets an unaided world that fails somewhere
between year 15 and year 30 across seeds. That is a tuning target checked by
long headless runs, not a rule the engine enforces. A run that survives past
30 years because the player played well is a correct outcome.

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

Every settlement outside the player's seat farms, eats, trades, levies,
suffers, and decides without the player. It does not wait to be observed and
does not act only when addressed. The player's city is one settlement under
the same rules, distinguished only by who gives its orders.

Foreign courts act on their own beliefs and needs. They write first, refuse,
delay, lie, and go silent.

### 2.4 The player sees mostly Belief, not World

World holds the truth. The player sees Belief: dated, sourced, incomplete,
sometimes wrong. Every player-facing number carries the date and origin of the
record it came from, and stale records stay stale until something arrives to
correct them.

No screen may read World directly. A quantity the court has not measured is
shown as an estimate or a range, or not shown.

Every fact the court does know must be reachable in the interface. A fact may
be absent only because the court has no evidence for it; in that case the
relevant dossier says that it is unknown, why, and what report, inspection, or
event could reveal it. Uncertainty limits precision, not access.

### 2.5 Orders act through people and institutions

An order names its subject, its authority, and the person or institution that
will carry it out. Between the order and the outcome sit travel time,
competence, competing duties, cost, and self-interest. Orders can be delayed,
performed badly, performed partly, or refused.

The player never mutates the world from a screen. Every change passes through
a registered action with a stated cost and a stated refusal.

### 2.6 Determinism is structural

Same version, same world data, same seed, same confirmed action log produce
the same run, byte for byte. Randomness is drawn from named streams, never
from wall-clock time or iteration order. Accepted model text is stored, not
regenerated.

### 2.7 The local model supplies language, not truth

The supported lightweight local model is required in normal windowed play. It
voices people, corrects player-written matter, interprets tablets, parses
orders, and summarizes permitted records.

It may not:

- see hidden World state;
- invent an authoritative fact, number, person, promise, or obligation;
- calculate simulation outcomes;
- choose player or non-player policy;
- mutate state;
- be rerun during replay to recover accepted text.

The supported baseline is `qwen3:4b-instruct`.

### 2.8 Religion has human and institutional causality

Gods do not act. Temples, priests, rites, omens, and oaths act, because people
believe and because institutions hold grain, land, labour, and authority.

A rite costs real goods and real days. An omen changes what people expect, and
so what they will do. A broken oath is a political fact other courts can cite.
No hidden divine favour modifier moves harvests or battles.

---

## 3. Alpha 0.7 pillars

### 3.1 A living, inspectable simulation

0.7 includes interacting foundations for:

- named people, households, kinship, office, health, and movement;
- stores, lots, ownership, custody, consumption, and loss;
- land, harvest, workshops, labour, service, corvée, and maintenance;
- institutions, authority, legitimacy, succession, law, and obligation;
- routes, cargo, couriers, merchants, trade, tribute, gifts, and news;
- courts, status, patronage, diplomacy, oath, ritual, and memory;
- disease, disruption, scarcity, local conflict, submission, and political
  transformation;
- observation, claims, reports, letters, archives, and actor Belief.

"Simulate everything" means important causes interact and can be explained. It
does not mean every imagined subsystem, commodity, profession, or named person
must ship in 0.7.

The rule runs the other way: **when a system can be written short and still
work, write it short.** A new entity type needs a rule that consumes it.
Anything without one stays a number on something that already exists.

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

#### 3.2.1 The blocks a letter is made of

**Decision — the block list, from the actual corpus.** Late Bronze Age
Akkadian letters, in the Amarna and Ugarit archives, are built from a small
set of fixed parts in a fixed order: an address ("Say to the king, my lord"),
a message marker (*umma* PN, "message of your servant PN"), a self-abasement
or prostration formula for a superior ("I fall at the feet of my lord seven
times and seven times"), a well-being formula (*lū šulmu*, "may there be
well-being"), then the body, then a closing. The opening parts carry the
relationship; the body carries the business. That is the game's model.

The outgoing tablet is composed of these blocks:

| Block | Required | Carries |
| --- | --- | --- |
| Address | yes | rank and claimed relationship: lord, servant, brother, father, son |
| Message marker | yes | who sends, and by whose authority |
| Prostration or greeting | by rank | deference, equality, or its pointed absence |
| Well-being | no | courtesy; its absence is legible as coldness |
| Recognition | no | what the king admits receiving or hearing |
| Matter | yes | one or two sentences written by the player |
| Terms | when material | structured quantities, goods, people, dates, destinations |
| Precedent | no | a cited oath, kinship, past gift, or earlier tablet |
| Warning | no | a stated consequence of refusal |
| Seal | yes | authority and dispatch form |

Address, marker, and greeting are chosen from the forms the sender's real
standing permits. A vassal who addresses a great king as "brother" is making a
claim, and the recipient reads it as one. Rank is never shown as a score.

#### 3.2.2 What the model does with the matter

**Decision — orders versus tone.** The model reads the player's Matter and
returns two things:

1. **Orders** — a list of structured commitments and requests: send X, promise
   Y by date Z, demand, refuse, offer marriage, swear. These are the only part
   with mechanical force.
2. **Tone** — a confidence reading of the wording, on a small scale from
   hedged through plain to emphatic.

Everything not parsed into an order is prose. It changes how the reader sees
the king; it moves nothing material by itself.

**Decision — how tone is balanced.** One rule, no second score. Each promise
recorded from a letter carries the tone it was made in. Tone sets what the
recipient expects, and the expectation sets what the outcome is worth:

- an emphatic promise raises the recipient's expectation; kept, it gains more
  standing than a hedged one; broken, it costs more;
- a hedged promise moves standing little in either direction;
- emphatic language with nothing delivered is the worst case, and a court that
  has been burnt discounts the next emphatic letter from that sender.

So confidence is a wager on delivery, not a persuasion stat. The player can
see the wager before sealing (§3.2.3). Numbers for it live in
`content/`, not in code, so tuning does not need a release.

#### 3.2.3 Nothing is sealed unseen

Before dispatch the writing table shows a deterministic panel: every order the
model parsed, in plain words, with quantities, dates, and destinations; the
recorded tone; and the prose that will travel unparsed. The player may edit,
remove, or cancel. Sealing without that confirmation is not possible.

If the model is unavailable or its output fails validation, the panel shows
the failure and the letter is not sent. It never guesses on the player's
behalf.

#### 3.2.4 The rest of the path

The player chooses among meaningful letter blocks; there is no abstract
"posture" menu and no exposed protocol score.

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

There are nine primary rooms. Each named view is real and opens typed objects,
not raw dictionaries or aliases for another view:

1. **Hall** — dated standing, passages, audience, arrivals, and matters moving.
2. **Scribes** — Inbox, Filed, Sent, Records, tablet, Desk, review, and dispatch.
3. **Alu** — Overview, Cohorts, Institutions, Sites, Works, and reception.
4. **Trade** — Exchange, Cargo, Routes, Movements, Dues, and letter-backed
   foreign orders.
5. **Storehouse** — Stores, Labour, Land, Reserves, Dues, and exact accounts.
6. **Muster** — formations, detachments, escorts, missions, and the same exact
   parsed order as corvee: who, number, destination, duration, purpose,
   rations, and official.
7. **Court** — People, Offices, Household, Audience, Justice, and Advisers.
8. **Shrine** — Rites, Offerings, Oaths, and Obligations.
9. **World** — Places, Routes, Journeys, Courts, News, Disease, and
   Displacement. It inspects and links; it does not issue another room's order.

#### 3.3.1 The Hall

The Hall is the room the player lands in and the room they end the fortnight
from. Three columns:

- **left** — the believed standing of what matters: grain, copper, tin, each
  with its change since the last fortnight, each dated to the record it came
  from;
- **centre** — the doors, listed vertically, each with its access letter, its
  mark (a plain placeholder is sufficient), and the count of matters flagged
  in that room;
- **right** — what is in motion: envoys and where they are believed to be, and
  orders dispatched but not yet resolved.

Counts are the only alert. A door with nothing behind it shows nothing.

Counsel belongs to named people in Court. Oaths belong to Shrine and linked
tablets. Works belong to Alu and project objects. Sickness belongs to people,
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

### 3.4 Text is scarce and specific

Screen text states a fact, a quantity, a date, or a consequence. No flavour
paragraph where a number belongs, no restating what the layout already shows.
Prose belongs in tablets, where a person wrote it and a scribe read it out.

---

## 4. Shared interaction contract

The same action uses the same key everywhere. Tab and Shift-Tab cycle room
tabs; arrows select; Enter opens or confirms a displayed preview; Space
toggles, except in Hall where it ends the fortnight; Escape cancels
the active mode and otherwise closes; `:` opens Command and `?` opens Help.
Ctrl-H raises Hall, Ctrl-G opens the window switcher, Ctrl-Tab and
Ctrl-Shift-Tab cycle windows, Ctrl-Shift-T tiles, Ctrl-Shift-C cascades, Ctrl-S
saves, Ctrl-O reloads, and Ctrl-+/Ctrl--/Ctrl-0 change type size. Function keys
are not part of the interface.

Every screen works with the keyboard alone. Mouse is an alternative, never the
only path.

Every action states its cost before confirmation and its refusal in plain
words. Destructive or irreversible orders confirm explicitly.

The Hall is an exception docket, not a second copy of every ledger. It answers:
who or what has reached the king, what changed, and where the evidence is.
Rooms show working state.

---

## 5. Technical

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

- Saves are versioned action logs.
- Loading starts the same campaign and reapplies the log in order.
- Confirmed player actions and accepted generated text are persisted.
- Loading does not rerun the language model.
- Incompatible semantic versions fail with a direct explanation.
- UI-only state may be restored separately but cannot affect replay.

### 5.4 Performance and scale

The simulation must complete a 96-fortnight reference run within the pinned
benchmark budget and remain deterministic under reordered iteration and
headless execution.

Scale is justified by decisions and causal interactions, not by a headline
agent count. Content should be large enough that trade, delay, substitution,
disease, labour conflict, and foreign autonomy are real, while small enough to
inspect and balance.

### 5.5 Verification

Release checks stay small: authority, inventory, conservation, compilation,
one save/load smoke, representative headless runs, and the pinned benchmark.
They verify the seams most likely to corrupt a campaign without turning the
test suite into a second implementation.

---

## 6. Release boundary

Only these workstreams may define scope. Ordered.

### 6.1 Retire the legacy court

Done. Stores, ordinary people, labour, land, geography, foreign actor belief,
seed, and date have one kernel authority. Court-facing records are projections,
and one phase runner advances the world. `tools/authority_audit.py` reports no
findings. The completion record is `docs/archive/TASK_2_TODO.md`.

### 6.2 Finish the correspondence vertical slice

- a foreign need or belief causes an incoming tablet;
- the Hall shows the arrival cheaply and immediately;
- the player composes the reply from the blocks in §3.2.1;
- parsed orders and tone are shown deterministically and confirmed (§3.2.3);
- seal, copy, scribe, courier, and route are recorded;
- dispatch, travel, receipt, silence, response, and consequence occur;
- gifts and marriage proposals use the same path;
- accepted text and structured meaning replay exactly.

**Decision — which orders a letter may issue.** The corpus, not invention. A
Late Bronze Age letter demands or promises goods, grain, metal, timber, and
labour; asks for or offers troops and escorts; complains of raiding and asks
for protection; reports enemy movement; arranges marriage and dowry; sends,
requests, and complains about gifts; cites and demands oaths; asks a detained
messenger be released; refers a dispute for judgement; asks for a physician,
a craftsman, or a scribe; announces accession or death; and threatens to go to
a third court. Each of those is one order kind. Nothing outside that list
ships in 0.7.

### 6.3 Complete the world and the rooms

- a playable autonomous regional network;
- grain, labour, trade in more than one good, transport, obligation, disease,
  politics, household, succession, and limited conflict interacting through
  the shared foundations;
- the nine rooms of §3.3 owning their verbs, with no working action lost.

**Decision — obligations, and what 0.7 needs.** Four kinds, all letter-facing
and all with a due date, a debtor, a creditor, and a stated remedy on failure:
deliver goods, supply labour or troops, pay tribute, and keep an oath. That is
enough for tribute, corvée, trade contracts, and diplomacy. No fifth kind
without a rule that reads it.

**Decision — justice and religion in 0.7.** Both stay, both stay small.
Justice is petitions, rulings, and precedent that people remember; it feeds
legitimacy and grievance and nothing else. Religion is §2.8: rites cost goods
and days, omens move expectations, oaths are political facts. Neither grows a
subsystem in 0.7.

### 6.4 Balance the collapse

Collapse is caused by ordinary population and grievance rules. A completed
fall is a terminal state, not a forecast or a timer.

- Whole-Alu unrest is the living-population-weighted grievance of resident
  cohorts, scaled 0..1000. Palace-dependent unrest remains a narrower court
  pressure and cannot by itself destroy the city.
- An active Alu falls when its living population is at or below 400 per
  thousand of its authored opening population, or whole-Alu unrest reaches
  1000. Limited conflict may bring it to the same fallen state.
- Falling records turn, cause, remaining population, unrest, and killed ruling
  elite. The ruler and represented local ruling house die. Autonomous
  decisions and new correspondence stop.
- Historical people, goods, transfers, tablets, and the fall event remain in
  World for reconstruction. The settlement mark, dependent site marks, usable
  routes, trade entries, and available foreign court disappear from Belief.
- If the player's Alu falls, the campaign ends immediately with the cause. No
  further order may mutate World. Other Alus may fall while play continues.

Balance remains knob-turning against long headless runs, once §6.1 to §6.3 are
real. The targets:

- an unshocked world stays mostly stable;
- one shock is usually survivable;
- connected shocks can cascade across settlements;
- across seeds, an unaided world fails between year 15 and year 30;
- every failure is reconstructable from stored events;
- population collapse, maximum unrest, survival, foreign fall, and player game
  over are exercised by the longitudinal probe;
- passive and austerity policies produce meaningfully different material and
  network outcomes; the probe must name what each policy actually does and may
  not present austerity as competent play.

The probe reports every event type, fall turn and cause, population trough,
unrest peak, shock kind, surviving Alu count, player outcome, and impossible
state. It checks that fallen rulers are dead, fallen marks are absent, no
population is negative, and terminal state and cause agree. A `fell_turn` and
cause may be written only after ordinary rules complete the fall; they must
never act as a predictive `collapsed` flag, scripted victim, or countdown.

---

## 7. Anti-goals

- no omniscient map, no fog-free strategy layer;
- no model-authored facts, numbers, or decisions;
- no scripted collapse, doom timer, or chosen victim;
- no abstract relationship, posture, or protocol score shown to the player;
- no entity type without a rule that consumes it;
- no research tree, technology bar, or iron victory in 0.7;
- no tactical battle layer;
- no second full-screen dashboard replacing the rooms.
