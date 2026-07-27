"""The desk: where the king writes (M11, D34).

The one window kind worth bespoke work, because writing is half the game. It is
also the only window in which the player types, and everything about it is built
around one loop: **type a line, watch the forms fail, fix it.**

The protocol column on the right is live. It is not advice and it is not a
warning (D19) — it is a checklist of forms the recipient's court expects, ticked
or not ticked, exactly as the scribe standing over the tablet would see them.
Nothing here says the letter is a mistake, or that the recipient will be angry,
or what to write instead. It says `✗ prostration` and lets the king decide
whether a great king is worth grovelling to today.

Two ways to fill the tablet:

* **the formulary** — the scribe's own draft, correct and dead. Free, instant,
  and it will never say anything the king actually means.
* **dictation** — the king's own words, typed. It can be better than the
  formulary, and it can be very much worse.

`ai/grader.py` grades both by the same rule, and the score is recomputed on
replay from the text rather than stored (D9), which is why what is kept here is
the letter and never the number.
"""
from __future__ import annotations

import textwrap

from ai.composer import Draft, fallback_text, raw_draft
from ai.grader import grade_for, profile_for
from tui import art, render, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

# What the king can mean. Deliberately few and deliberately blunt: an intent is
# a purpose, not a sentence, and the sentence is the player's job.
INTENTS = ("reassure", "refuse", "promise", "warn", "excuse", "request")


def formulary(recipient: str, intent: str, seed: int, turn: int) -> Draft:
    """The scribe's draft. Correct, complete, and says nothing."""
    profile_id = profile_for(recipient)
    text = fallback_text(recipient, intent, profile_id, seed, turn)
    return Draft(text=text, profile=profile_id,
                 score=grade_for(text, profile_id), source="formulary")


def dictated(text: str, recipient: str) -> Draft:
    """The king's own words, graded the moment he stops typing."""
    return raw_draft(text, recipient)


def compose(item: dict, draft: Draft, intent: str, dictating: bool = False,
            cursor: bool = True, house: dict | None = None,
            width: int = 84, height: int = 30) -> Screen:
    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    who = render.actor_name(item["sender"], house)
    style.panel(surface, 0, 0, width, height, title=f"THE DESK — TO {who.upper()}",
                note="[esc] burn it", focus=dictating, drop=False)

    right = width - 26          # where the protocol column begins

    # --- who you are writing to ---------------------------------------------
    art.draw(surface, right + 5, 3, art.face_for(who, item.get("persona", "")),
             lit=C["bone"], mid=C["dim"], dark=C["faint"])
    surface.text(right + 2, 12, who[: 22].center(22), C["clay"], C["ink"])
    surface.text(right + 2, 13, f"forms of {draft.profile}"[: 22],
                 C["ash"], C["ink"])

    for row in range(2, height - 2):
        surface.put(right, row, "│", C["faint"], C["ink"])

    # --- the intent ----------------------------------------------------------
    surface.text(3, 2, "you mean to", C["dim"], C["ink"])
    x = 15
    for name in INTENTS:
        chosen = name == intent
        surface.text(x, 2, name,
                     C["bone"] if chosen else C["ash"],
                     C["lapis"] if chosen else C["ink"])
        x += len(name) + 2
    surface.text(3, 3, "─" * (right - 5), C["faint"], C["ink"])

    # --- the tablet ----------------------------------------------------------
    y = 5
    body = draft.text.split("\n")
    for line in body:
        for wrapped in textwrap.wrap(line, right - 8) or [""]:
            if y >= height - 8:
                break
            surface.text(4, y, wrapped, C["clay"], C["ink"])
            y += 1
    if dictating and cursor and y < height - 8:
        # A block cursor, because a text-mode program had a block cursor.
        surface.put(4 + (len(body[-1]) if body else 0) % (right - 8), y - 1,
                    "█", C["flame"], C["ink"])

    # --- the forms, ticked or not --------------------------------------------
    score = draft.score
    checks = (
        ("address", score.address_ok),
        ("prostration", score.prostration_ok),
        ("self-designation", score.self_designation_ok),
        ("one topic only", score.topic_count <= 1),
    )
    surface.text(right + 2, 15, "THE FORMS", C["bone"], C["ink"])
    surface.text(right + 2, 16, "─" * 22, C["faint"], C["ink"])
    for offset, (name, ok) in enumerate(checks):
        surface.text(right + 2, 17 + offset, "✓" if ok else "✗",
                     C["barley"] if ok else C["blood"], C["ink"])
        surface.text(right + 4, 17 + offset, name,
                     C["clay"] if ok else C["blood"], C["ink"])
    surface.text(right + 2, 22, f"score {score.total} of 1000",
                 C["gold"], C["ink"])
    style.meter(surface, right + 2, 23, 22, score.total * 22 // 1000)
    if score.violations:
        surface.text(right + 2, 25, "Yabninu marks:", C["dim"], C["ink"])
        for offset, violation in enumerate(score.violations[:3]):
            surface.text(right + 2, 26 + offset, violation[:22],
                         C["blood"], C["ink"])

    # --- the keys ------------------------------------------------------------
    foot = height - 6
    surface.text(3, foot, "─" * (right - 5), C["faint"], C["ink"])
    if dictating:
        surface.text(3, foot + 1,
                     "you are dictating. the scribe writes what he hears.",
                     C["flame"], C["ink"])
        style.bar(surface, 2, height - 2, width - 4,
                  " [ctrl-d] done dictating   [backspace] unsay   "
                  "[esc] burn the tablet", fg=C["clay"], bg=C["lapis"])
    else:
        surface.text(3, foot + 1, f"source: {draft.source}", C["ash"], C["ink"])
        style.keycap(surface, 3, foot + 2, "tab", "change what you mean")
        style.keycap(surface, 32, foot + 2, "d", "dictate it yourself")
        style.keycap(surface, 3, foot + 3, "enter", "seal it and send")
        style.keycap(surface, 32, foot + 3, "esc", "burn the clay")
        style.bar(surface, 2, height - 2, width - 4,
                  " a tablet costs two hours, whatever it says",
                  fg=C["clay"], bg=C["lapis"])
    return surface.freeze()
