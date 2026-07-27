# TUI rework plan

Status: implemented and verified.

Related parked design: [LETTERS_REDESIGN.md](LETTERS_REDESIGN.md).

## Product direction

The windowed game will become a dashboard-led court rather than a collection of
independent reports.

- **The Hall / Home** is the main dashboard. It shows the king, date, remaining
  attention, a compact state of the kingdom, current concerns, recommended next
  steps, the inbox summary, and the routes to every other place.
- **Counsel** is the main ordering interface. The player tells Yabninu what
  should be done in ordinary language. A valid order is carried out immediately;
  an ambiguous order gets a clarification question.
- **The Inbox** is a larger, integrated bronze-age correspondence view.
- **Every visible button-like label is clickable.** Keyboard controls remain
  first-class and perform the same actions.
- **There is no persistent global header.** The complete realm header belongs
  to the Hall. Other places retain their own title and context.
- **Every place has a persistent contextual footer.** It shows only the actions
  available there, and those actions are clickable.

This supersedes the old rule that the interface never says what matters or what
the player might do. Advice must still be based only on Belief: the Hall and
Yabninu cannot reveal hidden simulation truth.

## Hall / Home

Recompose the Hall as a wider dashboard with five stable areas:

1. **Realm header**
   - ruler, kingdom, regnal date;
   - hours remaining and the fortnight's base allowance; (lamp oil thing with ascii art)
   - grain, unrest, legitimacy, and whether the sea is open.
2. **Matters before the king**
   - deterministic concerns derived from known facts;
   - plain-language consequence and recommended next step;
   - clicking a concern opens its evidence or the appropriate ordering context.
3. **Waiting in the Hall**
   - people, couriers, petitioners, and heralds;
   - age/waiting time remains visible;
   - no hidden urgency or hidden facts are used.
4. **Inbox summary**
   - unread count, oldest unread item, and recent arrivals;
   - one click opens the full Inbox.
5. **Places**
   - grouped rather than presented as one flat list:
     correspondence, kingdom, obligations, court, and world.

The concern system will live in a small pure module and return structured
records such as `Concern(title, reason, suggestion, destination)`. Initial
rules will cover unread correspondence, expiring summons, arrears, food trend,
unfilled offices, damaged institutions, neglected works, lapsed oaths,
unresolved petitions, plague, and idle/incorrectly placed troops. Each rule
will have a headless test proving it uses projected knowledge only.

Recommendations navigate or prefill Counsel; they do not silently spend hours
or issue orders when clicked.

## Counsel as the ordering interface

Replace the current list of six canned questions with a conversation and order
console.

The normal flow is:

1. The player types an instruction or question.
2. the present AI model parses it as valid actions in a format
4. Questions receive a spoken answer from Yabninu.
5. The orders actions is viewed by the player and accepted/tweaked
6. A valid order is executed immediately and logged.
7. Yabninu reports what he actually ordered or asks a clarification question.

There is no confirmation dialog for an unambiguous order. For a multi-action
instruction, all actions are preflighted against a temporary world and their
total attention cost before any are committed; the instruction therefore
succeeds as a whole or does nothing.

The parser vocabulary will be audited against every currently playable engine
action. The first implementation must cover allocations and priorities, troop
assignments, harvest labour, corvée, building and repair, gifts, inspections,
oaths, marriage, divination, archive searches, route closures, quarantine,
justice orders, and ending the fortnight. Unsupported or impossible orders
receive a useful in-world explanation rather than failing silently.

The screen will include:

- the conversation history;
- a large always-ready text field;
- hours remaining;
- a few clickable example orders relevant to current concerns;
- a contextual footer for send, revise/clear, leave, and help.

## Clickable text controls

Add interaction metadata beside the existing immutable glyph grid rather than
encoding actions in colour or replacing the testable `Screen` type.

- Introduce an interactive view wrapper containing a `Screen` and rectangular
  hit regions.
- Extend shared furniture such as `keycap` and footer buttons to register a hit
  region with a semantic command.
- Teach the Tk backend to convert a mouse position to a grid cell, show a hand
  cursor over a target, and dispatch the same command used by the keyboard.
- Keep the terminal and ASCII readers working by unwrapping the same `Screen`.
- Add tests for hit-region bounds, disabled controls, mouse/keyboard parity, and
  plain-text legibility.

Clickable controls will look like controls in monochrome as well as colour.
Selected states will use a glyph marker, not colour alone.

## Bronze-age Inbox

Replace the small Stack window with a longer correspondence workspace:

- a scrollable/selectable list of tablets;
- unread/read state, sender, subject, arrival, and time waiting;
- the selected tablet shown in full in the same window;
- clickable rows and keyboard movement;
- filters for unread and all;
- explicit attention cost before opening an unread tablet;
- contextual footer actions.

The Inbox will not redesign outgoing correspondence in this pass. The current
reply path may remain temporarily available, but it will not be expanded or
made central. The intended replacement is parked in `LETTERS_REDESIGN.md`.

## Contextual footer

Create one shared footer component used by every place.

- It is pinned to the bottom row.
- Each item shows its key and complete action label.
- Every enabled item is clickable.
- Disabled actions remain visible and state why when space permits.
- It never advertises an action the current controller will ignore.
- Escape/back and Help are placed consistently.

This pass also fixes existing contract mismatches, including the invisible
tablet answer shortcut, Counsel's inactive Enter instruction, the Altar's
incorrect stated cost, colour-only Desk selection, and raw internal IDs in
player-facing text.

## Delivery order

### Phase 1 — Interaction foundation

Add interactive views, hit regions, mouse dispatch, the shared footer, and
tests. Convert the existing Hall and one simple document screen to prove the
path without rewriting every screen at once.

### Phase 2 — Hall dashboard

Add the pure concern/advice projection, build the new Hall layout, group its
destinations, and connect concerns to evidence or a prefilled Counsel order.

### Phase 3 — Counsel ordering

Unify question and order routing, expand the validated action vocabulary,
preflight multi-action instructions, execute successful orders, and provide
in-world outcomes and clarification.

### Phase 4 — Inbox

Build the longer list-and-reader workspace, scrolling/selection, filters,
clickable tablets, and attention-cost handling. Preserve the existing outgoing
reply implementation without redesigning it.

### Phase 5 — Convert remaining places

Move all screens to the shared contextual footer and clickable controls. Remove
dead advertised keys, normalize player-facing names, and retain keyboard parity.

### Phase 6 — Verification and tuning

- Read every state through `tools/screens.py` in ASCII mode.
- Add scripted interaction tests for Hall → concern → Counsel → executed order.
- Test mouse and keyboard paths for identical actions and costs.
- Verify no advisory rule reads hidden World fields.
- Run the full test suite and corpus lint.
- Play several fortnights at 80-column and normal window sizes to tune density,
  truncation, and the number of simultaneous concerns.

## Completion criteria

The rework is complete when:

- a new player can identify a concern and a plausible response from the Hall;
- every destination and footer action can be activated by mouse or keyboard;
- ordinary-language orders in Counsel reach all major gameplay systems;
- ambiguous or impossible orders explain what is needed without mutating state;
- Inbox triage and tablet reading happen within one coherent window;
- ASCII output communicates every enabled, disabled, and selected state;
- engine determinism, replay, CLI play, and existing saves remain intact.

## Implementation record

Completed in this pass:

- the Hall is a 104-column dashboard backed by deterministic, Belief-only
  concerns and recommendations;
- Counsel accepts ordinary-language questions and orders, preflights compound
  orders, and commits them atomically;
- the 108-column Inbox combines correspondence triage and reading;
- interactive screens carry hit regions beside the glyph grid, so mouse,
  keyboard, terminal, and ASCII output share one composition;
- contextual, clickable footers and visible selection markers are used across
  the existing places;
- Help is now the Palace Tutor: a free conversational agent whose answers
  retrieve from an exhaustive command corpus before optional model phrasing;
- the outgoing-letter redesign remains deliberately parked in
  `LETTERS_REDESIGN.md`.
