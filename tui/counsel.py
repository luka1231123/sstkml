"""COUNSEL: the prime minister, asked questions and given ordinary orders.

The palace has two conversational agents with separate authority. The Tutor in
HELP knows controls and the closed command vocabulary: retrieval grounds him in
the current command corpus, so he does not advise on the kingdom. Yabninu knows
the *world*, and everything he says has passed through a person: he answers from
the same Belief the player could read himself, but he answers from **memory**,
and his memory is a fortnight stale and rounds in his own favour.

He advises from what he believes to be so. When he is wrong he is wrong
plausibly: the figure he gives is a real figure from a real ledger, only the
wrong one, or the right one from last fortnight. That is the same lie scribes tell in
`belief/distortion.py` and the diviner tells in M9, and it is the house rule —
**a wrong answer is always a plausible neighbour, never noise.**

**He speaks through a model** (D38, `ai/counsel.py`). What he is wrong about is
settled here, by arithmetic, before any prompt exists — `recall()` hands him a
stale figure or the wrong man's name one time in five — and the model is asked
only to put that into his mouth. So the lie is deterministic and replayable, and
the model cannot invent a different one: the numeric guard rejects any figure he
was not handed. The authored sentences below are runtime recovery when Ollama
hears instead, and nothing marks which of the two the player got.
"""
from __future__ import annotations

import textwrap

from tui import art, render, style
from tui.grid import INDEX, InteractiveScreen, Surface

C = INDEX

ASK_COST = 1        # an hour of the fortnight, every time

# Shortcuts, not the menu. You can type anything; these are the six things a
# king asks most mornings, on a key so he does not have to.
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


def recall(b: dict, topic: str, seed: int, turn: int) -> dict:
    """The figures he has in his head — which are not always the true ones.

    This is where he is wrong, and it is the only place. Everything downstream,
    the model included, is handed these and can do nothing but repeat them.
    """
    right = _reliable(seed, turn, topic)
    if topic == "grain":
        series = b.get("store_history", {}).get("grain", [])
        grain = b["stores"].get("grain", 0)
        stale = series[-2] if len(series) > 1 else grain
        return {"the granary holds":
                render.fmt_good("grain", grain if right else stale)}
    if topic == "arrears":
        owed = [group for group in b["groups"] if group["arrears_weeks"] >= 1]
        if not owed:
            return {"groups behind on the roll": 0}
        named = max(owed, key=lambda g: g["arrears_weeks"]) if right else owed[0]
        return {"the loudest group": named["name"],
                "fortnights they are unpaid": named["arrears_weeks"],
                "groups behind on the roll": len(owed)}
    if topic == "unanswered":
        waiting = sorted((r for r in b["relations"] if r["unanswered"]),
                         key=lambda r: -r["unanswered"])
        if not waiting:
            return {"men waiting on an answer": 0}
        first = waiting[0] if right else waiting[-1]
        return {"who has written and had nothing back":
                render.actor_name(first["other"], b.get("house")),
                "times he has written": first["unanswered"]}
    if topic == "oaths":
        live = [o for o in b["oaths"] if not o["dissolved"] and not o["lapsed"]]
        lapsed = [o for o in b["oaths"] if o["lapsed"]]
        facts = {"standing oath tablets": len(live)}
        if right:
            facts["tablets that lapsed at the succession"] = len(lapsed)
        return facts
    if topic == "troops":
        troops = b.get("troops", {})
        facts = {f["name"]: f"{f['strength']} men at {f['place']}, {f['task']}"
                 for f in troops.get("formations", [])[:3]}
        summons = troops.get("summons", [])
        if summons and right:
            facts["a summons stands"] = (
                f"{summons[0]['required']} men wanted at "
                f"{summons[0]['place']}, {summons[0]['mustered']} have gone")
        return facts
    if topic == "unrest":
        return {"the town, out of a hundred":
                b["unrest"] if right else max(0, b["unrest"] - 8)}
    return {}


def answer(b: dict, topic: str, seed: int, turn: int) -> str:
    """Grounded recovery content if Yabninu's required local voice fails.

    It keeps the structured facts visible, but the lightweight model is the
    normal human voice of the court.
    """
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


def recommend(b: dict, topic: str) -> str:
    """A concrete fallback opinion when no model is available."""
    if topic == "grain":
        groups = b.get("groups", [])
        if not groups:
            return "There is no roll for me to alter, my lord."
        largest = max(groups, key=lambda group: group["allocated"])
        return (
            f"The granary is falling. I would review the {largest['name']} "
            "first, and keep the field hands supplied while the crop still "
            "depends on them.")
    if topic == "arrears":
        owing = [group for group in b.get("groups", [])
                 if group["arrears_weeks"]]
        if not owing:
            return "Nobody is in arrears. I would leave the allocations standing."
        worst = max(owing, key=lambda group: group["arrears_weeks"])
        due = worst["size"] * worst["entitlement"]
        return (
            f"Pay the {worst['name']} first, my lord. Restore their allocation "
            f"to {due:,} qa; they have waited the longest.")
    if topic == "unanswered":
        unread = [item for item in b.get("stack", []) if not item["read"]]
        if not unread:
            return "The pile is read. I would spend the hour elsewhere."
        oldest = max(unread, key=lambda item: item["age"])
        return (
            f"Read the tablet from {render.actor_name(oldest['sender'], b.get('house'))} "
            "first. Its courier has stood here the longest.")
    if topic == "oaths":
        lapsed = [oath for oath in b.get("oaths", []) if oath["lapsed"]]
        if lapsed:
            return (
                f"Read {lapsed[0]['id'].replace('_', ' ')} and re-swear it if "
                "its bargain still serves you. At present nobody is bound.")
        return "The standing oaths still bind. I would read their clauses before promising more."
    if topic == "troops":
        summons = b.get("troops", {}).get("summons", [])
        formations = b.get("troops", {}).get("formations", [])
        if summons and formations:
            formation = max(formations, key=lambda item: item["strength"])
            return (
                f"I would send {formation['name']} to {summons[0]['place']} "
                "before the herald comes again.")
        return "No summons stands. I would leave each formation at its present work."
    if topic == "unrest":
        if b.get("unrest", 0) >= 45:
            return "Pay the longest arrears and call no new corvée this fortnight."
        return "The town is quiet enough. Do not purchase trouble merely because you can."

    from tui import advice
    matters = advice.concerns(b, 1)
    if matters:
        return matters[0].suggestion
    return "I have no immediate order to urge on you, my lord."


def reading(said, width: int, height: int, pending=None):
    portrait = width >= 80 and height >= 30 and not pending
    left = 21 if portrait else 3
    capacity = max(1, height - (8 if pending else 12))
    lines = []
    if pending:
        for index, text in enumerate(pending, 1):
            lines.extend((line, "bone") for line in textwrap.wrap(
                f"{index}. {text}", width - left - 3))
            lines.append(("", "clay"))
    else:
        for who, what in said:
            label = "you" if who == "king" else "Yabninu"
            lines.extend((line, "clay" if who == "king" else "bone")
                         for line in textwrap.wrap(f"{label}: {what}", width - left - 3))
            lines.append(("", "clay"))
    return left, capacity, lines


def page_count(said, width: int, height: int, pending=None) -> int:
    _, capacity, lines = reading(said, width, height, pending)
    return max(1, (len(lines) + capacity - 1) // capacity)


def compose(b: dict, said: list[tuple[str, str]], hours_left: int,
            typed: str = "", typing: bool = False,
            width: int = 92, height: int = 36,
            suggestions: list[str] | None = None,
            pending: list[str] | None = None, page: int = 0,
            pending_cost: int = 0) -> InteractiveScreen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    style.panel(surface, 0, 0, width, height, title="COUNSEL", drop=False)
    left, capacity, lines = reading(said, width, height, pending)
    if left == 21:
        art.draw(surface, 3, 3, art.SCRIBE, lit=C["bone"], mid=C["dim"], dark=C["faint"])
        surface.text(3, 13, "Yabninu", C["clay"], C["ink"])
        for row in range(3, height - 8):
            surface.put(18, row, "│", C["faint"], C["ink"])
    title = (f"ORDER REVIEW · {pending_cost}h · {hours_left}h left" if pending else
             f"Yabninu · {hours_left}h left · questions cost 1h")
    surface.text(3, 2, title[:width - 6], C["sand"], C["ink"])
    pages = page_count(said, width, height, pending)
    current = max(0, min(page, pages - 1))
    if pending:
        visible = lines[current * capacity:(current + 1) * capacity]
    else:
        end = max(0, len(lines) - current * capacity)
        visible = lines[max(0, end - capacity):end]
    if not lines:
        visible = [("Ask about the records, or draft an order.", "ash")]
    for offset, (line, tone) in enumerate(visible):
        surface.text(left, 4 + offset, line[:width - left - 3], C[tone], C["ink"])
    nav_y = 4 + capacity
    if pages > 1:
        label = (f"[pgup/pgdn] order {current + 1}/{pages}" if pending else
                 f"[pgup/pgdn] history {pages - current}/{pages}")
        surface.text(3, nav_y, label[:width - 6], C["sand"], C["ink"])
        surface.link(3, nav_y, min(len(label), width - 6), 1, "counsel:page")
    if not pending:
        foot = height - 7
        style.bar(surface, 2, foot, width - 4, " YOU SAY OR GIVE AN ORDER · [ctrl-u] clear", fg=C["bone"], bg=C["faint"])
        surface.link(29, foot, 14, 1, "Control-u")
        visible_typed = typed[-(width - 9):]
        style.bar(surface, 3, foot + 1, width - 6, " " + visible_typed, fg=C["bone"], bg=C["faint"])
        surface.put(4 + len(visible_typed), foot + 1, "█", C["flame"], C["faint"])
        surface.link(3, foot + 1, width - 6, 1, "focus")
        for index, suggestion in enumerate((suggestions or [])[:2]):
            style.keycap(surface, 3, foot + 2 + index, f"ctrl-{index + 1}",
                         suggestion[:width - 17], command=f"suggest:{index}")
    else:
        surface.text(3, height - 3, "Read every page; nothing ordered yet.", C["ash"], C["ink"])
    style.footer(surface, [
        style.FooterAction("enter", "confirm" if pending else "tell him"),
        style.FooterAction("esc", "cancel" if pending else "close"),
    ], y=height - 2, x=2, width=width - 4)
    return surface.interactive()
