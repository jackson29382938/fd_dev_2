#!/usr/bin/env python3
"""
Verify the vendor backend is correctly set up.

In development, swift/vendor/backend should be a symlink to python/.
For release builds, run scripts/prepare_vendor_backend.py first to resolve
the symlink into a real copy, then this script verifies file identity.

This replaces the old check_backend_sync.py which tried to maintain two
independent copies — a fragile approach that caused frequent CI failures.
"""

from __future__ import annotations

import filecmp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "python"
VENDOR = ROOT / "swift" / "vendor" / "backend"

# Files that must be identical between source and vendor (when not symlinked)
MIRRORED_FILES = [
    "bridge/ftid_bridge.py",
    "ftid_gen/address_utils.py",
    "ftid_gen/config.py",
    "ftid_gen/ftid_generator.py",
    "ftid_gen/label_processor.py",
    "ftid_gen/render/barcodes.py",
    "ftid_gen/render/text_overlay.py",
    "ftid_gen/settings_manager.py",
    "ftid_gen/tracking_models.py",
    "ftid_gen/tracking_utils.py",
    "user_tracking/subscription_manager.py",
]


def main() -> int:
    if VENDOR.is_symlink():
        target = VENDOR.resolve()
        if target == SOURCE.resolve():
            print("swift/vendor/backend is a symlink to python/ — development mode.")
            print("Run scripts/prepare_vendor_backend.py before release builds.")
            return 0
        print(f"ERROR: swift/vendor/backend symlink points to {target}, not {SOURCE}", file=sys.stderr)
        return 1

    if not VENDOR.is_dir():
        print(
            "ERROR: swift/vendor/backend does not exist.\n"
            "For development: ln -s ../../python swift/vendor/backend\n"
            "For release: python scripts/prepare_vendor_backend.py",
            file=sys.stderr,
        )
        return 1

    # Vendor is a real directory — verify all mirrored files match source
    failures: list[str] = []
    for rel_path in MIRRORED_FILES:
        src = SOURCE / rel_path
        vend = VENDOR / rel_path
        if not src.exists():
            print(f"WARNING: Source file missing: {rel_path}")
            continue
        if not vend.exists():
            failures.append(f"Missing in vendor: {rel_path}")
            continue
        if not filecmp.cmp(src, vend, shallow=False):
            failures.append(rel_path)

    if failures:
        print("Vendor backend files out of sync with python/:")
        for rel_path in failures:
            print(f"  - {rel_path}")
        print("\nRun: python scripts/prepare_vendor_backend.py")
        return 1

    print(f"All {len(MIRRORED_FILES)} vendor backend files match source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
