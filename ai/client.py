"""Small, optional Ollama transport. Nothing here is required for command mode."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "qwen3:14b"
OLLAMA = "http://127.0.0.1:11434/api/chat"


class ModelUnavailable(RuntimeError):
    pass


# --- the prompt boundary (spec 8.9) ------------------------------------------
# "Make the boundary a type, not a convention." A prompt is built from a flat
# mapping of pre-approved primitives, and this function is the only door.

class PromptLeak(AssertionError):
    """Something that must never reach the model was put in a prompt."""


# Named in spec 8.9. These are the keys whose values decide outcomes the ruler
# is supposed to have to *find out*; a model that has seen one can leak it in a
# sentence no guard would catch, because it is prose, not a number.
FORBIDDEN_KEYS = frozenset({
    "liability", "collapse", "collapse_index", "cause_oath_id",
    "climate", "climate_series", "coalition", "knowledge",
    "raid_weights", "raid_targeting", "report_bias", "true_facts",
    "accuracy", "divination_accuracy", "seed", "rng_ledger",
    # M8. The climate series is the future; `replacement_rate` and
    # `standing_yield` are consequences the player is supposed to have to
    # notice for himself, and a model that has seen either can hint at it in a
    # sentence no numeric guard would catch.
    "climate_series", "drought_curve", "replacement_rate", "equipment_floor",
    "standing_yield", "base_yield_per_iku",
    # M9. Divination accuracy is named in spec 8.9 outright. Fertility and the
    # mortality roll are the future of named people, and a model that has seen
    # either can foreshadow a death the player was supposed to be surprised by.
    "divination_accuracy", "diviner_competence", "diviner_loyalty",
    "diviner_bias", "fertility", "mortality_by_age", "will_die_on",
    "pregnant_until", "true_answer",
    # M10. `cause_oath_id` is named in spec 8.9 outright and is the answer to
    # the entire archive puzzle -- a librarian that has seen it will nudge, and
    # a nudged puzzle is no puzzle. The compartment counts go with it: nobody at
    # court has an infection count, so a correspondent who quotes one is
    # speaking from outside the world.
    "cause_oath_id", "expiated_correctly_turn", "beta", "gamma", "mortality",
    "exposure", "susceptible", "infected", "recovered", "plague_load",
})


def safe_fields(fields) -> dict[str, str | int]:
    """Return the mapping, or raise. Values must be primitives: the point is
    that no `World` object is reachable from anything a prompt is built out of,
    which is enforced here rather than trusted to every call site."""
    out: dict[str, str | int] = {}
    for key, value in fields.items():
        if not isinstance(key, str):
            raise PromptLeak(f"prompt field key is not a string: {key!r}")
        if key.casefold() in FORBIDDEN_KEYS:
            raise PromptLeak(f"forbidden field in prompt: {key!r}")
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise PromptLeak(
                f"prompt field {key!r} is {type(value).__name__}, "
                "not str or int")
        out[key] = value
    return out


class OllamaClient:
    def __init__(self, ai_log: list[dict] | None = None,
                 cache_dir: str | Path | None = None):
        self.ai_log = ai_log if ai_log is not None else []
        self.cache: dict[str, str] = {}
        self.cache_dir = Path(cache_dir) if cache_dir else None
        # The Voicer generates letter bodies on a background thread (spec 8.7),
        # so cache and log are touched from two threads. Neither feeds replay --
        # a save replays from the action log alone -- but they must not tear.
        self._lock = threading.Lock()

    def call(self, role: str, messages: list[dict], schema: dict | None,
             seed: int, max_tokens: int, timeout_s: float, turn: int = 0) -> str:
        model = os.environ.get("STTKML_MODEL", MODEL)
        prompt = json.dumps(messages, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(f"{role}|{model}|{prompt}|{seed}".encode()).hexdigest()
        path = self.cache_dir / f"{key}.txt" if self.cache_dir else None
        with self._lock:
            cached = key in self.cache
            if not cached and path and path.exists():
                self.cache[key] = path.read_text()
                cached = True
            raw = self.cache[key] if cached else ""
        if not cached:
            payload = {
                "model": model, "messages": messages, "stream": False, "think": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0, "top_k": 1, "top_p": 1,
                    "repeat_penalty": 1.05, "seed": seed,
                    "num_ctx": 8192, "num_predict": max_tokens,
                },
            }
            if schema:
                payload["format"] = schema
            endpoint = os.environ.get("OLLAMA_HOST", OLLAMA).rstrip("/")
            if not endpoint.endswith("/api/chat"):
                endpoint += "/api/chat"
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout_s) as response:
                    raw = json.loads(response.read())["message"]["content"]
            except (OSError, KeyError, ValueError, urllib.error.URLError) as exc:
                self._log({"turn": turn, "role": role, "prompt_sha": key,
                           "raw": "", "cached": False,
                           "error": type(exc).__name__})
                raise ModelUnavailable(str(exc)) from exc
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
            with self._lock:
                self.cache[key] = raw
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(raw)
        self._log({"turn": turn, "role": role, "prompt_sha": key,
                   "raw": raw, "cached": cached})
        return raw

    def flag_last(self, role: str, **flags) -> None:
        """Mark the most recent call of one role, e.g. `guard_fail=True` so the
        prompts can be tuned against real failures (spec 8.6). Scoped by role
        because two threads may be logging at once."""
        with self._lock:
            for entry in reversed(self.ai_log):
                if entry.get("role") == role:
                    entry.update(flags)
                    return

    def _log(self, entry: dict) -> dict:
        """Append one ai_log record and return it, so a caller can flag it
        (`guard_fail`) without racing another thread's append."""
        with self._lock:
            entry = {"call_id": f"c{len(self.ai_log) + 1:04d}", **entry}
            self.ai_log.append(entry)
            return entry
