#!/usr/bin/env python3
"""
Resolve the symlinked vendor backend into a real directory tree for release builds.

During development, swift/vendor/backend is a symlink to python/ so there is only
one source of truth. Before packaging the macOS app, run this script to produce a
real copy with all symlinks resolved — so the app bundle is self-contained and
does not depend on the repository layout.

Usage:
    # Full copy (for initial setup or CI):
    python scripts/prepare_vendor_backend.py --output swift/vendor/backend

    # Sync only changed files into an existing backend directory:
    python scripts/prepare_vendor_backend.py --output swift/dist/FTIDMacApp.app/Contents/Resources/backend --sync
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "swift" / "vendor" / "backend"
SOURCE = ROOT / "python"

# Files and directories to skip when copying vendor backend
SKIP_NAMES = {
    "__pycache__",
    ".DS_Store",
    "generated-labels",
    "barcodes",
    "progress",
    "ftid_import_template_20251103_181625.xlsx",
    "previous_maxicode.json",
    "ftid_data.json",
    ".encryption.key",
    "gui_app.py",
    "main.py",
    "tests",  # tests are not needed in the bundled backend
    "BUILD_GUIDE.md",
    "BUILD_README.md",
    "DEPLOYMENT_CHECKLIST.md",
    "ENHANCEMENTS_README.md",
    "MAXICODE_ENHANCEMENTS.md",
    "run_gui.command",
    "build_app.py",
    "README.md",
}


def should_skip(name: str) -> bool:
    return name in SKIP_NAMES


def copy_real(src: Path, dst: Path) -> None:
    """Copy a directory tree, resolving symlinks into real files."""
    if src.is_symlink():
        resolved = src.resolve()
        if resolved.is_dir():
            shutil.copytree(resolved, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(resolved, dst)
    elif src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in sorted(src.iterdir()):
            if should_skip(item.name):
                continue
            copy_real(item, dst / item.name)
    else:
        shutil.copy2(src, dst)


def sync_files(source: Path, output: Path) -> list[str]:
    """Sync individual changed files from source to output. Returns list of updated files."""
    updated = []

    # Key files that need to be in sync
    SYNC_FILES = [
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
        "ftid_gen/health_check.py",
        "ftid_gen/enhanced_maxicode.py",
        "ftid_gen/excel_importer.py",
        "ftid_gen/previous_maxicode.py",
        "ftid_gen/data_storage.py",
        "ftid_gen/package_tracker.py",
        "ftid_gen/tracking_fetcher.py",
        "ftid_gen/console_utils.py",
        "ftid_gen/settings_menu.py",
        "ftid_gen/logging_config.py",
        "maxicode/decode_maxicode.py",
        "maxicode/pure_maxicode.py",
        "maxicode/requirements.txt",
        "user_tracking/subscription_manager.py",
        "user_tracking/csv_manager.py",
        "user_tracking/google_drive_logger.py",
        "user_tracking/credentials.py",
        "user_tracking/ip_utils.py",
    ]

    for rel_path in SYNC_FILES:
        src = source / rel_path
        dst = output / rel_path
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or not filecmp.cmp(src, dst, shallow=False):
            shutil.copy2(src, dst)
            updated.append(rel_path)

    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare vendor backend for release build")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE,
        help=f"Source directory (default: {SOURCE.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Only sync changed files (for updating an existing backend directory)",
    )
    args = parser.parse_args()

    output: Path = args.output
    source: Path = args.source

    if not source.exists():
        print(f"ERROR: Source directory does not exist: {source}", file=sys.stderr)
        return 1

    if args.sync:
        # Sync mode: only update changed files
        if not output.exists():
            print(f"ERROR: Output directory does not exist: {output}", file=sys.stderr)
            return 1
        updated = sync_files(source, output)
        if updated:
            print(f"Synchronized {len(updated)} files:")
            for f in updated:
                print(f"  - {f}")
        else:
            print("All files already up to date.")
        return 0

    # Full copy mode: replace the entire directory
    if output.is_symlink():
        print(f"Removing symlink: {output}")
        output.unlink()
    elif output.is_dir():
        print(f"Removing old directory: {output}")
        shutil.rmtree(output)

    print(f"Copying {source.relative_to(ROOT)} -> {output.relative_to(ROOT)}")
    copy_real(source, output)

    # Verify
    bridge = output / "bridge" / "ftid_bridge.py"
    if not bridge.exists():
        print(f"ERROR: Bridge script missing after copy: {bridge}", file=sys.stderr)
        return 1

    print(f"Vendor backend ready at {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
