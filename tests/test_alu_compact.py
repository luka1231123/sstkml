"""The Alu's real window is a playable, pageable street."""
from __future__ import annotations

import play_gui
from belief.project import project
from load import load_campaign
from tui import alu, desktop
from tui.grid import cells, plain_text


SEED = 8814402919


def _belief():
    return project(load_campaign("seat", SEED))


def _lines(screen):
    return plain_text(cells(screen)).splitlines()


def _many(count: int) -> dict:
    return {
        "institutions": [{
            "id": f"i{index}", "name": f"house{index}",
            "kind": "granary", "head": "keeper", "group_name": "keepers",
            "condition": 500, "inspected": True, "history": [500],
        } for index in range(count)],
        "projects": [], "revenue": {}, "date": "first half",
    }


def test_real_sizes_keep_tabs_art_rows_frame_and_clicks_in_agreement() -> None:
    for width, height in (
            desktop.minimum_size("alu"), desktop.default_size("alu")):
        assert alu.table_room(height, width) == 4
        screen = alu.compose(
            _belief(), width=width, height=height, view="institutions")
        lines = _lines(screen)

        assert all(label in lines[2] for label in (
            "1 Overview", "2 Cohorts", "3 Institutions", "4 Sites", "5 Works"))
        assert all(label in lines[13] for label in (
            "[1] forge", "[2] granary", "[3] harbour", "[4] tablets"))
        assert all(name in "\n".join(lines[16:20]) for name in (
            "the palace forge", "the great granar", "the harbour of M",
            "the tablet house"))
        assert all(line.startswith("║") and line.endswith("║")
                   for line in lines[16:20])

        commands = [hit.command for hit in screen.hits if hit.enabled]
        assert {f"tab:{view}" for view in alu.VIEWS} <= set(commands)
        assert {"1", "2", "3", "4", "Tab", "alu:next", "Return",
                "n", "Escape"} <= set(commands)
        assert all(commands.count(str(number)) == 2 for number in range(1, 5))


def test_scrolling_pages_the_same_four_buildings_and_rows_together() -> None:
    for width, height in (
            desktop.minimum_size("alu"), desktop.default_size("alu")):
        lines = _lines(alu.compose(
            _belief(), width=width, height=height,
            view="institutions", scroll=2))
        assert "3–6 OF 6" in lines[14]
        assert all(label in lines[13] for label in (
            "[1] harbour", "[2] tablets", "[3] temple", "[4] walls"))
        body = "\n".join(lines[16:20])
        assert all(name in body for name in (
            "the harbour of M", "the tablet house",
            "the temple of Ba", "the walls of Uga"))


class _Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "") -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = 0


class _Game(play_gui.Game):
    @property
    def belief(self) -> dict:
        return self._test_belief


class _Window:
    def focus(self) -> None:
        pass


class _App:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def window(self, key: str, *_args, **_kwargs) -> _Window:
        self.opened.append(key)
        return _Window()


def test_cursor_reaches_the_last_page_and_number_opens_the_visible_row() -> None:
    game = _Game.__new__(_Game)
    game._test_belief = _many(100)
    game.alu_view = "institutions"
    game.alu_pick = ""
    game.alu_scroll = 0
    game._size = lambda _key: desktop.minimum_size("alu")
    game.repaint = lambda: None
    game.app = _App()

    for _ in range(120):
        game.on_alu_key(_Key(keysym="Down"))
    assert game.alu_pick == "i99"
    assert game.alu_scroll == 96

    game.on_alu_key(_Key(keysym="Up"))
    assert game.alu_pick == "i98"
    assert game.alu_scroll == 96
    game.on_alu_key(_Key(keysym="Down"))

    screen = alu.compose(
        game.belief, width=70, height=25, view="institutions",
        selected=game.alu_pick, scroll=game.alu_scroll)
    text = plain_text(screen)
    assert "97–100 OF 100" in text
    assert "house99" in text

    game.on_alu_key(_Key("4"))
    assert game.app.opened == ["institution:i99"]


def test_full_height_still_uses_one_page_for_art_and_rows() -> None:
    assert alu.table_room(36, 96) == alu.DRAWN == 6
    page = alu.institution_page(_many(100)["institutions"], 96, 36, 95)
    assert (page.start, page.end) == (94, 100)
