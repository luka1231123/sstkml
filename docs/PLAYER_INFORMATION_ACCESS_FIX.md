# Player information access fix

- Status: implemented minimally, subordinate to `SPEC.md`
- Release target: after 0.5.2
- Principle: every fact the court knows is reachable; every unknown is named

## 1. Problem

The game correctly prevents screens from reading omniscient World state, but
it also hides information the ruler should already possess. There are two
failure points:

1. a court-knowable field exists in World but is not projected into Belief;
2. a field exists in Belief but no room, row, dossier, record, or link renders
   it.

The player therefore cannot distinguish “the court does not know” from “the
interface forgot to show it.” This makes quantities feel arbitrary, prevents
planning, and weakens the central information game. Incomplete knowledge is
interesting only when the player can see the boundary of that knowledge.

## 2. Binding access rule

Every simulated data point must be classified as one of four kinds:

| Kind | Player access |
|---|---|
| Court record | Exact, dated, sourced, and always reachable |
| Observation or report | Reachable with value or range, date, source, and confidence |
| Derivation | Reachable with inputs, unit, and short formula or explanation |
| Unobserved truth | Shown as unknown with the reason and a way it may become known |

Only genuinely unobserved truth stays hidden. Examples are a foreign granary
that nobody has reported, a correspondent's private decision before a tablet
arrives, future random draws, the true side of an unheard lawsuit, and the
unseen infection count of a distant city. Debug tools may reveal these; the
player interface may not.

The following are not acceptable:

- omitting a known field because the room has no space;
- showing a number without its unit;
- showing a changed value without its previous value or cause record;
- hiding an order's executor, duration, destination, or ration source;
- replacing an exact court record with an unexplained adjective;
- showing a blank cell when the value is unknown;
- requiring the Command parser to discover information;
- exposing a value in Help or developer inspection but nowhere in play.

## 3. Common fact shape

Do not build a second data model. Add one small presentation shape and reuse it
in projections and typed dossiers:

```python
{"value": 1200, "unit": "qa", "as_of": 14,
 "source": "granary roll", "certainty": "counted"}
```

Rows sharing one source and date may put that metadata on the collection
instead of repeating it. `certainty` has only four player-facing values:
`counted`, `reported`, `estimated`, and `unknown`. An unknown fact also carries
`reason` and, when possible, `learn`:

```python
{"value": None, "certainty": "unknown",
 "reason": "no messenger has returned",
 "learn": "an arrival or a new mission may report this"}
```

Create one renderer for these facts. It prints the human value first and the
source/date second. It must support exact integers, ranges, words, booleans,
identifiers linked to dossiers, and short lists. Rooms may summarize, but
Enter on the summary must open the complete fact set.

## 4. Units and explanations

Every quantity shows its native unit and a useful interpretation. Native units
remain authoritative; interpretations are derived and labelled.

| Quantity | Required display |
|---|---|
| Grain and seed | qa, approximate ration-fortnights, and current obligation coverage |
| Metal | shekels, current institutional demand, and replacement coverage |
| People | heads; households where recorded |
| Labour | person-days, available this fortnight, committed, and remaining |
| Land | authored extent unit, planted share, open share, and seed required |
| Time | absolute due date plus fortnights remaining or overdue |
| Rates | per-thousand value plus plain-language effect on the current base |
| Condition | value out of 1000 plus reported/inspected status |
| Unrest and grievance | value out of 1000 plus band and recent direction |
| Price | good and quantity exchanged, not an unexplained scalar |

Add a compact unit glossary to Help. Every displayed unit links to its glossary
entry. Conversions use current known consumption and population rather than a
fixed flavour sentence.

## 5. Access paths by room

The Hall remains a summary. It must not hold all data. Every Hall value and
exception opens the owning room with the relevant row selected.

### 5.1 Hall

- Show source and date for grain, copper, tin, unrest, and legitimacy.
- Show current value, last value, delta, and the most recent known cause.
- Door counts open the exact filtered rows counted; never a room's default tab.
- Every arrival, visitor, mission, and unresolved order opens its dossier.
- Ending the fortnight previews outstanding deadlines, commitments, unused
  labour, unallocated stores, unread arrivals, and known imminent shortages.
- No warning is created from hidden World truth.

### 5.2 Scribes

Every tablet exposes:

- sender, recipient, copy, seal, scribe, courier, route, dispatch, arrival,
  reply-to record, archive status, and delegation;
- exact received text, structured terms, extracted quantities, due dates,
  protocol reading, and the source of each asserted fact;
- expected reply date and why that expectation was calculated;
- linked promises, claims, reservations, obligations, gifts, proposals, oaths,
  people, places, and later replies;
- a visible Reply action whenever a reply is legally possible, including the
  opening tablet.

If meaning cannot be parsed, show “unresolved wording” and keep the original
text. Never invent a structured meaning merely to fill the panel.

### 5.3 Alu

Overview shows totals and links to their component rows. Each cohort dossier
shows every court-knowable field:

- people, households, origin, ethnicity, status, tenure, representative,
  residence, institution, task, destination, route, arrival, duration,
  official, ration source, and armed state;
- labour per head, available labour, ration per head, ration owed, allowance,
  shortfall, hunger duration, grievance, priority, corvee used, field duty,
  infection observation, recoveries, and known deaths;
- the record or report supplying each value and its date.

Do not expose exact infection where only symptoms or burials are observed. The
dossier must still say that the count is unknown and name the available
evidence.

Each institution dossier shows place, type, head, staff cohort, condition,
inspection state, capacity, believed effective capacity, upkeep, current
shortfall, output, and condition history. Each site shows settlement,
controller, extent, capacity, function, holdings visible to the court, and
linked cohorts and institutions. Each work shows plan, progress, remaining
days, committed labour, materials required, materials spent, season limits,
supervisor, start date, and projected completion under the current allocation.

### 5.4 Trade

- Exchange lists every known good and price, with quote source and date.
- Cargo lists lot, good, quantity, owner, custodian, location, reservation,
  carrier, and destination.
- Routes list every known leg, mode, ordinary duration, seasonal state,
  reported hazard, capacity, last use, last report, and closure authority.
- Movements list carrier, cargo lots and quantities, path, present known
  position, departure, expected arrival, delay, escort, and linked letters.
- Dues show base, rate, expected yield, last yield, arrears, exemptions, and
  affected merchants.
- Unknown foreign stocks and prices appear as unknown, not absent.
- Every foreign demand or offer links to its tablet and Desk response.

### 5.5 Storehouse

- Stores lists every held good, including zero balances when the good has a
  ledger, obligation, reservation, or recent movement.
- Each good dossier shows quantity, unit, owner, custody, location, reserved,
  available, incoming, outgoing, produced, consumed, spoiled, destroyed, and
  history by fortnight.
- Grain also shows ration coverage, seed reserve, next known consumption,
  payroll need, and the arithmetic behind each figure.
- Labour lists every cohort's available, allocated, committed, performed, and
  lost person-days.
- Land shows every estate and field: extent, capacity, planted area, crop
  stage, seed in ground, standing crop, grain harvested, labour need, labour
  assigned, due base, rate, last due, and known weather gauge.
- Reserves and Dues must be real datasets, not alternative summaries of Stores
  and Land.

### 5.6 Muster

Every formation shows strength, believed ready strength, equipment state,
replacement need, task, place, commander, linked cohort, ration source,
mission, and losses. If readiness is only an armourer's estimate, show a range
and the report; do not omit it.

Every levy, detachment, escort, and mission shows the same complete order:
cohort, number, destination, route, start, duration, purpose, rations,
official, authority, current status, and result. Summons also show oath,
caller, required strength, already committed strength, due date, travel time,
and shortfall.

### 5.7 Court

Every person dossier shows known identity, kin, age, life state, health report,
location, faction, office, interests, competence report, loyalty report,
current responsibilities, linked orders, appearances, petitions, advice,
letters, gifts, oaths, succession standing, and history.

Private loyalty and competence remain reports or bands unless an exact court
assessment is actually recorded. A secret agenda is hidden only while no act,
claim, or report has revealed it; known interests and stated intentions remain
accessible.

Office dossiers show authority, holder, vacancy, institutional link, duties,
resources controlled, and appointment history. Justice exposes the complete
heard claim, counterclaim, evidence, wait, parties, precedent, ruling, and
consequence record; hidden case truth never crosses Belief.

### 5.8 Shrine

- Rites show eligibility, date, hours, goods, officiant, institution, purpose,
  prior performances, omissions, and linked records.
- Offerings show goods, quantity, source store, recipient institution, reason,
  date, and the petition, omen, oath, death, or plague record answered.
- Oaths show parties, superior, gods, sworn date, sworn-by person, every clause
  and argument, due state, lapse, dissolution, breach, remedy, and linked
  tablets.
- Obligations show debtor, creditor, authority, beneficiary, quantity, unit,
  destination, due date, status, reservations, performance, default, remedy,
  and source tablet.
- Omens show the question, subject, reported answer, publication state, date,
  and later events the player may compare. They never show divine correctness.

### 5.9 World

Every place dossier shows all received knowledge: name, kind, polity, rank,
map position, known sites, last reported population or range, authority,
court, production, stores, disease, displacement, conflict, fall, and the date
and source of every report. Missing categories explicitly say unknown.

Routes, journeys, courts, news, disease, and displacement each need complete
rows and dossiers. A report can update only the facts it carries; older facts
remain visible with their older dates. Contradictory reports remain side by
side until the court obtains better evidence. Fallen Alu disappear from the
active map but remain reachable through archive records and historical links.

## 6. Cross-room navigation

Every identifier rendered to the player is selectable. Enter opens the typed
dossier; Back returns to the same row and scroll position. Dossiers link both
directions:

- person ↔ office, cohort, order, letter, oath, petition, institution;
- good or lot ↔ store, owner, reservation, movement, obligation, loss;
- place ↔ site, court, route, journey, report, disease, displacement, fall;
- letter ↔ correspondent, route, courier, terms, obligation, reply;
- order ↔ issuer, executor, subject, resources, destination, result;
- event or change ↔ affected objects and source decision.

Add one global Records search through the existing Scribes archive. It searches
known object names, identifiers, tablets, and record titles; it does not search
hidden World fields. Search results open the same dossiers used by rooms.

## 7. Changes and causes

Every mutable dataset keeps enough projected history to answer:

1. what is the current known value;
2. what was the previous known value;
3. when and by how much it changed;
4. which event, order, transfer, consumption, loss, report, or correction
   caused the change;
5. which underlying object records support that explanation.

The fortnight receipt groups these by room. It is not a narrative summary and
does not expose hidden causality. “Unknown cause” is valid when the court sees
the result but has received no explanation.

## 8. Implementation sequence

### Step 1 — make the inventory

Create `belief/catalog.py`, a small explicit table with one row per
player-relevant field:

```text
object.field | visibility | projection path | room | dossier | unit
```

Classify every field in `engine/state.py`, `engine/entity.py`, and the kernel
records. Configuration tables used only by rules do not need player rows unless
the court is supposed to know the rule or price. This table is the deletion
gate for accidental hiding.

### Step 2 — audit both gaps

Create `tools/information_audit.py`. It reports:

- known/catalogued fields with no Belief projection;
- projected fields with no room or dossier consumer;
- values without unit, source, or date where required;
- unknown fields without reason;
- rendered identifiers without an open action;
- duplicate fields owned by more than one room.

Keep this an audit, not a large mirror-test of the game. It exits nonzero on a
missing required path and prints the exact field.

### Step 3 — complete Belief

Fill projection gaps one object family at a time: stores and cohorts, orders
and obligations, people and institutions, letters, then foreign reports.
Projection must never read ahead or flatten a report into truth. Preserve
multiple dated claims when sources disagree.

### Step 4 — complete typed dossiers

Extend the existing object window rather than creating new primary rooms. Add
one compact fact renderer and one dossier composer per existing object family.
Remove raw dictionary fallbacks once all catalogued types render deliberately.

### Step 5 — wire room rows

For each room, make every row open its dossier and make each summary link to
the rows used to calculate it. Preserve selection and geometry. Mouse and
keyboard must invoke the same command.

### Step 6 — add interpretation

Add units, reserve coverage, deadlines, ranges, source/date labels, and change
receipts. Derived figures must use Belief inputs only and expose their short
arithmetic.

### Step 7 — remove accidental secrecy

Delete comments and UI rules that intentionally withhold a court-knowable
mechanical value merely to surprise the player. Surprise should come from
uncertain reports, delayed consequences, conflicts, and other actors—not from
the interface suppressing the ruler's own records.

## 9. Completion checklist

The fix is complete when:

- every catalogued court-known field has a Belief path and a UI path;
- every projected collection has a complete row and typed dossier;
- every displayed quantity has a unit or is explicitly unitless;
- every report has source, date, and certainty;
- every unknown has a reason and, where possible, a discovery path;
- every summary opens its component records;
- every identifier opens the same object from keyboard and mouse;
- every action preview shows all inputs, commitments, delay, and executor;
- every resolved action links to a result or states that no report has arrived;
- no player screen reads World directly;
- the information audit has no findings;
- a player can explain every visible change without using a developer tool.

## 10. Minimal-code boundary

This work adds no new simulation system, primary room, resource, or dashboard.
It reuses Belief, the nine rooms, typed dossiers, Records search, and existing
event history. Prefer one fact renderer, one catalog, and links over bespoke
panels. Do not add authored prose to compensate for absent data.
