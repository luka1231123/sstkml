"""Ask: Yabninu answers "how do I" from the help records and "what should I do"
from the facts and the people tags (docs/PLAN.md, SPEC 2.7). The model only picks
which whole notes answer the question. It writes no words, so it cannot invent
a number, a key or a fact. Asking is free."""
from __future__ import annotations

import json
import math
import re
import tomllib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from ai import narrator
from ai.client import safe_fields
from belief import people
from belief.facts import facts

_STOP = frozenset("a an and are can do does for how i in is it me my of on please the to what where who with you".split())
_ALIASES = {
    "army": "troops", "soldiers": "troops", "mail": "inbox", "letters": "tablet",
    "tax": "due", "taxes": "due", "wages": "allocate", "payment": "allocate",
    "payments": "allocate", "cut": "allocate", "reduce": "allocate", "aid": "relief",
    "building": "institution", "buildings": "institution", "broken": "repair",
    "fix": "repair", "cancel": "abandon", "workers": "labour", "workmen": "labour",
    "courtier": "person", "appoint": "place",
}
_HOW = re.compile(r"\b(how(?! much| many)|where|which|key|button|cost)\b", re.I)
_QTY = re.compile(r"\bhow (much|many)\b|\bexact", re.I)
_WHO = re.compile(r"^\s*who\s+(is|are|was)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_URGENT = "(urgent) "        # marks a note for the model only; it is dropped from the answer
_SCHEMA = {"type": "object", "required": ["notes"], "properties": {
    "notes": {"type": "array", "maxItems": 4, "items": {"type": "integer"}}}}
_RULES = """You are Yabninu, the king's scribe. The king asks a question. Choose the numbered notes that answer it.
Reply as JSON: {"notes": [numbers]}. Pick at most 4 notes. A note marked (urgent) is urgent.
For a how-question, pick the note that says where to go, then the steps. Pick none if no note answers the question. /no_think"""
_SHOTS = (
    ("(1) (urgent) Salt lasts about 2 fortnights.\n(2) The next ship comes in 4 fortnights; salt falls 2 fortnights short.\n"
     "(3) Spoilage took a little.\n(4) You can buy salt from the quay in Trade [x].\n(5) You can send a runner for salt in Scribes [s].",
     "what should I do about salt?", [1, 2, 4, 5]),
    ("(1) Ehli-Nikkalu, the queen · Palace · wants her own son on the seat.", "how many ships are in the harbour?", []),
    ("(1) Filing moves a tablet out of the pile and into the tablet house.\n(2) It costs no hours.\n"
     "(3) Restoring brings the tablet back to the pile.\n(4) Press [x] to file a tablet; press [x] again to restore it.",
     "how do I file a letter?", [1, 2, 4]),
    ("(1) Nothing is urgent.\n(2) Oil lasts more than a year.", "what should I do?", [1]),
    ("(1) (urgent) Wine lasts about 2 fortnights.\n(2) Barley lasts more than a year.\n(3) You can buy wine from the quay in Trade [x].",
     "is anything urgent?", [1, 3]),
    ("(1) Nothing is urgent.\n(2) Oil lasts more than a year.\n(3) The exact count is 900 jars.", "how much oil do I have?", [2, 3]),
    ("(1) Open Muster [m], then Levies.\n(2) Choose a formation and set its task with the brackets.\n(3) Press A to give it.",
     "how do I change the guard?", [1, 2, 3]),
)

DOCS = tuple(SimpleNamespace(**{"examples": [], "keywords": [], "keys": [], **row}) for row in tomllib.loads(
    (Path(__file__).parent.parent / "content" / "help_commands.toml").read_text())["command"])
BY_ID = {doc.id: doc for doc in DOCS}


def _tokens(text: str) -> list[str]:
    out = []
    for raw in re.findall(r"[a-z0-9]+", text.casefold()):
        if raw not in _STOP:
            out.append(word := _ALIASES.get(raw, raw))
            if len(word) > 4 and word.endswith("s"):
                out.append(word[:-1])
            if len(word) > 5 and word.endswith("ing"):
                out.append(word[:-3])
    return out


_TERMS = [(Counter(_tokens(f"{d.id} {d.title} {d.syntax} {' '.join(d.keywords)}")),
           Counter(_tokens(f"{d.answer} {' '.join(d.examples)}")),
           {key.casefold() for key in d.keys}) for d in DOCS]
_DF = Counter(term for strong, body, _ in _TERMS for term in set(strong) | set(body))


def retrieve(question: str) -> list:
    """The help records that best fit the question; near ties join."""
    query, low = Counter(_tokens(question)), question.casefold()
    scored = []
    for doc, (strong, body, keys) in zip(DOCS, _TERMS):
        score = sum(n * (math.log((len(DOCS) + 1) / (_DF[t] + 1)) + 1)
                    * (min(strong[t], 3) * 3 + min(body[t], 2) + 4 * (t in keys)) for t, n in query.items())
        ids = set(_tokens(doc.id.replace("_", " ")))
        score += 20 * bool(ids and ids <= set(query)) + 7 * sum(" " in k and k.casefold() in low for k in doc.keywords)
        if score:
            scored.append((score, doc.id))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [BY_ID[i] for s, i in scored[:2] if s >= scored[0][0] * .9] or [BY_ID["help"]]


_ROOMS = re.findall(r"\[(\w)\] (\w+)", getattr(BY_ID.get("hall"), "syntax", ""))


def _keyed(text: str) -> str:
    """Put a room's key after its name, once: "Open Storehouse" becomes "Open Storehouse [t]"."""
    for key, room in _ROOMS:
        text = re.sub(rf"\b{room}\b(?! \[)", f"{room} [{key}]", text, count=1)
    return text


def _named(texts: dict, words: set) -> list:
    """The keys whose text has a word the question uses and no other text has."""
    seen = Counter(t for tokens in texts.values() for t in tokens)
    return [k for k, tokens in texts.items() if any(seen[t] == 1 and t in words for t in tokens)]


def _who(ids: list, q: str, words: set) -> list:
    """The people the question names: by their whole name, by a capitalised word of it,
    or, after "who is" or "what does ... want", by any word of their name or role that no one else has."""
    tags, asks = {i: people.tag(i) for i in ids}, bool(_WHO.match(q)) or "want" in words
    named = _named({i: set(_tokens(f"{t['name']} {t['role']}" if asks else " ".join(w for w in t["name"].split() if w[:1].isupper())))
                    for i, t in tags.items()}, words)
    return [i for i in ids if i in named or tags[i]["name"] and tags[i]["name"].casefold() in q.casefold()]


def _notes(b: dict, q: str) -> tuple[list[str], dict]:
    """The whole sentences an answer may use (people, facts, help records), and for each
    help-record sentence the index of its record's first, which an answer that uses it starts with."""
    words, fs, how = set(_tokens(q)), facts(b), bool(_HOW.search(q))
    ids = sorted({*(r["other"] for r in b["relations"]), *(m["id"] for m in b["house"]["members"]),
                  *(p["petitioner"] for p in b["justice"]["petitions"]), *(s["sender"] for s in b["stack"]),
                  *(i["head"] for i in b["institutions"] if i["head"])})
    topics = {*_named({f["id"]: set(_tokens(" ".join([f["id"], f["say"], *f["why"], *f["act"]]))) for f in fs}, words),
              *(f["id"] for f in fs if f["id"] in words)}
    who = _who(ids, q, words)
    hot = [f for f in fs if f["urgency"]][:3]
    shown = [f for f in fs if f["id"] in topics] or ([] if how or who or _WHO.match(q) else hot or fs[:1])
    out = []
    for i in who:
        out += [narrator._cap(people.line(i)), *(p["claim_text"] for p in b["justice"]["petitions"] if p["petitioner"] == i)]
    if shown and not any(f["urgency"] > 1 for f in shown):
        out.append("Nothing is urgent.")
    done = set()
    for f in shown:
        why = [narrator._cap(w) for w in f["why"]] if f["urgency"] or "why" in words else []
        acts = [a for a in f["act"] if (a.split()[0], a[-3:]) not in done]
        done |= {(a.split()[0], a[-3:]) for a in f["act"]}
        out += [_URGENT * (f["urgency"] > 1) + narrator._say(f), *why[:1], *(f"You can {a}." for a in acts), *why[1:],
                *([f"The exact count is {f['exact']}."] if _QTY.search(q) else [])]
    first = {}
    for doc in retrieve(q) if how else ():
        start = len(out)
        out += map(_keyed, _SENTENCE.split(doc.answer)[:4])
        first |= dict.fromkeys(range(start, len(out)), start)
    return out, first


def speak(question: str, said: list[tuple[str, str]], b: dict, seed: int, turn: int,
          client=None) -> tuple[str, str]:
    """(answer, "model" | "fallback"): up to 4 notes, word for word. No orders, no hours."""
    last = next((text for by, text in reversed(said) if by == "king"), "")
    q = question if _tokens(question) else f"{last} {question}"
    notes, first = _notes(b, q)
    if client is None or not notes:
        return " ".join(notes[:4]).replace(_URGENT, "") or "I do not know.", "fallback"
    field = safe_fields({"notes": "\n".join(f"({n}) {note}" for n, note in enumerate(notes, 1)), "question": q})
    messages = [{"role": "system", "content": _RULES}]
    for sample, ask, pick in _SHOTS:
        messages += [{"role": "user", "content": f"Notes:\n{sample}\n\nQuestion: {ask}"},
                     {"role": "assistant", "content": json.dumps({"notes": pick})}]
    messages.append({"role": "user", "content": f"Notes:\n{field['notes']}\n\nQuestion: {field['question']}"})
    try:
        picked = {n - 1 for n in json.loads(client.call("ask", messages, _SCHEMA, seed, 40, 30, turn, repeat=1.0))["notes"]
                  if 1 <= n <= len(notes)}
        chosen = sorted(picked | {first[n] for n in picked if n in first})[:4]
        return " ".join(notes[n] for n in chosen).replace(_URGENT, "") or "I do not know.", "model"
    except Exception:
        return " ".join(notes[:4]).replace(_URGENT, ""), "fallback"
