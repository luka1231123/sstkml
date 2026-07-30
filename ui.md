# SAY TO THE KING, MY LORD
## Windowed UI/UX rework specification — “The Palace Desktop”

- Status: proposed implementation specification
- Revision: 2026-07-28
- Scope: primary windowed game; terminal play remains supported
- Relationship to `SPEC.md`: this refines sections 4.4, 8, 11.3, M13.0, and
  M13.5. It does not weaken determinism, the World/Belief boundary, or the rule
  that models never decide the world.

---

## 1. Decision

Do not give the current interface another cosmetic pass. Recompose it as a
compact, persistent, multi-window information workspace with a coherent
1990s text-mode visual language.

Keep:

- real operating-system windows;
- the shared character-cell renderer;
- keyboard and mouse parity;
- the amber/clay/lapis palette, reverse-video bars, box drawing, and
  pure-ASCII fallback;
- the City screen's combination of stateful ASCII art, dense comparison, and
  direct drill-down;
- the rule that the player sees Belief rather than hidden World state.

Change:

- default typography from 14-point to 11-point monospace, with immediate,
  persistent font scaling;
- fixed compositions into resizable responsive layouts;
- large single-purpose reports into compact list/detail/action workbenches;
- Help from a 100 × 38 AI conversation into a roughly 52 × 20 deterministic
  field manual;
- Counsel from a 92 × 36 blocking-feeling chat into a compact order/advice
  window with immediate deterministic output;
- Counsel as the only practical route to many mechanics into direct controls
  on the screen where the relevant evidence is visible;
- silent refusals into specific inline explanations;
- unmanaged overlapping windows into remembered placement, useful tiling, and
  a window switcher;
- routine model calls into explicit, rare, cancellable background prose work.

The target is not a modern dashboard wearing ASCII. It is a good information
manager from 1993 that understands the mouse: fast, terse, inspectable,
keyboard-friendly, full of documents and ledgers, and attractive because every
cell has a purpose.

---

## 2. Goals and non-goals

### Goals

1. Help, a tablet, a ledger, and the Hall can remain visible together.
2. Information and action live together: troops can be assigned in Muster,
   rations changed in Roll, and routes closed from World/Health.
3. Screens are dense but legible. Empty space is intentional.
4. Most meaning is prose, tables, ledgers, timelines, and source annotations.
   ASCII art establishes place and, where possible, encodes state.
5. The player never has to guess whether wording, cost, target, or capability
   caused an action to fail.
6. Every implemented mechanic has a complete direct-control path. Typed
   commands are an additional power-user path.
7. The complete game is instant and usable with AI disabled or unavailable.
8. Better usability never becomes omniscience; claims retain source and age.
9. Windowed and terminal play share action meanings, costs, validation, names,
   and help text.

### Non-goals

- No single full-screen web-style dashboard.
- No icons, cards, radial menus, tooltips, or giant headings replacing text.
- Do not copy Dwarf Fortress's historical inconsistencies or Rule the Waves
  3's hidden right-click dependence.
- No animation for its own sake.
- No hidden truth, privileged freshness, correct-answer advice, or exact
  disease compartments.
- No model dependency for commands, Help, NPC policy, replay, or readable
  prose.
- No attention cost for selecting, sorting, filtering, moving windows,
  correcting syntax, or recovering from an interface error.

---

## 3. Current-state audit

The audit inspected the Tk controller, screen composers, hit regions, help
corpus, engine action union, text dumps for every screen, and a live windowed
run with AI disabled. The tree was under active M13 development, so this
document defines stable product contracts rather than preserving transient
line numbers.

### Measured window problem

The current backend uses a fixed 14-point font and fixed cell dimensions. On a
1512 × 982 display:

| Window | Cells | Approximate outer size |
|---|---:|---:|
| Hall | 104 × 36 | 1264 × 804 px |
| Help | 100 × 38 | 1216 × 848 px |
| Inbox | 108 × 36 | 1312 × 804 px |
| City | 96 × 36 | 1168 × 804 px |
| Stores | 62 × 22 | 760 × 496 px |

Pixel values vary by platform, but the relationship is decisive: Help covers
about 80% of the display width and 86% of its height. A multi-window
architecture rendered at replacement-screen sizes is functionally
single-window.

At 11 points, a 92 × 34 Hall measured about 844 × 624 px and a 52 × 20 Help
window about 484 × 372 px. Both fit with useful context still visible. This is
the target default density, not a hard accessibility limit.

### What works

City is the visual benchmark:

- it is immediately recognizable as a place;
- its skyline represents the institutions below;
- numbered buildings connect art, list, and detail;
- condition, keeper, and work share one screen;
- it leads to inspection, repair, and Works;
- its decoration reinforces information.

World, Desk, Justice, Altar, and the authored portraits also contain strong
visual material. Inbox's split list/reader and the shared clickable footer are
sound beginnings.

### Systemic problems

1. Fixed size defeats windowing; major screens open huge and near one origin.
2. Font scale, geometry memory, compact layouts, tiling, and window switching
   are absent.
3. Help and Counsel reserve many blank rows around portraits and conversation.
4. Stores, Roll, Land, Muster, Oaths, Relations, and several House/Altar
   decisions are read-only while Counsel is their practical action route.
5. Help, visible keys, controller handling, and parser grammar are separately
   authored and have already drifted.
6. The default local model is `qwen3:14b`; parser, Help, and Counsel permit
   waits of 8/30/45 seconds. In-progress threading work avoids freezing Tk,
   but there is still no small-model product policy, reliable busy marker,
   cancellation, request ordering, or duplicate-submit guard.
7. Help solves a simple indexed-reference problem with a large conversation.
8. Several engine refusals or insufficient-attention paths are silent or
   report only in Hall behind the active window.
9. Many collections truncate fixed subsets rather than scroll.
10. Mouse and keyboard commands are not fully equivalent; literal range
    labels and mismatched semantic commands can be inert.
11. Source and freshness are not consistently shown even though fallible
    information is the central mechanic.
12. Correspondence controls landed during this audit, including Delegate,
    Compare, Archive, and Outbox. They remain screen-private additions rather
    than a shared action/help/order contract, and conversation/receipt state
    still needs the persistent workspace specified below.
13. There is no persistent Orders workbench despite the order-heavy design.
14. Save/load/session state and attention need one coherent visible workflow.
15. Hall's unattributed `Do:` lines and repeated Counsel prompts make the
    adviser feel like the decision-maker.

---

## 4. Lessons from comparable interfaces

These are inputs, not literal templates.

| Reference | Observation | Decision here |
|---|---|---|
| [Dwarf Fortress Classic controls](https://dwarffortresswiki.org/index.php/DF2014%3AControls) | Context commands are printed on the current screen and arrows expose more options. | Keep contextual hotkeys, show the current mode, and never require memorization. |
| [Dwarf Fortress display settings](https://dwarffortresswiki.org/index.php/Settings) | Windowed mode can be resizable and players can choose grid dimensions/interface scale. | Font scale and cell count are first-class settings; resize recomposes. |
| [DFHack command launcher](https://docs.dfhack.org/en/stable/docs/tools/gui/launcher.html) | Text commands can have autocomplete, context help, output, and history without AI. | Build a deterministic command palette from the action registry. |
| [DFHack manipulator](https://docs.dfhack.org/en/stable/docs/tools/gui/manipulator.html) | Spreadsheet-like search, sort, filter, and assignments suit a deep simulation. | Management screens use dense tables, stable selection, and batch actions. |
| [Rule the Waves 3 official manual](https://ftp.matrixgames.com/pub/RuletheWaves3/RuleTheWaves3ManualPatch2026.pdf), pp. 14, 47–49, 79–86 | Dense map, list, construction, order-of-battle, log, report, and objective views cross-link; selection stays actionable and common operations have keyboard, menu, and map routes. | Use persistent workbenches, click-to-locate operational logs, and batch selection, but keep actions visible rather than right-click-only. |
| [Apple window guidance](https://developer.apple.com/design/human-interface-guidelines/windows) | Auxiliary windows preserve context, but too many create clutter; they should adapt and remember placement. | Open windows for cross-reference, reuse workbenches, and remember geometry. |
| [Microsoft window guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/win-window-mgt) | Resizable windows avoid truncated data; oversized secondary windows should fit the monitor. | All substantive windows are resizable and initially fit the work area. |
| [Microsoft dialog guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/win-dialog-box) | Dialogs interrupt flow; modeless tools suit frequent ongoing tasks. | Help, Counsel, ledgers, dossiers, and previews are modeless. |
| [Emily Short on parser UX](https://emshort.blog/2010/06/10/parser-discussion-redux/) and [Inform disambiguation](https://www.inform-fiction.org/manual/html/s33.html) | “Guess the verb” obscures whether wording or capability failed; good parsers ask focused questions. | Errors identify the unknown verb, target, value, or missing choice and show legal alternatives. |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Text must scale without loss of content/function; contrast and keyboard operation cannot be decorative afterthoughts. | Smaller default type is paired with 9–20 point scaling, reflow, colour-independent states, and complete keyboard paths. |
| [Apple progress guidance](https://developer.apple.com/design/human-interface-guidelines/progress-indicators) | Long work must not look frozen and should be cancellable when possible. | Optional model work is background work with textual status and Cancel. |

The synthesis: preserve mature keyboard speed and information density, add
visible mouse directness, and use real windows only where keeping context
visible has strategic value.

---

## 5. Experience model: the palace desktop

### Window roles

1. **Anchor — Hall.** One persistent home window. Closing it requests exit.
2. **Workbenches.** One instance each of Inbox, Orders, City, Works, Roll,
   Muster, Archive, World, Relations, and Health. Reopening raises the existing
   window and preserves selection, filters, scroll, and geometry.
3. **Documents/dossiers.** Multiple tablets, people, institutions, routes,
   obligations, projects, and places can remain open, keyed by entity ID.
4. **Utilities.** Help, command palette, Settings, Files, and Window Switcher
   are compact, modeless, and single-instance.
5. **Moment window.** Fortnight Chronicle receives focus when time advances
   but does not disable or hide Hall.

### Investigation loop

```text
notice a matter
  -> inspect its source
  -> compare it with a ledger, dossier, or competing claim
  -> choose a direct action or draft an order
  -> see exact target, cost, delegate, and conflict
  -> confirm only when persistence or irreversibility warrants it
  -> keep evidence and resulting order visible
```

Opening, selecting, sorting, filtering, comparing, and moving windows are free.
Only simulated acts consume attention.

### Default workspace

Place Hall upper-left with room for a compact utility/document on the right.
Fill free screen rectangles before covering the focused source. Reuse an
existing workbench rather than create duplicates.

```text
┌──────────── HALL · 92 × 34 ────────────┐  ┌──── HELP · 52 × 20 ────┐
│ matters, waiting court, quick ledgers   │  │ context / search / keys │
│ and navigation                         │  │ exact syntax and costs   │
│                                        │  └─────────────────────────┘
│                                        │  ┌──── selected tablet ────┐
└────────────────────────────────────────┘  │ source kept for compare  │
                                            └─────────────────────────┘
```

---

## 6. Window and typography contract

### Typography

- Default: **11-point** monospace.
- Range: **9–20 points**, one-point steps.
- `Cmd/Ctrl +`, `Cmd/Ctrl -`, and `Cmd/Ctrl 0` enlarge, reduce, and restore.
- Persist font, size, palette, pure-ASCII preference, and window geometry.
- Prefer a crisp narrow CP437-capable face with distinct `0/O`, `1/l/I`,
  `5/S`, punctuation, and box drawing; retain system-monospace fallbacks.
- Recompose cells at every size; do not scale a screen bitmap.
- Every colour-coded state also has a glyph or word.
- Target at least 4.5:1 contrast for ordinary text and 3:1 for meaningful
  focus/control boundaries in every built-in palette.

### Defaults and minimums

| Class | Default | Minimum | Examples |
|---|---:|---:|---|
| Anchor | 92 × 34 | 72 × 26 | Hall |
| Wide workbench | 88 × 30 | 66 × 22 | Inbox, Orders, City, World |
| Ledger workbench | 78 × 27 | 58 × 20 | Roll, Land, Muster, Works |
| Document/dossier | 62 × 25 | 46 × 18 | Tablet, person, institution |
| Compact utility | 52 × 20 | 40 × 15 | Help, Files, Settings |
| Command palette | 68 × 15 | 48 × 11 | typed commands |

City may default to 96 columns and Inbox to 90 where space allows. No initial
auxiliary window exceeds 80% of usable monitor width or height unless restoring
the player's saved geometry.

### Responsive tiers

| Tier | Width | Behaviour |
|---|---:|---|
| Wide | 88+ | list, detail, and context/action rail coexist |
| Standard | 68–87 | list/detail split; actions at bottom |
| Compact | 52–67 | panes stack or switch with Tab; art shrinks |
| Minimum | 40–51 utility, 46–51 document | one pane at a time; actions remain reachable |

Height bands: 28+ full useful art/history; 20–27 reduced art; 15–19 no
decorative art and scrollable content. Prevent shrinking below the class
minimum instead of clipping.

Remove on contraction in this order: decorative sky/borders/shadows/portraits;
redundant prose; lower-priority columns moved into detail; optional history
length. Never remove selection, provenance, cost, enabled actions, scroll
position, or focused input.

### Placement and persistence

- Open next to the source if a free rectangle exists.
- Never fully cover the selected source row/document.
- Reopening raises an existing workbench without resetting state.
- Entity windows are keyed by ID; explicit **Open another copy** permits a
  duplicate.
- Remember geometry, monitor, selection, filter, sort, and scroll. Clamp
  restored windows to available monitors.
- `F8` tiles; `Shift+F8` cascades; `Cmd/Ctrl+Tab` cycles; `F6` opens Window
  Switcher; `F2` raises Hall.
- Hall owns the session. Closing it uses the visible Save/Exit flow.

### Coexistence tests

At default font:

- Hall and Help are fully visible together at 1440 × 900.
- Tablet and Stores are fully visible together at 1366 × 768.
- Inbox and detached tablet are readable together at 1440 × 900.
- City and institution detail are readable together at 1440 × 900.
- At 200% type, every action remains reachable through reflow, pane switching,
  or scrolling.

---

## 7. Visual language

Aim for a coherent 1991–1995 text-mode application: native OS chrome outside;
reverse-video title/status fields, compact tabs, box rules, ledger rows,
selection cursors, shaded meters, and visible keycaps inside. Avoid floating
cards, glossy widgets, hamburger menus, toast stacks, and oversized headings.

Use setting-appropriate words for content and plain software terms for
operation. The **Tablet House** may still use **Search**, **Save**,
**Settings**, and **Close**.

### Symbols

| Glyph | ASCII | Meaning |
|---|---|---|
| `>` | `>` | selection |
| `*` | `*` | unread/new |
| `!` | `!` | known block, breach, deadline, failure |
| `?` | `?` | unknown/unresolved |
| `●` | `*` | observation under 3 fortnights old |
| `○` | `o` | observation 3–8 fortnights old |
| `·` | `.` | observation older than 8 fortnights |
| `×` | `x` | unavailable, followed by reason |
| `+` | `+` | queued/draft/change |
| `✓` | `v` | satisfied/delivered/confirmed |

Urgency is not truth. An urgent claim can still be stale or interested.

### Art budget

- Wide anchor/workbench: at most 30% of body rows.
- Ledger workbench: at most 20%.
- Document/dossier: at most 20%.
- Help, Files, Settings, command palette: no art or one tiny emblem.
- Compact tier: stateful art at most 15%; decorative art removed.

Prefer stateful art: City buildings decay/scaffold; Works shows active
construction; Stores shows filled/spoiled vessels; Land shows water/season;
Muster shows banners/empty ranks; World shows routes/freshness; House uses a
family tree; Oaths show broken seals.

Portraits identify speakers, but a ten-row portrait must not create a mostly
blank 36-row chat. Use five or six rows, collapsing to name/seal in compact
tiers.

### Density

- At least 70% of standard workbench body rows contain useful information,
  controls, or stateful art.
- No more than two consecutive empty body rows except paragraph spacing.
- Prose wraps; IDs and numeric columns do not.
- Critical numbers remain complete or move to detail; never misleadingly clip.
- Every collection shows `first–last / total`, a scrollbar, or both.
- Headers remain stable while bodies scroll.

---

## 8. Universal interaction grammar

### Mouse

- Single click selects; it never mutates state or spends hours.
- Double click/Enter opens or inspects.
- Click headers to sort; Shift-click and Cmd/Ctrl-click multi-select where
  batch actions are legal.
- Right-click may mirror actions but is never the sole path.
- Hover writes a plain explanation in the status bar, not a delayed tooltip.
- The wheel scrolls the pane under the pointer.
- Selecting/copying text does not activate a hit region.

### Keyboard

| Key | Meaning |
|---|---|
| `F1` or `?` | context Help |
| `F2` | Hall |
| `F3` | Inbox |
| `F4` | Orders |
| `F6` | Window Switcher |
| `F8` / `Shift+F8` | tile / cascade |
| `Cmd/Ctrl+Tab` | next game window |
| `:` or backtick | command palette |
| `/` | local filter/search |
| arrows, PgUp/PgDn, Home/End | navigate collections |
| `Tab/Shift+Tab` | next/previous pane or field |
| `Enter` | open/inspect/accept focused non-destructive action |
| `Space` | toggle multi-selection; Hall advances only with no input/list mode |
| `Esc` | cancel inline mode, then close auxiliary window |
| `Cmd/Ctrl+S` | save |
| `Cmd/Ctrl+O` | Files/load |
| `Cmd/Ctrl+,` | Settings |
| `Cmd/Ctrl+Q` | Save/Exit |

Context mnemonics remain printed. Active text input always wins over a
mnemonic; typing `q` in a letter never quits.

### Workbench grammar

```text
list/map -> stable selection -> detail/evidence -> visible actions
```

- Every workbench has five recognizable regions when space permits:
  primary list/map/art, persistent status, selected inspector, event/order
  ledger, and contextual command strip. Responsive tiers may stack or switch
  them, but do not change their meaning.
- Selection appears in both list and detail.
- Filters keep selection if it remains.
- Actions do not jump selection unless the entity leaves the workflow.
- Bottom one or two rows show complete labels and attention costs:
  `[H] Hear (1h)`.
- Strategically meaningful disabled actions remain visible with a reason:
  `× Read — needs 2h; 1h remains`.
- If actions overflow, **More…** opens a compact list but never hides the
  primary action.

### Confirmation

Routine reversible bookkeeping uses immediate commit plus undo where safe.
Persistent/delegated orders, letters, marriage, heir changes, work
abandonment, verdicts, quarantine changes, ending with drafts, save overwrite,
and unsaved exit use an inline semantic preview. It names target, quantity,
place, delegate, cost, known conflict, and irreversible effect. Parsed prose
never executes on its first Enter.

### Feedback

Every attempt produces a preview, a specific success with a result link, or a
specific refusal with the missing prerequisite and next route:

```text
Cannot read: costs 2h; 1h remains.
Cannot begin quay: 156 copper required; 42 uncommitted.
“ma hadu” matches a place and a garrison. Choose:
  [1] Ma'hadu harbour  [2] Ma'hadu garrison
```

Never use an unchanged screen, generic beep, or “say that another way” when the
interface can identify the missing field.

---

## 9. Information grammar

### Claims, not omniscient values

Every strategic value outside an immediately inspected local object has:

```text
value/statement
source actor, document, or inspection
observed date
received date
freshness
confidence only when the court can justify one
conflicts
```

A compact table can show freshness glyph plus source abbreviation; selected
detail shows the full tuple. “Current” means current in Belief, not World.

```text
grain       7,573p 20qa   ▼3,025   ● own count, Nisanu II
Ma'hadu     route shut              ○ harbour master, observed 3 fn ago
plague      ?                       · merchant; conflicts with physician
```

Opening a screen never refreshes a claim. Inspection or new reporting does.

### Common dossier

People, groups, institutions, settlements, routes, projects, formations,
shipments, contracts, obligations, orders, and cases share:

1. identity, aliases, type;
2. last-known location/status;
3. claims with source and age;
4. conflicts;
5. relationships and obligations;
6. related documents/history;
7. orders, blocks, deadlines;
8. legal actions.

Type-specific panes may vary, but header, provenance, links, and action
contract do not. Links raise another dossier without closing the source.

### Tables and cross-reference

- Column widths derive from current cells and content.
- Numbers align right with visible units.
- Stable IDs stay out of ordinary display; detail/autocomplete/developer mode
  may expose them.
- Sort and filter state are visible.
- Batch-capable tables support multi-selection.
- Changes use signed deltas and selective 12/24-fortnight sparklines.
- Each workbench can pin four documents/entities to a tray with Open, Compare,
  and Remove.
- Compare aligns value, source, observation date, and received date; it never
  synthesizes a truth verdict.

### Attention

Every action preview reads the controller's current `hours remaining / base`,
not a stale turn-start projection. Costs live in one action registry consumed
by composers, controller, Help, command palette, CLI, and tests.

---

## 10. Deterministic command palette

The text-adventure feeling comes from a capable text interface, not from
waiting for a large model.

Press `:` or backtick anywhere:

```text
┌─ COMMAND ─────────────────────────────────────────────────────┐
│ > assign chariotry to campa_                                 │
│ assign <formation> to <task> [at <place>]                    │
│   formation: chariotry     task: campaign                    │
│ > place: Carchemish        cost: 1h                          │
│ Tab complete  ↑ history  F1 help  Enter preview  Esc         │
└──────────────────────────────────────────────────────────────┘
```

Provide:

- legal verbs/synonyms and entity completion;
- parameter prompts, units, and live validation;
- exact preview before commit;
- command history and reverse search;
- examples and context help;
- clickable suggestions and full keyboard operation;
- explicit current selection, so `repair this` cannot refer invisibly.

Rules:

1. Closed action grammar only.
2. Resolve legal visible affordances from Belief only.
3. Accept common synonyms and optional articles.
4. Never silently choose among matches.
5. Point to the incomplete/unknown part and offer legal completions.
6. Preview structured meaning before mutation.
7. Replay stores structured action; history may retain original prose.
8. Direct controls, palette, terminal commands, and Help derive from the same
   `ActionDescriptor`.

If deterministic parsing fails, offer **Edit**, **Show examples**, and explicit
**Ask interpreter…**. A small model may asynchronously propose a draft, but
the normal validator, disambiguation, preview, and confirmation still apply.
Model output is never an action.

---

## 11. Help rework

Remove the Palace Tutor conversation from Help. Help is software documentation:
correct, fast, compact, and easy to keep beside play.

- Default 52 × 20; minimum 40 × 15.
- Modeless, resizable, geometry-persistent.
- `F1`/`?` raises it from any screen and sets current screen/entity/control
  context.
- No large portrait, model call, thinking state, or attention cost.

```text
┌─ FIELD MANUAL · CITY ───────────────────────────┐
│ Search: repair_                                 │
├─────────────────┬───────────────────────────────┤
│ CURRENT SCREEN  │ REPAIR AN INSTITUTION         │
│ > inspect       │ Select a building in City.    │
│   repair        │ [R] Repair opens an order     │
│   appoint       │ preview. Cost: 1h.            │
│   works         │ Command: repair <institution> │
│ ALL TOPICS      │ Example: repair tablet house  │
│   correspondence│ Related: Works, Appointments  │
├─────────────────┴───────────────────────────────┤
│ ↑↓ topic  Enter follow  / search  Esc close     │
└─────────────────────────────────────────────────┘
```

Content comes from screen/action registries:

- current controls and direct click path;
- exact syntax, cost, prerequisites, and current-name examples;
- what data means without strategic prescription;
- links to related windows;
- complete searchable action index;
- first-fortnight tutorial transcript.

Incremental deterministic search responds within 50 ms. Tests fail when an
enabled action/key/click path/verb lacks Help. Help answers “How do I assign
troops?” Strategic “Should I?” advice belongs to a named adviser.

---

## 12. Counsel rework

Counsel is a compact place to ask a person, inspect a draft order, and receive
attributed advice. It is not a universal control surface or giant chat client.

- Default 64 × 22; minimum 50 × 17.
- Five/six-row portrait only when space permits.
- Conversation uses available body instead of reserved blank rows.
- Bottom always has ready input, state/cost, and actions.
- Answers link to cited documents/dossiers.

Three input kinds:

1. **Known factual question:** immediate deterministic answer from adviser
   Belief, with source/uncertainty.
2. **Order:** deterministic grammar produces semantic preview; voice cannot
   change structured meaning.
3. **Open advice:** immediate short rule/authored answer; optional explicit
   **Elaborate** may request model prose.

Advice is a small attributed card:

```text
YABNINU'S VIEW
“The oldest petition is becoming a public insult.”
Basis: petition register, observed this morning
Uncertainty: neither side heard
[Open case] [Draft: hear case] [Dismiss]
```

Advice is generated at most once at the start of a fortnight, on explicit
request, or when a materially new known exception crosses a deterministic
threshold. Never on screen open, selection, or repaint.

If **Elaborate** or **Ask interpreter** invokes a model:

- immediate fallback stays visible;
- show `Yabninu is composing… [Cancel]`;
- every other window remains usable;
- only the requesting card is busy;
- completion never steals focus;
- failure retains fallback and states no longer answer was produced;
- repeated Enter cannot queue duplicates;
- stale/out-of-order results are discarded by request ID.

---

## 13. Hall and shared work surfaces

### Hall

**Purpose:** “What changed, what is waiting, what is due, and where do I go?”
It is an exception docket and physical audience, not an omniscient optimizer.

**Default:** 92 × 34. **Minimum:** 72 × 26.

```text
┌─ THE HALL · AMMURAPI · Nisanu II · 10/10h · sea SHUT · saved 09:14 ─────┐
│ MATTERS BEFORE THE KING                         │ QUICK LEDGERS          │
│ >! Judgement waiting 5 fn      petitioner ●    │ grain 7,573p ▼3,025   │
│  * Five unread tablets         oldest 4 fn     │ unrest 0 · standing 700│
│  ! Two offices vacant          city register ● │ inbox 5 unread          │
│  ○ Granary claim falling       scribe, 1 fn    │ orders 2 active / 1 !   │
│ SELECTED: Boundary petition · Ashiranu          ├─────────────────────────┤
│ Raised 5 fn ago. Neither party heard.           │ OPEN WINDOWS            │
│ [O] Open [H] Hear (1h) [D] Delegate [P] Pin    │ Hall · Inbox · Tablet   │
├─ WAITING IN THE HALL ───────────────────────────┼─ PLACES ────────────────┤
│ Ashiranu · boundary claim · 5 fn                │ Inbox Orders Counsel    │
│ courier from Carchemish · unread, new           │ Stores Roll Land City   │
│ 1–7 / 7                                         │ Muster Oaths House ...  │
├─────────────────────────────────────────────────┴─────────────────────────┤
│ Enter open  P pin  F defer  : command  Space end fortnight              │
└───────────────────────────────────────────────────────────────────────────┘
```

- Matters show source/freshness plus age/deadline.
- Selection expands evidence and actions without leaving Hall.
- Advice is quoted and attributed (`Yabninu: “I would hear them.”`), never an
  unattributed `Do:`.
- Click selects; double-click/**Open** opens evidence. Recommendations may
  prefill a draft but never execute.
- Waiting entries link to petition, tablet, dossier, or summons.
- Quick ledgers are known indicators and open their workbench.
- Space advances only when Hall has focus and no input, list selection mode,
  or preview is active.
- Ending opens an inline summary of unspent hours, urgent matters, drafts, and
  pending previews; the player may still proceed.

### Orders workbench

**Purpose:** manage every draft, confirmed order, mission, standing order, and
execution exception. **Default:** 88 × 30. **Minimum:** 66 × 22.

Tabs: Draft / Active / Blocked / Completed / All. Table: status, subject,
delegate, destination, last report, next review. Detail: trigger, bounds,
quantity, budget, authority, dispatch/receipt, execution, reports. Actions:
confirm, amend, revoke, duplicate, contact delegate, open evidence/dossiers.

This is the authoritative history of player intent. Counsel and direct screens
create drafts here; they do not keep separate order histories.

### Dossier

**Purpose:** common persistent inspection for any entity. **Default:** 62 ×
25. **Minimum:** 46 × 18. Stable tabs: Summary, Claims, Relations, Documents,
Orders, History. Foreign dossiers remain last-known; opening never refreshes.

### Window Switcher

**Purpose:** manage the desktop. **Default:** 42 × 17.

```text
> 1 Hall
  2 Inbox · 5 unread
  3 Tablet · Carchemish · unsent reply
  4 Stores · grain selected
  5 Institution · tablet house
```

Enter focuses; `X` closes auxiliary; `T` tiles; `C` cascades. Dirty drafts
require inline Save/Discard/Cancel.

---

## 14. Correspondence screens

### Inbox

**Purpose:** triage, read, compare, answer, delegate, and archive mail without
losing selection. **Default:** 90 × 30. **Minimum:** 66 × 22.

Left: 32–36-column scrollable list. Right: selected metadata, body/unread cost,
related items, actions. Tabs: Unread, Needs action, Delegated, All, Archive,
Outbox. Filters: sender, subject, age, status.

Rows show unread/urgent glyph, sender, subject, age, and response state.
Reading never makes the selected row vanish. Under an Unread filter, retain it
as a dim `just read` row until selection moves.

Actions:

- Read (2h), Open detached;
- Answer, Delegate request, Acknowledge;
- Compare, Conversation, Sender dossier;
- Pin, Archive/Restore.

Reading shows the body in place. Answer raises Desk while Inbox remains.
Delegate creates a structured draft linked to the tablet.

### Tablet

**Purpose:** persistent primary-source reading. **Default:** 60 × 25.
**Minimum:** 46 × 18.

Header includes sender/seal, sender date, observed/sent/received dates, and
read/answer/delegation/archive status. Body scrolls with position. A compact
facts block lists asserted values and related known claims, never hidden truth.
Actions mirror Inbox. Replace the current orphaned standalone-letter route with
this canonical document.

### Desk

**Purpose:** compose an exact reply while its source remains visible.
**Default:** 66 × 28. **Minimum:** 52 × 20.

Fields: recipient/thread, intent, subject, editable body, protocol checklist,
source link, Outbox status. Support cursor movement, selection, undo/redo,
scroll, immediate authored formulae, Save draft, Compare, Validate, Seal/send
(2h preview), and Discard.

No model is required for edit/grade/preview/send. Optional **Embellish**
produces an asynchronous side-by-side alternative and never replaces text
without acceptance.

### Outbox/conversation

Outbox is an Inbox tab, not another giant window. Show Draft, Sealed, Courier
assigned, In transit, Delivered if known, Intercepted if known, Answered. A
thread interleaves sent/received tablets by known dates and preserves uncertain
delivery.

---

## 15. Kingdom management screens

### Stores

**Purpose:** stock, movement, reservation, spoilage, bronze/melt chain, and
stock decisions. **Default:** 76 × 26. **Minimum:** 58 × 20.

Use at most five rows of stateful vessels/granary art. Table:

```text
good       known amount       Δ 12fn   source/age  reserved
grain      7,573p 20qa       -3,025    ● own count    1,400
seed       0p 0qa                 —     ○ scribe           —
```

Detail shows inflows/outflows, spoilage, commitments, last inspection,
conflicts, linked shipments/groups. Actions: inspect count, compare report,
open seed for food, reserve/release when supported, open melt/bronze detail,
draft purchase/transfer/allocation when supported.

### Roll

**Purpose:** rations, payment priority, labour assignment, arrears, and group
condition. **Default:** 82 × 28. **Minimum:** 62 × 21.

Columns: group, heads, due, allocated, paid last, arrears, loyalty band, task,
source/age. Direct actions: edit allocation with units; useful increment
buttons; move groups in priority; multi-select send/recall harvest; open group
dossier; compare allocation/payment/claim.

### Land

**Purpose:** connect season, water, seed, estate labour, dues, canals, and
harvest claims. **Default:** 80 × 28. **Minimum:** 60 × 21.

Six-row maximum stateful season/river/field art. Estate table: place,
crop/water, reported condition, labour supplied/needed, canal, last yield,
source/age. Actions: inspect seed/granary; send/recall groups; raise corvée;
dredge selected estate; set land due with preview; open estate/place/group;
open Stores/Roll/Works/source.

### Muster

**Purpose:** formations, commitments, readiness/equipment claims, place,
commander, and summons. **Default:** 80 × 27. **Minimum:** 60 × 20.

Direct actions: assign selected/multiple formations to garrison, watch,
harvest, campaign; choose place; appoint/dismiss commander; open summons,
oath, formation, place, commander; draft response to summoning tablet.

### Oaths and obligations

**Purpose:** exact clauses, parties, deadlines, performance claims, succession
state. **Default:** 78 × 28. **Minimum:** 58 × 20.

List statuses: standing, lapsed, reportedly breached, due, unknown. Detail:
seal, parties, witnesses/deities, clauses, performance, orders, documents,
source history. Actions: re-swear; draft satisfaction order; expiate; compare
archive copies; open related party/shipment/formation/rite/document; pin due
date. Never label expiation “correct” or an oath an objective supernatural
cause.

### City

**Purpose:** visual/operational overview of the seat. **Default:** 96 × 34.
**Minimum:** 70 × 24.

Preserve the skyline, numbered building correspondence, comparison table,
construction/condition, and Works route. Add stable selection; columns for
head, staffing, upkeep, throughput, condition, work, source/age; selected
detail/actions; filters All/Vacant/Damaged/Input-starved/Under work; scroll.
Click selects in art and table; double-click opens persistent institution
dossier. Direct actions: inspect, repair, appoint/dismiss, dossier, Works.

### Institution

**Purpose:** operate one institution while City remains. **Default:** 62 × 24.
Show reported vs inspected condition, head/staff/arrears, upkeep/input,
capacity/throughput, repair/build order, dependencies. Actions: inspect,
repair, appoint/dismiss, adjust exposed allocation, open linked dossiers,
compare, pin a block.

### Works

**Purpose:** active projects, available plans, labour/material/season
constraints, start/abandon. **Default:** 82 × 28. **Minimum:** 62 × 21.

Six-row maximum skyline/scaffold. Active table: progress, place, labour,
materials committed/spent, block, head, source. Plans tab: known requirements
and legal sites. Actions: begin work, assign/call corvée, dossiers, repair,
abandon with sunk-cost preview, compare resources, pin/delegate block.

---

## 16. Court, household, religion, and time

### Justice

**Purpose:** triage petitions, hear claims, inspect evidence, rule deliberately.
**Default:** 84 × 29. **Minimum:** 64 × 22.

Keep the court scene but cap it at seven rows. Queue shows kind, parties, wait,
heard, source. Detail shows both statements, known documents, relationships,
precedent, conflicts. Actions: hear (1h), open/compare dossiers/evidence,
delegate investigation when supported, rule for/against/split/defer. Verdict
uses inline irreversible preview; never reveal hidden truth/correctness.

### House

**Purpose:** family, offices, succession, factions, health claims, foreign
placement. **Default:** 82 × 29. **Minimum:** 62 × 22.

Tabs: Family tree; Offices; Succession; Abroad. Person detail shows relations,
claims, post, place, documents/orders. Actions: appoint, dismiss, name heir,
foreign marriage, contact/thread, related dossiers. Lists use player names,
search, and legal choices. Heir/marriage preview irreversibility.

Land and harbour dues must not be hidden behind House key brackets. Primary
routes are Land and Harbour/Relations; House may link a fiscal summary.

### Altar

**Purpose:** choose question, subject, offering; review and act on known omens.
**Default:** 68 × 24. **Minimum:** 52 × 18.

Cap art at six rows. Show harvest/route/death; explicit living subject chooser;
offering and availability; attention cost; dated readings/status; oath/rite
links; validation. Actions: consult (2h), select subject/offering, open related
entity, suppress/defy omen, expiate, pin reading. Never promise larger
offering produces truer forecast.

### Fortnight Chronicle

**Purpose:** show what changed/became known when time advanced and route into
new work. **Default:** 66 × 22. **Minimum:** 50 × 17.

Scrollable dated rows distinguish witnessed events, received reports about
earlier events, derived bookkeeping, and session/autosave notices. Actions:
open source/dossier, locate on World, pin, acknowledge. Filters separate urgent
exceptions, ordinary events, reports, orders, adviser suggestions, and session
notices; current and prior fortnight remain visually distinct. Only an urgent
known exception at the turn boundary may request focus, according to the
player's Alerts setting. It is not an OK-only modal and remains reopenable from
History.

---

## 17. Archive, world, diplomacy, and health

### Archive

**Purpose:** find and compare primary records without turning scholarship into
a chatbot. **Default:** 78 × 28. **Minimum:** 58 × 20.

Use a search/filter row, result list, selected preview, and actions. Search
supports exact phrase, all/any terms, document kind, actor, place, reign, and
known date. A result row shows title, kind, date, provenance, and matched
terms. The preview scrolls independently and highlights terms without changing
the text. Actions: open persistent tablet, compare, cite in a draft/order,
open related dossier, pin, save query, search within.

Every result is reachable by scrolling. Show `1–20 / 84`, not nine numbered
slots followed by clipped content. The one-hour game cost applies when the
query is submitted, never to changing filters, sorting returned records, or
opening a returned record.

Search and snippets are deterministic. An optional **Summarize selected**
operation may use a model, but the source stays beside the summary, the summary
is visibly labelled as generated commentary, and it is never indexed as a
primary record.

### World

**Purpose:** spatially relate last-known places, routes, correspondence,
orders, obligations, and sickness reports. **Default:** 104 × 32. **Minimum:**
68 × 22.

The map is drawn from ground authored in `content/` and carried across the
Belief boundary with the place's name, not from anything `tui/` knows: a
scenario on a different sea draws a different map from the same code, and a
place the tablet cannot locate is named beside the map rather than dropped from
it. `tui/atlas.py` holds the window and nothing else.

The ground is a block of characters. `[terrain]` in the scenario carries
`rows` — one character per cell of ground, three hundred columns by a hundred
and nineteen rows for Ugarit — with `west`/`north` and `step_lon`/`step_lat`
saying what a cell covers, so a real latitude can be turned into a column once,
by hand, and then left alone. The glyphs are `~` sea, `≈` river, `^` upland,
`,` sown, `.` dry, `:` desert, `;` marsh. It crosses the Belief boundary as
scenery: no rule reads it, and a scenario that authors none draws a map of
marks with no ground under them. Editing the map is editing those rows.

The map is bigger than the window on purpose. The arrows pan it; `+` and `-`
change how much ground one character stands for, up to `atlas.MAX_WIDE`; `[`
and `]` walk the places, and choosing a place hands the window back to it. A
place off the window is named under the map, with the count first, and stays
clickable there. Held back from, the ground is sampled in favour of the land: a
coastline that thins out and vanishes as you pull back lies about where the
islands are.

A place is drawn as one letter in brackets that say what it is: `{U}` your own
seat, `[H]` an imperial capital, `(C)` a royal seat, a bare letter for a town.
The letter is authored, the colour is whose empire answers for the place, and
two marks never share a cell — one of them steps aside, because a mark drawn
over a mark is a place that has silently vanished.

Behind the hubs is the hinterland: `[[sites]]` blocks, each a `kind` belonging
to a `hub`, with no names. A small palace is a holding, counted, not a town the
king writes to. They are drawn only on the layer that asks about them, they are
never clickable — no order in this game names one — and the tablet beside the
map counts them by kind.

The tablet is split into seven layers, reached by tabs across the top and by
`tab`: **Land**, the ground and the hubs standing on it; **Roads**, the land
and river routes with the fortnights written on them; **Trade**, the sea lanes
and where the metal comes from; **Farms**, the sown ground and the estates that
work it; **Holds**, the small palaces; **Courts**, who writes to you and how
they hold you; **Plague**, the roads you have shut. Land is the one the window
opens on. Every other layer dims the ground underneath itself so the player can
see where he is looking. The tabs wrap onto a second row rather than running
off the edge.

In a season that has shut the sea, a closed lane is drawn only when it is one
of the selected place's own: the route tablet lists all of them and says which
are closed, and a dotted line for every lane that is not there covers the map
in debris the player cannot act on.

One mark per place on the general map. What a place *also* is — a court with an
opinion of you, a road closed against the plague — belongs to the layer that is
about it, because a legend the player has to learn before he can read anything
is not a map.

Still to come, and deliberately left out for now: the small palaces are drawn
and counted but cannot yet be built, granted or lost; agricultural capacity is
shown as sown ground and estates rather than as a number the land phase reads;
and the roads are straight lines between hubs rather than tracks that follow
the ground.

Keep the ASCII map, but make its selection and layers operational:

- layers: Places, Routes, Couriers, Orders, Obligations, Sickness;
- pan and scroll independent of entity selection;
- selectable place and route edges, including keyboard traversal;
- legend for route state, freshness, source, and seasonal availability;
- selected detail with last observation, source, conflicts, linked orders,
  travellers, correspondence, and legal actions;
- filters for unknown/stale/closed/report due.

Actions: open place/route/correspondent dossier; open related tablet or order;
write; send gift; assign envoy/formation when supported; close/lift route;
compare reports; pin. A click on a route must select a route, not emit an
unhandled string. Opening World never updates a remote place.

### Relations and harbour

**Purpose:** manage correspondents, esteem claims, gifts, marriage ties,
obligations, harbour traffic, and unanswered threads. **Default:** 82 × 28.
**Minimum:** 62 × 21.

Table columns: court/correspondent, relationship band, last known esteem,
unanswered age, last contact, open obligation, route, source/age. Selected
detail distinguishes an actor's stated view, inferred court view, and known
acts. Actions: write/answer; gift; open conversation/dossier; compare claims;
propose foreign marriage; assign envoy; open oath/order/route; set harbour due
through a labelled Fiscal pane.

No decorative score may imply exact foreign sentiment. Show bands and the
evidence that produced them. Harbour due preview states the rate, custom,
likely known affected traffic, and that actor response remains uncertain.

### Health

**Purpose:** manage reported sickness, burials, route exposure, closures, and
known consequences without revealing epidemic compartments. **Default:** 78 ×
27. **Minimum:** 58 × 20.

The list includes place/route, reported sign, first/last report, deaths or
burials if reported, closure, source/age, and conflict. Detail shows the report
chain and known consequences of closure: stopped trade, correspondence, and
travel. Actions: close/lift route (1h preview); open source/place/route;
compare reports; write to correspondent; pin; open related rite/oath.

All rows beyond nine must be keyboard reachable. `Q` is never both a quit key
and a quarantine mnemonic; use the printed action mnemonic and semantic hit
command. Health reports describe Belief only and never expose susceptible,
infected, or recovered counts.

---

## 18. Files, settings, and session state

### Files

**Purpose:** make save, load, autosave, scenario, and exit state explicit.
**Default:** 58 × 22. **Minimum:** 44 × 17.

Show save name, ruler/scenario, year/fortnight, hours remaining, last save,
engine/schema version, and compatibility. Actions: Save, Save as, Load,
New game, Reveal location, Exit. Overwrite/load/exit use a compact inline
preview if they would discard unsaved state or drafts.

The save contract includes current attention hours, sealed/draft
correspondence, current orders, and every engine event needed for replay.
Loading must not refill attention. Window geometry, font, palette, filters, and
ordinary selection are preferences rather than simulated state and may live in
a separate profile file. Restore dirty text drafts only when their source
session matches.

Autosave occurs after a successful persistent action and after the fortnight
advances. It never fires because a window was moved or a filter changed. The
Hall status line shows saved/unsaved and time.

### Settings

**Purpose:** configure presentation, input, files, and optional AI without
leaving the game. **Default:** 56 × 23. **Minimum:** 44 × 17.

Tabs:

- Display: 9–20 point font, face, Compact/Standard/Comfortable row density,
  palette, contrast, Unicode/pure ASCII, live preview, reduced motion;
- Windows: restore placement, open-next-to-source, tile gap, reset layout;
- Input: key map, mouse activation, command history, repeat timing;
- Files: autosave, profile, save location;
- Alerts: urgent-focus policy, event categories, sound/bell, chronicle detail;
- AI: Off / Small local / Custom, model, deadline, context, cache, privacy;
- Accessibility: colour-independent symbols, focus style, text scale, copy
  mode, screen-reader announcements where the platform permits.

Changes preview immediately and can be reverted before closing. Resetting
layout or bindings names exactly what will change. The default presentation is
compact, not tiny; the font can be increased without content loss.

---

## 19. Complete action and click-path map

This table is normative. It maps every current player action dataclass to at
least one contextual direct route and one deterministic command. Labels and
availability come from the action registry rather than this prose.

The Required attention column is the product contract. During the audit,
`DelegateLetter` charged 1h in the direct GUI but fell through to 0h in the
parser's `action_cost()`; Phase 1 must remove that divergence.

| Action | Primary direct path | Deterministic command | Required attention |
|---|---|---|---:|
| End fortnight | Hall → **End fortnight** → review → Proceed | `end fortnight` | 0h |
| Allocate rations | Roll → group(s) → **Allocation** → amount → Apply | `allocate <amount> to <group>` | 0h |
| Set payment priority | Roll → Priority mode → move selected group(s) → Apply | `prioritize <groups>` | 0h |
| Eat seed | Stores → Seed → **Open for food** → quantity → Confirm | `eat <amount> seed` | 0h |
| Read letter | Inbox → tablet → **Read** | `read <tablet>` | 2h |
| File/restore letter | Inbox/Tablet → **File** / **Restore** | `file <tablet>`, `restore <tablet>` | 0h |
| Delegate letter | Inbox/Tablet → **Delegate** → courtier → preview | `delegate <tablet> to <person>` | 1h |
| Dictate reply | Inbox/Tablet → **Answer** → Desk → Seal/send | `answer <tablet>` opens Desk | 2h |
| Inspect ledger | Stores/Land → Granary or Seed → **Inspect count** | `inspect granary`, `inspect seed` | 1h |
| Send gift | Relations/Tablet → correspondent → **Gift** → good/quantity | `gift <amount> <good> to <actor>` | 1h |
| Send/recall harvest labour | Roll/Land → group(s) → **Send to fields** / **Recall** | `send <group> to harvest`, `recall <group>` | 1h |
| Assign troops | Muster → formation(s) → **Assign** → task/place | `assign <formation> to <task> at <place>` | 1h |
| Raise corvée | Land/Works → **Raise corvée** → days | `raise corvee <days>` | 1h |
| Dredge canal | Land → estate → **Dredge** → days | `dredge <estate> for <days>` | 1h |
| Foreign marriage | House Abroad/Relations → person → **Marry abroad** → court | `marry <person> to <court>` | 2h |
| Consult diviner | Altar → question/subject/offering → **Consult** | `consult <question> [for <subject>] [with <offering>]` | 2h |
| Suppress omen | Altar/House → omen → **Suppress** → preview | `suppress <omen>` | 2h |
| Defy omen | Altar/House → omen → **Defy** → preview | `defy <omen>` | 0h |
| Re-swear oath | Oaths → oath → **Re-swear** → preview | `swear <oath>` | 2h |
| Close/lift routes | Health/World → place/route → **Close** / **Lift** | `quarantine <place>`, `lift quarantine <place>` | 1h |
| Expiate oath | Oaths/Altar → oath → **Expiate** → offering | `expiate <oath> with <amount>` | 2h |
| Search archive | Archive → query → **Search** | `search archive for <terms>` | 1h |
| Hear petition | Justice → case → **Hear** | `hear <petition>` | 1h |
| Rule petition | Justice → heard case → verdict → preview | `rule <verdict> on <petition>` | 0h |
| Set land due | Land → Fiscal → rate → Apply | `set land due to <rate>` | 0h |
| Set harbour due | Relations/Harbour → Fiscal → rate → Apply | `set harbour due to <rate>` | 0h |
| Place person | House/Institution/Muster → post → **Appoint** → person | `appoint <person> to <post>` | 0h |
| Dismiss person | House/Institution/Muster → post → **Dismiss** → preview | `dismiss <post>` | 0h |
| Name heir | House Succession → person → **Name heir** → preview | `name <person> heir` | 0h |
| Begin building | Works Plans → plan → site → **Begin** → preview | `build <kind> at <place>` | 1h |
| Begin repair | City/Institution/Works → institution → **Repair** | `repair <institution>` | 1h |
| Abandon work | Works Active → project → **Abandon** → loss preview | `abandon <project>` | 1h |

The command column describes user language, not a second implementation. Both
paths construct the same structured action and pass through the same
availability, cost, preview, reducer, feedback, save, and order-history path.

Session/UI operations also need complete visible routes:

| Operation | Direct route | Key/palette |
|---|---|---|
| Open/raise a room | Hall Places or Window Switcher | F-keys / `open <room>` |
| Open dossier/tablet | selected row → Open | Enter/double-click |
| Filter/sort/scroll | local workbench controls | `/`, header, navigation keys |
| Compare/pin | selected entity/document → Compare/Pin | printed mnemonic |
| Help | title/status **Help** | `F1` / `?` |
| Save/load | Files or Hall status | Ctrl/Cmd-S, Ctrl/Cmd-O |
| Settings | Files/Window menu | Ctrl/Cmd-, |
| Tile/cascade/switch | Window Switcher | F8, Shift-F8, Ctrl/Cmd-Tab |
| Cancel active request/preview | visible Cancel | Esc or Ctrl-U in text request |
| Quit | Files → Exit | Ctrl/Cmd-Q |

Targets:

- after selecting the relevant row, a common direct action takes at most two
  activations before its semantic preview;
- every legal action is reachable within three activations from its relevant
  workbench;
- no action requires remembering a room letter, invisible range, or parser
  wording;
- mouse, keyboard, command palette, and terminal path show the same cost and
  produce the same event sequence for the same structured choice.

---

## 20. AI and adviser policy

### Product rule

**AI is prose seasoning, never interface infrastructure.** The complete game,
including Help and all orders, must remain fast and comprehensible with no
model process, no network, and an empty model cache.

Allowed model uses:

- explicit **Elaborate** on an already visible deterministic adviser answer;
- explicit **Ask interpreter** after the deterministic command parser has
  shown what it could not resolve;
- optional **Embellish** for a player-written letter, accepted manually;
- rare, important NPC voice passages prepared in the background and cached;
- optional summary of selected archive records, labelled and source-adjacent.

Forbidden model uses:

- Help search or control documentation;
- deciding, validating, costing, selecting, or executing an action;
- autoplay, AI governors, hidden World access, probability estimates, or
  “best action” rankings;
- ordinary screen open, selection, repaint, turn projection, or save/load;
- changing letter protocol grades or simulation effects;
- delaying input acknowledgement, direct controls, or deterministic fallback.

### Defaults and limits

- Default interface/adviser mode: **Off**. First-run setup may offer an
  explicit **Small local** opt-in.
- Small local target: a quantized model at or below roughly 4B parameters;
  larger custom models are an expert setting, never the shipped usability
  assumption.
- One in-flight request per role and one shared configurable concurrency cap.
- Context at most 2,048 tokens and output at most 160 tokens by default.
- Product deadline: 5 seconds for optional prose; interpreter draft 3 seconds.
- Show deterministic content within 100 ms and a textual busy state within
  another frame. Timeout/cancel keeps that content.
- Cache by model/version, role, normalized prompt, Belief snapshot identity,
  language, and seed. Replay consumes no model output.
- Request IDs, cancellation tokens, and source-version checks discard stale
  or out-of-order completion.
- Enter is disabled for the active request or idempotently raises it; it never
  queues duplicates.
- Model failure is a quiet local status, not an error dialog.

The present 14B default is outside this contract. In a measured warm run, Help
took about 5.8 seconds and Counsel about 14.3 seconds. Moving the call off the
Tk thread prevents a freeze, but does not make a frequently required workflow
usable. Remove Help's call, make adviser prose explicit, and optimize the
deterministic experience first.

### Adviser frequency and posture

- Hall may show facts/exceptions every fortnight; advice appears only when
  attributed to a named person.
- Advisers are pull-first. Each adviser supports Ask, Mute, Critical only,
  Dismiss, and **Why this advice?**; the last control reveals the known
  threshold and cited records, not hidden model reasoning.
- Each adviser proactively speaks at most once per fortnight, and only after a
  materially new known threshold or obligation.
- A per-adviser cooldown prevents the same topic from reappearing unless its
  known severity changes.
- Repeated known concern remains a docket row, not a repeated speech.
- Advice cites its basis and uncertainty and may conflict with another named
  adviser.
- Never display an unattributed imperative such as `Do: send grain`.
- Dismiss/snooze affects presentation only, not World state.

---

## 21. Implementation architecture

### One action registry

Create a declarative `ActionDescriptor` for every player action:

```text
id
action_type
label / short_label
contexts
keywords and deterministic grammar
fields and entity domains
current cost function
availability / refusal
preview composer
confirmation policy
execute
success formatter
help topic and examples
default mnemonic
batch policy
```

Screen controls, hit regions, keyboard handlers, command completion, Help, CLI
syntax, and automated coverage consume this registry. No screen stores a
second cost or invents a private command string. A controller dispatch receives
semantic intents such as `select:person:<id>` and `action:repair:<id>`, not
visible glyphs such as `↑`, `1-9`, or `a-z`.

The shared result type contains:

```text
status: preview | success | refusal | cancelled
action_id and target links
cost and hours remaining
message
missing field/prerequisite
events/order ID
undo token when legal
```

Render that result in the initiating workbench and Hall/session log. This
removes silent failures and feedback hidden behind another window.

### Responsive screen contract

Replace fixed `compose(width, height)` assumptions with:

- `ScreenDescriptor`: role, default/minimum cells, panes, actions, context Help;
- `WindowState`: geometry, active pane, selection IDs, filter, sort, scroll,
  pins, responsive tier;
- pane layouts that remeasure on configure events and preserve IDs/scroll;
- shared list/table/text viewport models with headers, scroll indicators, and
  mouse/keyboard selection;
- separate stateful art variants for wide/standard/compact, plus no-art
  minimum;
- semantic focus and input modes, so global keys never leak through an active
  tablet/editor/list.

Use the native OS frame as the window title. Do not draw a second large title
bar unless it carries game state/tabs that the OS frame cannot.

### Window manager

A small application-level manager owns:

- single-instance workbench keys and multi-instance entity keys;
- raise/reuse/open-next-to-source;
- work-area-aware placement, tiling, cascade, monitor clamping;
- geometry/profile persistence;
- focus history and Window Switcher;
- dirty-draft close negotiation;
- universal font/palette recomposition.

No workbench directly constructs an unmanaged `Toplevel`.

### Orders, documents, and provenance

- Persist structured player intent separately from resulting events as already
  required by replay; surface it through Orders.
- Use stable entity/document/order IDs for links and selection.
- Keep World/Belief projection one-way. UI composers receive Belief plus
  permitted local inspected facts, never World.
- Treat source/observed/received fields as common view data rather than
  hand-built strings per screen.
- Generate Help and control legends from descriptors, with authored conceptual
  paragraphs attached to registry topics.

### Background work

All optional model work enters a bounded worker service. The Tk thread enqueues
a request and immediately renders fallback/busy state; only the Tk event queue
applies a matching completion. The service supports cancel, timeout, request
identity, source version, duplicate suppression, and shutdown. Nothing calls a
model during a composer or reducer.

### Session integrity

- Serialize attention hours or derive them from a persisted action/session
  ledger with no opportunity to refill by load.
- Autosave only after successful mutations or turn advance.
- Preserve structured replay even when generated prose is absent.
- Make dirty state and last save visible.
- Route every global action through input-mode checks; an unadvertised Space
  on a read-only report cannot advance time and an unadvertised `Q` cannot
  exit.

---

## 22. Delivery plan

### Phase 0 — stabilize and freeze the contract

- Finish the current M13 state transition and make the full suite green.
- Generate an authoritative inventory of actions, rooms, controls, costs, and
  help coverage.
- Add Relations and Health to screenshot/text-dump coverage.
- Record current save compatibility and attention semantics.

Exit: the inventory fails CI on an orphan action, unreachable room, duplicate
mnemonic, false Help instruction, or uncovered reachable screen.

### Phase 1 — action routing and feedback

- Introduce `ActionDescriptor` and shared `ActionResult`.
- Move cost/validation/Help/CLI metadata into it.
- Fix semantic mouse/keyboard parity and House key collisions.
- Show success/refusal in the initiating window.
- Add scroll models to every truncated collection.
- Persist hours correctly.

Exit: every action in section 19 has equivalent direct, keyboard, palette, and
terminal tests.

### Phase 2 — compact responsive desktop

- Implement font scaling, responsive tiers, minimums, list/text scrolling.
- Add managed placement, geometry memory, tiling, switching, and workbench
  reuse.
- Remove duplicate interior title chrome.
- Replace Help with the deterministic 52 × 20 Field Manual.
- Add Files and Settings.

Exit: coexistence tests in section 6 pass at 1366 × 768, 1440 × 900, and 200%
text.

### Phase 3 — the daily decision loop

- Recompose Hall, Orders, Inbox, Tablet, Desk, and Counsel.
- Add correspondence archive/outbox/conversation/delegation states.
- Attribute/suppress adviser prompts according to section 20.
- Make the Fortnight Chronicle persistent and reopenable.

Exit: a player can discover a matter, inspect its source, compare it, reply or
order, and see its status without closing context or waiting for AI.

### Phase 4 — contextual kingdom and court controls

- Recompose Stores, Roll, Land, Muster, Oaths, City, Institution, Works,
  Justice, House, and Altar.
- Start from City's art/table/action pattern and Desk's source/form/preview
  pattern.
- Add every missing direct route before additional decoration.

Exit: Counsel is unnecessary for all current simulation actions.

### Phase 5 — cross-reference workbenches

- Recompose Archive, World, Relations, and Health.
- Add common dossiers, pins, compare, source links, and route selection.
- Complete Orders and provenance integration across them.

Exit: the player can answer “what changed, who said it, how old is it, what
conflicts, what did I order, and what is blocked?” through visible links.

### Phase 6 — optional prose and polish

- Enforce Off/Small/Custom model policy, bounded queue, cancel, cache, and
  performance telemetry.
- Add small/stateful responsive art variants and pure-ASCII snapshots.
- Tune density, palette, focus/hover/pressed states, key labels, and copy mode.
- Conduct usability sessions and address discovered paths, not just styling.

Exit: AI-off is the reference test configuration; AI-on can time out without
changing task completion or simulation results.

---

## 23. Verification and acceptance

### Automated contract tests

1. Enumerate every action dataclass; require descriptor, Help, direct context,
   deterministic grammar, cost, availability, preview, and success/refusal
   coverage.
2. Enumerate every reachable screen; require text snapshot and wide, standard,
   compact, minimum, pure-ASCII, and 200%-type render.
3. Render collection fixtures at 0, 1, 9, 10, and 100 rows; every row must be
   reachable and selection stable across filter/sort/resize.
4. Replay the same action through click, key, palette, and CLI; compare
   structured action, cost, events, result, and save log.
5. Validate every emitted hit command has a handler and every visible
   mnemonic is unique in its mode.
6. Validate Help against the live registry; stale keys, syntax, costs, or
   missing rooms fail CI.
7. Save/load after spending each possible number of hours; remaining hours
   must not increase.
8. Verify UI projectors cannot access hidden World fields or refresh Belief.
9. Verify active text/list/preview modes suppress dangerous global keys.

### Window and visual tests

- No initial auxiliary exceeds 80% of the work area.
- Hall + Help, Inbox + Tablet, City + Institution, and Stores + Roll can be
  meaningfully arranged at target resolutions.
- Resizing never clips the focused field, selection, actions, cost, source,
  scroll position, or cancel route.
- At default size, useful body-row density reaches section 7 targets.
- Every clickable item has stable focus, hover, pressed, and selected
  treatment; hand-cursor-only affordance fails review.
- Native and interior title bars do not repeat the same title.
- Colour removal and pure ASCII preserve every state distinction.

### AI failure tests

Run each optional model surface with AI Off, model missing, cold start, timeout,
malformed output, cancellation, duplicate Enter, completion after close,
out-of-order completion, and app shutdown. Direct controls and deterministic
content remain available; no late result steals focus, executes an action, or
changes replay.

### Performance budgets on reference hardware

| Interaction | p95 target |
|---|---:|
| Key/click acknowledgement | 50 ms |
| Help/filter incremental result | 50 ms |
| Deterministic parse/validation | 100 ms |
| Screen compose after resize | 25 ms |
| Window raise/switch | 100 ms |
| AI request fallback + busy state | 100 ms |

Optional model completion has a deadline rather than an animation target. It
never counts as required task completion.

### Task-based usability review

With Help available but no prior key knowledge, a new player must be able to:

1. find why grain changed and identify source age;
2. inspect the true granary, then change one ration allocation;
3. read and answer a tablet while keeping it visible;
4. assign a formation to a place;
5. begin or repair a work and see its labour/material block;
6. hear and rule on a petition without receiving a truth verdict;
7. compare two conflicting reports and close a route;
8. find an active/blocked order and contact its delegate;
9. enlarge type to 200%, tile two useful windows, and continue;
10. save with three hours remaining, load, and still have three hours.

Observe route, clicks/keys, backtracking, errors, and time. Targets: no task
requires Counsel; every error explains the missing choice; every task can be
completed with AI Off; common tasks reach preview within three contextual
activations.

---

## 24. Definition of done

The redesign is done when:

- the game reads as one coherent retro text-mode desktop, not a collection of
  oversized replacement screens;
- Hall and a compact Help/document can remain visible together;
- every current simulation action is present where its evidence is shown;
- City is no longer the exceptional good screen because other workbenches
  share its art/data/action discipline;
- Help is instant, deterministic, compact, correct, and generated from the
  live control contract;
- Counsel is optional, attributed, infrequent, and never a control bottleneck;
- every collection scrolls, every click has keyboard parity, every refusal is
  visible, and every destructive act previews its semantics;
- source, age, conflict, cost, and order status are present wherever they
  affect a decision;
- window placement, resize, font scaling, and switching make windowing useful;
- AI Off is fully featured, and optional small-model work is cancellable and
  unable to affect deterministic state;
- save/load cannot replenish attention;
- all acceptance suites and the ten usability tasks pass.

The visual north star remains City; the interaction north star is Desk. The
redesign succeeds by extending their best idea to the whole game: beautiful
ASCII that explains the state, dense records that show the evidence, and an
exact action beside the thing it changes.
