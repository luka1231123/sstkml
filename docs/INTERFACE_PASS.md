# What changed in the interface pass

Measured against seed 8814402919 at turn 6. Every screen below was read as
text with `python3 tools/screens.py all`, not looked at in a window.

## One room hears claims

The palace's judgement view is deleted. It showed the same case, the same two
arguments and the same three payments that Court already shows at the top of
the fortnight, so the game asked the player to decide one thing in two places.

- `palace.compose` no longer accepts `court`, `audience` or `justice`; a caller
  asking for one gets the people instead.
- `_court_controls` and `_court_catalog` are gone, and `CONTEXT_OF` no longer
  claims the `justice` context.
- `palace_court` is gone from the controller.
- The room is named **the Palace**. It holds people, offices, the house and
  foreign courts. Court hears the claims.
- `_evidence_lines` and `_court_detail` stay: Court draws its cases with them.

## Window sizes match what the screens draw

`tools/screens.py` had its own sizes, larger than the ones the game opened
windows at, so every screen read better in the tool than in play. The reader
now takes every size from `tui/desktop.py`, and the defaults were raised to
what each screen actually needs.

| window | was | now | why |
| --- | --- | --- | --- |
| palace | 74x25 | 82x30 | showed one row of ten people |
| altar | 54x24 | 74x30 | drawn for 78 columns; opened at 54 |
| alu | 74x25 | 86x32 | four buildings and their rows |
| stack | 80x27 | 82x28 | |
| orders | 72x24 | 84x28 | |
| works | 66x23 | 78x30 | nine plans against one detail pane |
| trade | 72x24 | 76x26 | |
| muster | 64x22 | 72x26 | |
| oaths | 62x22 | 70x26 | |
| plague | 62x22 | 72x26 | |
| counsel | 52x18 | 62x24 | six rows of conversation |
| letter, archive | 50x20 | 62x26 | |
| institution | 50x19 | 60x24 | |

Minimums are unchanged, so nothing that fitted before stops fitting. The
desktop contract still holds: Hall and Scribes fit side by side in 166 columns,
Palace and Storehouse likewise, and two rows of windows fit in 58 rows.

## Names

- The palace room is the Palace, not the Court.
- The last report panel says THE LAST REPORT, not THE COURT.
- The Hall's door `j` is Palace.
- The window is titled "Court and Hall".
- The muster is the Muster everywhere; it used to also be called the Corvée.

## Contracted notation removed

- Shrine: `skip L-180 U+120` is now `skip it: standing -180, unrest +120`, on
  its own row, clear of the altar drawing. Each rite takes three rows: when it
  falls, what it takes, what skipping it costs.
- Land: `ordered 150/1000` is `the due is 150 qa in every 1,000`;
  `returns 7,000/1000` is `yields 7,000 a 1,000`;
  `gauge 27 · ordinary 30 · the scribe's copy` is
  `the flood measured 27, ordinary is 30`.
- Land: the hands line drops words instead of cutting `idle` in half.
- Roll: an arrow between two equal numbers now prints one number.
  `0 / 107,790 qa = 0 full-roll fortnights` is
  `the grain left feeds the whole roll for 0 fortnights`.
  The column head `ration old→new` is `ration qa`.
- Works: the banner `CORVÉE, NOT COIN · LOW WATER · STORE-FED CREWS · NEW WORK
  OPENS HEADLESS` is one sentence: `Paid in called-up men and stored goods, not
  silver · low water`. `RETURN` and `WAGER` are `GIVES YOU` and `COSTS YOU`.
  `MEN OUT` is `WHAT IS BEING BUILT`.

## The Hall stopped repeating itself

The header printed the granary, the city's temper and the king's standing, and
the columns below printed all three again.

- The header keeps the hours, the sea and one granary line.
- The grain year runs the full width at the top, so it prints in full:
  `growing · 8 of 9 · 2 fortnights left · then harvest in 2` instead of
  `grow 8/9 · reap in 2`.
- Rations and work print the shortfall when there is one and say they are met
  when there is not, rather than `107,790 of 107,790`.
- Reserved and unspent grain print only when they are not both zero.
- `0 fortnights fed` is `not one whole fortnight fed`.
- `1 judgements wait` is `1 judgement waits`.
- Matters take one row each, speaker first, which gives the waiting list three
  rows instead of one.
- Door counts are `(4)` rather than a glyph and a number.

## Court

The claim comes before the pressure. The order was: how long the man has
waited, then his claim, then the answer. It is now claim, answer, then
`Waiting 5 fortnights · unrest +2 a fortnight after 2`, then the payments.

## Every control is spelled one way

`[esc]`, `[enter]`, `[tab]`, `[space]`, and lower-case letters, in every
window. The game had `[esc]` eleven times, `[Esc]` nine and `[Escape]` twice,
`[Enter]` eleven and `[enter]` five, and Court alone printed `[F] [A] [S]`.

## No Tk widgets left

The order review, the officeholder picker and the playtest note were raw Tk
panels with system buttons and a scrolling text box. They are grid windows now,
drawn through `tui/dialog.py` like every other screen. Help was a `ttk.Notebook`
with two `ScrolledText` tabs; it is one screen with Manual and Ask halves,
switched with `tab`.

The order review is modal in effect rather than by a window grab: while one
waits, `enter` and `esc` answer it from whichever window has the focus.

## Removed

- `tui/briefing.py`, earlier in this branch.
- `tests/test_hall_refocus.py`, which tested the deleted palace ornament.
- `tests/test_court_evidence.py`, which tested the deleted judgement view.
- Two adviser tests in `tests/test_living_court.py` and one docket test in
  `tests/test_collections.py`.
- The dead `hall_guided` flag from the controller and the save format.

## Verification

632 tests pass. The authority, information and inventory audits report no
findings. A native Tk run drove Court, the Hall, the Palace, the report, the
appointment picker, Help and the end of a fortnight.

## Still open

- The turn-82 finding: passive play still survives. Nothing here touches it.
- Storehouse and Trade wording is untouched.
- The Counsel portrait still takes nine rows of a 62-column window.
- The Muster still does not say who is being called or what calling costs.
