"""The embedded letter desk fits the Scribes' actual window."""
from __future__ import annotations

from tui import composer, desktop
from tui.grid import cells, plain_text


ITEM = {
    "sender": "hatti_king",
    "topic": "summons",
    "facts": {"troops": 60},
    "body": "Send sixty troops at once, as your oath requires.",
}
SEAL = {
    "scribe": "Yabninu",
    "courier": "Iliya",
    "route": "Ugarit > Hatti",
    "travel_time": 3,
}


def _compose(width: int, height: int, *, broken: bool = False,
             block_focus: str = "matter", terms=(), order=None,
             dictating: bool = False, matter_text: str = "",
             cursor_index: int = 9):
    matter = matter_text or (
        "My brother, send grain."
        if broken else
        "I cannot send sixty troops. My ships must guard Ugarit.")
    order = order or composer.opening_order("hatti_king")
    draft = (
        composer.dictated(matter, "hatti_king")
        if broken else
        composer.assemble("hatti_king", None, matter, order=order))
    return composer.compose(
        ITEM, draft, "request", width=width, height=height,
        matter=matter, block_order=order, block_focus=block_focus,
        terms=terms, seal_data=SEAL,
        bound=("order · refuse sixty troops", "tone · plain"),
        dictating=dictating, cursor_index=cursor_index)


def test_real_scribes_sizes_keep_the_draft_and_the_scribes_next_move() -> None:
    order = composer.opening_order("hatti_king")
    for width, height in (
            desktop.default_size("stack"), desktop.minimum_size("stack")):
        screen = _compose(width, height)
        grid = cells(screen)
        text = plain_text(grid)
        assert len(grid) == height
        assert all(len(row) == width for row in grid)
        for label in (
                "ADDRESS", "MARKER", "BOW", "RECOGNITION",
                "MATTER", "TERMS", "SEAL", "FINAL REVIEW"):
            assert label in text
        assert "I cannot send sixty troops" in text
        assert "Yabninu · Iliya · 3f" in text
        assert "YABNINU'S READING" in text
        assert "The address keeps the Sun above Ugarit." in text
        assert "Next · review terms, then seal." in text
        commands = {hit.command for hit in screen.hits}
        assert {f"block:{name}" for name in order} <= commands
        assert {
            "desk:block:previous", "desk:block:next",
            "desk:choice:previous", "desk:choice:next",
            "desk:block:add", "desk:block:remove",
            "desk:edit", "desk:correct", "desk:dispatch",
            "desk:discard",
        } <= commands


def test_form_break_and_fix_are_visible_at_default_and_minimum() -> None:
    for width, height in (
            desktop.default_size("stack"), desktop.minimum_size("stack")):
        text = plain_text(_compose(width, height, broken=True))
        assert "FORM BREAK · address · bow · rank" in text
        assert "The chosen address may be rejected." in text
        assert "Fix · court form · bow" in text


def test_term_controls_and_live_stylus_do_not_push_out_the_reading() -> None:
    order = tuple(
        list(composer.opening_order("hatti_king"))[:-1]
        + ["precedent", "seal"])
    width, height = desktop.minimum_size("stack")
    term = {"kind": "gift", "good": "grain", "quantity": 60}
    term_screen = _compose(
        width, height, block_focus="terms", terms=(term,), order=order)
    term_text = plain_text(term_screen)
    assert "PRECEDENT" in term_text
    assert "[t] field" in term_text and "[+] add" in term_text
    assert "YABNINU'S READING" in term_text
    assert "Next · review terms, then seal." in term_text

    writing = plain_text(_compose(width, height, dictating=True))
    assert "█" in writing
    assert "[ctrl-d] keep matter" in writing
    assert "YABNINU'S READING" in writing


def test_compact_dictation_follows_the_stylus_through_a_long_matter() -> None:
    matter = (
        "I cannot send the levy while the ships guard the northern road. "
        "When the watch returns, I will answer with sixty men at Ugarit.")
    screen = _compose(
        *desktop.minimum_size("stack"), dictating=True,
        matter_text=matter, cursor_index=matter.index("sixty"))
    text = plain_text(screen)
    assert "█sixty" in text
    assert "…" in text
    assert "[ctrl-d] keep matter" in text

    boundary_text = (
        "First sentence with several words and a route to Byblos that wraps "
        "cleanly. Second sentence with sixty guards, grain, copper, and the "
        "final instruction.")
    for cursor_index in range(len(boundary_text) + 1):
        at_cursor = plain_text(_compose(
            *desktop.minimum_size("stack"), dictating=True,
            matter_text=boundary_text, cursor_index=cursor_index))
        assert "█" in at_cursor, cursor_index


def test_required_or_exhausted_piece_controls_are_disabled() -> None:
    screen = _compose(
        *desktop.minimum_size("stack"),
        order=composer.permitted_blocks("hatti_king"),
        block_focus="marker")
    controls = {hit.command: hit.enabled for hit in screen.hits}
    assert controls["desk:block:add"] is False
    assert controls["desk:block:remove"] is False
