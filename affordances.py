"""Names the player may use, read from Belief alone (UI/UX spec 10).

Every function takes a Belief dict and returns ids or names already visible to
the player. No engine, no World, so nothing here can widen what he knows.

Shared by the palette and `ai/parser.py` so both resolve a word the same way.
"""
from __future__ import annotations

import re

# How letters in the stack are numbered when spoken about.
ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
         "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx")

# Closed vocabularies. Fixed by the engine, so constants, not Belief reads.
TROOP_TASKS = ("garrison", "watch", "harvest", "campaign")
LEDGERS = ("granary", "seed")
VERDICTS = ("for", "against", "split", "defer")
QUESTIONS = ("harvest", "sickness", "war", "voyage", "death")
RECEPTIONS = ("accept", "settle", "redirect", "refuse")
CORVEE_TASKS = ("work", "dredge", "build", "repair", "harvest", "escort")


def normal(value: str) -> str:
    """Casefold, strip punctuation, and drop a leading article."""
    words = re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip().split()
    while words and words[0] in {"a", "an", "the"}:
        words.pop(0)
    return " ".join(words)


def letters(belief: dict) -> dict[str, str]:
    return {(ROMAN[i] if i < len(ROMAN) else str(i + 1)): item["id"]
            for i, item in enumerate(belief.get("stack", []))}


def resolve_letter(value: str, belief: dict) -> str | None:
    ids = {item["id"] for item in belief.get("stack", [])}
    return letters(belief).get(
        str(value).lower(), value if value in ids else None)


def resolve_named(value: str, rows: list[dict], id_key: str = "id",
                  name_key: str = "name") -> str | None:
    """Resolve an exact id or an unambiguous player-facing name.

    Returns None when two rows match. Palette rule 4: never guess between them.
    """
    wanted = normal(value)
    exact: list[str] = []
    partial: list[str] = []
    for row in rows:
        item_id = row[id_key]
        names = {
            normal(item_id),
            normal(str(item_id).split(":", 1)[-1]),
            normal(str(row.get(name_key, ""))),
            normal(str(row.get(name_key, "")).split(",", 1)[0]),
        }
        if wanted in names:
            exact.append(item_id)
        elif len(wanted) >= 4 and any(
                name.startswith(wanted) or wanted.startswith(name)
                for name in names if name):
            partial.append(item_id)
    matches = list(dict.fromkeys(exact or partial))
    return matches[0] if len(matches) == 1 else None


def matches_for(value: str, rows: list[dict], id_key: str = "id",
                name_key: str = "name") -> list[str]:
    """Every id a partial word could mean. Feeds completion."""
    wanted = normal(value)
    found = []
    for row in rows:
        item_id = row[id_key]
        names = [normal(item_id), normal(str(row.get(name_key, "")))]
        if not wanted or any(name.startswith(wanted) for name in names if name):
            found.append(item_id)
    return list(dict.fromkeys(found))


# --- the domains --------------------------------------------------------------

def groups(belief: dict) -> list[dict]:
    return list(belief.get("groups", []))


def cohorts(belief: dict) -> list[dict]:
    return [row for row in belief.get("cohorts", []) if not row.get("parent")]


def detachments(belief: dict) -> list[dict]:
    return [row for row in belief.get("cohorts", []) if row.get("parent")]


def displaced(belief: dict) -> list[dict]:
    return [row for row in belief.get("cohorts", [])
            if row.get("status") == "petitioning"]


def formations(belief: dict) -> list[dict]:
    return list(belief.get("troops", {}).get("formations", []))


def institutions(belief: dict) -> list[dict]:
    return list(belief.get("institutions", []))


def plans(belief: dict) -> list[dict]:
    return list(belief.get("plans", []))


def projects(belief: dict) -> list[dict]:
    return list(belief.get("projects", []))


def people(belief: dict) -> list[dict]:
    return [person for person in belief.get("house", {}).get("members", [])
            if person.get("alive")]


def estates(belief: dict) -> list[dict]:
    return list(belief.get("land", {}).get("estates", []))


def oaths(belief: dict) -> list[dict]:
    return list(belief.get("oaths", []))


def omens(belief: dict) -> list[dict]:
    return list(belief.get("house", {}).get("omens", []))


def petitions(belief: dict) -> list[dict]:
    return list(belief.get("justice", {}).get("petitions", []))


def actors(belief: dict) -> list[dict]:
    return [{"id": relation["other"], "name": relation.get("name", relation["other"])}
            for relation in belief.get("relations", [])]


def goods(belief: dict) -> list[dict]:
    return list(belief.get("gift_goods", []))


def tablets(belief: dict) -> list[dict]:
    return list(belief.get("stack", []))


def places(belief: dict) -> list[dict]:
    found = {str(belief.get("seat", "seat"))}
    found.update(str(relation["place"]) for relation
                 in belief.get("relations", []) if relation.get("place"))
    found.update(str(inst["place"]) for inst in institutions(belief)
                 if inst.get("place"))
    found.update(str(estate["place"]) for estate in estates(belief)
                 if estate.get("place"))
    # The route tablet is the one place Belief spells a place the way the court
    # says it. Without this the game answers "akko" when it means Akko, both
    # here and in anything that reads an order back.
    named = {str(place["id"]): str(place.get("name") or place["id"])
             for place in belief.get("world_graph", {}).get("places", [])}
    found.update(named)
    return [{"id": place, "name": named.get(place, place)}
            for place in sorted(found)]


def posts(belief: dict) -> list[dict]:
    found = [inst["id"] for inst in institutions(belief)]
    found += [f"governor:{place['id']}" for place in places(belief)]
    found += [f"command:{formation['id']}" for formation in formations(belief)]
    found += [f"court:{relation['other']}"
              for relation in belief.get("relations", [])]
    return [{"id": post, "name": post.replace(":", " of ")} for post in found]


def _closed(values) -> list[dict]:
    return [{"id": value, "name": value} for value in values]


# Field domain -> the rows it may be drawn from. `registry.Field.domain` names
# one of these; anything not listed is free text and is not completed.
DOMAINS = {
    "group": groups,
    "cohort": cohorts,
    "detachment": detachments,
    "displaced": displaced,
    "formation": formations,
    "institution": institutions,
    "plan": plans,
    "project": projects,
    "person": people,
    "estate": estates,
    "oath": oaths,
    "omen": omens,
    "petition": petitions,
    "actor": actors,
    "good": goods,
    "tablet": tablets,
    "place": places,
    "post": posts,
    "task": lambda b: _closed(TROOP_TASKS),
    "ledger": lambda b: _closed(LEDGERS),
    "verdict": lambda b: _closed(VERDICTS),
    "question": lambda b: _closed(QUESTIONS),
    "reception": lambda b: _closed(RECEPTIONS),
    "corvee_task": lambda b: _closed(CORVEE_TASKS),
}


def rows_for(domain: str, belief: dict) -> list[dict]:
    """Everything the player may legally name in this domain, right now."""
    source = DOMAINS.get(domain)
    return [] if source is None else list(source(belief))


def resolve(domain: str, value: str, belief: dict) -> str | None:
    """One id, or None when the word is unknown or means more than one thing."""
    if domain == "quantity":
        text = normal(value).replace(",", "")
        return text if text.isdigit() else None
    if domain == "text":
        return value or None
    if domain == "tablet":
        return resolve_letter(value, belief)
    rows = rows_for(domain, belief)
    if not rows:
        return None
    if domain == "plan":
        return resolve_named(value, rows, "kind", "name")
    if domain == "post":
        wanted = normal(value).replace(" of ", " ")
        found = [row["id"] for row in rows
                 if normal(row["id"]).replace(" of ", " ") == wanted]
        if len(found) == 1:
            return found[0]
    return resolve_named(value, rows)


def name_in(domain: str, value: str, belief: dict) -> str:
    """The player-facing name of an id, or the id spoken as words.

    The reverse of `resolve`, and needed wherever the game has to read an
    order back to the player -- the Orders workbench most of all, since a
    record of intent written in engine ids is a record nobody can audit.
    """
    text = str(value)
    key = "kind" if domain == "plan" else "id"
    for row in rows_for(domain, belief):
        if row.get(key) == text:
            return str(row.get("name") or text).replace("_", " ")
    return text.replace("_", " ")


def completions(domain: str, prefix: str, belief: dict) -> list[str]:
    """Legal values beginning with what has been typed, for Tab and the list."""
    if domain in ("quantity", "text"):
        return []
    if domain == "tablet":
        wanted = normal(prefix)
        return [item["id"] for item in tablets(belief)
                if not wanted or normal(item["id"]).startswith(wanted)]
    rows = rows_for(domain, belief)
    key = "kind" if domain == "plan" else "id"
    return matches_for(prefix, rows, key, "name")
