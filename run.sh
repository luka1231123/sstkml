#!/usr/bin/env bash
# Run the game against the project's own interpreter, never the ambient one.
#
# The window backend needs a python built with Tk. Homebrew's python ships
# without it unless `python-tk` is installed, and /usr/bin/python3 (Apple's)
# has none at all -- so "python3 play_gui.py" silently landing on the wrong
# interpreter is the single easiest way to conclude the game is broken when it
# is not. This script removes that choice.
#
#   ./run.sh              the windowed game
#   ./run.sh --check      say which interpreter and whether Tk is there
#   ./run.sh --cli        the terminal game
#   ./run.sh --test       the suite
#   ./run.sh --probe      find which Tk step kills the process
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "no .venv here yet; making one..."
    BASE="$(command -v python3.14 || command -v python3)"
    "$BASE" -m venv .venv
    echo "made .venv from $BASE"
fi

case "${1:-}" in
    --check) exec "$PY" play_gui.py --check ;;
    --probe) exec "$PY" tools/tkprobe.py ;;
    --cli)   shift; exec "$PY" play_cli.py "${@:-ugarit}" ;;
    --test)  shift; exec "$PY" tools/run_tests.py "$@" ;;
    *)       exec "$PY" play_gui.py "$@" ;;
esac
