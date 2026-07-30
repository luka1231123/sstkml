# SAY TO THE KING, MY LORD

An information-constrained rulership simulation set in a fragile Late Bronze
Age world.

People, households, institutions, goods, labour, obligations, journeys,
disease, and foreign courts are simulated deterministically. The player holds
Ugarit together through fallible people and delayed, interested information,
not through an omniscient strategy layer.

[`SPEC.md`](SPEC.md) is the single current product and release authority.
Superseded specifications and implementation plans are preserved under
[`docs/archive`](docs/archive/README.md); they are history, not active
requirements.

## What is here now

- a deterministic, replayable court and world kernel;
- explicit goods, labour, ownership, custody, movement, obligations, and
  causal records;
- actor-specific dated Belief projected through one player boundary;
- agriculture, institutions, trade, cargo, news, disease, justice, household,
  ritual, military service, and construction foundations;
- required grounded local-model language for scribes, advisers, and tablets;
- a multi-window character-cell Palace Desktop;
- Hall, Court, Scribes' Room, Storehouse, City, Muster, World, and Shrine
  foundations;
- a four-part writing desk: Address, Recognition, player-written Matter, and
  Seal;
- versioned atomic saves, replay checks, audits, balance tools, screen renders,
  and a causal developer inspector.

The court and regional kernel are not yet fully unified, and the complete
world-to-letter-to-material-consequence loop is still release work. The
authoritative remaining scope is deliberately short and lives only in
[`SPEC.md` section 6](SPEC.md#6-path-to-10).

## Run

```sh
./run.sh                  # windowed game
./run.sh --cli ugarit     # terminal game
./run.sh --check          # interpreter, Tk, display, Ollama, and model
./run.sh --screens all    # render every screen as text
./run.sh --probe          # live Tk probe
```

`run.sh` uses the project `.venv`, creating it when absent. The windowed backend
requires Python with Tk support.

The Hall prints current controls. `Space` ends the fortnight, `Ctrl-S` saves,
`Ctrl-O` asks before reloading, `?` opens grounded Help, and `Q` quits.

## Required local language model

The supported baseline is:

```sh
ollama pull qwen3:4b-instruct
```

Ollama must be running. If `ollama serve` reports that port `11434` is already
in use, a server is already listening; do not start a second one.

The model supplies language, not simulation truth. It may correct the player's
one- or two-sentence letter matter, voice permitted beliefs, and summarize
selected records. It cannot see hidden World state, choose policy, invent
authoritative quantities, calculate outcomes, or mutate the game.

## Verify

```sh
./run.sh --test
.venv/bin/python tools/inventory.py
.venv/bin/python tools/corpus_lint.py
.venv/bin/python tools/m13_audit.py
.venv/bin/python tools/m13_benchmark.py
.venv/bin/python tools/balance.py prudent 96
.venv/bin/python tools/kernel_inspect.py where grain
```

`tools/kernel_inspect.py` is the omniscient developer inspector. It can explain
why a lot exists, where a quantity went, why an actor decided, what evidence a
belief rests on, what an obligation authorized, and which request was not
satisfied. It is never player-facing.

The runtime engine is standard-library-only, integer-state, immutable, seeded,
and replayable. `belief/` is the only World-to-player projection boundary.

## Repository map

```text
engine/          authoritative simulation, actions, systems, and records
engine/kernel/   world entities, allocation, farming, transport, and tick
belief/          safe dated projections for actors and player UI
ai/              required grounded court-language layer
tui/             character-cell screens and Tk/terminal backends
content/         scenarios, people, goods, formulae, and correspondence
tools/           audit, benchmark, balance, inspection, screens, and probes
tests/           deterministic engine, controller, UI, and AI contracts
docs/archive/    retired specifications and post-1.0 idea parking
SPEC.md          sole current 1.0 product specification
```
