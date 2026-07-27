# SAY TO THE KING, MY LORD

An information-constrained rulership simulation set in a fragile Late Bronze
Age world. People, goods, labour, institutions, journeys, disease, obligations,
and reports are calculated deterministically. The player holds the system
together through fallible people and delayed, interested information—not an
omniscient strategy layer.

[SPEC.md](SPEC.md) is the single current design authority. Superseded specs,
plans, decisions, and status records are preserved under
[`docs/archive/2026-07-28`](docs/archive/2026-07-28/README.md). Git is the
archive for retired code; obsolete implementations are not kept importable.

## Current state

M13.0 establishes the honest one-city foundation:

- staffed, headed institutions consume upkeep and lose output when neglected;
- agriculture, workshops, formations, corvée, and projects draw from finite
  labour and material records;
- disease follows authored introduction and modeled contact, while quarantine
  holds actual movement;
- rites and divination affect human decisions and institutions, never hidden
  supernatural physics or privileged future knowledge;
- correspondence supports read, compare, answer, delegate, file, reopen, and
  Outbox/transit workflows;
- Stores, Muster, Relations, Sickness, House, City, World, and the archive are
  available in the windowed game;
- saves are version 13, atomic, replay-verified, and preserve remaining
  attention;
- causal auditing and a pinned foundation benchmark guard conservation and
  accidental performance regressions.

M13.1 adds the world kernel beside it:

- Region, Polity, Settlement, Site, Route, Cohort, and Organization entities,
  with identifiers derived from a stable parent, turn, domain, and local
  ordinal rather than from any world-wide counter;
- goods held as lots whose owner and holder are separate, where every change
  leaves a transfer record and the ledger alone accounts for the world total;
- obligations with closed clause kinds, a lifecycle, and consequences the
  parties believe rather than effects the engine applies;
- a fortnight run as spec 6.1's phases, with every settlement crossing each
  phase together and one global allocation of everything exclusive;
- actor Belief: dated, sourced claims that keep their conflicts, read by
  policies that take `(actor, belief)` and never the world;
- Ma'hadu and an Alashiyan port producing, consuming, deciding, and changing
  with Ugarit idle — and identically with Ugarit deleted outright.

Ugarit itself is still the detailed pre-kernel `Court`, kept as the
`legacy_court` adapter until the M13.2 grain slice replaces it. Kernel
production is not yet seasonal; the sowing-to-threshing chain is M13.2's.

The wider world is not finished. Foreign settlements still need trade,
transport, credit, envoys, standing orders, and the generated institutions
specified for M13.2–M13.6. M14 builds displacement and conflict on that state;
M15 authors scenario starts; M16 finishes and ships the game. There is no M17.

## Run

```sh
./run.sh                  # windowed game
./run.sh --cli ugarit     # terminal game
./run.sh --check          # interpreter, Tk, and display check
./run.sh --screens all    # render every screen as text
./run.sh --probe          # live Tk probe
```

`run.sh` uses the project `.venv`, creating it when absent. The windowed backend
requires Python with Tk support.

Windowed controls are printed in the Hall. `Space` ends the fortnight,
`Ctrl-S` saves, `Ctrl-O` asks before reloading the autosave, `?` opens grounded
Help, and `Q` quits. The optional local model may phrase or interpret text, but
it cannot read hidden World state, perform arithmetic for the engine, or mutate
the simulation.

## Verify

```sh
./run.sh --test
.venv/bin/python tools/corpus_lint.py
.venv/bin/python tools/m13_audit.py
.venv/bin/python tools/m13_benchmark.py
.venv/bin/python tools/balance.py prudent 96
.venv/bin/python tools/kernel_inspect.py where grain
```

`tools/kernel_inspect.py` is the developer's causal inspector (spec 7.5): it
answers why a lot exists, where a quantity went, why an actor chose what it
chose, what evidence a belief rests on, what an obligation authorized, and who
asked for something and did not get it. It is omniscient and never
player-facing, and it works by replaying the deterministic world rather than by
keeping a causal log in the save.

The engine is standard-library-only, integer-state, immutable, seeded, and
replayable. `belief/` is the only World-to-player projection boundary.

## Repository map

```text
engine/   World state, actions, causal systems, tick, and records
engine/kernel/  snapshot, intents, one global allocation, the phased turn
belief/   safe, dated player projections
ai/       optional validated language layer and grounded Help
tui/      shared character-cell UI and Tk/terminal backends
content/  scenario, historical prose, rules, and correspondence
tools/    tests, audit, benchmark, balance, screens, and probes
SPEC.md   unified purpose, contracts, historical stance, and roadmap
```
