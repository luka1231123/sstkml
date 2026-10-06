"""Role C: the Voicer (spec 8.6, 8.7).

**The engine decides what is said. The model decides how.**

By the time anything here runs, every decision has been made: who wrote, what he
asserts, and -- crucially -- whether each figure is true (`engine/report.py`).
The model receives the already-distorted numbers and is never told they are
distorted. It cannot leak a truth it was never given, and the numeric guard
means it cannot invent one either. That is the whole of Law 1 in two sentences.

Everything here reads Belief dicts. No `World` object is reachable from this
module, and every prompt field passes `ai.client.safe_fields` on the way in.

On scheduling (8.7): thirty letters generated synchronously would cost minutes
of a turn nobody asked to spend. Instead a background worker fills bodies in
Stack order, top item first, capped per turn. Ordinary reports use short authored text so every reported quantity remains
visible. Decision replies can use the local voice, with authored recovery
while it is not ready or a guarded request fails. None of this can affect replay: text
never enters World.
"""
from __future__ import annotations

import threading
import tomllib
from pathlib import Path
from engine.actors import slug

from ai.client import ModelUnavailable, safe_fields
from ai.grader import load_formulae
from ai.numeric_guard import extract_numerals_and_number_words, guard

_CONTENT = Path(__file__).parent.parent / "content"
_PERSONAS = tomllib.loads((_CONTENT / "personas.toml").read_text())
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]
_LETTERS = tomllib.loads((_CONTENT / "corpus" / "letters.toml").read_text())

# Spec 8.7: "Cap generation at 8 bodies per turn. Items past that use templates.
# Nobody will notice, because the interesting items are at the top."
CAP_PER_TURN = 8


def persona(actor: str) -> dict:
    card = dict(_PERSONAS["default"])
    card.update(_PERSONAS.get(slug(actor), {}))
    return card


def _tone_pressure(item: dict) -> str:
    """How the standing tone bends under this particular letter's history.

    The persona is who he is; this is what today has done to him. Silence is the
    engine's loudest instrument -- an unanswered correspondent is the one system
    the player drives entirely by omission -- so it gets the strongest line.
    """
    lines = []
    unanswered = int(item.get("unanswered", 0))
    if unanswered == 1:
        lines.append("You wrote once before and had no reply.")
    elif unanswered == 2:
        lines.append(
            "You have written twice and had no reply. This is your third asking.")
    elif unanswered >= 3:
        lines.append(
            f"You have written {unanswered} times and had no reply. "
            "You are beginning to believe you are being ignored, and you are "
            "close to saying so.")
    esteem = item.get("sender_esteem", "formal")
    lines.append({
        "honoured": "Relations are close. Use the customary greeting.",
        "warm": "Relations are friendly. Keep the request direct.",
        "formal": "Relations are formal. State the matter.",
        "displeased": "You are displeased. State the unmet request.",
        "hostile": "Relations are hostile. Keep the address and state the demand.",
    }.get(esteem, "Relations are formal. State the matter."))
    return "\n".join(lines)


def _allowed_numbers(facts: dict, unanswered: int = 0) -> set[str]:
    """The fact figures, plus the formulaic numbers the register requires --
    the 'seven times and seven times' of the prostration, the 'thousand' of the
    blessings. Without these the guard would reject every correct letter.

    `unanswered` is licensed too, because the prompt states it and a man saying
    'this is my third asking' is doing exactly what he was told to do. It was
    slipping through only because 7 happens to be formulaic.
    """
    allowed = set(load_formulae()["meta"]["formulaic_numbers"])
    allowed.update(extract_numerals_and_number_words(
        " ".join(str(value) for _, value in sorted(facts.items()))))
    if unanswered:
        allowed.add(str(unanswered))
    return allowed


def _fact_lines(item: dict) -> str:
    """Spell each fact out the way spec 8.6's example prompt does. A bare key is
    a trap: handed `men: 10` the model put ten men aboard the ships, when the
    engine meant the garrison he has left to defend the island with."""
    facts = item.get("facts", {})
    if not facts:
        return "  (none -- assert no figures at all)"
    labels = _LETTERS.get(item.get("topic", ""), {}).get("labels", {})
    return "\n".join(f"  {labels.get(key, key)}: {value}"
                     for key, value in sorted(facts.items()))


def court_address(item: dict, text: str) -> str:
    title = item.get("recipient_title", "")
    if title:
        # Address only: a later reference to another court keeps its meaning.
        first, separator, rest = text.partition("\n")
        first = first.replace("king of Ugarit", str(title))
        if item.get("recipient_name"):
            first = first.replace("To Ammurapi", "To " + str(item["recipient_name"]))
        return first + separator + rest
    return text


def build_prompt(item: dict) -> list[dict]:
    """Assemble the Voicer prompt from a Belief stack item. Every field is run
    through `safe_fields`, so this raises rather than leaks."""
    card = persona(item.get("persona") or item["sender"])
    facts = item.get("facts", {})
    fields = safe_fields({
        "who": card["who"].strip().replace("\n", " "),
        "temper": card["temper"],
        "tone": card["tone"].strip().replace("\n", " "),
        "wants": card["wants"],
        "address": card["address"],
        "pressure": _tone_pressure(item),
        "min_lines": int(card["lines"][0]),
        "max_lines": int(card["lines"][1]),
    })
    # The facts are already distorted. To the model they are simply true.
    fact_lines = _fact_lines(item)
    prompt = (
        f"YOU ARE {_ACTORS.get(slug(item['sender']), slug(item['sender']))}. "
        f"{fields['who']}\n"
        f"TEMPER: {fields['temper']}\n"
        f"TONE: {fields['tone']}\n"
        f"{fields['pressure']}\n"
        f"YOU ADDRESS HIM AS: {court_address(item, fields['address'])}\n"
        f"WHAT YOU WANT: {fields['wants']}\n"
        f"WRITE: {fields['min_lines']} to {fields['max_lines']} lines. "
        "Output the letter only.\n"
        "FACTS YOU ASSERT (you may use no numbers other than these):\n"
        + fact_lines
    )
    return [
        {"role": "system", "content":
         "You are writing a Late Bronze Age diplomatic letter on clay. Write "
         "the letter only -- no title, no commentary, no signature block. "
         "Keep it brief. State the report or demand once. Omit filler about fairness, "
         "shared knowledge, or having goods for sale when the offer already says so. Use "
         "no number that was not given to you. Use short direct sentences. "
         "Keep conventional addresses, but add no metaphor, scenic detail, "
         "moral lesson, or repeated plea. State the matter and the request. /no_think"},
        {"role": "user", "content": prompt},
    ]


def fallback_body(item: dict) -> str:
    """The short authored report, or a decision-grounded reply recovery."""
    from ai import replier
    if replier.is_reply(item):
        # A foreign court's answer has no authored template and must not get
        # one: its words are built from the decision the engine wrote.
        return replier.recovery_text(item)
    from tui import render
    facts = dict(item.get("facts", {}))
    if item.get("sender_name"):
        facts["sender"] = item["sender_name"]
    return court_address(item, render.letter_body(item["sender"], item["topic"], facts))


def voice(item: dict, seed: int, turn: int, client=None) -> tuple[str, str]:
    """Return (text, source) where source is 'model' or 'fallback'.

    One regeneration on a guard failure, naming the stray numbers, then the
    recovery template. A model that keeps inventing figures simply stops being
    used for that tablet, and every failure is flagged in `ai_log` so the
    prompts can be tuned against it.

    A foreign court's answer goes to `ai/replier.py` instead. It is voiced from
    a decision rather than from an assertion, and it is guarded against
    inventing an answer as well as against inventing a figure. Dispatching here
    means every caller that already schedules the Stack -- the desktop and the
    command line both -- voices replies without knowing they exist.
    """
    from ai import replier
    if replier.is_reply(item):
        return replier.voice_reply(item, seed, turn, client)
    if client is None:
        return fallback_body(item), "fallback"
    allowed = _allowed_numbers(
        item.get("facts", {}), int(item.get("unanswered", 0)))
    messages = build_prompt(item)
    try:
        for attempt in range(2):
            text = client.call("voicer", messages, None, seed, 400, 30, turn)
            ok, stray = guard(text, allowed)
            if ok and text.strip():
                return text.strip(), "model"
            flag = getattr(client, "flag_last", None)
            if flag is not None:
                flag("voicer", guard_fail=True)
            if attempt == 0:
                messages = messages + [{"role": "user", "content":
                                        "Rewrite. These numbers were not given "
                                        "to you: " + ", ".join(stray)}]
    except ModelUnavailable:
        pass
    except Exception:
        # Broader than the composer's catch, deliberately: a letter body has a
        # correct answer waiting either way, so no failure of the model layer is
        # worth interrupting a turn for. The composer, by contrast, is producing
        # something the player will be graded on and must not fail quietly.
        pass
    return fallback_body(item), "fallback"


class Voicer:
    """Background generation in Stack order (spec 8.7).

    One worker per turn. Calling `schedule` again abandons the previous turn's
    work: the pile has changed, and the top of the new pile matters more than
    the tail of the old one.
    """

    def __init__(self, client=None, seed: int = 0, cap: int = CAP_PER_TURN):
        self.client = client
        self.seed = seed
        self.cap = cap
        self._bodies: dict[str, tuple[str, str]] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._generation = 0
        self.skipped = 0          # items past the cap this turn; see `note`

    def schedule(self, items: list[dict], turn: int) -> None:
        """Begin filling bodies for the Stack, top item first. Returns at once."""
        if self.client is None:
            self.skipped = 0
            return
        # A tablet whose accepted words are already stored is not work: Belief
        # projects them as `body`, and asking a model again would be the one
        # thing spec 2.6 forbids.
        pending = [it for it in items
                   if it.get("read") and it.get("topic") not in _LETTERS
                   and it["id"] not in self._bodies
                   and not str(it.get("body") or "").strip()]
        self.skipped = max(0, len(pending) - self.cap)
        batch = pending[:self.cap]
        if not batch:
            return
        with self._lock:
            self._generation += 1
            generation = self._generation
        self._thread = threading.Thread(
            target=self._work, args=(batch, turn, generation), daemon=True)
        self._thread.start()

    def _work(self, batch: list[dict], turn: int, generation: int) -> None:
        for item in batch:
            with self._lock:
                if generation != self._generation:
                    return                     # a new turn; this pile is stale
            try:
                result = voice(item, self.seed, turn, self.client)
            except Exception:
                # A background thread must never take the game down with it.
                # The template is already the answer for anything that fails.
                continue
            with self._lock:
                if generation == self._generation:
                    self._bodies[item["id"]] = result

    def body(self, item: dict) -> tuple[str, str]:
        """The text to show right now. Never blocks, never spins: if the worker
        has not reached this item, the player reads the template instead.

        Stored words come first and are never regenerated: they are what this
        tablet says (spec 2.6).
        """
        stored = str(item.get("body") or "").strip()
        if stored:
            return stored, "stored"
        if item.get("read") and item.get("topic") in _LETTERS:
            return fallback_body(item), "authored"
        with self._lock:
            ready = self._bodies.get(item["id"])
        if ready is not None:
            return ready
        return fallback_body(item), "fallback"

    def wait(self, timeout: float = 30.0) -> bool:
        """Block until the current batch finishes. For tests only -- the game
        never calls this, because the game never makes the player wait."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def note(self) -> str:
        """A diegetic line for the footer when the pile outran the scribes."""
        if not self.skipped:
            return ""
        return (f"  The scribes have read out only the top of the pile; "
                f"{self.skipped} further tablet(s) wait in summary.")
