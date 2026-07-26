# DECISIONS

Append-only log of choices that deviate from SPEC.md or resolve an ambiguity.

## D1 — Merged system files (M0)
Spec 1.3 lays out ~20 files under `engine/systems/`. We keep the *boundaries*
that matter (engine is stdlib-only; belief/ai/tui never reach World) but merge
the systems into `engine/systems.py` and the contract into
`engine/{core,state,actions,reduce,tick}.py`. A system graduates to its own file
when it outgrows the shared one. Rationale: fewer, denser files while systems
are small; the enforced boundaries are the load-bearing part, not the file count.

## D2 — Event sourcing is descriptive, not exclusive (M0)
Spec 2.1 wants `integrate` to be the *only* producer of a new World. We instead
let systems return `(new_world, events)` via pure `dataclasses.replace`, where
events *describe* what happened (they feed the UI and, later, Claims). Replay
determinism rests on the real guarantees — pure functions, seeded substream RNG,
integer state, canonical hashing, log replay with hash verification — not on
routing every mutation through one function. Verified: two runs byte-identical,
save→replay hash matches.

## D3 — Content loaded with tomllib, no pydantic (M0)
`load.py` (outside engine/) reads authored TOML with stdlib `tomllib` and builds
the frozen tree. No pydantic: validation is light and the authored surface small.
Revisit if content authoring errors start biting.

## D4 — Flat grain income until agriculture (M1)
`Court.grain_income` is a flat per-fortnight estate delivery. Agriculture (M8)
replaces it with real yields. The Ugarit economy is deliberately deficit-run
(≈46,200 qa owed vs 34,000 income) so the game is the order in which groups are
let go, not whether everyone can be fed.

## D5 — Plain terminal UI before Textual (M1, still holds through M2)
M1/M2 ship a command-mode REPL (`play_cli.py` + `tui/render.py`), not Textual.
Everything is reachable by command, matching the spec's "command mode only"
target. Textual arrives when tabs/scrolling/focus earn their weight (M3+).

## D6 — Letters carry structure, not prose (M2)
`engine/mail.py` holds `Letter` as sender/topic/facts/routing only; the body is
rendered on demand from `content/corpus/letters.toml` templates (spec 8.7). The
engine never holds letter text, so the AI composer (M7) slots in by replacing
the renderer, changing nothing in the engine. Correspondents (who writes, cadence,
authored facts) live in scenario content and are read into World at load.

## D7 — Closed-sea transit is leg-by-leg, with one liberty (M2)
Letters move one fortnight at a time. A seasonal sea leg is only *entered* when
the sea is open at the node, so winter letters wait in the harbour and land in
the spring flood (verified: 4 Alashiya letters arriving together at fortnight 8).
Liberty: a letter already mid-crossing when the season turns *completes* the leg
rather than retreating — matters only for the 4-leg Egypt route and keeps the
model simple. Interception is rolled once at dispatch against the riskiest leg.

## D8 — Flat, stdlib-only parser layer (M4)
The small parser lives at `ai/parser.py` rather than a one-file `roles/` package,
and the Ollama client uses `urllib` rather than adding an HTTP dependency.
High-confidence prose is parsed locally; all model JSON is checked against current
Belief IDs and the numeric guard before Actions are constructed. Transport failure
does not charge attention, while a genuine model clarification costs one hour.

## D9 — Protocol text lives in the action log (M5)
Outgoing prose still does not enter `World`; a sent `DictateReply` records the
exact text and its authored protocol profile as primitive fields. The desk grades
that text for display, and replay recomputes the grade rather than trusting a
stored total. The engine retains only the derived `ProtocolRecord` (never prose)
for M6 consequences. Dedicated, recipient/profile-tagged outgoing exemplars live
apart from intentionally unreliable incoming NPC templates.
