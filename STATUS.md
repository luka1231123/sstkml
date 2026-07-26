# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive). 7 tests green. Plays: `python3 play_cli.py ugarit`.

**In progress:** M4 — numeric guard built with adversarial tests.

**Next:** Ollama client + parser, kept optional so command mode remains complete.

**Rules that bite:** engine/ = stdlib only, integers only, no `random`/`hash()`/floats in engine. Read `SAY_TO_THE_KING_spec.md` Part 0 + `DECISIONS.md` before changing anything.
