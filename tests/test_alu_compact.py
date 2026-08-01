"""The Alu's minimum geometry is a real, playable street."""
from belief.project import project
from load import load_campaign
from tui import alu, desktop
from tui.grid import cells, plain_text


SEED = 8814402919


def _belief():
    return project(load_campaign("seat", SEED))


def _lines(screen):
    return plain_text(cells(screen)).splitlines()


def test_alu_minimum_keeps_four_drawn_and_actionable_houses():
    width, height = desktop.minimum_size("alu")
    assert (width, height) == (70, 25)
    assert alu.table_room(height) == 4
    assert alu.table_room(alu.COMPACT_HEIGHT) == 4

    screen = alu.compose(_belief(), width=width, height=height)
    lines = _lines(screen)

    # These are labels below four full-size building models, not a replacement
    # text list. The ledger directly below repeats the same four number keys.
    labels = lines[13]
    assert all(label in labels for label in
               ("[1] forge", "[2] granary", "[3] harbour", "[4] tablets"))
    assert any(glyph in "".join(lines[3:13])
               for glyph in ("▟", "█", "▓", "▤"))
    assert lines[16].startswith("║1 the palace forge")
    assert lines[19].startswith("║4 the tablet house")

    commands = {hit.command for hit in screen.hits}
    assert {"1", "2", "3", "4", "n", "Escape"} <= commands
    assert "the men are out on" not in "\n".join(lines)


def test_alu_minimum_pages_the_same_art_and_rows_together():
    width, height = desktop.minimum_size("alu")
    lines = _lines(alu.compose(
        _belief(), width=width, height=height, scroll=2))

    assert "3–6 OF 6" in lines[14]
    labels = lines[13]
    assert all(label in labels for label in
               ("[1] harbour", "[2] tablets", "[3] temple", "[4] walls"))
    assert lines[16].startswith("║1 the harbour")
    assert lines[19].startswith("║4 the walls")
