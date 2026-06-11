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

    # --- Optional integration checks (warnings, not hard failures) ---
    optional_checks = _check_optional_integrations()
    for name, info in optional_checks.items():
        checks[f"optional.{name}"] = info
        if not info["available"]:
            warnings.append(info["message"])

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
    }


def _check_optional_integrations() -> Dict[str, Dict[str, Any]]:
    """Return availability info for each optional third-party integration.

    Each entry includes a user-friendly message explaining what breaks and
    how to fix it, so the Swift frontend can surface actionable prompts
    instead of silently falling back.
    """
    results: Dict[str, Dict[str, Any]] = {}

    # Yelp API (real address lookup)
    yelp_key = os.environ.get("YELP_API_KEY", "")
    results["yelp_api"] = {
        "available": bool(yelp_key),
        "message": (
            "Yelp API key is not configured. Real-address lookup is disabled; "
            "generated labels will use random fake addresses instead. "
            "Set the YELP_API_KEY environment variable or add it to your .env file."
        ),
    }

    # Google Sheets / Drive (subscription tracking, order sheet)
    gspread_creds = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
    results["google_sheets"] = {
        "available": bool(gspread_creds),
        "message": (
            "Google Sheets credentials are not configured. Subscription tracking "
            "and order-sheet sync are disabled. Set GOOGLE_CREDENTIALS_PATH to the "
            "path of your service-account JSON key file."
        ),
    }

    # Telegram notifications
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    results["telegram"] = {
        "available": bool(telegram_token),
        "message": (
            "Telegram bot token is not configured. Label-generation notifications "
            "via Telegram are disabled. Set TELEGRAM_BOT_TOKEN in your .env file "
            "to enable them."
        ),
    }

    # OpenCV (advanced image processing)
    try:
        import cv2  # noqa: F401
        opencv_available = True
    except ImportError:
        opencv_available = False
    results["opencv"] = {
        "available": opencv_available,
        "message": (
            "OpenCV is not installed. Advanced barcode decoding and image "
            "preprocessing are unavailable; the app will fall back to pyzbar "
            "and zbar for barcode reading. Install opencv-python to enable "
            "enhanced decoding."
        ),
    }

    # PyObjC (macOS native integrations)
    try:
        import Foundation  # noqa: F401
        pyobjc_available = True
    except ImportError:
        pyobjc_available = False
    results["pyobjc"] = {
        "available": pyobjc_available,
        "message": (
            "PyObjC is not installed. Some macOS-native features (clipboard "
            "integration, native file dialogs) may be limited. Install pyobjc "
            "on macOS for the full experience."
        ),
    }

    return results
