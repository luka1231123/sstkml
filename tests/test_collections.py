"""No row of any collection is unreachable (UI/UX spec 23.3, phase 1).

The specification asks for collection fixtures at 0, 1, 9, 10, and 100 rows,
with every row reachable and the selection stable across resize. Ten is the
interesting one: it is the first size that does not fit the nine digits, and it
is exactly where the old screens stopped drawing and said nothing.
"""
from __future__ import annotations

from tui import archive, alu, collection, palace, works
from tui.grid import plain_text

SIZES = (0, 1, 9, 10, 100)


def _walk(total: int, room: int) -> set[int]:
    """Every index a player can bring on screen by scrolling from the top."""
    seen: set[int] = set()
    scroll = 0
    for _ in range(total + 2):
        page = collection.page(total, room, scroll)
        seen.update(range(page.start, page.end))
        if not page.more_below:
            break
        scroll = page.start + room
    return seen


def test_every_row_is_reachable_by_scrolling() -> None:
    for total in SIZES:
        for room in (1, 3, 9, 20):
            assert _walk(total, room) == set(range(total)), (total, room)


def test_a_page_never_runs_off_the_end_of_its_collection() -> None:
    for total in SIZES:
        for scroll in (-5, 0, 3, total, total * 2):
            page = collection.page(total, 9, scroll)
            assert 0 <= page.start <= max(0, total)
            assert page.start <= page.end <= total
            assert page.end - page.start <= 9


def test_a_selection_off_the_page_pulls_the_page_to_it() -> None:
    page = collection.page(100, 9, scroll=0, selected=42)
    assert page.start <= 42 < page.end
    page = collection.page(100, 9, scroll=90, selected=3)
    assert page.start <= 3 < page.end


def test_a_typed_number_resolves_to_the_row_the_player_can_see() -> None:
    page = collection.page(100, 9, scroll=30)
    assert page.absolute(1) == 30, "the first row shown is the one typed as 1"
    assert page.absolute(9) == 38
    assert page.absolute(10) == -1, "a row that is not shown cannot be typed"
    assert collection.page(0, 9, 0).absolute(1) == -1


def test_a_page_says_how_much_it_is_not_showing() -> None:
    assert collection.page(0, 9, 0).label() == "NONE"
    assert collection.page(5, 9, 0).label() == "5"
    assert collection.page(100, 9, 30).label() == "31–39 OF 100"


def test_a_selection_stops_at_the_ends_rather_than_wrapping() -> None:
    assert collection.step(10, 9, 1) == 9, "past the end stays at the end"
    assert collection.step(10, 0, -1) == 0
    assert collection.step(0, 0, 1) == -1


# --- the screens themselves ---------------------------------------------------

def _petitions(count: int) -> dict:
    return {"justice": {"petitions": [
        {"id": f"p{n}", "kind": f"kind{n}", "waiting": n, "good": "grain",
         "petitioner": "a", "against": "b", "claim_text": "x",
         "counter_text": "y"}
        for n in range(count)]}}


def _hits(count: int) -> list[dict]:
    return [{"ref": f"r{n}", "sender": "a", "snippet": f"snip{n}",
             "dated_as": "then", "title": "t", "kind": "letter"}
            for n in range(count)]


def _house(count: int) -> dict:
    return {"house": {"ruler": "king", "members": [
        {"id": f"m{n}", "name": f"person{n}", "alive": True, "age_years": 40 - n,
         "competence": "able", "health": "well", "loyalty": "true",
         "location": "ugarit", "post": "", "interests": [], "agenda": ""}
        for n in range(count)]}, "institutions": [], "revenue": {}}


def _institutions(count: int) -> dict:
    return {"institutions": [
        {"id": f"i{n}", "name": f"house{n}", "kind": "granary", "head": "",
         "condition": 500, "inspected": False, "history": [500],
         "group_name": "", "staff": 0, "upkeep": 0}
        for n in range(count)], "projects": [], "revenue": {}, "date": "first"}


def test_the_docket_shows_a_scrolled_petition_and_says_where_it_is() -> None:
    for count in SIZES:
        belief = _petitions(count)
        assert plain_text(palace.compose(belief, view="court", height=36))
        if not count:
            continue
        text = plain_text(palace.compose(
            belief, view="court", selected=f"p{count - 1}", height=36,
            scroll=count))                       # past the end; must clamp back
        assert f"kind{count - 1}" in text, count
        if count > 12:
            assert "OF" in text, "a partial list must say so"


def test_search_results_beyond_the_ninth_can_be_reached() -> None:
    hits = _hits(100)
    text = plain_text(archive.compose({}, "q", hits, scroll=90))
    assert "snip90" in text
    assert "snip9”" not in text or "snip99" in text
    assert "OF 100" in text


def test_the_house_shows_its_tenth_adult() -> None:
    for count in SIZES:
        belief = _house(count)
        assert plain_text(palace.compose(belief, view="house", height=36))
    text = plain_text(palace.compose(
        _house(100), view="house", selected="m99", height=36, scroll=95))
    assert "person99" in text
    assert "OF 100" in text


def test_the_city_table_pages_rather_than_stopping() -> None:
    for count in SIZES:
        belief = _institutions(count)
        assert plain_text(alu.compose(
            belief, height=36, view="institutions"))
    text = plain_text(alu.compose(
        _institutions(100), height=36, scroll=95, view="institutions"))
    assert "house99" in text
    assert "95–100 OF 100" in text


def _works(projects: int, plans: int) -> dict:
    return {
        "projects": [
            {"what": f"work{n}", "repair": False, "days_done": 1,
             "days_needed": 10, "spent": {}, "institution": ""}
            for n in range(projects)],
        "plans": [{"name": f"plan{n}", "kind": f"k{n}", "days": 10}
                  for n in range(plans)],
        "land": {"corvee_days": 0, "works_days": 0},
        "works_materials": {}, "works_season": True,
    }


def test_the_works_lists_page() -> None:
    """The two lists scroll independently; each is tested with the other short.

    Both long at once genuinely does not fit an 82 x 32 window -- three rows a
    project leaves the plans nothing -- and the specification's answer to that
    is the responsive tier, not a list that silently drops rows.
    """
    for count in SIZES:
        assert plain_text(works.compose(_works(count, count), height=32))

    out = plain_text(works.compose(_works(100, 2), height=32, scroll=95))
    assert "work95" in out
    assert "OF 100" in out

    buildable = plain_text(works.compose(_works(0, 100), height=32,
                                         plan_scroll=95))
    assert "plan95" in buildable
    assert "OF 100" in buildable
