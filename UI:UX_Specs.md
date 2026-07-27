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
