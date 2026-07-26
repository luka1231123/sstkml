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

## Play

```sh
python3 play_cli.py ugarit          # optional: <scenario> <seed>
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

```sh
python3 -c "import tests.test_m1 as t; t.test_replay_matches(); \
t.test_grain_is_conserved(); t.test_arrears_monotone_under_zero_allocation()"
```

(Or `pytest` if installed.)

## Layout

```
engine/   stdlib only. core, state, actions, reduce, tick, systems.
belief/   World -> Belief projection (plain dicts; the only thing UI/AI read).
ai/       (M4+) Ollama client, parser, composer, grader, numeric guard.
tui/      rendering + command parsing.
content/  authored TOML: scenarios, months, (later) goods, routes, decks, corpus.
load.py   content -> initial World.  session.py  headless driver + save/replay.
```
