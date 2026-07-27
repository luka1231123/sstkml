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

## D10 — Compact, authored diplomacy balance (M6)
Relations, gifts, gossip, oath audits, and misfortune share
`engine/relations.py` while the system is small. The spec fixes gift adequacy
bands and named protocol penalties but leaves exchange values, status floors,
reciprocity, god ranks, generic protocol effects, and deck weights to content;
those values live in `content/relations.toml` and
`content/decks/misfortune.toml`. Annual goods clauses are audited once, at
fortnight 24. M6 rejects unsupported oath clause kinds rather than silently
treating them as satisfied.

## D11 — Two distortion layers, two homes (M7)
Spec 8.6 says the engine distorts asserted facts "via `Relation.report_bias` and
`distortion.py`". We split them, because they are distortions of different
things and the belief boundary forbids engine importing belief:

* `engine/report.py` — the SENDER's lie. Applied once at A15, it is part of the
  world: the tablet really does say twenty ships, and counting at home never
  recovers the truth. `Letter.facts` is what he asserts, `Letter.true_facts`
  what was the case; the latter is never projected and never prompted.
* `belief/distortion.py` — the SCRIBE's slip, unchanged from M3. Corrupts the
  ruler's reading of the tablet, not the tablet.

They compose: the player sees the scribe's copy of the sender's lie. Only the
scribe's layer is recoverable (`inspect`); the sender's needs a second source,
which is what makes Gubla — frantic, accurate, `report_bias 150` — the control
case that teaches the system.

## D12 — Personas are voice, and nothing else (M7)
`content/personas.toml` holds tone, temper, wants and form of address; a test
asserts no persona contains a digit. Every figure was fixed by `report_bias`
before the model was called and every protocol grade is recomputed from the
finished text, so no persona edit can move an outcome. Fact keys are spelled
out for the prompt from authored `labels` in `content/corpus/letters.toml`: a
bare `men: 10` had the model putting ten men aboard the ships rather than
leaving ten to hold the island.

## D13 — Background generation is safe because text is not state (M7)
Spec 8.7's worker is a plain daemon thread (`ai/voicer.Voicer`). It cannot
affect replay, because a save replays from the action log and no letter body
ever enters `World`. `body()` never blocks: an item the worker has not reached
renders its authored template. The spec's "swap in if it arrives while the
player is still on the item" needs a live redraw and waits for Textual (D5);
generating in Stack order at turn start makes it mostly moot, since the top of
the pile is ready before the player has finished triaging.

## D14 — The prompt boundary is a function, not a habit (M7)
Spec 8.9 asks for a type. `ai/client.safe_fields` is the single door: it rejects
forbidden key names and anything that is not `str`/`int`, so no `World` object
is reachable from a prompt. `FORBIDDEN_KEYS` is checked by exact name, since
`seed_grain` is a store the player may see and `seed` is the RNG.

## D15 — The sexagesimal slip belongs to bulk only (M7, fixing M3)
M7 was what made two M3 scribe bugs visible: the fallback error was `value * 60`,
so any count under 60 that did not transpose gained a whole place — three
captured towns copied as 180, thirty-six ships as 2,160. Invisible in a granary
of 180,000 qa, absurd the moment a Voicer wrote it in a sentence. `transcribe`
now takes `sexagesimal`, passed only for bulk written in places; counted things
slip by a wedge or a transposition. The granary keeps its drama.

## D16 — The harvest is annual, and D4 is superseded (M8)
D4 gave `Court.grain_income` as a flat per-fortnight estate delivery, to be
replaced when agriculture landed. It has been. `grain_income` is now a small
residual (garden plots, olive and vine renders, tribute in kind — 4,000 qa)
and the harvest arrives once a year off the threshing floor. This changes the
shape of the game more than any number in it: the granary is a year's runway
that visibly falls, rather than a bath filling at a steady rate.

The deficit D4 established is preserved and restated: 1,188,000 qa at full
inputs in a normal year against 1,492,800 qa of entitlement. Paying everyone
empties the granary in year two; cutting one group to fit survives indefinitely
at a bounded unrest cost. `tools/balance.py` plays both and `tests/test_m8.py`
pins the result, so the claim is checked rather than asserted.

The scenario opens two fortnights into a growing season the predecessor began
(`opening_growing_turns`), so year one is a normal year the player inherits and
only year two answers to his decisions.

## D17 — Two homes for the land, mirroring the belief split (M8)
`engine/land.py` holds the climate series and the season; `engine/metal.py` holds
the bronze chain. Both are stdlib-only and integer-only like the rest of engine/.
The climate series is precomputed in full at load (30 years) and stored on World:
spec 6.4 requires the future to be fixed before turn one so divination can read
a true future value, and putting it in state rather than deriving it per turn is
what makes that possible.

What the player may see is deliberately thin and lives in `belief/project.py`:
a gauge reading (a lossy proxy, then run through the scribe), last year's actual
harvest (true, and the only hard datum), his own standing orders, and estate
overseers' letters — which carry M7's `report_bias`, so his own servants inflate
the hands they need and play down what went into the ground. He never sees the
climate index, any response table, or what is standing in the field.

## D18 — The yield formula's order is pinned, not merely documented (M8)
Spec 6.4 fixes the operation order because integer floor division is not
associative. `estate_yield` evaluates strictly left to right and
`tests/test_m8.py` recomputes it term by term. Ugarit's authored areas happen to
divide cleanly, so the two orderings agree *there* — the test therefore also
demonstrates the divergence on numbers that do not, rather than pretending the
scenario proves it. A scenario with less tidy figures would diverge silently.

## D19 — `replacement_rate` is not in Belief, and nothing announces the melt (M8)
Spec 6.5's whole design is that army strength never falls and replacement does.
So `belief/project.py` projects `Formation.strength` and never
`replacement_rate`, `events_lines` has no branch for `BronzeMelted`, and
`FORBIDDEN_KEYS` blocks the rate from any prompt. The melt ledger itself *is*
visible — one unemphasised line among the metals on the STORES tab, as 9.3 asks.
`test_nothing_announces_the_melt` asserts the silence, because the absence is
the mechanic and a later milestone could otherwise "helpfully" add a warning.

## D20 — Unrest tracks heads in arrears, not the sum of debt weeks (M8, fixing M1)
`recompute_unrest` summed every group's `debt_weeks`, so unrest scaled with how
finely the payroll happened to be divided rather than with how many people went
hungry. M8 added one group and lifted the deficit, and a court that let its
weavers go — a fifth of the heads, and the intended survivable choice —
saturated at maximum unrest inside four turns. It is now the size-weighted share
of the population in arrears, saturating at spec 6.3's bottom band of eight
fortnights. Letting one group go now costs roughly its share of the heads.

## D21 — The house is a cast, and heirs are re-ranked every turn (M9)
`Court.house` is a dict of `HouseMember`, and every one of them is a person the
engine can kill, marry, or make pregnant. Succession order is not stored as an
authored list: `_rank_heirs` recomputes `is_heir_rank` from sex, age, legitimacy
and faction on every `house.step`, not only when somebody is born or dies.

That is deliberately more work than necessary. Ranking on events alone was the
first implementation and it was wrong at turn one — the authored cast had never
had an event, so nobody was ranked and the HOUSE screen showed a king with no
successor. Recomputing every turn is idempotent, costs nothing at this scale,
and is self-healing: any future system that changes a person (plague, exile,
legitimation) gets correct ranks without knowing the succession rules exist.

## D22 — Oaths lapse at succession; they do not break (M9)
Spec 6.9 makes oaths personal and non-transitive, so `succeed()` sets
`lapsed = True` on every oath that is not already dissolved rather than
dissolving or breaking them. The distinction is the whole point:

- **broken** is a moral event with divine liability attached;
- **lapsed** is nobody's fault. The man who swore is dead.

A lapsed oath accrues no liability and imposes no obligation. It sits on the
OATHS screen marked LAPSED, which after a succession is the most important word
on that screen, and somebody has to travel and swear again before it means
anything. The regnal year resets to 1 and the scribes begin the count again —
so the player's own dating of his archive changes under him, which is historical
and is also a small, cheap way of making a succession feel like a discontinuity
rather than a stat change.

## D23 — Divination reads a future that already exists (M9)
`engine/divine.py` does not invent an answer and then arrange for it to come
true. `true_answer` reads state that is genuinely fixed in advance: the harvest
band comes off the climate series precomputed at load (D17), and a death reading
comes from `will_die_on`, which is pure in `(seed, turn, person)` and can
therefore be asked about a turn the game has not reached without advancing
anything. The diviner then distorts that truth by competence, loyalty and bias.

Two honest limits, recorded because they are easy to forget later:

1. A wrong reading is a *plausible neighbour*, never noise — "poor" for
   "middling", a rival faction for the true one. Noise would be free to detect
   after three consultations; a near miss is not.
2. The death reading is true *given no intervening change to that person's
   health*. Nothing currently changes health, so today it is simply true. M10's
   plague will change health, and at that point the diviner starts being right
   about the world as it stood when he asked. That is a feature, but it must be
   a chosen one — do not "fix" it by making `will_die_on` re-read live health,
   which would make the reading unfalsifiable.

Belief carries every omen ever given and no field that says whether it was
right (spec 6.11). The player checks the diviner against events or not at all.

## D24 — Personas are keyed by role, not only by name (M9)
A daughter married into another court writes home. She cannot have an authored
persona card, because she may have been *born during play* — no content file can
name her in advance. So belief stack items now carry a `persona` field, which is
normally the sender's own id but resolves to the shared `daughter_abroad` card
for any house member with `married_to_court` set, and `ai/voicer.build_prompt`
reads that field instead of the sender id.

Without it she fell through to `[default]` and wrote like a chancery clerk,
which is the wrong voice for the one correspondent with a foot in both houses.
The indirection is general: any future role that produces correspondents the
content cannot enumerate gets a card by setting one field in the projection.

## D25 — The military entity is deferred, and here is exactly what is missing (M9, for M11)
Recorded now because M10 does not touch troops and the gap would otherwise be
rediscovered at the point where it blocks work.

`Formation` currently carries `id, name, strength, equipment_floor,
replacement_rate`, and nothing in the codebase reads `strength`. It exists to be
the thing M8's melt ledger silently degrades (D19), and for that it is complete.
As a military entity it is not started.

One clarification against an earlier reading of this code: `Formation` and
`DependentGroup(function="garrison")` are **not** duplicates and must not be
merged. Spec line 343 keeps `troops` beside `dependents` on Court deliberately.
They are different axes — the 60-head `garrison_mahadu` group is a payroll
entity with mouths, arrears and loyalty; a formation is a military entity with
strength and equipment. Ugarit has both at Ma'hadu and should.

What is missing, all of it spec-mandated:

1. **`Formation.task` and `Formation.place`.** Spec 11 gives
   `ASSIGN_TROOPS formation=<id> task=garrison|harvest|campaign|watch place=<id>`.
   Everything below reads these two fields; nothing else is blocked by anything
   else.
2. **Troops as a labour source.** Spec 6.4 line 566: "Labour comes from `troops`
   assigned to `HARVEST`". `engine.land.labour_supplied` today reads only
   `field_labour` groups, `court.at_harvest`, and `corvee_days`. Until troops
   contribute, the garrison-or-the-harvest choice the spec calls the classic
   Bronze Age dilemma is absent rather than merely unpolished.
3. **`garrison_strength(place)`.** Spec 6.13's raid targeting is
   `grievance[owner] * knowledge[place] * (1000 - garrison_strength[place])`.
   There is no source for that term in current state. This is a hard M11 blocker
   and is the reason this note exists.
4. **The `provide_troops(n, within_turns_of_summons)` oath clause.** Spec 6.9
   line 749 lists it; spec 7.2 makes it half of Ugarit's premise — "your grain
   ships and your troops go north while your own coast is watched by four men in
   a tower." `engine/relations.py` handles `provide_goods` and `no_contact_with`
   and raises on everything else, and `content/scenarios/ugarit.toml` authors
   only the grain clause. Ugarit is currently sworn to send grain it has and
   troops it is never asked for.

Also open, and a content fix rather than a code one: Ugarit's formations total
490 strength (chariotry 90, household troops 400) against spec 7.2's "`troops`
total under 400. There is no military solution to anything." Either trim the
household troops or record why 490 is right. The cap is thematic, so drifting
past it quietly is how the endgame starts feeling winnable by force.

Deliberately NOT deferred-with-it: no combat resolution, no unit types, no
morale, no terrain. M11 needs raids against garrison strength and nothing more.

## D26 — A vow to a god does not lapse, and that is what makes M10 possible (M10)
D22 established that oaths are personal: when the man who swore dies, the oath
lapses, binds nobody, and accrues no liability. Spec 6.12 then asks for an
epidemic whose cause is "a genuinely violated oath, possibly sworn by the
player's *predecessor* and present in the archive from turn 1" — which D22 had
made impossible. A predecessor's oath is lapsed by definition.

The resolution is a distinction the period actually drew. An oath sworn to a
KING is a personal bond between two men and dies with either of them. A vow
sworn to a GOD is a dedication of the house and the city, and the god does not
accept "the man who promised is dead" as an argument. So `Oath.binds_house`:

- royal oaths lapse at succession, and their liability resets to zero;
- vows do not lapse, and their liability is inherited in full.

The new king therefore inherits every debt to heaven and none of the debts to
other kings, which is precisely the wrong way round for him, and he is not told
that any of it exists. This is what Mursili II's plague prayers are about.

## D27 — The clause that can be broken by forgetting (M10)
`maintain_rite(rite, fortnight)` is violated when the named rite is simply not
on the court's rite list any more. No action breaks it; an omission does, and
the omission was somebody else's, generations ago. Nobody at court is notified,
because nobody at court knows — the calendar was recopied at an accession and
what could not be read was not copied (`PA-UG-022`). It is in the archive and
only in the archive.

Ugarit authors three vows: two name festivals that are not on Ammurapi's
calendar and so accrue liability every year from turn 1, and one names
`first_fruits`, which IS kept and therefore can never be the cause. That third
vow exists to be eliminated by a reader who checks the rite list, and it is the
one clean deduction the puzzle offers. Spec 6.12 asks that a careful reader
narrow the field to three and not to one; the field is exactly three, and the
last step is an informed offering, which is what the historical kings were also
doing.

## D28 — The cause draw is uniform, against the obvious design (M10)
`designate_cause` first weighted the draw by liability, on the reasoning that the
more badly broken oath is the likelier grievance. The reasoning is fine and the
result was bad: Ugarit's Hatti grain oath carries an order of magnitude more
liability than the old vows, so it was the answer in roughly three runs in four,
and a puzzle with a modal answer is a puzzle you solve once and then remember.
Liability is invisible to the player either way (6.9), so the weighting bought
no fairness — it only made the game repeat itself. The draw is now uniform over
the oaths that genuinely carry liability, and `test_the_cause_draw_is_uniform`
pins it.

## D29 — An epidemic cannot be seeded with one case, for arithmetic reasons (M10)
With I = 1 in a city of 7,000, `S * I * beta // (pop * 1000)` floors to zero,
and so do recoveries and deaths. The state is a fixed point: the sickness sits
at one case for ever and nothing in the model can move it. Two fixes, both in
the scenario's favour:

1. Introduction seeds `max(5, population // 400)` cases. A ship does not deliver
   one sick man, it delivers a crew, and by the time the palace has a word for
   it a street has it. This is also true, which is convenient.
2. `beta` must exceed `gamma + mortality` or the epidemic cannot grow at all.
   At the first-authored 240 against 270 it burned out from any seeding,
   silently and every time. It is now 520, giving roughly 1.9, an epidemic that
   runs about two and a half years and takes a little under a third of the city.

`test_a_single_case_cannot_start_an_epidemic` pins the fixed point itself, so
nobody re-introduces it by "simplifying" the seeding later.

## D30 — Letters are filed at the END of the turn (M10)
The archive filing pass runs after A15, not after A3 with the arrivals. A
correspondent standing in the same city has no transit to cross, so an estate
overseer's letter is generated and delivered inside a single turn; filing with
the arrivals missed every one of them. The pass also offers the whole inbox
rather than only this turn's arrivals, because the scenario's opening letters
predate turn 1 and would otherwise leave a hole exactly where the player's first
correspondence belongs. `file_letter` dedupes on `ref`, so it is idempotent and
replay-safe.

## D31 — Belief gives graves, never compartments; and no verdict on an offering (M10)
`_plague` projects four things: whether there is sickness in the city (a
boolean — you can see a plague or you cannot), the gravediggers' cumulative
count run through the scribe, which roads the ruler has closed, and which oaths
he has made offerings against. S, I, R, beta, gamma, mortality and
`cause_oath_id` are all absent and all in `FORBIDDEN_KEYS`; nobody in 1190 BC
has an infection count, so a correspondent who quoted one would be speaking from
outside the world.

The load-bearing absence is the verdict. `offerings_made` lists what the king
did, in order, with nothing about how it was received — `OathExpiated` carries no
`correct` field, `events_lines` says only "the god does not answer", and there is
no field anywhere that could be read the other way. An epidemic about to burn out
on its own looks exactly like one that has been expiated, which is the honest
version of the historical situation. `test_nothing_announces_whether_the_offering_was_right`
asserts the silence, in the same spirit as D19's melt.
