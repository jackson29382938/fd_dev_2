#!/usr/bin/env python3
"""JSON bridge used by the native macOS app to drive the Python backend."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

# How long a preview temp dir may live before it is swept. Long enough for the
# frontend to load (possibly lazily) the rendered PNG, short enough to avoid
# unbounded buildup during layout editing sessions.
_PREVIEW_TEMP_MAX_AGE_SECONDS = 300


def _cleanup_preview_temp_dirs() -> None:
    """Sweep stale ``ftid_preview_*`` dirs from the system temp directory.

    Cleanup is purely age-based: the frontend may still be displaying the
    most recent composites, so only directories old enough that no UI can
    still reference them are removed.
    """
    cutoff = time.time() - _PREVIEW_TEMP_MAX_AGE_SECONDS
    try:
        temp_root = Path(tempfile.gettempdir())
        for stale in temp_root.glob("ftid_preview_*"):
            try:
                if stale.is_dir() and stale.stat().st_mtime < cutoff:
                    shutil.rmtree(stale, ignore_errors=True)
            except OSError:
                continue
    except Exception:
        pass

PROJECT_ROOT = Path(os.environ.get("FTID_BASE_DIR", Path(__file__).resolve().parent.parent))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ftid_gen.config import BASE_DIR, OUTPUT_DIR, TEMPLATES, FEDEX_TRACKING_PREFIX  # noqa: E402
from ftid_gen.data_storage import storage  # noqa: E402
from ftid_gen.previous_maxicode import previous_maxicode  # noqa: E402
from ftid_gen.settings_manager import settings  # noqa: E402
from user_tracking.csv_manager import load_history  # noqa: E402


class BridgeError(Exception):
    """Raised when the bridge cannot fulfill a request."""


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _read_payload() -> Dict[str, Any]:
    if sys.stdin.isatty():
        return {}

    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def _build_envelope(
    *,
    ok: bool,
    result: Any = None,
    error: Optional[str] = None,
    logs: str = "",
    error_report_path: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ok": ok,
        "result": result,
        "error": error,
        "logs": logs.strip(),
        "error_report_path": error_report_path,
    }


def _respond(
    *,
    ok: bool,
    result: Any = None,
    error: Optional[str] = None,
    logs: str = "",
    error_report_path: Optional[str] = None,
) -> None:
    envelope = _build_envelope(
        ok=ok, result=result, error=error, logs=logs, error_report_path=error_report_path
    )
    print(json.dumps(envelope, default=_json_default))


def _redacted_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    sensitive_keys = {"passcode", "password", "token", "secret", "credentials"}
    for key, value in payload.items():
        if key.lower() in sensitive_keys:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


def _error_report_dir() -> Path:
    base = Path(os.environ.get("FTID_STATE_DIR") or os.environ.get("FTID_OUTPUT_DIR") or Path.cwd())
    report_dir = base / "ErrorReports"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def _write_error_report(action: str, payload: Dict[str, Any], error: BaseException, logs: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_path = _error_report_dir() / f"ftid_error_{timestamp}_{action}.txt"
    sections = [
        "FTID Error Report",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Action: {action}",
        f"Working directory: {Path.cwd()}",
        f"Project root: {PROJECT_ROOT}",
        f"FTID_BASE_DIR: {os.environ.get('FTID_BASE_DIR', '')}",
        f"FTID_OUTPUT_DIR: {os.environ.get('FTID_OUTPUT_DIR', '')}",
        f"FTID_STATE_DIR: {os.environ.get('FTID_STATE_DIR', '')}",
        "",
        "Payload:",
        json.dumps(_redacted_payload(payload), indent=2, default=_json_default),
        "",
        "Error:",
        f"{type(error).__name__}: {error}",
        "",
        "Captured logs:",
        logs.strip() or "<none>",
        "",
        "Traceback:",
        traceback.format_exc().strip(),
        "",
    ]
    report_path.write_text("\n".join(sections), encoding="utf-8")
    return str(report_path)


def _capture_envelope(action: str, handler, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a handler with captured output and return a response envelope."""
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            result = handler(payload)
        return _build_envelope(ok=True, result=result, logs=buffer.getvalue())
    except BridgeError as exc:
        logs = buffer.getvalue()
        report_path = _write_error_report(action, payload, exc, logs)
        return _build_envelope(ok=False, error=str(exc), logs=logs, error_report_path=report_path)
    except Exception as exc:  # pragma: no cover - defensive bridge guard
        logs = buffer.getvalue()
        if logs:
            logs = f"{logs}\n{traceback.format_exc()}"
        else:
            logs = traceback.format_exc()
        report_path = _write_error_report(action, payload, exc, logs)
        return _build_envelope(ok=False, error=str(exc), logs=logs, error_report_path=report_path)


def _capture(action: str, handler, payload: Dict[str, Any]) -> None:
    envelope = _capture_envelope(action, handler, payload)
    print(json.dumps(envelope, default=_json_default))


def _require(payload: Dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value in (None, ""):
        raise BridgeError(f"Missing required field: {key}")
    return value


def _settings_snapshot() -> Dict[str, Any]:
    return settings.settings


def _previous_input_snapshot() -> Dict[str, Any]:
    return {
        "sender_zip": storage.get_previous_sender_zip() or "",
        "receiver_zip": storage.get_previous_receiver_zip() or "",
        "ups_tracking": storage.get_previous_ups_tracking() or "",
        "usps_tracking": storage.get_previous_usps_tracking() or "",
        "fedex_tracking": storage.get_previous_fedex_tracking() or "",
        "address_type": storage.get_previous_address_type() or "",
    }


def _history_snapshot(max_entries: int = 100) -> List[Dict[str, Any]]:
    return [_history_entry_from_row(row) for row in _read_history_rows()[:max_entries]]


def _collections_snapshot() -> Dict[str, Any]:
    history_entries = _history_snapshot()
    previous_entries = previous_maxicode.get_recent_entries()
    return {
        "history_entries": history_entries,
        "previous_maxicode_entries": previous_entries,
        "previous_inputs": _previous_input_snapshot(),
    }


def _resolve_manager(user_id: str, passcode: str):
    from user_tracking.subscription_manager import initialize_subscription_manager
    import gspread

    try:
        manager = initialize_subscription_manager()
        user_data = manager.find_user(user_id, passcode)
    except gspread.exceptions.APIError as exc:
        raise BridgeError(
            f"Subscription database is currently unavailable (Error {exc.code}). "
            "Please check your internet connection or try again later."
        )
    except Exception as exc:
        raise BridgeError(f"Failed to connect to subscription database: {exc}")

    if user_data is None:
        raise BridgeError("Invalid credentials.")
    if user_data.get("remaining_runs", 0) <= 0:
        raise BridgeError("No runs remaining for this account.")

    try:
        manager.current_user_id = user_id
        manager.current_user_row = user_data.get("row_number")
        manager.ensure_user_sheet_exists(user_id)
    except Exception as exc:
        raise BridgeError(f"Failed to initialize user session: {exc}")

    return manager, int(user_data.get("remaining_runs", 0))


def _carrier_metadata(carrier: str) -> Dict[str, str]:
    normalized = carrier.upper()
    if normalized == "UPS":
        return {"method": "FTID_UPS", "template_key": "4"}
    if normalized == "USPS":
        return {"method": "FTID_USPS", "template_key": "5"}
    if normalized == "FEDEX":
        return {"method": "FTID_FEDEX", "template_key": "6"}
    raise BridgeError(f"Unsupported carrier: {carrier}")


def _tracking_values(carrier: str, original_tracking: str) -> Dict[str, str]:
    from ftid_gen.tracking_utils import (
        modify_fedex_tracking_number,
        modify_tracking_number,
        modify_usps_tracking_number,
    )

    carrier = carrier.upper()
    if carrier == "UPS":
        return {
            "tracking_number": modify_tracking_number(original_tracking),
            "tracking_bar": original_tracking,
        }
    if carrier == "USPS":
        return {
            "tracking_number": modify_usps_tracking_number(original_tracking),
            "tracking_bar": original_tracking,
        }
    if carrier == "FEDEX":
        return {
            "tracking_number": modify_fedex_tracking_number(original_tracking),
            "tracking_bar": f"{FEDEX_TRACKING_PREFIX}{original_tracking}",
        }
    raise BridgeError(f"Unsupported carrier: {carrier}")


def _generate_address_info(zip_code: str, address_type: str) -> Dict[str, str]:
    from ftid_gen.address_utils import generate_fake_address, generate_full_name, search_yelp_for_address

    normalized_type = address_type.lower()
    if normalized_type == "real":
        address = search_yelp_for_address(zip_code) or generate_fake_address(zip_code)
        persisted_address_type = "R"
    else:
        address = generate_fake_address(zip_code)
        persisted_address_type = "F"

    if not address:
        raise BridgeError(f"Could not generate an address for ZIP code {zip_code}.")

    return {
        "name": generate_full_name(),
        "address": address["address"],
        "city": address["city"],
        "state": address["state"],
        "zip_code": address.get("zip_code", address.get("zip", zip_code)),
        "_persisted_address_type": persisted_address_type,
    }


def _store_previous_inputs(carrier: str, sender_zip: str, receiver_zip: str, tracking: str, address_type: str) -> None:
    storage.save_sender_zip(sender_zip)
    storage.save_receiver_zip(receiver_zip)
    storage.save_address_type("R" if address_type.lower() == "real" else "F")
    if carrier == "UPS":
        storage.save_ups_tracking(tracking)
    elif carrier == "USPS":
        storage.save_usps_tracking(tracking)
    elif carrier == "FEDEX":
        storage.save_fedex_tracking(tracking)


def _carrier_layout_for_method(method: str, label_layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from ftid_gen.label_processor import _get_layout

    carrier = method.replace("FTID_", "").lower()
    if label_layout:
        return _get_layout(carrier, label_layout)
    return settings.get(f"label_layout.{carrier}", {})


def _select_template_data(
    method: str,
    ftid_info: Dict[str, Any],
    label_layout: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from ftid_gen.label_processor import resolve_template_path

    if method == "FTID_UPS":
        default_template = os.path.join(str(BASE_DIR), TEMPLATES["4"][2])
        name = "FTID_UPS"
    elif method == "FTID_USPS":
        default_template = os.path.join(str(BASE_DIR), TEMPLATES["5"][2])
        name = "FTID_USPS"
    elif method == "FTID_FEDEX":
        default_template = os.path.join(str(BASE_DIR), TEMPLATES["6"][2])
        name = "FTID_FEDEX"
    else:
        raise BridgeError(f"Unsupported method: {method}")

    carrier_layout = _carrier_layout_for_method(method, label_layout)
    resolved_template = resolve_template_path(carrier_layout, default_template)
    if not resolved_template.exists():
        raise BridgeError(
            f"Template image not found for {method}. "
            f"Expected {resolved_template}. Verify bundled template assets are installed."
        )

    return {
        "name": name,
        "data": ftid_info["tracking_bar"],
        "template": str(resolved_template),
        "default_template": default_template,
    }


def _full_label_path_for(blank_label_path: str) -> Optional[str]:
    if "blank" not in blank_label_path:
        return None

    full_label_path = blank_label_path.replace("blank", "full", 1)
    return full_label_path if os.path.exists(full_label_path) else None


def _finalize_label_generation(
    *,
    ftid_info: Dict[str, Any],
    method: str,
    sender_info: Dict[str, str],
    receiver_info: Dict[str, str],
    manager,
    label_layout: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from ftid_gen.label_processor import process_label
    from user_tracking.csv_manager import save_run_to_csv

    if label_layout is None:
        label_layout = settings.get("label_layout", {})

    template_data = _select_template_data(method, ftid_info, label_layout)
    _, label_path = process_label(
        template_data["name"],
        template_data["data"],
        template_data["default_template"],
        str(BASE_DIR),
        ftid_info,
        label_layout=label_layout,
    )

    save_run_to_csv(ftid_info, method)
    previous_maxicode.add_maxicode(
        template_data["data"],
        method,
        ftid_info["original_tracking"],
        sender_info,
        receiver_info,
    )

    if not manager.deduct_run_and_log(ftid_info, method):
        raise BridgeError("The label was generated, but the subscription run could not be recorded.")

    return {
        "label_path": str(label_path),
        "full_label_path": _full_label_path_for(str(label_path)),
        "template_name": os.path.basename(template_data["template"]),
        "template_path": template_data["template"],
        "carrier": method.replace("FTID_", ""),
        "method": method,
        "ftid_info": ftid_info,
        "remaining_runs": manager.get_current_remaining_runs(),
    }


def _create_labels_pdf(image_paths: List[str]) -> Optional[str]:
    valid_paths = [path for path in image_paths if path and os.path.exists(path)]
    if not valid_paths:
        return None

    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = downloads_dir / f"batch_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    try:
        import img2pdf

        with open(pdf_path, "wb") as handle:
            handle.write(img2pdf.convert(valid_paths))
        return str(pdf_path)
    except Exception:
        from PIL import Image

        rgb_images = []
        try:
            for path in valid_paths:
                image = Image.open(path)
                if image.mode == "RGBA":
                    flattened = Image.new("RGB", image.size, (255, 255, 255))
                    flattened.paste(image, mask=image.split()[3])
                    rgb_images.append(flattened)
                elif image.mode != "RGB":
                    rgb_images.append(image.convert("RGB"))
                else:
                    rgb_images.append(image.copy())
                image.close()

            if not rgb_images:
                return None

            if len(rgb_images) == 1:
                rgb_images[0].save(pdf_path, "PDF", resolution=100.0)
            else:
                rgb_images[0].save(
                    pdf_path,
                    "PDF",
                    save_all=True,
                    append_images=rgb_images[1:],
                    resolution=100.0,
                )
            return str(pdf_path)
        finally:
            for image in rgb_images:
                image.close()


def _read_history_rows() -> List[Dict[str, Any]]:
    rows = load_history()
    return sorted(rows, key=lambda row: row.get("timestamp", ""), reverse=True)


def _history_entry_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    sender_csz = row.get("sender_city_state_zip") or ""
    receiver_csz = row.get("receiver_city_state_zip") or ""
    sender_zip = row.get("sender_zip") or (sender_csz.split()[-1] if sender_csz else "")
    receiver_zip = row.get("receiver_zip") or (receiver_csz.split()[-1] if receiver_csz else "")
    return {
        "timestamp": row.get("timestamp") or "",
        "method": row.get("method") or "",
        "tracking_number": row.get("tracking_number") or "",
        "original_tracking": row.get("original_tracking") or row.get("tracking_number") or "",
        "sender_name": row.get("sender_name") or row.get("sender") or "",
        "sender_address": row.get("sender_address") or "",
        "sender_city_state_zip": sender_csz,
        "receiver_name": row.get("receiver_name") or row.get("receiver") or "",
        "receiver_address": row.get("receiver_address") or "",
        "receiver_city_state_zip": receiver_csz,
        "sender_zip": sender_zip,
        "receiver_zip": receiver_zip,
    }


def handle_health(_: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.health_check import run_health_diagnostics

    collections = _collections_snapshot()
    diagnostics = run_health_diagnostics()
    return {
        "project_root": str(PROJECT_ROOT),
        "base_dir": str(BASE_DIR),
        "output_dir": str(OUTPUT_DIR),
        "state_dir": os.getcwd(),
        "settings": _settings_snapshot(),
        "history_count": len(collections["history_entries"]),
        "previous_maxicode_count": len(collections["previous_maxicode_entries"]),
        "diagnostics": diagnostics,
        "resources_ok": diagnostics.get("ok", False),
        **collections,
    }


def handle_login(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = _require(payload, "user_id")
    passcode = _require(payload, "passcode")
    _, remaining_runs = _resolve_manager(user_id, passcode)
    return {
        "user_id": user_id,
        "remaining_runs": remaining_runs,
        "settings": _settings_snapshot(),
        **_collections_snapshot(),
    }


def handle_lookup_zip(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.address_utils import auto_fill_from_zip, lookup_zipcode_info

    zip_code = _require(payload, "zip_code")
    info = lookup_zipcode_info(zip_code) or auto_fill_from_zip(zip_code)
    if not info:
        raise BridgeError(f"Could not look up ZIP code {zip_code}.")
    return {
        "zip_code": zip_code,
        "city": info.get("city", ""),
        "state": info.get("state", ""),
        "zip": info.get("zip", zip_code),
    }


def handle_settings_get(_: Dict[str, Any]) -> Dict[str, Any]:
    return _settings_snapshot()


def handle_settings_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    values = payload.get("values", {})
    if not isinstance(values, dict):
        raise BridgeError("Expected 'values' to be an object.")

    for key, value in values.items():
        settings.set(key, value)
    return _settings_snapshot()


def handle_settings_reset(_: Dict[str, Any]) -> Dict[str, Any]:
    settings.reset_to_defaults()
    return _settings_snapshot()


def handle_settings_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    target_path = _require(payload, "target_path")
    if not settings.export_settings(target_path):
        raise BridgeError("Failed to export settings.")
    return {"target_path": target_path}


def handle_settings_import(payload: Dict[str, Any]) -> Dict[str, Any]:
    source_path = _require(payload, "source_path")
    if not settings.import_settings(source_path):
        raise BridgeError("Failed to import settings.")
    return _settings_snapshot()


def handle_previous_inputs(_: Dict[str, Any]) -> Dict[str, Any]:
    return _previous_input_snapshot()


def handle_history(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"entries": _history_snapshot()}


def handle_previous_maxicode(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"entries": previous_maxicode.get_recent_entries()}


def handle_collections(_: Dict[str, Any]) -> Dict[str, Any]:
    return _collections_snapshot()


def handle_generate_label(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = _require(payload, "user_id")
    passcode = _require(payload, "passcode")
    carrier = _require(payload, "carrier").upper()
    receiver_zip = _require(payload, "receiver_zip")
    original_tracking = _require(payload, "tracking")
    address_type = payload.get("address_type", "fake")
    default_sender_zip = settings.get("from_address.zip_code", "")
    sender_zip = payload.get("sender_zip") or default_sender_zip
    if not sender_zip:
        raise BridgeError("Sender ZIP is required unless a default From ZIP is set in Settings.")

    manager, _ = _resolve_manager(user_id, passcode)
    metadata = _carrier_metadata(carrier)

    _store_previous_inputs(carrier, sender_zip, receiver_zip, original_tracking, address_type)
    sender_info = _generate_address_info(sender_zip, address_type)
    receiver_info = _generate_address_info(receiver_zip, address_type)
    tracking_values = _tracking_values(carrier, original_tracking)

    ftid_info = {
        "sender": sender_info["name"],
        "sender_address": sender_info["address"],
        "sender_2nd_line": f"{sender_info['city']} {sender_info['state']} {sender_info['zip_code']}",
        "receiver": receiver_info["name"],
        "receiver_address": receiver_info["address"],
        "receiver_2nd_line": f"{receiver_info['city']} {receiver_info['state']} {receiver_info['zip_code']}",
        "tracking_number": tracking_values["tracking_number"],
        "tracking_bar": tracking_values["tracking_bar"],
        "receiver_zip": receiver_info["zip_code"],
        "sender_zip": sender_info["zip_code"],
        "original_tracking": original_tracking,
    }

    label_layout = settings.get("label_layout", {})

    return _finalize_label_generation(
        ftid_info=ftid_info,
        method=metadata["method"],
        sender_info=sender_info,
        receiver_info=receiver_info,
        manager=manager,
        label_layout=label_layout,
    )


def handle_regenerate_history(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.ftid_generator import regenerate_from_zips

    user_id = _require(payload, "user_id")
    passcode = _require(payload, "passcode")
    method = _require(payload, "method")
    sender_zip = _require(payload, "sender_zip")
    receiver_zip = _require(payload, "receiver_zip")
    original_tracking = _require(payload, "original_tracking")
    address_choice = payload.get("address_type") or storage.get_previous_address_type() or "F"

    manager, _ = _resolve_manager(user_id, passcode)
    ftid_info = regenerate_from_zips(
        sender_zip,
        receiver_zip,
        original_tracking,
        method,
        address_choice=address_choice,
        allow_fallback_prompt=False,
    )
    if not ftid_info:
        raise BridgeError("Could not regenerate the selected history entry.")

    sender_info = {
        "name": ftid_info["sender"],
        "address": ftid_info["sender_address"],
        "city": ftid_info["sender_2nd_line"].split()[0] if ftid_info["sender_2nd_line"] else "",
        "state": ftid_info["sender_2nd_line"].split()[1] if len(ftid_info["sender_2nd_line"].split()) > 1 else "",
        "zip_code": sender_zip,
    }
    receiver_info = {
        "name": ftid_info["receiver"],
        "address": ftid_info["receiver_address"],
        "city": ftid_info["receiver_2nd_line"].split()[0] if ftid_info["receiver_2nd_line"] else "",
        "state": ftid_info["receiver_2nd_line"].split()[1] if len(ftid_info["receiver_2nd_line"].split()) > 1 else "",
        "zip_code": receiver_zip,
    }

    return _finalize_label_generation(
        ftid_info=ftid_info,
        method=method,
        sender_info=sender_info,
        receiver_info=receiver_info,
        manager=manager,
    )


def handle_regenerate_previous_maxicode(payload: Dict[str, Any]) -> Dict[str, Any]:
    entry = payload.get("entry")
    if not isinstance(entry, dict):
        raise BridgeError("Expected 'entry' to be an object.")

    regenerated_payload = {
        "user_id": _require(payload, "user_id"),
        "passcode": _require(payload, "passcode"),
        "method": _require(entry, "method"),
        "sender_zip": _require(entry.get("sender_info", {}), "zip_code"),
        "receiver_zip": _require(entry.get("receiver_info", {}), "zip_code"),
        "original_tracking": _require(entry, "tracking_number"),
    }
    return handle_regenerate_history(regenerated_payload)


def handle_import_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.excel_importer import excel_importer

    file_path = _require(payload, "file_path")
    dataframe = excel_importer.import_file(file_path)
    if dataframe is None:
        raise BridgeError("Could not import the selected file.")

    auto_mappings = excel_importer.auto_detect_columns(dataframe)
    preview_rows = dataframe.fillna("").astype(str).head(10).to_dict(orient="records")
    return {
        "file_path": file_path,
        "row_count": len(dataframe),
        "columns": [str(column) for column in dataframe.columns],
        "auto_mappings": auto_mappings,
        "preview_rows": preview_rows,
    }


def handle_create_import_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    target_path = _require(payload, "target_path")
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    import pandas as pd

    template_data = {
        "tracking_number": ["1Z9999999999999999", "4201234567890123456789", "123456789012"],
        "sender_zip": ["10001", "90210", "60601"],
        "receiver_zip": ["90210", "10001", "33101"],
        "sender_name": ["", "", ""],
        "receiver_name": ["", "", ""],
        "sender_address": ["", "", ""],
        "receiver_address": ["", "", ""],
        "method": ["FTID_UPS", "FTID_USPS", "FTID_FEDEX"],
    }

    dataframe = pd.DataFrame(template_data)
    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="Data", index=False)
        instructions = pd.DataFrame(
            {
                "INSTRUCTIONS": [
                    "REQUIRED COLUMNS:",
                    "tracking_number",
                    "sender_zip",
                    "receiver_zip",
                    "",
                    "OPTIONAL COLUMNS:",
                    "sender_name",
                    "receiver_name",
                    "sender_address",
                    "receiver_address",
                    "method",
                ]
            }
        )
        instructions.to_excel(writer, sheet_name="Instructions", index=False)

        for worksheet in writer.book.worksheets:
            max_row = max(worksheet.max_row, 1000)
            max_col = max(worksheet.max_column, 1)
            for column_index in range(1, max_col + 1):
                column_letter = worksheet.cell(row=1, column=column_index).column_letter
                worksheet.column_dimensions[column_letter].number_format = "@"
                for row_index in range(1, max_row + 1):
                    cell = worksheet.cell(row=row_index, column=column_index)
                    cell.number_format = "@"
                    if cell.value is not None:
                        cell.value = str(cell.value)

    return {"target_path": str(target)}


def handle_import_process(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.excel_importer import excel_importer

    user_id = _require(payload, "user_id")
    passcode = _require(payload, "passcode")
    file_path = _require(payload, "file_path")
    mappings = payload.get("mappings")
    if not isinstance(mappings, dict):
        raise BridgeError("Expected 'mappings' to be an object.")

    manager, _ = _resolve_manager(user_id, passcode)
    dataframe = excel_importer.import_file(file_path)
    if dataframe is None:
        raise BridgeError("Could not import the selected file.")

    results = excel_importer.process_batch(dataframe, mappings)
    skipped_rows = list(getattr(excel_importer, "last_skipped_rows", []))
    if not results:
        if skipped_rows:
            detail = "; ".join(
                f"row {item['row_number']}: {item['reason']}" for item in skipped_rows[:5]
            )
            raise BridgeError(
                f"No labels were generated. {len(skipped_rows)} row(s) were skipped. {detail}"
            )
        raise BridgeError("The selected file did not produce any batch results.")

    summary: Dict[str, int] = {}
    label_paths: List[str] = []
    processed_rows: List[Dict[str, Any]] = []

    for result in results:
        method = result["method"]
        ftid_info = {
            "sender": result["sender_info"]["name"],
            "sender_address": result["sender_info"]["address"],
            "sender_2nd_line": f"{result['sender_info']['city']} {result['sender_info']['state']} {result['sender_info']['zip_code']}",
            "receiver": result["receiver_info"]["name"],
            "receiver_address": result["receiver_info"]["address"],
            "receiver_2nd_line": f"{result['receiver_info']['city']} {result['receiver_info']['state']} {result['receiver_info']['zip_code']}",
            "tracking_number": result["modified_tracking"],
            "tracking_bar": result["original_tracking"] if method != "FTID_FEDEX" else f"{FEDEX_TRACKING_PREFIX}{result['original_tracking']}",
            "receiver_zip": result["receiver_zip"],
            "sender_zip": result["sender_zip"],
            "original_tracking": result["original_tracking"],
        }

        generated = _finalize_label_generation(
            ftid_info=ftid_info,
            method=method,
            sender_info=result["sender_info"],
            receiver_info=result["receiver_info"],
            manager=manager,
        )
        label_paths.append(generated["label_path"])
        summary[method] = summary.get(method, 0) + 1
        processed_rows.append(
            {
                "row_number": result["row_number"],
                "method": method,
                "original_tracking": result["original_tracking"],
                "modified_tracking": result["modified_tracking"],
                "label_path": generated["label_path"],
            }
        )

    pdf_path = _create_labels_pdf(label_paths)
    return {
        "summary": summary,
        "processed_rows": processed_rows,
        "skipped_rows": skipped_rows,
        "total_rows": len(dataframe),
        "processed_count": len(processed_rows),
        "skipped_count": len(skipped_rows),
        "label_paths": label_paths,
        "pdf_path": pdf_path,
        "remaining_runs": manager.get_current_remaining_runs(),
    }


def handle_maxicode_generate(_: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.enhanced_maxicode import enhanced_maxicode

    data = enhanced_maxicode.create_maxicode_from_scratch()
    return {
        "data": data,
        "length": len(data),
        "suggested_filename": f"enhanced_maxicode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
    }


def handle_maxicode_modify(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.enhanced_maxicode import enhanced_maxicode

    source = _require(payload, "data")
    data = enhanced_maxicode.modify_existing_maxicode(source)
    if not data:
        raise BridgeError("Could not modify the supplied MaxiCode data.")
    return {
        "data": data,
        "length": len(data),
        "suggested_filename": f"modified_maxicode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
    }


def handle_export_text(payload: Dict[str, Any]) -> Dict[str, Any]:
    target_path = _require(payload, "target_path")
    content = _require(payload, "content")
    with open(target_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return {"target_path": target_path}


def handle_render_preview_elements(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.label_processor import compose_label
    from PIL import Image

    carrier = _require(payload, "carrier").upper()
    ftid_info = payload.get("ftid_info")
    layout_overrides = payload.get("layout_overrides")

    if not ftid_info:
        from ftid_gen.address_utils import generate_fake_address, generate_full_name
        from ftid_gen.tracking_utils import modify_tracking_number

        sample_zip = "10001"
        address = generate_fake_address(sample_zip)
        fake_sender = generate_full_name()
        fake_receiver = generate_full_name()
        sample_tracking = "1Z9999999999999999"
        modified_tracking = modify_tracking_number(sample_tracking)
        ftid_info = {
            "sender": fake_sender,
            "sender_address": address["address"],
            "sender_2nd_line": f"{address['city']} {address['state']} {address['zip_code']}",
            "receiver": fake_receiver,
            "receiver_address": address["address"],
            "receiver_2nd_line": f"{address['city']} {address['state']} {address['zip_code']}",
            "tracking_number": modified_tracking,
            "tracking_bar": sample_tracking,
            "receiver_zip": address.get("zip_code", sample_zip),
            "sender_zip": sample_zip,
            "original_tracking": sample_tracking,
        }

    _cleanup_preview_temp_dirs()
    temp_dir = Path(tempfile.mkdtemp(prefix="ftid_preview_"))
    metadata = _carrier_metadata(carrier)

    label_layout: Dict[str, Any]
    if isinstance(layout_overrides, dict) and layout_overrides.get("barcode") is None and layout_overrides.get("maxicode") is None:
        if any(key in layout_overrides for key in ("ups", "usps", "fedex")):
            label_layout = layout_overrides
        else:
            label_layout = {carrier.lower(): layout_overrides}
    else:
        label_layout = settings.get("label_layout", {})
        if isinstance(layout_overrides, dict):
            label_layout = {**label_layout, carrier.lower(): layout_overrides}

    template_data = _select_template_data(metadata["method"], ftid_info, label_layout)
    composite_path = temp_dir / "composite_label.png"

    try:
        compose_label(
            metadata["method"],
            ftid_info.get("tracking_bar", ftid_info["original_tracking"]),
            template_data["default_template"],
            ftid_info=ftid_info,
            label_layout=label_layout,
            output_path=composite_path,
        )
    except Exception as exc:
        raise BridgeError(
            f"Could not render preview for {carrier}. "
            f"Verify template assets, fonts, and MaxiCode dependencies. Details: {exc}"
        ) from exc

    with Image.open(composite_path) as composite_image:
        width, height = composite_image.size

    return {
        "composite": str(composite_path),
        "base_template": str(composite_path),
        "barcode": None,
        "maxicode": None,
        "zip_barcode": None,
        "ftid_info": ftid_info,
        "template_width": width,
        "template_height": height,
    }


def handle_tracking_list(_: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    entries = tracking_manager.get_all()
    return {
        "entries": [e.to_dict() for e in entries],
        "stats": tracking_manager.get_stats(),
    }


def handle_tracking_add(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    tracking_number = _require(payload, "tracking_number")
    entry = tracking_manager.add_entry(
        tracking_number=tracking_number,
        carrier=payload.get("carrier", "UNKNOWN"),
        label=payload.get("label", ""),
        store=payload.get("store", ""),
        origin_zip=payload.get("origin_zip", ""),
        destination_zip=payload.get("destination_zip", ""),
        estimated_delivery=payload.get("estimated_delivery", ""),
        source=payload.get("source", "manual"),
    )
    return entry.to_dict()


def handle_tracking_delete(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    entry_id = _require(payload, "entry_id")
    if not tracking_manager.remove_entry(entry_id):
        raise BridgeError(f"Tracking entry not found: {entry_id}")
    return {"deleted": True}


def handle_tracking_refresh(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    from ftid_gen.tracking_fetcher import tracking_fetcher

    entry_id = payload.get("entry_id")
    if entry_id:
        entry = tracking_manager.get_entry(entry_id)
        if not entry:
            raise BridgeError(f"Tracking entry not found: {entry_id}")
        entries = [entry]
    else:
        entries = tracking_manager.get_active()

    updated = []
    for entry in entries:
        result = tracking_fetcher.fetch_status(entry)
        if result:
            new_status = result.get("status", "")
            if new_status and new_status != entry.status:
                tracking_manager.update_status(
                    entry.id,
                    status=new_status,
                    details=result.get("details", ""),
                    location=result.get("location", ""),
                    estimated_delivery=result.get("estimated_delivery", ""),
                )
                updated.append(entry.id)

    return {
        "updated_count": len(updated),
        "updated_ids": updated,
    }


def handle_tracking_import_sheet(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise BridgeError("Expected 'rows' to be a list of dictionaries.")
    added = tracking_manager.import_from_sheet_rows(rows)
    return {
        "added_count": len(added),
        "entries": [e.to_dict() for e in added],
    }


def handle_tracking_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    entry_id = _require(payload, "entry_id")
    entry = tracking_manager.get_entry(entry_id)
    if not entry:
        raise BridgeError(f"Tracking entry not found: {entry_id}")
    tracking_manager.mark_notification_seen(entry_id)
    return entry.to_dict()


def handle_tracking_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    entry_id = _require(payload, "entry_id")
    allowed_fields = {"label", "store", "origin_zip", "destination_zip", "estimated_delivery", "carrier", "status", "status_details", "notification_seen"}
    updates = {k: v for k, v in payload.items() if k != "entry_id" and k in allowed_fields}
    entry = tracking_manager.update_entry(entry_id, **updates)
    if not entry:
        raise BridgeError(f"Tracking entry not found: {entry_id}")
    return entry.to_dict()


def handle_tracking_stats(_: Dict[str, Any]) -> Dict[str, Any]:
    from ftid_gen.package_tracker import tracking_manager
    return tracking_manager.get_stats()


HANDLERS = {
    "health": handle_health,
    "login": handle_login,
    "lookup_zip": handle_lookup_zip,
    "settings_get": handle_settings_get,
    "settings_update": handle_settings_update,
    "settings_reset": handle_settings_reset,
    "settings_export": handle_settings_export,
    "settings_import": handle_settings_import,
    "previous_inputs": handle_previous_inputs,
    "history": handle_history,
    "previous_maxicode": handle_previous_maxicode,
    "collections": handle_collections,
    "generate_label": handle_generate_label,
    "regenerate_history": handle_regenerate_history,
    "regenerate_previous_maxicode": handle_regenerate_previous_maxicode,
    "import_preview": handle_import_preview,
    "create_import_template": handle_create_import_template,
    "import_process": handle_import_process,
    "maxicode_generate": handle_maxicode_generate,
    "maxicode_modify": handle_maxicode_modify,
    "export_text": handle_export_text,
    "render_preview_elements": handle_render_preview_elements,
    "tracking_list": handle_tracking_list,
    "tracking_add": handle_tracking_add,
    "tracking_delete": handle_tracking_delete,
    "tracking_refresh": handle_tracking_refresh,
    "tracking_import_sheet": handle_tracking_import_sheet,
    "tracking_detail": handle_tracking_detail,
    "tracking_update": handle_tracking_update,
    "tracking_stats": handle_tracking_stats,
}


def main() -> None:
    if len(sys.argv) < 2:
        _respond(ok=False, error="Missing action argument.")
        return

    action = sys.argv[1]
    handler = HANDLERS.get(action)
    if handler is None:
        _respond(ok=False, error=f"Unknown action: {action}")
        return

    payload = _read_payload()
    _capture(action, handler, payload)


def _serve() -> None:
    """Long-lived server mode: one JSON request per stdin line.

    Request:  {"id": <any>, "action": "<name>", "payload": {...}}
    Response: envelope dict (same as single-shot mode) plus the request "id",
    emitted as a single line on the real stdout.

    Keeping the process alive means the interpreter and heavy imports
    (pandas, PIL, ...) are paid once per app session instead of once per
    click, which makes every bridge call dramatically faster.
    """
    real_stdout = sys.stdout
    # Stray prints from libraries must never corrupt the line protocol.
    sys.stdout = sys.stderr

    def emit(envelope: Dict[str, Any]) -> None:
        real_stdout.write(json.dumps(envelope, default=_json_default) + "\n")
        real_stdout.flush()

    # Signal readiness so the frontend can distinguish "warming up" from "hung".
    emit({"id": None, "ok": True, "result": {"ready": True}, "error": None, "logs": "", "error_report_path": None})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id: Any = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            action = request.get("action", "")
            handler = HANDLERS.get(action)
            if handler is None:
                envelope = _build_envelope(ok=False, error=f"Unknown action: {action}")
            else:
                payload = request.get("payload") or {}
                if not isinstance(payload, dict):
                    envelope = _build_envelope(ok=False, error="Request payload must be an object.")
                else:
                    envelope = _capture_envelope(action, handler, payload)
        except json.JSONDecodeError as exc:
            envelope = _build_envelope(ok=False, error=f"Malformed request line: {exc}")
        except Exception as exc:  # pragma: no cover - defensive serve guard
            envelope = _build_envelope(ok=False, error=str(exc), logs=traceback.format_exc())
        envelope["id"] = request_id
        emit(envelope)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        _serve()
    else:
        main()
