# SAY TO THE KING, MY LORD

## Alpha 0.7 — world model and task list

- Status: live, and **subordinate to the root `SPEC.md`**. It may sequence
  work and describe the world model in detail. It may not add scope. Where the
  two disagree, `SPEC.md` wins.
- Revision: 2026-08-01
- Scope: Alpha 0.7 and the agreed direction toward 1.0
- Post-0.7, post-1.0, and DLC ideas remain pinned separately (§11).

This document begins with the game that exists today. It is deliberately
honest about the difference between working simulation, authored content,
representational UI, partial systems, and absent systems.

It then states the foundation for Alpha 0.7: this is not the Ugarit
campaign. It is one shared autonomous world in which the player may begin as
the king of any major **Alu**. The world already contains everything needed to
start a campaign; there are no separate campaign packages in 0.7.

Sections 1 to 7 describe the build. Section 8 is the world model; section 10 is
the task list. Section 12 holds the decisions taken and the questions still
marked **[OPEN]**.

---

## 1. The intended game

The player rules a city through its court, households, institutions, records,
messengers, officials, workers, soldiers, dependants, neighbours, and gods as
understood by its people.

The player does not control the world directly. Orders pass through people and
institutions. Knowledge arrives late, incomplete, disputed, damaged, or
self-interested. The world continues outside the player's sight.

A campaign begins by choosing an Alu with an authored court profile and a
deterministic random seed. All 55 Alu remain in the same simulation; an Alu
without authored court content is not playable yet.

For Alpha 0.7 every playable city uses the same king-and-court systems. The
chosen Alu still changes the campaign through:

- geography, routes, neighbours, and access to resources;
- production, labour, trade, tribute, and strategic dependencies;
- local population, cohorts, court, institutions, and military capacity;
- available evidence, correspondence, and relationships;
- opening dangers, opportunities, and plausible forms of survival or collapse.

Greek, Egyptian, Levantine, Anatolian, and other governmental or cultural
variations would be interesting, but they are not an Alpha 0.7 requirement.
They are pinned for examination after 0.7. In 0.7, every king and city uses the
same underlying rules and UI.

The campaign begins at the start of the end of the Bronze Age system. Depending
on the seed, the player has roughly one, two, or three years of runway before
the regional crisis becomes acute. The immediate purpose of play is survival:
last as long as possible while the world around the city displaces people,
breaks routes, loses production, and transfers pressure to the surviving Alu.

---

## 2. What exists in the world today

The current repository contains two overlapping versions of the world.

### 2.1 The legacy court world

The larger and more playable implementation has one privileged player court.
It contains:

- a ruler, household, heirs, kin, officeholders, and dependants;
- stores, estates, fields, workshops, institutions, formations, and projects;
- settlements, courts, sites, terrain, routes, seasons, and correspondents;
- letters, couriers, inboxes, copies, archives, claims, promises, and marriage
  proposals;
- foreign courts, relationships, status, gifts, oaths, and partial beliefs;
- petitions, precedents, rites, omens, revenue, harbour activity, and plague;
- scheduled events, authored opening conditions, and deterministic random
  outcomes.

This is the source of most current rooms, actions, campaign material, and
visible detail. Its data and assumptions are strongly shaped around Ugarit.

### 2.2 The general simulation kernel

The newer kernel represents the world without making the player's city a
special type. Its generic entities include:

- regions and polities;
- settlements and sites;
- routes and journeys;
- cohorts and organizations;
- lots of goods, owners, custody, and transfers;
- labour, obligations, reservations, contracts, and claims;
- actor observations, beliefs, intentions, and decisions.

The kernel now carries the whole authored map, not a test corner of it. One
registry holds 8 regions, 55 polities, 55 rulers, 55 settlements, 240 sites,
99 routes, 171 cohorts, and 75 organizations. 54 settlements run autonomously;
the fifty-fifth is the player's seat.

### 2.3 One shared authority

Places, routes, sites, land, harvest, stores, ordinary people, foreign actor
belief, date, and seed now have one authority in the kernel. Court-facing
records are projections. `tools/authority_audit.py` reports no duplicate or
missing authority, and the court systems join the kernel's ordered turn.

### 2.4 The intended scale of the existing map

The current world map has the right overall selection and scale for Alpha 0.7.
It should be treated as a network of roughly 30 **Alu** corresponding to major
cities and regional centres. `Alu` is the product term; current code still uses
`Place`, `Settlement`, and the `hub` field on decorative sites.

Only Alu are full settlement-level entities. An Alu contains or controls:

- its king, court, Seat, institutions, stores, and named officials;
- population cohorts whose sum is the authoritative population;
- its historically associated hinterland;
- its Exchange, harbour when coastal, and productive capacity;
- dependent palace centres;
- the local ends or maintained portions of roads and sea routes;
- military formations, obligations, production, and local knowledge.

The roughly 400 smaller historical settlements in the represented region are
not simulated individually. They are abstracted into the population,
production, cohorts, and capacities of their owning Alu. Named minor
places may appear in reports or map detail, but they do not run a second,
hidden settlement simulation.

Every authored palace, grain, metal, timber, horse, and luxury symbol now
carries one classification — Alu, dependent palace centre, or capacity — and
one owning Alu. `docs/ALU_CLASSIFICATION.md` records the verdicts. No
decorative mark runs a settlement simulation. Roads and sea legs connect Alu;
their maintenance, safety, and access may belong to the Alu along the route.

The world model should follow the way the world map already describes the
region rather than replacing it with a different geography.

---

## 3. What is simulated today

“Simulated” here means state persists and changes because rules resolve it. It
does not mean every current system is deep, balanced, or already connected to
the general kernel.

### 3.1 Material and economic life

The current game resolves:

- grain stocks, rations, consumption, shortage, and spoilage;
- land allocation, sowing, harvest, climate effects, and seed use;
- labour assignment, corvée, transport capacity, and competing demands;
- workshops, metals, production, and some material requirements;
- institutional upkeep, maintenance, construction, and repair;
- harbour cargo, merchants, dues, and revenue;
- ownership and transfer of lots in the kernel;
- farming, consumption, market bargains, contracts, and voyages in the
  kernel's autonomous settlements.

The legacy economy is broader. The kernel economy is more general and
accountable. They are not fully unified.

### 3.2 People, household, and government

The current game resolves:

- aging, health, conception, birth, mortality, heirs, and succession;
- appointments and dismissals;
- household needs and some unrest;
- institutions losing condition or effectiveness without support;
- petitions, rulings, precedents, and aging justice cases;
- oaths, rites, divination, expiation, and legitimacy effects;
- player orders that cost time and pass through defined action contexts.

Named life is concentrated around the player's court. The wider population is
mostly represented as groups and quantities.

For the intended model, cohorts are the population. An Alu's true population is
derived by summing its cohorts; it is not stored as a second mutable total. The
player may see only an estimate or range, depending on the quality and age of
the court's records.

Most people are simulated in aggregate **cohorts** rather than as individuals.
A cohort combines people with a shared home, current location, ethnicity,
livelihood, status, material conditions, duties, and institutional ties.
Cohorts supply labour and levies, consume goods, suffer disease and
displacement, and may support, resist, bargain with, or abandon institutions.
Named individuals are reserved for rulers, court members, officials,
specialists, messengers, and other people whose personal identity matters.

### 3.3 Movement, information, and diplomacy

The current game resolves:

- route-based travel time;
- courier dispatch, letter transit, delay, arrival, and interception;
- unanswered correspondence and relationship decay;
- gifts, requests, promises, claims, marriage proposals, and obligations;
- foreign court observations, needs, decisions, and replies;
- partial, dated, sourced, and sometimes wrong beliefs;
- archive filing and later search.

The complete causal chain from an autonomous foreign need, through a letter
and player reply, to material execution is only partly unified.

### 3.4 Disease, security, and military force

The current game resolves:

- plague introduction, spread, mortality, quarantine, and closures;
- troop formations, assignments, readiness-related state, and summons;
- disruption and some political or social pressure.

It does not resolve tactical battles or a full operational war between
autonomous powers.

### 3.5 Time and autonomy

The game advances in fortnights. On advance it processes scheduled events,
production, consumption, travel, correspondence, disease, household change,
institutions, construction, unrest, justice, oaths, foreign observations, and
new reports.

The kernel also lets non-player settlements farm, consume, plan, trade, move
goods, and settle obligations without player contact. This autonomy is real
but currently narrow.

---

## 4. What is authored or representational, not fully simulated

The following may react visually or feed rules, but they are primarily written
content or map representation:

- the terrain grid, coastlines, place coordinates, glyphs, ranks, and map
  labels;
- the route network and travel legs;
- most named cities, courts, officials, correspondents, opening relationships,
  and opening stocks;
- unnamed farm, resource, palace, and hinterland markers;
- letter formulae, archive texts, justice cases, rites, gods, offices, and
  institutional descriptions;
- opening crises and scheduled correspondence cadences;
- many construction, land, household, revenue, and gift-value tables.

Terrain is currently scenery. Mountains, coast, and other terrain cells do not
themselves change travel, agriculture, visibility, or military outcomes.
Routes determine travel.

Several map layers combine live state with authored symbols:

- **Roads** shows real route legs, availability, and known freshness.
- **Trade** shows sea lanes and authored trade/resource sites, not a complete
  live trade-flow model.
- **Farms** shows sown ground and authored estates, not every active farm and
  harvest flow.
- **Holds** shows authored palace or control markers, not dynamic borders or
  territorial possession.
- **Courts** shows correspondents and relationship information.
- **Plague** shows known quarantines and closures, not omniscient epidemic
  truth.

The local language model is presentation, not simulation authority. It may
voice, correct, or summarize permitted information. The engine owns facts,
decisions, quantities, and outcomes.

---

## 5. What is not simulated yet

The current game does not yet provide:

- starting a campaign as any Alu directly from shared world data;
- an Alu model that encapsulates its Seat, dependent palace centres,
  hinterland, cohorts, Exchange, harbour, roads, production, and institutions;
- authoritative cohort populations with appropriately uncertain player-facing
  estimates;
- procedural world, terrain, polity, or city generation;
- one authoritative simulation shared by the player city and every foreign
  settlement;
- a complete regional economy for all important goods and settlements;
- dynamic borders, territorial conquest, coalitions, or full political
  transformation;
- tactical combat or a complete operational war system;
- working envoy missions;
- terrain-driven movement, farming, visibility, or warfare;
- dynamic creation, destruction, ownership, and loss of sites on the map;
- a complete map view of journeys, news, obligations, armies, and material
  flows;
- the complete survival, displacement, attack, and defeat loop;
- the Bronze-to-Iron endgame pinned for 1.0.

A fully named population, procedural geography, campaign packages, cultural
government variants, and full warfare are not Alpha 0.7 requirements merely
because they appear in this gap list.

---

## 6. What is in the UI today

The current desktop is a real multi-window interface. Windows retain geometry
and can be compared side by side. Keyboard and mouse interaction, focus,
minimum sizing, a window switcher, a command palette, notices, and refusals are
implemented and covered by headless tests.

### 6.1 Main rooms and workbenches

| Window | Working content and actions | Current limitation |
| --- | --- | --- |
| Hall | Opens the main rooms and shows the court's entry point | Still reflects the current Ugarit-shaped room organization |
| Scribes' Room | Inbox, outbox, records, tablets, archive search, reading, filing, delegation, replying, and dispatch | Correspondence causality is not fully unified with the kernel |
| Writing Table | Address, Recognition, player-written Matter, Seal, corrections, terms, and dispatch | Depends on a local model for intended presentation; structured consequences remain incomplete in places |
| Storehouse | Stores, rolling accounts, land, allocations, priorities, dues, and seed decisions | Uses much of the legacy court economy |
| Muster | Formations, assignments, summons, and military records | No full war or battle resolution |
| Oaths | Oaths and their records or consequences | Intended room consolidation is unfinished |
| World | Pan, zoom, place selection, route inspection, map layers, courts, plague closures, and starting letters | Gifts and marriage use letters; envoy is visibly disabled |
| Counsel | Conversation with an adviser using permitted context | Local-model dependent with fallback; adviser is not an autonomous source of truth |
| Altar | Rites, divination, omen response, and expiation | Uses current culturally specific content |
| City | Institutions, works, construction, repair, and civic condition | Not yet a generic city-government framework |
| Palace | Court, household, relationships, offices, succession, and justice | Strongly tied to the single privileged player court |
| Sickness | Disease evidence and quarantine controls | Separate room remains; world/person/route integration is incomplete |
| Orders | Available orders, subjects, costs, and execution entry points | Some actions still belong to legacy systems |
| Help | Searchable controls and contextual help | Content follows the current room layout |

Focused windows also exist for individual letters, archive records,
institutions, and the fortnight chronicle.

### 6.2 World map controls that work

The world map currently supports:

- arrow-key panning with edge clamping;
- zooming;
- cycling and clicking places;
- clicking and inspecting routes;
- local or all-road lists;
- Land, Roads, Trade, Farms, Holds, Courts, and Plague layers;
- opening correspondence with a known court.

The map is a knowledge and navigation surface, not an omniscient command map.
Direct remote action is intentionally limited. Envoys are not wired.

### 6.3 Registered player actions

The action registry currently exposes 33 player actions across 19 contexts.
Twenty-one consume court time. The working verbs include:

- advance the fortnight;
- allocate goods and set priorities;
- consume seed in an emergency;
- read, file, delegate, answer, and dispatch letters;
- inspect ledgers and search the archive;
- send or recall harvest labour;
- assign troops;
- raise corvée and dredge a canal;
- consult a diviner, suppress or defy an omen, swear an oath, quarantine, and
  expiate;
- hear and rule on petitions;
- set land and harbour dues;
- appoint or dismiss a person and name an heir;
- begin construction or repair, or abandon a work.

Direct instant gift and foreign-marriage buttons are intentionally unavailable.
Those commitments are meant to travel through correspondence.

### 6.4 Current reliability

At the time of writing the repository's automated suite collects 817
tests. This is strong evidence that the implemented actions, state
transitions, rendering paths, and keyboard contracts work as tested. It is not
evidence that the game is complete, balanced, understandable, or enjoyable.

---

## 7. Where Ugarit is still hard-coded

The repository currently has one legacy campaign file:
`content/scenarios/ugarit.toml`.

It no longer authors the map: places, sites, and routes now live in
`content/kernel/`. Ugarit-specific assumptions still appear in:

- the singular privileged `World.court`;
- player, ruler, settlement, officeholder, institution, god, rite, and archive
  identifiers;
- correspondence personas and letter corpora;
- climate, land, house, works, revenue, justice, and gift content;
- the kernel's small authored world;
- tests that encode the present campaign.

Some mechanics are reusable, and much of the map code is generic. The current
content architecture is not yet sufficient to select any mapped Alu and derive
its campaign directly from the shared world.

---

## 8. Proposed Alpha 0.7 contract

### 8.1 One authoritative world

There is one world model for every Alu. Choosing an Alu gives the player
authority over its king and government; it does not give that Alu different
physics.

The current duplicate court and kernel authorities are transitional code, not
the intended architecture. Population, goods, land, routes, obligations,
beliefs, and date must each have one authoritative representation.

### 8.2 Alu, kings, and ownership

An **Alu** is a major city or regional centre together with its historically
associated hinterland. The existing map supplies the world; Alpha 0.7 does not
generate a new geography or load a separate campaign package.

Every Alu has a king. The king owns or holds the Alu through the shared
political model. There is no abstract relationship score between a king and
his own Alu.

Rule can still fail through concrete state:

- cohorts become hungry, discontented, uncooperative, or displaced;
- officials and institutions fail to execute orders;
- obligations go unpaid;
- succession fails or a rival takes the kingship;
- the Seat is abandoned or captured.

Relations between different realms are primarily relations and obligations
between their kings. Alu also have material connections through roads, trade,
migration, disease, tribute, and conflict.

### 8.3 Minimum contents of an Alu

An Alu contains only the distinctions needed by rules:

- **Seat** — the principal walled palace centre, including court,
  administration, central stores, and royal authority;
- **dependent palace centres** — subordinate centres controlled by the Alu,
  without separate kings or autonomous settlement simulation;
- **cohorts** — the entire ordinary population;
- **hinterland** — food, raw materials, and labour-producing capacity;
- **walls** — defence of the Seat;
- **Exchange** — merchant, storage, and commercial capacity treated together;
- **harbour** — only for a coastal Alu;
- **temple** — religious capacity and rites treated institutionally;
- **troops**;
- **road and sea access**.

Farms, villages, workshops, merchant houses, warehouses, and minor buildings
are not separate objects unless a rule genuinely requires an individually
located asset. Their effects normally belong to the Alu's capacities.

### 8.4 Cohorts are the population

Population is not a second mutable record. The true population of an Alu is
the sum of the people in its cohorts. The king sees an estimate derived from
dated records and reports.

Every person belongs to exactly one ordinary-population cohort. At minimum a
cohort records:

- people and households;
- home Alu and current location;
- ethnicity;
- livelihood;
- legal or institutional status;
- available labour;
- ration requirement, nutrition, and health;
- obligations;
- cooperation or grievance;
- whether it is displaced;
- capacity for organized violence.

Soldiers are assignments drawn from cohorts, not a second population.
Displacement is a condition, not a permanent occupation or ethnicity.
Ethnicity may affect language, social connections, reception, and migration
preferences; it does not mechanically determine loyalty or hostility.

Cohorts split only when some members receive a materially different location,
duty, treatment, or condition. Compatible cohorts merge when those differences
end. Both operations conserve people and households.

### 8.5 Corvée

The king may levy all or part of a cohort for corvée. The order names:

- the source cohort;
- the number of people or share of available labour;
- the task and destination;
- the duration;
- the ration source;
- the responsible official.

The engine creates a temporary detachment. Its people remain counted once and
cannot simultaneously perform their ordinary work, serve in a formation, and
perform corvée. Corvée consumes rations, causes fatigue or losses where
appropriate, and may increase grievance. Released workers merge back when
compatible.

There is no general manual “split cohort” action. Corvée, levy, migration, and
other concrete assignments perform the necessary split.

### 8.6 Roads, trade routes, and caravans

These are three different facts:

- a **road or sea leg** is a physical connection with time, season, capacity,
  condition, risk, and control;
- a **trade route** is a repeated commercial pattern across one or more legs;
- a **caravan or voyage** is a particular moving party with people, transport,
  provisions, cargo, owner, destination, and current location.

Not every road is a trade route. Roads also carry couriers, troops, corvée,
tribute, and displaced cohorts.

Trade routes strengthen through repeated successful journeys and weaken when
merchants reroute or stop travelling. Goods movement must distinguish trade,
tribute, taxation, gifts, requisition, military supply, and relief even when
they use the same transport system.

Merchants act autonomously. The king may authorize or finance trade, request
imports, offer exports, set dues, grant exemptions, requisition goods, provide
escorts, repair routes, close access, and negotiate through correspondence.
The king does not direct every caravan.

### 8.7 Initiating shocks

Alpha 0.7 needs a small, coded set of shocks:

1. long drought;
2. local crop failure;
3. earthquake;
4. destructive sea season;
5. epidemic;
6. route violence and raiding;
7. political rupture or succession crisis;
8. rare volcanic disruption.

A shock changes ordinary world variables. It may reduce fertility or yield,
damage stores, walls, harbours, and roads, kill people, close capacity, raise
risk, interrupt obligations, or remove government. It may not set a `collapse`
flag or choose an Alu to destroy.

Collapse must emerge over years through feedback: shortage weakens people and
institutions; weak institutions lose routes and revenue; failed routes stop
trade and reports; failed Alu displace cohorts and transfer pressure to their
neighbours.

### 8.8 Survival

The seed provides roughly one, two, or three years before regional pressures
become acute. It determines shocks and initial variation, not a hidden
countdown or predetermined sequence of fallen Alu.

The player's Alpha 0.7 objective is to keep the chosen Alu alive for as long as
possible by feeding its population, maintaining authority and essential
capacity, protecting routes, allocating labour and troops, and responding to
displaced cohorts.

Combat remains abstract. If a hostile force reaches the Seat, the engine
resolves defence from committed people, supplies, readiness, walls, route, and
local conditions. If the defence loses and the Seat falls, the campaign ends.

### 8.9 Royal verbs

The stable Alpha 0.7 verbs are:

- inspect;
- allocate and ration;
- levy and assign;
- appoint and dismiss;
- judge;
- demand, offer, promise, and correspond;
- dispatch;
- build and repair;
- tax, exempt, and requisition;
- protect and close;
- accept, settle, redirect, and refuse;
- offer, consult, swear, and expiate;
- wait and end the fortnight.

The king acts through orders, officials, institutions, and messengers. A valid
order identifies its subject, authority, executor, material cost, labour,
destination, and expected delay where those facts apply.

### 8.10 Target window ownership

| Window | Owns | Principal verbs |
| --- | --- | --- |
| Hall | urgent matters, passage of time | inspect, open, end fortnight |
| Alu | cohorts, institutions, sites, walls, works, dependent centres | inspect, build, repair, accept, settle, redirect, refuse |
| Trade | Exchange, merchants, cargo, caravans, commercial routes | finance, authorize, request, offer, tax, exempt, requisition, escort, close |
| Storehouse | stores, labour roll, land, reserves, dues | inspect, allocate, ration, prioritize, tax |
| World | Alu, roads, sea legs, moving parties, displacement, known danger | inspect, compare, follow, open correspondence |
| Scribes | letters, reports, promises, obligations, archives | read, file, delegate, reply, demand, offer, promise, dispatch |
| Court | king, court, officials, succession, justice | appoint, dismiss, judge, pardon, name heir |
| Muster | formations, cohorts, detachments, garrisons, escorts, defence | levy exact cohorts, release, assign, reinforce, escort, recall |
| Shrine | temple support, rites, divination, oaths | offer, consult, swear, expiate |

Counsel, Orders, and Help remain supporting utilities. An action has one owning
window even when another window links to it. World displays trade movement;
Trade owns commercial decisions.

### 8.11 Determinism and knowledge

The same version, shared world data, chosen Alu, seed, and confirmed action log
produce the same run.

World state contains true cohorts, cargo, conditions, and outcomes. The player
sees dated Belief: estimates, reports, missing information, and claims. The map
must not reveal a trade route, epidemic, movement, or failure merely because
the simulation knows it.

### 8.12 Pinned 1.0 endgame

Iron is a 1.0 endgame, not an Alpha 0.7 task. Alpha 0.7 must not add a research
bar, iron victory condition, or partial technology system.

---

## 9. How Alpha 0.7 tasks are specified

The following tasks are ordered by dependency, but none is permission to code
from the short description alone.

Before implementation, every task must receive a focused design pass against:

- current engine state and authority;
- existing content and identifiers;
- current UI and action routes;
- save and replay compatibility;
- conservation and deterministic ordering;
- player knowledge versus hidden World state;
- performance across the complete shared world;
- tests that demonstrate causality rather than only a successful function call.

If a task exposes a contradiction with an earlier task, the specification is
revised before code is added. Temporary adapters must have an explicit deletion
condition.

---

## 10. Alpha 0.7 implementation tasks

### Task 1 — Classify the existing map as Alu and dependent content — **Done**

Done and dusted. Every map mark carries one classification and one owning Alu.
The classification and the reasoning behind each verdict are in
`docs/ALU_CLASSIFICATION.md`, which is now a record, not a plan.

### Task 2 — Finish one-authority world consolidation — **Done**

The kernel owns the shared facts and date. Court-facing views project from it,
foreign actors use kernel organizations and beliefs, and all systems advance
through the ordered phase runner. Old saves are refused by version. The
authority audit reports no duplicate or missing authority.

### Task 3 — Make the shared world start every campaign — **Done**

`load_campaign(chosen_alu, seed)` always loads `content/world.toml`, then
requires a matching authored profile under `content/courts/`. `seat` is the
only current profile. The other 54 Alu run autonomously and are refused as
player starts until their courts are authored. Saves record `chosen_alu`.

### Task 4 — Make kings own Alu — **Done**

**Decided:** Every Alu opens with its own polity and ruler identity. Imperial
`power` authors a polity-to-polity overlord, not ownership of the vassal's Alu.
A polity may hold several Alu after capture. Dependent palace centres remain
Sites of their Alu and have no king. `Settlement.owner` is authoritative;
holdings are derived. Succession replaces `Polity.ruler`; capture replaces
`Settlement.owner`. The organization that runs stores and policy remains a
separate economic controller.

**Where it stands:** The registry enforces one opening owner and ruler for all
55 Alu. Succession and capture change those references. Royal correspondents
resolve to the same Person rulers used by polity ownership.

**Complete when:** Every Alu resolves to exactly one current owner and king;
succession or capture changes that authority explicitly; foreign diplomacy
addresses kings; discontent remains cohort and institutional state.

### Task 5 — Reduce Alu contents to the minimum authentic model — **Done**

**Current code:** Legacy Court separately stores estates, workshops,
institutions, projects, formations, stores, and harbour traffic. Kernel `Site`
and `Organization` can already represent functions, capacities, holders,
palaces, temples, merchants, and productive ground, but the data remains much
more granular and split between systems.

**Decided:** An Alu is a Settlement with an owner and king, a governing
Organization, population Cohorts, Book lots, and one rule-bearing food Site.
Dependent palace centres and hinterland capacities are Sites of that Alu.
Exchange is the market behaviour of organizations, not a building. A harbour
exists through a sea-route endpoint and cargo capacity. Temple, walls, and
formations are added only where their existing rules consume them; farms,
workshops, warehouses, and villages are not multiplied into building records.

**Where it stands:** All 55 Alu pass the minimum-state check and autonomous
turn. The playable court is an authored projection over the same registry,
Book, cohorts, sites, and organizations; no empty court is fabricated for an
Alu without a profile.

**Complete when:** Every Alu can be simulated with only the agreed contents;
dependent palace centres belong to an Alu and have no separate king; farms,
workshops, warehouses, and villages are not needlessly multiplied into
buildings.

### Task 6 — Complete the cohort population model — **Done**

**Current code:** Kernel `Cohort` already stores settlement, kind, households,
people, origin, labour, ration, hunger, and grievance. `seat_people.py` already
conserves people through split and merge, maps legacy dependent groups, and
prevents work draws from exceeding the cohort. Legacy `Place.population`,
plague compartments, and `Court.dependents` remain competing population
representations.

**Design before implementation:** Define the smallest representation for
ethnicity, status, health, displacement, institutional tie, and organized
violence. Specify compatibility rules for merging and whether ethnicity can
ever change. Decide how disease state composes with cohorts without restoring
a separate place population.

**Complete when:** Every ordinary person exists in exactly one cohort;
population totals are derived; ethnicity persists through split, merge,
migration, hunger, disease, and casualties; player-facing totals remain Belief
estimates.

### Task 7 — Replace generic corvée days with cohort detachments — **Done**

**Current code:** `RaiseCorvee` accepts only days. `engine.land` chooses legacy
dependent groups automatically, `Court.corvee_sources` stores the result, and
`seat_people.py` adapts those days into cohort work draws. This already prevents
some double spending but does not let the king choose a cohort, head count,
destination, duration, ration source, or official.

**Design before implementation:** Define the corvée order and temporary
detachment lifecycle. Specify conversion between heads and person-days,
seasonal availability, competing levy or harvest assignments, return and
merge, refusal, fatigue, mortality, grievance, and cancellation.

**Complete when:** The player can levy all or part of a chosen cohort for a
specific task; those people are unavailable elsewhere; all people, labour, and
rations conserve; release returns the surviving detachment without duplication.

### Task 8 — Unify physical roads and sea legs — **Done**

**Current code:** Legacy routes are 56 courier-oriented edges with mode,
seasonality, legs, and risk. Kernel routes have explicit legs, cargo capacity,
toll jurisdictions, season, and risk, but only two are authored. Terrain still
does not affect travel.

**Design before implementation:** Map every current route into kernel legs.
Define direction, controller, condition, maintenance, closure, capacity, risk,
and seasonal rules. Decide which properties belong to a whole route and which
belong to a leg. Do not add terrain effects without an explicit rule and test.

**Complete when:** Letters, caravans, voyages, troops, disease, and displaced
cohorts use the same physical network; no legacy route graph remains
authoritative.

### Task 9 — Build autonomous trade routes and caravans — **Done**

**Current code:** Kernel trade matches grain bargains, reserves goods and
capacity, creates `Contract` records, and moves sea voyages and land caravans
with risk and arriving news. Successful movement strengthens durable trade
routes, inactivity weakens them, and the Trade window shows the chosen
Exchange's evidence.

**Design before implementation:** Generalize movement without erasing the
meaningful differences between ships and caravans. Define merchant decision
inputs, transport ownership, cargo, provisions, guards, rerouting, losses,
commercial memory, route formation and decay, duties, exemptions, royal
finance, escorts, requisition, and information carried by travellers.

**Complete when:** Autonomous merchants create real land and sea movements;
repeated successful movements produce a known trade route; unsafe or
unprofitable routes decay; goods and transport capacity conserve; not every
physical road becomes a trade route.

### Task 10 — Implement material shocks — **Done**

**Current code:** Legacy content contains an authored drought curve; legacy and
kernel farming consume climate; plague can spread through arrivals; kernel
voyages can be lost; succession and route risk exist. Earthquake, general
storm damage, political rupture, route-violence escalation, and a common shock
framework do not.

**Design before implementation:** Specify each of the eight shocks as changes
to existing quantities and capacities. Define geographic reach, onset,
duration, recovery, discoverability, seeded probability, and event records.
Prefer extending shared climate, health, route, ownership, and capacity rules
over creating eight isolated minigames.

**Complete when:** Each shock has deterministic unit tests for its direct
effects and leaves an inspectable causal record. No shock writes “collapsed,”
selects a scripted victim, or invents consequences outside ordinary systems.

### Task 11 — Implement cascading failure and recovery — **Done**

**Current code:** Food loss weakens and kills cohorts, closes labour and trade
capacity, displaces survivors, and can turn refused or desperate groups into
attackers. Shock recovery restores damaged capacities. Headless runs retain a
mostly stable unshocked population, recover isolated damage, and produce
multi-Alu displacement under connected shocks without a collapse flag.

**Design before implementation:** Identify the smallest feedback loops that
connect food, labour, institutions, routes, trade, reports, obligations,
displacement, and defence. Define reversible distress separately from
abandonment or capture. Include recovery and rerouting so collapse is possible,
not guaranteed.

**Complete when:** Long headless runs demonstrate a mostly stable unshocked
baseline, frequent recovery from one shock, and possible multi-Alu cascades
from connected shocks. Every failure can be reconstructed from stored events.

### Task 12 — Implement displacement and abstract defence — **Done**

**Current code:** Severe hunger splits a routed displaced cohort. Reception may
accept, settle, redirect, or refuse it. High grievance and hunger can produce a
hostile force; defence consumes grain, uses assigned defenders and walls, and
records either casualties or the chosen Seat's fall.

**Design before implementation:** Define why cohorts leave, how they choose
destinations, what they carry, and how reception changes cooperation. Define
the conditions that distinguish petitioners, settlers, raiders, and attackers.
Specify defence inputs and consequences without a tactical battle layer.

**Complete when:** Cohorts move without duplication, may be accepted, settled,
redirected, or refused, and can become a hostile force through causal state.
A defeated Seat ends the chosen-Alu campaign; combat produces an explainable
record and conserves people and supplies.

### Task 13 — Rebuild royal actions around the agreed verbs — **Done**

**Current code:** The registry exposes 38 player actions across 20 contexts.
Allocation, correspondence, appointments, justice, dues, works, rites,
quarantine, troop assignment, cohort reception, and cohort-specific corvée all
have action routes. Trade finance lends real crown lots to merchants;
requisition returns merchant lots to crown ownership and custody; exemption
sets dues to zero; closures, escorts, requests, and offers reuse their existing
route, troop, and correspondence actions.

**Design before implementation:** Audit each existing action against the target
verb list. Keep compatible action IDs where semantics remain valid; retire
obsolete player paths without breaking replay. For every new action define
subject, authority, executor, cost, delay, refusal, structured outcome, and
owning window before adding it to the registry.

**Complete when:** Every enabled royal verb has one registered action path,
one owning window, deterministic cost, explicit confirmation where destructive,
and tested refusal and success outcomes. No UI mutates world state directly.

### Task 14 — Reorganize windows and add Trade — **Done**

**Target:** The Hall exposes Scribes, Alu, Trade, Storehouse, Muster, Court,
Shrine, and World beside itself. Alu owns cohorts, institutions, sites, and
works; Muster owns exact detachments and levy/corvee orders; foreign Trade
orders pass through the Scribes' writing and review path. Function keys are
not part of the shared interaction contract.

**Design before implementation:** Compare every existing working action with
the target ownership table before moving controls. Decide whether Alu absorbs
Storehouse and City immediately or through a staged adapter. Preserve focused
letter, archive, institution, and chronicle windows. Do not remove a working
door until its complete action path is visible elsewhere.

**Complete when:** The nine primary rooms own the agreed verbs; Trade has a
working route/caravan/Exchange view; World links to Trade without owning its
orders; supporting utilities remain available; keyboard, mouse, focus,
minimum-size, and window-persistence tests pass.

### Task 15 — Add the Alpha 0.7 campaign lifecycle — **Done**

**Current code:** A run records its chosen authored Alu profile and seed, uses
the seed for a one-to-three-year pressure threshold, stops when the Seat falls,
and reports fortnights, reigns, population, shocks, and cause. All 55 Alu run;
only `seat` currently has authored player-court content.

**Design before implementation:** Define how the seed produces initial
variation and a pressure window without a hidden destruction schedule. Define
the minimum campaign result: chosen Alu, reigns, fortnights survived, population
history, major losses, cause of Seat fall, and world state at the end.

**Complete when:** Any Alu with an authored court profile can start
reproducibly, the world can remain stable or cascade naturally, Seat fall ends
the run with an evidence-backed record, and no Alpha 0.7 system checks an iron
or technology victory.

### Task 16 — Save migration, performance, balance, and release verification — **Done**

**Current code:** Save version 17 refuses older logs, records `chosen_alu`, and
rebuilds a campaign by reapplying confirmed actions and accepted text. The
authority and inventory audits are clean; compile, save/load, conservation,
and representative headless runs are the release checks. The 96-turn reference
run advances in about 75 ms per turn on the development machine. In the
30-year seed-11 run the first Alu empties by year 20 and six are empty by year
30, while unshocked seeds remain mostly stable.

**Design before implementation:** Set migration policy before deleting fields.
Define representative seeds, chosen Alu, shock combinations, run length, and
performance budget. Separate invariant tests from balance expectations so
tuning does not weaken conservation.

**Complete when:** Old saves fail with a clear version message; authority and
inventory audits have no faults; conservation, save/load, benchmark, and
representative long runs are clean; multiple seeds demonstrate stability,
recovery, and cascading failure without a scripted collapse.

---

## 11. Pinned outside Alpha 0.7

### Release 1.0

- the Iron Age transition and victory condition;
- other durable survival victories;
- the final campaign endgame.

### After Alpha 0.7

- civilization-specific kingship, government, court, law, religion,
  administration, and UI variations;
- separate campaign or scenario packages;
- reconsideration of how Greek, Egyptian, Levantine, Anatolian, and other Alu
  differ beyond shared world data.

### After 1.0

- tactical battles and deeper operational warfare;
- territorial conquest and detailed army manoeuvre;
- individually simulating the hundreds of minor settlements;
- additional regions, eras, and larger population simulation.

These ideas must not quietly enlarge the Alpha 0.7 task list.

---

## 12. Decisions and open questions

Settled here, or in `SPEC.md` where marked. Change them there first.

- **Task order.** `SPEC.md` §6 sets it: retire the legacy court (Task 2),
  then the correspondence slice, then the world and the rooms, then balance.
  Tasks 3 to 16 below are dependency order inside that.
- **Save policy.** Refuse a pre-change save with a clear version message. No
  migration path in Alpha 0.7.
- **Survival scoring.** The end-of-run record states: chosen Alu, seed,
  fortnights survived, reigns, population at start and end, goods and routes
  lost, the shocks that landed, and the cause of the Seat's fall.
- **Collapse window.** `SPEC.md` §1: a balance target of year 15 to 30 for an
  unaided world, not a rule the engine enforces.

Resolved: only Alu with authored court profiles are playable. All 55 remain
simulated; `seat` is the only current playable profile.

---

## 13. Superseded documents

Done and dusted. Kept as record. Neither adds a requirement to this file.

| Document | Why it is closed |
| --- | --- |
| `docs/archive/2026-08-01-release-1.0/SPEC.md` | The release-1.0 contract, replaced by the root `SPEC.md` |
| `docs/ALU_CLASSIFICATION.md` | Task 1, implemented; now a record of the verdicts |
| `docs/archive/PHASE_C_AUTHORITY.md` | Superseded by the completed authority design |
| `docs/archive/ONE_AUTHORITY_DESIGN.md` | Task 2 design, implemented |
| `docs/archive/TASK_2_TODO.md` | Task 2 completion record |
| `docs/WORLD_AGENT_PLAN.md` | Correspondence chain delivered |
| `docs/FARMING_HISTORICITY.md` | A standing note, never a plan |

The authority documents are archived because the audit is clean.
