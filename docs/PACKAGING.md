# Downloadable editions

The offline edition includes the game, Python, Tk and all scenario files.
It does not connect to Ollama, download a model or require Python installation.
All eight courts use the same simulation and controls as the Ollama edition.
Letters use authored text and replies report the engine's recorded decision.
The letter desk still reads gifts, grain requests and promises from your words.
Help uses the court's current records; typed orders use the listed grammar.
Free-form model interpretation and rewriting are the differences.

The Ollama edition includes the same game and runtime. Install Ollama separately
and run `ollama pull qwen3:4b-instruct`. Model weights and the Ollama service are
not included in the download. If the service or model is missing, the app offers
offline play instead.

## Builds made here

`dist/say-to-the-king-offline-darwin-arm64.zip` and
`dist/say-to-the-king-ollama-darwin-arm64.zip` contain separate applications and
a short installation note. Both are approximately 12 MiB. SHA-256 files sit
beside them. These are Apple Silicon builds using a macOS 26 runtime.
They are ad-hoc signed, not Developer ID signed or notarized. macOS may block
a downloaded copy until the player reviews it in Privacy & Security.

Source files, development saves, caches and model weights are excluded.
Packaged saves are stored in `~/Library/Application Support/Say To The King/saves`.
Both editions share these saves. Source runs keep using the repository's
`saves/` directory. To transfer a source campaign, copy its city directory to
the packaged save directory while the game is closed.

## Rebuild

Use Python 3.12 or newer with working Tk on the target operating system:

```sh
.venv/bin/python -m pip install -r packaging/requirements.txt
.venv/bin/python tools/build_packages.py
```

Use `--edition offline` or `--edition ollama` to build one edition. PyInstaller
builds for the current OS and architecture. Windows and Linux need native
builds on those systems; the Mac ZIPs do not run there.

The **Build game packages** GitHub Actions workflow builds Windows x64 on
Windows Server 2022 and Linux x86-64 on Ubuntu 22.04, using Python 3.13.
Run it from the repository's Actions tab, or with
`gh workflow run packages.yml --ref main`. Version tags also trigger it.
Each job uploads both editions and their checksums after loading the packaged
game and opening its windows. No Ollama service is needed for these checks.

Windows downloads are ZIPs: extract the whole archive, then run the `.exe`
inside its game folder. Keep `_internal` beside the executable. These builds
are not Authenticode signed. Linux downloads are `.tar.gz` archives: extract
one and run `./Play.sh` in a desktop session. They require glibc 2.35 or newer;
older distributions and Linux ARM are not covered by these builds.

Windows saves use `%LOCALAPPDATA%/Say To The King/saves`. Linux saves use
`~/.local/share/say-to-the-king/saves`, or the corresponding `XDG_DATA_HOME`
location. Both editions share their platform's save directory.

From source, `./run.sh --offline` selects offline play. The environment variable
`STTKML_DATA_DIR` can select another player-data directory for portable use.

## Verification performed

Both packaged executables loaded their bundled Tcl/Tk 9.0.4, enumerated all
eight courts and opened a campaign through `--package-info`. The offline app
also opened its native Court and Reign windows. Its client factory returns
None, with no service probe or model initialization.

With network transport blocked, an eight-fortnight Pylos playthrough paid a
judgement, set a purchasing mandate, issued workshop tools, read a grain offer,
wrote and sealed a reply, and saved/resumed with matching stores. Authored help
and reports worked; accept, refusal and counteroffer wording preserved their
recorded terms without a model. A separate 36-fortnight run dispatched a grain
request, but that recipient did not answer; no delivery success is claimed.

This verifies the offline gameplay path, not long-term campaign balance.
The ordinary alpha limitations still apply to both editions.
