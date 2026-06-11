"""Data models for the package tracking feature."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


CARRIER_TRACKING_URLS: Dict[str, str] = {
    "USPS": "https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking}",
    "UPS": "https://www.ups.com/track?loc=en_US&tracknum={tracking}",
    "FEDEX": "https://www.fedex.com/fedextrack/?trknbr={tracking}",
}

STATUS_PENDING = "pending"
STATUS_IN_TRANSIT = "in_transit"
STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
STATUS_DELIVERED = "delivered"
STATUS_EXCEPTION = "exception"
STATUS_UNKNOWN = "unknown"

ACTIVE_STATUSES = {STATUS_PENDING, STATUS_IN_TRANSIT, STATUS_OUT_FOR_DELIVERY}


def normalize_tracking_number(tracking_number: str) -> str:
    """Normalize copied/pasted carrier numbers without destroying carrier prefixes."""
    return re.sub(r"[^0-9A-Z]", "", str(tracking_number or "").upper())


def detect_carrier(tracking_number: str) -> str:
    """Auto-detect carrier from tracking number format.

    The order matters: FedEx Ground numbers often start with 96 and can be the
    same length as USPS numbers, so FedEx-specific patterns must be checked
    before the broad USPS digit-length fallback.
    """
    cleaned = normalize_tracking_number(tracking_number)
    if cleaned.startswith("1Z") and len(cleaned) == 18:
        return "UPS"

    if cleaned.isdigit():
        length = len(cleaned)

        fedex_prefixes = ("612", "748", "96")
        if length == 12:
            return "FEDEX"
        if length == 15 and cleaned.startswith("9"):
            return "FEDEX"
        if length in (20, 22, 26, 30, 34) and cleaned.startswith(fedex_prefixes):
            return "FEDEX"

        usps_prefixes = ("420", "92", "93", "94", "95")
        if length in (20, 22, 26, 30, 34) and cleaned.startswith(usps_prefixes):
            return "USPS"
        if length in (20, 22, 26, 30, 34):
            return "USPS"
        if 12 <= length <= 34:
            return "FEDEX"

    return "UNKNOWN"


def get_tracking_url(carrier: str, tracking_number: str) -> str:
    """Get the carrier tracking URL for a tracking number."""
    template = CARRIER_TRACKING_URLS.get(carrier.upper(), "")
    if template:
        return template.format(tracking=normalize_tracking_number(tracking_number))
    return ""


@dataclass
class StatusTimeline:
    """A single status update in a package's history."""
    timestamp: str = ""
    status: str = STATUS_UNKNOWN
    location: str = ""
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusTimeline":
        return cls(
            timestamp=data.get("timestamp", ""),
            status=data.get("status", STATUS_UNKNOWN),
            location=data.get("location", ""),
            details=data.get("details", ""),
        )


@dataclass
class TrackingEntry:
    """A tracked package."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tracking_number: str = ""
    carrier: str = "UNKNOWN"
    status: str = STATUS_PENDING
    status_details: str = ""
    last_updated: str = ""
    label: str = ""
    store: str = ""
    origin_zip: str = ""
    destination_zip: str = ""
    estimated_delivery: str = ""
    history: List[StatusTimeline] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "manual"
    notification_seen: bool = True

    def __post_init__(self):
        self.tracking_number = normalize_tracking_number(self.tracking_number)
        self.carrier = (self.carrier or "UNKNOWN").upper()
        if self.carrier == "UNKNOWN" and self.tracking_number:
            self.carrier = detect_carrier(self.tracking_number)

    @property
    def tracking_url(self) -> str:
        return get_tracking_url(self.carrier, self.tracking_number)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def status_color(self) -> str:
        """Return a color name for the status (used by UI)."""
        return {
            STATUS_PENDING: "gray",
            STATUS_IN_TRANSIT: "blue",
            STATUS_OUT_FOR_DELIVERY: "orange",
            STATUS_DELIVERED: "green",
            STATUS_EXCEPTION: "red",
        }.get(self.status, "gray")

    @property
    def carrier_icon(self) -> str:
        return {
            "UPS": "brown",
            "USPS": "green",
            "FEDEX": "purple",
        }.get(self.carrier, "gray")

    def add_status(self, status: str, details: str = "", location: str = "") -> None:
        """Add a new status update to the timeline."""
        now = datetime.now().isoformat()
        self.status = status or STATUS_UNKNOWN
        self.status_details = details or ""
        self.last_updated = now
        self.history.append(StatusTimeline(
            timestamp=now,
            status=self.status,
            location=location or "",
            details=self.status_details,
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tracking_number": self.tracking_number,
            "carrier": self.carrier,
            "status": self.status,
            "status_details": self.status_details,
            "last_updated": self.last_updated,
            "label": self.label,
            "store": self.store,
            "origin_zip": self.origin_zip,
            "destination_zip": self.destination_zip,
            "estimated_delivery": self.estimated_delivery,
            "history": [h.to_dict() for h in self.history],
            "created_at": self.created_at,
            "source": self.source,
            "notification_seen": self.notification_seen,
            "tracking_url": self.tracking_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackingEntry":
        history = [StatusTimeline.from_dict(h) for h in data.get("history", []) if isinstance(h, dict)]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            tracking_number=data.get("tracking_number", ""),
            carrier=data.get("carrier", "UNKNOWN"),
            status=data.get("status", STATUS_PENDING),
            status_details=data.get("status_details", ""),
            last_updated=data.get("last_updated", ""),
            label=data.get("label", ""),
            store=data.get("store", ""),
            origin_zip=data.get("origin_zip", ""),
            destination_zip=data.get("destination_zip", ""),
            estimated_delivery=data.get("estimated_delivery", ""),
            history=history,
            created_at=data.get("created_at", datetime.now().isoformat()),
            source=data.get("source", "manual"),
            notification_seen=data.get("notification_seen", True),
        )
