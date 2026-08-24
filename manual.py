"""The field manual: deterministic Help, assembled from the registries.

UI/UX specification section 11. Help is software documentation, not a
conversation: correct, fast, compact, free, and never a model call. It answers
"how do I assign troops?" and deliberately does not answer "should I?", which
belongs to a named adviser who is allowed to be wrong.

Topics come from two places and are joined here. The live action registry knows
the exact cost, the command grammar, the mnemonic, and which screens offer an
action -- all of it generated rather than transcribed, so a new action arrives
in Help the moment it arrives in the game. `content/help_commands.toml` carries
the authored prose that explains what a thing *means*, which no registry can
derive.

Search is a plain deterministic scan. There is no ranking model and no index to
go stale: at this corpus size the whole thing is scanned per keystroke in well
under the specification's 50 ms.
"""
from __future__ import annotations

import dataclasses
import re

import registry
from ai import help_agent

_WORD = re.compile(r"[a-z0-9]+")

# Which window each help category belongs beside, so opening Help from a screen
# can put that screen's topics at the top.
SCREEN_OF_CATEGORY = {
    "interface": "hall",
    "correspondence": "stack",
    "stores": "stores",
    "land": "land",
    "muster": "muster",
    "works": "works",
    "justice": "justice",
    "house": "house",
    "altar": "altar",
    "oaths": "oaths",
    "archive": "archive",
    "relations": "relations",
    "health": "plague",
    "alu": "alu",
}


@dataclasses.dataclass(frozen=True)
class Topic:
    id: str
    title: str
    screens: tuple[str, ...]
    body: str
    syntax: str = ""
    command: str = ""
    cost: int | None = None
    key: str = ""
    examples: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    @property
    def cost_line(self) -> str:
        if self.cost is None:
            return ""
        if self.cost == 0:
            return "Cost: no hours."
        unit = "hour" if self.cost == 1 else "hours"
        return f"Cost: {self.cost} {unit}."


def _titlecase(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _from_descriptor(descriptor) -> Topic:
    """A topic generated from an action, so it cannot drift from the game."""
    doc = help_agent.BY_ID.get(descriptor.help_topic)
    body = doc.answer if doc is not None else ""
    where = ", ".join(_titlecase(context) for context in descriptor.contexts)
    lead = f"{descriptor.label} is offered in {where}."
    return Topic(
        id=f"action:{descriptor.id}",
        title=descriptor.label.upper(),
        screens=descriptor.contexts,
        body=(lead + (" " + body if body else "")),
        syntax=(f"[{descriptor.mnemonic}] {descriptor.label}"
                if descriptor.mnemonic else descriptor.label),
        command=descriptor.grammar[0] if descriptor.grammar else "",
        cost=descriptor.cost,
        key=descriptor.mnemonic,
        examples=tuple(doc.examples[:2]) if doc is not None else (),
        related=tuple(sorted(set(descriptor.contexts))),
        keywords=tuple(doc.keywords) if doc is not None else (),
    )


def _from_doc(doc) -> Topic:
    """A topic for something authored that is not one action -- a screen, a
    concept, the shape of the interface."""
    screen = SCREEN_OF_CATEGORY.get(doc.category, "hall")
    return Topic(
        id=f"topic:{doc.id}",
        title=doc.title.upper(),
        screens=(screen,),
        body=doc.answer,
        syntax=doc.syntax,
        examples=tuple(doc.examples[:2]),
        keywords=tuple(doc.keywords),
        related=(screen,),
    )


def _build() -> tuple[Topic, ...]:
    """One topic per action, plus the authored topics no action covers.

    A doc that is already some action's prose is not listed again on its own:
    it would put "Repair" and "Repair an institution" side by side in the list,
    saying the same thing twice and making the manual look padded. The screen
    and concept entries -- the Hall, the Inbox, the terminal -- have no action
    behind them and are listed in their own right.
    """
    live = registry.player_descriptors()
    topics = [_from_descriptor(d) for d in live]
    spoken_for = {d.help_topic for d in live}
    topics += [_from_doc(doc) for doc in help_agent.DOCS
               if doc.id not in spoken_for]
    topics.sort(key=lambda topic: topic.title)
    return tuple(topics)


TOPICS = _build()
BY_ID = {topic.id: topic for topic in TOPICS}


def for_screen(screen: str) -> tuple[Topic, ...]:
    """Topics belonging to one window, which is what Help opens showing."""
    return tuple(topic for topic in TOPICS if screen in topic.screens)


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def search(query: str, screen: str = "") -> tuple[Topic, ...]:
    """Every topic matching `query`, best first, deterministically.

    Scoring is ordinary and explainable: a hit in the title beats a hit in a
    keyword, which beats a hit in the body, and a topic belonging to the screen
    the player is looking at gets a nudge. Ties break on title so the list never
    reorders itself between identical searches.
    """
    terms = _tokens(query)
    if not terms:
        ordered = for_screen(screen) if screen else ()
        rest = tuple(topic for topic in TOPICS if topic not in ordered)
        return ordered + rest

    scored: list[tuple[int, str, Topic]] = []
    for topic in TOPICS:
        title = topic.title.casefold()
        keywords = " ".join(topic.keywords).casefold()
        haystack = " ".join((topic.body, topic.command, topic.syntax,
                             " ".join(topic.examples))).casefold()
        score = 0
        for term in terms:
            if term in title:
                score += 8
            if term in keywords:
                score += 4
            if term in haystack:
                score += 2
        if not score:
            continue
        if screen and screen in topic.screens:
            score += 3
        scored.append((-score, topic.title, topic))
    scored.sort(key=lambda row: (row[0], row[1]))
    return tuple(topic for _score, _title, topic in scored)


def covered_keys() -> frozenset[str]:
    """Every control the manual documents, for the coverage test."""
    keys = set()
    for topic in TOPICS:
        if topic.key:
            keys.add(topic.key)
    return frozenset(keys)


def covered_actions() -> frozenset[str]:
    return frozenset(
        topic.id.split(":", 1)[1] for topic in TOPICS
        if topic.id.startswith("action:"))
