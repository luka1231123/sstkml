"""One scroll model for every list in the game (UI/UX spec 8, 23.3).

The audit's ninth systemic problem: many collections showed a fixed subset --
the first nine search results, the first eight petitions, the first nine
members of the house -- and simply did not draw the rest. That is not a display
limit, it is a silent loss of state. A tenth petition is a real petition, and a
game that hears eight of them is wrong in a way no screenshot reveals.

The rule this module enforces is the specification's: *no row is unreachable*.
A collection knows its length, how many rows the window can spare, and where
the selection is; from those it yields a page and, when the page is not the
whole thing, says so in words the player can act on.

Everything is integers and pure functions, so the acceptance test can render a
list at 0, 1, 9, 10, and 100 rows and assert every row is reachable without
opening a window.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Page:
    """A slice of a collection, and what to say about the rest of it."""

    start: int
    end: int
    scroll: int
    total: int
    room: int

    @property
    def more_above(self) -> bool:
        return self.start > 0

    @property
    def more_below(self) -> bool:
        return self.end < self.total

    @property
    def partial(self) -> bool:
        return self.more_above or self.more_below

    def slice(self, items):
        return list(items)[self.start:self.end]

    def rows(self, items):
        """Visible items as `(display number, index in the whole, item)`.

        The display number restarts at 1 on every page, because it exists to be
        typed: the keyboard has nine digits and a collection may have four
        hundred rows, so `[3]` must mean the third row the player can see. The
        absolute index comes with it so the controller can resolve that back to
        the right member of the collection without recomputing the page.
        """
        return [(number, index, item)
                for number, (index, item) in enumerate(
                    enumerate(list(items)[self.start:self.end], self.start), 1)]

    def absolute(self, number: int) -> int:
        """The index a typed display number refers to, or -1 if it is not shown."""
        index = self.start + int(number) - 1
        return index if self.start <= index < self.end else -1

    def label(self) -> str:
        """`13–21 OF 42`, or `NONE`, or nothing when everything is shown."""
        if not self.total:
            return "NONE"
        if not self.partial:
            return f"{self.total}"
        return f"{self.start + 1}–{self.end} OF {self.total}"


def page(total: int, room: int, scroll: int = 0,
         selected: int = -1) -> Page:
    """The visible window over a collection, with the selection kept in view.

    `scroll` is an offset rather than a page number, so a controller can move
    by one row or one screen with the same field. It is clamped rather than
    rejected: a window that shrinks under a scrolled list must show something
    sensible instead of an empty rectangle.
    """
    total = max(0, int(total))
    room = max(0, int(room))
    if not room or not total:
        return Page(0, 0, 0, total, room)
    scroll = max(0, min(int(scroll), max(0, total - room)))
    if 0 <= selected < total:
        # Reveal the selection. Moving off the bottom of a list must scroll it,
        # not silently move a cursor the player can no longer see.
        if selected < scroll:
            scroll = selected
        elif selected >= scroll + room:
            scroll = selected - room + 1
    return Page(scroll, min(total, scroll + room), scroll, total, room)


def step(total: int, selected: int, by: int) -> int:
    """Move a selection by `by` rows, stopping at the ends rather than wrapping.

    Wrapping is wrong for a docket: a player pressing Down at the last petition
    means "no more", and jumping to the first one reads as a lost keystroke.
    """
    if total <= 0:
        return -1
    return max(0, min(total - 1, selected + by))
