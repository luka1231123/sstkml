"""Role E: the Counsellor — a person you talk to (M11, D33, D38).

Yabninu is a chat. You type whatever you want and he answers in character, with
the run of everything the king could see for himself. He will advise, argue,
guess, and tell you what he thinks you should do, because that is what a
counsellor is for.

He gets the conversation so far, so you can follow up: "and the chariotry?" is a
question he can answer.

Two things are held back and both are game design, not caution: figures he was
handed stale stay stale (he is wrong about one thing in five, decided in
`tui/counsel.py` before any prompt exists), and the answers to the game's
puzzles are not in his digest — he does not know which oath the gods are angry
about any more than the king does.

With no Ollama running he falls back to authored lines. Nothing tells the player
which he got.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from ai.client import ModelUnavailable, safe_fields

_CONTENT = Path(__file__).parent.parent / "content"
_PERSONAS = tomllib.loads((_CONTENT / "personas.toml").read_text())

TONE = (
    "You are Yabninu, chief scribe of the palace of Ugarit. You have served "
    "two kings and buried one. You are dry, literal, and a little tired. You "
    "say 'my lord' when you are being careful and drop it when you are not."
)


def digest(b: dict, remembered: dict) -> str:
    """Everything he can speak about: the state of the house, as he has it.

    Broad on purpose. A counsellor who can only answer six questions is a menu,
    and the player can already read a menu off the ledgers himself.
    """
    lines = [
        f"the date: {b['date']}, regnal year {b['regnal_year']}",
        f"the sea: {'open' if b['sea_open'] else 'shut for the season'}",
        f"unrest in the town: {b['unrest']} of 100",
        f"the king's standing: {b['legitimacy']} of 1000",
        f"hours in the fortnight: {b['attention']}",
    ]
    stores = ", ".join(f"{good.replace('_', ' ')} {amount:,}"
                       for good, amount in sorted(b["stores"].items()))
    lines.append(f"the stores: {stores}")

    roll = "; ".join(
        f"{group['name']}: {group['size']} heads, allocated "
        f"{group['allocated']:,} qa, {group['arrears_weeks']} fortnights "
        f"unpaid, they are {group['loyalty']}"
        for group in b["groups"])
    lines.append(f"the roll: {roll}")

    troops = b.get("troops", {})
    if troops.get("formations"):
        lines.append("the men: " + "; ".join(
            f"{f['name']} {f['strength']} at {f['place']} ({f['task']})"
            for f in troops["formations"]))
    for summons in troops.get("summons", []):
        lines.append(f"a summons stands: {summons['required']} men wanted at "
                     f"{summons['place']}, {summons['mustered']} have gone, "
                     f"due turn {summons['due_turn']}")

    land = b.get("land") or {}
    if land:
        lines.append(
            f"the land: gauge {land['gauge']}, last threshing floor "
            f"{land['last_harvest']:,}, seed in store {land['seed_in_store']:,},"
            f" seed in the ground {land['seed_in_ground']:,}, hands supplied "
            f"{land['labour_days_this_turn']:,} against "
            f"{land['labour_days_needed']:,} wanted")

    for oath in b["oaths"]:
        state = ("dissolved" if oath["dissolved"] else
                 "LAPSED, nobody is bound" if oath["lapsed"] else "standing")
        clauses = "; ".join(
            f"{clause['kind'].replace('_', ' ')} "
            + ", ".join(f"{key} {value}"
                        for key, value in sorted(clause["args"].items()))
            for clause in oath["clauses"])
        lines.append(f"oath {oath['id']} ({state}): {clauses}")

    waiting = [r for r in b["relations"] if r["unanswered"]]
    if waiting:
        lines.append("unanswered letters: " + "; ".join(
            f"{r['other']} {r['unanswered']} times ({r['esteem']})"
            for r in sorted(waiting, key=lambda r: -r["unanswered"])[:8]))

    unread = [item for item in b["stack"] if not item["read"]]
    if unread:
        lines.append("on the pile unread: " + "; ".join(
            f"{item['sender']} about {item['topic']}" for item in unread[:8]))

    house = b.get("house") or {}
    living = [p for p in house.get("members", []) if p["alive"]]
    if living:
        lines.append("the house: " + "; ".join(
            f"{p['name']} {p['age_years']}, {p['health']}"
            + (f", heir {p['heir_rank']}" if p["heir_rank"] else "")
            for p in living))

    if remembered:
        lines.append("what you had counted yourself: " + "; ".join(
            f"{key} {value}" for key, value in remembered.items()))
    return "\n".join(f"  {line}" for line in lines)


def build_prompt(question: str, said: list[tuple[str, str]],
                 knowledge: str) -> list[dict]:
    card = dict(_PERSONAS.get("scribe", {}))
    fields = safe_fields({
        "question": question,
        "tone": (card.get("tone") or TONE).strip().replace("\n", " "),
    })
    history = "\n".join(
        f"{'The king' if who == 'king' else 'You'}: {what}"
        for who, what in said[-8:])
    prompt = (
        f"{fields['tone']}\n\n"
        "What you know of the house this morning:\n"
        f"{knowledge}\n\n"
        + (f"The conversation so far:\n{history}\n\n" if history else "")
        + f"The king asks: {fields['question']}\n\n"
        "Answer him in two to four sentences, in your own voice. You may "
        "advise him, disagree with him, and say what you would do. Use the "
        "figures above when you have them and say plainly when you do not "
        "know a thing. Never invent a number."
    )
    return [
        {"role": "system", "content":
         "You are a Late Bronze Age palace scribe, speaking to your king in "
         "person. You are a real adviser: you have opinions and you give them. "
         "Be concise, concrete, and never break character. /no_think"},
        {"role": "user", "content": prompt},
    ]


def speak(question: str, said: list[tuple[str, str]], knowledge: str,
          authored: str, seed: int, turn: int, client=None) -> tuple[str, str]:
    """Return `(what he says, 'model' | 'fallback')`."""
    if client is None:
        return authored, "fallback"
    try:
        text = client.call("counsel", build_prompt(question, said, knowledge),
                           None, seed + len(said), 300, 45, turn)
        return (text.strip(), "model") if text.strip() else (authored, "fallback")
    except (ModelUnavailable, Exception):
        return authored, "fallback"
