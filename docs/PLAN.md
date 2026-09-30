# Plan: tell the engine in words

- Status: Do now 1–5 and Do later 1–2 built 2026-09-29 on branch `words-first`. Owner playtest pending.
- Written: 2026-09-29

## Problem

The engine is deep, but the player cannot see it. The playtest notes say so:

- "do I have 3 million what of grain?" and "I don't like doing math in my games"
- "I see grain declining but I don't see what I have to do"
- "does replying actually have any effect?"
- "who tf asks all these people"
- "I want an LLM tab to help with actual playing"

The Hall shows kernel units: `grain 42,670 qa Δ−108,394 qa`, `work 127,320 days`.

## The rule

The engine decides. The facts layer measures. The model speaks.

```
World ─project()─▶ Belief ─facts()─▶ Facts ─narrator─▶ words on screen
                                       └──── template line (model slow or out)
```

- Words first. Every screen opens with: what is wrong, why, what the king can do.
- A number appears only where the player acts on it or compares it.
- Numbers use human units, rounded to about 2 figures: fortnights, men, days.
- Exact ledgers stay one key away, behind "details".
- The model sees only Facts. It never sees World. `ai/numeric_guard.py` still applies.
- Template lines must read well alone. The model adds a voice, not the meaning.

Prose rules for templates and model (from the owner's notes):

- Short sentences. No adjectives that carry no fact. No metaphors.
- Never state the obvious. Bad: "Lower unrest means a calmer city."
- Good: "Bread lasts 3 fortnights. Harvest comes in 2. The gap is 1 fortnight."

## Parts

**Fact** (`belief/facts.py`, deterministic, no model). One record per topic:

```
{"id": "grain", "say": "grain lasts about 3 fortnights", "trend": "falling",
 "why": ["rations for 5 groups ate 108,000 qa", "harvest in 2 fortnights"],
 "urgency": 3, "source": "steward of the granary", "sure": "counted",
 "act": ["buy grain", "ask a court for aid", "cut rations"],
 "exact": "42,670 qa"}
```

`sure` is `counted`, `reported` or `rumour`. It comes from Belief distortion.

**Why.** At the end of each tick, sum the seat's `Transfer`s by `phase` and `reason`.
Keep the top flows per good on the court record, like `_record_stores` in
`engine/tick.py`. Belief projects them. No new simulation.

**Narrator** (`ai/narrator.py`). Input: the top facts by urgency, plus last
fortnight's receipts. Output: the steward's briefing, 6 sentences at most.
Order: last fortnight's result, what changed, why, what comes next, what to do.
It runs in the background while the tick resolves. The text is cached in the
campaign `ai_cache` by seed and turn, so replay never reruns the model.
A failed guard gives the template lines. If the prose is weak, try `STTKML_MODEL=qwen3:14b`.

## Where the words appear

1. **Briefing** at the top of the Hall. It replaces the STORES, STANDING and RATIONS blocks.
2. **Receipt** after each decision: what moved, who is pleased, who is angry.
3. **People tag** on every speaker: who they are, what they want, their side.
4. **Why** key on any meter or matter. It speaks the fact's `why` list.
5. **Ask** window: one chat for "how do I" and "what should I do". It merges `ai/counsel.py` and `ai/help_agent.py` over the same Facts.

## Do now (built; playtest pending)

1. **Decide.** Done 2026-09-29: plan approved, pending work committed, SPEC 3.4
   rewritten, old plan docs deleted.
2. **Facts and why** (1 session). `belief/facts.py` for grain, labour, stores,
   standing and unrest. Record the Transfer flows in the tick.
   Check: `./run.sh --screens hall` shows "grain lasts about N fortnights" and 2 causes.
3. **Words-first Hall** (1 session). Template briefing, meters as words plus
   one number, details key for the ledgers. No model yet.
   Check (owner, 15 min): play 3 fortnights. Say the worst problem, its cause and one action, with no math.
4. **Narrator** (1 to 2 sessions). Briefing, receipts and the Why key through the model.
   Check (owner, 15 min): end 5 fortnights. The briefing arrives in under 10 s.
   The briefing has no invented number and no line you would call AI prose.
5. **People and Ask** (1 to 2 sessions). Add `wants` and `side` to the
   correspondents and cases in `content/`. Build the Ask window.
   Check (owner, 15 min): ask "what should I do about grain?" and "how do I buy grain?".
   Both answers must be correct and short.

## Do later

1. Done: facts for trade, letters and foreign courts, with `sure` spoken.
2. Done: facts for plague, troops and works.
3. A narrated World map: one line for each place the court knows about.
4. Delete every number panel that words have replaced. Do not keep both.
5. Balance only after the owner can read the game.

## Done when

The owner plays one year (24 fortnights). At any fortnight, the owner can answer
these 3 questions from the screen alone: What is my worst problem? Why? What can
I do? No test suite. Verify with `./run.sh --check`, `./run.sh --screens` and F8 notes.
