"""The foreign court's answer, put into words it did not decide (spec 2.7).

A reply arrives as facts and nothing else: `engine/mail.py` writes the decision
and the terms offered back onto the tablet and leaves `text` empty, because a
court's answer is engine truth and prose is not (`engine/correspondence_policy`).
This module is the language half of that split. It is handed a projected Belief
item -- decision, the terms exactly as the engine wrote them, who wrote and how
he addresses the king -- and asks the model for the courtesies around them.

The guards are therefore stricter than the Voicer's. An ordinary tablet only has
to avoid inventing a figure; an answer must also not invent an ANSWER. So a
refusal that reads as a grant is rejected, a counter that drops the quantity it
offers is rejected, every numeral must have been supplied, and the tablet must
sit inside the ordinary letter budget of 25 to 90 words (spec 3.5).

Nothing here decides anything, and no `World` object is reachable: the item is a
plain dict from `belief/project.py` and every prompt field passes
`ai.client.safe_fields`. When the model fails, `recovery_text` is a plain
formulaic reading of the same facts -- crash recovery, not a second AI-off mode.
Accepted text is stored on the case and projected back as `body`, so replay
reads words rather than asking a model for them again (spec 2.6).
"""
from __future__ import annotations

import textwrap
import tomllib
from pathlib import Path

from ai.client import ModelUnavailable, safe_fields
from ai.grader import load_formulae
from ai.numeric_guard import (
    extract_numerals_and_number_words,
    guard,
    normalise,
)
from ai.voicer import persona

_CONTENT = Path(__file__).parent.parent / "content"
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]
_GOODS = tomllib.loads((_CONTENT / "goods.toml").read_text())

# The three topics `engine/mail.py` puts on a returning tablet. A delay or an
# ignored case writes no tablet at all, which is why silence is projected state
# rather than a letter with sad words in it (`belief/project.py`).
TOPICS = {
    "reply_accept": "accept",
    "reply_refuse": "refuse",
    "reply_counter": "counter",
}

# What the answer is called on a screen and in the recovery reading. Plain and
# administrative: the interface says what happened, the letter says it in person.
WORDS = {
    "accept": "accepted",
    "refuse": "refused",
    "counter": "terms offered back",
}

# Language that would make the tablet say something the court did not decide.
# A model that grants what was refused has invented an obligation, which is
# exactly what spec 2.7 forbids, and no numeric guard would catch it.
_GRANTS = (
    "i grant", "it is granted", "i send", "i shall send", "i will send",
    "is sent", "shall be sent", "will be sent", "i give", "i shall give",
)
_REFUSALS = (
    "cannot", "can not", "i will not", "i shall not", "do not send",
    "refuse", "unable", "nothing", "none", "deny",
)


def is_reply(item: dict) -> bool:
    """Whether this projected tablet is a foreign court's answer."""
    return str(item.get("topic", "")) in TOPICS


def decision_of(item: dict) -> str:
    """The decision as the engine wrote it, or "" while the seal is unbroken.

    The topic alone would give it away, so the decision is read from the facts,
    and Belief withholds the facts of an unread tablet. A king who has not had
    the answer read out to him does not know what it says.
    """
    facts = item.get("facts") or {}
    decision = str(facts.get("decision", ""))
    return decision if decision in WORDS else ""


def terms_of(item: dict) -> list[dict]:
    """The terms offered back, exactly as delivered. Never rounded, never cut."""
    return [dict(term) for term in (item.get("terms") or ())]


def term_phrase(term: dict) -> str:
    """One term as an administrative phrase: quantity, good, and its due turn."""
    parts: list[str] = []
    quantity = int(term.get("quantity", 0) or 0)
    good = str(term.get("good", "") or "")
    if quantity and good:
        unit = _GOODS.get(good, {}).get("unit", "")
        measure = f"{quantity:,} {unit}".strip()
        parts.append(f"{measure} of {good.replace('_', ' ')}")
    elif good:
        parts.append(good.replace("_", " "))
    person = str(term.get("person_id", "") or "")
    if person:
        parts.append(_ACTORS.get(person, person.replace("_", " ")))
    destination = str(term.get("destination", "") or "")
    if destination:
        parts.append("to " + destination.replace("_", " "))
    due = int(term.get("due_turn", 0) or 0)
    if due:
        parts.append(f"by turn {due}")
    kind = str(term.get("kind", "term")).replace("_", " ")
    return f"{kind}: " + ", ".join(parts) if parts else kind


def _figures(item: dict) -> list[str]:
    """Every number the court's answer is allowed to contain."""
    figures: list[str] = []
    for term in terms_of(item):
        for key in ("quantity", "due_turn"):
            value = int(term.get(key, 0) or 0)
            if value:
                figures.append(str(value))
    for value in (item.get("facts") or {}).values():
        if isinstance(value, int) and not isinstance(value, bool):
            figures.append(str(value))
        elif isinstance(value, str):
            figures.extend(extract_numerals_and_number_words(value))
    return figures


def _allowed_numbers(item: dict) -> set[str]:
    """The supplied figures plus the formulae the register requires.

    The same licence the Voicer grants: "seven times and seven times" is a
    prostration, not an assertion about seven of anything (`ai/voicer.py`).
    """
    allowed = set(load_formulae()["meta"]["formulaic_numbers"])
    allowed.update(_figures(item))
    return allowed


def _quantities_kept(text: str, item: dict) -> bool:
    """Every offered quantity must still be on the tablet.

    A counter whose figure has been dropped is worse than no reply: the king
    would read a willing answer and could not see what was actually offered.
    """
    present = {normalise(value)
               for value in extract_numerals_and_number_words(text)}
    return all(
        normalise(str(term["quantity"])) in present
        for term in terms_of(item)
        if int(term.get("quantity", 0) or 0)
    )


def _decision_kept(text: str, decision: str) -> bool:
    """The words must carry the decision the court actually took."""
    lowered = text.casefold()
    granting = any(marker in lowered for marker in _GRANTS)
    refusing = any(marker in lowered for marker in _REFUSALS)
    if decision == "accept":
        return granting and not refusing
    if decision == "refuse":
        return refusing and not granting
    # A counter says no to the figure asked and yes to a figure of its own, so
    # both registers are expected and neither alone is enough.
    return granting and refusing


def _compact(text: str) -> bool:
    """The ordinary letter budget (spec 3.5), in words and in lines of clay."""
    lines = [line for line in text.splitlines() if line.strip()]
    return 25 <= len(text.split()) <= 90 and 1 <= len(lines) <= 8


def reply_ok(text: str, item: dict, decision: str) -> bool:
    """Whether this wording may be accepted as the court's answer."""
    if not text.strip() or not _compact(text):
        return False
    ok, _stray = guard(text, _allowed_numbers(item))
    return (ok and _quantities_kept(text, item)
            and _decision_kept(text, decision))


def build_prompt(item: dict, decision: str) -> list[dict]:
    """Assemble the reply prompt from a Belief item. Raises rather than leaks."""
    sender = str(item.get("sender", ""))
    card = persona(item.get("persona") or sender)
    terms = terms_of(item)
    fields = safe_fields({
        "who": card["who"].strip().replace("\n", " "),
        "temper": card["temper"],
        "tone": card["tone"].strip().replace("\n", " "),
        "address": card["address"],
        "esteem": str(item.get("sender_esteem", "formal")),
        "decision": {
            "accept": "You agree to what he asked, exactly as he asked it.",
            "refuse": "You decline what he asked. You offer nothing instead.",
            "counter": (
                "You decline the amount he asked and offer these terms "
                "instead, and no others."),
        }[decision],
        "terms": "; ".join(term_phrase(term) for term in terms) or "none",
    })
    prompt = (
        f"YOU ARE {_ACTORS.get(sender, sender)}. {fields['who']}\n"
        f"TEMPER: {fields['temper']}\n"
        f"TONE: {fields['tone']}\n"
        f"RELATIONS ARE: {fields['esteem']}\n"
        f"YOU ADDRESS HIM AS: {fields['address']}\n"
        "YOU ARE ANSWERING A TABLET HE SENT YOU.\n"
        f"YOUR ANSWER: {fields['decision']}\n"
        f"THE TERMS YOU OFFER: {fields['terms']}\n"
        "WRITE: 25 to 90 words. State the answer plainly and keep every "
        "figure. Output the letter only."
    )
    return [
        {"role": "system", "content":
         "You are answering a Late Bronze Age diplomatic tablet on clay. Write "
         "the letter only -- no title, no commentary, no signature block. Say "
         "the answer you were given and no other answer. Use no number that "
         "was not given to you. Promise nothing further. /no_think"},
        {"role": "user", "content": prompt},
    ]


def recovery_text(item: dict, width: int = 64) -> str:
    """The plain reading when the court's voice cannot be had.

    Formulaic and short, and built from the same facts the model would have
    been given. It exists for a failed service; it is not a mode.
    """
    sender = _ACTORS.get(str(item.get("sender", "")),
                         str(item.get("sender", "a foreign court")))
    decision = decision_of(item)
    if not decision:
        return (f"An answer from {sender}. The seal is unbroken; nothing of "
                "what it says is known yet.")
    said = {
        "accept": "What you asked of me is granted, as your tablet had it.",
        "refuse": "What you asked of me I cannot send, and I send nothing "
                  "in its place.",
        "counter": "What you asked of me I cannot send whole. I offer these "
                   "terms instead, and no others.",
    }[decision]
    lines = [f"To my brother, from {sender}.",
             "Your tablet was read out in my hall.",
             said]
    lines += [term_phrase(term) + "." for term in terms_of(item)]
    lines.append("The scribe of this house wrote it; my courier bears it "
                 "sealed.")
    return "\n".join(
        "\n".join(textwrap.wrap(line, width) or [""]) for line in lines)


def voice_reply(item: dict, seed: int, turn: int,
                client=None) -> tuple[str, str]:
    """Return (text, source) with source 'stored', 'model', or 'fallback'.

    Stored text wins over everything, including a working model: once the court
    has read an answer, those are the words on that tablet forever (spec 2.6).
    Otherwise one regeneration on a rejected wording, then the recovery reading.
    """
    stored = str(item.get("body") or "").strip()
    if stored:
        return stored, "stored"
    decision = decision_of(item)
    if not decision or client is None:
        return recovery_text(item), "fallback"
    messages = build_prompt(item, decision)
    try:
        for attempt in range(2):
            text = client.call("replier", messages, None, seed, 400, 30, turn)
            if reply_ok(text, item, decision):
                return text.strip(), "model"
            flag = getattr(client, "flag_last", None)
            if flag is not None:
                flag("replier", validation_fail=True)
            if attempt == 0:
                messages = messages + [{"role": "user", "content": (
                    "Rewrite in 25 to 90 words. Say plainly that the answer "
                    f"is: {WORDS[decision]}. Repeat every figure you were "
                    "given and add none.")}]
    except ModelUnavailable:
        pass
    except Exception:
        # As broad as the Voicer's catch, and for the same reason: the answer
        # already has a correct plain reading waiting, so no failure of the
        # language layer is worth interrupting a turn for.
        pass
    return recovery_text(item), "fallback"
