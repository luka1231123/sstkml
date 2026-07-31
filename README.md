# SAY TO THE KING, MY LORD

Information-constrained rulership sim. Fragile Late Bronze Age world.

People, households, institutions, goods, labour, obligations, journeys, disease, foreign courts — all simulated deterministically. Player hold Ugarit together through fallible people and delayed, interested information. No omniscient strategy layer.

[`SPEC.md`](SPEC.md) = sole current product and release authority. Superseded specs and plans live in [`docs/archive`](docs/archive/README.md) — history, not active requirements.

## What is here now

- deterministic, replayable court and world kernel;
- explicit goods, labour, ownership, custody, movement, obligations, causal records;
- actor-specific dated Belief projected through one player boundary;
- agriculture, institutions, trade, cargo, news, disease, justice, household, ritual, military service, construction foundations;
- required grounded local-model language for scribes, advisers, tablets;
- multi-window character-cell Palace Desktop;
- Hall, Court, Scribes' Room, Storehouse, City, Muster, World, Shrine foundations;
- four-part writing desk: Address, Recognition, player-written Matter, Seal;
- versioned atomic saves, replay checks, audits, balance tools, screen renders, causal developer inspector.

Court and regional kernel not yet unified. Full world-to-letter-to-material-consequence loop still release work. Remaining scope short, lives only in [`SPEC.md` section 6](SPEC.md#6-path-to-10).

## Run

```sh
./run.sh                  # windowed game
./run.sh --cli ugarit     # terminal game
./run.sh --check          # interpreter, Tk, display, Ollama, and model
./run.sh --screens all    # render every screen as text
./run.sh --probe          # live Tk probe
```

`run.sh` use project `.venv`, create when absent. Windowed backend need Python with Tk support.

Hall print current controls. `Space` end fortnight, `Ctrl-S` save, `Ctrl-O` ask before reload, `?` open grounded Help, `Q` quit.

## Required local language model

Supported baseline:

```sh
ollama pull qwen3:4b-instruct
```

Ollama must run. If `ollama serve` report port `11434` already in use, server already listening — do not start second one.

Model supply language, not simulation truth. It may correct player's one- or two-sentence letter matter, voice permitted beliefs, summarize selected records. It cannot see hidden World state, choose policy, invent authoritative quantities, calculate outcomes, or mutate game.

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

`tools/kernel_inspect.py` = omniscient developer inspector. Explain why lot exist, where quantity went, why actor decided, what evidence belief rest on, what obligation authorized, which request unsatisfied. Never player-facing.

Runtime engine standard-library-only, integer-state, immutable, seeded, replayable. `belief/` = only World-to-player projection boundary.

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