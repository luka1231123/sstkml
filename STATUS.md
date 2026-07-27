# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive) · M4 (numeric guard + optional prose parser) · M5 (formulae + protocol grader + desk) · M6 (relations, gifts, status, unanswered decay, oaths, protocol consequences, misfortune) · M7 (persona cards, report bias, distorted asserted facts, background generation, prompt boundary) · M8 (climate series, agriculture, labour and corvee, canals, the bronze chain, the melt ledger, workshops) · M9 (the house, reproduction, child mortality, marriage abroad as an agent, the queen mother, succession and the oath reset, divination) · M10 (integer SIR, quarantine, the predecessor archive, `cause_oath_id`, expiation, the librarian). 121 tests green. Plays: `python3 play_cli.py ugarit`.

**Next:** M11 — displacement: rival courts, displaced groups, reception policy, the coalition, raid targeting. Target per spec: a coalition assembled entirely from refusals, verifiable in the log. **Do the troops work first (D25)** — raid targeting reads `garrison_strength[place]`, which has no source in current state.

**Rules that bite:** engine/ = stdlib only, integers only, no `random`/`hash()`/floats in engine. Read `SAY_TO_THE_KING_spec.md` Part 0 + `DECISIONS.md` before changing anything.

**Tests:** `python3 tools/run_tests.py` (no pytest needed; `run_tests.py m8:melt` filters). Also `python3 tools/corpus_lint.py` and `python3 tools/balance.py [passive|prudent]`.

**Three layers of number, since M7 (D11).** A figure the player reads has passed
through: what is true (`Letter.true_facts`) → what the sender asserts
(`report_bias`, `engine/report.py`) → what the scribe copied
(`belief/distortion.py`). Only the last is recoverable by `inspect`; the middle
one needs a second correspondent. Gubla is the honest control case.

**Two clocks, since M8 (D16).** Grain now arrives once a year off the threshing
floor, so the granary is a runway rather than a tap. Seed sits in store only
between threshing and sowing (f12–f18) — that six-fortnight window is the only
time `eat seed` is even possible, and the bill lands at the next threshing.
Meanwhile the melt ledger climbs on the STORES tab, unremarked, and the
chariotry's replacement rate falls without the army losing a man. Nothing
announces either. Do not add a warning: see D19.

**Nobody is bound, since M9 (D22).** When the king dies every oath he swore
*lapses* — not broken, no liability, just void, because the man who swore is
dead. The regnal year resets to 1 and the archive's own dating changes under the
player. Someone has to travel and swear again. Meanwhile the diviner answers
from a future that genuinely already exists (the climate series, `will_die_on`)
and lies about it by competence and loyalty; a wrong reading is always a
plausible neighbour, never noise.

**The archive is the puzzle, since M10 (D26–D31).** When an epidemic begins the
engine designates a genuinely violated oath as its cause and never says which.
Two of Ugarit's three vows have been in breach since before turn 1 because they
name festivals that fell off the calendar generations ago; the third names one
still kept and can be eliminated by a reader who checks. Vows to gods do not
lapse at succession (D26), which is the only reason a predecessor's oath can
still bind. Searching costs an hour, and nothing anywhere tells the player
whether an offering was accepted — the curve is the only answer. Do not add a
confirmation message: see D31.

**Known gap: troops (D25).** `Formation` has no `task` and no `place`, so
`ASSIGN_TROOPS` does not exist, troops supply no harvest labour, and there is no
`garrison_strength(place)` — which M11's raid targeting requires. The
`provide_troops` oath clause is neither implemented nor authored. Do this before
M11. Do not merge `Formation` into `DependentGroup`: see D25.

**Known gap.** The balance numbers (D16, `tools/balance.py`) are verified on one
seed, `8814402919`. A seed sweep is worth doing before M13.
