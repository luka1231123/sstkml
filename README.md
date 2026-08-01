# SAY TO THE KING, MY LORD

Information-constrained rulership sim. Fragile Late Bronze Age world.

People, households, institutions, goods, labour, obligations, journeys, disease, and foreign courts are simulated deterministically. The player holds the Seat through fallible people and delayed, interested information. No omniscient strategy layer.

[`SPEC.md`](SPEC.md) = sole current product and release authority (Alpha 0.7). Superseded specs and plans live in [`docs/archive`](docs/archive/README.md) — history, not active requirements.

## What is here now

- deterministic, replayable court and world kernel;
- explicit goods, labour, ownership, custody, movement, obligations, causal records;
- actor-specific dated Belief projected through one player boundary;
- agriculture, institutions, trade, cargo, news, disease, justice, household, ritual, military service, construction foundations;
- required grounded local-model language for scribes, advisers, tablets;
- multi-window character-cell Palace Desktop;
- Hall, Scribes, Alu, Trade, Storehouse, Muster, Court, Shrine, and World;
- corpus-derived writing blocks and a parsed order/tone review before sealing;
- versioned atomic saves, replay checks, audits, balance tools, screen renders, causal developer inspector.

The shared world contains 55 simulated Alu; authored court content currently makes only `seat` playable. Remaining scope lives only in [`SPEC.md` section 6](SPEC.md#6-path-to-alpha-07).

## Run

```sh
./run.sh                  # windowed game
./run.sh --cli seat       # terminal game
./run.sh --check          # interpreter, Tk, display, Ollama, and model
./run.sh --screens all    # render every screen as text
./run.sh --probe          # live Tk probe
```

`run.sh` use project `.venv`, create when absent. Windowed backend need Python with Tk support.

Hall prints current controls. `Space`, then `Enter`, ends the fortnight; `Ctrl-S` saves, `Ctrl-O` asks before reload, `?` opens grounded Help, and `Q` quits.

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
docs/            live design docs; docs/archive/ is retired material
SPEC.md          sole current product specification (Alpha 0.7)
```
