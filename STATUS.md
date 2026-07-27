# STATUS

**Done:** M0 (determinism spine) · M1 (famine loop) · M2 (letters/closed-sea) · M3 (scribe distortion + archive) · M4 (numeric guard + optional prose parser) · M5 (formulae + protocol grader + desk) · M6 (relations, gifts, status, unanswered decay, oaths, protocol consequences, misfortune) · M7 (persona cards, report bias, distorted asserted facts, background generation, prompt boundary) · M8 (climate series, agriculture, labour and corvee, canals, the bronze chain, the melt ledger, workshops) · M9 (the house, reproduction, child mortality, marriage abroad as an agent, the queen mother, succession and the oath reset, divination) · M10 (integer SIR, quarantine, the predecessor archive, `cause_oath_id`, expiation, the librarian) · D25 (troops: task, place, garrison strength, troops on the harvest, the `provide_troops` clause and its summons). 247 tests green. Plays: `./run.sh` (windows) or `./run.sh --cli` (terminal).

**Next:** M12 — **the city as a machine** (D39, D40; spec 6.18–6.22). Institutions layered over the existing dependent groups, heads who are people and who misreport, justice and precedent in the hall, the land due and the harbour due, `place` and the heir, and building as a long bet on which crisis is coming. Then M13 — **the world, the envoy, and the standing order** (D35, renumbered): foreign cities carrying the same institutions, seen only as far as the player has travelled. M14 Displacement, M15 scenarios, M16 epilogue.

**What has to be balanced in M12, and where it will fail.** These are the numbers to watch and the failure each one produces if it is wrong:

| number | too low | too high |
|---|---|---|
| institution `base_decay` (4–12/fortnight) | buildings are permanent; repair is never a decision | everything is always broken; the player learns to ignore condition |
| repair cost vs. build cost | building new is always right; the city sprawls | repair is always right; nothing is ever built and M12 has no long bet |
| project `days_needed` (granary 900, wall 4,000) | walls appear every few years and raids stop mattering | nothing is ever finished and the corvée is a tax with no product |
| corvée days vs. harvest need | building is free; the year-later bill never lands | one project starves the estates and the run is unwinnable at turn 20 |
| land due elasticity (flight per 100 points) | tax is free money and the granary stops mattering | one raise empties the estates permanently and there is no way back |
| harbour due lag (3–6 fortnights) | the punishment is instant and reads as a rule, not a consequence | the merchants leave so late the player never connects it |
| verdict legitimacy (±20 / −35) | judging is free and the hall is a chore | one wrong verdict ends a reign and the player stops hearing cases |
| precedent penalty (double) | precedent is flavour | the player is locked into year-2 mistakes forever |
| head misreport size | inspect is never worth an hour | every figure is a lie and the player trusts nothing, which is not tension |

**The two real failure points.** (1) **Attention inflation** — M12 adds hearing, inspecting, appointing and building to a fortnight that already cannot afford to read its post. If the hour budget is not re-tuned, everything new is dead content. The fix is that most of M12 is *free* actions on screens (appoint, name an heir, set a due, order the corvée) and only `hear` and `inspect` cost hours. (2) **Legibility** — a machine with two hidden multipliers, a head who lies about one of them, and a year-long build time can become a system the player cannot form a theory about. The CITY screen has to make condition and output visible *as a history*, not as a number, or the whole thing reads as random.

**Known gap.** The balance numbers (D16, `tools/balance.py`) are still verified on one seed, `8814402919`. A seed sweep is now blocking rather than nice-to-have: M12 adds three new economic dials and tuning them against a single climate series will produce a game that is balanced for one weather pattern.

`engine/troops.garrison_strength(court, place)` is there for 6.13's weighting whenever M12 starts (D32); the one number in it that was invented rather than specified is the half-weight for `watch`, so check that first if raid targeting reads wrong.

**Rules that bite:** engine/ = stdlib only, integers only, no `random`/`hash()`/floats in engine. Read `SAY_TO_THE_KING_spec.md` Part 0 + `DECISIONS.md` before changing anything.

**Run it:** `./run.sh` — the launcher uses the project's own `.venv` and makes one if it is missing. Never call bare `python3`: on this machine it resolves to Apple's 3.9.6, which has neither `tomllib` nor Tk, and the resulting error names a module rather than the mistake. `./run.sh --check` prints the interpreter, the Tk version and whether there is a display.

**Tests:** `./run.sh --test` (or `python3 tools/run_tests.py`) (no pytest needed; `run_tests.py m8:melt` filters). Also `python3 tools/corpus_lint.py` and `python3 tools/balance.py [passive|prudent]`.

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

**The army is 390 men, since D25 (D32).** Three formations, each in one place
doing one thing, and it cannot be two: the seat, the coast, the harvest, or the
muster at Carchemish. The summons clock starts when the courier hands the tablet
over, read or not, and the tablet asks for more men than the oath obliges
because the viceroy exaggerates. The true figure is in the clause, on the OATHS
page, from turn 1. Nothing points this out. Still absent and meant to be: combat
resolution, unit types, morale, terrain.

**The renderer's output is a grid, from M11 (D33).** `Screen` is a rectangle of
`(glyph, fg, bg)` and it is the only thing `tui/` produces. The terminal backend
and the shipped Tk backend are both consumers of it; neither is privileged and
the terminal one must keep working. Screens are **asserted, not screenshotted** —
a test indexes a cell and checks a glyph, in the same headless run as the engine.
Colour never carries meaning alone: every distinction is duplicated by a glyph or
a word, and monochrome is a supported path.

**Read a screen, never photograph one.** `./run.sh --screens [hall|stack|stores|
roll|muster|letter <n>|all] [--turns=N] [--seed=N]` composes any screen from the
seed and prints its glyphs — no display, no window, no image. Because every
screen is a pure function of Belief, that text *is* what the window paints. For a
game already running, `STK_DUMP=1 ./run.sh` writes every window to
`saves/screens.txt` on each repaint (or press `\` to write and print on demand)
and `--screens live` reads it back; that is the only path that reads a real
window, and it exists for when the two disagree.

**The look is 1993 (D36).** Sixteen saturated colours, not a spectrum of taupe:
DOS text mode on a CRT — Turbo Vision, Norton Commander. All the furniture is
`tui/style.py` (title bar, drop shadow, key caps, status bar) and nothing draws
its own. **Every door in the hall now opens**: stack, stores, roll, muster,
oaths, land, house, the desk, counsel, the altar, the tablet house, the known
world, HELP, and the fortnight-turns window.

**The art is in `tui/art.py` and nowhere else (D37).** Twelve faces at 13x9,
picked by *station* rather than by name, plus the altar, the shelves, the seal
frieze. No drawing carries a colour: `art.draw()` colours by glyph weight, so
one drawing renders warm at an altar and cold on a ledger. A test walks every
drawing for double-width glyphs, because one would shear every column to its
right in silence.

**The desk takes typing.** `[d]` dictates, `[tab]` changes what you mean, and
the protocol column grades live — `✗ prostration`, never "you should". The
formulary is free, correct and says nothing; a dictated tablet can be better and
can be far worse. `ai/grader.py` grades both, and the score is recomputed on
replay from the text (D9).

Still to build in M11: the **packaged executable** (PyInstaller, icon,
double-click), save/load from the window game, and the remaining verbs —
allocate, priority, gift, harvest, corvee, assign, dredge, marry, swear,
expiate, quarantine — which exist in the engine and have no window yet.

**Windows are OS windows.** The hub is terminal-sized and stays that way; the
archive, the map, the desk and a letter each open as a real window with its own
title bar, moved and closed on its own. The player puts the granary beside the
letter that makes a claim about it — cross-checking is the game's central act and
two windows make it reading instead of memory. The hub owns the session: closing
it ends the game, closing anything else is free. Every window is reachable from
the hub by keyboard, always.

**Known gap.** The balance numbers (D16, `tools/balance.py`) are verified on one
seed, `8814402919`. A seed sweep is worth doing before M13.
