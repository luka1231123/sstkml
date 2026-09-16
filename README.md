# SAY TO THE KING, MY LORD

Information-constrained rulership sim. Fragile Late Bronze Age world.

People, households, institutions, goods, labour, obligations, journeys, disease, and foreign courts are simulated deterministically. The player holds the Seat through fallible people and delayed, interested information. No omniscient strategy layer.

[`SPEC.md`](SPEC.md) is the sole product authority. [`docs/PLAYABLE.md`](docs/PLAYABLE.md) records what the game measures today and what is left before it plays.
[`docs/FIRST_YEAR.md`](docs/FIRST_YEAR.md) walks through rations, grain relief,
harvest decisions and the aftermath report.

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

The shared world contains 55 simulated Alu; authored court content currently makes only `seat` playable.

## Run

```sh
./run.sh                  # windowed game
./run.sh --playtest       # fresh campaign with its own autosave; F8 records notes
./run.sh --check          # interpreter, Tk, display, Ollama, and model
./run.sh --screens         # render one screen as text
./run.sh --probe          # live Tk probe
```

`run.sh` use project `.venv`, create when absent. Windowed backend need Python with Tk support.

Each fortnight opens in Court: one person or letter, with actions beside it.
`f/a/s` reviews a judgement, `enter` reads a letter, `b` replies, and `d` defers.
`tab` leaves Court for the Hall: the dashboard of the year, stores, standing,
rations and labour, waiting matters, and the doors to every working room.
`space` in the Hall ends the fortnight and opens the next Court; `l` shows the
last report. `Ctrl-H` returns here. `?` opens free help, which is one of the
game's own screens with Manual and Ask halves; `Ctrl-Shift-R` resets window sizes.
Claims are heard only in Court; the Palace holds people, offices and envoys.
`F8` records a playtest note. Last report is available without opening another window.
Hall `o` opens Orders and receipts. Long Stores/Muster/Orders details and order
reviews use left/right; Counsel uses Page Up/Page Down. Notes now attach the
originating screen automatically. See [the playtest route](docs/PLAYTEST_DECISIONS.md).

Version 29 saves still load. `--playtest` starts a separate autosave folder.

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
.venv/bin/python tools/first_year.py
.venv/bin/python tools/inventory.py
.venv/bin/python tools/corpus_lint.py
.venv/bin/python tools/m13_benchmark.py
.venv/bin/python tools/balance.py austerity 96
.venv/bin/python tools/gameplay_probe.py 4 180
.venv/bin/python tools/gameplay_probe.py 3 720 --baseline --policy passive
.venv/bin/python tools/information_audit.py
.venv/bin/python tools/kernel_inspect.py where grain
```

`tools/kernel_inspect.py` = omniscient developer inspector. Explain why lot exist, where quantity went, why actor decided, what evidence belief rest on, what obligation authorized, which request unsatisfied. Never player-facing.

`tools/look.py` = read a run without reading a screen.

```sh
.venv/bin/python tools/look.py figures --turns 60 --every 4   # numbers, one row a turn
.venv/bin/python tools/look.py events --turns 40              # events by domain, not 767 lines
.venv/bin/python tools/look.py events --turns 40 --each --kind hungry
.venv/bin/python tools/look.py belief justice.petitions       # what a screen could show
.venv/bin/python tools/look.py belief stores --diff --turns 8 # what the last turn changed
```

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
docs/            PLAYABLE.md: measured state and the work left
SPEC.md          sole current product specification
```
