"""Package tracking manager with JSON persistence."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterable, Tuple

from ftid_gen.tracking_models import (
    TrackingEntry,
    StatusTimeline,
    detect_carrier,
    normalize_tracking_number,
    STATUS_PENDING,
    STATUS_DELIVERED,
    STATUS_IN_TRANSIT,
    STATUS_OUT_FOR_DELIVERY,
    STATUS_EXCEPTION,
    STATUS_UNKNOWN,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_status(value: Any) -> str:
    raw = _clean_text(value).lower().replace("-", " ").replace("_", " ")
    status_map = {
        "delivered": STATUS_DELIVERED,
        "complete": STATUS_DELIVERED,
        "completed": STATUS_DELIVERED,
        "in transit": STATUS_IN_TRANSIT,
        "transit": STATUS_IN_TRANSIT,
        "shipped": STATUS_IN_TRANSIT,
        "out for delivery": STATUS_OUT_FOR_DELIVERY,
        "exception": STATUS_EXCEPTION,
        "alert": STATUS_EXCEPTION,
        "returned": STATUS_EXCEPTION,
        "return to sender": STATUS_EXCEPTION,
        "pending": STATUS_PENDING,
        "label created": STATUS_PENDING,
        "pre shipment": STATUS_PENDING,
        "pre-shipment": STATUS_PENDING,
        "unknown": STATUS_UNKNOWN,
    }
    return status_map.get(raw, STATUS_PENDING if not raw else raw.replace(" ", "_"))


class TrackingManager:
    """Manages tracking entries with local JSON persistence."""

    def __init__(self, storage_file: str = "tracking_data.json"):
        self.storage_file = storage_file
        self._entries: Dict[str, TrackingEntry] = {}
        self._lock = threading.Lock()
        self._load()

    def _resolve_path(self) -> Path:
        if os.path.isabs(self.storage_file):
            return Path(self.storage_file)
        state_dir = os.environ.get("FTID_STATE_DIR", "")
        if state_dir:
            return Path(state_dir) / self.storage_file
        return Path(__file__).resolve().parent.parent / self.storage_file

    def _load(self) -> None:
        path = self._resolve_path()
        if not path.exists():
            self._entries = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries: Dict[str, TrackingEntry] = {}
            for item in data.get("entries", []):
                if not isinstance(item, dict):
                    continue
                entry = TrackingEntry.from_dict(item)
                if entry.id:
                    entries[entry.id] = entry
            self._entries = entries
        except Exception:
            backup_path = path.with_suffix(f".corrupt.{int(datetime.now().timestamp())}.json")
            try:
                shutil.copy2(path, backup_path)
            except Exception:
                pass
            print(f"Warning: Tracking data corrupt. Backup saved to {backup_path}. Starting fresh.")
            self._entries = {}

    def _save(self) -> None:
        path = self._resolve_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 2,
                "saved_at": _now_iso(),
                "entries": [e.to_dict() for e in self.get_all()],
            }
            fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, str(path))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise
            backup = path.with_suffix(".backup.json")
            try:
                shutil.copy2(path, backup)
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: Could not save tracking data: {e}")

    def _find_existing_by_tracking(self, tracking_number: str) -> Optional[TrackingEntry]:
        normalized = normalize_tracking_number(tracking_number)
        for existing in self._entries.values():
            if existing.tracking_number == normalized:
                return existing
        return None

    @staticmethod
    def _merge_optional_fields(entry: TrackingEntry, **kwargs: Any) -> bool:
        changed = False
        for key, value in kwargs.items():
            if value is None or key in ("id", "created_at", "history", "status"):
                continue
            if not hasattr(entry, key):
                continue
            cleaned_value = _clean_text(value) if isinstance(value, str) else value
            if cleaned_value == "":
                continue
            if getattr(entry, key) != cleaned_value:
                setattr(entry, key, cleaned_value)
                changed = True
        return changed

    @staticmethod
    def _sort_key(entry: TrackingEntry) -> Tuple[str, str]:
        return (entry.last_updated or entry.created_at or "", entry.created_at or "")

    def add_entry(
        self,
        tracking_number: str,
        carrier: str = "UNKNOWN",
        label: str = "",
        store: str = "",
        origin_zip: str = "",
        destination_zip: str = "",
        estimated_delivery: str = "",
        source: str = "manual",
        status: str = STATUS_PENDING,
    ) -> TrackingEntry:
        """Add a tracking entry, merging metadata when the number already exists."""
        with self._lock:
            tracking_number = normalize_tracking_number(tracking_number)
            if not tracking_number:
                raise ValueError("Tracking number cannot be empty.")

            carrier = (carrier or "UNKNOWN").upper()
            if carrier == "UNKNOWN":
                carrier = detect_carrier(tracking_number)

            existing = self._find_existing_by_tracking(tracking_number)
            if existing:
                changed = self._merge_optional_fields(
                    existing,
                    carrier=carrier if carrier != "UNKNOWN" else "",
                    label=label,
                    store=store,
                    origin_zip=origin_zip,
                    destination_zip=destination_zip,
                    estimated_delivery=estimated_delivery,
                    source=source,
                )
                if status and status != existing.status:
                    existing.add_status(_canonical_status(status), details="Tracking metadata updated")
                    existing.notification_seen = False
                    changed = True
                if changed:
                    self._save()
                return existing

            entry = TrackingEntry(
                tracking_number=tracking_number,
                carrier=carrier,
                label=_clean_text(label),
                store=_clean_text(store),
                origin_zip=_clean_text(origin_zip),
                destination_zip=_clean_text(destination_zip),
                estimated_delivery=_clean_text(estimated_delivery),
                source=_clean_text(source) or "manual",
                status=_canonical_status(status),
            )
            entry.add_status(entry.status, details="Tracking added")
            self._entries[entry.id] = entry
            self._save()
            return entry

    def remove_entry(self, entry_id: str) -> bool:
        """Remove a tracking entry by ID."""
        with self._lock:
            if entry_id in self._entries:
                del self._entries[entry_id]
                self._save()
                return True
            return False

    def get_entry(self, entry_id: str) -> Optional[TrackingEntry]:
        """Get a single entry by ID."""
        return self._entries.get(entry_id)

    def get_by_tracking_number(self, tracking_number: str) -> Optional[TrackingEntry]:
        """Get a single entry by tracking number."""
        return self._find_existing_by_tracking(tracking_number)

    def _get_all_unsorted(self) -> List[TrackingEntry]:
        return list(self._entries.values())

    def get_all(self) -> List[TrackingEntry]:
        """Get all tracking entries, most recently updated first."""
        entries = self._get_all_unsorted()
        entries.sort(key=self._sort_key, reverse=True)
        return entries

    def get_active(self) -> List[TrackingEntry]:
        """Get only active (non-delivered) entries."""
        return sorted(
            [e for e in self._entries.values() if e.is_active],
            key=self._sort_key,
            reverse=True,
        )

    def get_by_carrier(self, carrier: str) -> List[TrackingEntry]:
        """Get entries filtered by carrier."""
        carrier = carrier.upper()
        return sorted(
            [e for e in self._entries.values() if e.carrier == carrier],
            key=self._sort_key,
            reverse=True,
        )

    def get_by_status(self, status: str) -> List[TrackingEntry]:
        """Get entries filtered by status."""
        normalized_status = _canonical_status(status)
        return sorted(
            [e for e in self._entries.values() if e.status == normalized_status],
            key=self._sort_key,
            reverse=True,
        )

    def search(self, query: str) -> List[TrackingEntry]:
        """Search entries by tracking number, label, store, route, status, or details."""
        query = query.lower().strip()
        if not query:
            return self.get_all()

        def haystack(entry: TrackingEntry) -> str:
            parts = [
                entry.tracking_number,
                entry.carrier,
                entry.status,
                entry.status_details,
                entry.label,
                entry.store,
                entry.origin_zip,
                entry.destination_zip,
                entry.estimated_delivery,
                entry.source,
            ]
            parts.extend([h.location for h in entry.history])
            parts.extend([h.details for h in entry.history])
            return " ".join(p for p in parts if p).lower()

        return sorted(
            [e for e in self._entries.values() if query in haystack(e)],
            key=self._sort_key,
            reverse=True,
        )

    def update_entry(self, entry_id: str, **kwargs) -> Optional[TrackingEntry]:
        """Update fields on an entry."""
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return None
            changed = self._merge_optional_fields(entry, **kwargs)
            if "status" in kwargs and kwargs["status"]:
                normalized_status = _canonical_status(kwargs["status"])
                if normalized_status != entry.status:
                    entry.add_status(normalized_status, details=kwargs.get("status_details", "Status updated"))
                    entry.notification_seen = False
                    changed = True
            if changed:
                self._save()
            return entry

    def update_status(
        self,
        entry_id: str,
        status: str,
        details: str = "",
        location: str = "",
        estimated_delivery: str = "",
    ) -> Optional[TrackingEntry]:
        """Update the status of an entry and append to timeline when anything changes."""
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return None

            normalized_status = _canonical_status(status)
            details = _clean_text(details)
            location = _clean_text(location)
            estimated_delivery = _clean_text(estimated_delivery)

            previous_location = entry.history[-1].location if entry.history else ""
            changed = (
                normalized_status != entry.status
                or details != entry.status_details
                or (location and location != previous_location)
                or (estimated_delivery and estimated_delivery != entry.estimated_delivery)
            )

            if not changed:
                return None

            entry.add_status(normalized_status, details=details, location=location)
            if estimated_delivery:
                entry.estimated_delivery = estimated_delivery
            entry.notification_seen = False
            self._save()
            return entry

    def mark_notification_seen(self, entry_id: str) -> None:
        """Mark an entry's notification as seen."""
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.notification_seen = True
                self._save()

    def get_unseen_count(self) -> int:
        """Get count of entries with unseen status changes."""
        return sum(1 for e in self._entries.values() if not e.notification_seen)

    @staticmethod
    def _value(row: Dict[str, Any], *names: str) -> str:
        lower_map = {str(k).strip().lower(): v for k, v in row.items()}
        for name in names:
            if name in row and _clean_text(row.get(name)):
                return _clean_text(row.get(name))
            lowered = name.strip().lower()
            if lowered in lower_map and _clean_text(lower_map[lowered]):
                return _clean_text(lower_map[lowered])
        return ""

    @staticmethod
    def _tracking_columns() -> Iterable[Tuple[str, str, str]]:
        return (
            ("Tracking", "Method 1", ""),
            ("Tracking 1", "Method 1", ""),
            ("tracking_number", "carrier", ""),
            ("Tracking 2", "Method 2", " (2nd)"),
            ("Tracking 3", "Method 3", " (3rd)"),
        )

    def import_from_sheet_rows(self, rows: List[Dict[str, Any]]) -> List[TrackingEntry]:
        """Import tracking entries from parsed Google Sheet rows.

        Expected row format matches the user's sheet:
        Action | What | Store | Seller | Total | Payment | Email | Where |
        Method 1 | Tracking | URL | To | From | Tracking 2 | Url 2 |
        Method 2 | Method 3 | Status | Tracking 3
        """
        added_or_updated: List[TrackingEntry] = []

        with self._lock:
            for row in rows:
                if not isinstance(row, dict):
                    continue

                what = self._value(row, "What", "what", "Label", "label")
                store = self._value(row, "Store", "store")
                seller = self._value(row, "Seller", "seller")
                store_label = " - ".join(part for part in [store, seller] if part)
                to_zip = self._value(row, "To", "to", "destination_zip", "Destination ZIP")
                from_zip = self._value(row, "From", "from", "origin_zip", "Origin ZIP")
                status = _canonical_status(self._value(row, "Status", "status"))

                for tracking_column, method_column, suffix in self._tracking_columns():
                    tracking = normalize_tracking_number(self._value(row, tracking_column))
                    if not tracking or not any(c.isdigit() for c in tracking):
                        continue

                    method = self._value(row, method_column).upper()
                    carrier = method if method in ("UPS", "USPS", "FEDEX") else detect_carrier(tracking)
                    label = f"{what}{suffix}" if what else suffix.strip()

                    existing = self._find_existing_by_tracking(tracking)
                    if existing:
                        changed = self._merge_optional_fields(
                            existing,
                            carrier=carrier,
                            label=label,
                            store=store_label,
                            origin_zip=from_zip,
                            destination_zip=to_zip,
                            source="sheet_import",
                        )
                        if status and status != existing.status:
                            existing.add_status(status, details="Updated from sheet")
                            existing.notification_seen = False
                            changed = True
                        if changed:
                            added_or_updated.append(existing)
                        continue

                    entry = TrackingEntry(
                        tracking_number=tracking,
                        carrier=carrier,
                        label=label,
                        store=store_label,
                        origin_zip=from_zip,
                        destination_zip=to_zip,
                        source="sheet_import",
                        status=status,
                    )
                    entry.add_status(status, details="Imported from sheet")
                    self._entries[entry.id] = entry
                    added_or_updated.append(entry)

            if added_or_updated:
                self._save()

        return added_or_updated

    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        all_entries = self._get_all_unsorted()
        by_carrier: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for e in all_entries:
            by_carrier[e.carrier] = by_carrier.get(e.carrier, 0) + 1
            by_status[e.status] = by_status.get(e.status, 0) + 1
        return {
            "total": len(all_entries),
            "active": sum(1 for e in all_entries if e.is_active),
            "delivered": by_status.get(STATUS_DELIVERED, 0),
            "exception": by_status.get(STATUS_EXCEPTION, 0),
            "by_carrier": by_carrier,
            "by_status": by_status,
            "unseen": self.get_unseen_count(),
        }


# Global instance
tracking_manager = TrackingManager()
