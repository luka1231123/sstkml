# SAY TO THE KING, MY LORD

## Unified product and implementation specification

- Status: authoritative
- Revision: 2026-07-28
- Current milestone: M13.0
- Finish line: M16; there is no M17

This document supersedes the former root specification, the append-only
decision log, the rolling status file, and the standalone interface plans.
Those records remain intact under `docs/archive/2026-07-28/`; they explain how
the present code came to exist, but they no longer decide what the game becomes.

When code, old documentation, and this specification disagree, this
specification is the target. During M13 migration, existing behaviour may be
kept temporarily only when its replacement is named here and its deletion gate
is explicit.

---

## 1. The game

### 1.1 Purpose

> **SAY TO THE KING, MY LORD is an information-constrained rulership
> simulation in which autonomous households, cities, institutions, merchants,
> and courts move finite people and goods through space and time, while the
> player tries to preserve Ugarit's material capacity, legitimacy, and
> obligations through fallible people and delayed knowledge.**

The player does not operate a kingdom from above. The player is a ruler at one
court, receiving partial reports and acting through people. The world continues
without the player, does not exist merely to furnish letters, and does not wait
for a screen to be opened.

The inspiration taken from deep simulation games is causal completeness rather
than indiscriminate detail. The game does not need to name every shepherd. It
does need to know why a shipment exists, who owns it, where it is, which people
move it, and what fails when it does not arrive.

### 1.2 Player fantasy

The fantasy is not “solve the authored crisis.” It is:

1. Learn what may be happening from dated, interested, sometimes conflicting
   testimony.
2. Decide which obligations, people, and capacities must be protected.
3. Issue exact orders or delegate policies to people with their own knowledge
   and interests.
4. Watch consequences propagate through material and political systems.
5. Revise institutions and relationships before a local failure becomes a
   cascade.

The player should feel less like an omniscient optimizer and more like the
person holding together a machine whose components can speak, conceal, bargain,
leave, and break.

### 1.3 The primary loop

Each fortnight:

1. The world advances simultaneously.
2. Actors observe some of what happened.
3. Reports, petitions, arrivals, and exceptions reach the court after real
   delays.
4. The Hall presents what the court currently knows needs attention.
5. The player reads, cross-checks, judges, allocates, negotiates, delegates, or
   deliberately does nothing.
6. Orders enter institutions and journeys; they do not teleport effects.
7. The world advances again, including everywhere the player did not look.

### 1.4 Success, failure, and history

The historical starting situation constrains the run. The historical outcome
does not.

Ugarit is not secretly sentenced to burn. It may be destroyed, depopulated,
subordinated, transformed, or preserved at great cost. Survival is not a
victory screen, and destruction is not the only honest ending. M16 evaluates
continuity, obligations, population, institutional capacity, political
autonomy, and the archive produced by the actual run.

A strong run may preserve people while losing independence. A ruler may keep
the palace and hollow out the countryside. A city may survive the scenario
horizon but create debts its successor cannot bear. The epilogue must describe
those outcomes rather than force all runs into one archaeological layer.

---

## 2. Non-negotiable laws

### Law 1 — The simulated world causes the story

Letters, petitions, prices, raids, migrations, and political demands originate
in world state and actor decisions. A cadence may schedule routine accounting,
but it may not fabricate foreign activity to make a static world appear alive.

### Law 2 — Every consequential flow has a ledger

Goods, labour, people, animals, ships, credit, and obligations have explicit
sources, owners, locations, transfers, uses, and losses. No unexplained faucet
or sink may decide a strategic outcome.

For every conserved good over a turn:

```text
opening + produced + imported + recovered
  = closing + consumed + exported + spoiled + destroyed
```

The same person-days cannot be assigned to fields, corvée, workshops, ships,
and formations at once.

### Law 3 — The outside world is autonomous

Every included polity and settlement has persistent material state and an
actor policy. It produces, consumes, plans, trades, refuses, substitutes,
stores, moves, and reacts without player contact. Removing the player court
from a headless run must not stop the rest of the network.

### Law 4 — The player sees Belief, never World

`World` is truth. Each actor, including the player court, has a dated and
sourced `Belief`. The UI and language-model layer read only the player's
Belief. Conflicting claims coexist. Unknown is a legitimate value.

No freshness badge, confidence label, adviser summary, or map position may
silently turn a claim into truth.

### Law 5 — Commands act through people and institutions

Changing an allocation may be direct bookkeeping. Anything at distance or
requiring judgement must have a delegate, authority, execution site, travel or
communication delay, and report path.

### Law 6 — The interface interprets exactly; people may not

Direct controls and parsing are UI and must not misread the player.

After an order is previewed and confirmed, its structured meaning is exact.
The delegate may then apply it literally, late, incompletely, corruptly, or
competently according to the simulation. Interface ambiguity is a defect;
human interpretation is content.

### Law 7 — Determinism is structural

The same version, seed, content, and confirmed action log produce the same
world and hashes. Randomness comes only from content-addressed, named streams.
No system depends on iteration order, wall-clock time, network timing, model
output timing, or a shared random sequence.

### Law 8 — The language model never decides the world

The optional model may classify player prose against a closed action grammar
and phrase already-selected content. It may not invent facts, calculate
outcomes, choose NPC policy, mutate state, or be required for play.

Replay never invokes a model. Offline play is a complete supported mode.

### Law 9 — Material causality is not supernatural

Gods are real to the people in the simulation, not objective hidden
interventions in its physics.

- Disease spreads through people, animals, goods, routes, and conditions.
- Weather and harvests arise from the climate and production systems.
- Fire, pregnancy, death, and military outcomes have material causes.
- Rites, vows, omens, and expiation affect expenditure, labour, legitimacy,
  policy, morale, relationships, and what actors believe.
- There is no true `cause_oath_id`.
- A “correct” offering does not alter pathogen transmission.
- Divination is a fallible forecast from observations, traditions,
  competence, and interest; it does not read a privileged future value.

The game may allow the player to believe that a rite changed events. It must
not settle the theology behind the screen.

### Law 10 — History constrains mechanisms, not outcomes

Authored facts state their confidence. Attested people, places, institutions,
and obligations are distinguished from plausible reconstruction and fiction.
Uncertainty is exposed rather than repaired with false precision.

### Law 11 — One current path

There is one current economy, one world ontology, one order pipeline, one
Belief boundary, and one interaction contract. Replaced source code is deleted;
Git is its archive. Compatibility adapters are temporary, named, tested, and
assigned a deletion milestone.

---

## 3. Historical stance

### 3.1 What “historically accurate” means here

The game aims for:

- plausible institutions, material constraints, travel, production, and
  diplomatic practice;
- an internally coherent late-thirteenth-century starting cast;
- uncertainty labels where chronology or interpretation is disputed;
- historically plausible magnitudes expressed as tunable scenario values;
- no claim that a convenient simulation coefficient is a recovered ancient
  measurement.

Every named historical content record must carry:

```text
status: attested | reconstructed | fictional
date_range: earliest/latest plausible year
source: citation key(s)
confidence: high | medium | low
note: what is known, inferred, or invented
```

Mechanical parameters use the same provenance discipline:

```text
basis: attested | comparative | design
source: citation key(s), if any
tuning_note: why the game value differs or remains uncertain
```

### 3.2 The economy is mixed, not a modern market

Ugarit's palace, temples, estates, villages, merchant houses, and private
households overlap without collapsing into one royal inventory. Taxes and
corvée coexist with gifts, contracts, loans, privately controlled property,
and merchants tied to royal administration.

Consequences for the simulation:

- The palace owns and commands some goods, not all goods in its territory.
- A merchant can serve the crown and still have household interests,
  creditors, partners, exemptions, and private cargo.
- A local quote is not a universal price.
- Redistribution and exchange coexist.
- Revenue is a transfer from a real producer or shipment, not periodic income.
- Royal orders have jurisdictional and institutional limits.

The Ugaritic record includes town and district contributions of silver,
produce, and corvée labour, and also tablets concerning merchants and private
individuals. The design should preserve that plurality rather than choose
between “command economy” and “free market.”

### 3.3 Long-distance exchange is physical

Late Bronze Age exchange connected Anatolia, northern Syria, Mesopotamia,
Cyprus, Egypt, the Levant, and the Aegean. The Uluburun wreck demonstrates a
mixed high-value cargo and a broad network; it does not define the capacity or
cargo of every vessel.

Trade in this game is therefore a network of specific contracts, lots,
journeys, intermediaries, and risks. Copper, tin, grain, timber, textiles,
oil, wine, silver, animals, and prestige materials do not become numbers in a
global market pool.

### 3.4 Collapse is multicausal and uneven

The end of the Late Bronze Age was neither simultaneous everywhere nor
explained by a single accepted cause. Climate stress, extraction, inequality,
political conflict, warfare, disease, migration, and failures in interdependent
networks could reinforce one another differently by place.

The game therefore has no collapse meter, scripted invasion date, mandatory
sequence, or universal drought result. A healthy network generally absorbs one
isolated loss. Cascades require weak reserves, connected dependencies,
correlated pressures, and actor choices.

### 3.5 Religion is historical evidence, not secret physics

Ancient rulers interpreted epidemics, harvests, military outcomes, and family
misfortune through vows, rites, omens, and divine anger. The Hittite plague
prayers are valuable evidence for royal reasoning and archive practice. They
are not evidence that an oath changed a pathogen's reproduction rate.

The simulation models:

- the search for a culpable vow;
- factions proposing different ritual causes;
- costly offerings and festivals;
- public confidence or anger after compliance or neglect;
- policy changed by an omen;
- priests with expertise, interests, and reputations;
- coincidence that remains interpretable.

It does not store a metaphysically correct answer.

### 3.6 Content corrections required in M13

The scenario registry must resolve the following before scale-up:

- Do not mix the Amarna-period Rib-Addi and Abimilki directly into
  Ammurapi's late-thirteenth-century court without an explicit fictional or
  archival framing.
- Treat Talmi-Teshub as the ruler/viceroy at Carchemish, not casually as
  Ammurapi's brother.
- Mark the family relationship of Ehli-Nikkalu as disputed rather than fact.
- Use Sinaranu's exemption as an earlier precedent or inherited house claim
  where chronology requires it.
- Do not model Mari as an ordinary functioning peer city in Ammurapi's world.
- Gubla and Byblos are one place, not two nodes.
- Split settlements, polities, and regions: Hattusa, Alashiya, the Delta, and
  the Lukka lands are not the same entity kind.
- Replace placeholder equal populations with sourced ranges or explicitly
  labeled design estimates.
- Do not transplant an Amarna formula or diplomatic relationship into the
  later setting without a dated rationale.

### 3.7 Core historical references

These sources establish design constraints; content records should add
page/tablet-level citations as they are authored.

- A. Bernard Knapp and Sturt W. Manning,
  [“Crisis in Context: The End of the Late Bronze Age in the Eastern
  Mediterranean”](https://www.journals.uchicago.edu/doi/10.3764/aja.120.1.0099).
- The French Ministry of Culture,
  [Ugaritic society](https://archeologie.culture.gouv.fr/ougarit/fr/la-societe-ougaritique).
- *The Cambridge Ancient History*,
  [“Ugarit”](https://www.cambridge.org/core/books/cambridge-ancient-history/ugarit/0DD28A3167FEBFE1A51EB8791522CBCC).
- [“The Merchant at
  Nuzi”](https://www.cambridge.org/core/journals/iraq/article/the-merchant-at-nuzi/EE32FAD8C167ADF8630938A7F8E839E3),
  for the relationship between merchants and royal administration.
- [“The Metal Trade of Ugarit and the Problem of Transportation of Commercial
  Goods”](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/288D631EBD77E72D691B387AAD0453D3/S0021088900009979a.pdf/metal_trade_of_ugarit_and_the_problem_of_transportation_of_commercial_goods.pdf).
- Institute of Nautical Archaeology,
  [Uluburun Late Bronze Age
  shipwreck](https://nauticalarch.org/projects/uluburun-late-bronze-age-shipwreck-excavation/).
- The Metropolitan Museum of Art,
  [The Amarna Letters](https://www.metmuseum.org/essays/the-amarna-letters).
- [“Grain Tribute in Hittite
  Syria”](https://www.journals.uchicago.edu/doi/10.1086/724269).
- French Ministry of Culture,
  [Mari's political history](https://archeologie.culture.gouv.fr/mari/en/political-history).
- ORACC,
  [Gubla/Byblos geographic entry](https://oracc.museum.upenn.edu/geonames/cbd/qpn/x000001200.html).

---

## 4. Present foundation and debt

### 4.1 Keep

The existing project has valuable foundations:

- standard-library deterministic engine;
- integer state and content-addressed random domains;
- canonical serialization, hashing, save, and replay;
- World-to-Belief projection;
- action and event records;
- fortnight calendar and seasonal routes;
- agriculture, arrears, bronze, institutions, works, justice, revenue, house,
  succession, plague, and correspondence prototypes;
- a shared cell-grid renderer with terminal and Tk backends;
- keyboard/mouse parity infrastructure;
- the Hall, Inbox, Counsel, and retrieval-grounded Help;
- authored visual language and correspondence corpus.

These are foundations, not proof that the current systems form one world.

### 4.2 Measured baseline at the M13 audit

The 2026-07-27 audit found:

- 338 tests passing;
- 34 authored places, 43 routes, 14 correspondents, and one detailed Court;
- after 96 unattended turns, no foreign `Place` record changed;
- all detailed production, stores, institutions, labour, and politics belonged
  to the player's Court;
- correspondents generated fixed facts on authored cadences;
- the Inbox reached 329 items after 96 idle turns;
- a scripted prudent policy survived while ignoring all foreign relations and
  correspondence;
- the World view hardcoded only 16 nodes;
- state size and hash time grew with the document flood.

The current game is consequently a palace under scripted pressure, not yet an
autonomous world. M13 is the transformation, not an expansion pack.

### 4.3 Debt M13.0 must clear before multiplying the city model

The local model may not be copied outward until these invariants hold:

- a missing institution is not treated as perfectly effective;
- a headless or unstaffed institution cannot produce at full capacity;
- staff quantity and arrears affect actual throughput;
- required upkeep is consumed, not merely checked;
- labour assigned to harvest, corvée, ships, formations, and workshops is
  exclusive;
- a zero harvest still resets seasonal assignments and bookkeeping;
- revolt and institutional failure have consumers rather than discarded
  calculations;
- residual grain, oil, harbour traffic, and misfortune losses are either tied
  to explicit sources or labeled temporary and removed in the named M13 slice;
- quarantine affects physical movement, not only a flag;
- disease has material introduction paths and viable seeding;
- formations cannot retain nominal capability indefinitely without people,
  equipment, and replacement capacity.

### 4.4 Interaction debt M13.0 must clear

Every implemented mechanic must be reachable and inspectable in the primary
windowed interface:

- Inbox selection must not hide a newly read tablet before its body is shown.
- Incoming correspondence needs Read, Answer/Respond, Delegate, Compare, and
  Archive paths, plus Outbox/in-transit state.
- Archive results must open.
- Stores must expose the melt ledger and bronze in circulation.
- Muster must expose summons and deadlines.
- Relations and disease need dossiers.
- Ritual consultations requiring a person must allow the person to be chosen.
- Counsel must preview the exact structured order before it can mutate state.
- Impossible input must explain itself rather than disappear.
- Model-backed parsing and phrasing may not block the UI thread.
- Save, load, autosave, and incompatible-save messaging must be reachable.
- Collections must scroll rather than silently truncate.
- Attention totals must agree in every projection.
- The World view must be generated from scenario and Belief data.

---

## 5. M13 world ontology

The ontology must distinguish identity, ownership, location, authority, and
knowledge. IDs are stable strings. Runtime IDs derive from stable parents,
turn, domain, and local ordinal; they never depend on global creation order.

### 5.1 Geography and political structure

`Region`
: A broad geographic or ecological area. It may modify climate, travel, and
  production. It is not a government or a market.

`Polity`
: A political authority with a ruler, court, obligations, strategy,
  relationships, controlled or claimed settlements, and succession.

`Settlement`
: A persistent inhabited node with population cohorts, local stores,
  institutions, assets, production, consumption, security, and a governing
  authority.

`Site`
: A port, estate, mine, pasture, watch post, shrine, or other productive or
  strategic location that is not necessarily a city.

`Route`
: A connection between sites or settlements with mode, legs, seasonal
  availability, capacity, ordinary cost, toll jurisdictions, and risk. Routes
  transport people, goods, animals, news, and disease; they are not
  letter-only edges.

One entity may participate in several relationships: Ugarit is a settlement;
its kingdom is a polity; Ma'hadu is a port site/settlement under that polity;
Alashiya is a polity or regional label whose particular ports must be named
separately where the simulation needs them.

### 5.2 People, households, and organizations

`Person`
: Persistent identity, age, household, location, offices, skills,
  competence, loyalty, interests, health, authority, relationships, memories,
  and actor Belief.

`Household`
: People, dependants, labour capacity, consumption, stores, land or other
  assets, debts, obligations, status, and patronage. Ordinary households may be
  cohorts; politically connected households are named.

`Organization`
: Palace, temple, merchant house, village council, workshop group, military
  formation, ship partnership, or other enduring actor. It owns assets and
  goods, employs or commands people, holds obligations, and follows policy.

`Office`
: Authority attached to an institution or jurisdiction. Appointment changes
  what a person may observe and command; it does not merge the office's assets
  into that person's inventory.

Every decision belongs to a person or organization. A settlement itself may
have a policy controller, but it is never an unexplained omniscient actor.

### 5.3 Population scale

The game uses persistent cohorts for ordinary population:

- free agricultural households;
- dependent palace/temple workers;
- craftspeople;
- merchants and carriers;
- soldiers and watch;
- enslaved or coerced labour;
- displaced households;
- elite and cult households.

Cohorts preserve origin, residence, household count, people by broad age band,
skills, assets, obligations, health, grievances, and patrons. Splitting and
merging must conserve people and history. A cohort becoming politically
important may generate named representatives without recreating its past.

Named people remain persistent even when not in contact. Detail may be sparse,
but “dehydrating” an actor must never erase ownership, memory, relationship,
location, obligation, or previous acts.

### 5.4 Goods, lots, and assets

The first complete economy is intentionally small:

- grain, seed grain, and fodder;
- oil and wine;
- livestock and horses;
- wool/flax and textiles;
- timber and charcoal;
- copper, tin, bronze, and finished bronze equipment;
- pottery/containers;
- silver and gold by weight;
- a grouped prestige category for resin, glass, ivory, lapis, amber, and
  similar goods until a scenario needs a separate chain.

`GoodsLot` records good, quantity, quality band, owner, holder, location,
provenance, and reservations. Goods do not vanish when a contract is signed.
Ownership and custody may differ while cargo is in transit.

`Asset` records owner, location, kind, condition, capacity, operators, upkeep,
and liens. Fields, wells, workshops, granaries, ships, pack trains, roads,
walls, and harbours use the same ownership and maintenance grammar.

### 5.5 Obligations, contracts, credit, and claims

`Obligation`
: Party, beneficiary, clause, quantity or service, due rule, status, authority,
  and consequences actors believe apply. Taxes, corvée, rations, tribute,
  diplomatic gifts, oaths, debts, and summons all use explicit clauses.

`Contract`
: Parties, goods/service, quantity, quality, quote and payment unit, delivery
  place/window, carrier, risk allocation, security, witnesses, and status.

`Debt`
: Creditor, debtor, principal, unit, due rule, security, payments, and
  enforcement history.

`LegalClaim`
: Parties, object, assertions, evidence, jurisdiction, precedent, and outcome.
  M12's authored cases become examples; M13 later generates disputes from
  debts, land, contracts, injury, inheritance, exemptions, and service.

### 5.6 Movement

`Journey`
: People/animals/assets moving together, route plan, current leg, provisions,
  pace, purpose, permissions, risk, and intended report path.

`Shipment`
: Contract or order, cargo lots, owner, custodian, carrier, capacity consumed,
  origin, destination, route, status, expected window, and losses.

An envoy, caravan, ship, troop formation, refugee cohort, and courier use the
same route availability and location rules while retaining type-specific
capacity and decisions.

### 5.7 Orders and missions

`Order` contains:

```text
id
principal
delegate
issued_at / received_at
authority
verb and target
trigger
scope and exclusions
quantity or service
budget and payment good
reserve floor / price ceiling / risk limit
destination or jurisdiction
deadline / expiry / review date
reporting rule
confirmed structured meaning
original prose, if any
status and execution log
```

Statuses:

```text
draft -> confirmed -> dispatched -> received
      -> accepted | refused
      -> active -> blocked | completed | expired | revoked
```

`Mission` binds an order to a journey and delegate. No foreign action completes
merely because an Order object exists.

### 5.8 Observation, claim, and Belief

`Observation`
: What an actor could perceive at a place and time, with method and limits.

`Claim`
: What an actor asserts, derived from observations, memory, interest, and
  distortion. Claims retain source, observation date if known, transmission
  chain, received date, confidence basis, and linked subject.

`Belief`
: An actor's collection of claims and deductions. Conflicts remain. A
  deduction records its inputs; it does not overwrite them.

Documents and conversations carry Claims. They are not the origin of facts.

---

## 6. World simulation

### 6.1 Simultaneous turn resolution

The M13 engine must not mutate cities one by one in an order that advantages
the first city. Each fortnight operates on a read-only opening snapshot,
collects intents, and resolves contested resources globally with stable rules.

Target phase order:

1. Advance calendar and derive regional seasonal/climate conditions.
2. Complete scheduled leg arrivals, births, deaths, deadlines, and previously
   committed effects.
3. Project each actor's local observations into its own Belief.
4. Actors and standing orders submit intents from that Belief.
5. Resolve exclusive labour, asset, route, and transport capacity.
6. Run production, maintenance, construction, and institutional services.
7. Run household, organization, formation, and journey consumption.
8. Create quotes; negotiate or match compatible contracts; reserve goods and
   capacity.
9. Load, move, unload, lose, seize, or reroute physical journeys and cargo.
10. Settle delivery, payment, tax, debt, tribute, and obligation ledgers.
11. Run disease, health, fertility, migration, and mortality from the resulting
    contacts and conditions.
12. Resolve political reactions, appointments, disputes, refusals, and
    relationship memory.
13. Degrade or repair institutions and assets from use, upkeep, staffing, and
    events.
14. Generate new observations, reports, petitions, and documents from what
    actors noticed and want.
15. Project the player court's Belief and assemble the Hall docket.
16. Accept player actions; dispatch resulting orders and journeys.
17. Assert invariants, hash, and autosave.

The implementation may split phases further. It may not change their causal
direction without updating this specification and the invariant tests.

### 6.2 Production

Production consumes exclusive inputs:

```text
potential output
  × environmental response
  × supplied labour response
  × asset/institution response
  × input-material response
  × skill/organization response
```

All factors are authored integer tables scaled by 1000. Operation order is
pinned by tests. Output becomes owned GoodsLots at a location.

Agricultural output depends on local land, water, seed, labour, tools, and
growing-season conditions. A regional shock is correlated but local modifiers
matter; every eastern Mediterranean settlement does not receive one identical
harvest roll.

### 6.3 Consumption and household pressure

Households and organizations consume food, fodder, fuel, upkeep, and production
inputs. Shortage drives choices rather than an immediate generic unrest delta:

1. draw down accessible reserves;
2. substitute goods or reduce consumption;
3. sell output, animals, tools, or claims;
4. borrow or pledge assets;
5. seek patronage, exemption, or relief;
6. evade tax/service or desert an institution;
7. send members away, flee, band together, or accept bondage;
8. suffer disease and mortality risk.

These choices create debts, petitions, lost capacity, factions, and eventual
displacement. M14 consumes those real histories.

### 6.4 Labour and authority

Every labour pool is exclusive per fortnight. Availability derives from people
at a place, health, status, season, obligations, and enforcement.

An order cannot allocate labour the principal does not control. Raising corvée
creates an obligation, enforcement effort, avoidance, and political memory; it
does not summon abstract days from the world.

### 6.5 Institutions

Institution output depends on:

- physical condition and asset capacity;
- required staff actually present;
- staff health, arrears, skill, and loyalty;
- a competent authorized head where the task requires one;
- consumed upkeep and operating inputs;
- congestion and current workload.

Missing, headless, empty, unfed, or unequipped institutions have explicit
degraded behaviour. There is no “missing means 1000” fallback.

Institution reports are claims by responsible people. A false report does not
change the physical condition.

### 6.6 Trade and price

There is no global exchange and no always-visible market-clearing price.

A quote is:

```text
seller + buyer/audience
place and date
good + quality + quantity band
payment good/credit terms
unit price
validity window
delivery terms
source of the player's knowledge
```

Actors form quotes from their reserve target, expected production and demand,
urgent obligations, transport/risk cost, relationship, bargaining position,
credit exposure, and remembered alternatives. The price algorithm is
deterministic and tunable; it is not described as an exact ancient formula.

Palace orders, temple stores, household exchange, merchant contracts, taxes,
tribute, gifts, and seizure remain distinct transfer mechanisms.

### 6.7 Logistics

A physical trade requires:

- goods that exist and are transferable;
- an owner willing or compelled to transfer them;
- a contract or authority;
- containers where required;
- a ship, caravan, or other carrier with capacity and condition;
- crew, animals, provisions, and wages/rations;
- an available route and permissions;
- loading, travel, and unloading time;
- a destination institution able to receive it.

Season, weather, tolls, port capacity, piracy, hostility, disease, and asset
condition affect individual legs. The closed sea blocks suitable sea movement,
not just letters. A journey already at sea follows the explicitly authored
hazard/continuation rule for its route; it does not teleport back.

### 6.8 Politics and relationships

Polities and organizations pursue needs through named officeholders. Policy
uses deterministic priorities such as reserve preservation, obligations,
dynastic security, revenue, patronage, prestige, military security, and
factional interest.

Relationship state is memory of acts and claims, not a single universal
friendship score. It records:

- status each party claims;
- fulfilled, late, refused, and disputed obligations;
- gifts and aid;
- injuries, asylum, extradition, and seizure;
- unanswered or unacknowledged matters;
- witnesses and gossip paths;
- personal relationships between officeholders.

Succession changes authority and personal bonds without erasing institutional
memory, debts, archives, or every political expectation.

### 6.9 Disease

Disease travels with infected people, animals, and where justified contaminated
goods. Exposure uses actual co-location and journeys. Detection is delayed and
reported through observers.

Quarantine closes or restricts specified movement, with material effects on
trade, provisions, correspondence, esteem, and enforcement. It cannot stop a
letter while leaving its courier physically present.

Ritual response can change gatherings, movement, expenditures, care, morale,
and policy. It cannot directly change disease coefficients.

### 6.10 Shocks and cascades

Shocks are explicit events with causes and scope:

- local or regional weather;
- harvest failure;
- fire or infrastructure loss;
- epidemic;
- route closure;
- piracy, banditry, seizure, or war;
- succession and contested authority;
- creditor failure;
- labour flight;
- institutional breakdown.

An authored deck may select plausible initiating shocks, but it may not delete
goods or change statistics without an event that identifies location, affected
owners, and material resolution.

A cascade is an emergent chain across systems. For example:

```text
Hittite grain demand
-> crown extraction
-> household reserve loss and debt
-> labour flight
-> weaker next harvest
-> reduced future tribute capacity
-> refusal or coercion
-> political and military consequence
```

---

## 7. Agency, delegation, and information

### 7.1 Actor decisions

NPC policy is deterministic code over the actor's Belief, obligations,
resources, authority, personality parameters, and remembered outcomes. It may
use scored alternatives, finite-state policy, or utility tables. It never reads
truth the actor could not know and never calls a language model.

An actor decision records:

- considered intents;
- believed inputs;
- chosen intent and tie-break;
- authority used;
- reasons available to the developer inspector.

The player sees only the explanation the actor chooses to give.

### 7.2 Standing orders

A standing order is a delegated policy, not a player-authored script running
against World.

Example:

> If the crown granary is reported below four thousand parisu, seek grain at
> Gubla, preserving twenty talents of silver and paying no more than the last
> witnessed price plus one fifth. Report if no cargo can sail before winter.

The delegate:

- receives it after communication delay;
- evaluates the trigger using the delegate's Belief;
- checks authority, budget, and practical capacity;
- interprets unfilled discretion from competence, loyalty, interests, and
  literalness;
- creates contracts and journeys if possible;
- records blocks and decisions;
- reports according to the order and personal incentives.

The target M13 failure is fair and inspectable: grain arrives late because the
delegate obeyed the confirmed words rather than the player's unstated intent.
The parser did not invent a different order.

### 7.3 Envoys

An envoy is a person on a Journey with an Order, retinue, provisions, gifts,
authority, instructions, and a reporting expectation.

Negotiation uses:

- what the envoy knows;
- what the counterpart knows;
- authority and limits;
- each side's needs and alternatives;
- relationship and protocol;
- competence, loyalty, risk tolerance, and private interest;
- travel and communication latency.

An envoy may wait, fail, exceed authority, accept a side arrangement, fall ill,
be detained, or return with a partial agreement. Every outcome must arise from
state and be replayable.

### 7.4 Correspondence and gossip

Routine reports have schedules because institutions keep accounts. Foreign
letters do not repeat static authored crises merely because a cadence elapsed.

A report is generated when:

- an actor wants something;
- an order requires a report;
- an obligation approaches or fails;
- a material or political event crosses an actor's threshold;
- a routine office account is due;
- an actor strategically repeats, withholds, bundles, or distorts information.

Routine items may be bundled by the court's staff. The Inbox must not grow by
hundreds of near-identical tablets in four years.

There is no source-free “rumour” system. Gossip is a claim copied from one
actor to another, retaining a transmission chain where known. Chains may be
lost or falsely asserted, but the simulation always knows how the information
moved.

### 7.5 Causal audit

Development builds need an omniscient inspector that can answer:

- Why does this lot exist?
- Where did this quantity go?
- Why did this actor choose this?
- Which observation supported that belief?
- Why is this shipment blocked?
- Which order authorized this act?
- Which event caused this report?

The player-facing UI shows evidence available to the court, never this truth.

---

## 8. Interaction specification

### 8.1 The Hall is an exception docket

The Hall is home, not an omniscient analytics dashboard. It shows:

- ruler, date, season, and consistent attention;
- people physically waiting;
- newly arrived and overdue matters;
- changes detected in known claims;
- active orders needing judgement;
- blocked missions and approaching obligations;
- Inbox summary and routes to dossiers.

Each matter states:

- who raised it;
- subject and known location;
- observation date and arrival date where known;
- linked evidence and conflicting claims;
- deadline or age;
- linked order or obligation;
- actions to inspect, acknowledge, delegate, pin, or defer.

The Hall may quote an adviser's recommendation. It may not display an
unattributed “Do this” as the game's correct answer.

### 8.2 Dossiers are the common inspection grammar

People, households, organizations, settlements, institutions, routes,
shipments, contracts, obligations, and orders use the same dossier structure:

- identity and last known location;
- current claims with source, observation date, received date, and confidence;
- conflicting claims;
- trend/history known to the court;
- material and political relationships;
- active orders and obligations;
- actions available from current authority.

Foreign dossiers show last-known claims. Opening them never refreshes knowledge.

### 8.3 Orders desk

The central management screen lists:

- draft and confirmed orders;
- principal and delegate;
- trigger and bounds;
- dispatch/receipt status;
- last execution and last report;
- blocks and exceptions;
- next review/expiry;
- revoke, amend, duplicate, inspect, and contact actions.

Direct manipulation remains available for precise local bookkeeping. Prose is
an additional input surface, not the only route to exact controls.

### 8.4 Counsel

Counsel accepts questions and draft instructions.

For instructions:

1. Parse against a closed grammar.
2. Resolve IDs only from current legal affordances.
3. Present a semantic preview with target, delegate, trigger, quantity, budget,
   limits, deadline, and known conflicts.
4. Require confirmation for every persistent/delegated order.
5. Commit the structured order atomically.
6. Preserve original prose for history, not for replay interpretation.

For questions, Counsel answers from Belief and may be biased or mistaken as a
person. Help remains free and authoritative about controls only.

### 8.5 Inbox and archive

The correspondence workflow is:

```text
arrived -> unread -> read -> answered/delegated/acknowledged
        -> archived
```

The player can:

- open a selected item without it disappearing from under the reader;
- answer or draft a response;
- delegate its requested action;
- compare it beside related claims and documents;
- inspect conversation history;
- see Outbox, in-transit, intercepted-if-known, delivered-if-known, and
  answered status;
- filter and bundle routine reports;
- archive and reopen search hits.

Reading and investigation may cost attention. Wrestling the interface does not.

### 8.6 World view

The World view is data-driven from scenario entities and player Belief. It is
an operational graph rather than an omniscient atlas.

It can layer known:

- routes and seasonal availability;
- journeys and shipments;
- correspondents and report freshness;
- obligations and active orders;
- reported shortages, conflict, or disease.

Unknown nodes, uncertain routes, and stale claims remain visibly uncertain.
Hardcoded subsets are prohibited.

### 8.7 Windows and accessibility

The shared cell grid and real OS windows remain. Cross-checking two documents
or a claim against a ledger is a core interaction.

- Keyboard and mouse invoke the same commands.
- Every enabled action is visible in context.
- Selection and status never rely on colour alone.
- Collections scroll.
- The supported compact layout loses decoration before information or actions.
- Model work is asynchronous and always has a deterministic fallback.

### 8.8 Palace desktop contract

The windowed game is a compact, persistent multi-window workspace in the
existing text-mode visual language, not a full-screen web dashboard.

- Default type is 11-point monospace, adjustable from 9–20 points; layout
  recomposes rather than scaling a bitmap.
- Windows remember geometry, selection, filter, sort, and scroll, are clamped
  to visible monitors, and reopen without resetting work.
- Lists use a stable list/detail/action grammar, show range/total, keep headers
  fixed, and expose disabled strategic actions with the reason.
- Single click selects; double-click or Enter opens. Mutation and attention
  spending require an explicit labeled action.
- Every action shows its cost and result in the active workbench. Destructive,
  delegated, and persistent actions preview exact semantics before commit.
- Claims show source, observation date, received date, age, confidence, and
  conflicts wherever those distinctions affect a decision.
- Help is immediate, deterministic, free, searchable, and generated from the
  live control/action contract. Counsel is optional advice and prose input,
  never the only control path.
- Optional model work is cancellable, request-scoped, unable to steal focus,
  and unable to change deterministic capability.
- Save/load preserves attention and in-progress session state; loading may not
  refill the current fortnight.

The City screen is the visual north star: stateful ASCII should explain the
system, dense records should expose evidence, and the relevant exact action
should sit beside the thing it changes.

---

## 9. Migration from the current game

| Current mechanism | M13 target | Disposition |
|---|---|---|
| One detailed player `Court` | Polities, settlements, organizations, households, and people use shared world grammar | Migrate; remove one-court assumptions |
| Minimal foreign `Place` | Region/Polity/Settlement/Site | Replace |
| Fixed correspondent cadence/facts | Actor observations, wants, obligations, and reports | Replace and delete cadence crisis content |
| Routes transport letters | Routes carry journeys, cargo, people, news, and disease | Generalize |
| Synthetic harbour cargo/revenue | Duties on physical cleared shipments | Replace by M13.3 |
| Residual flat grain income | Named gardens, estates, tribute, tax, or trade lots | Remove by M13.2 |
| Institution upkeep checked only | Upkeep consumed with a ledger | Fix in M13.0 |
| Staffing weakly affects output | Exclusive staff quantity, condition, skill, head, and inputs | Fix in M13.0 |
| Authored justice truths | Cases generated from actual claims and transactions, with authored tutorial cases retained | Migrate by M13.5 |
| Random misfortune changes values | Located, owned, causal shocks | Replace by M13.5 |
| Quarantine flag/mail behaviour | Restrictions on physical journeys and contacts | Replace by M13.3 |
| Objective divine plague cause | Competing human interpretations; material disease | Remove in M13.0 |
| Diviner reads precomputed future | Fallible forecast from evidence and interest | Replace in M13.0 |
| Hardcoded World drawing | Belief-driven graph | Replace in M13.0 |
| Immediate prose execution | Exact semantic preview; delegated Order | Replace in M13.4 |
| Hall prescribes response | Sourced exceptions and attributed advice | Refine in M13.0 |
| Archive grows with cadence spam | Event-driven reports, bundles, retained causal records | Replace by M13.4 |
| Global `letter_seq`/`omen_seq`/`gift_seq` counters | Runtime IDs derived from parent, turn, domain, and local ordinal | Replace in M13.1 |
| Detailed player `Court` as source of truth | `legacy_court` adapter over kernel entities | Delete at the M13.2 exit |

Migration rules:

1. Build a thin vertical slice before converting all content.
2. A legacy mechanism and replacement may coexist only behind an explicit
   adapter named `legacy_*` with a deletion gate in this table.
3. No archived Python package or `old_*.py` directory.
4. Delete replaced code as soon as parity tests and the vertical slice pass.
5. Pre-M13 saves are not guaranteed. Increment the save version and give a
   clear incompatibility message rather than maintaining two world ontologies.
6. Preserve authored prose and research where it can be attached to new
   source-aware content records.

---

## 10. Technical contract

### 10.1 Boundaries

- `engine/` remains standard-library only.
- `belief/` is the only World-to-player projection boundary.
- UI and AI receive primitive Belief/dossier data, never engine objects.
- Content loading validates entity kinds, IDs, units, references, source
  metadata, and authored parameter ranges.
- Rendering does not mutate state.

### 10.2 Randomness

All random draws derive from:

```text
seed | turn | domain | stable entity key | optional local ordinal
```

Domains are registered. Adding or skipping one draw cannot perturb another
system. No `random.*` call exists in engine code outside the keyed wrapper.

### 10.3 Integer state and units

World state contains no floats. Every quantity names its unit. Ratios are
integer-scaled. Conversions are centralized and loss rules explicit.

### 10.4 Events and replay

Systems may return new immutable state plus descriptive events; exclusive event
sourcing is not required. Every consequential transfer and actor decision must
still emit enough structured evidence for:

- conservation checks;
- causal inspection;
- epilogue reconstruction;
- save/replay divergence diagnosis.

Replay uses confirmed structured actions/orders. It never reparses prose or
regenerates model text.

### 10.5 Belief enforcement

Tests must prove:

- no World object is reachable from projected data;
- hidden keys do not enter prompts;
- dossiers expose provenance and age;
- opening a screen cannot create knowledge;
- actor policies read actor Belief, not global World, except physical
  resolution functions applying already-chosen intents.

### 10.6 Performance and scale target

The reference M13 world contains approximately:

- 34–40 settlements/sites;
- 8–12 polities;
- at least 500 persistent named or cohort actors;
- 250 concurrent journeys/shipments at stress;
- 20 years / 480 fortnights.

On the recorded reference development machine:

- a 480-turn unattended reference run completes within 30 seconds;
- p95 world tick remains below 100 ms;
- median state hashing remains below 20 ms;
- the canonical save remains below 25 MiB;
- the active Inbox remains bounded and routine archive records are bundled;
- a benchmark regression above twice the pinned baseline fails review.

These are initial budgets, not permission to discard state. If hardware makes
an absolute CI threshold unreliable, CI compares against a checked-in baseline
on the same runner while the release machine records the absolute values.

### 10.7 Kernel identity and IDs

Section 5 says IDs are stable strings and that runtime IDs never depend on
global creation order. That rule is binding, and the present game breaks it:
`letter_seq`, `omen_seq`, and `gift_seq` are global monotonic counters, so
inserting one letter renumbers every later document and changes the state
hash. The kernel replaces them.

Authored entities carry a namespaced stable ID from content:

```text
region:north_levant
polity:ugarit
settlement:ugarit
site:mahadu_harbour
org:palace_ugarit
person:niqmaddu
```

Runtime entities derive their ID from a stable parent, the turn, a registered
domain, and an ordinal local to that triple:

```text
<parent>/<turn>/<domain>/<ordinal>
site:mahadu_harbour/57/shipment/0
```

The ordinal counts within one `(parent, turn, domain)` only, and is assigned in
the deterministic sorted order of the loop that creates the entities. No kernel
ID may come from a world-wide counter, insertion order, or `id()`. Two runs of
the same seed and the same confirmed actions must produce byte-identical IDs.

Entities live in flat registries on `World`, one mapping per kind, keyed by ID.
Every iteration over a registry is over `sorted(...)` keys. Nothing in the
kernel may depend on mapping order.

### 10.8 Ownership, custody, and lots

`GoodsLot` is the only place a quantity of a good exists. Fields: good, integer
quantity in that good's declared unit, quality band, `owner`, `holder`,
location, provenance, and reservations.

`owner` and `holder` are separate and may differ for as long as the world
requires — cargo under sail belongs to a merchant house and is held by a ship's
master; grain on deposit belongs to a household and is held by a temple. A
contract moves ownership; loading moves custody. Neither moves the other by
implication.

Rules:

- quantity is never negative; a lot reaching zero is removed at the end of the
  phase that emptied it, and its provenance is folded into the lot that
  received the goods;
- reserved quantity never exceeds quantity;
- owner, holder, and location must each name an entity that exists this turn;
- lots split by conserving quantity and copying provenance; two lots merge only
  when good, quality, owner, holder, and location all match;
- every change passes through the transfer functions in `engine/ownership.py`
  and emits a `Transfer` record — turn, phase, lot, quantity, previous and new
  owner, previous and new holder, reason, and the authority relied on. No
  system constructs or edits a lot directly.

The `Transfer` record is what conservation checking and the causal inspector
read. A system that moves goods without one is a defect even when its
arithmetic balances.

`Asset` uses the same owner/holder/location grammar, adding condition,
capacity, operators, upkeep, and liens.

### 10.9 Obligation clauses

An `Obligation` is authored or generated from an enumerated clause kind. The
kinds are closed; adding one is a specification change:

```text
fixed_quantity     so many units of a good, by a date
share_of_yield     a scaled share of a measured production event
per_head           a quantity scaled by counted people or animals
service_days       labour or military service, in person-days
on_demand          rendered when the holder of the right calls for it
```

A due rule is `(kind, parameters)` over: a named season span, every N
fortnights from a start turn, an absolute date, or a named trigger event.
Status runs `pending -> due -> part_paid -> discharged | defaulted | remitted
| disputed`.

Consequences are recorded as what the parties *believe* follows from default,
as Claims with a holder — not as effects the engine applies automatically. A
creditor acts because it believes it may, and it may be wrong about that.

### 10.10 Tick decomposition

Section 6.1 fixes the causal order of seventeen phases. The kernel implements
it as snapshot, intents, resolution:

`engine/kernel/snapshot.py`
: Produces the read-only opening World for the turn. Phases 3 and 4 read the
  snapshot and nothing else. No settlement may observe another settlement's
  same-turn result.

`engine/kernel/intent.py`
: An `Intent` is a frozen record of actor, kind, payload, the authority relied
  on, and the belief basis it was chosen from. Phase 4 produces intents only.
  Producing an intent changes nothing.

`engine/kernel/resolve.py`
: Phase 5 allocates every exclusive resource — person-days, asset capacity,
  route capacity, transport tonnage — across all claimants at once. The
  allocation rule is stable and documented: claimants sort by obligation
  priority, then authority rank, then entity ID, and are served greedily to
  their stated need. Ties are broken by ID and never by iteration order. A
  settlement's position in any list may not affect what it receives.

Phases 6 onward apply already-chosen intents against granted allocations. Each
phase returns a new immutable World plus events. No phase may read state
written by a later phase in the same turn; a phase needing a later phase's
result is mis-ordered, and the fix is to move it, not to peek.

The existing single-city systems become phase implementations rather than a
parallel path: `land` and `works` under production, `house` under consumption,
`revenue` and `justice` under settlement, `plague` under disease, `relations`
and `appointments` under politics, `institution` under degradation, `mail` and
`archive` under report generation. They keep their arithmetic; they lose the
right to mutate the world in place.

### 10.11 Actor Belief boundary

`belief/` remains the only World-to-player boundary and gains no new job here.
Actor Belief is engine-internal and separate:

`engine/observe.py`
: Turns location, presence, and method into `Observation` records for an
  actor. Observation is bounded by where the actor is and what it can reach.

`engine/believe.py`
: Folds observations, received claims, memory, and interest into that actor's
  Belief. Conflicting claims are retained side by side. A deduction records
  its inputs and never overwrites them.

Actor policy functions take `(actor, actor_belief)` and return intents. They do
not take `World`. This is enforced by signature inspection in the test suite,
not by convention, because it is the one boundary whose accidental crossing
would be invisible in output and fatal to the premise. The physical resolution
functions that apply already-chosen intents are the sole exception, and they
choose nothing.

### 10.12 Save version 14 and the legacy court

The kernel changes what world state means, so the save version becomes 14.
Saves below 14 are refused with a message naming the version found and the
version required. Two world ontologies are not maintained (migration rule 5).

Ugarit's detailed `Court` survives M13.1 as the adapter `legacy_court` under
migration rule 2. It is a converted view over kernel entities, not a second
source of truth: settlement, institutions, and stores are kernel-owned, and
the adapter presents them in the shape the current UI and systems expect. Its
deletion gate is the M13.2 exit — the grain vertical slice is what removes it.
Foreign settlements never touch it. If a foreign settlement needs a mechanism
that only `legacy_court` provides, that mechanism is promoted to the kernel
rather than copied.

---

## 11. Verification

### 11.1 Invariants

Assert in tests and debug builds:

- goods conservation by good, lot, owner transfer, and world total;
- population conservation across cohorts, births, deaths, and migration;
- exclusive person-days and asset capacity;
- no ownership or custody without an existing entity/location;
- no shipment exceeds carrier capacity;
- no contract delivers an unowned or nonexistent lot;
- payment, debt, tax, and tribute balance;
- institution output cannot exceed available capacity and inputs;
- disease transmission requires a modeled contact path;
- every report links to an actor intent and underlying observations;
- every distant act links to authority and an order/policy;
- every actor decision uses only that actor's Belief;
- deterministic replay and stable hashes;
- no float in canonical World;
- no hidden World field in player or model projections.

From the kernel contract (section 10.7-10.12):

- no runtime ID derives from a world-wide counter or from iteration order, and
  the same seed and confirmed actions reproduce every ID byte for byte;
- every quantity change to a lot has a matching `Transfer` record, and the
  records alone reconstruct each lot's history;
- lot reservations never exceed quantity, and owner, holder, and location all
  name entities that exist;
- no phase reads state written by a later phase of the same turn;
- exclusive allocation is unchanged by the order settlements appear in any
  registry — permuting the registries must not change the result;
- actor policy functions do not accept `World`, verified by signature;
- the `legacy_court` adapter holds no state the kernel does not own.

### 11.2 Required causal scenarios

M13 is not complete until automated, reproducible scenarios prove:

1. **Unattended world:** foreign settlements produce, consume, trade, change
   policy, and sometimes fail without player contact.
2. **Drought propagation:** a poor inland harvest raises local need, creates
   quotes and contracts, draws cargo, changes household pressure elsewhere,
   and generates delayed reports.
3. **Tin chain:** source/intermediary disruption changes quotes and shipment
   availability, then reaches the harbour, forge, melt ledger, and formation
   replacement after physical delays.
4. **Harbour decay:** reduced clearance queues cargo, increases loss/cost,
   redirects a merchant, and reduces real duty income.
5. **Exclusive labour:** levying troops or corvée during agricultural work
   reduces that work; no people are counted twice.
6. **Literal order:** a delegate executes the confirmed wording rather than an
   unstated intention, reproducibly and with an audit trail.
7. **Corrupt order:** private benefit changes execution without changing what
   the parser recorded.
8. **Conflicting sources:** two actors observe/report the same event
   differently; the player receives both without truth reconciliation.
9. **Route closure:** journeys wait or reroute according to policy, prices and
   delays change, correspondence follows people, and disease exposure changes.
10. **Political neglect:** ignoring a foreign actor changes its material and
    diplomatic choices; it is not only an esteem countdown.
11. **No zombie continuation:** a polity with no legitimacy, institutions,
    food, or authority changes form, loses control, fragments, submits, or
    ends; it does not run forever as a zeroed record.
12. **No predetermined collapse:** at least one difficult policy family can
    preserve Ugarit to the scenario horizon, and at least one apparently
    competent policy can fail through an explainable cascade.

### 11.3 UX live tests

Script and manually verify:

- Hall matter → evidence → drafted order → preview → confirmation → dispatch;
- Inbox read → compare → answer/delegate → archive → reopen;
- order blocked → dossier → amendment;
- foreign claim aging without screen-open refresh;
- mouse and keyboard parity;
- offline and model-enabled parity of available mechanics;
- compact layout access to every action;
- save/load/autosave and incompatible pre-M13 save message;
- consistent attention cost in Hall, destination, log, and replay.

---

## 12. Milestones

### M0–M12 — Foundation

Implemented foundations are retained where they satisfy this specification.
Passing old tests is necessary but does not waive the M13 invariants.

### M13.0 — Purpose, truthfulness, and a clean foundation

Deliver:

- this unified specification;
- old specifications, status, decisions, and parked plans moved intact to the
  dated documentation archive;
- no archived or duplicate source path;
- objective divine causality removed;
- divination converted from privileged future-reading to fallible forecast;
- save version incremented where world meaning changes;
- institution staffing, head, upkeep, labour exclusivity, and harvest reset
  invariants fixed;
- primary UI access and workflow gaps in section 4.4 fixed;
- data-driven World view;
- a conservation/causal audit harness;
- benchmark command and reference baseline;
- all tests, corpus lint, screen dumps, CLI smoke, Tk live probe, and at least
  one 96-turn balance sweep passing.

Exit gate:

> The current one-city game is internally honest, every existing mechanic is
> operable through the primary UI, the specification has one authority, and it
> is safe to copy the corrected grammar outward.

### M13.1 — World kernel

Deliver:

- Region/Polity/Settlement/Site ontology;
- persistent households/cohorts, organizations, ownership, goods lots, and
  obligations;
- snapshot/intents/global-resolution tick;
- actor-specific Belief;
- causal developer inspector;
- two foreign settlements advancing under the same accounting grammar.

Exit gate:

> With Ugarit idle or removed, the other settlements continue to produce,
> consume, decide, and change.

### M13.2 — Grain vertical slice

Scope:

- Ugarit;
- Ma'hadu;
- one inland supplier;
- one foreign polity;
- grain/seed/fodder;
- one merchant organization;
- one ship or caravan;
- one tribute/tax obligation.

Deliver physical production, household pressure, quotes, contract, loading,
journey, delivery, payment, and reports.

Exit gate:

> A drought or extraction decision creates a complete, conserved,
> source-to-household chain that the developer inspector can explain.

### M13.3 — Trade, logistics, and bronze

Deliver:

- mixed ownership and credit;
- ships, caravans, provisions, capacity, route restrictions, and risk;
- copper/tin/bronze production and exchange;
- physical harbour clearance and duties;
- alternate suppliers and routes;
- quarantine over movement.

Exit gate:

> A route failure propagates into prices, cargo delays, forge throughput, the
> melt ledger, and military replacement, while a costly alternative remains
> possible where the network permits it.

### M13.4 — Agency, envoys, and standing orders

Deliver:

- deterministic actor policies over actor Belief;
- Order and Mission lifecycle;
- semantic order preview;
- envoys and negotiation;
- event-driven correspondence and report bundling;
- execution differences from competence, loyalty, interest, and literalness.

Exit gate:

> Grain can arrive late because a real delegate followed a confirmed standing
> order literally, and every link from wording to consequence is inspectable.

### M13.5 — Interaction and generated institutions

Deliver:

- Hall exception docket;
- common dossiers;
- Orders desk;
- full correspondence workflow;
- operational World layers;
- dynamically arising debts, claims, petitions, and precedents;
- removal of replaced cadence, synthetic economy, and duplicate UI paths.

Exit gate:

> In under one minute a player can answer: What changed? Why do I believe it?
> What have I ordered? Who is acting? What is blocked? What will become due?

### M13.6 — Scale, emergence, and balance

Deliver:

- historically reviewed 34–40-node network;
- performance budgets;
- long-run policy and no-action sweeps;
- paired-seed causal tests;
- economy and political balance;
- state/archive growth controls;
- all section 11 scenarios.

Exit gate:

> The world creates fair, varied, traceable crises without authored crisis
> cadence, and interacting with foreign systems is necessary to preserve the
> local one.

### M14 — Displacement, coalition, and conflict

M14 consumes M13 state:

- household flight and refugees retain origin, skills, property, kin, patrons,
  grievances, and previous refusals;
- raiders require actual people, leaders, food, equipment, ships, intelligence,
  and targets;
- coalitions emerge from aligned needs and histories;
- levies and campaigns consume the same labour, equipment, and logistics as the
  rest of the world;
- raids steal/destroy actual lots and assets and generate further choices;
- diplomacy, settlement, employment, tribute, bribery, division, and force can
  all alter a threat.

Exit gate:

> A coalition and its targets can be explained entirely from previous world
> events and actor choices; no “Sea Peoples” stack spawns on a date.

### M15 — Scenario starts

M15 is authoring and calibration, not another mechanical centre.

Deliver Ugarit, Egypt, Amurru, and Pylos as starting configurations over the
same simulation grammar, with justified capability differences and historical
source registries. New scenario-only mechanics require proof that the common
ontology cannot express the distinction.

Exit gate:

> Each start creates a genuinely different information and authority problem
> without forking the engine.

### M16 — Endings and release

Deliver:

- political discontinuity and scenario-horizon endings;
- continuity evaluation;
- causal epilogue generated from the actual archive and world history;
- tutorials and contextual Help;
- accessibility and compact-layout completion;
- save/replay/checkpoint polish;
- long-form balance and performance passes;
- packaging and release verification.

Exit gate:

> The shipped game supports complete runs, explains their history without
> inventing facts, and remains playable offline. The project is finished.

There is no M17. Any release-blocking polish is an M16 exit requirement.

---

## 13. Parallel development plan

Parallel work is organized around contracts, not around several agents editing
the same central files.

### Ownership rule

One integration owner controls the hot world contracts:

- world schema;
- `engine/state.py`;
- `engine/tick.py`;
- load/save migration;
- action/event/Belief interfaces.

Other agents build new modules and fixtures against reviewed interfaces.
Concurrent edits to the hot files require explicit handoff.

### Wave 1 — M13.0 and interfaces

1. **Integrator:** invariants, save version, ontology RFC, hot-file changes.
2. **Local-systems agent:** staffing, upkeep, exclusive labour, disease and
   divine-causality corrections.
3. **Interaction agent:** M13.0 workflow gaps and synthetic-Belief UI fixtures.
4. **Research/QA agent:** historical registry, conservation fuzzing,
   benchmarks, causal probes.

### Wave 2 — Vertical slice

1. **Integrator:** snapshot/intents/resolution and migration.
2. **Economy/logistics agent:** lots, production, contracts, carriers, routes.
3. **Agency/orders agent:** actor policy, Orders, Missions, envoys.
4. **Information/UX agent:** observations, claims, dossiers, Orders desk.

Integration happens at the end of each thin causal path—grain first, then
bronze—not after four isolated subsystems are “finished.”

### Wave 3 — Scale and adversarial testing

1. Historical/content authoring against frozen schemas.
2. M14 interface/test authoring against M13 entities.
3. Performance and balance sweeps.
4. Red-team agent searching for conservation leaks, omniscience, free labour,
   inert failures, dominant policies, and unexplained state changes.

No agent parallelizes by creating a second economy, tick, Belief projection, or
legacy code tree.

---

## 14. Anti-goals

- No global market screen or universal price.
- No static foreign cities animated by letter cadence.
- No authored crisis whose mechanics do not exist.
- No global RNG, float state, or iteration-order outcomes.
- No LLM arithmetic, policy, facts, or mutation.
- No UI that deliberately misparses an order.
- No actor with access to knowledge it could not obtain.
- No commodity, population, labour, or money sink without a ledger event.
- No free duplicate labour.
- No perfect missing/headless institution fallback.
- No objective divine plague cause or privileged future-reading diviner.
- No collapse meter, scripted invasion date, or mandatory destruction.
- No “Sea Peoples” as an ahistorical unit stack.
- No modern nation-state treatment of regions, courts, cities, and households.
- No exact historical price or population claim without evidence and
  uncertainty.
- No interface-generated knowledge refresh.
- No cadence-spam Inbox.
- No omniscient “correct move” recommendation.
- No source archive inside the runtime tree.
- No dual legacy/new simulation after its named deletion gate.
- No M17.

---

## 15. Definition of finished

The game is good enough to finish when:

- the world remains active and fragile without player attention;
- every major pressure is a traceable interaction among people, goods,
  institutions, information, and obligations;
- foreign trade and politics are necessary, not decorative;
- no single policy trivially solves the network;
- crises are legible after investigation without being announced in advance;
- orders scale through delegation while preserving exact player intent;
- people can obey, misunderstand, exploit, refuse, and report those orders;
- historical claims are sourced and uncertainty is honest;
- religious belief shapes history without becoming secret supernatural
  physics;
- survival, subordination, transformation, and destruction are all possible
  results of the calculation;
- the UI lets a player manage this complexity through exceptions, dossiers,
  orders, and correspondence rather than omniscient micromanagement;
- deterministic replay, conservation, Belief isolation, performance, offline
  play, and complete runs pass their release gates.

When a proposed feature does not strengthen that game, it does not belong.
