"""List, detail, and the actions that belong beside them (UI/UX spec 15, 8).

The Stores, the Roll, the Land, the Muster and the Oaths were tablets: framed
tables that could be read and closed. Everything they described was changed
somewhere else, and in practice that somewhere else was Counsel -- which is to
say the only route to half the game's mechanics ran through the optional model
layer. That is the audit's fourth systemic problem and the thing this module
exists to end.

The shape is the City's, because the City is the screen that already works: a
thing to look at, a table to compare it against, and the exact order beside the
evidence for it. Here that is a scrolling list on the left, the selected row's
detail on the right, and a footer of the actions this screen actually offers --
drawn from `registry.in_context`, so a screen cannot advertise an action the
registry does not have, and an action added to the registry appears here with
the cost the rest of the game charges.

Nothing in this module knows what a granary is. It lays out rows and controls;
`tui/ledgers.py` says what the rows mean.
"""
from __future__ import annotations

import dataclasses

import registry
from tui import collection, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX


@dataclasses.dataclass(frozen=True)
class Row:
    """One line of the list, and the id an order will name."""

    id: str
    cells: tuple[tuple[str, str], ...]      # (text, colour name)
    mark: str = ""                          # a glyph, never a colour alone


@dataclasses.dataclass(frozen=True)
class Control:
    """One offered action: its key, what it says, and whether it is possible.

    `why` is the reason it is not, and it is drawn beside the disabled key
    rather than hidden. A control the player can see and cannot use is
    information; a control that vanishes is a lie about the shape of the game.
    """

    action_id: str
    key: str
    label: str = ""
    enabled: bool = True
    why: str = ""

    @property
    def descriptor(self) -> registry.ActionDescriptor | None:
        return registry.BY_ID.get(self.action_id)

    def caption(self, hours: int) -> str:
        descriptor = self.descriptor
        text = self.label or (descriptor.short_label if descriptor else
                              self.action_id)
        if descriptor is not None and descriptor.cost:
            text += f" · {descriptor.cost}h"
        return text


def affordable(control: Control, hours: int) -> Control:
    """Disable what the fortnight can no longer pay for, and say so."""
    descriptor = control.descriptor
    if not control.enabled or descriptor is None:
        return control
    if descriptor.cost > hours:
        return dataclasses.replace(
            control, enabled=False,
            why=f"needs {descriptor.cost}h, {hours} left")
    return control


def tabs(surface: Surface, x: int, y: int, width: int,
         choices: tuple[tuple[str, str], ...], chosen: str) -> None:
    """A row of named views over the same window.

    Tabs are a promise that the window keeps its identity while the player
    looks at it from another side -- so the strip is always drawn in full, and
    the unchosen tabs stay legible rather than fading to decoration. Each is
    clickable and each answers to its own number.
    """
    for index, (key, label) in enumerate(choices, 1):
        if x >= width - 2:
            break
        here = key == chosen
        text = f" {index} {label} "
        surface.text(x, y, text[:max(0, width - x - 1)],
                     C["ink"] if here else C["clay"],
                     C["sand"] if here else C["faint"])
        surface.link(x, y, len(text), 1, f"tab:{key}")
        x += len(text) + 1


def compose(title: str, headers: tuple[str, ...], widths: tuple[int, ...],
            rows: list[Row], selected: str, detail: list[tuple[str, str]],
            controls: list[Control], hours: int,
            width: int, height: int, scroll: int = 0,
            notice: str = "", empty: str = "nothing here.",
            note: str = "",
            views: tuple[tuple[str, str], ...] = (),
            view: str = "") -> InteractiveScreen:
    """The whole screen: list left, detail right, controls along the bottom."""
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title=title,
                note="[esc] close", drop=False)
    style.notice(surface, 2, 1, width - 4, notice)
    if views:
        tabs(surface, 2, 2, width, views, view)

    # The list gets the width its columns actually need, and the detail takes
    # what is left -- rather than a fixed share, which cut the last column off
    # every wide table and hid the very figures the screen exists to compare.
    natural = sum(abs(spec) for spec in widths) + 2 * len(widths) + 2
    stacked = width < 68 or natural > width - 24
    if stacked:
        list_width, detail_x = width - 4, 3
    else:
        list_width = max(30, min(natural, width - 24))
        detail_x = list_width + 4

    top = 3
    style.bar(surface, 2, top, list_width, " ", fg=C["bone"], bg=C["faint"])
    _columns(surface, 3, top, headers, widths, list_width,
             header=True)

    # The list. Height is what is left after the footer and, when the panes are
    # stacked, after the detail that now sits beneath it.
    footer_rows = rows_needed(controls, hours, width)
    available = height - top - 3 - footer_rows
    if stacked:
        # Both panes in one column. The list keeps at least a third of what is
        # left, so a long detail cannot squeeze the collection down to a single
        # row -- which is a list that has stopped being a list. The detail is
        # what gets cut, and it is cut at the end, where the least urgent lines
        # already are.
        room = max(1, min(available - 4, max(available // 3, 5)))
        detail = detail[:max(0, available - room - 1)]
    else:
        room = max(1, available)
    body = room
    chosen = next((n for n, row in enumerate(rows) if row.id == selected), -1)
    page = collection.page(len(rows), room, scroll, chosen)
    if not rows:
        surface.text(3, top + 2, empty[:list_width], C["ash"], C["ink"])
    for number, index, row in page.rows(rows):
        y = top + 1 + number
        picked = row.id == selected
        surface.text(2, y, ">" if picked else " ", C["flame"], C["ink"])
        if row.mark:
            surface.text(1, y, row.mark, C["flame"], C["ink"])
        _columns(surface, 3, y, row.cells, widths, list_width,
                 bright=picked)
        surface.link(1, y, list_width, 1, f"pick:{row.id}")
    if page.partial:
        surface.text(3, top + 1 + (page.end - page.start) + 1,
                     f"↑↓ {page.label()}"[:list_width], C["dim"], C["ink"])

    if not stacked:
        for y in range(top, height - 2 - footer_rows):
            surface.put(list_width + 2, y, "│", C["faint"], C["ink"])

    detail_y = (top + 2 + (page.end - page.start) + 2) if stacked else top + 1
    detail_room = width - detail_x - 2
    for offset, (text, tone) in enumerate(detail):
        if detail_y + offset >= height - 2 - footer_rows:
            break
        surface.text(detail_x, detail_y + offset, text[:detail_room],
                     C.get(tone, C["clay"]), C["ink"])

    # The controls. Two rows if they do not fit on one, because dropping one
    # silently is how an action becomes unreachable.
    _controls(surface, controls, hours, height - 2, width)
    if note:
        surface.text(3, height - 3 - footer_rows, note[:width - 6],
                     C["ash"], C["ink"])
    return surface.interactive()


def _columns(surface: Surface, x: int, y: int, cells, widths, limit: int,
             header: bool = False, bright: bool = False) -> None:
    right = x + limit - 2
    background = C["faint"] if header else C["ink"]
    for index, spec in enumerate(widths):
        if index >= len(cells) or x >= right:
            break
        if header:
            text, tone = str(cells[index]), "bone"
        else:
            text, tone = cells[index]
            if bright and tone in ("clay", "dim"):
                tone = "bone"
        span = min(abs(spec), right - x)
        if span <= 0:
            break
        text = str(text)
        if len(text) > span:
            text = text[:max(0, span - 1)] + "…"
        at = x + (span - len(text)) if spec < 0 else x
        surface.text(at, y, text, C.get(tone, C["clay"]), background)
        x += span + 2


def rows_needed(controls: list[Control], hours: int, width: int) -> int:
    """How many footer rows the controls take at this width."""
    return len(_lay_out(controls, hours, width))


def _lay_out(controls: list[Control], hours: int,
             width: int) -> list[list[tuple[Control, str]]]:
    """Pack the controls into rows, shortening captions before wrapping.

    A control is never dropped. The reason is the whole point of the module:
    an action the screen does not print is an action the player cannot find,
    and the audit's fourth problem was exactly a set of actions with no visible
    route. When the room runs out the *explanation* goes first, then the
    caption shortens to the registry's own short label, and only then does a
    second row open.
    """
    rows: list[list[tuple[Control, str]]] = [[]]
    column = 3
    for control in controls:
        caption = control.caption(hours)
        if not control.enabled and control.why:
            caption += f" ({control.why})"
        needed = len(control.key) + len(caption) + 6
        if column + needed > width - 3:
            short = control.caption(hours)
            if column + len(control.key) + len(short) + 6 <= width - 3:
                caption, needed = short, len(control.key) + len(short) + 6
            else:
                rows.append([])
                column = 3
                caption = short
                needed = len(control.key) + len(short) + 6
        rows[-1].append((control, caption))
        column += needed
    return rows


def _controls(surface: Surface, controls: list[Control], hours: int,
              y: int, width: int) -> None:
    """Print every control, wrapping to another row rather than dropping one."""
    laid = _lay_out(controls, hours, width)
    for offset, row in enumerate(laid):
        line = y - (len(laid) - 1 - offset)
        style.bar(surface, 2, line, width - 4, "", fg=C["clay"], bg=C["lapis"])
        column = 3
        for control, caption in row:
            column += style.keycap(
                surface, column, line, control.key, caption, control.enabled,
                command=f"do:{control.action_id}", bg=C["lapis"]) + 2
