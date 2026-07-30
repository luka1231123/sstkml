"""Role D: the Librarian (spec 8.8).

Given 3 to 12 archive hits -- title, date, and a 200-character snippet -- write
a three-line orienting summary and cite every DocRef.

**It may not assert anything that is not in the snippets, and the player opens
the real document, which is authoritative.** That is the whole contract. The
librarian is a finding aid, not an oracle: it tells the player which tablets are
in front of him and in what order, and the reading is still his to do.

This matters especially when sickness makes the court search old vows. The
keeper may report what priests or tablets claim; he may not infer a privileged
divine verdict that the material simulation does not contain. The prompt is
built only from Belief hits, and the numeric guard runs against the snippets:
the summary may use a figure only if a tablet in front of it used that figure
first.

Cheap, low stakes, and high value. The required lightweight model supplies the
normal collation; the templated list is exact runtime recovery and remains
useful when too few hits need summarizing.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from ai.client import ModelUnavailable, safe_fields
from ai.grader import load_formulae
from ai.numeric_guard import extract_numerals_and_number_words, guard

_CONTENT = Path(__file__).parent.parent / "content"
_PERSONAS = tomllib.loads((_CONTENT / "personas.toml").read_text())

MIN_HITS = 3
MAX_HITS = 12


def _allowed_numbers(hits: list[dict]) -> set[str]:
    """Every figure in the snippets, plus the formulaic ones. A librarian may
    repeat a number off a tablet and may not produce one of his own."""
    allowed = set(load_formulae()["meta"]["formulaic_numbers"])
    for hit in hits:
        allowed.update(extract_numerals_and_number_words(
            " ".join((hit.get("title", ""), hit.get("snippet", ""),
                      hit.get("dated_as", "")))))
    return allowed


def _hit_lines(hits: list[dict]) -> str:
    return "\n".join(
        f"  [{hit['ref']}] {hit.get('title') or hit['kind']}"
        f" ({hit.get('dated_as') or 'undated'}): {hit.get('snippet', '')}"
        for hit in hits)


def build_prompt(query: str, hits: list[dict]) -> list[dict]:
    card = dict(_PERSONAS.get("librarian", {}))
    fields = safe_fields({
        "query": query,
        "count": len(hits),
        "tone": (card.get("tone", "") or
                 "You are the keeper of the tablet house. You are precise, "
                 "unhurried, and you do not speculate.").strip().replace("\n", " "),
    })
    prompt = (
        f"{fields['tone']}\n"
        f"The king has asked the tablet house for: {fields['query']}\n"
        f"You have found {fields['count']} tablets. They are:\n"
        + _hit_lines(hits) + "\n\n"
        "Write exactly three lines orienting him: what kind of thing these are, "
        "how they group, and which he should open first. Cite every reference "
        "in square brackets. State nothing that is not written above -- if the "
        "tablets do not say a thing, you do not know it, and you do not guess. "
        "Do not tell him what any of it means."
    )
    return [
        {"role": "system", "content":
         "You are a Late Bronze Age palace archivist listing tablets you have "
         "physically found. Be terse. Cite every reference. Never infer, never "
         "speculate, never draw a conclusion. /no_think"},
        {"role": "user", "content": prompt},
    ]


def fallback_summary(query: str, hits: list[dict]) -> str:
    """The recovery finding aid: what was found, in archive order.

    Genuinely good enough, because the facts are the content -- which is the
    same reason spec 8.8 says the templated epilogue is good enough.
    """
    if not hits:
        return f"Nothing in the tablet house answers to '{query}'."
    kinds: dict[str, int] = {}
    for hit in hits:
        kinds[hit["kind"]] = kinds.get(hit["kind"], 0) + 1
    shape = ", ".join(f"{count} {kind.replace('_', ' ')}"
                      for kind, count in sorted(kinds.items()))
    lines = [f"The tablet house returns {len(hits)} tablets for '{query}': {shape}.",
             "They are set out oldest first, as they lie in the room."]
    for hit in hits:
        lines.append(
            f"  [{hit['ref']}] {hit.get('dated_as') or 'undated'} — "
            f"{hit.get('title') or hit['kind']}")
    return "\n".join(lines)


def summarize(query: str, hits: list[dict], seed: int, turn: int,
              client=None) -> tuple[str, str]:
    """Return (text, source) where source is 'model' or 'fallback'.

    Below MIN_HITS there is nothing to orient anyone through and the list is
    the better answer; above MAX_HITS the spec's contract does not hold, so the
    list is truncated before the prompt is built rather than after.
    """
    hits = list(hits[:MAX_HITS])
    if client is None or len(hits) < MIN_HITS:
        return fallback_summary(query, hits), "fallback"
    allowed = _allowed_numbers(hits)
    refs = {hit["ref"] for hit in hits}
    try:
        messages = build_prompt(query, hits)
        for attempt in range(2):
            text = client.call("librarian", messages, None, seed, 300, 30, turn)
            ok, stray = guard(text, allowed)
            # A citation the archive does not contain is the one failure mode
            # that would actively mislead: the player would go looking for a
            # tablet that is not there and conclude it was lost.
            cited = {token.strip("[]") for token in text.split()
                     if token.startswith("[") and token.endswith("]")}
            invented = sorted(cited - refs)
            if ok and not invented and text.strip():
                return text.strip(), "model"
            flag = getattr(client, "flag_last", None)
            if flag is not None:
                flag("librarian", guard_fail=True)
            if attempt == 0:
                complaint = []
                if stray:
                    complaint.append("numbers not on any tablet: "
                                     + ", ".join(stray))
                if invented:
                    complaint.append("references that do not exist: "
                                     + ", ".join(invented))
                messages = messages + [
                    {"role": "user",
                     "content": "Rewrite using only what is written above. "
                                + "; ".join(complaint)}]
    except ModelUnavailable:
        pass
    except Exception:
        # Same reasoning as the Voicer: a finding aid always has a correct
        # offline answer, so no failure here is worth interrupting a turn for.
        pass
    return fallback_summary(query, hits), "fallback"
