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
- **M7 — the voicer.** Correspondents now lie in their own interest: the engine
  distorts each asserted figure at the source by `report_bias` and keeps the
  truth off the tablet and out of the prompt. Persona cards give each sender a
  voice; bodies generate in the background in Stack order and fall back to
  authored templates instantly, so nothing ever waits on the model. The prompt
  boundary is enforced by a function, not a convention.
- **M8 — land and metal.** The climate series is fixed at scenario start, so a
  bad year was always going to be a bad year. Grain comes off a threshing floor
  once a year through an opaque yield formula the player never sees; he reasons
  from a gauge reading, his overseers' self-interested letters, and last year's
  number. Labour, corvee and canals are his levers. Meanwhile tin runs out, the
  workshops go on meeting demand by melting down what already exists, and the
  chariotry quietly stops being replaceable. Nothing announces that.
- **M9 — house and cult.** The family is a cast of people who age, marry, bear
  children, and die, and the succession is recomputed from them every turn. A
  daughter married abroad becomes a correspondent with her own loyalties and her
  own report bias. When the king dies, every oath he swore lapses — not broken,
  simply void, because the man who swore is dead — the regnal year resets to 1,
  and somebody has to travel and swear again. The diviner reads a future that
  was already fixed at scenario start and misreports it by competence, loyalty
  and interest; nothing in the archive ever tells you whether he was right.
- **M10 — plague and the archive puzzle.** An integer epidemic arrives off a
  courier from somewhere that already had it, and quarantine works — at the cost
  of the trade, the correspondent's goodwill, and the letters that would have
  told you anything. Meanwhile the gods are angry about one specific broken
  promise, and the engine will not say which. Two of the vows in your archive
  have been in breach since before you were born, because they name festivals
  that fell off the calendar when somebody recopied it badly and left out what
  he could not read. You search the tablet house an hour at a time, you make an
  offering against your best guess, and nothing ever tells you whether it was
  accepted. The epidemic curve is the only answer you get.

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

The tests are plain functions with plain asserts, so pytest is a convenience and
not a dependency:

```sh
python3 tools/run_tests.py            # all milestones
python3 tools/run_tests.py m7:voicer  # filter by module and test name
python3 tools/corpus_lint.py
python3 tools/balance.py prudent      # or `passive`; spec 10.4's harness
```

## Layout

```
engine/   stdlib only. core, state, actions, reduce, tick, systems, relations,
          report (what a sender claims, as against what is true), land
          (climate + agriculture), metal (the bronze chain, the melt ledger),
          house (birth, death, marriage, succession), divine (omens read off a
          future fixed at load, then distorted by the diviner), plague
          (integer SIR + the theological puzzle), archive (the permanent
          record, and the hour it costs to search it).
belief/   World -> Belief projection (plain dicts; the only thing UI/AI read).
ai/       optional Ollama client, parser/composer/voicer/librarian, numeric guard,
          protocol grader, and the prompt boundary (client.safe_fields).
tui/      rendering + command parsing.
content/  authored TOML: scenarios, months, relations, routes, decks, corpus,
          and corpus/predecessor_archive (what was in the room before turn 1).
load.py   content -> initial World.  session.py  headless driver + save/replay.
```
