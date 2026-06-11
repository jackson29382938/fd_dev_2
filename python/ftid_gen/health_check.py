"""Startup diagnostics for bundled resources and writable paths."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from ftid_gen.config import (
    BASE_DIR,
    FONT_ARIAL,
    FONT_BOLD,
    FONT_MAIN,
    OUTPUT_DIR,
    STATE_DIR,
    TEMPLATES,
)


def _check_path(path: Path, *, label: str, issues: List[str], checks: Dict[str, Any], required: bool = True) -> bool:
    exists = path.exists()
    checks[label] = {"path": str(path), "exists": exists}
    if required and not exists:
        issues.append(f"Missing required resource: {label} ({path})")
    return exists


def run_health_diagnostics() -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, Any] = {}

    template_keys = {
        "ups_blank": TEMPLATES["4"][2],
        "usps_blank": TEMPLATES["5"][2],
        "fedex_blank": TEMPLATES["6"][2],
    }

    for label, relative in template_keys.items():
        blank_path = BASE_DIR / relative
        _check_path(blank_path, label=label, issues=issues, checks=checks)
        full_path = blank_path.with_name(blank_path.name.replace("_blank", "_full", 1))
        full_label = label.replace("_blank", "_full")
        if not full_path.exists():
            warnings.append(f"Reference full template not found: {full_label} ({full_path})")
        checks[full_label] = {"path": str(full_path), "exists": full_path.exists()}

    for label, font_path in {
        "font_main": FONT_MAIN,
        "font_bold": FONT_BOLD,
        "font_arial": FONT_ARIAL,
    }.items():
        _check_path(font_path, label=label, issues=issues, checks=checks)

    for label, directory in {
        "output_dir": OUTPUT_DIR,
        "state_dir": STATE_DIR,
    }.items():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            writable = os.access(directory, os.W_OK)
            checks[label] = {"path": str(directory), "exists": directory.exists(), "writable": writable}
            if not writable:
                issues.append(f"Directory is not writable: {label} ({directory})")
        except OSError as exc:
            checks[label] = {"path": str(directory), "exists": False, "writable": False, "error": str(exc)}
            issues.append(f"Could not prepare directory {label}: {exc}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
    }
