"""Package tracking manager with JSON persistence."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ftid_gen.tracking_models import (
    TrackingEntry,
    StatusTimeline,
    detect_carrier,
    get_tracking_url,
    STATUS_PENDING,
    STATUS_DELIVERED,
)


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
            self._entries = {
                item["id"]: TrackingEntry.from_dict(item)
                for item in data.get("entries", [])
                if isinstance(item, dict) and "id" in item
            }
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
                "version": 1,
                "entries": [e.to_dict() for e in self._entries.values()],
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
        """Add a new tracking entry. Raises ValueError if duplicate."""
        with self._lock:
            tracking_number = tracking_number.strip().replace(" ", "").upper()
            if not tracking_number:
                raise ValueError("Tracking number cannot be empty.")

            for existing in self._entries.values():
                if existing.tracking_number == tracking_number:
                    raise ValueError(f"Tracking number {tracking_number} already exists (id: {existing.id}).")

            if carrier == "UNKNOWN" or not carrier:
                carrier = detect_carrier(tracking_number)

            entry = TrackingEntry(
                tracking_number=tracking_number,
                carrier=carrier,
                label=label,
                store=store,
                origin_zip=origin_zip,
                destination_zip=destination_zip,
                estimated_delivery=estimated_delivery,
                source=source,
                status=status,
            )
            entry.add_status(status, details="Tracking added")
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

    def _get_all_unsorted(self) -> List[TrackingEntry]:
        return list(self._entries.values())

    def get_all(self) -> List[TrackingEntry]:
        """Get all tracking entries, newest first."""
        entries = self._get_all_unsorted()
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries

    def get_active(self) -> List[TrackingEntry]:
        """Get only active (non-delivered) entries."""
        return sorted(
            [e for e in self._entries.values() if e.is_active],
            key=lambda e: e.created_at, reverse=True,
        )

    def get_by_carrier(self, carrier: str) -> List[TrackingEntry]:
        """Get entries filtered by carrier."""
        carrier = carrier.upper()
        return sorted(
            [e for e in self._entries.values() if e.carrier == carrier],
            key=lambda e: e.created_at, reverse=True,
        )

    def get_by_status(self, status: str) -> List[TrackingEntry]:
        """Get entries filtered by status."""
        return sorted(
            [e for e in self._entries.values() if e.status == status],
            key=lambda e: e.created_at, reverse=True,
        )

    def search(self, query: str) -> List[TrackingEntry]:
        """Search entries by tracking number, label, or store."""
        query = query.lower().strip()
        if not query:
            return self.get_all()
        return sorted(
            [e for e in self._entries.values()
             if query in e.tracking_number.lower()
             or query in e.label.lower()
             or query in e.store.lower()],
            key=lambda e: e.created_at, reverse=True,
        )

    def update_entry(self, entry_id: str, **kwargs) -> Optional[TrackingEntry]:
        """Update fields on an entry."""
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return None
            for key, value in kwargs.items():
                if hasattr(entry, key) and key not in ("id", "created_at", "history"):
                    setattr(entry, key, value)
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
        """Update the status of an entry and append to timeline."""
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return None
            entry.add_status(status, details=details, location=location)
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

    def import_from_sheet_rows(self, rows: List[Dict[str, Any]]) -> List[TrackingEntry]:
        """Import tracking entries from parsed Google Sheet rows.

        Expected row format matches the user's sheet:
        Action | What | Store | Seller | Total | Payment | Email | Where |
        Method 1 | Tracking | URL | To | From | Tracking 2 | Url 2 |
        Method 2 | Method 3 | Status | Tracking 3
        """
        added = []
        existing = {e.tracking_number for e in self._entries.values()}
        status_map = {
            "delivered": STATUS_DELIVERED,
            "in transit": "in_transit",
            "out for delivery": "out_for_delivery",
            "exception": "exception",
            "pending": STATUS_PENDING,
        }

        with self._lock:
            for row in rows:
                tracking = str(row.get("Tracking") or row.get("tracking") or "").strip()
                if not tracking or not any(c.isdigit() for c in tracking):
                    continue

                tracking = tracking.replace(" ", "").upper()
                if tracking in existing:
                    continue

                what = str(row.get("What") or row.get("what") or "").strip()
                store = str(row.get("Store") or row.get("store") or "").strip()
                seller = str(row.get("Seller") or row.get("seller") or "").strip()
                store_label = f"{store} - {seller}" if seller else store

                method1 = str(row.get("Method 1") or row.get("method_1") or "").strip().upper()
                carrier = detect_carrier(tracking)
                if method1 in ("UPS", "USPS", "FEDEX"):
                    carrier = method1

                to_zip = str(row.get("To") or row.get("to") or "").strip()
                from_zip = str(row.get("From") or row.get("from") or "").strip()
                status_raw = str(row.get("Status") or row.get("status") or "").strip().lower()
                status = status_map.get(status_raw, STATUS_PENDING)

                entry = TrackingEntry(
                    tracking_number=tracking,
                    carrier=carrier,
                    label=what,
                    store=store_label,
                    origin_zip=from_zip,
                    destination_zip=to_zip,
                    source="sheet_import",
                    status=status,
                )
                entry.add_status(status, details="Imported from sheet")
                self._entries[entry.id] = entry
                added.append(entry)
                existing.add(tracking)

                for num, suffix in [("Tracking 2", " (2nd)"), ("Tracking 3", " (3rd)")]:
                    tracking_n = str(row.get(num) or "").strip()
                    if tracking_n and any(c.isdigit() for c in tracking_n):
                        tracking_n = tracking_n.replace(" ", "").upper()
                        if tracking_n not in existing:
                            method_n = str(row.get(f"Method {'2' if num == 'Tracking 2' else '3'}") or "").strip().upper()
                            carrier_n = detect_carrier(tracking_n)
                            if method_n in ("UPS", "USPS", "FEDEX"):
                                carrier_n = method_n
                            entry_n = TrackingEntry(
                                tracking_number=tracking_n,
                                carrier=carrier_n,
                                label=f"{what}{suffix}" if what else "",
                                store=store_label,
                                origin_zip=from_zip,
                                destination_zip=to_zip,
                                source="sheet_import",
                            )
                            entry_n.add_status(STATUS_PENDING, details="Imported from sheet")
                            self._entries[entry_n.id] = entry_n
                            added.append(entry_n)
                            existing.add(tracking_n)

            if added:
                self._save()

        return added

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
            "exception": by_status.get("exception", 0),
            "by_carrier": by_carrier,
            "by_status": by_status,
        }


# Global instance
tracking_manager = TrackingManager()
