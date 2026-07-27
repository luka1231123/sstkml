# The Palace Desktop — windows, typography, and placement

- Status: working implementation specification
- Revision: 2026-07-28
- Milestone: M13.0
- Authority: subordinate to [SPEC.md](SPEC.md). Where this document and
  `SPEC.md` disagree, `SPEC.md` wins.

---

## 1. Why this document exists

`SPEC.md` §8.8 states the palace desktop contract in twenty-eight lines. It
says what must be true — 11-point default type adjustable 9–20, layout that
recomposes rather than scaling a bitmap, windows that remember geometry and
reopen without resetting work — but it does not say which numbers to hit.

The numbers exist in exactly one place:
`docs/archive/2026-07-28/plans/UI_UX_REWORK_SPEC_M12-final.md`, 1509 lines,
SHA-256 `3b2397d7…95c721`, matching the checksum pinned by the archive README.
That file is complete and unmodified. The root `UI:UX_Specs.md` is a truncated
copy of its first 3,948 bytes — a byte-identical prefix that stops mid-section
3 — and is not a second document.

The archive README demotes M12-final to "historical evidence, not current
authority". That is correct as policy: its screen inventory is pre-M13, and
much of it (the Orders workbench, the full dossier grammar, generated
institutions) belongs to M13.1 and later. But its measurements do not conflict
with `SPEC.md` — every number in §8.8 matches it, and it is a strict superset.

So this document takes `SPEC.md` §8.8 as the binding contract and M12-final's
tables as the concrete design wherever §8.8 is silent, rather than inventing
sizes. It covers the window and typography layer only.

## 2. What is already built

M13.0's interaction debt (`SPEC.md` §4.4) is substantially closed. The suite
stands at 388 passing, with one pre-existing unrelated failure in
`test_m12.test_a_building_site_takes_the_hands_the_fields_wanted`. Inbox
read/answer/delegate/compare/archive, openable archive results, the melt
ledger, summons and deadlines, relations and disease dossiers, chosen ritual
subjects, counsel order preview, visible refusals, off-thread model work, and
the data-driven World view all exist and are covered by
`tests/test_m13_ui_foundation.py`, `test_m13_correspondence.py`, and
`test_m13_world_view.py`.

What is not built is the window layer itself.

## 3. Scope

Four deliverables.

1. **Typography.** `tui/backend_tk.py` hardcodes 14-point and has no scaling
   path. Move to an 11-point default over a 9–20 range in one-point steps,
   bound to `Ctrl/Cmd +`, `Ctrl/Cmd -`, and `Ctrl/Cmd 0`, persisted.
2. **Recomposition.** Every window size is a hardcoded literal in
   `play_gui.Game.compose` (104×36, 108×36, 92×36, …). Windows must recompute
   their cell capacity when resized or when the font changes, recompose at the
   new size, and clamp to a class minimum rather than clipping. No bitmap is
   ever scaled.
3. **Placement and persistence.** There is no geometry storage of any kind.
   Remember geometry per window, clamp restored windows to visible monitors,
   and reopen without resetting selection, filter, sort, or scroll.
4. **Switcher and tiling.** Neither exists. Add the Window Switcher plus `F6`,
   `F8`, `Shift+F8`, `Ctrl+Tab`, and `F2`.

Out of scope, deferred to M13.1+: the Orders workbench, the generalized entity
dossier, the Settings screen, the Files screen, the Help and Counsel content
reworks, and M12-final §19's normative action-and-click-path map. This
document changes how windows behave, not what they say.

## 4. Typography

- Default 11-point monospace; range 9–20 in one-point steps.
- `Ctrl/Cmd +` enlarges, `Ctrl/Cmd -` reduces, `Ctrl/Cmd 0` restores 11.
- Font size, family, pure-ASCII preference, and geometry persist across runs.
- Changing size holds the window's pixel rectangle steady and recomputes how
  many cells fit inside it, then recomposes. Larger type therefore means fewer
  cells and a simpler layout, never a magnified image.
- Retain the existing `FONT_STACK` fallback chain and its guarantee that an
  unknown family cannot silently become proportional.
- Every colour-coded state keeps a glyph or word, as today.

## 5. Window classes

Classes come from M12-final §6.

| Class | Default | Minimum |
|---|---:|---:|
| Anchor | 92 × 34 | 72 × 26 |
| Wide workbench | 88 × 30 | 66 × 22 |
| Ledger workbench | 78 × 27 | 58 × 20 |
| Document / dossier | 62 × 25 | 46 × 18 |
| Compact utility | 52 × 20 | 40 × 15 |
| Command palette | 68 × 15 | 48 × 11 |

Per-window assignment, with the per-screen sizes M12-final gives. The
`Current` column is what `play_gui.py` opens today.

| Window key | Screen | Current | Default | Minimum |
|---|---|---:|---:|---:|
| `hall` | Hall | 104 × 36 | 92 × 34 | 72 × 26 |
| `stack` | Inbox | 108 × 36 | 90 × 30 | 66 × 22 |
| `city` | City | 96 × 36 | 96 × 34 | 70 × 24 |
| `world` | World | 86 × 30 | 90 × 30 | 68 × 22 |
| `justice` | Justice | 90 × 34 | 84 × 29 | 64 × 22 |
| `house` | House | 86 × 34 | 82 × 29 | 62 × 22 |
| `relations` | Relations | 92 × 32 | 82 × 28 | 62 × 21 |
| `archive` | Archive | 84 × 32 | 78 × 28 | 58 × 20 |
| `works` | Works | 82 × 32 | 82 × 28 | 62 × 21 |
| `plague` | Health | 78 × 28 | 78 × 27 | 58 × 20 |
| `roll` | Roll | 78 × 22 | 82 × 28 | 62 × 21 |
| `land` | Land | 70 × 24 | 80 × 28 | 60 × 21 |
| `muster` | Muster | 62 × 18 | 80 × 27 | 60 × 20 |
| `oaths` | Oaths | 76 × 28 | 78 × 28 | 58 × 20 |
| `stores` | Stores | 62 × 22 | 76 × 26 | 58 × 20 |
| `desk` | Desk | 84 × 30 | 66 × 28 | 52 × 20 |
| `altar` | Altar | 78 × 32 | 68 × 24 | 52 × 18 |
| `counsel` | Counsel | 92 × 36 | 64 × 22 | 50 × 17 |
| `fortnight` | Chronicle | 66 × 18 | 66 × 22 | 50 × 17 |
| `help` | Help | 100 × 38 | 52 × 20 | 40 × 15 |
| `institution:*` | Institution | 68 × 22 | 62 × 24 | 46 × 18 |
| `letter:*` | Tablet | — | 60 × 25 | 46 × 18 |
| `archive:*` | Tablet | — | 60 × 25 | 46 × 18 |
| `switcher` | Switcher | — | 42 × 17 | 40 × 15 |

No auxiliary window opens larger than 80% of usable monitor width or height
unless it is restoring the player's own saved geometry.

Help drops from 100 × 38 to 52 × 20 and Counsel from 92 × 36 to 64 × 22. Only
the window shrinks here; the content rework is M13.1 and both screens must
still compose legibly at the smaller size, which §6 exists to guarantee.

## 6. Responsive tiers

| Tier | Width | Behaviour |
|---|---:|---|
| Wide | 88+ | list, detail, and context rail coexist |
| Standard | 68–87 | list/detail split; actions at the bottom |
| Compact | 52–67 | panes stack or switch with Tab; art shrinks |
| Minimum | below 52 | one pane at a time; actions stay reachable |

Height bands: 28 and above keeps full art and history; 20–27 reduces art;
15–19 drops decorative art and scrolls content.

On contraction, remove in this order: decorative sky, borders, shadows, and
portraits; then redundant prose; then lower-priority columns, moved into the
detail pane; then optional history length. **Never** remove selection,
provenance, cost, enabled actions, scroll position, or focused input.

Below the class minimum, refuse to shrink rather than clip.

## 7. Placement and persistence

- Open next to the source window when a free rectangle exists.
- Never fully cover the selected source row or document.
- Reopening raises the existing workbench without resetting its state.
- Entity windows are keyed by ID, so a second tablet is a second window.
- Remember geometry, monitor, selection, filter, sort, and scroll.
- Clamp restored geometry to the monitors actually attached, so a window saved
  on a display that is now gone still opens somewhere visible.
- The Hall owns the session; closing it uses the visible save/exit flow.

Selection and scroll already live on the `Game` controller rather than on the
windows, so closing and reopening a window preserves them today. This is a
property worth a regression test, not new code.

## 8. Switcher and bindings

The Window Switcher, 42 × 17, lists open windows with a one-line state note:

```text
> 1 Hall
  2 Inbox · 5 unread
  3 Tablet · Carchemish · unsent reply
  4 Stores · grain selected
  5 Institution · tablet house
```

`Enter` focuses, `X` closes an auxiliary window, `T` tiles, `C` cascades. A
window holding a dirty draft requires an inline Save / Discard / Cancel before
it closes.

| Key | Action |
|---|---|
| `F2` | raise the Hall |
| `F6` | open the Window Switcher |
| `F8` | tile |
| `Shift+F8` | cascade |
| `Ctrl+Tab` | cycle windows |
| `Ctrl/Cmd +` `-` `0` | font larger, smaller, reset |

## 9. Architecture

**`tui/desktop.py`, new, no Tk import.** Window classes and their sizes, the
per-window assignment table, `tier()` and height bands, minimum clamping,
monitor clamping, and the tiling and cascade rectangle maths — all pure
functions over plain integers. This mirrors how `tui/grid.py` keeps rendering
assertable without a display, and it is what lets the geometry logic be tested
in the headless suite rather than only in front of a screen.

Preferences load and save here too: font size, family, pure-ASCII flag, and a
geometry map keyed by window key, written to `saves/settings.json`. A corrupt
or absent file falls back to defaults silently; a settings file must never
stop the game from starting.

**`tui/switcher.py`, new.** `compose(entries, pick, width, height)` returning
an `InteractiveScreen` with hit regions, exactly like the other composers, so
the switcher is testable as cells.

**`tui/backend_tk.py`.** Default `font_size` 11. Hold the font as a real
`tkfont.Font` so cell metrics can be measured. Add `set_font_size`, geometry
read/write, and a `<Configure>` handler that converts the pixel rectangle into
a cell capacity, clamps it to the window's class minimum, and calls back into
the controller to recompose when the capacity actually changes. `App` gains
tiling, cascade, cycling, and an inventory of open windows for the switcher.

**`play_gui.py`.** Replace the hardcoded sizes in `compose` with a lookup of
each window's live cell capacity, falling back to the class default. Bind the
new keys. Load preferences at start-up and save geometry on change and on
exit.

## 10. Verification

Headless, in `tests/test_desktop.py`:

- every window class default is at or above its own minimum;
- clamping refuses to go below the minimum instead of clipping;
- restored geometry off the edge of a monitor lands back inside it;
- tiling produces non-overlapping rectangles that cover the work area;
- cascade offsets monotonically and stays inside the work area;
- `tier()` and the height bands return the documented boundaries;
- preferences round-trip, and a corrupt settings file yields defaults;
- the switcher composes with correct hit regions and marks the focused window;
- every screen in the table composes without error at both its default and its
  minimum size — this is the real guard on the responsive claim.

With a display, extending `tests/test_window.py`:

- a font change holds the pixel rectangle and changes the cell capacity;
- a resize triggers exactly one recomposition at the new capacity;
- geometry survives close and reopen;
- closing and reopening a window preserves selection, filter, and scroll.

Coexistence, from M12-final §6, verified at the default font: Hall and Help
together at 1440 × 900; Tablet and Stores together at 1366 × 768; Inbox and a
detached tablet readable together at 1440 × 900; City and an institution
detail readable together at 1440 × 900; and at 20-point type every action
still reachable through reflow, pane switching, or scrolling.

## 11. Definition of done

The player can set type from 9 to 20 points and every screen stays legible and
complete; windows can be resized freely and recompose instead of clipping or
scaling; the desktop remembers where everything was and reopens it without
losing work; and the Hall, Help, a ledger, and a tablet can be read side by
side on an ordinary laptop display.
