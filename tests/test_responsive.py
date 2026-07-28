"""Every screen composes at its default and its minimum (UI/UX spec 6).

This is the real guard on the responsive claim. The window layer can offer to
resize all it likes; what matters is whether the composer hands back a correct
rectangle at the small end, and whether the things the specification forbids
removing -- selection, actions, provenance -- are still in it.

The screens are built from one Belief at a fixed seed and turn, so a failure
here is a composer that cannot survive its own stated minimum, not a wobble in
the world.
"""
from __future__ import annotations

from belief.project import project
from engine.tick import advance
from load import load_scenario
from tui import (altar, archive, city, counsel, desktop, document, hall,
                 help as help_page, inbox, orders, palace, plague, works,
                 worldmap)
from tui.grid import cells, plain_text

SEED = 8814402919


def _belief(turns: int = 8):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world, project(world)


def _screens(world, b):
    order = document.order_of(b)
    return {
        "hall": lambda w, h: hall.compose(b, w, h, hours_left=10),
        "stack": lambda w, h: inbox.compose(
            b, w, h, order, "", "unread", 0, 10, ""),
        "stores": lambda w, h: document.stores(b, w, h),
        "roll": lambda w, h: document.roll(b, w, h),
        "muster": lambda w, h: document.muster(b, w, h),
        "oaths": lambda w, h: document.oaths(b, w, h),
        "land": lambda w, h: document.land(b, w, h),
        "world": lambda w, h: worldmap.compose(
            b, w, h, 0, 0, world.court.seat),
        "city": lambda w, h: city.compose(b, None, w, h),
        "works": lambda w, h: works.compose(b, "", w, h),
        "palace": lambda w, h: palace.compose(b, view="court", width=w,
                                              height=h),
        "orders": lambda w, h: orders.compose(b, [], 0, width=w, height=h),
        "plague": lambda w, h: plague.compose(b, "", w, h),
        "archive": lambda w, h: archive.compose(b, "", [], "", False, w, h),
        "altar": lambda w, h: altar.compose(b, [], "harvest", None, w, h),
        "counsel": lambda w, h: counsel.compose(
            b, [], 10, "", False, w, h, [], None),
        "help": lambda w, h: help_page.compose(w, h, "repair", "", "city"),
        "fortnight": lambda w, h: document.fortnight(b, [], w, h),
    }


def test_every_screen_composes_exactly_at_its_default_and_its_minimum():
    world, b = _belief()
    for key, compose in _screens(world, b).items():
        for width, height in (desktop.default_size(key),
                              desktop.minimum_size(key)):
            grid = cells(compose(width, height))
            assert len(grid) == height, (key, width, height)
            assert all(len(row) == width for row in grid), (key, width, height)


def test_shrinking_to_the_minimum_keeps_the_actions_reachable():
    """Decoration may go; a control may not (spec 6, contraction order)."""
    world, b = _belief()
    screens = _screens(world, b)
    for key in ("hall", "stack", "city", "palace", "works", "orders"):
        small = plain_text(cells(screens[key](*desktop.minimum_size(key))))
        assert "[" in small and "]" in small, key


def test_a_screen_at_its_minimum_still_answers_the_mouse():
    """Hit regions survive contraction, so mouse parity is not a wide-window
    luxury (spec 8, "mouse and keyboard invoke the same commands")."""
    world, b = _belief()
    screens = _screens(world, b)
    for key in ("hall", "stack", "city"):
        screen = screens[key](*desktop.minimum_size(key))
        assert getattr(screen, "hits", ()), key


def test_the_widest_and_narrowest_screens_land_in_the_expected_tiers():
    assert desktop.tier(desktop.default_size("city")[0]) == desktop.WIDE
    assert desktop.tier(desktop.minimum_size("city")[0]) == desktop.STANDARD
    assert desktop.tier(desktop.default_size("help")[0]) == desktop.COMPACT
    assert desktop.tier(desktop.minimum_size("help")[0]) == desktop.MINIMUM


def test_two_windows_fit_side_by_side_on_an_ordinary_laptop():
    """Coexistence, spec 6: Hall and Help together, Tablet and Stores together.

    Checked in cells rather than pixels -- the pixel form depends on the font,
    and the point of the contract is that the *columns* fit.
    """
    hall_columns = desktop.default_size("hall")[0]
    help_columns = desktop.default_size("help")[0]
    assert hall_columns + help_columns <= 160

    tablet_columns = desktop.default_size("letter:")[0]
    stores_columns = desktop.default_size("stores")[0]
    assert tablet_columns + stores_columns <= 150
