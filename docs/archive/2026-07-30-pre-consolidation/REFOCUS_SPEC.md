# SAY TO THE KING, MY LORD — ARCHIVED REFOCUS SPECIFICATION

## Refocus specification: a living Bronze Age court

> Archived on 2026-07-30. Repository-root `SPEC.md` supersedes this document.

- Status: archived on 2026-07-30
- Revision: 2026-07-29, corrected after product-direction review
- Scope: player fantasy, correspondence, simulation, rooms/windows, text, and
  UI/UX
- Relationship to `SPEC.md`: this document does not replace the current
  authority until accepted. It refocuses the existing game without removing
  the features that make it distinct.

---

## 1. The correction

This project should not become a generic settlement dashboard with Bronze Age
names.

Its identity is:

- a court that rules through people rather than omniscient controls;
- letters and tablets as delayed, political, material communication;
- a palace made from different rooms, desks, ledgers, doors, and documents;
- real operating-system windows that let the player arrange evidence;
- a character-grid visual language with clay, bronze, lapis, seals, figures,
  buildings, and maps;
- historically specific obligations, status, religion, kinship, and ceremony;
- a required lightweight local language model that gives scribes, advisers,
  translations, and tablets their living voice;
- a deep deterministic world underneath all of it.

Those are not bloat. They are the game.

The bloat is repetition, filler, duplicate implementation paths, inert
mechanics, excessive instructions, unreadable density, decorative space that
does not change, and a new bespoke interface for every small action.

The refocus is therefore:

> **Keep the strange, specific Bronze Age court. Make every room useful, every
> letter consequential, and every visible detail arise from the simulated
> world.**

The game may learn from deep simulation games, correspondence games, old
information software, and physical tabletop spaces. It should not resemble
any one of them closely enough to lose its own shape.

---

## 2. North-star game

The player rules a Late Bronze Age polity from a physical court.

Households, fields, institutions, workshops, temples, merchants, ships,
caravans, armies, foreign courts, and displaced people continue to act in the
same material world. Goods have owners and locations. People have duties,
interests, knowledge, kin, health, memory, and limited authority. News moves
with people. Orders travel, are interpreted, and may be delayed, exploited,
refused, or obeyed too literally.

The player does not click directly on a distant city to change it. The player
learns through witnesses and tablets, compares claims with ledgers and other
people, writes or dictates an answer, appoints someone, assigns resources,
and waits for the world to answer.

The central fantasy is:

> **Hold together a complex material system by reading people, writing exact
> words, arranging scarce capacity, and deciding whom to trust.**

The correspondence layer and the management layer are one game:

- a shortage creates a report;
- the report contains a claim and often a request;
- the player checks the relevant store, person, route, or obligation;
- the reply creates an order, refusal, promise, negotiation, or relationship
  memory;
- that communication travels physically;
- people act on what they understood;
- material consequences later return as new evidence.

---

## 3. What is wrong now

### 3.1 The strong foundation

Keep:

- deterministic simulation and replay;
- keyed randomness and integer state;
- World/Belief separation;
- goods lots, ownership, custody, and transfer records;
- exclusive labour;
- seasonal agriculture and production;
- institutions, staffing, upkeep, condition, and projects;
- physical routes, journeys, trade, disease, and news;
- autonomous settlements and actors;
- households, officeholders, obligations, religion, dynasty, justice, and
  diplomacy as interacting parts of the world;
- the Hall, Court, City, Tablet House, Desk, World map, and stateful art;
- real windows and the ability to keep evidence side by side;
- compact keyboard/mouse character-grid interaction.

### 3.2 The actual excess

At the time of this audit, after consolidating the Claude worktrees:

- the action inventory contains 32 player action types;
- actions are spread across 19 interface contexts;
- the desktop registry contains more than twenty window/entity-window kinds;
- an unattended run produces 58 active tablets after 24 fortnights, 146 after
  48, and 335 after 96;
- several screens are 90–108 cells wide but still truncate important text;
- Inbox, Counsel, Archive, Works, and several ledgers often contain large
  empty areas or instructions instead of meaningful state;
- the merged build passes 633 tests, but those tests do not prove that the
  game is readable or that its decisions are fun.

The number of rooms is not itself the problem. The problem is that too many
rooms are oversized reports, too many repeat the same furniture, and too many
actions have their own private control path.

### 3.3 Text failures

- Incoming tablets repeat unchanged requests on a fixed cadence.
- Outgoing replies are padded with generic lines to satisfy a protocol score.
- Summaries, adviser comments, full letters, and footers often restate the
  same fact.
- Interface instructions occupy the world-facing play area.
- Disabled or incomplete actions advertise zero-value commands.
- Long prose conceals the one sentence that changes the player's decision.
- Modern software explanation and Bronze Age speech are mixed together.

### 3.4 UI/UX failures

- Several windows are replacement screens with OS chrome, not convincing
  objects or places that coexist usefully.
- The Palace repeats almost the same large scene for Court, House, and
  Relations.
- The current Court art is mostly static; it does not sufficiently reflect
  who is present, who is absent, what is broken, or what the player selected.
- The Inbox dedicates most of a large reader to announcing that the tablet is
  unread.
- The Desk makes a short refusal into a long generic document.
- Counsel resembles a mostly empty chat client rather than a person in court.
- The Archive shows few results beside decorative shelves and large blank
  space.
- Store, Roll, Land, Muster, and Oath controls expose irrelevant or invalid
  actions for the current selection.
- Repeated borders, title bars, hints, and `Esc close` lines consume cells
  without establishing hierarchy.
- Multi-window play lacks a strong spatial logic: windows open, but the player
  does not always understand which ones belong together.

---

## 4. Design laws

### Law 1 — The simulated world writes the story

Letters, petitions, trade offers, warnings, vows, disputes, migration, and
political demands originate in world state and actor decisions. A cadence may
produce a real routine account. It may not invent activity to keep the pile
busy.

### Law 2 — Simulation depth is preserved

The world may simulate far more than the player sees at once. Simplifying a
screen does not authorize simplifying away ownership, people, labour,
logistics, knowledge, institutional capacity, history, or actor agency.

### Law 3 — Distinct presentation, shared foundations

The Storehouse should not look like the Shrine. The Court should not operate
like the World map. Their identity matters.

Underneath, they share selection, scrolling, action validation, feedback,
provenance, order creation, and save/replay. A distinctive room does not need
a private engine or a private input language.

### Law 4 — Communication is action

A consequential letter is not flavour pasted on an order. Its address,
status claim, terms, omissions, attached goods, messenger, seal, and timing
are part of what the recipient receives and acts upon.

The interface must preserve the player's exact material meaning while allowing
social meaning, deliberate ambiguity, formula, rhetoric, and human
interpretation to matter.

### Law 5 — Court time represents court work

Attention remains a core resource. It is not charged for wrestling with the
interface.

Free:

- moving and arranging windows;
- selecting, scrolling, filtering, and comparing;
- reading material already known to the ruler;
- examining a previously opened tablet;
- inspecting summaries, histories, and current orders;
- correcting an unconfirmed input.

Costs court time:

- having a new or difficult tablet read, translated, collated, or verified;
- holding an audience or hearing;
- commissioning a physical inspection;
- dictating, revising, sealing, and dispatching consequential writing;
- issuing a complex order through an official;
- consulting specialists;
- personally supervising work.

The cost follows an in-world act and is previewed before commitment.

### Law 6 — Text is scarce and specific

Primary text must identify state, report evidence, express a person's intent,
present a choice, or record a consequence.

Repetition is not atmosphere. Generic filler is not historical voice.

### Law 7 — Skeuomorphism must carry state

A room, tablet, shelf, seal, map, jar, figure, wall, or tool is useful when it
shows identity, capacity, condition, presence, ownership, progress, or
selection.

Decoration may establish place, but it contracts before information and does
not repeat unchanged across several rooms.

### Law 8 — The game remains culturally specific

Do not rename every historical relationship into generic strategy-game terms.
Oaths, household, corvée, audience, seal, offering, brotherhood, vassalage,
temple service, and tablet practice remain where they express real differences.

They should interact through common systems rather than become isolated
minigames.

---

## 5. Primary loop

Each fortnight:

1. the Hall changes to show who and what has reached the court;
2. the player opens relevant rooms and keeps evidence side by side;
3. the player reads, compares, questions, hears, writes, allocates, appoints,
   promises, refuses, delegates, or deliberately waits;
4. confirmed letters and orders enter real institutions, hands, and routes;
5. the world advances simultaneously;
6. people act from their knowledge, authority, needs, and interests;
7. consequences return locally or through delayed reports.

The loop is not “clear every notification.” Some matters should be ignored.
The challenge is deciding which silence, claim, obligation, shortage, or
person deserves the court's time.

---

## 6. Correspondence is a core game

### 6.1 What makes a letter fun

A good letter creates several simultaneous decisions:

- Do I believe the sender?
- What do they actually want?
- What status do they claim between us?
- What am I willing to promise?
- What must I avoid promising?
- Should I answer directly, delay, threaten, reassure, counteroffer, delegate,
  send a gift, send an envoy, or remain silent?
- Which scribe, language, seal, and courier should carry it?
- What will the recipient probably understand from these exact words?

The fun is not typing padding or guessing a hidden correct formula.

### 6.2 Incoming tablets

An incoming tablet is a physical document with:

- sender and claimed standing;
- seal or lack of seal;
- language/script and reader required;
- sent date, received date, and known route;
- one primary matter;
- explicit claims, requests, offers, threats, promises, or acknowledgements;
- attached or referenced obligations, people, goods, places, and previous
  tablets;
- possible damage, interception, copying, omission, or translation history.

The Inbox row is compact:

```text
seal · sender · matter · request/deadline · age
```

The selected tablet shows enough physical and social context to decide whether
to spend court time opening, translating, checking, or answering it.

### 6.3 The writing surface

The Desk is not a generic text editor and not a multiple-choice dialogue box.
It is a structured clay-tablet workbench.

A letter can contain:

1. **Address** — lord, servant, brother, father, son, king, official, household.
2. **Recognition** — what was received or what relationship is acknowledged.
3. **Matter** — the claim, report, request, answer, order, or offer.
4. **Terms** — quantity, quality, place, deadline, price, condition, authority.
5. **Posture** — reassure, defer, refuse, rebuke, warn, bargain, submit,
   insist, remain deliberately cool.
6. **Witness/seal** — scribe, witnesses, gods invoked, seal, messenger.

Not every letter needs every part. Most should be three to six compact lines.

The player may:

- assemble clauses through direct controls;
- edit the resulting text;
- dictate free text and resolve it into exact clauses;
- remove a formula deliberately;
- preserve ambiguity deliberately;
- attach a gift, order, copy, credential, or named envoy;
- choose courier and route where alternatives exist;
- keep a draft unsealed.

The structured clauses are authoritative for material intent. The rendered
words, protocol, omissions, and tone are authoritative for what the recipient
socially interprets.

### 6.4 No protocol score

Replace the visible `1000/1000` grader with a scribe's reading of likely
interpretation:

```text
Yabninu expects:
  Talmi-Teshub will read this as a refusal.
  You still acknowledge the summons.
  No date or alternative force is promised.
  Calling him “brother” disputes the rank he claims.
```

This is advice from a person, not a perfect validation oracle. The interface
still guarantees that quantities, targets, and deadlines in the confirmed
structured meaning are not misparsed.

Protocol knowledge comes from:

- prior correspondence;
- scribes and envoys;
- archive examples;
- the recipient's known reactions;
- status and oath records.

A player can knowingly break formula or make an insult. Accidental software
misinterpretation is still a defect.

### 6.5 Scribes are people, and lightweight AI is required

Different scribes may know different scripts, formulae, courts, precedents,
and people. They can:

- translate;
- propose a compact formula;
- warn about status or precedent;
- collate conflicting copies;
- draft in their own voice;
- carry biases and interests;
- become overworked, absent, ill, loyal, or compromised.

Their abilities create institutional dependence. They should not generate
long unsolicited speeches.

The shipped game requires a lightweight local language model. It is the normal
way scribes phrase drafts, advisers interpret likely reception, tablets receive
character voice, and summaries are compressed. It is not an optional
“embellish” button and the deterministic fallback is not the reference
experience.

The model receives only structured facts and Belief available to the speaking
character. It may:

- choose concise historically grounded phrasing;
- preserve a persona and social posture;
- explain how a scribe thinks a recipient will read the wording;
- summarize a tablet or thread without erasing uncertainty;
- propose clause wording that the player can accept or revise;
- voice advisers, envoys, priests, petitioners, and correspondents.

It may not:

- invent a person, quantity, place, event, obligation, or delivery;
- silently add or remove a promise;
- decide whether an order succeeds;
- choose NPC policy from hidden World state;
- mutate simulation state directly.

The structured clause preview remains the authority for material meaning. The
model is mandatory because language, interpretation, and human presence are
part of the game—not because arithmetic or causality are delegated to it.

### 6.6 Delivery and consequence

A sealed tablet chooses or inherits:

- courier;
- route;
- provisions/status cost;
- copies;
- destination person or office;
- expected but uncertain arrival.

The tablet may wait, be copied, be intercepted, arrive after its deadline, or
reach a successor. The recipient responds from their own Belief and interests.

Conversation history is therefore not a chat transcript. It is a physical
sequence of dated tablets, silences, couriers, receipts, and consequences.

### 6.7 Compact Bronze Age copy

Ordinary letters are concise, formulaic, and pointed.

Rules:

- one primary matter;
- the status formula establishes relationship quickly;
- the actionable sentence comes early;
- repetitions occur only for rhetorical force or escalation;
- no generic lines about the scribe faithfully recording the message unless
  authenticity is actually disputed;
- target roughly 25–90 words for an ordinary tablet;
- longer royal or legal documents exist, but are exceptional and scroll.

Example:

```text
TO AMMURAPI, THE KING OF UGARIT:
Thus Talmi-Teshub, servant of the Sun.

Send 200 household troops to Carchemish within two fortnights.
Let them come armed. The Sun will not ask twice.
```

A compact answer:

```text
TO TALMI-TESHUB:
Thus Ammurapi, king of Ugarit.

I have heard the summons. I will not send 200 men.
Sixty watchmen can depart when the sea opens. Send word if this is accepted.
```

The final letterform—compact angular Latin, spacing, seal marks, clay surface,
and cuneiform-influenced punctuation—receives its own visual/copy pass. It
must remain highly readable and should not pretend that Latin text is literal
Ugaritic cuneiform.

### 6.8 Required lightweight-model contract

- Ship against a small quantized local model suitable for ordinary consumer
  hardware; roughly 1.5B–4B parameters is the target class.
- First-run setup verifies or installs the supported model rather than asking
  whether AI should be enabled.
- The model is loaded once and shared by correspondence and court roles.
- Each request is narrow, schema-grounded, short-context, and short-output.
- A visible scribe/adviser owns every request; there is no anonymous “AI.”
- Generation begins from structured facts, clauses, persona, relationship,
  and permitted Belief.
- Numeric and named-entity guards reject invented material terms.
- Accepted text is stored with the tablet so reopening it never regenerates
  different words.
- Simulation replay uses the stored structured meaning. Text does not need to
  be regenerated during replay.
- Timeouts and malformed output use an emergency compact formulary so the
  session is recoverable, but a build that routinely falls back fails the
  product requirement.
- The target is immediate acknowledgement and a short visible composing state,
  not a long chat-style wait.

---

## 7. The palace desktop

### 7.1 Core rule

Keep real operating-system windows.

The player should be able to place:

- a letter beside the store it describes;
- a treaty beside the reply being written;
- a person beside the office being filled;
- a route beside a shipment and a foreign court;
- two conflicting tablets beside each other.

That physical comparison is part of the game.

The desktop should feel like opening doors and laying objects on a working
table, not like launching unrelated applications.

### 7.2 Window classes

There are three useful kinds:

1. **Rooms** — persistent places with their own furniture and activity.
2. **Objects** — tablets, ledgers, maps, dossiers, oaths, cases, and orders
   that can remain open beside a room.
3. **Moment sheets** — compact previews, receipts, and turn summaries attached
   to the room that caused them.

Rooms are single-instance. Objects may have multiple instances by identity.
Moment sheets do not become permanent windows unless pinned.

### 7.3 The eight rooms

The Hall and seven primary doors preserve a palace without turning every
subsystem or step in a workflow into a separate top-level window.

#### 1. The Hall — anchor and passage

Purpose:

- date, court time, season, and critical local state;
- people and couriers physically waiting;
- new or changed matters;
- active orders that require the ruler;
- visible doors to every room;
- end the fortnight.

The Hall is not a dashboard of every number. It is the place where matters
arrive and where the player chooses which door to open.

Its art changes with attendance, unrest, ruler condition, season, visiting
envoys, guards, and urgent physical events.

#### 2. The Court — people, audience, office, and judgement

The current Palace/Court becomes a live audience room rather than one repeated
backdrop above three unrelated tabs.

It contains:

- people actually present;
- audience and petition queue;
- advisers who can be selected and questioned;
- officeholders and vacancies;
- household members at court;
- foreign envoys physically present;
- hearings, judgements, appointment, dismissal, and succession acts.

Court modes such as Audience, Household, Offices, and Envoys rearrange people
and furniture within the same room. They do not redraw the identical palace
scene.

The selected figure in the art is the selected person in the record below.
Absence is visible. Vacant positions leave a visible empty station.

Justice belongs here as an audience process, not as an isolated report window.
Relations appear through envoys and people here, while the wider relationship
history lives with World and correspondence.

#### 3. The Scribes' Room — correspondence, records, and dispatch

It contains:

- unread and active tablets;
- filed tablets and predecessor archive;
- conversation sequences;
- copies, seals, provenance, and search;
- the current order/document rack;
- a writing table with the source tablet pinned beside the wet reply;
- likely-interpretation notes, direct dictation, seal, and dispatch.

The shelves encode quantity, age, section, and selection without consuming
half the screen. Search and filters are software-clear. Retrieving or having a
difficult text collated may cost court time; filtering known indexes does not.

The Scribes' Room opens tablet objects only when the player deliberately pins
one for comparison. Reading, filing, searching, answering, and dispatching are
stations in this one room, not a chain of overlapping windows. The writing
table remains one of the visual and interaction centrepieces of the game.

#### 4. The Storehouse — stock, land, rations, and obligations

This replaces several disconnected read-only ledgers without turning them
into a generic spreadsheet.

It has connected stations:

- jars/bins and current stores;
- incoming and outgoing lots;
- reserves and seed;
- ration/service roll;
- estate and harvest accounts;
- dues, tribute, and committed quantities;
- melt and tool/equipment records.

Selecting grain changes the visible account, vessels, obligations, flows, and
available actions together. A bronze selection must never show “open seed for
food.”

Exact ledgers can open as object windows beside the Storehouse.

#### 5. The City — institutions, assets, and works

Keep the City skyline and make it more stateful.

Buildings show:

- condition;
- staffing and leadership;
- missing inputs;
- activity;
- congestion;
- repair or construction;
- fire, abandonment, or expansion.

Selecting a building connects art, record, dependencies, workers, inputs,
outputs, and legal actions. Works is a City mode and project object, not
another mostly empty top-level room.

Institutions at Ma'hadu or other settlements open their own place/institution
objects from World.

#### 6. The Muster Yard — formations, watches, escorts, and service

Keep Muster distinct because the physical allocation of armed people is both
strategic and culturally visible.

It contains:

- formations and actual people;
- commanders;
- equipment condition;
- current duty and location;
- summons and oath/service commitments;
- escorts for couriers, caravans, and envoys;
- conflict with harvest, watch, and construction labour.

It uses the same assignment system as other labour while preserving military
identity and obligations.

#### 7. The Known World — places, routes, foreign courts, and journeys

Keep the authored character map.

It shows only what the court believes:

- places and last-known condition;
- routes and seasonal state;
- couriers, envoys, ships, caravans, and formations;
- trade offers and obligations;
- foreign relationships and known officeholders;
- disease, conflict, or displacement reports as optional layers.

Selecting a place, route, actor, or journey must select that actual kind and
offer relevant actions. The player's own seat must not accidentally receive a
foreign-route command.

World opens maps, place dossiers, route records, and conversation histories as
objects.

#### 8. The Shrine — rites, oaths, offerings, and interpretation

Religion remains because it shapes expenditure, legitimacy, policy, faction,
and what people believe.

The Shrine contains:

- ritual calendar and temple capacity;
- vows and oaths relevant to the gods;
- offerings and available goods;
- divination questions and dated readings;
- priests, factions, reputation, and precedent;
- political consequences of compliance, neglect, suppression, or defiance.

Divination is not a “pick offering to buy forecast accuracy” minigame. It is a
consultation with a person and institution whose reading can affect policy and
politics without reading hidden future truth.

Oaths may also open as legal tablet objects and connect to Court, Tablet House,
World, and Storehouse.

### 7.4 Supporting object windows

Keep a small common family:

- Tablet;
- Person/household;
- Institution/site;
- Place/route/journey;
- Ledger/lot/obligation;
- Order/mission;
- Petition/oath.

Each object has a distinctive header and relevant body, but shares provenance,
history, links, selection, and action feedback.

Do not make Files, Settings, Help, a window switcher, and every filter into
large themed rooms. They are compact utilities.

### 7.5 Window behaviour

- Opening a door raises its existing room.
- Opening an object places it near its source without fully covering it.
- Each room remembers useful geometry and selection.
- Two to four windows should coexist meaningfully at the default scale.
- Tiling and switching helpers exist but remain quiet utilities.
- Closing a room does not lose drafts, filters, or selection.
- The Hall owns the session.
- No initial window fills almost the entire display unless the player chose
  that layout.

Multi-window remains core. Window-management chores do not.

---

## 8. Visual direction

### 8.1 Not a generic retro desktop

The character grid and 1990s information density remain useful techniques,
but “software from 1993” is no longer the entire visual north star.

The stronger north star is:

> **A Bronze Age palace translated into a precise character-cell instrument.**

OS chrome remains outside. Inside, rooms use clay, limestone, timber, bronze,
lapis, textile, lamplight, seals, shelving, vessels, figures, walls, and
routes.

### 8.2 Partial skeuomorphism

Use physical metaphors for:

- identity and place;
- spatial relationships;
- quantity and capacity;
- selection;
- wear, vacancy, congestion, and progress;
- documents and provenance.

Use plain software controls for:

- search;
- scrolling;
- save/load;
- settings;
- accessibility;
- exact numeric entry;
- sorting and filtering.

Do not disguise a search field as a riddle or make a player drag a virtual
tablet across the screen to file it.

### 8.3 Room-specific stateful art

- Hall: bodies waiting, doors, guards, couriers, ruler's station.
- Court: named figures, empty offices, envoys, petitioners, household.
- Tablet House: shelves, tablet stacks, seals, broken/copied tablets.
- Desk: clay field, stylus, seal, attached docket, courier token.
- Storehouse: vessels, bins, reserved seals, incoming/outgoing space.
- City: buildings, scaffolds, damage, smoke, vacancy, activity.
- Muster: ranks, empty places, equipment, banners, animals.
- World: routes, moving parties, stale/uncertain marks.
- Shrine: altar, offerings, attending priest, ritual state.

Art contracts before controls and should usually occupy no more than one third
of a management room. A strongly stateful moment may temporarily use more.

### 8.4 Typography

The final type system should include:

- a compact, angular, Bronze Age-influenced display face for titles, seals,
  dates, and short labels;
- a narrow, highly readable face for tables and controls;
- a readable tablet hand for letter bodies, distinct without becoming a fake
  cuneiform novelty font;
- clear numerals and unit marks;
- full scaling and pure-ASCII fallbacks.

Typography is a dedicated next-stage prototype. Do not select the final font
from prose alone; test Hall, Tablet, Desk, Storehouse, and World together.

---

## 9. Shared interaction grammar

Distinct rooms use one reliable rhythm:

```text
see a physical state or list
-> select a person/object/place
-> inspect evidence and relationships
-> choose a culturally specific action
-> set exact terms
-> preview court time, goods, people, authority, and wording
-> confirm
-> receive a local result and persistent record
```

Common rules:

- single click selects;
- double-click or Enter opens the object;
- actions appear beside the selected thing;
- invalid zero-value actions are hidden until a value is meaningful;
- strategically important disabled actions remain with a short reason;
- every refusal appears in the initiating room;
- scrolling never changes the meaning of number keys;
- instructions appear only during input or in Help;
- screen text never truncates the distinguishing part of a name or an
  important quantity while decorative space remains.

Typed commands remain an optional power-user route. They should sound natural
to the setting, but direct controls remain complete.

---

## 10. Simulation scope

The final game still aims to simulate:

- households, cohorts, named people, age, kinship, health, and movement;
- land, water, harvests, animals, goods, tools, and ownership;
- work, service, corvée, offices, institutions, and maintenance;
- ships, caravans, routes, trade, tax, tribute, gifts, credit, and debt;
- letters, speech, reports, archives, translation, seals, and belief;
- courts, status, patronage, oath, law, ritual, legitimacy, and succession;
- disease, displacement, conflict, coalition, submission, transformation, and
  political collapse.

“Simulate everything” is an end goal for interacting causes, not a requirement
to expose everything equally in the first release slice.

### System organization

All of that grows from seven shared foundations:

1. people and households;
2. goods, ownership, and consumption;
3. labour, assets, and production;
4. routes, journeys, and physical exchange;
5. institutions, office, and authority;
6. obligations, relationships, and memory;
7. observation, belief, communication, and archive.

Religion, justice, dynasty, diplomacy, trade, war, and disease retain their
historical identity while using these foundations.

---

## 11. Disposition of current features

| Current feature | Decision | Refocused form |
|---|---|---|
| Deterministic kernel and causal ledgers | Keep | Foundation |
| Autonomous actor/world simulation | Keep | Foundation |
| World/Belief separation | Keep | Reports and actor decisions |
| Attention/court time | Keep, refine | In-world court work only |
| Letters and correspondence | Keep and deepen | Core loop |
| Formulae, status, seals, scribes | Keep and deepen | Scribes' Room |
| Protocol grader | Replace | Scribe's likely interpretation |
| Free-form letter writing | Keep | Clause-backed dictation/editing |
| Lightweight local AI | Keep and require | Normal tablet, scribe, adviser, and interpretation layer |
| Real OS windows | Keep | Palace desktop |
| Hall | Keep and make stateful | Anchor/passages |
| Palace/Court/House | Recompose | Live Court room |
| Relations | Redistribute | Court envoys + World + tablets |
| Inbox, Archive, and Desk | Merge spatially | Scribes' Room stations |
| Stores, Roll, Land | Connect | Storehouse stations/objects |
| City and Works | Connect | City room + project objects |
| Muster | Keep | Muster Yard |
| World | Keep and deepen | Map/journeys/foreign state |
| Altar, rites, oaths, divination | Keep, rework | Shrine and linked tablets |
| Justice | Keep, rework | Court audience process |
| House, appointments, succession | Keep | Court people/offices |
| Disease and quarantine | Keep | World layer + people/routes |
| Counsel | Keep as people, not chat shell | Select advisers in Court |
| Help | Keep deterministic | Compact utility |
| Routine repeated letters | Remove | State-driven escalation |
| Padded formulary filler | Remove | Compact exact letters |
| Unattributed “Do:” advice | Remove | Named person and evidence |
| Invalid zero-value controls | Remove | Contextual input |
| Large repeated static scenes | Replace | Room-specific changing art |
| Window tiling/switcher as prominent mechanics | De-emphasize | Quiet utilities |
| Duplicate legacy/new simulation paths | Remove after migration | One world grammar |

This refocus removes defects and duplication, not the courtly systems.

---

## 12. Report and text budgets

### Routine information

- ordinary event: one line;
- routine institutional report: three to six compact rows;
- ordinary letter: roughly 25–90 words;
- adviser warning: one or two sentences with named evidence;
- action result: one line plus a link to its record;
- long legal, diplomatic, ritual, or archival documents: exceptional and
  scrollable.

### Repetition

- An institution produces at most one routine bundle per fortnight.
- The same warning does not become new unless severity, deadline, evidence,
  cause, or responsible person changes.
- A correspondent repeats a demand only as an intentional escalation.
- The active Inbox is bounded by bundling and resolution, not by silently
  deleting history.
- A normal 96-fortnight run must remain triageable.

### Voice separation

- Room controls: terse and clear.
- Reports: compact administrative language.
- Letters: Bronze Age formula and personality.
- Advisers: named human voice.
- Help: plain software explanation.
- Archive: original document text.

Do not make every layer speak like the same narrator.

---

## 13. First refocused playable slice

The first slice proves both the deep simulation and the distinctive court.

It contains:

- Ugarit, Ma'hadu, one inland supplier, and one foreign port;
- the current grain, labour, institution, trade, and route kernel;
- a small named court with at least two differently capable scribes;
- Hall, Court, Scribes' Room, Storehouse, City, Muster, World, and Shrine
  in their refocused forms;
- compact state-driven reports;
- the required lightweight local model with grounded scribe, adviser, summary,
  and tablet-voice roles;
- incoming tablets caused by shortage, obligation, offer, delay, or request;
- outgoing tablets with clauses, status, terms, seal, and courier;
- delivery delay and recipient response;
- one important oath;
- one court hearing;
- one ritual/divination decision with political but not supernatural physics;
- one drought sequence and one route disruption.

The player must be able to:

- receive a request and understand why it exists;
- compare its claims with a store, route, person, or older tablet;
- write a short answer whose exact promise is visible;
- choose socially meaningful formula and posture;
- dispatch it through a real route;
- allocate labour or goods consistently with the answer;
- see the recipient and world react later;
- explain a failure through both material and communicative causes.

---

## 14. Complexity gates

### Simulation gates

- Every important quantity change is causal and conserved.
- Foreign actors continue without player contact.
- Letters originate in actor belief, need, obligation, or strategy.
- The same underlying event can produce different reports and responses.
- A confirmed letter's material meaning is replayable.
- Social interpretation can differ by recipient without changing the confirmed
  quantity, target, or deadline.

### Correspondence gates

- An ordinary letter can be drafted in under one minute.
- The player can deliberately make a promise, refusal, counteroffer, insult,
  ambiguity, or status claim.
- No correct protocol score is exposed.
- No generic filler is required for mechanical success.
- A letter can be understood without reading a paragraph of software help.
- Conversation history shows travel, silence, receipt, and consequence.
- The normal Desk, tablet voice, and adviser-interpretation paths use the
  supported lightweight model.
- Generated text introduces no unconfirmed number, entity, promise, or fact.

### Window gates

- Hall plus any two relevant room/object windows coexist at default scale.
- Every primary door has a unique purpose and changing visual state.
- No room repeats a large unchanged scene from another room.
- A common task never requires opening an unrelated room.
- Every room can raise a linked object without losing selection.
- Window management never costs court time.

### UI gates

- The Hall answers “who or what has reached me?”
- The selected room answers “what is happening here?”
- One linked object or inspector answers “why do I believe it?”
- A relevant action is visible beside its subject.
- Invalid actions do not masquerade as active zero-value commands.
- Decorative art contracts before evidence, terms, and controls.

### Growth gates

A new player-facing mechanic must:

- strengthen the Bronze Age court fantasy;
- emerge from or affect at least two shared simulation foundations;
- create a recurring decision rather than a one-time curiosity;
- have a natural home in an existing room or object type;
- generate useful correspondence, material consequence, or both;
- avoid adding another primary door unless the palace genuinely lacks a place
  for it.

---

## 15. Implementation order

### Step 1 — Stop the flood

- Remove fixed-cadence repeated crisis tablets.
- Bundle routine accounts.
- Replace outgoing filler with compact formulae.
- Keep all correspondence history, but bound the active pile.

### Step 2 — Rebuild the correspondence loop

- Define letter clauses and their exact structured meaning.
- Replace the numeric protocol score with likely-interpretation notes.
- Add seal, scribe, courier, route, copy, and attachment choices.
- Preserve direct editing and dictation.
- Make grounded lightweight-model phrasing and interpretation the normal path.
- Test dispatch, delay, receipt, response, accepted-text storage, and replay.
- Test emergency fallback separately; it is recovery, not the reference mode.

### Step 3 — Give the windows a palace logic

- Establish the eight rooms and three window classes.
- Recompose Court first so people, vacancy, presence, and selection change its
  scene.
- Recompose reading, archive, and writing as stations in the Scribes' Room.
- Connect Storehouse stations and City/Works.
- Keep Muster, World, and Shrine distinct.

### Step 4 — Remove UI defects

- Eliminate irrelevant zero-value actions.
- Put validation and results in the initiating window.
- Remove repeated interior titles and instructions.
- Fix truncation before adding more art.
- Ensure two-to-four-window coexistence and persistent selection.

### Step 5 — Join correspondence to the kernel

- Generate requests, offers, accounts, and warnings from actual world state.
- Make promises and orders reserve or pursue real people, goods, and capacity.
- Make news and tablets travel with routes.
- Delete the remaining duplicate court economy after kernel migration.

### Step 6 — Prototype Bronze Age type and material

- Produce Hall, Court, Tablet, Desk, Storehouse, and World mockups together.
- Test compact angular lettering at several scales.
- Tune clay/bronze/lapis palettes, seal marks, borders, and object silhouettes.
- Preserve accessibility, exact numbers, and pure-ASCII fallback.

---

## 16. Definition of the refocused game

The refocus succeeds when:

- the game could not be mistaken for a generic management simulator;
- the palace feels like a set of connected places and working objects;
- opening several windows supports comparison and rulership;
- letters are brief enough to enjoy and deep enough to matter;
- the player can express exact material terms and meaningful social posture;
- scribes, seals, couriers, routes, status, silence, and delay create play;
- the Court visibly changes with its people and problems;
- religion, oath, household, justice, and diplomacy remain culturally
  specific while interacting with the material simulation;
- the world is deeper than any one room;
- atmosphere comes from state, language, and consequence rather than filler;
- complexity produces stories instead of interface chores.
- the lightweight model is always present as the human language of the court
  while the simulation remains materially authoritative.

The final test for a proposed simplification is:

> **Does it remove friction while preserving the court, the letters, the
> rooms, and the culture?**

If it removes the identity along with the friction, it is the wrong
simplification.
