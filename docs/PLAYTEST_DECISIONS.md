# Playtest: can you understand an order and recognize what followed?

Build: 2026-09-16. Start a fresh, separate campaign:

```sh
./run.sh --playtest seat 8814402919
```

Use F8 whenever something surprises you. Write what you expected, what happened,
and what you wanted to do next. Ctrl-Enter saves the note; Escape closes it while
keeping its draft. Long notes wrap. Colons and question marks stay in the editor.
The note captures the originating screen, seed, turn, hours and three recent
orders, including when you opened it from a confirmation. Notes remain local in
`saves/seat/playtest-<timestamp>/notes.jsonl`, beside that campaign's autosave.
You do not need to copy screenshots or repeat the turn number.

## First session: decisions, not a prescribed winning strategy

1. **Hear the shipwright.** Read both arguments and choose a ruling. Cancel its
   review once, then give the ruling you want. Can you explain the payment and
   unrest effect before pressing Enter? Note any wording that implies a reward
   or consequence the game has not actually promised.
2. **Try Muster.** Tab to Hall, then M. Use up/down to choose a formation, T to
   change its proposed duty, and L to change destination. Left/right reads detail
   pages. A reviews the order; left/right reads a long review; Escape cancels.
   Confirm an assignment when satisfied. Do you understand which place loses
   defenders, which gains them, and what watch means? Try shrinking the window.
   The task/place controls must remain visible. O/K opens the Palace for commanders.
3. **Read the receipt.** Ctrl-H returns to Hall. O opens Orders. Choose Everything
   with 3, use arrows to choose an order, and left/right to read its details.
   Can you distinguish the order you gave from what the current roll reports?
4. **Compare food choices.** Hall → T opens Storehouse. Look at counted grain,
   reserved grain and the available estimate. Read the history description.
   Hall → X opens Trade. F reviews a local grain purchase; cancel or confirm it.
   Is the copper unit clear? Can you find how much grain was actually received
   in Orders afterward? Does the purchase feel meaningfully different from a
   foreign request?
5. **Ask Yabninu.** Hall → J → C. Ask a question or write an order. Questions cost
   an hour; orders are reviewed before a second Enter. Page Up/Page Down reads
   conversation history or a long pending order. If suggestions are displayed,
   Ctrl-1/Ctrl-2 copies one into the input without sending it. Try a long answer
   and a cancelled order. Does anything disappear that you still need?
6. **End the fortnight.** Ctrl-H, then Space. Leave Court with Tab and use L for
   the report. Find your assignment and purchase. Does the report help explain
   what changed, or merely repeat numbers? Record that distinction.

You can stop here with useful notes. Do not force every action into one
fortnight: attention is limited. If a control fails, note it and continue
elsewhere rather than finding a workaround silently.

## Then play a year your way

Continue to turn 24. Judge or defer claims, allocate food and hands, and use
Trade's G/Relief view to request grain if that seems useful. Read replies and
look for actual cargo; an accepted letter is not a delivery. Follow the
shipwright's return after your first ruling. Use notes at these moments:

- you cannot tell what needs attention;
- you cannot predict what an order will spend;
- a later event seems unrelated to your decision;
- waiting seems just as good as intervening;
- you understand a tradeoff and genuinely want to choose;
- year end arrives: what would make you want to play the next year?

Optional second run: use the same seed, make a different first ruling, and be
more selective about payments. Compare who returns and what they ask for.
There is no requested “correct” outcome. A player choosing to wait is evidence,
not a failed playtest.

## What changed for this test

- Muster prioritizes controls over artwork, pages long details, and reviews an
  assignment before spending its hour. The preview compares equipped defence
  contributions and known summons; it does not invent additional harvest work.
- Local trade states the copper purse, counted price, estimated receipt/payment
  and remaining copper. Its receipt uses the actual goods transferred.
- Stores labels its available-grain estimate and history; long details remain
  reachable. Orders also pages receipts and is one key away from Hall.
- Assignment and purchase receipts carry into the next report and survive saves.
  Counsel uses the same action/receipt path after its compound-order preflight.
- Counsel makes room for conversation, recovers earlier text, and pages complete
  pending orders. Confirmation dialogs page instead of cutting off long orders.
- Notes attach the actual originating window and readable screen, wrap long text,
  and no longer treat punctuation as window-opening shortcuts.

## Known boundary

The existing troop `harvest` assignment does not feed the current kernel's farm
labour calculation. The interface now says so and points to Land/Rations for
working harvest assignments. Connecting those systems requires a separate
conservation and balance change. No engine balance, save format, artificial
crisis, extra claimant or victory condition was added for this test.

The next decision depends on your notes: repair comprehension first; then compare
player-feasible policies and tune the demonstrated causes of weak tradeoffs.
