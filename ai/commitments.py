"""What a finished matter binds the crown to, read out of the player's words.

The desk has no term editor. The player writes what he wants said, and this
reads the sentences back and reports the commitments it finds, so that they can
be shown before the tablet is sealed. Nothing here mutates the world: the terms
it returns are the same `A.LetterTerm` records `engine/letter_terms.py` has
always reserved goods against.

Deterministic and offline on purpose. A commitment the player cannot see before
sealing is worse than one the reader missed, so every rule here is narrow: it
fires on a stated quantity or a named person, never on a mood.
"""
from __future__ import annotations

import dataclasses
import re

from ai.numeric_guard import normalise

# Every phrase that opens a commitment, and the term kind it opens. Order
# matters: the first pattern that matches a sentence claims it, so a request
# ("send me") is tested before a gift ("send").
_GIVING = r"(?:i\s+send|i\s+give|i\s+have\s+sent|there\s+go(?:es)?)"
_PROMISING = r"(?:i\s+shall\s+send|i\s+will\s+send|i\s+promise|i\s+shall\s+give)"
_ASKING = r"(?:send\s+me|let\s+.{0,20}?\s*send\s+me|i\s+ask\s+(?:for|of)|grant\s+me)"

from ai.numeric_guard import _NUMBER_WORDS  # noqa: E402  (shared word list)

# A quantity is digits or a run of English number words; the phrase that
# follows it, up to the next "and", comma or stop, is where the good is named.
_WORD = "|".join(sorted((w for w in _NUMBER_WORDS if w not in ("a", "and")),
                        key=len, reverse=True))
_QUANTITY = rf"(\d[\d,]*|(?:(?:{_WORD})[\s-]*)+)"
_GOOD = r"([a-z][a-z\s'’-]{2,40}?)"
_STOP = r"(?=\s+and\b|[.,;:]|$)"


@dataclasses.dataclass(frozen=True)
class Commitment:
    """One promise or request the matter makes, with the words that made it."""
    kind: str
    good: str = ""
    quantity: int = 0
    person_id: str = ""
    person_name: str = ""
    destination: str = ""
    sentence: str = ""

    def describe(self) -> str:
        if self.kind == "marriage_proposal":
            return f"{self.person_name or self.person_id} is offered in marriage"
        subject = f"{self.quantity:,} {self.good.replace('_', ' ')}"
        return {
            "gift": f"you send {subject}",
            "promise_good": f"you promise {subject}",
            "request_good": f"you ask for {subject}",
            "service": f"you pledge {subject}",
        }.get(self.kind, f"{self.kind}: {subject}")


def _sentences(matter: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", matter.strip())
    return [part.strip() for part in parts if part.strip()]


def _number(word: str) -> int:
    value = normalise(word.replace(",", "").strip())
    try:
        return int(value)
    except ValueError:
        return 0


def _goods_index(belief: dict) -> dict[str, str]:
    """Spoken good name -> id, for every good the crown could actually send."""
    index: dict[str, str] = {}
    for entry in belief.get("gift_goods", []):
        good = str(entry.get("id") or "")
        if good:
            index[good.replace("_", " ")] = good
            index[good] = good
    for good in belief.get("stores", {}):
        index.setdefault(str(good).replace("_", " "), str(good))
    return index


def _match_good(phrase: str, index: dict[str, str]) -> str:
    """The good named in a phrase like "jars of oil" or "parisu of grain"."""
    words = phrase.lower().strip().strip(".,")
    if words in index:
        return index[words]
    for name, good in sorted(index.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(name)}\b", words):
            return good
    return ""


def _destination(sentence: str, actors: set[str], belief: dict) -> str:
    """Which court the sentence names, by id or by the name it is written by."""
    from tui import render

    said = sentence.casefold()
    for actor in sorted(actors):
        spoken = render.actor_name(actor, belief.get("house")).casefold()
        if actor.casefold() in said or (spoken and spoken in said):
            return actor
        # "the king of Assur" against "the king of Assur, my brother".
        tail = spoken.split(",")[0].strip()
        if tail and tail in said:
            return actor
    return ""


def _people_index(belief: dict) -> dict[str, tuple[str, str]]:
    people: dict[str, tuple[str, str]] = {}
    for person in belief.get("house", {}).get("members", []):
        if not person.get("alive"):
            continue
        name = str(person.get("name") or "")
        if not name:
            continue
        # People are named on the page with their standing -- "Sharelli, the
        # queen mother" -- and the king writing about her uses her name alone.
        people[name.casefold()] = (str(person["id"]), name)
        people.setdefault(name.split(",")[0].strip().casefold(),
                          (str(person["id"]), name))
    return people


def _quantity_terms(sentence: str, opener: str, kind: str,
                    goods: dict[str, str]) -> tuple[Commitment, ...]:
    """Every counted good named after this opener. One clause, one commitment.

    "forty jars of oil and two talents of copper" is two commitments, because
    the store is asked for two different things and each must be seen.
    """
    start = re.search(opener, sentence, re.I)
    if start is None:
        return ()
    rest = sentence[start.end():]
    found: list[Commitment] = []
    for match in re.finditer(rf"\b{_QUANTITY}\s+{_GOOD}{_STOP}", rest, re.I):
        quantity = _number(match[1])
        good = _match_good(match[2], goods)
        if quantity and good:
            found.append(Commitment(kind=kind, good=good, quantity=quantity,
                                    sentence=sentence.strip()))
    return tuple(found)


def read(matter: str, belief: dict) -> tuple[Commitment, ...]:
    """Every commitment the finished matter makes, in the order it makes them."""
    goods = _goods_index(belief)
    people = _people_index(belief)
    actors = {str(row.get("other")) for row in belief.get("relations", [])}
    found: list[Commitment] = []

    for sentence in _sentences(matter):
        marriage = re.search(
            r"[Ii]\s+(?:give|offer|send)\s+(?:my\s+)?(?:daughter|son|sister|"
            r"brother|kinsman|kinswoman)?\s*([A-Z][\w'’-]+)"
            r"[^.]*?\b(?:to|into)\b", sentence)
        if marriage:
            key = marriage[1].casefold()
            if key in people:
                person_id, name = people[key]
                destination = _destination(sentence, actors, belief)
                found.append(Commitment(
                    kind="marriage_proposal", person_id=person_id,
                    person_name=name, destination=destination,
                    sentence=sentence.strip()))

        for opener, kind in ((_ASKING, "request_good"),
                             (_PROMISING, "promise_good"),
                             (_GIVING, "gift")):
            terms = _quantity_terms(sentence, opener, kind, goods)
            if terms:
                found.extend(terms)
                break

    return tuple(found)


def as_terms(commitments: tuple[Commitment, ...]):
    """The engine's own term records, for dispatch."""
    from engine import actions as A

    return tuple(
        A.LetterTerm(
            kind=item.kind, good=item.good, quantity=item.quantity,
            person_id=item.person_id, destination=item.destination)
        for item in commitments)
