"""The drawn windows: art, the desk, counsel, the altar, the map, the archive.

The art is checked the same way everything else in `tui/` is checked — by
reading cells. A drawing that desynchronises the grid is a bug that shows up as
every column to its right being one off, so it is worth a test rather than an
eye.
"""
from __future__ import annotations

from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from tui import altar, archive, art, composer, counsel, worldmap
from tui.grid import BadGlyph, Surface, _check, plain_text

SEED = 8814402919


def _world(turns: int = 8):
    world = load_scenario("ugarit", SEED)
    for _ in range(turns):
        world, _ = advance(world)
    return world


def _belief(turns: int = 8) -> dict:
    return project(_world(turns))


def _drawings():
    for name in dir(art):
        value = getattr(art, name)
        if (isinstance(value, tuple) and value
                and all(isinstance(row, str) for row in value)):
            yield name, value


# --- the art ------------------------------------------------------------------

def test_every_drawing_is_one_column_per_cell() -> None:
    """A double-width glyph shears every column to its right, silently."""
    for name, rows in _drawings():
        for row in rows:
            for glyph in row:
                try:
                    _check(glyph)
                except BadGlyph as error:
                    raise AssertionError(f"{name}: {error}") from None


def test_every_drawing_is_a_rectangle() -> None:
    for name, rows in _drawings():
        widths = {len(row) for row in rows}
        assert len(widths) == 1, f"{name} is ragged: {sorted(widths)}"


def test_every_face_is_the_same_size() -> None:
    """So a face can go in any slot without the text beside it moving."""
    sizes = {art.size(face) for face in art.FACES.values()}
    assert sizes == {(13, 9)}, sizes


def test_a_face_is_chosen_by_station_not_by_name() -> None:
    assert art.face_for("the Great King of Hatti") is art.KING
    assert art.face_for("Abdi-hagab, overseer of Siyannu") is art.OVERSEER
    assert art.face_for("Sinaranu the merchant") is art.MERCHANT
    assert art.face_for("a man nobody has placed") is art.STRANGER


def test_a_drawing_survives_being_read_as_text() -> None:
    surface = Surface(20, 12)
    art.draw(surface, 0, 0, art.KING)
    text = plain_text(surface.freeze())
    assert "█" in text and text.count("\n") == 11


def test_the_frieze_is_exactly_as_long_as_asked() -> None:
    for width in (1, 7, 24, 25, 90):
        assert len(art.frieze(width)) == width


# --- the desk -----------------------------------------------------------------

def test_the_formulary_is_correct_and_says_nothing() -> None:
    """The scribe's draft always passes protocol. That is its whole problem."""
    draft = composer.formulary("hatti_king", "refuse", SEED, 8)
    assert draft.source == "formulary"
    assert draft.score.total >= 900
    assert draft.score.address_ok and draft.score.self_designation_ok


def test_a_dictated_tablet_is_graded_by_the_same_rule() -> None:
    bad = composer.dictated("give me grain", "hatti_king")
    assert bad.score.total < 500
    assert not bad.score.address_ok


def test_the_desk_shows_the_forms_failing_without_saying_so() -> None:
    b = _belief()
    item = b["stack"][0]
    draft = composer.dictated("give me grain", item["sender"])
    text = plain_text(composer.compose(item, draft, "request",
                                       house=b.get("house")))
    assert "✗ address" in text
    assert "THE FORMS" in text
    # It marks the form. It never says what to write, or that this is a mistake.
    assert "you should" not in text.lower()


def test_the_desk_names_every_intent_the_king_may_have() -> None:
    b = _belief()
    item = b["stack"][0]
    draft = composer.formulary(item["sender"], "warn", SEED, 8)
    text = plain_text(composer.compose(item, draft, "warn",
                                       house=b.get("house")))
    for intent in composer.INTENTS:
        assert intent in text


# --- counsel ------------------------------------------------------------------

def test_counsel_answers_every_question_he_offers() -> None:
    b = _belief()
    for _key, _question, topic in counsel.QUESTIONS:
        said = counsel.answer(b, topic, SEED, 8)
        assert said and "my lord" in said or len(said) > 20


def test_counsel_is_wrong_sometimes_and_always_the_same_times() -> None:
    """Deterministic, because everything in this game is replayable."""
    first = [counsel._reliable(SEED, turn, "grain") for turn in range(40)]
    again = [counsel._reliable(SEED, turn, "grain") for turn in range(40)]
    assert first == again
    assert not all(first), "he is never wrong, which makes him a ledger"
    assert any(first), "he is never right, which makes him noise"


def test_the_room_is_a_conversation_and_not_a_menu() -> None:
    """You type at him. The six keys are shortcuts, not the whole of it."""
    b = _belief()
    text = plain_text(counsel.compose(b, [
        ("king", counsel.QUESTIONS[0][1]),
        ("scribe", counsel.answer(b, "grain", SEED, 8))], 6))
    assert "YOU SAY" in text and "GIVE AN ORDER" in text
    assert "[enter] tell him" in text
    assert "Yabninu:" in text


def test_what_he_is_handed_is_what_he_can_say() -> None:
    """His wrongness is settled before any prompt exists, so it replays."""
    b = _belief()
    first = counsel.recall(b, "grain", SEED, 8)
    assert first == counsel.recall(b, "grain", SEED, 8)
    assert first, "he was handed nothing to say"


def test_the_digest_carries_the_house_and_not_the_answers() -> None:
    """He can speak about anything the king could see; no more than that."""
    from ai import counsel as ai_counsel

    text = ai_counsel.digest(_belief(), {})
    assert "the roll:" in text and "the stores:" in text
    assert "oath oath_hatti_grain" in text
    # The puzzles are not in his head either (D31, spec 8.9).
    assert "cause_oath" not in text and "will_die" not in text


def test_the_room_says_what_a_question_costs() -> None:
    text = plain_text(counsel.compose(_belief(), [], 6))
    assert "an hour a question" in text


# --- the map ------------------------------------------------------------------

def test_the_map_places_every_correspondent_somewhere() -> None:
    b = _belief()
    charted = {place["id"] for place in b["world_graph"]["places"]}
    for relation in b["relations"]:
        assert relation["place"] in charted, relation["place"]


def test_the_map_greys_the_sea_when_the_sea_is_shut() -> None:
    """On the layer the sea lanes are drawn on, where the season bites."""
    b = dict(_belief())
    b["sea_open"] = False
    text = plain_text(worldmap.compose(b, 86, 30, layer="trade"))
    assert "the sea is shut" in text
    b["sea_open"] = True
    assert "the sea lanes are open" in plain_text(
        worldmap.compose(b, 86, 30, layer="trade"))


def test_the_route_tablet_names_nodes_and_the_kind_of_link() -> None:
    text = plain_text(worldmap.compose(_belief(), 86, 30))
    assert "Ugarit" in text and "Hattusa" in text and "Alashiya" in text
    assert "land" in text and "sea" in text


# --- the altar and the tablet house -------------------------------------------

def test_the_altar_offers_a_question_and_an_offering() -> None:
    text = plain_text(altar.compose(_belief(), []))
    assert "WHAT YOU WOULD KNOW" in text
    assert "of the harvest" in text
    assert "does not buy a truer answer" in text


def test_the_altar_shows_what_he_said_without_marking_it_doubtful() -> None:
    reading = "He reads the liver and says: the year will be poor."
    text = plain_text(altar.compose(_belief(), [reading]))
    assert "reads the liver" in text
    assert "may be wrong" not in text.lower()
    assert "uncertain" not in text.lower()


def test_the_tablet_house_finds_what_was_searched_for() -> None:
    world = _world()
    world, _ = apply(world, A.SearchArchive("oath"))
    b = project(world)
    hits = b["archive_index"]["hits"]["oath"]
    assert hits, "the archive returned nothing for a word that is in it"
    text = plain_text(archive.compose(b, "oath", hits))
    assert "oath" in text
    assert "tablets are shelved here" in text


def test_the_tablet_house_says_when_nothing_answers() -> None:
    text = plain_text(archive.compose(_belief(), "wheelbarrow", []))
    assert "nothing in this house answers to that" in text
