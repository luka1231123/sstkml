"""M13.0 interaction integrity: selection, confirmation, and visible refusals."""
from __future__ import annotations

from ai import parser
from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from tui import altar, archive, alu, counsel, inbox, plague, render
from tui.grid import plain_text
from engine import seat

SEED = 8814402919


def _world(turns: int = 8):
    world = load_campaign("seat", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


class _Key:
    def __init__(self, char: str = "", keysym: str = "",
                 command: str = "", state: int = 0) -> None:
        self.char = char
        self.keysym = keysym or char
        self.command = command
        self.state = state


def _controller():
    import play_gui

    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = _world()
    game.hours = project(game.world)["attention"]
    game.log = []
    game.client = None
    game.repaint = lambda: None
    return game


def test_reading_does_not_replace_the_selected_inbox_body() -> None:
    world = _world()
    first = next(item for item in project(world)["stack"] if not item["read"])
    world, _ = apply(world, A.ReadLetter(first["id"]))

    # It has left the Unread list, but remains the selected tablet on the
    # right-hand side until the player deliberately moves.
    view = inbox.compose(
        project(world), selected=first["id"], filter_name="unread")
    text = plain_text(view)
    assert "THE TABLET IS UNREAD" not in text
    assert "reached your hand" in text
    assert f"reply:{first['id']}" in {
        hit.command for hit in view.hits if hit.enabled}


def test_inbox_marks_a_known_answer_and_disables_duplicate_answer() -> None:
    world = _world()
    first = next(item for item in project(world)["stack"] if not item["read"])
    world, _ = apply(world, A.ReadLetter(first["id"]))
    world, _ = apply(world, A.DictateReply(first["id"], "answer"))
    turn = next(
        letter.answered_turn for letter in world.inbox
        if letter.id == first["id"])
    view = inbox.compose(
        project(world), selected=first["id"], filter_name="all",
        answered={first["id"]: turn})
    text = plain_text(view)
    assert f"answered, turn {turn}" in text
    assert f"reply:{first['id']}" not in {
        hit.command for hit in view.hits if hit.enabled}


def test_inbox_reply_key_opens_the_desk_for_the_selected_tablet() -> None:
    game = _controller()
    first = next(item for item in game.belief["stack"] if not item["read"])
    game.world, _ = apply(game.world, A.ReadLetter(first["id"]))
    game.stack_order = [item["id"] for item in game.belief["stack"]]
    game.inbox_filter = "unread"
    game.inbox_scroll = 0
    game.inbox_pick = first["id"]
    opened: list[str] = []
    game.open_desk = lambda letter_id: opened.append(letter_id)

    game.on_inbox_key(_Key("r"))
    assert opened == [first["id"]]


def test_navigation_after_reading_moves_to_first_remaining_unread() -> None:
    game = _controller()
    unread = [
        item for item in inbox.ordered_items(game.belief, filter_name="unread")
    ]
    assert len(unread) > 1
    first = unread[0]
    game.world, _ = apply(game.world, A.ReadLetter(first["id"]))
    game.stack_order = [item["id"] for item in unread]
    game.inbox_filter = "unread"
    game.inbox_scroll = 0
    game.inbox_pick = first["id"]

    game.on_inbox_key(_Key(keysym="Down"))
    assert game.inbox_pick == unread[1]["id"]


def test_archive_results_are_links_and_openable_by_number() -> None:
    game = _controller()
    game.world, _ = apply(game.world, A.SearchArchive("oath"))
    game.archive_hits = game.belief["archive_index"]["hits"]["oath"]
    game.archive_query = "oath"
    game.archive_typing = False
    assert game.archive_hits

    view = archive.compose(
        game.belief, "oath", game.archive_hits)
    first = game.archive_hits[0]
    assert f"open:{first['ref']}" in {
        hit.command for hit in view.hits if hit.enabled}
    assert first["ref"] in plain_text(archive.tablet(first, game.belief))

    opened: list[dict] = []
    game.open_archive_document = lambda item: opened.append(item)
    game.on_archive_key(_Key("1"))
    assert opened == [first]


def test_altar_names_and_cycles_the_death_subject() -> None:
    game = _controller()
    people = [
        person for person in game.belief["house"]["members"]
        if person["alive"]
    ]
    assert len(people) > 1
    game.altar_question = "death"
    game.altar_subject = people[0]["id"]
    game.altar_offering = None
    game.altar_notice = ""

    text = plain_text(altar.compose(
        game.belief, [], "death", subject=game.altar_subject))
    assert people[0]["name"] in text
    game.on_altar_key(_Key("]"))
    assert game.altar_subject == people[1]["id"]


def test_altar_refusals_are_visible_and_do_not_mutate_the_world() -> None:
    game = _controller()
    game.altar_question = "death"
    game.altar_subject = "there_is_no_such_person"
    game.altar_offering = None
    game.altar_notice = ""
    before = game.world

    game.on_altar_key(_Key(keysym="Return"))
    assert game.world is before
    assert "Name a living member" in game.altar_notice
    assert game.altar_notice in plain_text(altar.compose(
        game.belief, [], "death", subject=game.altar_subject,
        notice=game.altar_notice))


def test_counsel_preview_is_non_mutating_until_confirmed() -> None:
    game = _controller()
    game.counsel_said = []
    game.counsel_typed = ""
    game.counsel_typing = True
    game.counsel_pending = None
    before = seat.allowances(game.world).get("smiths_palace")

    game.submit_counsel("allocate smiths_palace 7000")
    assert seat.allowances(game.world).get("smiths_palace") == before
    assert game.log == []
    assert game.counsel_pending is not None
    assert "smiths" in game.counsel_pending["descriptions"][0].lower()

    game.confirm_counsel_order()
    assert seat.allowances(game.world)["smiths_palace"] == 7000
    assert game.log[-1]["action"]["_t"] == "Allocate"


def test_counsel_keeps_the_newest_exchange_on_screen() -> None:
    said = [
        ("scribe", f"old report {index}") for index in range(40)
    ] + [("scribe", "THE NEWEST ANSWER MUST REMAIN VISIBLE")]
    text = plain_text(counsel.compose(project(_world()), said, 6))
    assert "THE NEWEST ANSWER MUST REMAIN VISIBLE" in text
    assert "old report 0" not in text


def test_counsel_never_swallows_an_empty_parse_result() -> None:
    import play_gui

    game = _controller()
    game.counsel_said = []
    game.counsel_typed = ""
    game.counsel_typing = True
    game.counsel_pending = None
    original = play_gui.ai_parser.parse
    play_gui.ai_parser.parse = lambda *_args, **_kwargs: parser.ParseResult()
    try:
        game.submit_counsel("make it so")
    finally:
        play_gui.ai_parser.parse = original
    assert "neither a question nor an order" in game.counsel_said[-1][1]


def test_sickness_dossier_scrolls_every_known_place_without_claiming_truth() -> None:
    belief = project(_world())
    dossiers = plague.place_dossiers(belief)
    assert len(dossiers) > plague.page_size(28)

    last = dossiers[-1]
    view = plague.compose(
        belief, selected_place=last["id"], height=28, scroll=10_000)
    text = plain_text(view)
    assert last["name"].upper() in text
    assert "no current report is held" in text
    assert last["source"] in text
    assert "not a live view" in text
    assert f"plague:select:{last['id']}" in {
        hit.command for hit in view.hits if hit.enabled}


def test_sickness_mouse_and_keyboard_navigation_reach_the_tail() -> None:
    game = _controller()
    dossiers = plague.place_dossiers(game.belief)
    game.plague_pick = dossiers[0]["id"]
    game.plague_scroll = 0
    game.plague_notice = ""

    game.on_plague_key(_Key(command=f"plague:select:{dossiers[-1]['id']}"))
    assert game.plague_pick == dossiers[-1]["id"]
    assert game.plague_scroll > 0

    game.on_plague_key(_Key(keysym="Up"))
    assert game.plague_pick == dossiers[-2]["id"]
    game.on_plague_key(_Key(keysym="Down"))
    assert game.plague_pick == dossiers[-1]["id"]


def test_counsel_question_refusal_is_visible_in_counsel() -> None:
    game = _controller()
    game.counsel_said = []
    game.hours = 0
    before = game.world

    game.ask_counsel("What of the grain?", "grain")
    assert game.world is before
    assert "takes 1 hour" in game.counsel_said[-1][1]
    assert "0 remain" in game.counsel_said[-1][1]


def test_answer_refusal_is_visible_in_the_inbox() -> None:
    game = _controller()
    item = next(letter for letter in game.belief["stack"]
                if not letter["read"])
    game.world, _ = apply(game.world, A.ReadLetter(item["id"]))
    game.hours = 1
    game.inbox_notice = ""
    game.session_notice = ""
    game.desk = None

    game.open_desk(item["id"])
    assert "requires 2 hours" in game.inbox_notice
    screen = inbox.compose(
        game.belief, selected=item["id"], filter_name="all",
        hours_left=game.hours, notice=game.inbox_notice)
    assert game.inbox_notice in plain_text(screen)


def test_failed_city_inspection_stays_put_and_explains_itself() -> None:
    game = _controller()
    game.hours = 0
    game.alu_notice = ""
    game.session_notice = ""
    before = game.world

    game.on_alu_key(_Key("1"))
    assert game.world is before
    assert "requires 1 hour" in game.alu_notice
    assert game.alu_notice in plain_text(
        alu.compose(game.belief, notice=game.alu_notice))


def test_divination_ui_calls_it_a_forecast_not_future_access() -> None:
    assert "future that genuinely already exists" not in (altar.__doc__ or "")
    assert "privileged access" in (altar.__doc__ or "")
    assert "ask for a forecast" in render.house_screen(project(_world()))
