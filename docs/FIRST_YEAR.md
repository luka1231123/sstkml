# Play the first year

Start a reproducible campaign with `./run.sh seat 8814402919`.
The normal local language service is still required. This starts a new game;
version 27 saves cannot be loaded after the correspondence repair.

Your first objective is to reach the next sowing with food, seed and a working
court. No score or scripted success screen is attached to this objective.

New games open Yabninu's briefing. Enter opens his selected matter without
spending time; arrows choose another. Start with the grain count, then return
with Ctrl-H. The briefing responds to your orders and brings a named court
dispute forward after that first inspection. In Court, read both accounts and
the three labeled payments before choosing a verdict. A preview can be
cancelled; a confirmed judgement produces a receipt naming who was paid.

Tab in Hall switches to the full palace; Tab again returns to the briefing.
Neither view requires you to clear the list before ending a fortnight.

1. In Hall, read the granary coverage and the season. Open Storehouse and inspect
   the grain count if you want to spend an hour improving that record.
2. In Storehouse → Rations, inspect who goes short. Brackets draft a ration;
   left/right draft the queue. Enter gives the displayed order, Escape cancels.
   When arrears exist, R drafts repayment from unreserved grain. Compare the
   debt it clears with the grain left for the next queue. A repayment does not
   instantly restore goodwill or strength.
3. In Trade, G from Exchange opens Relief. Choose a known court and a quantity.
   Enter prepares a grain request in Scribes. Edit the matter, review the terms,
   then seal and confirm. This is a request for help, not a purchase. You can be
   refused, sent less, kept waiting, or lose the courier or cargo.
4. On the eve of harvest, choose a group in Rations and press H. The review
   compares the shared crop with labour before the deadline. Enter commits;
   Escape cancels. The estimate assumes unchanged crop and strength. If the
   shortfall is already zero, extra labour is not needed to meet that estimated
   deadline, and the group's ordinary work is still a real competing use.
5. End the fortnight in Hall. The report compares expected ration debt with the
   new payroll and shows field counts, cargo receipts and letter-status changes.
   Use arrows, Page Up/Down, Home/End to read the entire report. Space closes it;
   it does not advance another turn. Open Scribes to read an arrived answer.
6. Recheck the labour roll after harvest. Plan next sowing from the grain and
   seed you actually hold. Orders retains the figures recorded when you sent
   hands or paid debt; the latest report is preserved in the save.

For development, run `.venv/bin/python tools/first_year.py`. It compares waiting
with a small policy that reads only player Belief, writes replayable saves and
reports under `output/first-year`, and lists any refused actions. This is a
repeatable exercise of the loop, not an optimal strategy or a fun rating.
