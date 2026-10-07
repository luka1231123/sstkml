# SAY TO THE KING, MY LORD

A Bronze Age court game about ruling through letters, accounts and people whose reports may be late or unreliable. You hear disputes, allocate grain, manage obligations and deal with neighbouring rulers through a desktop of movable text windows.

The idea is interesting, and there are moments when an earlier decision comes back as a different problem. The game is an early alpha, though. Long campaigns need balancing, some claims become repetitive, and the interface needs more work.

Much of this was vibe coded. It became a lesson in adding features faster than checking whether they made the game better. The simulation grew before the basic experience had enough play time.

## What you can play

Eight courts are available: Ugarit, Byblos, Tyre, Carchemish, Alashiya, Pylos, Pi-Ramesses and Hattusa. They have different reserves, routes, households and obligations. Pylos has workshop accounts, Egypt has temple and provincial accounts, and Hattusa has military service requirements. These are game scenarios; the cultural and agricultural differences are incomplete.

The game tracks goods, labour, trade, journeys, disease, households and debts. Decisions spend actual stores, letters take time to arrive, and earlier judgements can affect later claims. Each court has its own autosave.

## Run

Downloadable builds include Python and Tk. The offline edition needs no model;
the Ollama edition uses a separately installed local model. See [packaging notes](docs/PACKAGING.md).

To run from source without Ollama:

```sh
./run.sh --offline
```

To run from source with Ollama:

```sh
ollama pull qwen3:4b-instruct
./run.sh
```

The launcher creates a project virtual environment when needed.

```sh
./run.sh --check       # check local requirements
./run.sh --playtest    # separate playtest save
```

The local model helps with letters and advice. Ordinary reports use authored text; the engine calculates outcomes.

## Basic controls

Each fortnight opens in Court. Tab takes you to the Hall; Space in the Hall ends the fortnight. Enter in the Hall opens the account behind the selected report. G opens cultural governing orders where available.

F2 opens the reign screen, F3 shows current aims, and L in the Hall shows the last report. Ctrl-H returns to the Hall. Use ? for help and Tab within Ask for the manual.

## Fast headless play

After setup, you can run all eight courts without windows or Ollama:

```sh
.venv/bin/python tools/quick_play.py --turns 72
```

This uses a simple policy and writes results to `output/quick-play.json`. It helps find economic problems; it does not measure whether the game is fun.

## Notes

[Play report](docs/HUMAN_PLAY_REPORT.md) · [Player research](docs/MARKET_RESEARCH.md) · [Opening balance](docs/OPENING_BALANCE.md) · [Specification](SPEC.md)

The code is split between `engine/` for the simulation, `belief/` for what the player can know, `tui/` for screens, `ai/` for language, and `content/` for scenarios. Inspection and balance tools live in `tools/`.
