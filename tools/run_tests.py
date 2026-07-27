#!/usr/bin/env python3
"""Run the suite without pytest.

The tests are plain functions with plain asserts, so pytest is a convenience,
not a dependency -- and "28 tests green" should not be a claim that only holds
on a machine where pytest happens to be installed. This runner keeps the project
honest to its own stdlib-only rule.

    python3 tools/run_tests.py            # all milestones
    python3 tools/run_tests.py m7         # one module
    python3 tools/run_tests.py m7:voicer  # substring match on test names
"""
from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

MODULES = sorted(p.stem for p in (ROOT / "tests").glob("test_*.py"))


def run(selector: str = "") -> int:
    module_filter, _, name_filter = selector.partition(":")
    passed = failed = 0
    for module_name in MODULES:
        if module_filter and module_filter not in module_name:
            continue
        module = importlib.import_module(f"tests.{module_name}")
        for name in sorted(vars(module)):
            if not name.startswith("test_") or name_filter not in name:
                continue
            try:
                getattr(module, name)()
                passed += 1
            except Exception:
                failed += 1
                print(f"FAIL {module_name}.{name}")
                traceback.print_exc(limit=6)
                print()
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else ""))
