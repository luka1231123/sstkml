"""Natural language -> current closed Action vocabulary (spec 8.3)."""
from __future__ import annotations

import dataclasses
import json
import re

import registry
from ai.numeric_guard import extract_numerals_and_number_words, guard
from engine import actions as A

VERBS = {
    "READ_FULL", "ALLOCATE", "SET_PRIORITY", "DICTATE",
    "INSPECT_LEDGER", "EAT_SEED", "SEND_GIFT", "END_TURN",
    "SEND_TO_HARVEST", "RECALL_FROM_HARVEST", "RAISE_CORVEE", "ASSIGN_TROOPS",
    "CONSULT_DIVINER", "MARRY_ABROAD", "SWEAR_OATH",
    "DREDGE_CANAL", "BUILD", "REPAIR", "ABANDON_WORK",
    "SUPPRESS_OMEN", "DEFY_OMEN", "QUARANTINE", "LIFT_QUARANTINE",
    "EXPIATE", "SEARCH_ARCHIVE", "HEAR_PETITION", "RULE_PETITION",
    "SET_LAND_DUE", "SET_HARBOUR_DUE", "PLACE_PERSON", "DISMISS_PERSON",
    "NAME_HEIR",
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


def _normal(value: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip().split()
    while words and words[0] in {"a", "an", "the"}:
        words.pop(0)
    return " ".join(words)


def _resolve_named(value: str, rows: list[dict], id_key: str = "id",
                   name_key: str = "name") -> str | None:
    """Resolve an exact ID or an unambiguous player-facing name."""
    wanted = _normal(value)
    exact: list[str] = []
    partial: list[str] = []
    for row in rows:
        item_id = row[id_key]
        names = {
            _normal(item_id),
            _normal(str(row.get(name_key, ""))),
            _normal(str(row.get(name_key, "")).split(",", 1)[0]),
        }
        if wanted in names:
            exact.append(item_id)
        elif len(wanted) >= 4 and any(
                name.startswith(wanted) or wanted.startswith(name)
                for name in names if name):
            partial.append(item_id)
    matches = list(dict.fromkeys(exact or partial))
    return matches[0] if len(matches) == 1 else None


def _resolve_group(value: str, belief: dict) -> str | None:
    return _resolve_named(value, belief.get("groups", []))


def _resolve_formation(value: str, belief: dict) -> str | None:
    return _resolve_named(
        value, belief.get("troops", {}).get("formations", []))


def _resolve_institution(value: str, belief: dict) -> str | None:
    return _resolve_named(value, belief.get("institutions", []))


def _resolve_plan(value: str, belief: dict) -> str | None:
    return _resolve_named(value, belief.get("plans", []), "kind", "name")


def _resolve_person(value: str, belief: dict) -> str | None:
    rows = [person for person in belief.get("house", {}).get("members", [])
            if person["alive"]]
    return _resolve_named(value, rows)


def _resolve_place(value: str, belief: dict) -> str | None:
    wanted = _normal(value)
    matches = [place for place in _place_ids(belief)
               if _normal(place) == wanted]
    return matches[0] if len(matches) == 1 else None


def preparse(line: str, belief: dict) -> ParseResult | None:
    """Only high-confidence forms belong here; ambiguity goes to the model."""
    text = line.lower().strip().rstrip(".")
    groups = {g["id"] for g in belief["groups"]}
    match = re.fullmatch(
        r"(?:allocate|give|pay)\s+(.+?)\s+(\d+)(?:\s+qa)?", text)
    if match and (group := _resolve_group(match[1], belief)):
        return ParseResult((A.Allocate(group, int(match[2])),),
                           source="preparser")
    match = re.fullmatch(
        r"(?:allocate|give|pay)\s+(\d+)(?:\s+qa)?\s+to\s+(.+)", text)
    if match and (group := _resolve_group(match[2], belief)):
        return ParseResult((A.Allocate(group, int(match[1])),),
                           source="preparser")
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
    match = re.fullmatch(
        r"(?:send|order|put)\s+(.+?)\s+to\s+(?:the\s+)?(?:harvest|fields)",
        text)
    # Some household formations also appear among the social groups.  Prefer
    # the military order below when a name can denote either one.
    if (match and not _resolve_formation(match[1], belief)
            and (group := _resolve_group(match[1], belief))):
        return ParseResult((A.SendToHarvest(group, True),), source="preparser")
    match = re.fullmatch(
        r"(?:recall|return)\s+(.+?)(?:\s+from\s+(?:the\s+)?(?:harvest|fields))?",
        text)
    if match and (group := _resolve_group(match[1], belief)):
        return ParseResult((A.SendToHarvest(group, False),),
                           source="preparser")
    match = re.fullmatch(
        r"(?:assign|send|order|set)\s+(.+?)\s+to\s+"
        r"(garrison|watch|harvest|campaign)"
        r"(?:\s+(?:at|in|to)\s+(.+))?", text)
    formation = _resolve_formation(match[1], belief) if match else None
    place = _resolve_place(match[3], belief) if match and match[3] else ""
    if match and formation and (not match[3] or place):
        return ParseResult(
            (A.AssignTroops(formation, match[2], place or ""),),
            source="preparser")
    match = re.fullmatch(r"(?:raise|levy|call)(?:\s+a)?\s+corvee(?:\s+of)?\s+(\d+)(?:\s+days)?", text)
    if match:
        return ParseResult((A.RaiseCorvee(int(match[1])),), source="preparser")
    match = re.fullmatch(
        r"(?:set\s+)?(?:the\s+)?priority(?:\s+to)?\s+([\w:.-]+(?:\s+[\w:.-]+)*)",
        text)
    if match:
        order = tuple(match[1].split())
        if order and all(group in groups for group in order):
            return ParseResult((A.SetPriority(order),), source="preparser")
    match = re.fullmatch(
        r"(?:dredge|clear)(?:\s+the)?\s+([\w:.-]+)(?:\s+canal)?"
        r"(?:\s+(?:with|for))?\s+(\d+)(?:\s+days)?", text)
    if match and match[1] in _estate_ids(belief):
        return ParseResult(
            (A.DredgeCanal(match[1], int(match[2])),), source="preparser")
    match = re.fullmatch(
        r"(?:build|put\s+up)\s+(.+?)(?:\s+(?:at|in)\s+(.+))?", text)
    plan = _resolve_plan(match[1], belief) if match else None
    place = _resolve_place(match[2], belief) if match and match[2] else (
        belief.get("seat", "seat"))
    if match and plan and place:
        return ParseResult((
            A.BeginBuild(plan, place),),
            source="preparser")
    match = re.fullmatch(
        r"(?:repair|mend)\s+(.+)", text)
    if match and (institution := _resolve_institution(match[1], belief)):
        return ParseResult((A.BeginRepair(institution),), source="preparser")
    match = re.fullmatch(
        r"(?:abandon|stop|call\s+off)(?:\s+work(?:\s+on)?)?\s+([\w:.-]+)",
        text)
    if match and match[1] in _project_ids(belief):
        return ParseResult((A.AbandonWork(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:close|quarantine)(?:\s+the)?(?:\s+routes?(?:\s+to)?)?\s+(.+)",
        text)
    if match and (place := _resolve_place(match[1], belief)):
        return ParseResult((A.Quarantine(place),), source="preparser")
    match = re.fullmatch(
        r"(?:open|reopen|lift\s+quarantine(?:\s+on)?)"
        r"(?:\s+the)?(?:\s+routes?(?:\s+to)?)?\s+(.+)", text)
    if match and (place := _resolve_place(match[1], belief)):
        return ParseResult((A.Quarantine(place, True),), source="preparser")
    match = re.fullmatch(
        r"(?:search|look\s+in)(?:\s+the)?(?:\s+archive|\s+tablet\s+house)?"
        r"(?:\s+for)?\s+(.+)", text)
    if match and match[1].strip():
        return ParseResult(
            (A.SearchArchive(match[1].strip()),), source="preparser")
    match = re.fullmatch(
        r"(?:hear|listen\s+to)(?:\s+the)?(?:\s+case)?\s+([\w:.-]+)", text)
    if match and match[1] in _petition_ids(belief):
        return ParseResult((A.HearPetition(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:rule|judge)(?:\s+the)?(?:\s+case)?\s+([\w:.-]+)"
        r"\s+(for|against|split|defer)", text)
    if match and match[1] in _petition_ids(belief):
        return ParseResult(
            (A.RulePetition(match[1], match[2]),), source="preparser")
    match = re.fullmatch(
        r"(?:set|make|raise|lower)(?:\s+the)?\s+land\s+due(?:\s+to)?\s+(\d+)",
        text)
    if match:
        return ParseResult((A.SetLandDue(int(match[1])),), source="preparser")
    match = re.fullmatch(
        r"(?:set|make|raise|lower)(?:\s+the)?\s+harbou?r\s+due"
        r"(?:\s+to)?\s+(\d+)", text)
    if match:
        return ParseResult((A.SetHarbourDue(int(match[1])),), source="preparser")
    match = re.fullmatch(
        r"(?:appoint|place|send)\s+(.+?)\s+(?:to|as)\s+(.+)",
        text)
    person = _resolve_person(match[1], belief) if match else None
    post = _resolve_post(match[2], belief) if match else None
    if match and person and post:
        return ParseResult(
            (A.PlacePerson(person, post),), source="preparser")
    match = re.fullmatch(
        r"(?:dismiss|remove)(?:\s+the\s+holder\s+of)?\s+([\w:.-]+)", text)
    if match and match[1] in _post_ids(belief):
        return ParseResult((A.DismissPerson(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:name|make)\s+(.+?)(?:\s+the)?\s+heir", text)
    if match and (person := _resolve_person(match[1], belief)):
        return ParseResult((A.NameHeir(person),), source="preparser")
    match = re.fullmatch(
        r"(?:omen|divine|consult)(?:\s+the\s+diviner)?(?:\s+about)?"
        r"(?:\s+the)?\s+(harvest|route)", text)
    if match:
        return ParseResult((A.ConsultDiviner(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:omen|divine|consult)(?:\s+the\s+diviner)?(?:\s+about)?"
        r"\s+(?:the\s+)?death(?:\s+of)?\s+(\w+)", text)
    if match and match[1] in _house_ids(belief):
        return ParseResult((A.ConsultDiviner("death", match[1]),),
                           source="preparser")
    match = re.fullmatch(
        r"(?:swear|re-?swear)(?:\s+the)?(?:\s+oath)?\s+([\w:.-]+)", text)
    if match and match[1] in {o["id"] for o in belief.get("oaths", [])}:
        return ParseResult((A.SwearOath(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:marry|send)\s+(.+?)\s+(?:to|into)"
        r"(?:\s+the)?(?:\s+court\s+of)?\s+([\w:.-]+)", text)
    person = _resolve_person(match[1], belief) if match else None
    if (match and person
            and match[2] in {relation["other"]
                             for relation in belief.get("relations", [])}):
        return ParseResult(
            (A.MarryAbroad(person, match[2]),), source="preparser")
    match = re.fullmatch(
        r"(?:suppress|hush)(?:\s+the)?(?:\s+omen)?\s+([\w:.-]+)", text)
    if match and match[1] in _omen_ids(belief):
        return ParseResult((A.SuppressOmen(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:defy|act\s+against)(?:\s+the)?(?:\s+omen)?\s+([\w:.-]+)", text)
    if match and match[1] in _omen_ids(belief):
        return ParseResult((A.DefyOmen(match[1]),), source="preparser")
    match = re.fullmatch(
        r"(?:expiate|make\s+offering\s+against)(?:\s+the)?(?:\s+oath)?"
        r"\s+([\w:.-]+)(?:\s+(\d+))?", text)
    if match and match[1] in _oath_ids(belief):
        return ParseResult(
            (A.Expiate(match[1], int(match[2] or 0)),), source="preparser")
    if text in {"end", "end turn", "finish", "finish turn"}:
        return ParseResult((A.EndTurn(),), source="preparser")
    return None


def _formation_ids(belief: dict) -> set:
    return {f["id"] for f in belief.get("troops", {}).get("formations", [])}


def _house_ids(belief: dict) -> set:
    return {p["id"] for p in belief.get("house", {}).get("members", [])
            if p["alive"]}


def _estate_ids(belief: dict) -> set:
    return {estate["id"] for estate in belief.get("land", {}).get("estates", [])}


def _plan_ids(belief: dict) -> set:
    return {plan["kind"] for plan in belief.get("plans", [])}


def _institution_ids(belief: dict) -> set:
    return {inst["id"] for inst in belief.get("institutions", [])}


def _project_ids(belief: dict) -> set:
    return {project["id"] for project in belief.get("projects", [])}


def _petition_ids(belief: dict) -> set:
    return {petition["id"] for petition
            in belief.get("justice", {}).get("petitions", [])}


def _omen_ids(belief: dict) -> set:
    return {omen["id"] for omen in belief.get("house", {}).get("omens", [])}


def _oath_ids(belief: dict) -> set:
    return {oath["id"] for oath in belief.get("oaths", [])}


def _place_ids(belief: dict) -> set:
    places = {belief.get("seat", "seat")}
    places.update(relation["place"] for relation in belief.get("relations", []))
    places.update(inst["place"] for inst in belief.get("institutions", []))
    places.update(estate["place"] for estate
                  in belief.get("land", {}).get("estates", []))
    return places


def _post_ids(belief: dict) -> set:
    posts = _institution_ids(belief)
    posts.update(f"governor:{place}" for place in _place_ids(belief))
    posts.update(f"command:{formation}" for formation in _formation_ids(belief))
    posts.update(f"court:{relation['other']}"
                 for relation in belief.get("relations", []))
    return posts


def _resolve_post(value: str, belief: dict) -> str | None:
    if institution := _resolve_institution(value, belief):
        return institution
    wanted = _normal(value).replace(" of ", " ")
    matches = [
        post for post in _post_ids(belief)
        if _normal(post).replace(" of ", " ") == wanted]
    return matches[0] if len(matches) == 1 else None


def _affordances(belief: dict, hours_left: int) -> str:
    letters = ", ".join(f"{roman}={lid}" for roman, lid in _letters(belief).items()) or "none"
    groups = ", ".join(g["id"] for g in belief["groups"])
    actors = ", ".join(r["other"] for r in belief.get("relations", []))
    goods = ", ".join(g["id"] for g in belief.get("gift_goods", []))
    return (
        f"Hours left: {hours_left}\n"
        f"Letters (use exact id): {letters}\nGroups: {groups}\n"
        f"Correspondents: {actors}\nGift goods: {goods}\n"
        f"House (living): {', '.join(sorted(_house_ids(belief))) or 'none'}\n"
        f"Oaths: {', '.join(o['id'] for o in belief.get('oaths', [])) or 'none'}\n"
        f"Formations: {', '.join(sorted(_formation_ids(belief))) or 'none'}\n"
        f"Estates: {', '.join(sorted(_estate_ids(belief))) or 'none'}\n"
        f"Institutions: {', '.join(sorted(_institution_ids(belief))) or 'none'}\n"
        f"Build kinds: {', '.join(sorted(_plan_ids(belief))) or 'none'}\n"
        f"Projects: {', '.join(sorted(_project_ids(belief))) or 'none'}\n"
        f"Places: {', '.join(sorted(_place_ids(belief))) or 'none'}\n"
        f"Petitions: {', '.join(sorted(_petition_ids(belief))) or 'none'}\n"
        f"Omens: {', '.join(sorted(_omen_ids(belief))) or 'none'}\n"
        f"Posts: {', '.join(sorted(_post_ids(belief))) or 'none'}\n"
        "Troop tasks: garrison, watch, harvest, campaign\n"
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
    if verb in ("SEND_TO_HARVEST", "RECALL_FROM_HARVEST"):
        group = args.get("group")
        if group not in groups:
            raise ValueError("unknown group")
        return A.SendToHarvest(group, verb == "SEND_TO_HARVEST")
    if verb == "ASSIGN_TROOPS":
        from engine.troops import TASKS
        formation, task = args.get("formation"), args.get("task")
        if formation not in _formation_ids(belief):
            raise ValueError("unknown formation")
        if task not in TASKS:
            raise ValueError("troops cannot be set to that")
        place = args.get("place", "")
        return A.AssignTroops(formation, task, place if type(place) is str else "")
    if verb == "RAISE_CORVEE" and type(args.get("days")) is int:
        return A.RaiseCorvee(args["days"])
    if verb == "DREDGE_CANAL":
        estate, days = args.get("estate"), args.get("days")
        if estate not in _estate_ids(belief) or type(days) is not int:
            raise ValueError("invalid canal order")
        return A.DredgeCanal(estate, days)
    if verb == "BUILD":
        kind = args.get("kind")
        place = args.get("place", belief.get("seat", "seat"))
        if kind not in _plan_ids(belief) or place not in _place_ids(belief):
            raise ValueError("invalid building order")
        return A.BeginBuild(kind, place)
    if verb == "REPAIR":
        institution = args.get("institution")
        if institution not in _institution_ids(belief):
            raise ValueError("unknown institution")
        return A.BeginRepair(institution)
    if verb == "ABANDON_WORK":
        project = args.get("project")
        if project not in _project_ids(belief):
            raise ValueError("unknown work")
        return A.AbandonWork(project)
    if verb == "CONSULT_DIVINER":
        question = args.get("question")
        if question not in ("harvest", "death", "route"):
            raise ValueError("the diviner does not read that")
        subject = args.get("subject", "")
        if question == "death" and subject not in _house_ids(belief):
            raise ValueError("no such person in the house")
        return A.ConsultDiviner(question, subject if question == "death" else "")
    if verb == "MARRY_ABROAD":
        person, actor = args.get("person"), args.get("actor")
        actors = {r["other"] for r in belief.get("relations", [])}
        if person not in _house_ids(belief) or actor not in actors:
            raise ValueError("invalid marriage")
        return A.MarryAbroad(person, actor)
    if verb == "SWEAR_OATH":
        oath = args.get("oath")
        if oath not in _oath_ids(belief):
            raise ValueError("no such oath")
        return A.SwearOath(oath)
    if verb in ("SUPPRESS_OMEN", "DEFY_OMEN"):
        omen = args.get("omen")
        if omen not in _omen_ids(belief):
            raise ValueError("no such omen")
        return A.SuppressOmen(omen) if verb == "SUPPRESS_OMEN" else A.DefyOmen(omen)
    if verb in ("QUARANTINE", "LIFT_QUARANTINE"):
        place = args.get("place")
        if place not in _place_ids(belief):
            raise ValueError("no such place")
        return A.Quarantine(place, verb == "LIFT_QUARANTINE")
    if verb == "EXPIATE":
        oath, offering = args.get("oath"), args.get("offering", 0)
        if oath not in _oath_ids(belief) or type(offering) is not int:
            raise ValueError("invalid expiation")
        return A.Expiate(oath, offering)
    if verb == "SEARCH_ARCHIVE":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("empty archive search")
        return A.SearchArchive(query.strip())
    if verb == "HEAR_PETITION":
        petition = args.get("petition")
        if petition not in _petition_ids(belief):
            raise ValueError("no such petition")
        return A.HearPetition(petition)
    if verb == "RULE_PETITION":
        petition, verdict = args.get("petition"), args.get("verdict")
        if petition not in _petition_ids(belief) or verdict not in {
                "for", "against", "split", "defer"}:
            raise ValueError("invalid judgement")
        return A.RulePetition(petition, verdict)
    if verb in ("SET_LAND_DUE", "SET_HARBOUR_DUE"):
        rate = args.get("rate")
        if type(rate) is not int or not 0 <= rate <= 1000:
            raise ValueError("invalid due")
        return A.SetLandDue(rate) if verb == "SET_LAND_DUE" else A.SetHarbourDue(rate)
    if verb == "PLACE_PERSON":
        person, post = args.get("person"), args.get("post")
        if person not in _house_ids(belief) or post not in _post_ids(belief):
            raise ValueError("invalid appointment")
        return A.PlacePerson(person, post)
    if verb == "DISMISS_PERSON":
        post = args.get("post")
        if post not in _post_ids(belief):
            raise ValueError("invalid post")
        return A.DismissPerson(post)
    if verb == "NAME_HEIR":
        person = args.get("person")
        if person not in _house_ids(belief):
            raise ValueError("no such living person")
        return A.NameHeir(person)
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
    """What the typed path charges -- which is what every path charges.

    This used to be a second cost table, and it had already drifted: it had no
    branch for `DelegateLetter`, so delegating through Counsel was free while
    delegating through the Inbox cost an hour. The registry is now the single
    statement of cost (UI/UX spec 19, 21), and this function is a lookup so the
    two cannot disagree again.
    """
    return registry.cost_of(action)
