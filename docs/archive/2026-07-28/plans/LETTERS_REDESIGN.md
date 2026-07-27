# Parked design: letters and replies

Status: intentionally deferred until after the dashboard, Counsel ordering, and
Inbox navigation are working.

## Direction agreed so far

Outgoing correspondence should begin with the player's own words, not with a
choice among same-shaped reply templates.

The likely pipeline is:

1. The player writes or dictates what the king wants to say.
2. The court/scribe formats those words according to the recipient's diplomatic
   conventions.
3. The game shows the resulting tablet before it is sealed.
4. The recipient distills the sent text into one or more understood actions,
   promises, refusals, threats, requests, or relationship signals.
5. Those interpreted meanings, rather than a UI intent button, drive the
   simulation consequences.

The king's wording must remain consequential. Formatting may add address,
prostration, self-designation, and closing formulae, but it must not silently
replace, soften, strengthen, or invent the substance of what the player wrote.

## Questions reserved for the later design pass

- Does the player review the formatted tablet, or is trusting the scribe part of
  the risk?
- Can the scribe misunderstand the player's raw instruction?
- Are extracted actions shown to the player, or only discovered through the
  recipient's later behaviour?
- How are multiple topics, conditions, quantities, deadlines, and promises
  represented?
- What happens when prose is diplomatic but operationally ambiguous?
- Does sending still cost a flat two hours?
- Which exact text and extracted meanings belong in the replay log?
- How does the offline/no-model path preserve the same expressive range?
- Should incoming letters use a similarly structured interpretation pipeline,
  or remain authored reports with prose on top?

No implementation of the current Desk/composer should be expanded until these
questions are resolved.
