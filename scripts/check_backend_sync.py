#!/usr/bin/env python3
"""
Backward-compatible alias for check_vendor_sync.py.

The old check_backend_sync.py tried to auto-sync files between python/ and
swift/vendor/backend. That approach was fragile and caused CI failures.

Now swift/vendor/backend is a symlink to python/ in development mode, and
scripts/prepare_vendor_backend.py creates a real copy for release builds.

This script just delegates to the new check_vendor_sync.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = ROOT / "scripts" / "check_vendor_sync.py"

if not CHECK_SCRIPT.exists():
    print(f"ERROR: {CHECK_SCRIPT} not found", file=sys.stderr)
    sys.exit(1)

raise SystemExit(subprocess.call([sys.executable, str(CHECK_SCRIPT)] + sys.argv[1:]))
