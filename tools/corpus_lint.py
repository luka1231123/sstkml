#!/usr/bin/env python3
"""Grade every dedicated outgoing exemplar; incoming NPC prose is intentionally messy."""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ai.grader import grade_for  # noqa: E402


def lint(path: str | Path = ROOT / "content" / "corpus" / "outgoing.toml") -> list[str]:
    errors = []
    for index, item in enumerate(tomllib.loads(Path(path).read_text()).get("letters", []), 1):
        profile, recipient, text = (
            item.get("profile"), item.get("recipient"), item.get("text", ""))
        if not profile or not recipient or "{" in text or "}" in text:
            errors.append(f"letter {index}: missing profile/recipient or unexpanded placeholder")
            continue
        try:
            score = grade_for(text, profile, recipient=recipient)
        except KeyError as exc:
            errors.append(f"letter {index}: {exc}")
            continue
        if score.total <= 900:
            errors.append(f"letter {index} ({profile}): {score.total} {score.violations}")
    return errors


if __name__ == "__main__":
    failures = lint()
    if failures:
        print("\n".join(failures))
        raise SystemExit(1)
    print("outgoing corpus: all exemplars score above 900")
