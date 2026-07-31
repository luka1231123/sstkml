"""M13.0 correspondence: one persistent workflow from arrival to sent copy."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from tempfile import TemporaryDirectory

import registry
from belief.project import project
from engine import actions as A
from engine import archive as engine_archive
from engine.core import state_hash
from engine.reduce import apply
from engine.state import Document
from engine.tick import advance
from engine.state import with_routes
from load import load_scenario
from session import play, replay, save
from tui import archive, inbox
from tui.grid import plain_text

SEED = 8814402919


def _world(turns: int = 8):
    world = load_scenario("ugarit", SEED)
    # Zero route risk so replies are never randomly intercepted: the outbox
    # and in-transit assertions must not depend on interception RNG.
    world = with_routes(world, tuple(
        dataclasses.replace(route, risk=0) for route in world.routes))
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _unread(world):
    return next(item for item in project(world)["stack"] if not item["read"])


def _raises_value_error(work) -> str:
    try:
        work()
    except ValueError as error:
        return str(error)
    raise AssertionError("expected ValueError")


def test_answer_filing_and_delegation_are_canonical_projected_state() -> None:
    world = _world()
    item = _unread(world)
    world, _ = apply(world, A.ReadLetter(item["id"]))
    world, delegated = apply(
        world, A.DelegateLetter(item["id"], "ehli_nikkalu"))
    world, _ = apply(
        world, A.DictateReply(
            item["id"], "answer", "Let this be my complete answer."))
    turn = world.date.absolute

    projected = next(
        letter for letter in project(world)["stack"]
        if letter["id"] == item["id"])
    assert projected["answered_turn"] == turn
    assert projected["delegated_to"] == "ehli_nikkalu"
    assert projected["delegated_turn"] == turn
    assert delegated == [
        A.LetterDelegated(item["id"], "ehli_nikkalu", turn)]

    world, filed = apply(world, A.ArchiveLetter(item["id"]))
    belief = project(world)
    assert item["id"] not in {letter["id"] for letter in belief["stack"]}
    filed_item = next(
        letter for letter in belief["correspondence_archive"]
        if letter["id"] == item["id"])
    assert filed_item["answered_turn"] == turn
    assert filed_item["delegated_to"] == "ehli_nikkalu"
    assert filed == [A.LetterArchived(item["id"], True)]

    world, _ = apply(world, A.ArchiveLetter(item["id"], False))
    assert item["id"] in {letter["id"] for letter in project(world)["stack"]}


def test_filing_and_delegation_refuse_unread_or_absent_tablets() -> None:
    world = _world()
    item = _unread(world)
    assert "read the tablet" in _raises_value_error(
        lambda: apply(world, A.ArchiveLetter(item["id"])))
    assert "read the tablet" in _raises_value_error(
        lambda: apply(
            world, A.DelegateLetter(item["id"], "ehli_nikkalu")))
    assert "no such letter" in _raises_value_error(
        lambda: apply(world, A.ArchiveLetter("not-a-tablet")))


def test_outbox_keeps_the_sent_copy_without_claiming_unknown_delivery() -> None:
    world = _world()
    item = _unread(world)
    world, _ = apply(world, A.ReadLetter(item["id"]))
    body = "A complete sent copy, retained even if its courier vanishes."
    world, events = apply(
        world, A.DictateReply(item["id"], "answer", body))
    sent_id = next(
        event.letter_id for event in events
        if isinstance(event, A.LetterSent))

    sent = next(
        letter for letter in project(world)["outbox"]
        if letter["id"] == sent_id)
    assert sent["body"] == body
    assert sent["in_transit"]
    assert sent["status"] == "courier away — no receipt"

    for _ in range(48):
        if sent_id not in {
                letter.id for letter in world.letters_in_transit}:
            break
        world, _ = advance(world)
    assert sent_id not in {
        letter.id for letter in world.letters_in_transit}
    sent = next(
        letter for letter in project(world)["outbox"]
        if letter["id"] == sent_id)
    assert not sent["in_transit"]
    assert sent["status"] == "sent — no answer"
    assert sent["body"] == body


def test_correspondence_ui_exposes_outbox_compare_delegate_and_filing() -> None:
    world = _world()
    item = _unread(world)
    world, _ = apply(world, A.ReadLetter(item["id"]))
    world, _ = apply(
        world, A.DictateReply(item["id"], "answer", "My retained answer."))
    belief = project(world)

    active = inbox.compose(
        belief, selected=item["id"], filter_name="all",
        delegate_to="ehli_nikkalu")
    commands = {hit.command for hit in active.hits if hit.enabled}
    assert f"compare:{item['id']}" in commands
    assert f"archive:{item['id']}" in commands
    assert f"delegate:{item['id']}:ehli_nikkalu" in commands
    assert "view:outbox" in commands

    sent = inbox.compose(belief, filter_name="outbox")
    text = plain_text(sent)
    assert "3 SENT" in text
    assert "ON THE ROAD" in text
    assert "My retained answer." in text


def test_inbox_controller_executes_compare_delegate_and_archive_paths() -> None:
    import play_gui

    world = _world()
    item = _unread(world)
    world, _ = apply(world, A.ReadLetter(item["id"]))
    game = play_gui.Game.__new__(play_gui.Game)
    game.seed = SEED
    game.world = world
    game.hours = project(world)["attention"]
    game.log = []
    game.load_armed = False
    game.session_notice = ""
    game.stack_order = [
        letter["id"] for letter in project(world)["stack"]]
    game.inbox_pick = item["id"]
    game.inbox_filter = "all"
    game.inbox_scroll = 0
    game.inbox_body_scroll = 0
    game.inbox_pane = "rack"
    game.inbox_delegate_pick = "ehli_nikkalu"
    game.repaint = lambda: None
    compared: list[str] = []
    game.open_letter = lambda letter: compared.append(letter["id"])

    class Key:
        def __init__(self, char: str = "", keysym: str = "",
                     command: str = "") -> None:
            self.char = char
            self.keysym = keysym or char
            self.command = command
            self.state = 0

    game.on_inbox_key(Key("c"))
    assert compared == [item["id"]]

    before = game.hours
    game.on_inbox_key(Key("d"))
    delegated = next(
        letter for letter in project(game.world)["stack"]
        if letter["id"] == item["id"])
    assert delegated["delegated_to"] == "ehli_nikkalu"
    assert game.hours == before - registry.BY_ID["delegate_letter"].cost

    game.on_inbox_key(Key("x"))
    assert game.inbox_filter == "archived"
    assert item["id"] in {
        letter["id"]
        for letter in project(game.world)["correspondence_archive"]}


def test_scribes_room_can_leave_records_with_numbers_or_station_arrows() -> None:
    import play_gui

    world = _world()
    game = play_gui.Game.__new__(play_gui.Game)
    game.world = world
    game.hours = project(world)["attention"]
    game.stack_order = [
        letter["id"] for letter in project(world)["stack"]]
    game.inbox_pick = game.stack_order[0]
    game.inbox_filter = "all"
    game.inbox_scroll = 0
    game.inbox_body_scroll = 0
    game.inbox_pane = "rack"
    game.desk = None
    game.archive_typing = False
    game.archive_open_ref = ""
    game.repaint = lambda: None

    class Key:
        def __init__(self, char: str = "", keysym: str = "",
                     command: str = "", state: int = 0) -> None:
            self.char = char
            self.keysym = keysym or char
            self.command = command
            self.state = state

    game.on_inbox_key(Key("4"))
    assert game.inbox_filter == "records"
    game.on_inbox_key(Key("1"))
    assert game.inbox_filter == "all"
    game.on_inbox_key(Key(keysym="Left"))
    assert game.inbox_filter == "records"
    game.on_inbox_key(Key(keysym="Right"))
    assert game.inbox_filter == "all"


def test_desk_stylus_undo_and_laid_aside_draft_are_real_state() -> None:
    import play_gui
    from tui import composer

    world = _world()
    item = _unread(world)
    world, _ = apply(world, A.ReadLetter(item["id"]))
    matter = "I cannot grant what you ask."
    blocks = composer.default_blocks()
    draft = composer.assemble(item["sender"], blocks, matter)
    game = play_gui.Game.__new__(play_gui.Game)
    game.world = world
    game.desk_drafts = {}
    game.repaint = lambda: None
    game.desk = {
        "letter_id": item["id"],
        "intent": "reply",
        "dictating": False,
        "dictated": True,
        "buffer": matter,
        "matter": matter,
        "cursor": len(matter),
        "history": [],
        "future": [],
        "source_scroll": 0,
        "terms": (),
        "blocks": blocks,
        "block_focus": "matter",
        "generation": 0,
        "composing": False,
        "draft": draft,
    }

    class Key:
        def __init__(self, char: str = "", keysym: str = "",
                     command: str = "", state: int = 0) -> None:
            self.char = char
            self.keysym = keysym or char
            self.command = command
            self.state = state

    game.on_desk_key(Key("e"))
    assert game.desk["dictating"]
    original = game.desk["buffer"]
    game.on_desk_key(Key("!", "!"))
    assert game.desk["buffer"] == original + "!"
    game.on_desk_key(Key(char="\x1a", keysym="z", state=4))
    assert game.desk["buffer"] == original
    game.on_desk_key(Key(char="\x04", keysym="d", state=4))
    assert not game.desk["dictating"]
    game.on_desk_key(Key(keysym="Escape"))
    assert game.desk is None
    assert game.desk_drafts[item["id"]]["matter"] == original
    assert original in game.desk_drafts[item["id"]]["draft"].text


def test_archive_hit_projects_and_scrolls_the_complete_body() -> None:
    marker = "THE LAST LINE REMAINS LEGIBLE"
    body = ("archiveword " * 90) + marker
    world = engine_archive.add(_world(), Document(
        ref="M13-LONG",
        kind="letter_in",
        received_turn=3,
        sender="byblos_king",
        dated_as="a foreign date",
        body=body,
        title="archiveword long tablet",
        tags=("archiveword",),
    ))
    world, _ = apply(world, A.SearchArchive("archiveword"))
    belief = project(world)
    hit = next(
        item for item in belief["archive_index"]["hits"]["archiveword"]
        if item["ref"] == "M13-LONG")
    assert hit["body"] == body
    assert marker not in hit["snippet"]
    rendered = plain_text(
        archive.tablet(hit, belief, height=24, scroll=10_000))
    assert "LAST LINE REMAINS LEGIBLE" in rendered


def test_correspondence_actions_round_trip_through_a_verified_save() -> None:
    probe = load_scenario("ugarit", SEED)
    probe, _ = advance(probe)
    probe, _ = advance(probe)
    item = _unread(probe)
    actions = [
        A.ReadLetter(item["id"]),
        A.DelegateLetter(item["id"], "ehli_nikkalu"),
        A.DictateReply(item["id"], "answer", "A replayable reply."),
        A.ArchiveLetter(item["id"]),
    ]
    final, log, _ = play(SEED, "ugarit", [[], actions])
    with TemporaryDirectory() as directory:
        path = Path(directory) / "campaign.json"
        save(path, SEED, "ugarit", 2, log, final)
        loaded = replay(path)
    assert state_hash(loaded) == state_hash(final)
    filed = next(
        letter for letter in project(loaded)["correspondence_archive"]
        if letter["id"] == item["id"])
    assert filed["answered_turn"] == 2
    assert filed["delegated_to"] == "ehli_nikkalu"
