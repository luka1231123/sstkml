"""Natural language -> current closed Action vocabulary (spec 8.3)."""
from __future__ import annotations

import dataclasses
import json
import re

from ai.numeric_guard import extract_numerals_and_number_words, guard
from engine import actions as A

VERBS = {
    "READ_FULL", "ALLOCATE", "SET_PRIORITY", "DICTATE",
    "INSPECT_LEDGER", "EAT_SEED", "SEND_GIFT", "END_TURN",
}
_ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
          "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx")
SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"enum": ["actions", "clarify"]},
        "actions": {"type": "array", "maxItems": 4, "items": {
            "type": "object", "properties": {
                "verb": {"enum": sorted(VERBS)}, "args": {"type": "object"},
            }, "required": ["verb"],
        }},
        "question": {"type": "string", "maxLength": 160},
    },
    "required": ["kind"],
}


@dataclasses.dataclass(frozen=True)
class ParseResult:
    actions: tuple[object, ...] = ()
    question: str | None = None
    source: str = "model"
    unavailable: bool = False


def _letters(belief: dict) -> dict[str, str]:
    return {(_ROMAN[i] if i < len(_ROMAN) else str(i + 1)): item["id"]
            for i, item in enumerate(belief["stack"])}


def _resolve_letter(value: str, belief: dict) -> str | None:
    ids = {item["id"] for item in belief["stack"]}
    return _letters(belief).get(value.lower(), value if value in ids else None)


def preparse(line: str, belief: dict) -> ParseResult | None:
    """Only high-confidence forms belong here; ambiguity goes to the model."""
    text = line.lower().strip().rstrip(".")
    groups = {g["id"] for g in belief["groups"]}
    match = re.fullmatch(r"(?:allocate|give|pay)\s+(\w+)\s+(\d+)(?:\s+qa)?", text)
    if match and match[1] in groups:
        return ParseResult((A.Allocate(match[1], int(match[2])),), source="preparser")
    match = re.fullmatch(r"(?:allocate|give|pay)\s+(\d+)(?:\s+qa)?\s+to\s+(\w+)", text)
    if match and match[2] in groups:
        return ParseResult((A.Allocate(match[2], int(match[1])),), source="preparser")
    match = re.fullmatch(r"(?:read|open)(?:\s+letter)?\s+([\w:.-]+)", text)
    if match and (letter := _resolve_letter(match[1], belief)):
        return ParseResult((A.ReadLetter(letter),), source="preparser")
    match = re.fullmatch(r"(?:inspect|count)(?:\s+the)?\s+(granary|seed)", text)
    if match:
        return ParseResult((A.InspectLedger(match[1]),), source="preparser")
    match = re.fullmatch(r"(?:eat|use)\s+(\d+)(?:\s+qa)?(?:\s+of)?\s+seed(?:\s+grain)?", text)
    if match:
        return ParseResult((A.EatSeed(int(match[1])),), source="preparser")
    match = re.fullmatch(
        r"(?:gift|send)\s+(\w+)\s+(\w+)\s+(\d+)", text)
    if match:
        actors = {r["other"] for r in belief.get("relations", [])}
        goods = {g["id"] for g in belief.get("gift_goods", [])}
        if match[1] in actors and match[2] in goods:
            return ParseResult((
                A.SendGift(match[1], match[2], int(match[3])),),
                source="preparser")
    match = re.fullmatch(
        r"send\s+(\d+)\s+(\w+)\s+to\s+(\w+)", text)
    if match:
        actors = {r["other"] for r in belief.get("relations", [])}
        goods = {g["id"] for g in belief.get("gift_goods", [])}
        if match[3] in actors and match[2] in goods:
            return ParseResult((
                A.SendGift(match[3], match[2], int(match[1])),),
                source="preparser")
    match = re.fullmatch(r"(?:reply|answer)(?:\s+to)?\s+([\w:.-]+)\s+(.{1,200})", text)
    if match and (letter := _resolve_letter(match[1], belief)):
        return ParseResult((A.DictateReply(letter, match[2]),), source="preparser")
    if text in {"end", "end turn", "finish", "finish turn"}:
        return ParseResult((A.EndTurn(),), source="preparser")
    return None


def _affordances(belief: dict, hours_left: int) -> str:
    letters = ", ".join(f"{roman}={lid}" for roman, lid in _letters(belief).items()) or "none"
    groups = ", ".join(g["id"] for g in belief["groups"])
    actors = ", ".join(r["other"] for r in belief.get("relations", []))
    goods = ", ".join(g["id"] for g in belief.get("gift_goods", []))
    return (
        f"Hours left: {hours_left}\n"
        f"Letters (use exact id): {letters}\nGroups: {groups}\n"
        f"Correspondents: {actors}\nGift goods: {goods}\n"
        "Ledgers: granary, seed\nReply intent: free text, at most 200 characters\n"
        "Legal verbs: " + ", ".join(sorted(VERBS))
    )


def _action(item: dict, belief: dict):
    verb, args = item.get("verb"), item.get("args", {})
    if verb not in VERBS or not isinstance(args, dict):
        raise ValueError("unknown action")
    groups = {g["id"] for g in belief["groups"]}
    if verb == "READ_FULL":
        letter = _resolve_letter(args.get("item", ""), belief)
        if not letter:
            raise ValueError("unknown letter")
        return A.ReadLetter(letter)
    if verb == "ALLOCATE":
        group, qa = args.get("group"), args.get("qa")
        if group not in groups or type(qa) is not int:
            raise ValueError("invalid allocation")
        return A.Allocate(group, qa)
    if verb == "SET_PRIORITY":
        order = args.get("order")
        if not isinstance(order, list) or any(group not in groups for group in order):
            raise ValueError("invalid priority")
        return A.SetPriority(tuple(order))
    if verb == "DICTATE":
        letter = _resolve_letter(args.get("item", ""), belief)
        intent = args.get("intent")
        if not letter or not isinstance(intent, str) or not intent.strip() or len(intent) > 200:
            raise ValueError("invalid reply")
        return A.DictateReply(letter, intent.strip())
    if verb == "INSPECT_LEDGER" and args.get("ledger") in {"granary", "seed"}:
        return A.InspectLedger(args["ledger"])
    if verb == "EAT_SEED" and type(args.get("qa")) is int:
        return A.EatSeed(args["qa"])
    if verb == "SEND_GIFT":
        recipient = args.get("recipient")
        good, quantity = args.get("good"), args.get("quantity")
        actors = {r["other"] for r in belief.get("relations", [])}
        goods = {g["id"] for g in belief.get("gift_goods", [])}
        if (recipient not in actors or good not in goods
                or type(quantity) is not int):
            raise ValueError("invalid gift")
        return A.SendGift(recipient, good, quantity)
    if verb == "END_TURN":
        return A.EndTurn()
    raise ValueError("invalid arguments")


def parse(line: str, belief: dict, hours_left: int, seed: int, turn: int,
          client=None) -> ParseResult:
    quick = preparse(line, belief)
    if quick:
        return quick
    if client is None:
        return ParseResult(unavailable=True)
    messages = [
        {"role": "system", "content":
         "Convert the player's request to JSON only. Use only listed verbs and IDs. "
         "If ambiguous, return {\"kind\":\"clarify\",\"question\":\"...\"}. /no_think"},
        {"role": "user", "content": _affordances(belief, hours_left) + "\nPLAYER: " + line},
    ]
    try:
        raw = client.call("parser", messages, SCHEMA, seed, 80, 8, turn)
        allowed = set(extract_numerals_and_number_words(
            " ".join(message["content"] for message in messages)))
        if not guard(raw, allowed)[0]:
            raise ValueError("model invented a number")
        data = json.loads(raw)
        if data.get("kind") == "clarify":
            question = data.get("question")
            if not isinstance(question, str) or not question.strip():
                raise ValueError("empty clarification")
            return ParseResult(question=question[:160])
        items = data.get("actions")
        if data.get("kind") != "actions" or not isinstance(items, list) or not 1 <= len(items) <= 4:
            raise ValueError("invalid action list")
        return ParseResult(tuple(_action(item, belief) for item in items))
    except Exception as exc:
        # Transport failure is distinct: it should not charge an hour.
        from ai.client import ModelUnavailable
        if isinstance(exc, ModelUnavailable):
            return ParseResult(unavailable=True)
        return ParseResult(question="My lord, would you say that another way?")


def action_cost(action) -> int:
    if isinstance(action, (A.ReadLetter, A.DictateReply)):
        return 2
    if isinstance(action, A.InspectLedger):
        return 1
    if isinstance(action, A.SendGift):
        return 1
    return 0
