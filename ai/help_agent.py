"""Retrieval-grounded answers about controls and playable commands.

The tutor knows the game, not the kingdom.  Its knowledge is the authored
command corpus in ``content/help_commands.toml``; retrieval chooses the small
part relevant to a question. Help itself remains an exact software manual,
while a named court speaker may use the required model to phrase those
retrieved records without changing them.
"""
from __future__ import annotations

import dataclasses
import math
import re
import tomllib
from collections import Counter
from pathlib import Path

from ai.client import ModelUnavailable, safe_fields
from ai.numeric_guard import extract_numerals_and_number_words, guard

_PATH = Path(__file__).parent.parent / "content" / "help_commands.toml"
_WORD = re.compile(r"[a-z0-9]+|\\")
_STOP = frozenset({
    "a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "in",
    "is", "it", "me", "my", "of", "on", "please", "the", "to", "what",
    "where", "with", "you",
})
_ALIASES = {
    "army": "troops",
    "soldiers": "troops",
    "mail": "inbox",
    "letters": "tablet",
    "tax": "due",
    "taxes": "due",
    "wages": "allocate",
    "payment": "allocate",
    "payments": "allocate",
    "building": "institution",
    "buildings": "institution",
    "broken": "repair",
    "fix": "repair",
    "cancel": "abandon",
    "workers": "labour",
    "workmen": "labour",
    "courtier": "person",
    "appoint": "place",
}


@dataclasses.dataclass(frozen=True)
class CommandDoc:
    id: str
    category: str
    title: str
    syntax: str
    answer: str
    examples: tuple[str, ...]
    keywords: tuple[str, ...]
    keys: tuple[str, ...]
    verbs: tuple[str, ...]

    @property
    def passage(self) -> str:
        examples = " | ".join(self.examples)
        return (
            f"[{self.id}] {self.title}\n"
            f"Exact form: {self.syntax}\n"
            f"{self.answer}\n"
            f"Examples: {examples}"
        )


@dataclasses.dataclass(frozen=True)
class Hit:
    doc: CommandDoc
    score: float


def _load() -> tuple[CommandDoc, ...]:
    data = tomllib.loads(_PATH.read_text())
    return tuple(CommandDoc(
        id=row["id"],
        category=row["category"],
        title=row["title"],
        syntax=row["syntax"],
        answer=row["answer"],
        examples=tuple(row.get("examples", [])),
        keywords=tuple(row.get("keywords", [])),
        keys=tuple(row.get("keys", [])),
        verbs=tuple(row.get("verbs", [])),
    ) for row in data["command"])


DOCS = _load()
BY_ID = {doc.id: doc for doc in DOCS}


def _tokens(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for raw in _WORD.findall(text.casefold().replace("-", " ")):
        if raw in _STOP:
            continue
        word = _ALIASES.get(raw, raw)
        found.append(word)
        if len(word) > 4 and word.endswith("s"):
            found.append(word[:-1])
        if len(word) > 5 and word.endswith("ing"):
            found.append(word[:-3])
    return tuple(found)


def _document_terms(doc: CommandDoc) -> tuple[Counter, Counter, Counter]:
    strong = Counter(_tokens(
        f"{doc.id} {doc.title} {doc.syntax} {' '.join(doc.keywords)}"))
    body = Counter(_tokens(f"{doc.answer} {' '.join(doc.examples)}"))
    keys = Counter(key.casefold() for key in doc.keys)
    return strong, body, keys


_TERMS = {doc.id: _document_terms(doc) for doc in DOCS}
_DF = Counter(
    term
    for doc in DOCS
    for term in set(_TERMS[doc.id][0]) | set(_TERMS[doc.id][1])
)


def is_catalogue_question(question: str) -> bool:
    words = set(_tokens(question))
    return bool(words & {"all", "every", "list", "catalogue", "catalog"}
                and words & {"command", "commands", "order", "orders"})


def retrieve(question: str, limit: int = 5) -> tuple[Hit, ...]:
    """Return the command records most relevant to a natural question."""
    terms = _tokens(question)
    if not terms:
        return (Hit(BY_ID["help"], 1.0),)
    query = Counter(terms)
    query_terms = set(query)
    lowered = question.casefold().strip()
    scored: list[Hit] = []
    for doc in DOCS:
        strong, body, keys = _TERMS[doc.id]
        score = 0.0
        for term, count in query.items():
            idf = math.log((len(DOCS) + 1) / (_DF[term] + 1)) + 1
            score += count * idf * (
                min(strong[term], 3) * 3.0
                + min(body[term], 2) * 1.0
                + min(keys[term], 1) * 4.0)
        id_terms = set(_tokens(doc.id.replace("_", " ")))
        if id_terms and id_terms <= query_terms:
            score += 20
        for phrase in doc.keywords:
            if " " in phrase and phrase.casefold() in lowered:
                score += 7
        if score:
            scored.append(Hit(doc, score))
    scored.sort(key=lambda hit: (-hit.score, hit.doc.id))
    if not scored:
        return (Hit(BY_ID["help"], 1.0),)
    multi_part = any(
        f" {joiner} " in f" {lowered} " for joiner in ("and", "or", "also"))
    if not multi_part and not is_catalogue_question(question):
        # Most questions ask for one operation. Shared words such as "send"
        # should not drag gift-giving into an answer about a campaign.
        scored = [hit for hit in scored if hit.score >= scored[0].score * 0.90]
    return tuple(scored[:max(1, limit)])


def covered_verbs() -> frozenset[str]:
    return frozenset(verb for doc in DOCS for verb in doc.verbs)


def covered_keys() -> frozenset[str]:
    return frozenset(key.casefold() for doc in DOCS for key in doc.keys)


def catalogue_answer() -> str:
    orders = ", ".join(doc.title.casefold()
                       for doc in DOCS if doc.category == "orders")
    return (
        "I know every current Hall control, room control, and Counsel order. "
        "The order tablets cover " + orders + ". Ask about any one of those "
        "and I will give you its exact form, cost, and an example."
    )


def fallback_answer(question: str, hits: tuple[Hit, ...]) -> str:
    """Answer entirely from retrieved records when the model is absent."""
    if is_catalogue_question(question):
        return catalogue_answer()
    if not hits:
        return BY_ID["help"].answer
    first = hits[0].doc
    answer = first.answer
    if first.examples:
        answer += f" For example: {first.examples[0]}"
    # A genuinely two-part question should not have its second half silently
    # discarded. Keep the threshold high so ordinary synonym matches stay
    # concise.
    if (len(hits) > 1 and hits[1].score >= hits[0].score * 0.82
            and hits[1].doc.id != first.id
            and hits[1].doc.category == first.category):
        second = hits[1].doc
        answer += f" Related: {second.answer}"
    return answer


def current_choices(belief: dict) -> str:
    """Projected identifiers that make a retrieved syntax immediately usable."""
    sections = [
        ("groups", [row["id"] for row in belief.get("groups", [])]),
        ("formations", [row["id"] for row in belief.get(
            "troops", {}).get("formations", [])]),
        ("institutions", [row["id"] for row in belief.get("institutions", [])]),
        ("build kinds", [row["kind"] for row in belief.get("plans", [])]),
        ("projects", [row["id"] for row in belief.get("projects", [])]),
        ("petitions", [row["id"] for row in belief.get(
            "justice", {}).get("petitions", [])]),
        ("living people", [row["id"] for row in belief.get(
            "house", {}).get("members", []) if row["alive"]]),
        ("oaths", [row["id"] for row in belief.get("oaths", [])]),
        ("correspondents", [row["other"]
                            for row in belief.get("relations", [])]),
    ]
    return "\n".join(
        f"{title}: {', '.join(values) if values else 'none'}"
        for title, values in sections)


def build_prompt(question: str, said: list[tuple[str, str]],
                 hits: tuple[Hit, ...], belief: dict) -> list[dict]:
    retrieved = "\n\n".join(hit.doc.passage for hit in hits)
    if is_catalogue_question(question):
        retrieved += "\n\nFULL ORDER INDEX:\n" + "\n".join(
            f"- {doc.title}: {doc.syntax}"
            for doc in DOCS if doc.category == "orders")
    history = "\n".join(
        f"{'Player' if who == 'player' else 'Tutor'}: {text}"
        for who, text in said[-6:])
    fields = safe_fields({
        "question": question,
        "retrieved_passages": retrieved,
        "current_choices": current_choices(belief),
        "conversation": history,
    })
    return [
        {"role": "system", "content":
         "You are the game's Help agent. Answer how to operate the game, not "
         "what strategic choice to make. Use only the retrieved command "
         "passages and current choices below. Never invent a key, command, "
         "cost, rule, or identifier. Give exact syntax and one useful example "
         "when the question asks how to do something. If the passages do not "
         "answer it, say so plainly. Be concise. /no_think"},
        {"role": "user", "content":
         "RETRIEVED COMMAND PASSAGES:\n"
         f"{fields['retrieved_passages']}\n\n"
         "CURRENT VALID NAMES:\n"
         f"{fields['current_choices']}\n\n"
         + (f"RECENT CONVERSATION:\n{fields['conversation']}\n\n"
            if fields["conversation"] else "")
         + f"QUESTION:\n{fields['question']}"},
    ]


def _retrieval_question(
        question: str, said: list[tuple[str, str]]) -> str:
    """Resolve short follow-ups against the last thing the player asked."""
    lowered = question.casefold()
    terms = set(_tokens(question))
    follows = (len(terms) <= 3
               or bool(re.search(r"\b(that|this|those|there|it)\b", lowered)))
    if follows:
        previous = next(
            (text for who, text in reversed(said) if who == "player"), "")
        if previous:
            return previous + "\n" + question
    return question


def speak(question: str, said: list[tuple[str, str]], belief: dict,
          seed: int, turn: int, client=None) -> tuple[str, str, tuple[Hit, ...]]:
    """Retrieve exact help records, then phrase them through the court voice."""
    hits = retrieve(_retrieval_question(question, said))
    authored = fallback_answer(question, hits)
    if client is None:
        return authored, "fallback", hits
    messages = build_prompt(question, said, hits, belief)
    try:
        text = client.call(
            "help", messages, None, seed + len(said), 420, 30, turn).strip()
        allowed = set(extract_numerals_and_number_words(
            " ".join(message["content"] for message in messages)))
        if not text or not guard(text, allowed)[0]:
            return authored, "fallback", hits
        return text, "model", hits
    except (ModelUnavailable, Exception):
        return authored, "fallback", hits
