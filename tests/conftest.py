"""Keep the automated suite away from the desktop window server."""

from __future__ import annotations

import os


# Loaded before test modules, and inherited by pytest-xdist workers.  A
# deliberate Tk integration run can opt in with ``STK_HEADLESS=0``.
os.environ.setdefault("STK_HEADLESS", "1")
