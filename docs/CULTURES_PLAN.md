# Cultural campaigns and clear language

Requested 2026-10-06. This is the current implementation plan.

## Result

Keep the original movable palace windows. Expand the five existing campaigns
with Pylos, Pi-Ramesses and Hattusa. Each new court must have its own population,
royal household, institutions, foreign obligations and governing decisions.
Differences must affect goods, labour or authority, rather than only names.

## Work

1. Author three complete campaigns using the existing world map and canonical
   seat remapping. Use Mycenaean palace administration at Pylos, an Egyptian
   royal administration at Pi-Ramesses and the Hittite imperial court at Hattusa.
   These are historically inspired scenarios, not reconstructions of an exact
   documented reign. Change inherited local cults, names, rites and testimony.
2. Add a governance account and culture-specific orders. Use existing living
   households, real inventories and stated obligations. Collection transfers
   available goods; it cannot mint tribute. Relief spends royal goods. Give
   every order a visible cost, destination, cooldown and receipt.
3. Put those orders in a native window reachable from the city charter. Keep
   reading free. Review paid orders through the existing confirmation flow.
   Expand the city selector to eight campaigns without overlapping its details
   or consuming a campaign number for the resume control.
4. Rewrite player-facing prose across screens, authored content, deterministic
   briefings and model prompts. Use short sentences, named actors and concrete
   actions. Keep quantities, uncertainty, deadlines and consequences. Avoid
   metaphors, motivational language and lectures about obvious mechanics.
   A tablet voice may say who received what; it must remain easy to read.
5. Integrate the new accounts into the fortnight report and city goals. Show
   the actual result and explain failures such as missing grain or workers.
6. Preserve recorded version-30 histories. Existing campaigns retain their
   previous engine behavior until their saved content cutoff. New governance
   must not change a previously recorded transfer or generate surprise replay
   events. New campaigns use separate autosaves.
7. Run ordinary campaign progression and native interactions. Inspect all
   eight opening screens, governance orders, receipts and save/resume. No new
   automated test suite. Record limitations honestly.

## Division of work

- Campaign author: new court content, loader support and new city chapters.
- Governance author: state, actions, engine rules and public projection.
- Prose editor: screen and content prose, plus model style instructions.
- Main agent: plan, native controls, reviews, registry, reports, integration
  and final gameplay inspection.

## Completion requirements

- All eight courts load, advance and have distinct readable introductions.
- Pylos, Pi-Ramesses and Hattusa have reachable governing orders with real effects.
- The player can identify what an order costs and whom it affects before use.
- Existing saves resume and future orders are saved deterministically.
- City selection, goals and governance controls fit their native windows.
- No general replacement of the desktop with a web interface.

## Completed

Implemented all eight campaign openings, three governing accounts and their
native controls. Rewrote screen prose, authored fallback letters and generation
prompts. Corrected letter identities and rank forms for current rulers.

Ordinary six-fortnight runs closed each new account successfully and resumed
from its save with matching court state. Assessment outside harvest failed;
assessment with actual harvest receipts succeeded. Hattusa troops at Carchemish
reduced home defence. Existing Byblos version-30 save resumed. Native inspection
confirmed all eight selector choices, the charter link, order review and a
recorded Pylos tool issue. No automated test suite was added or run.

Scope limits: the six-fortnight institutional cycle is a game abstraction.
Egypt shares the existing agricultural seasons. Hattusa uses the existing
military-assignment and diplomacy systems; this is not a complete empire
administration or combat reconstruction. Long-term balance and enjoyment still
need ordinary play.
