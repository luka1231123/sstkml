"""Yabninu tells the king the facts in words (docs/PLAN.md, SPEC 2.7).
The model only rewords a draft built from Facts. A failed guard gives the draft."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from ai.client import safe_fields
from ai.numeric_guard import extract_numerals_and_number_words, guard, normalise

_P = tomllib.loads(
    (Path(__file__).parent.parent / "content" / "narrator_prompt.toml").read_text())
_BAD = re.compile(r"\b(?:tapestr\w*|testament|delv\w*|looming|whisper\w*|realm\w*|beacon\w*"
                  r"|amidst|palpabl\w*|weav(?:e|es|ing)|navigat\w*)\b|[*#_`—–]"
                  r"|(?<![a-z])-|-(?![a-z])", re.I)


def _cap(text: str) -> str:
    text = text.strip().rstrip(".")
    return text[:1].upper() + text[1:] + "."


def _stems(text: str) -> set[str]:
    return {re.sub(r"(?:ing|ed|es|s)$", "", w) for w in re.findall(r"[a-z]{4,}", text.lower())}


def _say(f: dict) -> str:
    src = f["source"] or "the court"
    if src[0].islower() and src.split()[0] not in ("the", "a", "an", "your"):
        src = "the " + src
    lead = {"reported": f"{src} reported that ", "rumour": "a rumour says that "}
    return _cap(lead.get(f["sure"], "") + f["say"])


def _can(acts: list[str]) -> str:
    return "You can " + " or ".join(acts[:2]) + "."


def template(facts: list[dict], receipts: list[str]) -> str:
    top = facts[:3]
    out = [_cap("Last fortnight: " + receipts[0])] if receipts else []
    if top and not top[0]["urgency"]:
        out.append("Nothing is urgent.")
    for f in top:
        out.append(_say(f))
        if f["urgency"] and f["why"]:
            out.append(_cap(f["why"][0]))
    acts = [a for f in top if f["urgency"] for a in f["act"]]
    tail = [_can(acts)] if acts else []
    return " ".join(out[:6 - len(tail)] + tail) or "Nothing to report."


def _why_template(f: dict) -> str:
    return " ".join([_say(f), *([_cap("; ".join(f["why"]))] if f["why"] else []),
                     *([_can(f["act"])] if f["act"] else [])])


def _ok(text: str, draft: str, limit: int, also: str) -> bool:
    parts = re.split(r"(?<=[.!?])\s+", text)
    keys = lambda s: set(re.findall(r"\[[^\]]+\]", s))
    nums = lambda s: {normalise(n) for n in extract_numerals_and_number_words(s)}
    told = lambda s: len(re.findall(r"\b(?:reported|says)\b", s))
    return (bool(text) and len(parts) <= limit
            and told(text) >= told(draft)
            and all(len(p.split()) <= 20 for p in parts)
            and not _BAD.search(text)
            and guard(text, set(extract_numerals_and_number_words(draft)))[0]
            and nums(draft) <= nums(text)
            and _stems(text) <= _stems(draft + " " + also)
            and ("rumour" not in draft.lower() or "rumour" in text.lower())
            and keys(draft) <= keys(text))


def _voice(kind: str, draft: str, limit: int, tokens: int, client, seed: int, turn: int) -> str:
    if client is None:
        return ""
    task, role = _P[kind], "narrator_" + kind
    messages = [
        {"role": "system", "content": _P["system"]["text"] + "\n\n" + task["ask"]},
        {"role": "user", "content": task["example_in"]},
        {"role": "assistant", "content": task["example_out"]},
        {"role": "user", "content": safe_fields({"draft": draft})["draft"]},
    ]
    try:
        for _ in range(2):
            text = client.call(role, messages, None, seed, tokens, 30, turn).strip()
            if _ok(text, draft, limit, task["also"]):
                return text
            client.flag_last(role, guard_fail=True)
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": _P["retry"]["text"]}]
    except Exception:
        pass
    return ""


def briefing(facts: list[dict], receipts: list[str], client, *,
             seed: int, turn: int) -> tuple[str, str]:
    draft = template(facts, receipts)
    text = _voice("brief", draft, 6, 220, client, seed, turn) if facts else ""
    return (text, "model") if text else (draft, "fallback")


def why(fact: dict, client, *, seed: int, turn: int) -> tuple[str, str]:
    draft = _why_template(fact)
    text = _voice("why", draft, 3, 120, client, seed, turn)
    return (text, "model") if text else (draft, "fallback")
