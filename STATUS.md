# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive) · M4 (numeric guard + optional prose parser) · M5 (formulae + protocol grader + desk). 21 tests green. Plays: `python3 play_cli.py ugarit`.

**Next:** M6 — relations, status claims, gifts, oaths, unanswered-letter decay, and protocol consequences.

**Rules that bite:** engine/ = stdlib only, integers only, no `random`/`hash()`/floats in engine. Read `SAY_TO_THE_KING_spec.md` Part 0 + `DECISIONS.md` before changing anything.
