# From working court to compelling reign

Current handoff, 2026-09-16: [playtest the decision-review build](PLAYTEST_DECISIONS.md).
The sections below retain the earlier assessment. The guided Hall has since been
retired; the returning debt/household-grain claim and competing advice already
exist. Do not reimplement them from this historical proposal. Follow
[AI_NEXT_PLAN.md](AI_NEXT_PLAN.md) for current priorities; a larger workshop arc
remains deferred until the existing loop is understood and worth playing.

Assessment: 2026-09-15. These are design conclusions from the current code and
the linked games' official descriptions, not a comparative human playtest.

Playtest update: the first returning-character slice is now implemented as a
continued debt dispute or a household grain request, selected by the original
award. It moves real goods and allows refusal; it does not yet simulate a
workshop commission. The Hall now includes conflicting institutional advice,
an annual reckoning and earlier relief prompts. Opening reserves are tighter,
and F8 captures playtest notes in a separate campaign folder. The larger
workshop arc and sensory polish below remain future work, guided by this test.

## What the comparisons expose

- [Yes, Your Grace](https://store.steampowered.com/app/1115690/Yes_Your_Grace/)
  ties limited supplies to petitioners, family problems and returning characters.
  The useful lesson is to attach a resource choice to someone the player knows.
- [Suzerain](https://www.suzeraingame.com/) gives cabinet members their own
  agendas and connects national policy to family, allies and a final legacy.
  The useful lesson is disagreement with lasting personal stakes.

Our missing connection is between an order and the next situation involving
the same people. `engine/justice.py` pays the claimant, changes city unrest and
removes the petition. It does not yet create a later situation for that claimant
based on the ruling. More dialogue alone would leave that gap intact.

## Delivered foundation

The guided Hall selects real matters, explains units and costs, and opens the
right record. Court verdicts show understandable payments. Named receipts now
carry into the following fortnight, alongside people whose claims still wait.
Ration and labour orders are paired with the next recorded arrears; that is an
observed comparison, not a claim that the order caused every change.
The existing Orders history preserves past decisions. These are navigation and
continuity improvements, not a completed relationship simulation.

## Remaining work, in order

1. **One returning person with a consequential arc.** Start with the shipwright.
   Record the ruling in authoritative state. A later request must depend on
   the payment and actual workshop resources, labour and time. Assistance can
   enable work; it cannot conjure a repaired ship. A refusal must leave a
   playable alternative. Show the original ruling in the return audience.
2. **Different credible advice.** Give two existing officers different
   priorities about the same real shortage. Each argument cites information
   they possess and offers a valid action. The player chooses whose cost to bear.
3. **A legible first-year purpose and payoff.** Show the coming harvest,
   outstanding obligations and the condition of the people at year's end.
   Use a retrospective tied to actual choices, with unresolved problems that
   motivate a second year. Do not imply there is only one correct policy.
4. **Pressure and recovery that need decisions.** The measured passive first
   year ends without ration debt. Test several seeds and competing policies
   before claiming urgency; tune causes and recovery opportunities together.
5. **A complete beginner playtest.** Observe someone reaching a first decision,
   explaining its cost and recognizing its later result without coaching.
   Follow with the whole year. Automated checks cannot establish that it is fun.
6. **Sensory polish after the loop works.** Clear arrival cues, seasonal changes,
   readable portraits and optional restrained sound should make events legible.

## Where AI programming helps

Use AI during development to implement and explore conditional story branches,
generate varied simulated play policies, and check conservation, replay and
what each character could know. Review the resulting authored situations.
At runtime the language model can express a person's known situation and
remembered decisions in their own voice. Engine records must determine those
memories, available actions, payments and outcomes. Test that changing the
wording cannot change a verdict or reveal an unread answer.

The next milestone is one complete returning-character arc with at least two
materially different, recoverable outcomes, visible in both replay and play.
