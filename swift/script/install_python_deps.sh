#!/usr/bin/env bash
# Populate swift/vendor/python-site-packages/ from a Python 3.13 interpreter.
#
# The Swift app bundle embeds the Python backend + its dependencies. To make
# the build fully self-contained (no system Python required) we install the
# project requirements into swift/vendor/python-site-packages/, which the
# build script picks up automatically.
#
# Usage:
#   script/install_python_deps.sh
#   PYTHON_BIN=/path/to/python3.13 script/install_python_deps.sh
#
# Override behaviour with environment variables:
#   PYTHON_BIN         – which Python 3.13 interpreter to use (default:
#                        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13)
#   PIP_INDEX_URL      – custom PyPI index, if needed
#   SKIP_INSTALL       – set to 1 to only verify the destination exists
#   EXTRA_REQUIREMENTS  – path to a second requirements file to merge in
#
# Requirements:
#   * Python 3.13 with pip
#   * Network access to PyPI (or PIP_INDEX_URL)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST_DIR="$ROOT_DIR/vendor/python-site-packages"
PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python 3.13 not found at $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN to the interpreter you want to use." >&2
  exit 1
fi

if [[ "${SKIP_INSTALL:-0}" == "1" ]]; then
  echo "Skipping install (SKIP_INSTALL=1). Destination: $DST_DIR"
  exit 0
fi

mkdir -p "$DST_DIR"

echo "Using Python: $PYTHON_BIN"
"$PYTHON_BIN" --version

# Resolve the requirements file. The top-level python/requirements.txt is the
# canonical list; we also accept an override via the env var.
REQ_FILE=""
if [[ -n "${EXTRA_REQUIREMENTS:-}" && -f "${EXTRA_REQUIREMENTS}" ]]; then
  REQ_FILE="$EXTRA_REQUIREMENTS"
elif [[ -f "$ROOT_DIR/../python/requirements.txt" ]]; then
  REQ_FILE="$ROOT_DIR/../python/requirements.txt"
elif [[ -f "$ROOT_DIR/vendor/backend/requirements/requirements.txt" ]]; then
  REQ_FILE="$ROOT_DIR/vendor/backend/requirements/requirements.txt"
fi

if [[ -z "$REQ_FILE" ]]; then
  echo "No requirements.txt found. Looked in vendor/backend/requirements/ and ../python/." >&2
  exit 1
fi

# Earlier requirements lists installed the abandoned `barcode` package, whose
# files overwrite `python-barcode` in the shared `barcode/` module directory
# and crash on import (it needs the long-removed `pkg_resources`). `pip
# install --target --upgrade` does not remove files from uninstalled
# packages, so purge any leftover copy before reinstalling.
if [[ -d "$DST_DIR/barcode" ]] && grep -q "pkg_resources" "$DST_DIR/barcode/__init__.py" 2>/dev/null; then
  echo "Removing legacy 'barcode' package remnants from vendor tree."
  rm -rf "$DST_DIR/barcode" "$DST_DIR"/barcode-*.dist-info "$DST_DIR"/python_barcode-*.dist-info
fi

echo "Installing requirements from: $REQ_FILE"

PIP_ARGS=(--target "$DST_DIR" --upgrade --no-cache-dir)
if [[ -n "${PIP_INDEX_URL:-}" ]]; then
  PIP_ARGS+=(--index-url "$PIP_INDEX_URL")
fi

"$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" -r "$REQ_FILE"

# A few packages pull in C extensions; drop cache/test/doc payloads from the
# vendor tree so the app bundle stays lean without touching runtime modules.
find "$DST_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$DST_DIR" -type f -name '*.pyc' -delete 2>/dev/null || true
find "$DST_DIR" -type d \( -name 'tests' -o -name 'test' \) -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$DST_DIR/docs" "$DST_DIR/PyObjCTest"

# Sanity check: the barcode module must be importable from the vendor tree.
PYTHONPATH="$DST_DIR" "$PYTHON_BIN" -c "from barcode.codex import Code128; from barcode.writer import ImageWriter" \
  || { echo "Vendor tree sanity check failed: barcode module is broken." >&2; exit 1; }

echo ""
echo "Done. swift/vendor/python-site-packages is ready."
echo "Next step:  bash script/build_and_run.sh"
