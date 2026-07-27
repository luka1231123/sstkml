"""COUNSEL: a man in a room, who costs an hour and can be wrong (D33, D36).

The second advisor, and the opposite of HELP in every way that matters. HELP
knows the game and is never wrong because it is a written page. Yabninu knows
the *world*, and everything he says has passed through a person: he answers from
the same Belief the player could read himself, but he answers from **memory**,
and his memory is a fortnight stale and rounds in his own favour.

He is not a hint system. He never says what to do — he says what he believes to
be so, and the player decides. When he is wrong he is wrong plausibly: the
figure he gives is a real figure from a real ledger, only the wrong one, or the
right one from last fortnight. That is the same lie the scribes tell in
`belief/distortion.py` and the diviner tells in M9, and it is the house rule —
**a wrong answer is always a plausible neighbour, never noise.**

Ships with no model, which is the whole reason he is written this way (D33). His
answers are authored sentences filled with figures from Belief, chosen by
arithmetic on the seed. Nothing here calls out.
"""
from __future__ import annotations

import textwrap

from tui import art, render, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

ASK_COST = 1        # an hour of the fortnight, every time

# What may be asked, and by which key. Short, because a list of thirty questions
# is a menu and a menu is not a conversation.
QUESTIONS = (
    ("1", "how do we stand for grain?", "grain"),
    ("2", "who is owed, and how badly?", "arrears"),
    ("3", "who has written and had no answer?", "unanswered"),
    ("4", "what am I bound to?", "oaths"),
    ("5", "where are the men?", "troops"),
    ("6", "what do you make of the town?", "unrest"),
)


def _reliable(seed: int, turn: int, topic: str) -> bool:
    """Whether he has it right this time.

    Deterministic and unexplained: the player is never told which answer was the
    bad one, and there is no tell to learn. The only defence is the ledger, which
    is two keystrokes away and costs nothing — which is precisely the lesson.
    """
    salt = sum(ord(letter) for letter in topic)
    return (seed // 7 + turn * 3 + salt) % 5 != 0


def answer(b: dict, topic: str, seed: int, turn: int) -> str:
    """What Yabninu says. One paragraph, in his own voice, possibly wrong."""
    right = _reliable(seed, turn, topic)

    if topic == "grain":
        grain = b["stores"].get("grain", 0)
        series = b.get("store_history", {}).get("grain", [])
        stale = series[-2] if len(series) > 1 else grain
        shown = grain if right else stale
        return (f"The granary holds {render.fmt_good('grain', shown)}, my lord. "
                "I had it counted, though the counting was not this morning.")

    if topic == "arrears":
        owed = [group for group in b["groups"] if group["arrears_weeks"] >= 1]
        if not owed:
            return ("Nobody is owed, my lord, and that is a thing I have not "
                    "been able to say often.")
        worst = max(owed, key=lambda group: group["arrears_weeks"])
        named = worst if right else owed[0]
        return (f"The {named['name']} are the loudest — {named['arrears_weeks']} "
                f"fortnights unpaid, and there are {len(owed)} groups behind on "
                "the roll altogether. They speak to each other, my lord.")

    if topic == "unanswered":
        waiting = sorted((r for r in b["relations"] if r["unanswered"]),
                         key=lambda r: -r["unanswered"])
        if not waiting:
            return "No man is waiting on your hand, my lord."
        first = waiting[0] if right else waiting[-1]
        return (f"{render.actor_name(first['other'], b.get('house'))} has "
                f"written {first['unanswered']} times and had nothing back. "
                "A silence is read, my lord. It is simply read as an answer "
                "you did not trouble to give.")

    if topic == "oaths":
        live = [oath for oath in b["oaths"]
                if not oath["dissolved"] and not oath["lapsed"]]
        lapsed = [oath for oath in b["oaths"] if oath["lapsed"]]
        if lapsed and right:
            return (f"{len(lapsed)} of your tablets lapsed at the succession, "
                    "my lord — nobody is bound by them, neither you nor him. "
                    "That is a comfort until the day it is not.")
        return (f"You hold {len(live)} standing tablets. I have not read the "
                "clauses since they were sworn; they are in the archive, and "
                "the clauses are where the figures are.")

    if topic == "troops":
        troops = b.get("troops", {})
        formations = troops.get("formations", [])
        summons = troops.get("summons", [])
        where = ", ".join(f"{f['name']} at {f['place']}" for f in formations[:3])
        if summons and right:
            first = summons[0]
            return (f"{where}. And there is a summons standing — {first['required']} "
                    f"men wanted at {first['place']}, of whom {first['mustered']} "
                    "have gone. The herald has not stopped coming.")
        return f"{where}, my lord, and each doing the one thing it was set to do."

    if topic == "unrest":
        unrest = b["unrest"] if right else max(0, b["unrest"] - 8)
        mood = ("quiet" if unrest < 20 else "grumbling" if unrest < 45
                else "sullen" if unrest < 70 else "close to something")
        return (f"The town is {mood}. I put it at {unrest} out of a hundred, "
                "but I am a scribe and not a market, my lord, and the market "
                "would put it higher.")

    return "I do not understand the question, my lord."


def compose(b: dict, said: list[tuple[str, str]], hours_left: int,
            width: int = 80, height: int = 32) -> Screen:
    """The room: his face, what has been said, and what may be asked.

    `said` is the conversation so far — `(who, what)`, oldest first. It is
    session state and not world state: a conversation is not a fact about the
    kingdom, and nothing here is written into the log.
    """
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="COUNSEL", drop=False)

    art.draw(surface, 3, 2, art.SCRIBE, lit=C["bone"], mid=C["dim"],
             dark=C["faint"])
    surface.text(3, 12, "Yabninu", C["clay"], C["ink"])
    surface.text(3, 13, "your scribe", C["ash"], C["ink"])
    surface.text(3, 15, f"{hours_left} hours", C["flame"], C["ink"])
    for row in range(2, height - 9):
        surface.put(18, row, "│", C["faint"], C["ink"])

    left = 21
    room = width - left - 3
    y = 2
    if not said:
        for line in textwrap.wrap(
                "He is standing where he always stands, a little behind the "
                "chair, with a tablet he has not been asked for.", room):
            surface.text(left, y, line, C["ash"], C["ink"])
            y += 1
    for who, what in said:
        if y >= height - 10:
            break
        speaker = "you" if who == "king" else "Yabninu"
        surface.text(left, y, f"{speaker}:",
                     C["flame"] if who == "king" else C["sky"], C["ink"])
        y += 1
        for line in textwrap.wrap(what, room - 2):
            if y >= height - 10:
                break
            surface.text(left + 2, y, line,
                         C["clay"] if who == "king" else C["bone"], C["ink"])
            y += 1
        y += 1

    # --- what may be asked ---------------------------------------------------
    foot = height - 9
    style.bar(surface, 2, foot, width - 4, " YOU MAY ASK", fg=C["bone"],
              bg=C["faint"])
    room = width // 2 - 8
    for offset, (key, text, _topic) in enumerate(QUESTIONS):
        column = 3 if offset % 2 == 0 else width // 2 + 2
        style.keycap(surface, column, foot + 1 + offset // 2, key,
                     text[:room], enabled=hours_left >= ASK_COST)
    surface.text(3, height - 4,
                 "every question costs an hour, and he answers from memory.",
                 C["ash"], C["ink"])
    style.bar(surface, 2, height - 2, width - 4,
              " he is not always right. the ledgers are.",
              fg=C["clay"], bg=C["lapis"])
    return surface.freeze()
