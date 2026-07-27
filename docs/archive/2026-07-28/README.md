# Documentation archive — 2026-07-28

This directory preserves the project records superseded by the unified
[SPEC.md](../../../SPEC.md). They are historical evidence, not current
authority.

The archived bytes are pinned by these post-relocation SHA-256 checksums:

| Archived file | SHA-256 |
|---|---|
| `specs/SAY_TO_THE_KING_spec.md` | `0d6ec34522bdc6bd88d6cd1321857a9842729e0c88714f394d7419890d8aa375` |
| `project-records/DECISIONS.md` | `392eb9d2d20a0d4028437368da4540b306e9b0acaaed3076e9581372784ccc10` |
| `project-records/STATUS.md` | `34b14f9c2493fd5d645d1fe70d362e0313e55aed039ff2a4bea0b7cec14e585f` |
| `plans/TUI_REWORK_PLAN.md` | `1b0f1a09f62b39ee56eaae6d84020595618a813c118d40b7bf1bf8feb74ad404` |
| `plans/LETTERS_REDESIGN.md` | `a295436ca0db8b89ab36bd80fd210d9cec1ac16cea3976eca61941715b4a5e07` |
| `plans/UI_UX_REWORK_SPEC.md` | `25ff532d0a7eb027bff34c028572bbf3c8f30b8874398e7d7806fc2acc08a457` |
| `plans/UI_UX_REWORK_SPEC_M12-final.md` | `3b2397d7e071bc62d474bdbb1125677e755dcff54ddde2f51ae6c3ea4995c721` |

## Contents

- `specs/` — the original implementation specification.
- `project-records/` — the append-only decision history and rolling status
  snapshot, including uncommitted work present at consolidation.
- `plans/` — implemented or parked standalone interface plans, including the
  final M12 UI working specification captured after the initial consolidation.

The current design, milestone gates, technical contract, and roadmap live only
in the repository-root [SPEC.md](../../../SPEC.md).

## Retired source paths

Obsolete source is not duplicated under this documentation tree: Git is the
code archive, so a retired implementation cannot remain importable by accident.
The M13.0 cleanup removed these paths from the working runtime:

| Retired path at baseline `e87b5dc` | Current replacement |
|---|---|
| `tui.document.stack` | `tui.inbox.compose` and `Game.on_inbox_key` |
| `tui.document.house` | `tui.household.compose` and `Game.on_house_key` |
| `Game.on_tablet_key` numeric Stack branch | the integrated Inbox selection/read workflow |

Use `git show e87b5dc:tui/document.py` and
`git show e87b5dc:play_gui.py` to inspect the exact retired code. This ledger is
the index; repository history is the intact copy.
