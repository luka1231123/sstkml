"""Reject numbers that were not supplied to the model (spec 8.6)."""
from __future__ import annotations

import re

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30, "fortieth": 40,
    "fiftieth": 50, "sixtieth": 60, "seventieth": 70, "eightieth": 80,
    "ninetieth": 90, "hundredth": 100, "thousandth": 1000,
}
_NUMBER_WORDS = set(_ONES) | set(_TENS) | set(_ORDINALS) | {"a", "and", "hundred", "thousand"}
_TOKEN = re.compile(r"\d+(?:[;:]\d+)+|\d{1,3}(?:,\d{3})+|\d+|[a-z]+", re.I)


def _word_value(words: list[str]) -> int:
    total = current = 0
    for word in words:
        if word in ("a", "and"):
            if word == "a" and current == 0:
                current = 1
        elif word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word in _ORDINALS:
            current += _ORDINALS[word]
        elif word == "hundred":
            current = max(1, current) * 100
        elif word == "thousand":
            total += max(1, current) * 1000
            current = 0
    return total + current


def normalise(numeral: str) -> str:
    """Return a decimal value for digits, English number words, or base-60 forms."""
    value = numeral.lower().replace("-", " ").strip()
    if re.fullmatch(r"\d+(?:[;:]\d+)+", value):
        parts = [int(part) for part in re.split(r"[;:]", value)]
        if any(part >= 60 for part in parts[1:]):
            return value
        result = 0
        for part in parts:
            result = result * 60 + part
        return str(result)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", value):
        return str(int(value.replace(",", "")))
    words = value.split()
    if words and all(word in _NUMBER_WORDS for word in words):
        return str(_word_value(words))
    return value


def extract_numerals_and_number_words(text: str) -> list[str]:
    found: list[str] = []
    phrase: list[str] = []
    for match in _TOKEN.finditer(text.replace("-", " ")):
        token = match.group(0).lower()
        if token in _NUMBER_WORDS:
            phrase.append(token)
        else:
            if phrase:
                # "and" and "a" alone are ordinary prose, not numbers.
                if any(word not in ("a", "and") for word in phrase):
                    found.append(" ".join(phrase))
                phrase = []
            if token[0].isdigit():
                found.append(token)
    if phrase and any(word not in ("a", "and") for word in phrase):
        found.append(" ".join(phrase))
    return found


def guard(text: str, allowed: set[str]) -> tuple[bool, list[str]]:
    permitted = {normalise(value) for value in allowed}
    stray = [value for value in extract_numerals_and_number_words(text)
             if normalise(value) not in permitted]
    return not stray, stray
