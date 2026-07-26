"""ASCII rendering of Belief (spec Part 9). Reads only the projected dict.

Plain terminal output for M1 -- Textual arrives when tabs and scrolling earn
their weight (M2+). Numbers show in display units with a remainder, the way the
tablets do it. No colour dependency; glyphs and words carry the meaning.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

_CONTENT = Path(__file__).parent.parent / "content"
_LETTERS = tomllib.loads((_CONTENT / "corpus" / "letters.toml").read_text())
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]


def actor_name(actor: str) -> str:
    return _ACTORS.get(actor, actor)


def letter_summary(topic: str) -> str:
    return _LETTERS.get(topic, {}).get("summary", topic)


def letter_body(sender: str, topic: str, facts: dict) -> str:
    tpl = _LETTERS.get(topic, {}).get("template")
    if tpl is None:
        return f"(a letter from {actor_name(sender)} concerning {topic})"
    fields = dict(facts)
    fields.setdefault("sender", actor_name(sender))
    try:
        return tpl.format(**fields)
    except KeyError:
        return tpl        # missing fact placeholder: show the raw template


# Display units (spec 6.2). Promoted to content/goods.toml when metals land (M8).
_DISPLAY = {
    "grain": ("parisu", 60), "seed_grain": ("parisu", 60),
    "copper": ("talent", 3600), "tin": ("talent", 3600), "bronze": ("talent", 3600),
    "oil": ("jar", 12), "wine": ("jar", 12),
}


def fmt_good(good: str, qa: int) -> str:
    unit = _DISPLAY.get(good)
    if unit is None:
        return f"{qa:,}"
    name, per = unit
    return f"{qa // per:,} {name} {qa % per} qa" if per > 1 else f"{qa:,}"


def _bar(value: int, total: int, width: int = 10) -> str:
    filled = 0 if total <= 0 else min(width, value * width // total)
    return "▓" * filled + "░" * (width - filled)


_ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
          "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx")


def _num(i: int) -> str:
    return _ROMAN[i] if i < len(_ROMAN) else str(i + 1)


def header(b: dict) -> str:
    title = f"{b['actor'].upper()} OF {b['scenario'].upper()}"
    sea = "OPEN" if b["sea_open"] else "SHUT"
    return (f"  {title} · {b['date']} · sea: {sea}\n"
            f"  audience  {_bar(b['attention'], b['attention_base'])}  "
            f"{b['attention']} / {b['attention_base']}     "
            f"unrest {b['unrest']}   legitimacy {b['legitimacy']}")


def stack_screen(b: dict) -> str:
    """The Stack: the morning's pile, as it stands (spec 9.1)."""
    stack = b["stack"]
    unread = sum(1 for it in stack if not it["read"])
    lines = [f"  THE STACK — {len(stack)} on the pile, {unread} unread", ""]
    if not stack:
        lines.append("    (nothing has come. the harbour is quiet.)")
    for i, it in enumerate(stack):
        dim = " " if not it["read"] else "·"
        label = f"{_num(i)}."
        lines.append(f"  {it['freshness']} {label:<5}{actor_name(it['sender']):<34}"
                     f"{letter_summary(it['topic'])[:34]:<34} {dim}")
    return "\n".join(lines)


def searchable_text(it: dict) -> str:
    body = letter_body(it["sender"], it["topic"], it["facts"])
    return f"{actor_name(it['sender'])} {letter_summary(it['topic'])} {body}".lower()


def archive_screen(b: dict, matches: list | None = None) -> str:
    """Every document received, by received turn only -- it cannot sort by the
    senders' own dates, which share no epoch (spec 6.17)."""
    items = b["archive"] if matches is None else matches
    lines = ["  THE ARCHIVE — sorted by the turn it reached your hand", ""]
    if matches is not None:
        lines[0] = f"  THE ARCHIVE — {len(items)} document(s) found"
    if not items:
        lines.append("    (nothing found.)")
    for it in items:
        r = "read" if it["read"] else "    "
        lines.append(f"  {it['freshness']} [turn {it['received_turn']:>3}] {r}  "
                     f"{actor_name(it['sender']):<32}{letter_summary(it['topic'])[:28]:<28} {it['id']}")
    lines.append("\n  open one with:  read <id>        search with:  search <word>")
    return "\n".join(lines)


def letter_full(it: dict) -> str:
    who = actor_name(it["sender"])
    return (f"  ── {who} ──\n\n  "
            + letter_body(it["sender"], it["topic"], it["facts"]).replace("\n", "\n  ")
            + "\n")


def lists_screen(b: dict) -> str:
    """The payroll. The most important screen in the game (spec 9.3)."""
    lines = ["  RATION LISTS, in the order they are paid", ""]
    lines.append(f"    {'group':<28}{'heads':>6}{'ration':>7}{'allocated':>11}"
                 f"{'owed wk':>9}  loyalty")
    by_id = {g["id"]: g for g in b["groups"]}
    order = b["priority"] + [g["id"] for g in b["groups"] if g["id"] not in b["priority"]]
    for gid in order:
        g = by_id[gid]
        weeks = g["arrears_weeks"]
        mark = " " if weeks == 0 else ("!" if weeks < 4 else "#")
        lines.append(f"  {mark} {g['name']:<28}{g['size']:>6}{g['entitlement']:>7}"
                     f"{g['allocated']:>11}{weeks:>9}  {g['loyalty']}")
    return "\n".join(lines)


def stores_screen(b: dict) -> str:
    lines = ["  STORES", ""]
    for good in b["stores"]:
        lines.append(f"    {good:<14}{fmt_good(good, b['stores'][good]):>28}")
    return "\n".join(lines)


def events_lines(events, court) -> list[str]:
    """Diegetic footer lines for what the turn's advance surfaced."""
    from engine import actions as A
    out = []
    arrivals = [e for e in events if isinstance(e, A.LetterArrived)]
    if arrivals:
        senders = ", ".join(sorted({actor_name(e.sender) for e in arrivals}))
        out.append(f"  A courier has come. On the pile now: {senders}.")
    for e in events:
        if isinstance(e, A.RiteSkipped):
            out.append(f"  The temple records that the rite '{e.rite_id}' was not kept.")
    return out
