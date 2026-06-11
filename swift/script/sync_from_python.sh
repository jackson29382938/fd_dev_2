#!/usr/bin/env bash
# Refresh swift/vendor/backend/ from the sibling python/ project.
#
# The swift/ folder is fully self-contained — it does NOT require python/ to
# build or run. This script is purely a convenience for keeping the vendored
# copy up to date when the Python backend changes upstream.
#
# Usage:
#   script/sync_from_python.sh                # uses ../python relative to swift/
#   script/sync_from_python.sh /path/to/python

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${1:-$ROOT_DIR/../python}"
DST_DIR="$ROOT_DIR/vendor/backend"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Source python project not found at: $SRC_DIR" >&2
  echo "Pass the path as the first arg if python/ lives somewhere else." >&2
  exit 1
fi

for required in bridge ftid_gen user_tracking maxicode requirements; do
  if [[ ! -d "$SRC_DIR/$required" ]]; then
    echo "Source python project is missing the '$required' directory." >&2
    echo "Got: $SRC_DIR" >&2
    exit 1
  fi
done

mkdir -p "$DST_DIR"

echo "Syncing python → swift/vendor/backend from $SRC_DIR"

for d in bridge ftid_gen user_tracking maxicode requirements; do
  mkdir -p "$DST_DIR/$d"
  rsync -a --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='.idea' \
    "$SRC_DIR/$d/" "$DST_DIR/$d/"
  echo "  · $d"
done

# Optional: refresh .env and encryption key from upstream if present.
for f in .env .encryption.key; do
  if [[ -f "$SRC_DIR/$f" ]]; then
    cp "$SRC_DIR/$f" "$DST_DIR/$f"
    echo "  · $f"
  fi
done

# Refresh the app icon.
if [[ -f "$SRC_DIR/requirements/app_icon.icns" ]]; then
  cp "$SRC_DIR/requirements/app_icon.icns" "$ROOT_DIR/vendor/app_icon.icns"
  echo "  · app_icon.icns"
fi

echo "Done. swift/vendor/backend is in sync with $SRC_DIR."
