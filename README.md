# SAY TO THE KING, MY LORD

A terminal game about ruling a Late Bronze Age kingdom through its archive.
Deterministic simulation core (stdlib only); a local language model will later
sit on top as an interpretation and prose layer that never touches state.

See `SAY_TO_THE_KING_spec.md` for the full design and `DECISIONS.md` for how the
build deviates from it.

## Status

- **M0 — determinism spine.** RNG substreams, calendar, integer-only state,
  canonical JSON + hashing, save/load/replay with field-level divergence checks.
- **M1 — the core loop.** Attention, stores + spoilage, rations, arrears,
  dependents, unrest, rites. Playable in command mode; a 60-turn famine you lose
  by choosing who to let starve.
- **M2 — letters and latency.** Routes, couriers, leg-by-leg transit, the closed
  sea and the spring flood, the schedule, correspondents on cadence, the STACK
  screen, reading (costs hours), and template replies from the desk. The pile
  outgrows the audience budget; the famine now writes to you by name.
- **M3/M4 — belief and interpretation.** Scribe distortion, ledger inspection,
  the archive, a numeric guard, deterministic prose pre-parser, and an optional
  validated Ollama parser. Invalid or unavailable model output never reaches state.
- **M5 — the desk.** Authored diplomatic formulae, deterministic protocol
  grading, guarded composition with offline fallback, raw player dictation,
  splitting, burning, and exact sent-text replay.
- **M6 — relations and oaths.** Status claims, delayed gifts and gossip,
  unanswered-letter decay, delivery-time protocol consequences, readable oath
  clauses, hidden divine liability, and deterministic misfortune.

## Play

```sh
python3 play_cli.py ugarit          # optional: <scenario> <seed>
python3 play_cli.py ugarit --no-ai  # deterministic command mode only
```

Type `help` at the prompt. Everything is reachable by command; there is no GUI
requirement and no model dependency.

## Run headless / replay

```python
from session import play, save, replay
world, log, hashes = play(8814402919, "ugarit", [[] for _ in range(60)])
save("save.json", 8814402919, "ugarit", 60, log, world)
replay("save.json")   # rebuilds from seed, refuses on hash divergence
```

## Tests

Run `pytest` if installed; the test modules are also plain functions and require
no runtime dependencies.

```sh
python3 tools/corpus_lint.py
```

## Layout

```
engine/   stdlib only. core, state, actions, reduce, tick, systems, relations.
belief/   World -> Belief projection (plain dicts; the only thing UI/AI read).
ai/       optional Ollama client, parser/composer, numeric guard, protocol grader.
tui/      rendering + command parsing.
content/  authored TOML: scenarios, months, relations, routes, decks, corpus.
load.py   content -> initial World.  session.py  headless driver + save/replay.
```
