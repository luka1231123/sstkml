"""Local-model composer with deterministic guards and compact recovery drafts."""
from __future__ import annotations

import dataclasses
import re
import tomllib
from collections import Counter
from pathlib import Path

from ai.client import ModelUnavailable
from ai.grader import ProtocolScore, formula, grade_for, load_formulae, profile_for
from ai.numeric_guard import (
    extract_numerals_and_number_words,
    guard,
    normalise,
)

_CONTENT = Path(__file__).parent.parent / "content"
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]
_EXEMPLARS = tomllib.loads(
    (_CONTENT / "corpus" / "outgoing.toml").read_text()
)["letters"]
# The scribe's standing instructions, his per-rank instruction, and the
# rough-to-formatted pairs he is shown. Authored in one file so a prompt change
# is a content change (`content/scribe_prompt.toml`).
_SCRIBE = tomllib.loads((_CONTENT / "scribe_prompt.toml").read_text())
# Letters demonstrating one convention each, by rank direction.
_HISTORICAL = tomllib.loads(
    (_CONTENT / "corpus" / "historical.toml").read_text()
)["letters"]


def historical(direction: str = "") -> tuple[dict, ...]:
    """Exemplars, optionally only those written in one rank direction."""
    return tuple(
        letter for letter in _HISTORICAL
        if not direction or letter.get("direction") == direction)


def scribe_messages(recipient: str, matter: str) -> list[dict]:
    """The scribe's prompt for one matter: standing rules, rank, examples.

    Assembled here rather than written inline so that the rules, the register
    and the worked pairs can each be read and tested on their own.
    """
    rule = formula(load_formulae(), profile_for(recipient))
    direction = rule.get("direction", "level")
    system = _SCRIBE["system"]["text"]
    rank = _SCRIBE.get("rank", {}).get(direction, {}).get("text", "")
    if rank:
        system = f"{system}\n\n{rank}"
    messages = [{"role": "system", "content": system}]
    for pair in _SCRIBE.get("examples", []):
        if pair.get("direction") != direction:
            continue
        messages.append({"role": "user", "content": pair["rough"]})
        messages.append({"role": "assistant", "content": pair["formatted"]})
    recipient_name = _ACTORS.get(recipient, recipient.replace("_", " "))
    messages.append({
        "role": "user",
        "content": (f"Recipient: {recipient_name} ({rule['label']}).\n"
                    f"Matter to put into form:\n{matter}"),
    })
    return messages
_INTENT_MARKERS = {
    # These are semantic hints, not required magic words. Small local models
    # naturally render the same posture several ways ("stand firm in loyalty"
    # is still reassurance), so the gate must recognize a compact family of
    # expressions rather than turn good prose into an apparent service error.
    "reassure": (
        "reassur", "do not fear", "goodwill", "loyal", "at peace",
        "heart is open", "heart remains", "stand firm",
    ),
    "refuse": (
        "cannot", "refus", "shall not", "will not", "not perform",
        "unable",
    ),
    "promise": (
        "i shall", "i promise", "i will", "my seal binds", "shall obey",
    ),
    "warn": ("danger", "enemy", "warn", "watch", "threat"),
    "excuse": ("could not", "delay", "because", "pardon", "obstacle"),
    "request": ("i ask", "request", "send", "i seek", "grant"),
}
_COMMITMENT = re.compile(
    r"\b(?:i|we|my house|ugarit)\s+"
    r"(?:shall|will|promise|swear|pledge|guarantee|undertake)\b",
    re.I,
)
_NAME = re.compile(r"\b[A-Z][A-Za-z'’-]{2,}\b")
_NEGATION = re.compile(
    r"\b(?:not|no|never|cannot|can't|cant|won't|wont|don't|dont|isn't|isnt|"
    r"wasn't|wasnt|couldn't|couldnt|shouldn't|shouldnt|wouldn't|wouldnt|"
    r"without|refus\w*|deny|denies|denied)\b",
    re.I,
)


@dataclasses.dataclass(frozen=True)
class Draft:
    text: str
    profile: str
    score: ProtocolScore
    source: str


@dataclasses.dataclass(frozen=True)
class MatterCorrection:
    """A compact matter clause and whether Yabninu or recovery supplied it."""

    text: str
    source: str


def _intent_key(intent: str) -> str:
    lowered = intent.casefold()
    return next((key for key in _INTENT_MARKERS if key in lowered), "")


def _body(intent: str) -> tuple[str, str]:
    """Return recognition and matter clauses without inventing material facts."""
    forms = {
        "reassure": (
            "Your tablet was heard in my hall.",
            "Let your heart be reassured: goodwill remains between our houses.",
        ),
        "refuse": (
            "Your words were heard in my hall.",
            "What you seek I cannot perform and cannot grant; "
            "let this refusal stand.",
        ),
        "promise": (
            "Your command was heard in my hall.",
            "What was asked I shall perform; my seal binds this answer.",
        ),
        "warn": (
            "Hear the word brought swiftly to my gate.",
            "Danger gathers upon the road; set your watch before it "
            "reaches your walls.",
        ),
        "excuse": (
            "Your words were heard in my hall.",
            "I could not answer at the appointed time; this delay was "
            "not contempt.",
        ),
        "request": (
            "Let this tablet be heard in your hall.",
            "I ask for an answer to the matter already named; send it "
            "beneath your seal.",
        ),
    }
    return next(
        (body for key, body in forms.items() if key == _intent_key(intent)),
        (
            "The words dictated in my hall are set before you.",
            "Hear this matter as Ammurapi has spoken it beneath his seal.",
        ),
    )


def _compact(text: str) -> bool:
    """Model drafts share the same small physical envelope as fallback clay."""
    lines = [line for line in text.splitlines() if line.strip()]
    return 25 <= len(text.split()) <= 90 and 3 <= len(lines) <= 6


def _model_draft_ok(text: str, profile_id: str, recipient: str,
                    intent: str) -> bool:
    """Keep small-model phrasing inside known rank and intent boundaries."""
    if not _compact(text):
        return False
    score = grade_for(text, profile_id, recipient=recipient)
    if not (score.address_ok and score.prostration_ok
            and score.self_designation_ok and score.topic_count <= 1):
        return False
    key = _intent_key(intent)
    return not key or any(
        marker in text.casefold() for marker in _INTENT_MARKERS[key])


def fallback_text(recipient: str, intent: str, profile_id: str,
                  seed: int = 0, turn: int = 0) -> str:
    data = load_formulae()
    rule = formula(data, profile_id)
    name = _ACTORS.get(recipient, recipient)
    opening = rule["opening"].format(recipient=name)
    lines = [opening]
    prostration = rule.get("prostration", "")
    # A deterministic scribal lapse makes learned raw dictation meaningfully better.
    if prostration and (seed + turn) % 5:
        lines.append(prostration)
    # Between equals the wish for the other house is not decoration; a tablet
    # without it is graded as one that skipped the greeting.
    if rule.get("wellbeing_required") and rule.get("wellbeing"):
        lines.append(rule["wellbeing"])
    lines.extend(_body(intent))
    lines.append("Yabninu wrote it; the palace courier bears the sealed tablet.")
    return "\n".join(lines)


def raw_draft(text: str, recipient: str) -> Draft:
    profile_id = profile_for(recipient)
    return Draft(
        text, profile_id, grade_for(text, profile_id, recipient=recipient), "player")


def split_draft(draft: Draft, recipient: str) -> tuple[Draft, ...]:
    """Split a genuinely multi-topic tablet, repeating its required formulae."""
    if draft.score.topic_count < 2:
        return ()
    rule = formula(load_formulae(), draft.profile)
    body = []
    for line in draft.text.splitlines():
        if not line:
            continue
        if re.search(rule["opening_regex"], line, re.I):
            continue
        if rule.get("prostration_regex") and re.search(
                rule["prostration_regex"], line, re.I):
            continue
        body.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", line)
                    if part.strip())
    if len(body) < 2:
        return ()

    def make(part: list[str]) -> Draft:
        text = "\n".join(value for value in (
            rule["opening"].format(recipient=_ACTORS.get(recipient, recipient)),
            rule.get("prostration", ""), "\n".join(part),
        ) if value)
        return Draft(
            text, draft.profile,
            grade_for(text, draft.profile, recipient=recipient), "split")

    for cut in range(1, len(body)):
        out = (make(body[:cut]), make(body[cut:]))
        if all(part.score.topic_count <= 1 for part in out):
            return out
    return ()


def _mark_last(client, role: str, **flags) -> None:
    flag = getattr(client, "flag_last", None)
    if flag is not None:
        flag(role, **flags)
    else:                                   # a test double with only an ai_log
        log = getattr(client, "ai_log", None)
        if log:
            log[-1].update(flags)


def _mark_guard_fail(client, role: str = "composer") -> None:
    _mark_last(client, role, guard_fail=True)


def _recovery_matter(matter: str) -> str:
    """Keep the player's exact substance while fitting it onto at most two lines.

    Recovery is deliberately mechanical: it may join sentences with semicolons
    but never paraphrases, invents a reason, or changes a number.
    """
    clean = " ".join(str(matter).split())
    parts = [
        part.strip()
        for part in re.findall(r"[^.!?]+(?:[.!?]+|$)", clean)
        if part.strip()
    ]
    if len(parts) <= 2:
        return clean
    first = parts[0].rstrip(".!?") + "."
    rest = "; ".join(part.rstrip(".!?") for part in parts[1:]) + "."
    return f"{first} {rest}"


def _number_multiset(text: str) -> Counter[str]:
    return Counter(
        normalise(value)
        for value in extract_numerals_and_number_words(text)
    )


def _named_terms(text: str) -> set[str]:
    """Return likely names, ignoring ordinary capitalization after a stop."""
    names: set[str] = set()
    for match in _NAME.finditer(text):
        before = text[:match.start()].rstrip()
        if before and before[-1] not in ".!?":
            names.add(match.group(0).casefold())
    return names


def _matter_ok(original: str, corrected: str) -> bool:
    """Apply narrow, deterministic safety checks to a stylistic correction."""
    text = " ".join(corrected.split())
    if not text or len(text.split()) > 60:
        return False
    sentences = [
        part for part in re.findall(r"[^.!?]+(?:[.!?]+|$)", text)
        if part.strip()
    ]
    if not 1 <= len(sentences) <= 2:
        return False
    if _number_multiset(text) != _number_multiset(original):
        return False

    if not _named_terms(text) <= _named_terms(original):
        return False
    if not _COMMITMENT.search(original) and _COMMITMENT.search(text):
        return False
    if bool(_NEGATION.search(original)) != bool(_NEGATION.search(text)):
        return False
    return True


def correct_matter(recipient: str, matter: str, seed: int, turn: int,
                   client=None) -> MatterCorrection:
    """Have Yabninu compact a matter without changing its material meaning.

    The result contains only the corrected matter, never an address or closing.
    Numbers must survive exactly, new named actors/places and new commitments
    are rejected, and the physical envelope is one or two concise sentences.
    """
    recovery = _recovery_matter(matter)
    if client is None:
        return MatterCorrection(recovery, "fallback")

    messages = scribe_messages(recipient, matter)
    limit = int(_SCRIBE["meta"].get("max_words", 140))
    try:
        for attempt in range(int(_SCRIBE["meta"].get("attempts", 2))):
            text = client.call(
                "matter_corrector", messages, None, seed, limit, 20, turn)
            if _matter_ok(matter, text):
                return MatterCorrection(" ".join(text.split()), "model")
            _mark_last(client, "matter_corrector", validation_fail=True)
            if attempt == 0:
                messages.append({
                    "role": "user",
                    "content": (
                        "Try once more. Copy every number and named term "
                        "exactly. Do not add a commitment. Return only one or "
                        "two concise sentences."
                    ),
                })
    except ModelUnavailable:
        pass
    return MatterCorrection(recovery, "fallback")


def compose(recipient: str, intent: str, facts: dict, seed: int, turn: int,
            client=None) -> Draft:
    data = load_formulae()
    profile_id = profile_for(recipient, data)
    rule = formula(data, profile_id)
    allowed = set(data["meta"]["formulaic_numbers"])
    allowed.update(extract_numerals_and_number_words(
        " ".join(str(value) for _, value in sorted(facts.items()))))
    exemplars = [item["text"] for item in _EXEMPLARS if item["profile"] == profile_id][:2]
    opening = rule["opening"].format(recipient=_ACTORS.get(recipient, recipient))
    prompt = (
        f"RECIPIENT: {_ACTORS.get(recipient, recipient)}\n"
        f"RELATION: {rule['label']}\nINTENT: {intent}\n"
        f"REQUIRED OPENING: {opening}\n"
        f"REQUIRED PROSTRATION: {rule.get('prostration', '')}\n"
        f"FACTS YOU MAY CITE: {facts}\n"
        "USE NO OTHER NUMBERS.\nEXEMPLARS:\n" + "\n---\n".join(exemplars)
    )
    messages = [
        {"role": "system", "content":
         "You are Yabninu, scribe of Ammurapi. Write only a compact Bronze Age "
         "tablet of 25 to 90 words in 3 to 6 formulaic lines. Preserve the "
         "stated intent, recipient, and facts exactly; invent no terms. /no_think"},
        {"role": "user", "content": prompt},
    ]
    if client is not None:
        try:
            for attempt in range(2):
                text = client.call("composer", messages, None, seed, 350, 25, turn)
                ok, stray = guard(text, allowed)
                if ok and _model_draft_ok(
                        text, profile_id, recipient, intent):
                    return Draft(
                        text, profile_id,
                        grade_for(text, profile_id, recipient=recipient), "model")
                if not ok:
                    _mark_guard_fail(client)
                else:
                    _mark_last(client, "composer", validation_fail=True)
                if attempt == 0:
                    correction = (
                        "Rewrite in 25 to 90 words and 3 to 6 lines. Keep the "
                        "required opening and prostration exactly, and express "
                        f"only this intent: {intent}."
                        if ok else
                        "Rewrite. Remove these unlicensed numbers: "
                        + ", ".join(stray)
                    )
                    messages.append({"role": "user", "content": correction})
        except ModelUnavailable:
            pass
    text = fallback_text(recipient, intent, profile_id, seed, turn)
    return Draft(
        text, profile_id, grade_for(text, profile_id, recipient=recipient), "fallback")
