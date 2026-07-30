"""Reading a foreign court's answer, and seeing when none came (spec 3.2, 3.5).

The engine decides and writes facts; these tests are about the other end of that
tablet. They say what the king may read, when he may read it, that the terms he
reads are the terms that were offered, that words once accepted are never asked
for again, and that a tablet nobody answered is still on the rack with its date
and its road on it.
"""
from __future__ import annotations

import dataclasses

from ai import replier
from ai.grader import profile_for
from ai.voicer import Voicer
from belief.project import project
from engine import actions as A
from engine import mail, tick
from engine.reduce import apply
from load import load_scenario
from tui import document, inbox
from tui.desktop import minimum_size
from tui.grid import cells, plain_text

SEED = 1


def _dispatch(world, recipient: str, quantity: int) -> A.DispatchLetter:
    place = world.foreign_courts[recipient].place
    path = mail.shortest_path(world.routes, world.court.seat, place)
    return A.DispatchLetter(
        recipient=recipient, reply_to="", text="Send grain, my brother.",
        profile=profile_for(recipient),
        terms=(A.LetterTerm(kind="request_good", good="grain",
                            quantity=quantity, due_turn=40),),
        scribe_id="yabninu", seal="royal", courier_id="courier_1", path=path)


def _sent(recipient: str, quantity: int):
    """A world in which one request for grain is on the road."""
    world = load_scenario("ugarit", SEED)
    world, _ = tick.advance(world)
    world, _ = mail.apply_dispatch(world, _dispatch(world, recipient, quantity))
    sent = world.letters_in_transit[-1].id
    return world, sent


def _reply(world, sent: str):
    return next(
        (letter for letter in world.inbox if letter.reply_to == sent), None)


def _until_answered(world, sent: str, limit: int = 40):
    for _ in range(limit):
        world, _ = tick.advance(world)
        if _reply(world, sent) is not None:
            return world
    raise AssertionError("no answer came home")


def _outbox_item(world, sent: str) -> dict:
    return next(item for item in project(world)["outbox"]
                if item["id"] == sent)


def _stack_item(world, letter_id: str) -> dict:
    return next(item for item in project(world)["stack"]
                if item["id"] == letter_id)


# --- the answer is readable ---------------------------------------------------

def test_a_delivered_counter_is_read_with_its_decision_and_exact_terms():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)
    world, _ = apply(world, A.ReadLetter(reply.id))

    item = _stack_item(world, reply.id)
    assert item["facts"]["decision"] == "counter"
    # The terms as the court offered them, to the qa. A rounded counter is a
    # different counter.
    assert item["terms"] == [{
        "kind": "promise_good", "good": "grain", "quantity": 50000,
        "person_id": "", "destination": "", "due_turn": 40}]
    assert document.is_answer(item)
    assert "terms offered back" in document.answer_subject(item)

    belief = project(world)
    text = plain_text(inbox.compose(
        belief, selected=reply.id, filter_name="all"))
    assert "terms offered back" in text
    assert "50,000" in text
    assert "due 40" in text

    tablet = plain_text(document.tablet(item, body="Words on the clay."))
    assert "terms offered back" in tablet and "50,000" in tablet


def test_the_sent_tablet_records_the_answer_it_received():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)

    # The tablet is here and unbroken: its arrival is known, its answer is not.
    waiting = _outbox_item(world, sent)
    assert waiting["status"] == "answer come — seal unbroken"
    assert waiting["decision"] == "" and waiting["counter_terms"] == []

    world, _ = apply(world, A.ReadLetter(reply.id))
    answered = _outbox_item(world, sent)
    assert answered["status"] == "answered — terms offered back"
    assert answered["decision"] == "counter"
    assert answered["counter_terms"][0]["quantity"] == 50000
    assert answered["reply_id"] == reply.id
    assert answered["reply_turn"] == reply.arrive_turn
    assert not answered["silent"]


def test_a_refusal_and_an_acceptance_read_as_what_they_are():
    for recipient, quantity, word in (
            ("pharaoh", 30000, "accepted"), ("hatti_king", 30000, "refused")):
        world, sent = _sent(recipient, quantity)
        world = _until_answered(world, sent)
        reply = _reply(world, sent)
        world, _ = apply(world, A.ReadLetter(reply.id))
        item = _stack_item(world, reply.id)
        assert document.answer_subject(item).endswith(word), recipient
        assert _outbox_item(world, sent)["status"] == f"answered — {word}"


# --- nothing before the tablet arrives ---------------------------------------

def test_no_word_of_the_answer_crosses_before_the_tablet_does():
    world, sent = _sent("carchemish_viceroy", 60000)
    for _ in range(40):
        world, _ = tick.advance(world)
        decided = [case for case in world.correspondence if case.decision]
        if decided and _reply(world, sent) is None:
            break
    else:                                   # pragma: no cover - scenario guard
        raise AssertionError("no case was decided while its reply travelled")

    belief = project(world)
    item = next(entry for entry in belief["outbox"] if entry["id"] == sent)
    assert item["decision"] == ""
    assert item["counter_terms"] == []
    assert not item["answered"]
    assert item["status"] in {
        "courier away — no receipt", "sent — no receipt", "sent — no answer"}
    assert not [entry for entry in belief["stack"]
                if document.is_answer(entry)]
    assert "counter" not in plain_text(
        inbox.compose(belief, selected=sent, filter_name="outbox")).casefold()


def test_an_unread_answer_keeps_its_decision_under_the_seal():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    item = _stack_item(world, _reply(world, sent).id)
    assert item["facts"] == {} and item["terms"] == []
    assert document.answer_subject(item) == "an answer to your tablet"
    text = plain_text(inbox.compose(
        project(world), selected=item["id"], filter_name="all"))
    assert "50,000" not in text
    assert "UNBROKEN SEAL" in text


# --- silence is state --------------------------------------------------------

def _asked_until_ignored(recipient: str, quantity: int, askings: int = 5):
    """Ask one court for grain it cannot spare until it stops replying.

    A court that has been asked once too often decides `ignore` and writes no
    tablet at all (`engine/correspondence_policy.py`). From the seat that is
    indistinguishable from a drowned courier, which is exactly why the waiting
    has to be visible rather than absent.
    """
    world = load_scenario("ugarit", SEED)
    world, _ = tick.advance(world)
    last = ""
    for _ in range(askings):
        world, _ = mail.apply_dispatch(
            world, _dispatch(world, recipient, quantity))
        last = world.letters_in_transit[-1].id
        for _ in range(6):
            world, _ = tick.advance(world)
    assert any(case.decision == "ignore" for case in world.correspondence)
    assert _reply(world, last) is None, "the court answered after all"
    return world, last


def test_an_ignored_tablet_reads_as_silence_with_its_date_and_road():
    world, sent = _asked_until_ignored("alashiya_gov", 9000)
    item = _outbox_item(world, sent)
    assert item["silent"]
    assert item["status"] == "sent — no answer"
    assert item["decision"] == "" and item["counter_terms"] == []
    assert item["path"] and item["travel_turns"] >= 1
    assert item["expected_reply_turn"] > item["sent_turn"]

    belief = project(world)
    text = plain_text(inbox.compose(
        belief, selected=sent, filter_name="outbox"))
    assert "NO ANSWER" in text
    assert f"sent turn {item['sent_turn']}" in text
    assert "UNANSWERED" in text
    # The road it went by is still on the screen; the tablet has not vanished.
    assert item["path"][-1].replace("_", " ") in text


# --- accepted words are stored, not made again -------------------------------

class _Counter:
    """A client that would answer, and records that it was asked."""

    def __init__(self) -> None:
        self.calls = 0

    def call(self, *_args, **_kwargs) -> str:
        self.calls += 1
        return "I cannot send what you ask. I send fifty thousand instead."


def _with_stored_text(world, text: str):
    cases = tuple(
        dataclasses.replace(case, reply_text=text)
        if case.reply_letter_id else case
        for case in world.correspondence)
    return dataclasses.replace(world, correspondence=cases)


def test_stored_words_are_projected_and_never_asked_for_again():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)
    world, _ = apply(world, A.ReadLetter(reply.id))
    stored = ("Say to my brother: what you ask I cannot send whole. "
              "I send 50,000 of grain by turn 40, and no more.")
    world = _with_stored_text(world, stored)

    item = _stack_item(world, reply.id)
    assert item["body"] == stored

    client = _Counter()
    text, source = replier.voice_reply(item, SEED, 9, client)
    assert (text, source) == (stored, "stored")
    assert client.calls == 0

    voicer = Voicer(client, SEED)
    voicer.schedule([item], 9)
    assert voicer.wait()
    assert voicer.body(item) == (stored, "stored")
    assert client.calls == 0

    assert stored[:24] in plain_text(inbox.compose(
        project(world), selected=reply.id, filter_name="all"))


def test_a_guarded_answer_keeps_the_decision_and_the_figures():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)
    world, _ = apply(world, A.ReadLetter(reply.id))
    item = _stack_item(world, reply.id)

    assert replier.decision_of(item) == "counter"
    good = ("Say to my brother: the grain you ask for I cannot send whole, "
            "for my own people eat. I will send 50,000 of grain by turn 40, "
            "and my courier carries this tablet sealed. Let there be peace "
            "between our houses as before.")
    assert replier.reply_ok(good, item, "counter")
    # A figure nobody gave the court.
    assert not replier.reply_ok(good.replace("50,000", "80,000"), item,
                               "counter")
    # A counter that has dropped what it offered.
    assert not replier.reply_ok(
        good.replace("50,000 of grain by turn 40", "what I can spare"),
        item, "counter")
    # An answer that grants what the court refused.
    granted = ("Say to my brother: what you ask I grant, and it is granted "
               "gladly. The grain goes out to you with my own courier under "
               "my seal, as our houses have always done for one another.")
    assert not replier.reply_ok(granted, item, "counter")


def test_a_failed_voice_falls_back_to_a_plain_reading_of_the_same_facts():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)
    world, _ = apply(world, A.ReadLetter(reply.id))
    item = _stack_item(world, reply.id)

    class _Broken:
        def call(self, *_args, **_kwargs) -> str:
            raise OSError("the service is not there")

    text, source = replier.voice_reply(item, SEED, 9, _Broken())
    assert source == "fallback"
    assert "50,000" in text and "turn 40" in text
    assert "cannot send whole" in text


# --- the boundary ------------------------------------------------------------

def _leaves(value, path: str = "belief"):
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str), f"{path}: key {key!r}"
            yield from _leaves(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _leaves(item, f"{path}[{index}]")
    else:
        yield path, value


def test_no_world_object_reaches_the_projection_of_an_answer():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    world, _ = apply(world, A.ReadLetter(_reply(world, sent).id))
    for path, value in _leaves(project(world)):
        assert isinstance(value, (str, int, float, bool, type(None))), (
            f"{path} projected {type(value).__name__}")


def test_the_answer_prompt_carries_no_forbidden_field():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)
    world, _ = apply(world, A.ReadLetter(reply.id))
    item = _stack_item(world, reply.id)

    messages = replier.build_prompt(item, "counter")
    prompt = " ".join(message["content"] for message in messages)
    # The court's own stores, needs, and beliefs are what it decided FROM. The
    # language layer is told the decision and never the reasoning (spec 2.7).
    for hidden in ("stores", "need", "floor", "claim", "basis", "report_bias"):
        assert hidden not in prompt.casefold(), hidden
    assert "50,000" in prompt and "turn 40" in prompt


# --- screens -----------------------------------------------------------------

def test_the_answer_survives_the_smallest_rack_and_answers_the_mouse():
    world, sent = _sent("carchemish_viceroy", 60000)
    world = _until_answered(world, sent)
    reply = _reply(world, sent)
    world, _ = apply(world, A.ReadLetter(reply.id))
    belief = project(world)

    for view, selected in (("all", reply.id), ("outbox", sent)):
        width, height = minimum_size("stack")
        screen = inbox.compose(
            belief, width, height, order=[selected], selected=selected,
            filter_name=view)
        grid = cells(screen)
        assert len(grid) == height
        assert all(len(row) == width for row in grid)
        text = plain_text(screen)
        assert "50,000" in text, view
        # Mouse and keyboard reach the same commands at the minimum size.
        assert {f"view:{view}", f"select:{selected}"} <= {
            hit.command for hit in screen.hits}
        assert "[" in text and "]" in text

    item = _stack_item(world, reply.id)
    width, height = minimum_size("letter:")
    grid = cells(document.tablet(item, body="Words on the clay.",
                                width=width, height=height))
    assert len(grid) == height and all(len(row) == width for row in grid)
