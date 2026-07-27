# SAY TO THE KING, MY LORD
## Windowed UI/UX rework specification — “The Palace Desktop”

- Status: proposed implementation specification
- Revision: 2026-07-28
- Scope: the primary windowed game; terminal play remains supported
- Relationship to `SPEC.md`: this document operationalizes the interaction
  requirements in sections 4.4, 8, 11.3, and M13.0/M13.5. It does not weaken
  the World/Belief boundary, determinism, or the rule that models never decide
  game state.

---

## 1. Decision

The current interface should not receive another cosmetic pass. It should be
recomposed as a compact, persistent, multi-window information workspace with a
1990s text-mode visual language.

Keep:

- real operating-system windows;
- the shared character-cell renderer;
- keyboard and mouse parity;
- the amber, clay, lapis, and shadow palette;
- box drawing, reverse-video bars, key labels, and pure-ASCII fallback;
- the City screen's combination of stateful ASCII art, dense information, and
  direct drill-down;
- the principle that the player sees Belief rather than hidden World state.

Change:

- default typography from 14-point to 11-point monospace, with immediate,
  persistent font scaling;
- fixed compositions into resizable, responsive layouts;
- large single-purpose reports into compact list/detail/action workbenches;
- Help from a 100 × 38 AI conversation into a roughly 52 × 20 deterministic
  reference window;
- Counsel from a 92 × 36 blocking chat into a compact order/advice window whose
  deterministic result appears immediately;
- Counsel as the only practical route to many actions into direct controls on
  the screen where the relevant information is visible;
- silent refusals into visible, specific explanations;
- overlapping-at-one-origin window creation into remembered placement, useful
  tiling, and a window switcher;
- automatic or routine model calls into explicit, rare, asynchronous prose
  enhancement.

The target feeling is not “a modern dashboard wearing an ASCII skin.” It is a
good information-management game from 1993 that happens to understand the
mouse: fast, terse, inspectable, keyboard-friendly, full of ledgers and
documents, and handsome because its text layout is deliberate.

---

## 2. Product goals and non-goals

### 2.1 Goals

1. **Several useful windows remain visible.** Help, a tablet, a ledger, and the
   Hall must behave as references and work surfaces, not replacement screens.
2. **Information and action live together.** A player looking at troops can
   assign troops; a player looking at a ration group can change its allocation;
   a player looking at a route can close it.
3. **The interface is dense but legible.** Empty space is intentional, not the
   result of a giant fixed canvas with little content.
4. **The game is text-first.** Most meaning is in prose, tables, ledgers,
   timelines, and source annotations. ASCII art establishes place and mood and,
   where possible, encodes state.
5. **The UI never makes the player guess the interface.** Unknown commands,
   unaffordable actions, missing prerequisites, and ambiguous targets explain
   what is needed.
6. **Direct controls are complete.** Typed prose is an additional interface,
   not a dependency and not the only path to a mechanic.
7. **The interface is instant without AI.** Navigation, Help, reading,
   selection, filtering, ordering, previews, and fallbacks do not wait for a
   model or network socket.
8. **Uncertainty remains gameplay.** Better usability must not become
   omniscience. Every claim retains its source and age.
9. **The windowed and terminal games share semantics.** They may lay information
   out differently, but they use the same action descriptors, costs,
   validation, names, and help text.

### 2.2 Non-goals

- Do not turn the game into a single full-screen web dashboard.
- Do not replace text with icons, cards, radial menus, or large illustrative
  panels.
- Do not imitate Dwarf Fortress's historical inconsistencies or Rule the
  Waves 3's hidden right-click dependence.
- Do not add animation for its own sake.
- Do not reveal true values, future events, hidden disease counts, actor
  motives, or the “correct” strategic answer.
- Do not make a language model necessary for commands, Help, NPC policy,
  replay, or understandable prose.
- Do not spend in-world attention on selecting, sorting, filtering, moving a
  window, correcting syntax, or recovering from an interface error.

---

## 3. Current-state audit

### 3.1 Method

The audit used:

- the current Tk controller, composers, interaction hit regions, command corpus,
  and engine action union;
- plain-text dumps of all composed screens at seed `8814402919`, turn 6;
- a live windowed run with AI disabled;
- actual Tk geometry measurements on a 1512 × 982 display;
- current direct and typed action paths;
- the authoritative product specification and the archived prior TUI plan.

The tree was under active M13 development during the audit. This specification
therefore treats individual current line numbers as incidental and describes
stable product contracts rather than preserving every transient route.

### 3.2 Measured window problem

The current backend uses a 14-point monospace font and fixed cell dimensions.
On the audit display, the resulting windows measured:

| Window | Cell size | Approximate outer size | Share of display |
|---|---:|---:|---:|
| Hall | 104 × 36 | 1264 × 804 px | 84% wide, 82% high |
| Help | 100 × 38 | 1216 × 848 px | 80% wide, 86% high |
| Inbox | 108 × 36 | 1312 × 804 px | 87% wide, 82% high |
| City | 96 × 36 | 1168 × 804 px | 77% wide, 82% high |
| Stores | 62 × 22 | 760 × 496 px | 50% wide, 51% high |

These pixel values are platform-specific, but the relationship is decisive:
Hall and Help cannot be viewed side by side, and Help covers nearly the entire
usable display. A multi-window architecture rendered at replacement-screen
sizes is functionally single-window.

At 11 points, a 92 × 34 Hall measured about 844 × 624 px and a 52 × 20 Help
window about 484 × 372 px. Those windows can coexist on the same display with
room for native window chrome and a gap. This is the target default density,
not a hard accessibility limit.

### 3.3 What presently works

The City is the strongest direction:

- it is immediately recognizable as a place;
- its skyline changes with the institutions it represents;
- numbered buildings connect picture, list, and detail;
- condition, keeper, and current work share one screen;
- it leads directly to institution inspection, repair, and Works;
- decoration and data reinforce one another.

The World map, Desk, Justice scene, Altar, and some portraits also contain good
raw visual material. The Inbox's split list/reader and the shared clickable
footer are sound structural beginnings.

### 3.4 Systemic problems

1. **Fixed size defeats windowing.** Most screens open large and near the same
   origin. The source window is frequently hidden by the destination.
2. **Font scale is not a user setting.** Fourteen points is globally hardcoded
   as the default, even for dense ledgers.
3. **Several large windows are mostly empty.** Counsel and Help devote many
   rows to portraits, labels, blank conversation space, and suggestions.
4. **Many reports cannot act on what they show.** Stores, Roll, Land, Muster,
   Oaths, World, Relations, and disease information route important decisions
   through Counsel or another unrelated screen.
5. **The action vocabulary and visible help can drift.** Current help text has
   described keys that differ from the controller, because controls, parser
   grammar, and Help are authored separately.
6. **Model calls block the UI thread.** The current shared default is a
   14-billion-parameter local model. Counsel allows a 45-second call, Help a
   30-second call, and parser fallback an 8-second call from synchronous key
   handlers.
7. **Help solves the wrong problem.** The user needs quick controls, syntax,
   costs, and context. A large conversational portrait screen is slower to
   scan and harder to keep open than a small indexed manual.
8. **Errors are often silent.** Insufficient hours, illegal states, impossible
   targets, and failed engine validation can leave the screen unchanged.
9. **Collections truncate or underuse space.** Several report composers assume
   their list fits. Others leave most of a fixed canvas blank.
10. **Navigation semantics vary by window.** Some unhandled keys fall through
    to Hall navigation; conversational rooms capture all keys; secondary
    windows do not share a reliable global switcher.
11. **Source and freshness are not consistently visible.** The game's central
    information constraint is stronger in the simulation than in the UI.
12. **File/session operations are not yet a coherent workspace.** Save, load,
    autosave state, incompatibility, settings, and window layout need visible
    routes in the primary windowed interface.

---

## 4. Lessons from comparable interfaces

These references are inputs, not templates to copy literally.

| Reference | Useful observation | Decision for this game |
|---|---|---|
| [Dwarf Fortress Classic controls](https://dwarffortresswiki.org/index.php/DF2014%3AControls) | Context-specific commands are printed on the current screen; arrows indicate more options; the same physical key can be meaningful in a local mode. | Keep visible contextual hotkeys, but show the current mode and never hide an action behind memorization. |
| [Dwarf Fortress display settings](https://dwarffortresswiki.org/index.php/Settings) | Windowed mode can be resizable, and players can choose desired grid dimensions or interface scale. | Treat font scale and cell count as first-class settings; recompose on resize. |
| [DFHack command launcher](https://docs.dfhack.org/en/stable/docs/tools/gui/launcher.html) | A text command surface can provide autocomplete, context help, output, history, and search without an AI parser. | Build a deterministic command palette from the legal action registry. |
| [DFHack manipulator](https://docs.dfhack.org/en/stable/docs/tools/gui/manipulator.html) | Spreadsheet-like search, sort, filter, and at-a-glance assignments suit a deep simulation. | Management screens use dense tables, stable selection, filters, and batch operations. |
| [Rule the Waves 3 manual](https://ftp.matrixgames.com/pub/RuletheWaves3/Rule%20the%20Waves%203%20Manual%20EBOOK.pdf), pp. 47 and 114 | Its main ship list supports multi-selection and many object actions; a status screen can remain open while the player operates elsewhere. | Use persistent workbench windows and batch selection. Do not make right-click the only discovery path. |
| [Apple window guidance](https://developer.apple.com/design/human-interface-guidelines/windows) | Auxiliary windows are useful for preserving context, but excessive windows create clutter; windows should adapt fluidly and remember user placement. | Open new windows when cross-reference matters, reuse existing workbenches, and remember geometry. |
| [Microsoft window-management guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/win-window-mgt) | Resizable windows avoid truncated data; oversized secondary windows should be reduced to fit the target monitor. | Every substantive window is resizable and initially fits the active work area. |
| [Microsoft dialog guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/win-dialog-box) | Dialogs interrupt flow and are overused; modeless tools suit frequent ongoing tasks. | Help, Counsel, ledgers, dossiers, and previews are modeless. Modal interruption is reserved for rare destructive file operations. |
| [Emily Short on parser interfaces](https://emshort.blog/2010/06/10/parser-discussion-redux/) and [Inform's disambiguation guidance](https://www.inform-fiction.org/manual/html/s33.html) | “Guess the verb” leaves the player unsure whether wording or capability is wrong; good parsers identify ambiguity and ask a focused question. | Exact controls and autocomplete are primary; parser errors identify the unknown verb, target, value, or missing choice. |
| [WCAG resize-text guidance](https://www.w3.org/WAI/WCAG20/Understanding/resize-text) | Text must be scalable without losing content or functionality. | Smaller default type is paired with 9–20 point scaling and responsive recomposition, not fixed tiny text. |
| [Apple progress-indicator guidance](https://developer.apple.com/design/human-interface-guidelines/progress-indicators) | Long work must not look frozen and should be cancellable when possible. | Optional model work is background work with a textual status and Cancel action; the rest of the game remains usable. |

The synthesis is: preserve the speed and density of a mature keyboard
interface, add the discoverability and directness of visible mouse controls,
and use real windows only where keeping context visible has strategic value.

---

## 5. Experience model: the palace desktop

The game is a desktop of documents and places at court.

### 5.1 Window roles

1. **Anchor — Hall.** One persistent home window. Closing it requests exit.
2. **Workbenches.** One instance each of Inbox, Orders, City, Works, Roll,
   Muster, Archive, World, Relations, and Health. Reopening raises the existing
   window and preserves selection, scroll, filters, and geometry.
3. **Documents and dossiers.** Multiple tablets, people, institutions,
   routes, obligations, cases, projects, and places may be open
   simultaneously, keyed by entity ID.
4. **Utilities.** Help, command palette, Settings, Files, and Window Switcher
   are compact, modeless, and single-instance.
5. **Moment windows.** The Fortnight Chronicle receives focus when time
   advances but does not hide or disable the Hall.

### 5.2 Core investigation loop

```text
notice a matter
    -> inspect its source
    -> compare a claim with a ledger, dossier, or other claim
    -> choose a direct action or draft an order
    -> see exact cost, target, delegate, and consequence wording
    -> confirm only when persistence or irreversibility warrants it
    -> keep the evidence and resulting order visible
```

Opening, selecting, sorting, filtering, comparing, and moving windows are
always free. Only simulated acts consume attention.

### 5.3 Default workspace

On first launch, place the Hall at the upper left with room for one compact
utility or document to its right. Subsequent windows fill free rectangles
before overlapping the focused source window.

```text
┌──────────── HALL · 92 × 34 ────────────┐  ┌──── HELP · 52 × 20 ────┐
│ matters, waiting court, quick ledgers   │  │ context / search / keys │
│ and navigation                         │  │ exact syntax and costs   │
│                                        │  └─────────────────────────┘
│                                        │
└────────────────────────────────────────┘  ┌── selected tablet ──────┐
                                            │ source kept for compare  │
                                            └─────────────────────────┘
```

This is an initial placement, not a forced tiling shell. The player can move,
resize, minimize, and close auxiliary windows with native controls.

---

## 6. Window, typography, and responsive-layout contract

### 6.1 Typography

- Default font size: **11 points**.
- Supported range: **9–20 points**, in one-point increments.
- Shortcuts: `Cmd/Ctrl +` enlarges, `Cmd/Ctrl -` reduces, and
  `Cmd/Ctrl 0` restores the player's chosen default.
- Font, size, palette, pure-ASCII preference, and per-window geometry persist
  between sessions.
- Prefer a crisp, narrow, CP437-capable monospace face with clear distinctions
  among `0/O`, `1/l/I`, `5/S`, punctuation, and box drawing. Bundle a
  permissively licensed face only after its license and platform rendering
  have been reviewed; retain the current system-monospace fallback chain.
- Scale type rather than stretching a rendered screen bitmap. Every size
  produces a newly composed cell grid.
- Cursor, selection, unread state, disabled state, and urgency may use colour,
  but always retain a glyph or word distinction.

The smaller default is an information-density choice, not a mandate to endure
small text. Increasing type must reflow or scroll content without hiding an
action.

### 6.2 Default and minimum sizes

Defaults are expressed in cells so they remain coherent across fonts.

| Class | Typical default | Minimum | Examples |
|---|---:|---:|---|
| Anchor | 92 × 34 | 72 × 26 | Hall |
| Wide workbench | 88 × 30 | 66 × 22 | Inbox, Orders, City, World |
| Ledger workbench | 78 × 27 | 58 × 20 | Roll, Land, Muster, Works |
| Document/dossier | 62 × 25 | 46 × 18 | Tablet, person, institution, oath |
| Compact utility | 52 × 20 | 40 × 15 | Help, Files, Settings |
| Command palette | 68 × 15 | 48 × 11 | typed orders and navigation |

City may default to 94–96 columns because its skyline uses the width well.
Inbox may default to 90 columns when the work area allows. No initial window
may exceed 80% of the active monitor's usable width or height except when the
user previously chose and saved that geometry.

### 6.3 Responsive tiers

Each composer receives current width and height and chooses a layout tier.
The backend recomposes after a debounced resize; the `Text` widget does not
merely expose blank cells around a fixed screen.

| Tier | Width | Behaviour |
|---|---:|---|
| Wide | 88+ | list, detail, and narrow context/action rail may coexist |
| Standard | 68–87 | list/detail split; actions use bottom rows |
| Compact | 52–67 | list and detail stack or switch with `Tab`; art shrinks |
| Minimum | 40–51 for utilities, 46–51 for documents | one pane at a time; all commands remain in the action bar |

Height has corresponding bands:

- 28+ rows: full useful art and history;
- 20–27 rows: reduced art and shorter context blocks;
- 15–19 rows: no decorative art, scrollable content, two-row action/status bar;
- below the class minimum: prevent further shrink rather than silently clip.

When space contracts, remove in this order:

1. decorative sky, borders, shadows, and portraits;
2. redundant prose already represented in a selected detail;
3. lower-priority table columns moved into detail;
4. optional history/sparkline length.

Never remove selection, source/age, cost, enabled actions, scroll position, or
the focused text input.

### 6.4 Placement and persistence

- New workbenches open adjacent to their source when a free rectangle exists.
- A new window must not fully cover the selected source row or source
  document. If no free rectangle fits, cascade by one title-bar height and four
  character cells.
- Reopening a workbench raises the existing instance; it does not reset or
  duplicate it.
- Entity documents can be duplicated explicitly with **Open another copy**,
  but ordinary activation raises the existing entity window.
- Remember geometry, monitor, selection, filter, sort, and scroll by window
  kind. Clamp restored geometry to the currently available monitors.
- `F8` tiles visible game windows; `Shift+F8` cascades them;
  `Cmd/Ctrl+Tab` cycles them; `F6` opens a compact Window Switcher; `F2`
  raises Hall.
- The Window Switcher lists open windows, selected entity, dirty draft or busy
  state, and keys to focus or close them.
- Hall remains open for the session. Closing Hall invokes the same visible
  Save/Exit flow as `Cmd/Ctrl+Q`.

### 6.5 Required coexistence tests

At the default font:

- Hall and Help are fully visible together at 1440 × 900.
- A tablet and Stores are fully visible together at 1366 × 768.
- Inbox and a detached tablet can be read together at 1440 × 900.
- City and institution detail can be read together at 1440 × 900.
- At 200% of the default font, every action remains reachable through reflow,
  pane switching, or scrolling.

---

## 7. Visual language

### 7.1 Era and tone

Aim for a coherent 1991–1995 text-mode application:

- native OS title bars outside;
- reverse-video title and status fields inside;
- single- and double-line frames;
- a visible `>` selection cursor;
- compact tabs, ledger rules, shaded meters, and explicit keycaps;
- no glossy widgets, floating cards, hamburger menus, toast stacks, or
  oversized modern headings.

Use words ordinary to the setting for content, and plain modern terms for
operating the software. A player can visit the **Tablet House** and still use
**Search**, **Save**, **Settings**, and **Close**.

### 7.2 Palette and state symbols

Retain the authored palette and formalize a redundant symbol vocabulary:

| Glyph | Pure ASCII | Meaning |
|---|---|---|
| `>` | `>` | selected row |
| `*` | `*` | unread or newly arrived |
| `!` | `!` | known block, breach, deadline, or failure |
| `?` | `?` | unknown or unresolved |
| `●` | `*` | observation under 3 fortnights old |
| `○` | `o` | observation 3–8 fortnights old |
| `·` | `.` | observation older than 8 fortnights |
| `×` | `x` | unavailable action, followed by a reason |
| `+` | `+` | queued, drafted, or newly changed |
| `✓` | `v` | satisfied, delivered, or confirmed |

Urgency is not a truth score. A deadline can be known and urgent; an alarming
claim can still be stale or self-interested.

### 7.3 ASCII art budget

Art is required where it adds identity or makes state easier to read. It is
bounded so that it cannot consume the work surface.

- Anchor/wide workbench, wide tier: at most 30% of body rows.
- Ledger workbench: at most 20%.
- Document/dossier: at most 20%.
- Help, Files, Settings, and command palette: at most one small emblem or no
  art.
- Compact tier: stateful art may use at most 15%; purely decorative art is
  removed.

Prefer art that encodes state:

- City buildings visibly decay, scaffold, close, or recover.
- Works shows the skyline/scaffold of active projects.
- Stores shows filled, empty, sealed, or spoiled vessels.
- Land shows water level, season, and field condition.
- Muster shows formation banners and empty ranks.
- World shows routes, freshness, and known movement.
- House uses its family tree as both art and data.
- Oaths show broken/lapsed seals.

Portraits identify a speaker, but a ten-row portrait must not force the
conversation or action area into a mostly blank 36-row window. Use a compact
five- or six-row portrait, or collapse it to a name/seal in standard and
compact tiers.

### 7.4 Density rules

- A standard workbench should use at least 70% of its body rows for meaningful
  content, controls, or stateful art.
- No fixed standard layout may contain more than two consecutive empty body
  rows unless a narrative document intentionally separates paragraphs.
- Long prose wraps; identifiers and numeric columns do not.
- Rows show complete critical numbers or move them to detail. They do not clip
  a quantity into a misleading value.
- Every collection shows `first–last / total`, visible scroll affordance, or
  both.
- Headers remain stable while the body scrolls.

---

## 8. Universal interaction grammar

### 8.1 Mouse

- Single click selects. Selection alone never mutates state or spends hours.
- Double click or `Enter` opens/inspects the selected entity.
- Click a column header to sort; click again to reverse.
- Shift-click extends a range and Cmd/Ctrl-click toggles individual rows where
  batch actions are legal.
- A right-click context menu may mirror common actions, but no action may
  exist only there.
- Hovering a control writes one line of plain explanation in the status bar.
  Do not rely on delayed floating tooltips.
- Scroll wheel scrolls the pane under the pointer, not whichever pane last had
  keyboard focus.
- Text selection for copying must not accidentally activate a hit region.

### 8.2 Keyboard

The following vocabulary is global unless a text field is actively editing:

| Key | Meaning |
|---|---|
| `F1` or `?` | context Help |
| `F2` | raise Hall |
| `F3` | raise Inbox |
| `F4` | raise Orders |
| `F6` | Window Switcher |
| `F8` / `Shift+F8` | tile / cascade game windows |
| `Cmd/Ctrl+Tab` | next game window |
| `:` or backtick | command palette for current context |
| `/` | focus local filter/search |
| `Up/Down` | previous/next row |
| `PgUp/PgDn` | previous/next page |
| `Home/End` | first/last row |
| `Tab/Shift+Tab` | next/previous pane or field |
| `Enter` | open, inspect, or accept the focused non-destructive control |
| `Space` | toggle row in a multi-selection; only Hall uses bare Space to advance time when no list or input has focus |
| `Esc` | cancel inline mode, then close auxiliary window |
| `Cmd/Ctrl+S` | save |
| `Cmd/Ctrl+O` | Files / load |
| `Cmd/Ctrl+,` | Settings |
| `Cmd/Ctrl+Q` | Save/Exit flow |

Contextual mnemonic keys remain printed beside actions. Typing into an active
field always wins over a mnemonic; the letter `q` in a tablet draft never
quits.

### 8.3 Selection, detail, and action bar

Every workbench follows one grammar:

```text
list or map  ->  stable selection  ->  detail/evidence  ->  visible actions
```

- The selection marker and selected entity name appear in both list and
  detail.
- Switching a filter keeps the selected entity if it remains in the result.
- Performing an action does not jump selection unless the entity genuinely
  leaves that workflow. If it leaves, select the nearest next row and state
  what changed.
- The bottom one or two rows are the action/status bar. It shows complete
  labels and attention costs, for example `[H] Hear (1h)`.
- Disabled actions remain visible when strategically meaningful and state a
  short reason: `× Read — needs 2h; 1h remains`.
- When the action bar cannot show every legal action, `[More…]` opens a compact
  action list. It is never used to hide the primary action.

### 8.4 Confirmation

Do not add a modal confirmation to routine, reversible bookkeeping.

Use an inline semantic preview for:

- sending a letter;
- a persistent or delegated order;
- marriage;
- naming or changing the heir;
- abandoning work with sunk resources;
- verdicts;
- lifting or imposing a quarantine;
- ending a fortnight with an unconfirmed draft;
- overwriting a save or exiting with unsaved actions.

The preview names the target, quantity, place, delegate, cost, known conflict,
and irreversible consequence. Confirm and Cancel are in the same window. A
parsed order never executes merely because the player pressed Enter once.

### 8.5 Feedback and recovery

Every attempted action produces one of:

1. a semantic preview;
2. a specific success line and a link to the resulting order/event;
3. a specific refusal with the unmet prerequisite and a useful next route.

Examples:

```text
Cannot read this tablet: it costs 2h and 1h remains.
Cannot begin the quay: 156 copper required; 42 is uncommitted.
“ma hadu” matches Ma'hadu harbour and the Ma'hadu garrison. Choose one:
  [1] place:ma_hadu   [2] institution:garrison_ma_hadu
```

Never use an unchanged screen, a generic beep, or “say that another way” as
the entire response when the interface can identify the missing field.

---

## 9. Information grammar

### 9.1 Claims, not omniscient values

Every strategic value shown outside an immediately inspected local object has
an information tuple:

```text
value or statement
source actor/document/inspection
observed date
received date
freshness
confidence, only when the court has a justified confidence assessment
conflicts
```

The compact table may show only a freshness glyph and source abbreviation.
The selected detail shows the full tuple. “Current” means current in Belief,
not current in World.

Examples:

```text
grain       7,573 p 20 qa   ▼ 3,025   ● own count, Nisanu II
Ma'hadu     route shut      ○ harbour master, observed 3 fn ago
plague      ?              · merchant report; conflicts with physician
```

Opening a screen never refreshes a claim. Inspection or a newly arrived report
does.

### 9.2 Common dossier

People, groups, institutions, settlements, places, routes, projects,
formations, shipments, contracts, obligations, orders, and cases share a
modeless dossier pattern:

1. identity, aliases, and type;
2. last known location/status;
3. current claims with source and age;
4. conflicting claims;
5. known relationships and obligations;
6. related documents and event history;
7. active orders, blocks, and deadlines;
8. context-legal actions.

A dossier may specialize its middle panes, but its header, provenance rows,
links, and action contract remain shared. Links open or raise another dossier
without closing the source.

### 9.3 Tables

- Column widths derive from current cells and actual content.
- Numeric columns align right and include units in the heading or value.
- Stable IDs stay out of the default presentation; they appear in detail,
  autocomplete, copy, and developer mode.
- Sorting is stable and visibly named in the title:
  `THE ROLL · sort: arrears ↓`.
- Filters are visible fields or compact toggles, never invisible modes.
- Tables with legal batch operations support multi-selection.
- A table row may have one primary inline action, but the complete action set
  belongs in the action bar/detail pane.
- Changes since the previous fortnight use signed deltas and, where useful, a
  12- or 24-fortnight sparkline. Do not put sparklines on every number.

### 9.4 Cross-reference tray

Each workbench can pin up to four entity/document references to a one-line
tray. A pinned reference survives selection changes and offers:

- **Open**;
- **Compare** with the current selection;
- **Remove**.

Compare opens the two existing documents side by side when space permits. It
does not synthesize a truth verdict. For numeric claims it aligns value,
source, observed date, and received date. For prose it shows both passages.

### 9.5 Attention

Attention appears consistently as `hours remaining / base` in the Hall and in
every action preview that can spend it. All projections read the controller's
current remaining amount, not a stale turn-start value.

Costs are attached to semantic actions in one registry. Composers, controller,
Help, command palette, terminal mode, and tests all read that registry.

---

## 10. Deterministic command palette

The 1990s text-adventure feeling should come from a capable text interface, not
from waiting for a large model.

### 10.1 Invocation and layout

Press `:` or backtick in any game window to open a compact modeless palette
near that window:

```text
┌─ COMMAND ─────────────────────────────────────────────────────┐
│ > assign chariotry to campa_                                 │
│                                                              │
│ assign <formation> to <task> [at <place>]                    │
│   formation: chariotry                                       │
│   task: campaign                                             │
│ > place: Carchemish      due: —      cost: 1h                │
│                                                              │
│ Tab complete  ↑ history  F1 full help  Enter preview  Esc    │
└──────────────────────────────────────────────────────────────┘
```

It provides:

- legal verb and synonym completion;
- context-legal entity completion by player-facing name;
- parameter prompts and units;
- one-line live validation;
- exact semantic preview before commit;
- command history and reverse search;
- examples and Help for the current verb;
- clickable suggestions and full keyboard operation;
- current-window context, so `repair this` can refer only to the explicitly
  selected institution shown in the palette.

### 10.2 Parser rules

1. Parse against the closed action grammar.
2. Resolve only legal visible affordances from Belief.
3. Accept common synonyms and optional articles.
4. Never silently choose among multiple targets.
5. Point to the unknown or incomplete part.
6. Offer valid completions, not a generic retry.
7. Show the structured action before mutation.
8. Store the structured action in replay; preserve original prose as history.

The command palette, direct controls, and terminal commands are generated from
the same `ActionDescriptor` records. This removes the current possibility that
Help teaches `[w] Works` while the controller listens for a different key.

### 10.3 Model fallback

The deterministic parser is the default and complete path. If the input does
not parse, the palette offers:

```text
I know “send” and “household troops”, but “north quickly” needs:
  task = garrison | watch | harvest | campaign
  place = one known place
[Edit]  [Show examples]  [Ask interpreter…]
```

**Ask interpreter** is explicit. It may call a small model asynchronously to
propose a structured draft, but the same validator, disambiguation, preview,
and confirmation still apply. No model output is an action.

---

## 11. Help rework

The current Palace Tutor conversation is removed from Help. Help is software
documentation and must be correct, fast, compact, and easy to keep beside the
game.

### 11.1 Window

- Default: 52 × 20 cells.
- Minimum: 40 × 15 cells.
- Modeless, resizable, and geometry-persistent.
- `F1` or `?` raises it from any screen and sets context to the focused
  window, selected entity type, and focused control.
- No portrait larger than a two- or three-row seal; preferably no portrait.
- No model call, no “thinking” state, and no in-world attention cost.

### 11.2 Layout

```text
┌─ FIELD MANUAL · CITY ───────────────────────────┐
│ Search: repair_                                 │
├─────────────────┬───────────────────────────────┤
│ CURRENT SCREEN  │ REPAIR AN INSTITUTION         │
│ > inspect       │ Select a building in City.    │
│   repair        │ [R] Repair opens an order     │
│   appoint       │ preview. Cost: 1h.            │
│   works         │                               │
│                 │ Command:                      │
│ ALL TOPICS      │ repair <institution>          │
│   correspondence│ Example: repair tablet house  │
│   kingdom       │                               │
│   court         │ Related: Works, Appointments  │
├─────────────────┴───────────────────────────────┤
│ ↑↓ topic  Enter follow  / search  Esc close     │
└─────────────────────────────────────────────────┘
```

### 11.3 Content

Help is built from the action and screen registries:

- current keys and clickable controls;
- exact command syntax;
- cost and prerequisites;
- direct click path;
- examples using current legal names when helpful;
- “what this screen means” without strategic prescriptions;
- links to related windows and dossiers;
- a complete searchable action index;
- a short first-fortnight tutorial transcript.

Search is incremental substring/token search over authored records. Results
appear within 50 ms for the current corpus. The same registry test fails if an
enabled action, visible key, direct click path, or command verb lacks Help.

### 11.4 Strategy advice is not Help

Help answers “How do I assign troops?” It does not answer “Should I send the
chariotry?” Strategic advice belongs to a named, fallible adviser in Counsel
and is visibly attributed.

---

## 12. Counsel rework

Counsel becomes a compact place to ask a person, understand a draft order, and
see attributed advice. It is not the universal control surface and it is not a
large chat client.

### 12.1 Window

- Default: 64 × 22 cells.
- Minimum: 50 × 17 cells.
- Compact five- or six-row portrait only in wide/high layouts.
- Conversation scrollback uses the available body instead of reserving blank
  rows.
- The bottom always contains a ready input line, state/cost line, and actions.
- Direct links in an answer open the cited document or dossier.

### 12.2 Three kinds of input

1. **Known factual question.** Deterministic authored projection answers
   immediately from the adviser's Belief, including source and uncertainty.
2. **Order.** The same deterministic command grammar produces a semantic
   preview. Counsel adds voice around the preview but cannot change it.
3. **Open-ended advice.** An immediate short rule-based/adviser-authored answer
   appears. The player may explicitly request **Elaborate** for optional model
   prose.

Questions and advice remain fallible because the adviser uses personal Belief
and interests, not because the interface randomly corrupts command semantics.

### 12.3 Advice card

Counsel's recurring advice is a small attributed card, not an auto-generated
conversation:

```text
YABNINU'S VIEW
“The oldest petition is becoming a public insult.”
Basis: petition register, observed this morning
Uncertainty: neither side has been heard
[Open case] [Draft: hear case] [Dismiss advice]
```

Advice is generated at most:

- once at the beginning of a fortnight;
- when the player explicitly asks;
- when a materially new known exception crosses a deterministic threshold.

It never fires on every screen open, selection change, or repaint.

### 12.4 Busy behaviour

If **Elaborate** or **Ask interpreter** invokes a model:

- the immediate fallback remains visible;
- a one-line `Yabninu is composing a longer answer… [Cancel]` appears;
- the player may continue using every window;
- only the requesting card/input is marked busy;
- completion adds a note without stealing focus;
- timeout or failure quietly retains the fallback and states
  `No longer answer was produced`;
- repeated Enter cannot queue duplicate requests.

---

## 13. Screen specification — Hall and shared work surfaces

### 13.1 Hall

**Purpose:** answer “What changed, what is waiting, what is due, and where do I
go?” Hall is an exception docket and physical audience, not an omniscient
optimization dashboard.

**Default:** 92 × 34. **Minimum:** 72 × 26.

```text
┌─ THE HALL ─ AMMURAPI · Nisanu II · 10/10h · sea SHUT · saved 09:14 ─────┐
│ MATTERS BEFORE THE KING                         │ QUICK LEDGERS          │
│ >! Judgement waiting 5 fn      petitioner ●    │ grain  7,573p ▼3,025  │
│  * Five unread tablets         oldest 4 fn     │ unrest 0   standing 700│
│  ! Two offices vacant          city register ● │ inbox 5 unread          │
│  ○ Granary claim is falling    scribe, 1 fn    │ orders 2 active / 1 !   │
│                                                 │ routes sea shut         │
│ SELECTED: Boundary petition · Ashiranu          ├─────────────────────────┤
│ Raised 5 fn ago. Neither party heard.           │ OPEN WINDOWS            │
│ Evidence: petition:boundary…  No known deadline │ Hall · Inbox · Tablet   │
│ [O] Open  [H] Hear (1h)  [D] Delegate  [P] Pin │ [F6] switch             │
├─ WAITING IN THE HALL ───────────────────────────┼─ PLACES ────────────────┤
│ Ashiranu · boundary claim · 5 fn                │ Inbox  Orders  Counsel  │
│ Abdi-Anu · shipwright · 2 fn                    │ Stores Roll Land City   │
│ courier from Carchemish · unread, new           │ Muster Oaths House ...  │
│ 1–7 / 7                                         │                        │
├─────────────────────────────────────────────────┴─────────────────────────┤
│ [Enter] open  [P] pin  [F] defer  [:] command  [Space] end fortnight     │
└───────────────────────────────────────────────────────────────────────────┘
```

Requirements:

- Matters show source/freshness and age/deadline in the row.
- Selection expands evidence and legal actions without leaving Hall.
- Advice, when present, is quoted and attributed:
  `Yabninu: “I would hear them.”`; never `Do: hear them`.
- Clicking a matter selects it. Double-click or **Open** opens evidence.
  Clicking a recommendation may prefill a draft but never execute it.
- Waiting people and couriers link to their petition, tablet, dossier, or
  summons.
- Quick ledgers are compact known indicators and open the corresponding
  workbench. They are not raw World values.
- Open windows lists the three most recent plus the Window Switcher.
- Space advances time only when Hall itself has focus and no list multi-select,
  filter, input, or inline preview is active.
- Ending the fortnight opens an inline summary of unspent hours, unresolved
  urgent matters, unsent drafts, and pending order previews. The player can
  still proceed.

### 13.2 Orders workbench

**Purpose:** inspect and manage every draft, confirmed order, mission, standing
order, and execution exception.

**Default:** 88 × 30. **Minimum:** 66 × 22.

Panes:

- filter tabs: Draft / Active / Blocked / Completed / All;
- table: status, subject, delegate, destination, last report, next review;
- selected semantic detail: trigger, bounds, quantity, budget, authority,
  dispatch/receipt state, execution, linked reports;
- action bar: confirm, amend, revoke, duplicate, contact delegate, open
  evidence/dossiers.

This is the authoritative history of player intent. Counsel and direct
controls create drafts here; they do not maintain separate order histories.
Blocked orders link to the known reason and responsible person/place.

### 13.3 Dossier window

**Purpose:** common inspection surface for any entity.

**Default:** 62 × 25. **Minimum:** 46 × 18.

Tabs are type-dependent but use stable names: Summary, Claims, Relations,
Documents, Orders, History. Opening a foreign dossier never refreshes it.
Multiple dossiers can remain open for comparison.

### 13.4 Window Switcher

**Purpose:** make a many-window game manageable.

**Default:** 42 × 17.

It shows numbered open windows in recent-use order:

```text
> 1 Hall
  2 Inbox · 5 unread
  3 Tablet · Carchemish · unsent reply
  4 Stores · grain selected
  5 Institution · tablet house
```

Click/Enter focuses; Delete or `X` closes an auxiliary window; `T` tiles;
`C` cascades. Dirty drafts require an inline Save/Discard/Cancel choice.

---

## 14. Screen specification — correspondence

### 14.1 Inbox

**Purpose:** triage, read, compare, respond to, delegate, and archive incoming
correspondence without losing selection.

**Default:** 90 × 30. **Minimum:** 66 × 22.

Wide/standard layout:

- left 32–36 columns: scrollable tablet list;
- right: selected metadata, full body or unread cost, related items, and
  actions;
- tabs: Unread, Needs action, Delegated, All, Archive, Outbox;
- filters: sender, subject, age, status; stable sort;
- visible `first–last / total`.

Rows show unread/urgent glyph, sender, compact subject, age, and response
state. The selected row never disappears merely because reading changed it
from unread to read. It remains selected and visible until the player moves or
changes filter; if the active Unread filter would exclude it, retain it as a
temporary dimmed row labeled `just read` until selection moves.

Actions:

- **Read (2h)**;
- **Open detached**;
- **Answer**;
- **Delegate request**;
- **Acknowledge**;
- **Compare**;
- **Conversation**;
- **Sender dossier**;
- **Pin**;
- **Archive / Restore**.

Reading shows the body in the same window. Answer opens or raises Desk while
the letter remains visible. Delegate creates a structured draft linked to the
tablet. Compare opens related claims/documents without deciding which is true.

### 14.2 Tablet document

**Purpose:** persistent primary-source reading and cross-reference.

**Default:** 60 × 25. **Minimum:** 46 × 18.

Header:

- sender and seal;
- sender's date string;
- observed/sent/received dates where known;
- read/answer/delegation/archive status;
- attention cost before first reading.

Body scrolls with a position indicator. A compact side or bottom block lists
asserted figures and related known claims, not hidden truth. Actions mirror
Inbox and include **Copy passage** for player notes/debugging. Multiple tablets
can remain open.

### 14.3 Desk

**Purpose:** compose an exact outgoing tablet while its source and diplomatic
forms remain inspectable.

**Default:** 66 × 28. **Minimum:** 52 × 20.

Panes/fields:

- recipient, thread, intent, subject;
- editable body with cursor, selection, undo/redo, and scroll;
- protocol checklist with exact failed form and player-facing consequence;
- immediate authored formulae;
- related source tablet link;
- Outbox status after sealing.

Actions:

- choose intent/template;
- dictate/edit exact text;
- save draft;
- compare source/thread;
- validate forms;
- seal and send (inline preview, 2h);
- discard draft.

No model is needed to type, edit, grade, preview, or send. An optional
**Embellish** action may asynchronously propose alternate prose in a side-by-
side diff. It never replaces the player's current draft without acceptance.

### 14.4 Outbox and conversation

Outbox is an Inbox tab, not a separate giant window. It shows Draft, Sealed,
Courier assigned, In transit, Delivered if known, Intercepted if known, and
Answered. A conversation view interleaves sent and received documents by
known dates and preserves uncertain delivery state.

---

## 15. Screen specification — kingdom management

### 15.1 Stores

**Purpose:** understand counted stock, movement, reservations, spoilage, and
the bronze/melt chain; issue stock-specific decisions.

**Default:** 76 × 26. **Minimum:** 58 × 20.

Top art uses at most five rows of stateful jars, bins, or granary bays.
The table shows:

```text
good        known amount       Δ 12fn   source/age   reserved
grain       7,573p 20qa      -3,025     ● own count     1,400
seed        0p 0qa                —      ○ scribe        —
```

Selected detail shows recent inflows/outflows, spoilage, committed quantities,
last inspection, conflicting reports, and links to shipments/groups.

Actions:

- inspect selected ledger/count (with cost);
- compare a reported figure to another document;
- open seed for food;
- reserve/release goods when the order system supports it;
- open melt ledger and bronze-in-use detail;
- draft purchase, transfer, or allocation order where the world model supports
  it.

### 15.2 Roll

**Purpose:** manage rations, pay-down priority, labour assignment, arrears, and
the groups whose work sustains the court.

**Default:** 82 × 28. **Minimum:** 62 × 21.

Table columns: group, heads, due, allocated, paid last turn, arrears, loyalty
band, task, source/age. Selection opens group detail and payment history.

Direct actions:

- edit allocation with numeric field and units;
- raise/lower allocation by useful increments;
- move selected groups up/down in payment priority;
- multi-select groups and send to/recall from harvest;
- open group dossier;
- compare allocation, last payment, and current claim.

Reordering and allocation show projected bookkeeping semantics, not guaranteed
future loyalty or production outcomes.

### 15.3 Land

**Purpose:** connect season, water, seed, estate labour, dues, canals, and
harvest claims.

**Default:** 80 × 28. **Minimum:** 60 × 21.

The stateful art band shows season, river gauge, and field/water condition in
no more than six rows. The estate table shows place, crop/water type, reported
condition, labour supplied/needed, canal state, last yield, and source/age.

Direct actions:

- inspect seed or granary;
- send/recall selected work groups;
- raise corvée;
- allocate dredging days to selected estate;
- set land due with an inline numeric preview;
- open estate/place/group dossier;
- open Stores, Roll, Works, or the associated report.

### 15.4 Muster

**Purpose:** see formations, their real commitments as known, readiness claims,
locations, equipment, and summons; assign them without leaving the screen.

**Default:** 80 × 27. **Minimum:** 60 × 20.

The table shows formation, men, task, place, reported readiness/equipment,
commander, and source/age. A summons block shows issuer, required men, mustering
place, due date, sent amount, and linked oath/tablet.

Direct actions:

- assign selected formation to garrison, watch, harvest, or campaign;
- choose a place from current legal destinations;
- multi-select formations for the same compatible assignment;
- appoint/dismiss commander;
- open summons, oath, formation, place, or commander dossier;
- draft response to the summoning tablet.

### 15.5 Oaths and obligations

**Purpose:** inspect exact clauses, parties, deadlines, performance claims, and
succession status; act on the obligation.

**Default:** 78 × 28. **Minimum:** 58 × 20.

Left: oath/obligation list with standing, lapsed, breached-as-reported, due, or
unknown status. Right: seal, parties, witnesses/deities, exact clauses, known
performance, related orders/documents, and source history.

Direct actions:

- re-swear a lapsed oath;
- draft an order to satisfy a clause;
- expiate against a selected oath;
- compare the current copy to archive copies;
- open party, shipment, formation, rite, or document;
- pin deadline in Hall.

The UI never marks an expiation “correct” or an oath as the objective
supernatural cause of an event.
