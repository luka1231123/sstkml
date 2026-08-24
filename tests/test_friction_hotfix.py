"""Small input mistakes must not spend a fortnight or hide the cursor."""
from __future__ import annotations

import play_gui
from tui import trade
from tui.grid import plain_text


class Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "", state: int = 0) -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = state


def test_space_advances_only_from_the_hall() -> None:
    game = play_gui.Game.__new__(play_gui.Game)
    advanced = []
    game.end_fortnight = lambda: advanced.append("advanced")

    game.on_tablet_key(Key(char=" ", keysym="space"), "letter:L-1")
    game.on_tablet_key(Key(char=" ", keysym="space"), "archive:record-1")
    assert advanced == []

    game.on_key(Key(char=" ", keysym="space"))
    assert advanced == ["advanced"]


def test_opening_the_next_room_dismisses_the_fortnight_report() -> None:
    game = TradeGame.__new__(TradeGame)
    game._test_belief = {"stack": []}
    closed: list[str] = []
    opened: list[str] = []
    game.app = type("App", (), {"close": lambda _self, key: closed.append(key)})()
    game.open_door = opened.append

    game.on_tablet_key(Key("z"), "fortnight")
    assert closed == []
    game.on_tablet_key(Key("d"), "fortnight")
    assert closed == [], "no answerable tablet means no next station"

    game.on_tablet_key(Key("t"), "fortnight")
    assert closed == ["fortnight"]
    assert opened == ["t"]


def _trade_belief(count: int = 24) -> dict:
    return {
        "trade": {"movements": [
            {"id": f"movement-{index}", "origin": f"origin-{index}",
             "destination": f"destination-{index}", "cargo": [],
             "arrives": index + 1}
            for index in range(count)
        ]},
        "revenue": {},
    }


class TradeGame(play_gui.Game):
    @property
    def belief(self) -> dict:
        return self._test_belief


class Window:
    def focus(self) -> None:
        pass


class App:
    def __init__(self, opened: list[str]) -> None:
        self.opened = opened
        self.windows = {}

    def window(self, key: str, *_args, **_kwargs) -> Window:
        self.opened.append(key)
        return Window()

    def close(self, _key: str) -> None:
        pass


def test_trade_cursor_pages_to_every_row_and_opens_what_is_visible() -> None:
    game = TradeGame.__new__(TradeGame)
    game._test_belief = _trade_belief()
    game.trade_view = "movements"
    game.trade_pick = ""
    game._size = lambda _key: (66, 22)
    game.repaint = lambda: None
    opened = []
    game.open_focus = lambda kind, item: opened.append((kind, item["id"]))

    initial = plain_text(trade.compose(
        game.belief, width=66, height=22, view="movements"))
    assert ">origin-0" in initial
    game.on_trade_key(Key(keysym="Return"))
    assert game.trade_pick == "movement-0"
    assert opened == [("movement", "movement-0")]
    opened.clear()

    game.on_trade_key(Key(command="trade:next"))
    assert game.trade_pick == "movement-1"
    for _ in range(30):
        game.on_trade_key(Key(keysym="Down"))
    assert game.trade_pick == "movement-23", "Down should stop at the end"
    assert game.trade_scroll == 12

    game.on_trade_key(Key(keysym="Up"))
    assert game.trade_pick == "movement-22"
    assert game.trade_scroll == 12, "Up should not drag a stable page"

    screen = trade.compose(
        game.belief, width=66, height=22, view="movements",
        selected=game.trade_pick, scroll=game.trade_scroll)
    text = plain_text(screen)
    assert "origin-12" in text and "origin-22" in text
    assert "13–24 OF 24" in text
    assert any(hit.command == "trade:open:movements:22"
               for hit in screen.hits)

    game.on_trade_key(Key(keysym="Return"))
    assert opened == [("movement", "movement-22")]


def test_alu_number_opens_the_numbered_institution_instead_of_changing_tab() -> None:
    game = TradeGame.__new__(TradeGame)
    game._test_belief = {
        "institutions": [{
            "id": "granary_seat", "name": "the granary",
            "inspected": True,
        }],
    }
    game.alu_view = "institutions"
    game.alu_pick = ""
    game.repaint = lambda: None
    opened = []
    game.app = App(opened)

    game.on_alu_key(Key("1"))

    assert game.alu_view == "institutions"
    assert game.alu_pick == "granary_seat"
    assert opened == ["institution:granary_seat"]
