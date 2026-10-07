# SAY TO THE KING, MY LORD

**Playable alpha.** [Download on itch.io](https://rexvo.itch.io/sttkml) · [GitHub releases](https://github.com/luka1231123/sstkml/releases/tag/v0.6.0-alpha.1)

A Bronze Age court game about keeping a kingdom alive during a collapse. You rule through letters, accounts and people whose reports may be late or unreliable, using a desktop of movable text windows.

The game tracks grain, labour, trade, journeys, disease, military obligations, temples, households and debts. Decisions spend actual stores, letters take time to arrive, and earlier judgements can affect later claims. Keeping everyone paid and fed becomes harder as harvests fail and routes close.

The idea is interesting, and there are moments when an earlier decision comes back as a different problem. It is still an early alpha: long campaigns need balancing, some claims become repetitive, and the interface needs more work.

Much of this was vibe coded. It became a lesson in adding features faster than checking whether they made the game better. The simulation grew before the basic experience had enough play time.

## Courts and editions

Eight courts are available: Ugarit, Byblos, Tyre, Carchemish, Alashiya, Pylos, Pi-Ramesses and Hattusa. They have different reserves, routes, households and obligations. Pylos has workshop accounts, Egypt has temple and provincial accounts, and Hattusa has military service requirements. These are game scenarios; the cultural and agricultural differences are incomplete.

Both editions use the same simulation and have all eight courts:

- **Offline:** authored letters and reports, with deterministic parsing of supported requests, gifts and promises. No Python or Ollama installation is needed for the packaged game.
- **Ollama:** dynamic letter wording, replies, advice and interpretation through a local model. Install Ollama and its model separately. Model weights are not bundled; the app offers offline play if the service or model is missing.

## Run from source

Requires Python 3.12 or newer with working Tk. The launcher creates `.venv` when needed, using your installed Python. The game uses Python's standard library; PyInstaller is needed only to build downloadable packages.

```sh
./run.sh --offline
```

For local language generation, install and start Ollama, then:

```sh
ollama pull qwen3:4b-instruct
./run.sh
```

Useful launcher options:

```sh
./run.sh --check       # check Python, Tk and local requirements
./run.sh --playtest    # use a separate playtest save
./run.sh --cli         # terminal interface
./run.sh --screens     # render screens as text without opening windows
```

`STTKML_MODEL` selects another local model. Generation quality and parsing can vary between models.

## Controls

Each fortnight opens in Court. Tab takes you to the Hall; Space in the Hall ends the fortnight. Enter in the Hall opens the account behind the selected report. G opens cultural governing orders where available.

F2 opens the reign screen, F3 shows current aims, and L in the Hall shows the last report. Ctrl-H returns to the Hall. Use ? for help and Tab within Ask for the manual.

## How it works

The simulation is deterministic for a given seed, scenario and action log. `engine.reduce.apply(world, action)` handles player decisions; `engine.tick.advance(world)` runs the fortnight's scheduled arrivals, production, consumption, health, politics and reports.

The player sees a projection of the world through `belief/`, rather than unrestricted access to the simulation state. Reports and letters can contain old, incomplete or distorted information.

The local model produces language and proposes interpretations. The engine validates actions and calculates their consequences. Generated prose does not directly change stores or decide whether a shipment arrives. Saves retain actions and language records so loading a campaign does not require regenerating its letters.

| Location | Purpose |
| --- | --- |
| `engine/` | World state, actions, scheduled effects and turn systems |
| `belief/` | Information available to the player |
| `tui/` | Character-grid screens, text art, movable windows and Tk/terminal backends |
| `ai/` | Ollama client, letter generation, advice and commitment parsing |
| `content/` | TOML scenarios, court households, goods, routes and authored text |
| `session.py` | Save, load and action replay |
| `play_gui.py`, `play_cli.py` | Desktop and terminal game loops |
| `tools/`, `packaging/` | Inspection, balance drivers and native packaging |

## Saves and headless runs

Each court has its own autosave. Source runs use `saves/` in the repository. Packaged editions share their platform's save location:

| Platform | Save directory |
| --- | --- |
| macOS | `~/Library/Application Support/Say To The King/saves` |
| Windows | `%LOCALAPPDATA%/Say To The King/saves` |
| Linux | `~/.local/share/say-to-the-king/saves` (respects `XDG_DATA_HOME`) |

Set `STTKML_DATA_DIR` to choose a different player-data root. Save files contain the court, seed, action log and session metadata. Alpha updates can change the save format; incompatible versions require a new campaign.

After source setup, run all eight courts without windows or Ollama:

```sh
.venv/bin/python tools/quick_play.py --turns 72
```

This uses a simple policy and writes results to `output/quick-play.json`. It helps find economic problems; it does not measure whether the game is fun.

## Build packages

Build on the target operating system with Python and Tk available:

```sh
.venv/bin/python -m pip install -r packaging/requirements.txt
.venv/bin/python tools/build_packages.py
```

Use `--edition offline` or `--edition ollama` to build one edition. PyInstaller bundles Python, Tk and scenario files into `dist/`; development saves and model weights are excluded. It builds for the current OS and architecture.

The GitHub Actions `packages.yml` workflow builds Windows x64 and Linux x86-64 editions. It runs manually or on version tags and uploads packages with SHA-256 checksums.

Current Mac downloads require Apple Silicon and macOS 26; they are ad-hoc signed and not notarized. Windows builds are unsigned ZIPs: extract the whole archive and keep `_internal` beside the executable. Linux builds require a desktop session and glibc 2.35 or newer: extract the archive and run `./Play.sh`.

Critical feedback is welcome, especially where the rules are confusing, the decisions become repetitive, or a campaign stops being interesting. Include the court, fortnight, edition and steps to reproduce a bug when you can.

## License

Copyright © 2026 Luka Rekhviashvili. Licensed under [GNU GPLv3](LICENSE) (GPL-3.0-only). You may modify and redistribute the game, including commercially, under the license's terms. Distributed derivatives must provide their corresponding source under GPLv3. The game comes without warranty.

Bundled third-party runtimes and libraries retain their own licenses. Ollama and model weights are distributed separately.
