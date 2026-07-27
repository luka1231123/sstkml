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

## D32 — The military entity, closing D25 (pre-M11)
D25 listed four missing things and said to do them before M11 because raid
targeting reads a term that had no source. All four are now in.

**`Formation.task` and `Formation.place`** (spec 11's `ASSIGN_TROOPS`). Four
tasks, and the point of having them is that they are exclusive. The same men
hold the seat, watch the coast, reap the barley, or go north to a muster, and a
king with 390 of them cannot do two of those. `Formation` is *not* merged into
`DependentGroup` and must not be: D25 has the argument, and it still stands.

**Troops are labour** (spec 6.4 line 566). `harvest_hands` adds
`strength * labour_days_per_head` for every formation tasked to `harvest`, on
the same per-head rate as everybody else, with no `output_modifier` — a soldier
is fed out of the payroll group he belongs to, and starving him surfaces as
unrest long before it surfaces as a short harvest. The garrison-or-the-harvest
dilemma is now a real one in both directions, and the test named for it in
`tests/test_troops.py` pins both ends at once.

**`garrison_strength(place)`**, which is what M11 was actually waiting for.
Garrison counts full, watch counts half, harvest and campaign count nought.
A watch is men who can see a sail coming and cannot do anything about it; spec
7.2's four men in a tower are the whole joke and should not read as a defence.
This is the one number in the module invented rather than specified, and M11
should revisit the half if raid weighting reads wrong.

**`provide_troops(n, within_turns_of_summons)`**, and the design is in where the
number comes from. The clause carries the true figure; the letter is only the
trigger. The viceroy of Carchemish already exaggerated `troops` (M7's
`report_bias`), so the tablet asks for more men than the oath obliges, and the
king who obeys the tablet sends men he did not owe out of an army that cannot
spare them. The oath is readable on the OATHS page from turn 1. Nothing points
this out.

Two smaller things follow from that, both deliberate:

- **The clock starts on delivery, not on reading.** `note_summons` runs off
  arrivals in A3, before the A10 audit, and does not care whether the tablet has
  been opened. An unread demand is still a demand delivered, and the Great
  King's clerks date it from the day their courier handed it over. The summons
  is correspondingly absent from Belief until the letter is read — he is bound
  by something he has not been told about, which is the argument for reading the
  pile and the only one the game makes.
- **It is judged once, on the due turn.** One failed muster is one breach,
  however long the overlord goes on remembering it. Same shape as the yearly
  grain clause, and the same reason: liability is a weight on the misfortune
  deck, not a bill.

Also done, the content fix D25 asked for: Ugarit's formations were 490 against
spec 7.2's "under 400". Now 390 — chariotry 90, household troops 260, and a
40-man watch at Ma'hadu that exists to be the tower. Answering the summons costs
200 of them.

Still deliberately absent, exactly as D25 said: no combat resolution, no unit
types, no morale, no terrain. M11 needs raids against garrison strength and
nothing more.

## D33 — The interface becomes M11, and it is built for a double-click (pre-M12)
The game is good and nobody can get into it. `play_cli.py` is a 561-line command
loop with a 40-line help string, and the first thing a new player meets is a
prompt and a wall of verbs. Part 9 of the spec — the node map, the sparklines,
the house tree, the desk — was written at M0 and is still mostly unbuilt. This
milestone is Part 9, and it goes in front of displacement because the coalition
is the system that most needs a map and a chart to be legible at all, and
building those after M12 would mean building M12's screens twice.

Displacement, scenarios and the epilogue each shift back one: M12, M13, M14.

**The target is an executable, so the host is a graphics toolkit, not a terminal
framework.** A store launches a binary and expects a real window: a console
program gets no proper window at all, and on Windows it gets a `cmd.exe` frame
around the art. The setup the player performs is a double-click.

**The toolkit is Tk**, which follows from the windows (below) more than from
anything else. It is the only option that is in the standard library, gives
genuine operating-system windows, and bundles into a single artifact with the
Tcl/Tk runtime inside it — so the Linux `python3-tk` problem, which is real when
a user installs from source, does not exist for someone who downloads a build.
The project's stdlib-only norm survives intact, which no other candidate managed.
Rendering is a grid of cells into a `Text` widget with a tag per palette pair;
if that proves too slow or too soft-edged, a font-atlas blit onto a `Canvas`
replaces it without anything above the backend noticing, which is the point of
spec 9.6.

**The grid abstraction is the whole design** (spec 9.6). `Screen` is a rectangle
of `(glyph, fg, bg)` and the renderer's only output. The terminal backend and
the window backend are both consumers, and neither is privileged. Three things
fall out, and all three are the reason to do it this way rather than draw
straight into a window:

- Screens are **asserted, not screenshotted**. A test indexes a cell and checks
  a glyph. The interface joins the engine in the headless suite instead of being
  the one part of the project nobody can test.
- The terminal path survives, so the game stays playable over `ssh` and the
  80-column degrade path (M14) is a backend, not a rewrite.
- `belief/project.py` stays the only thing the interface reads. The grid sits
  below the renderer, not beside the Belief boundary, and cannot become a second
  door into `World`.

**Colour never carries meaning alone.** Sixteen entries, authored in content.
Every colour distinction is duplicated by a glyph or a word, and monochrome and
`--pure-ascii` are supported paths. Part 0's information rules did not stop
being true because the terminal got nicer, and a freshness that is only a hue is
a freshness the player cannot cross-check.

**Operating-system windows, and they are the organising idea.** The hub is a
small window, about the size of a terminal, and it stays that size. The archive,
the map, the desk and a letter each open as *another OS window*: own title bar,
own taskbar entry, moved and closed on its own. The player arranges his own
table.

The argument for paying real money for this — and it does cost exclusive
fullscreen and any launcher overlay, both of which hook a graphics context Tk
does not have — is that the game's central act is cross-checking one number
against another. M3's whole target was "the player cross-checks a number and
finds it wrong", and there are now three layers between him and any figure
(D11). On a single surface that comparison is an act of memory, which is exactly
the faculty the game is already taxing on purpose. Two windows side by side make
it an act of reading. A king's table has several tablets open on it at once, and
this is the one place where the interface should imitate the desk rather than
the terminal.

Two rules follow and are not optional. The hub owns the session: closing it ends
the game, closing anything else is free. And every window is reachable from the
hub by keyboard alone, because a player who has closed a window and cannot find
it again has lost the game to the interface.

**Two advisors, and the split is the point.**

- **HELP** is free, always right, and out of fiction. Rules, syntax, hour costs,
  what is available this turn. It is built on the deterministic pre-parser's
  existing `_affordances` (`ai/parser.py`) and it does not call a model, ever.
- **COUNSEL** is a named courtier who costs an hour and can be wrong. He reads
  the same Belief the player does, and he is subject to competence and loyalty
  the way the diviner is (D23) and the scribes are (D11). He will not check the
  oath unless asked. He is the game's thesis applied to its own tutorial.

Keeping them apart is what makes both honest. A single advisor would have to be
either a liar you cannot learn the controls from or an oracle that hands the
player the clean channel the entire game is built to deny him.

**COUNSEL must work with no model, because it ships.** A downloaded binary
cannot assume a local Ollama, and paying per player is not a plan. So the
offline floor is authored lines selected by persona and bias, on the machinery
`ai/voicer.py` and `engine/report.py` already have; a live model is an upgrade
for the player who configures one, not a dependency of the build. This also
keeps the prompt boundary (spec 8.9, `FORBIDDEN_KEYS`) defensible: an advisor
holding the whole action surface is the single feature most likely to leak
`liability` or `cause_oath_id`, and a deterministic core cannot leak at all.


## D34 — Window kinds, not rooms: the shape of M11
The instruction was a living world rather than a management screen. A first pass
answered it with a palace of six drawn rooms, which was the wrong answer: it
forces one metaphor onto seven different jobs, and most of those jobs are better
served by an ordinary abstract window. A chat is a better advisor than a painted
chamber is.

**The principle is that form follows function, and there is no rule beyond
that.** A window is given the flavour of a place when being somewhere makes the
moment better, and is a plain functional window when it does not. This is a
judgement made per window, not a system. Most windows are plain.

**Where a place earns it, and why — three of them:**

- **The hall.** The hub, always open, owns the session: the date, the season, the
  hours burning down, who is waiting on you. It is also where an audience
  happens, and that is the real argument. Being *received* is different from
  being messaged; an envoy who is standing in your hall, in front of the people
  waiting behind him, is a different conversation from a chat window.
- **The temple.** Divination, rites, expiation. An omen delivered in a plain
  window is a string. Delivered at an altar, after a walk, it is a ritual, and
  the game already turns on the player half-believing it (D23).
- **The tablet house.** Search costs an hour, and the room is the reason that
  reads as expensive rather than arbitrary. The M10 puzzle depends on the player
  feeling the hour before he spends it.

Everything else is a plain window with no setting: stores, the roll, the muster,
letters, oaths, the graph, the composer. Dressing a table of numbers as a room
adds nothing and costs art.

**Six window kinds, reused.** Each is one widget class instantiated many times,
which is why this is cheaper than six bespoke rooms and not more expensive:

1. **Conversation.** Scrollback, typed input, a portrait, a name, turn-taking,
   persona-driven, costs hours. Plain for the everyday ones — COUNSEL at your
   shoulder, a word with the scribe. Staged in the hall when someone is
   *received*, and at the altar when it is the diviner: same widget, a setting
   drawn behind it.
2. **Document.** A letter, an archive record, an oath, a predecessor's tablet.
   Plain, small, many open at once, closed in a keystroke, and all identical in
   furniture so the eye goes to the figures. This is the kind that makes
   cross-checking work, which is what D33 bought the OS windows for.
3. **Ledger.** Stores, the court roll, the muster, an estate. A table: dense,
   cold, sortable, sparklines where a series exists. Spec 9.3 says the roll
   should look like a payroll because it is one, and that is the aesthetic for
   the whole kind.
4. **Composer.** Writing, which is half the game. An editor with the draft, the
   grader marking against `formulae.toml` as you type, and the scribe's advisory
   line. The one kind that deserves bespoke work.
5. **Diagram.** The correspondence graph (spec 9.3.6 — a graph, never a map) and
   the family tree. Nodes, edges, freshness.
6. **Utility.** HELP, settings, the save dialog. Out of fiction, plain, free.

**Aliveness comes from people who talk, not places you look at.** This is the
correction that matters. A drawn storeroom is looked at once and is wallpaper by
the third fortnight; a scribe who answers when addressed is alive every time he
is opened. The project already has the machinery for this and is not using it for
anything but letters: `content/personas.toml`, `ai/voicer.py`, `engine/report.py`
give every figure a voice, a temper, and a bias. Pointing that at conversation
windows — courtiers, the diviner, envoys — is the highest-yield work in the
milestone, and it is mostly authoring rather than code.

Two supporting levers, both cheap:

- **The hall shows people, not counters.** The rations officer is waiting
  *because* arrears crossed four fortnights; the brother is waiting because he
  wants something. State embodied as persons, projected from Belief, no new
  systems.
- **The fortnight ends like something happens.** `end` is currently a command
  that reprints a screen. It is the only moment the world moves on its own and it
  should be the heaviest beat in the loop: what arrived arrives, what changed is
  shown rather than summarised, consequence seen before cause is understood.

Anything a conversation, a document, a ledger or a diagram already does well, it
keeps doing. No screen is dressed as a place to make it feel important.

**Deliberately not built, each a real sink:**

- **Bespoke art per screen.** Six painted rooms was the rejected design. Art
  budget goes to portraits for the ~15 people who recur, and to three settings:
  the hall, the altar, the tablet house.
- **Animation or a frame loop.** Redraw on state change; nothing here moves.
- **Geography.** No coastline, coordinates or distances (spec 9.3.6). A pretty
  map is not merely wasted work but a lie about what the player knows.
- **A dashboard.** Spec 9.4 forbids it, and separate windows are what make
  knowing two things at once cost a decision.
- **Procedural art.** Hand-author the little there is.
- **Custom window chrome.** Use the operating system's title bars.
- **Sound.** After M14, or never.
- **Mouse-first interaction.** Writing is the game; every window fully
  keyboard-operable, none requiring a mouse.

## D35 — The world, the envoy, and the standing order (M12)
Displacement was M12. It moves to M13, because a coalition assembled out of
refused people is thin if there are four places to be refused from, and because
scenarios and the epilogue both read a world that does not exist yet. This
milestone builds the world the rest of the game has been assuming.

Rumour is explicitly **not** in scope. It was proposed and declined.

**A big world, and the cast is not bounded.** Many named cities, trading houses
that persist for generations, and travellers who do not. A small cast was
proposed and rejected: the point of the period is a dense, interconnected
Mediterranean, and a court that corresponds with six people is a diorama.

Scale is bought with **detail, not headcount**. A person is a cheap record —
id, name, place, house, a trait or two, a memory of the player. Only persons in
contact with the court are carried at full detail; the rest are records that
become detailed when the player's attention reaches them, and quietly stop being
detailed when it leaves. Determinism is unaffected either way: everything is
integers under seeded substreams and hashes as it always has. The thing to watch
is `state_hash` cost per turn, not correctness.

**The trade network is real and invisible.** Cities produce and demand; routes
have capacity and a season (the closed sea already exists, D7); prices move with
supply, demand, and events. None of it is projected to Belief. The player never
sees a price he has not been told, and the same three layers apply to being told
(D11), so a market report is a claim by a man with a reason to shade it.

**The envoy is the verb.** Reaching the network means sending a person: he
travels, which takes fortnights; he negotiates with his own competence, loyalty
and instructions; he comes back, or does not, and what he reports is his
account. He can exceed his instructions, be intercepted, take a better offer, or
come home having agreed something the king would not have. This is the main new
interaction and it is deliberately high-latency: the game is already about
acting on old information, and trade is where that hurts most concretely.

**Agency, generalised.** Cities and persons pursue their own wants each tick —
trade, ally, refuse, marry, move, raid. M9's marry-abroad-as-an-agent is the
working precedent and this is that, everywhere. The player learns what happened
by letter, from a participant with a bias, or from a third party who saw it.
Nothing is announced.

**The standing order is the open-ended verb, and it is the milestone's real
idea.** The player writes an instruction in prose. It is parsed into a structured
order — a trigger, a scope, a limit — and then *given to a person*, who carries
it out with his own competence, loyalty and reading of what was meant. He is not
a script the engine runs; he is a man doing his best with a sentence.

    "if the granary falls below four thousand parisu, buy grain at Gubla,
     up to twenty talents of bronze"

The competent, loyal official does roughly that. The literal one buys at Gubla
when Byblos was cheaper and closer, because Gubla is what the letter said. The
lazy one waits until it is convenient. The disloyal one buys at the price he
reports and pockets the difference. Every one of them writes back saying it is
done. This is what turns free text from a flavour feature into the deepest
system in the game, and it reuses `ai/parser.py`, the persona machinery, and the
oath-clause shape rather than inventing anything.

Orders are structured before they are stored, so replay stays deterministic: the
log holds the parsed order and the prose, and nothing is re-interpreted by a
model at load. Same rule as protocol grades (D9).

**Target:** a run in which the grain arrives late because the man sent to buy it
did what he was told rather than what was meant, and the letter saying so is
perfectly polite.

---

## D36. The look is 1993, and the furniture is one module

**The palette is sixteen saturated colours, not a spectrum of taupe.** The
brief was "tasteful but retro" and the failure mode of that brief is a beige
dashboard: six greys, a muted accent, and the visual personality of a settings
page. So the reference is fixed and specific — a DOS text-mode program of about
1993, on a CRT. Turbo Vision, Norton Commander, the shareware menu you booted
from a floppy. Amber that is actually amber, a red that alarms, lapis used as a
*field* and not as a tint.

Sixteen was a hardware limit then and is a discipline now. A screen that needs a
seventeenth colour is a screen doing too much, and the cap is enforced by a test.

**The furniture lives in `tui/style.py` and nowhere else.** Four pieces do all
the work:

* a **title bar** — a filled field over the top border, so a window announces
  itself the way text mode did, by inverting
* a **drop shadow** in `░`, one cell down and right, which says *these windows
  stack* without a compositor
* **key caps** — `[s] the stack`, the letter hot, the word plain
* a **status bar** along the bottom naming the keys that work here

Consequences taken deliberately:

* The title field covers only the title, not the whole top edge. A filled edge
  is handsome in colour and a hole in monochrome, where the rule would simply
  vanish; the border has to survive `plain_text`.
* A **door that is not built is drawn in ash and marked with a dot**, never
  removed. A player who can see the shape of the game and be told "not yet" has
  been told the truth; a menu that quietly shrinks has not. `hall.BUILT` is the
  single list, and the controller reads it rather than keeping a second one.
* The turn boundary is a **window**, not a redraw. A fortnight passing is the
  only moment the player does not control and it should feel like one. It
  reports what occurred and never what it means — D19 holds here as everywhere,
  and an empty fortnight is shown as an empty fortnight, because quiet is
  information.

**HELP is the free advisor, and it is a written page.** It knows the game —
which key opens what, what an hour costs — and it is never wrong, because
nothing in it is generated. COUNSEL will know the *world*, cost an hour, and be
able to be mistaken, because he is a person. That is the whole distinction, and
it is why HELP can ship without a model.

---

## D37. Art by station, and only where it earns its place

**Twelve faces, chosen by what a man is and not by who he is.** A face per
correspondent is wallpaper and, worse, it is a crowd of strangers; a dozen faces
reused for the stations of a small world — king, viceroy, merchant, overseer,
priest, scribe, physician, herald, queen, envoy, soldier, and the one for a man
nobody has placed — reads as a court. They are all 13x9, so a face can go in any
slot without the text beside it moving.

**No drawing carries a colour.** `art.draw()` colours by glyph *weight*: `█▓`
are the lit face of a thing, `▒░` its shadow, punctuation its edges. So the same
altar renders in flame at the altar and in ash on a ledger, and every drawing
survives `plain_text` as a picture rather than as a smear. A test walks every
drawing in the file for double-width glyphs — one would shear every column to
its right, silently, which is exactly the class of bug an eye does not catch.

**Where art is allowed:** the three settings D34 named (the hall, the altar, the
tablet house), and a face beside anyone who speaks. Nowhere else. A picture on a
ledger would make the numbers feel authored, and the numbers are the one thing
in this game that must feel found.

**The desk is the one window that takes typing**, so it owns every key it sees
and nothing falls through to the hall. A king who types `q` into a letter means
the letter q; a controller that quits instead has lost the tablet he was
writing. Changing the intent discards a dictation, and it is the only
destructive key on the screen.

**COUNSEL ships without a model.** Yabninu answers from the same Belief the
player could read himself, from memory, and is wrong about one answer in five —
deterministically, unexplained, with no tell to learn. When he is wrong he gives
a real figure from a real ledger, only the wrong one: the same rule as the
scribes (D11) and the diviner (M9). The only defence is the ledger, which is two
keystrokes away and costs nothing, and that is the lesson.

---

## D38. Counsel speaks through a model, and the command line is a person

**Reverses the "ships with no model" position in D33.** Yabninu is a chat. The
player types anything and he answers in character, with the run of everything
the king could see for himself — the roll, the stores, the oath clauses, the
men, the house, who is waiting — plus the conversation so far, so a follow-up is
a question he can answer. He advises, disagrees, and says what he would do,
because that is what a counsellor is for. A six-question menu is not a
character; it is a menu, and the player can already read a menu off the ledgers.

What is held back is game design, not caution: figures handed to him stale stay
stale (he is wrong about one thing in five, decided in `tui/counsel.py` before
any prompt exists, so it replays), and the answers to the game's puzzles are not
in his digest. He does not know which oath the gods are angry about any more
than the king does.

Authored lines remain for a machine with no Ollama. They are a fallback, not the
design, and nothing on screen says which the player got.

**The command line should be Yabninu.** The player does not type into a void; he
tells his scribe, who writes it down or misunderstands him. One box, one
character, whether the input is a question or an order.

### Three tiers of input, and only one of them may be wrong

| tier | interpreted by | may it be wrong |
|---|---|---|
| direct manipulation — a ration, the pay order, a posting | nothing | **never.** Fiddling with numbers must not go through a model |
| prose to the game — "read the tablet from Gubla" | the parser: deterministic first, model second | **no.** It is a keyboard shortcut; the player sees the result |
| prose to a person — "buy grain at Gubla if the granary falls under four thousand" | the man you gave it to | **yes, and that is the content of the game** |

Interpretation by the parser must never be wrong, because it is UI.
Interpretation by a person should be wrong, because it is the game.

---

## D39. The city is a machine, and the payroll row was always an institution

**Spec 6.18.** A `DependentGroup` becomes the staff of an `Institution` — a
building with a head, a condition and an output. `DependentGroup` is not
replaced and not touched: arrears, loyalty, desertion and the named petitioner
all keep working, and the institution is a derived layer over them.

The reason this is worth an entity rather than a screen: today, starving a group
produces a grudge. With institutions, starving the harbour **stops clearing
ships**, and the tin does not arrive, and no letter explains why. The same
decision the player already makes acquires a mechanism he can watch fail. That
is the difference between a number he regrets and a machine he broke.

Two multipliers, neither announced: `output_modifier` from arrears (6.3,
unchanged) and `condition` from neglect. Both are on the CITY screen for anyone
who looks, exactly as the melt ledger is on STORES (D19).

**Heads carry the three layers of number into the city (D11).** A head reports
his own institution's condition, and a head who has gone unpaid reports a
granary fuller than it is. `inspect` costs an hour and returns the truth. The
player finds out at the threshing otherwise.

**Every foreign city has the same shape and none of it is visible.**
`knowledge[place]` is `never | hearsay | visited`, and even `visited` shows the
head's figure rather than the truth. This is what makes M13's trade a thing done
with people instead of with a price table.

---

## D40. The four things a king did that the game had no verb for

Judging, taxing, appointing, and building. All four are added; **the bindings
that were paperwork are cut.**

* **Justice (6.19).** The hall already queues the people waiting. They become
  petitioners with a claim, a counter-claim, and a truth that is never
  projected. Four verdicts — for, against, split, defer — and deferring is a
  verdict that compounds. **Precedent is the mechanic worth building:** a ruling
  in year 2 is quoted back in year 9, and contradicting yourself costs double.
  Nothing marks a petitioner as honest and nothing says which verdict was right;
  the correction arrives later, as a letter, from someone who was there.
* **Revenue (6.20).** The land due and the harbour due. Both are a squeeze with
  a lag: raise the harbour due and the income lands this fortnight, the
  merchants leave three to six fortnights later. The lag is the design.
* **Appointment and the heir (6.22).** `place` generalises M9's marry-abroad to
  every post at home and abroad. Every trustworthy man is a member of your
  house; every one you place is a rival you have armed; every post you leave
  empty decays at 40 a fortnight.
* **Building (6.21).** The **corvée keeps its name** — it is the right word for
  the thing and the player should learn it. Projects consume materials as they
  proceed, only run in the right season, and use the same hands as the harvest.
  A wall is 4,000 days: a year and a half of labour spent on a guess about which
  crisis is coming, resolved long after you have forgotten you guessed.

**Cut:** `expiate` as a verb (it is what you do at the altar), `harvest` and
`recall` (an overseer's job — give the order to a man), `dredge` (a project),
`close`/`open` (quarantine with another name), `pri` (a column you order), and
`hush`/`defy` as separate verbs (one choice about one omen).

**Kept and given teeth:** `swear`. It is inert today because nothing pursues a
broken oath; it becomes the spine at M14, when the clause that says two hundred
men is the reason Carchemish comes or does not.

## D41 — the city is drawn, and it is drawn from the lie

A table of conditions with a sparkline each was legible and dead. The CITY
screen now stands its institutions up as buildings on one ground line, and
`art.weather` erodes each drawing to match its condition: dressed stone at 800,
hollow at 400, a dithered footprint at 100. Holes are punched on a fixed
`(x, y)` lattice, never at random — the same ruin every time, so repairing a
thing brings it back the way it went.

This is the fourth station to earn art after the three in D34, on a stricter
test than "it would look nice": **here the picture is the information.** A
player who never reads a figure on this screen can still see which quarter of
his city is going, which is exactly the failure mode 6.18 risks — two hidden
multipliers and a flattering head add up to a system that reads as random.

And it draws the *reported* condition, not the true one. The harbourmaster in
arrears says his quay is sound, so the quay is drawn sound. The lie is in the
picture now, which is where a lie belongs, and `inspect` is what buys the truth.

The one invariant worth a test: **weathering is monotone in condition**, counted
by glyph weight rather than eyeballed. A step that swapped a glyph for a heavier
one would read, at a glance, as a building being repaired.

## D42 — building costs hands, and the hands are the harvest's

`Project` (6.21) draws its days from `Court.corvee_days` — the same seasonal
pool `land.labour_supplied` feeds the estates from — through a second counter,
`Court.works_days`, that the fields subtract. That subtraction is the entire
cost of building. Not the goods: the hands, billed a year later at a harvest
with nothing to connect it to.

Three consequences, all deliberate:

**Materials are what the men eat.** One rate for every project, charged per
thousand days worked, and the biggest line in it is grain. A building site
competes with the granary directly, which is what makes a wall a bet placed with
your food.

**Nothing is refunded.** Calling the men off returns the unspent days to the
season's pool and nothing else. What they ate is eaten. A project you can cancel
cleanly is a purchase, not a decision.

**Nothing explains a fortnight in which the number did not move.** Out of
season, out of corvée, and out of grain look identical from the palace, and the
fortnight report says nothing about any of them (D19). Only `WorkFinished` is
announced, because the opening of a granary is a day the city keeps.

A repair is priced when the order is given and never revised. The fabric decays
while the men work, so a repair commissioned at 400 lands near 950 rather than
at 1000. That gap is not a rounding error, it is the interest on having left it.
