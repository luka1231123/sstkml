"""Deterministic, data-driven epistolary protocol grader (spec 8.5)."""
from __future__ import annotations

import dataclasses
import re
import tomllib
from pathlib import Path

_CONTENT = Path(__file__).parent.parent / "content"
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]


@dataclasses.dataclass(frozen=True)
class ProtocolScore:
    address_ok: bool
    prostration_ok: bool
    self_designation_ok: bool
    topic_count: int
    violations: tuple[str, ...]
    total: int


def load_formulae(path: str | Path | None = None) -> dict:
    return tomllib.loads(Path(path or _CONTENT / "formulae.toml").read_text())


def formula(data: dict, profile: str) -> dict:
    value: object = data
    for part in profile.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"unknown protocol profile: {profile}")
        value = value[part]
    if not isinstance(value, dict):
        raise KeyError(f"invalid protocol profile: {profile}")
    return value


def profile_for(recipient: str, data: dict | None = None) -> str:
    data = data or load_formulae()
    return data["recipients"].get(recipient, "ugarit.ruler_to_other")


# A wish for the other house takes several forms across the corpus; any of them
# counts as one having been offered.
_WELLBEING_MARKS = (
    "may it be well with",
    "your health",
    "heart be reassured",
)


def _has(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()


def _quotes(text: str) -> bool:
    """Does the tablet repeat the other party's own words back at them?"""
    return '"' in text or "saying:" in text.casefold()


def grade(text: str, profile: dict, weights: dict,
          recipient: str | None = None) -> ProtocolScore:
    if recipient and "{recipient}" in profile["opening"]:
        expected = profile["opening"].format(
            recipient=_ACTORS.get(recipient, recipient))
        address_ok = text.casefold().startswith(expected.casefold())
    else:
        address_ok = bool(re.search(profile["opening_regex"], text, re.I))
    prostration_ok = (not profile.get("prostration_regex")
                      or bool(re.search(profile["prostration_regex"], text, re.I)))
    designation = profile.get("requires_self_designation", "")
    self_ok = not designation or _has(text, designation)

    topics = profile.get("topics", {})
    topic_count = sum(
        any(_has(text, marker) for marker in markers)
        for _, markers in sorted(topics.items())
    ) or 1

    violations: list[str] = []
    penalty = 0
    if not address_ok:
        violations.append("wrong_address")
        penalty += weights["address"]
    if not prostration_ok:
        violations.append("missing_prostration")
        penalty += weights["prostration"]
    if not self_ok:
        violations.append("missing_self_designation")
        penalty += weights["self_designation"]
    for term in profile.get("forbidden_terms", []):
        if _has(text, term):
            violations.append("kinship_overreach" if term.casefold() == "my brother"
                              else f"forbidden_term:{term}")
            penalty += weights["forbidden_term"]
    extra = max(0, topic_count - int(profile.get("max_topics", 1)))
    if extra:
        violations.append("multi_topic")
        penalty += extra * weights["extra_topic"]
    has_excuse = any(_has(text, term) for term in profile.get("excuse_terms", []))
    has_request = any(_has(text, term) for term in profile.get("request_terms", []))
    if profile.get("forbidden_pattern_excuse_and_request") and has_excuse and has_request:
        violations.append("excuse_and_request")
        penalty += weights["excuse_and_request"]
    oath = any(_has(text, term) for term in profile.get("oath_terms", []))
    gods = profile.get("gods_required_if_oath_mentioned", [])
    if oath and any(not _has(text, god) for god in gods):
        violations.append("wrong_oath_gods")
        penalty += weights["oath_gods"]

    # The conventions the corpus documents beyond address and rank: a wish for
    # the other house, a quotation of what is being answered, and a closing.
    # Each is graded only where the register asks for it -- a wellbeing wish
    # sent down to an officer is as wrong as its absence between brothers.
    wellbeing = profile.get("wellbeing", "")
    said_well = any(_has(text, phrase) for phrase in _WELLBEING_MARKS)
    if wellbeing:
        said_well = said_well or _has(text, wellbeing.rstrip("."))
    if profile.get("wellbeing_required") and not said_well:
        violations.append("missing_wellbeing")
        penalty += weights.get("wellbeing", 0)
    if profile.get("wellbeing_forbidden") and said_well:
        violations.append("wellbeing_downward")
        penalty += weights.get("wellbeing", 0)
    if profile.get("closing_required") and not _has(text, "seal"):
        violations.append("missing_closing")
        penalty += weights.get("closing", 0)
    quoting = profile.get("quotation_form", "")
    if quoting and _quotes(text) and not _has(text, quoting.rstrip(":")):
        violations.append("unmarked_quotation")
        penalty += weights.get("quotation", 0)

    return ProtocolScore(
        address_ok, prostration_ok, self_ok, topic_count,
        tuple(violations), max(0, 1000 - penalty),
    )


def grade_for(text: str, profile_id: str, data: dict | None = None,
              recipient: str | None = None) -> ProtocolScore:
    data = data or load_formulae()
    return grade(text, formula(data, profile_id), data["weights"], recipient)
