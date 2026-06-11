#!/bin/bash
# FTID Generator GUI Launcher
# Runs the GUI application using Python 3.13 from python.org

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Prefer Python 3.13 from python.org, then fall back to python3 on PATH.
PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/gui_app.py"
