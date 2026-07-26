"""Optional model composer with deterministic, graded fallback drafts."""
from __future__ import annotations

import dataclasses
import re
import tomllib
from pathlib import Path

from ai.client import ModelUnavailable
from ai.grader import ProtocolScore, formula, grade_for, load_formulae, profile_for
from ai.numeric_guard import extract_numerals_and_number_words, guard

_CONTENT = Path(__file__).parent.parent / "content"
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]
_EXEMPLARS = tomllib.loads(
    (_CONTENT / "corpus" / "outgoing.toml").read_text()
)["letters"]


@dataclasses.dataclass(frozen=True)
class Draft:
    text: str
    profile: str
    score: ProtocolScore
    source: str


def _body(intent: str) -> str:
    forms = {
        "reassure": "Let your heart be reassured. Your words have reached my house.",
        "refuse": "I cannot grant what you seek. Let this answer stand.",
        "promise": "I shall perform what has been asked of my house.",
        "warn": "Danger stands upon the road. Let this warning reach you in time.",
        "excuse": "An obstacle delayed my house; let this explanation be heard.",
        "request": "I ask that the matter named by my lord receive an answer.",
    }
    lowered = intent.casefold()
    return next((body for key, body in forms.items() if key in lowered),
                "The matter dictated by my lord is set before the recipient.")


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
    lines.extend((
        _body(intent),
        "The words that came to me have been heard.",
        "My scribe has placed them faithfully upon this tablet.",
        "Nothing in the message has been hidden from my sight.",
        "My house remembers the hand from which the message came.",
        "Let this writing make my purpose plain.",
        "The seal of my house stands upon these words.",
        "A courier bears them without addition or omission.",
        "When this tablet is heard, let its answer be known.",
        "Thus I have spoken; thus it is written.",
    ))
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


def _mark_guard_fail(client) -> None:
    log = getattr(client, "ai_log", None)
    if log:
        log[-1]["guard_fail"] = True


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
         "You are Yabninu, scribe of Ammurapi. Write only the tablet, 10 to 18 lines. /no_think"},
        {"role": "user", "content": prompt},
    ]
    if client is not None:
        try:
            for attempt in range(2):
                text = client.call("composer", messages, None, seed, 350, 25, turn)
                ok, stray = guard(text, allowed)
                if ok:
                    return Draft(
                        text, profile_id,
                        grade_for(text, profile_id, recipient=recipient), "model")
                _mark_guard_fail(client)
                if attempt == 0:
                    messages.append({"role": "user", "content":
                                     "Rewrite. Remove these unlicensed numbers: "
                                     + ", ".join(stray)})
        except ModelUnavailable:
            pass
    text = fallback_text(recipient, intent, profile_id, seed, turn)
    return Draft(
        text, profile_id, grade_for(text, profile_id, recipient=recipient), "fallback")
