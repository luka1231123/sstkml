"""The Known World and the Desk form one physical correspondence workflow."""
from __future__ import annotations

from ai.composer import MatterCorrection
from belief.project import project
from engine import actions as A
from engine.tick import advance
from load import load_scenario
import play_gui
from tui import composer, inbox, worldmap
from tui.grid import plain_text


SEED = 8814402919


class _Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "", state: int = 0) -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = state


def _game() -> play_gui.Game:
    world = load_scenario("ugarit", SEED)
    for _ in range(6):
        world, _ = advance(world)
    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = world
    game.hours = project(world)["attention"]
    game.log = []
    game.client = None
    game.app = None
    game.desk = None
    game.desk_drafts = {}
    game.inbox_notice = ""
    game.repaint = lambda: None
    game.world_place_pick = world.court.seat
    game.world_route_scroll = 0
    game.world_all_routes = False
    return game


def test_foreign_court_actions_all_begin_as_letters() -> None:
    belief = _game().belief
    screen = worldmap.compose(
        belief, 104, 32, selected_place="hattusa")
    text = plain_text(screen)
    enabled = {hit.command for hit in screen.hits if hit.enabled}

    assert "world:letter:hatti_king:letter" in enabled
    assert "world:letter:hatti_king:gift" in enabled
    assert "world:letter:hatti_king:marriage_proposal" in enabled
    assert "Gift" in text and "Marriage" in text
    assert text.count("by letter") >= 2
    assert "Envoy" in text and "not yet wired" in text
    assert not any(
        command.startswith(("do:", "world:open:")) for command in enabled)


def test_courier_path_uses_known_routes_and_reports_travel_time() -> None:
    belief = _game().belief
    path = worldmap.route_path(belief, belief["seat"], "hattusa")

    assert path[0] == belief["seat"]
    assert path[-1] == "hattusa"
    assert worldmap.path_legs(belief, path) > 0
    assert worldmap.route_path(belief, "nowhere", "hattusa") == ()


def test_world_letter_and_inbox_reply_open_the_same_desk() -> None:
    game = _game()
    game.world_place_pick = "hattusa"
    game.on_world_key(_Key(
        command="world:letter:hatti_king:marriage_proposal"))

    assert game.desk["draft_key"] == "new:hatti_king"
    assert game.desk["reply_to"] == ""
    assert game.desk["recipient"] == "hatti_king"
    assert game.desk["term_builder"]["kind"] == "marriage_proposal"
    assert game.desk["path"][0] == game.belief["seat"]
    assert game.desk["path"][-1] == "hattusa"
    assert set(game.desk["blocks"]) == {"address", "recognition", "seal"}

    game.on_desk_key(_Key(keysym="Escape"))
    incoming = game.belief["stack"][0]
    game.open_desk(incoming["id"])
    assert game.desk["draft_key"] == incoming["id"]
    assert game.desk["reply_to"] == incoming["id"]
    assert game.desk["recipient"] == incoming["sender"]
    assert set(game.desk["blocks"]) == {"address", "recognition", "seal"}


def test_wet_tablet_survives_close_and_selector_changes_until_discarded() -> None:
    game = _game()
    game.open_new_letter("hatti_king", "hattusa", "gift")
    game.desk["matter"] = "I send sixty measures of grain."
    game.desk["buffer"] = game.desk["matter"]
    game.desk["terms"] = (
        A.LetterTerm("gift", good="grain", quantity=60),)
    original_matter = game.desk["matter"]
    original_terms = game.desk["terms"]
    game._regrade()

    game.on_desk_key(_Key(command="block:address"))
    game.on_desk_key(_Key(command="desk:choice:next"))
    game.on_desk_key(_Key(command="desk:term:focus:quantity"))
    game.on_desk_key(_Key(command="desk:term:value:next"))
    assert game.desk["matter"] == original_matter
    assert game.desk["terms"] == original_terms

    game.on_desk_key(_Key(keysym="Escape"))
    assert game.desk is None
    assert "new:hatti_king" in game.desk_drafts

    game.world_place_pick = "egypt"
    game.open_new_letter("hatti_king", "hattusa")
    assert game.desk["matter"] == original_matter
    assert game.desk["terms"] == original_terms
    assert game.desk["term_builder"]["quantity"] == 70

    game.on_desk_key(_Key(command="desk:discard"))
    assert game.desk is None
    assert "new:hatti_king" not in game.desk_drafts


def test_compact_bronze_desk_keeps_terms_route_and_mouse_parity_visible() -> None:
    matter = "I send sixty measures of grain."
    blocks = composer.default_blocks()
    draft = composer.assemble("hatti_king", blocks, matter)
    item = {
        "sender": "hatti_king",
        "topic": "new letter",
        "facts": {"route": "seat > carchemish > hattusa"},
        "new_letter": True,
    }
    screen = composer.compose(
        item, draft, width=78, height=26, blocks=blocks,
        block_focus="terms", matter=matter,
        terms=(A.LetterTerm(
            "gift", good="grain", quantity=60, due_turn=9),),
        term_builder={
            "kind": "gift", "good": "grain",
            "quantity": 60, "due_turn": 9,
        },
        term_focus="due_turn",
        seal_data={
            "scribe": "Yabninu",
            "courier": "Iliya",
            "route": "seat > carchemish > hattusa",
            "travel_time": 4,
        })
    text = plain_text(screen)
    enabled = {hit.command for hit in screen.hits if hit.enabled}

    for heading in ("ADDRESS", "RECOGNITION", "MATTER", "TERMS", "SEAL"):
        assert heading in text
    assert "k:GIFT" in text and "g:grain" in text
    assert "q:60" in text and "due:t9" in text
    assert "Yabninu · Iliya · about 4f" in text
    assert "╲·╱" in text
    for command in (
        "desk:block:previous", "desk:block:next",
        "desk:choice:previous", "desk:choice:next",
        "desk:term:field:next",
        "desk:term:value:previous", "desk:term:value:next",
        "desk:term:add", "desk:term:remove", "desk:dispatch",
    ):
        assert command in enabled


def test_term_picker_builds_and_removes_engine_terms() -> None:
    game = _game()
    game.open_new_letter("hatti_king", "hattusa", "gift")
    game.desk["block_focus"] = "terms"
    game.desk["term_builder"].update(
        good="grain", quantity=60, due_turn=9)

    game.on_desk_key(_Key(command="desk:term:add"))
    assert game.desk["terms"] == (
        A.LetterTerm("gift", good="grain", quantity=60, due_turn=9),)

    game.on_desk_key(_Key(command="desk:term:remove"))
    assert game.desk["terms"] == ()


def test_yabninu_corrects_only_matter_and_never_material_terms(
        monkeypatch) -> None:
    game = _game()
    game.open_new_letter("hatti_king", "hattusa")
    game.desk["matter"] = "Send grain at once."
    game.desk["buffer"] = game.desk["matter"]
    game.desk["terms"] = (
        A.LetterTerm("request_good", good="grain", quantity=60),)
    terms_before = game.desk["terms"]
    game._regrade()
    monkeypatch.setattr(
        play_gui.ai_composer, "correct_matter",
        lambda *_args: MatterCorrection(
            "Send the grain without delay.", "model"))
    game._run_model = lambda work, done: done(work(), None)

    game._request_desk_draft(game._desk_item())

    assert game.desk["matter"] == "Send the grain without delay."
    assert game.desk["terms"] == terms_before


def test_seal_dispatches_exactly_one_structured_action() -> None:
    game = _game()
    game.open_new_letter("hatti_king", "hattusa")
    game.desk["matter"] = "I send sixty measures of grain."
    game.desk["buffer"] = game.desk["matter"]
    game.desk["terms"] = (
        A.LetterTerm("gift", good="grain", quantity=60),)
    game._regrade()
    expected_text = game.desk["draft"].text
    issued: list[object] = []

    def do(action, window=""):
        issued.append((action, window))
        return True

    game.do = do
    game.on_desk_key(_Key(command="desk:dispatch"))

    assert len(issued) == 1
    action, window = issued[0]
    assert type(action) is A.DispatchLetter
    assert window == "stack"
    assert action.recipient == "hatti_king"
    assert action.reply_to == ""
    assert action.text == expected_text
    assert action.terms == (
        A.LetterTerm("gift", good="grain", quantity=60),)
    assert action.scribe_id == "yabninu"
    assert action.courier_id == "iliya"
    assert action.seal == "palace"
    assert action.path[0] == game.belief["seat"]
    assert action.path[-1] == "hattusa"
    assert game.desk is None


def test_outbox_glance_shows_terms_route_and_handling() -> None:
    belief = {
        "attention": 8,
        "stack": [],
        "correspondence_archive": [],
        "outbox": [{
            "id": "L99",
            "sender": "ugarit_king",
            "recipient": "hatti_king",
            "topic": "grain",
            "sent_turn": 7,
            "status": "courier away",
            "in_transit": True,
            "body": "These are my words.",
            "facts": {},
            "terms": [{
                "kind": "gift", "good": "grain", "quantity": 60,
            }],
            "path": ["seat", "carchemish", "hattusa"],
            "scribe_id": "yabninu",
            "seal": "palace",
            "courier_id": "iliya",
        }],
        "house": {},
    }
    shown = play_gui.Game._outbox_belief(belief)
    text = plain_text(inbox.compose(
        shown, width=100, height=32, selected="L99",
        filter_name="outbox"))

    assert "terms GIFT · grain · 60" in text
    assert "route seat > carchemish > hattusa" in text
    assert "yabninu · palace · iliya" in text
