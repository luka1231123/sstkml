"""Small, optional Ollama transport. Nothing here is required for command mode."""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "qwen3:14b"
OLLAMA = "http://127.0.0.1:11434/api/chat"


class ModelUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, ai_log: list[dict] | None = None,
                 cache_dir: str | Path | None = None):
        self.ai_log = ai_log if ai_log is not None else []
        self.cache: dict[str, str] = {}
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def call(self, role: str, messages: list[dict], schema: dict | None,
             seed: int, max_tokens: int, timeout_s: float, turn: int = 0) -> str:
        model = os.environ.get("STTKML_MODEL", MODEL)
        prompt = json.dumps(messages, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(f"{role}|{model}|{prompt}|{seed}".encode()).hexdigest()
        cached = key in self.cache
        path = self.cache_dir / f"{key}.txt" if self.cache_dir else None
        if not cached and path and path.exists():
            self.cache[key] = path.read_text()
            cached = True
        if cached:
            raw = self.cache[key]
        else:
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
                self.ai_log.append({
                    "call_id": f"c{len(self.ai_log) + 1:04d}", "turn": turn,
                    "role": role, "prompt_sha": key, "raw": "",
                    "cached": False, "error": type(exc).__name__,
                })
                raise ModelUnavailable(str(exc)) from exc
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
            self.cache[key] = raw
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(raw)
        self.ai_log.append({
            "call_id": f"c{len(self.ai_log) + 1:04d}", "turn": turn,
            "role": role, "prompt_sha": key, "raw": raw, "cached": cached,
        })
        return raw
