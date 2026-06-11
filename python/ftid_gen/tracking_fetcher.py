"""Tracking status fetcher with web scraping and API fallback."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

from ftid_gen.tracking_models import (
    TrackingEntry,
    STATUS_PENDING,
    STATUS_IN_TRANSIT,
    STATUS_OUT_FOR_DELIVERY,
    STATUS_DELIVERED,
    STATUS_EXCEPTION,
    STATUS_UNKNOWN,
)

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "usps": {
        "delivered": STATUS_DELIVERED,
        "out for delivery": STATUS_OUT_FOR_DELIVERY,
        "in transit": STATUS_IN_TRANSIT,
        "acceptance": STATUS_IN_TRANSIT,
        "processed": STATUS_IN_TRANSIT,
        "arrived": STATUS_IN_TRANSIT,
        "departure": STATUS_IN_TRANSIT,
        "label created": STATUS_PENDING,
        "pre-shipment": STATUS_PENDING,
        "exception": STATUS_EXCEPTION,
        "alert": STATUS_EXCEPTION,
        "returned": STATUS_EXCEPTION,
    },
    "ups": {
        "delivered": STATUS_DELIVERED,
        "out for delivery": STATUS_OUT_FOR_DELIVERY,
        "in transit": STATUS_IN_TRANSIT,
        "pickup": STATUS_IN_TRANSIT,
        "origin scan": STATUS_IN_TRANSIT,
        "departure scan": STATUS_IN_TRANSIT,
        "arrival scan": STATUS_IN_TRANSIT,
        "label created": STATUS_PENDING,
        "exception": STATUS_EXCEPTION,
        "return to sender": STATUS_EXCEPTION,
    },
    "fedex": {
        "delivered": STATUS_DELIVERED,
        "out for delivery": STATUS_OUT_FOR_DELIVERY,
        "in transit": STATUS_IN_TRANSIT,
        "picked up": STATUS_IN_TRANSIT,
        "at facility": STATUS_IN_TRANSIT,
        "departed": STATUS_IN_TRANSIT,
        "arrived": STATUS_IN_TRANSIT,
        "label created": STATUS_PENDING,
        "exception": STATUS_EXCEPTION,
        "return": STATUS_EXCEPTION,
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalize_status(carrier: str, raw_status: str) -> str:
    carrier = carrier.lower()
    raw_lower = raw_status.lower().strip()
    mapping = STATUS_MAP.get(carrier, {})
    for key, normalized in mapping.items():
        if key in raw_lower:
            return normalized
    return STATUS_UNKNOWN


class TrackingFetcher:
    """Fetches tracking status from carrier websites and APIs."""

    def __init__(self, cache_ttl_minutes: int = 15):
        self._cache_ttl = cache_ttl_minutes * 60
        self._cache_path = self._resolve_cache_path()

    def _resolve_cache_path(self) -> Path:
        state_dir = os.environ.get("FTID_STATE_DIR", "")
        if state_dir:
            return Path(state_dir) / "tracking_cache.json"
        return Path(__file__).resolve().parent.parent / "tracking_cache.json"

    def _load_cache(self) -> Dict[str, Any]:
        if not self._cache_path.exists():
            return {}
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cache(self, cache: Dict[str, Any]) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _get_cached(self, tracking: str) -> Optional[Dict[str, Any]]:
        cache = self._load_cache()
        entry = cache.get(tracking)
        if entry:
            age = time.time() - entry.get("timestamp", 0)
            if age < self._cache_ttl:
                return entry.get("data")
        return None

    def _set_cache(self, tracking: str, data: Dict[str, Any]) -> None:
        cache = self._load_cache()
        cache[tracking] = {"data": data, "timestamp": time.time()}
        self._save_cache(cache)

    def fetch_status(self, entry: TrackingEntry) -> Optional[Dict[str, Any]]:
        """Fetch the current status for a tracking entry.

        Returns dict with keys: status, details, location, estimated_delivery
        """
        cached = self._get_cached(entry.tracking_number)
        if cached:
            return cached

        result = None
        carrier = entry.carrier.upper()

        try:
            if carrier == "USPS":
                result = self._fetch_usps(entry.tracking_number)
            elif carrier == "UPS":
                result = self._fetch_ups(entry.tracking_number)
            elif carrier == "FEDEX":
                result = self._fetch_fedex(entry.tracking_number)
        except Exception as e:
            logger.warning("Error fetching status for %s: %s", entry.tracking_number, e)

        if result:
            self._set_cache(entry.tracking_number, result)

        return result

    def _fetch_usps(self, tracking: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking}"
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            text = resp.text

            json_match = re.search(r'var\s+trackingResults\s*=\s*(\[.*?\]);', text, re.DOTALL)
            if json_match:
                results = json.loads(json_match.group(1))
                if results:
                    latest = results[0]
                    raw_status = latest.get("status", "")
                    return {
                        "status": _normalize_status("usps", raw_status),
                        "details": raw_status,
                        "location": latest.get("location", ""),
                        "estimated_delivery": latest.get("estimatedDelivery", ""),
                    }

            status_match = re.search(r'class="tracking-status[^"]*"[^>]*>([^<]+)<', text)
            if status_match:
                raw_status = status_match.group(1).strip()
                return {
                    "status": _normalize_status("usps", raw_status),
                    "details": raw_status,
                    "location": "",
                    "estimated_delivery": "",
                }

            meta_match = re.search(r'"status"\s*:\s*"([^"]+)"', text)
            if meta_match:
                raw_status = meta_match.group(1)
                return {
                    "status": _normalize_status("usps", raw_status),
                    "details": raw_status,
                    "location": "",
                    "estimated_delivery": "",
                }

        except requests.RequestException as e:
            logger.warning("USPS fetch failed for %s: %s", tracking, e)

        return None

    def _fetch_ups(self, tracking: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"https://www.ups.com/track?loc=en_US&tracknum={tracking}"
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            text = resp.text

            ld_match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', text, re.DOTALL)
            if ld_match:
                ld_data = json.loads(ld_match.group(1))
                if isinstance(ld_data, dict):
                    delivery_status = ld_data.get("deliveryStatus", "")
                    if delivery_status:
                        return {
                            "status": _normalize_status("ups", delivery_status),
                            "details": delivery_status,
                            "location": ld_data.get("deliveryLocation", ""),
                            "estimated_delivery": ld_data.get("expectedDelivery", ""),
                        }

            status_match = re.search(r'"packageStatus"\s*:\s*"([^"]+)"', text)
            if status_match:
                raw_status = status_match.group(1)
                return {
                    "status": _normalize_status("ups", raw_status),
                    "details": raw_status,
                    "location": "",
                    "estimated_delivery": "",
                }

        except requests.RequestException as e:
            logger.warning("UPS web fetch failed for %s: %s", tracking, e)

        return self._fetch_ups_api(tracking)

    def _fetch_ups_api(self, tracking: str) -> Optional[Dict[str, Any]]:
        try:
            from ftid_gen.settings_manager import settings
            api_key = settings.get("tracking.ups_api_key", "")
            if not api_key:
                return None

            url = f"https://onlinetools.ups.com/api/track/v1/details/{tracking}"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            track_result = data.get("trackResponse", {}).get("shipment", [{}])[0]
            package = track_result.get("package", [{}])[0]
            activity = package.get("activity", [{}])
            if activity:
                latest = activity[0]
                raw_status = latest.get("status", {}).get("description", "")
                location = latest.get("location", {})
                loc_str = f"{location.get('city', '')}, {location.get('state', '')}".strip(", ")
                return {
                    "status": _normalize_status("ups", raw_status),
                    "details": raw_status,
                    "location": loc_str,
                    "estimated_delivery": "",
                }

        except Exception as e:
            logger.warning("UPS API fetch failed for %s: %s", tracking, e)

        return None

    def _fetch_fedex(self, tracking: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"https://www.fedex.com/fedextrack/?trknbr={tracking}"
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            text = resp.text

            status_match = re.search(r'"statusCode"\s*:\s*"([^"]+)"', text)
            desc_match = re.search(r'"statusDescription"\s*:\s*"([^"]+)"', text)
            if status_match:
                raw_status = desc_match.group(1) if desc_match else status_match.group(1)
                return {
                    "status": _normalize_status("fedex", raw_status),
                    "details": raw_status,
                    "location": "",
                    "estimated_delivery": "",
                }

            fedex_status = re.search(r'"scanEvent"\s*:\s*\{[^}]*"eventDescription"\s*:\s*"([^"]+)"', text)
            if fedex_status:
                raw_status = fedex_status.group(1)
                return {
                    "status": _normalize_status("fedex", raw_status),
                    "details": raw_status,
                    "location": "",
                    "estimated_delivery": "",
                }

        except requests.RequestException as e:
            logger.warning("FedEx web fetch failed for %s: %s", tracking, e)

        return self._fetch_fedex_api(tracking)

    def _fetch_fedex_api(self, tracking: str) -> Optional[Dict[str, Any]]:
        try:
            from ftid_gen.settings_manager import settings
            api_key = settings.get("tracking.fedex_api_key", "")
            api_secret = settings.get("tracking.fedex_api_secret", "")
            if not api_key or not api_secret:
                return None

            auth_url = "https://apis.fedex.com/oauth/token"
            auth_resp = requests.post(auth_url, data={
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": api_secret,
            }, timeout=15)
            auth_resp.raise_for_status()
            token = auth_resp.json().get("access_token", "")

            track_url = "https://apis.fedex.com/track/v1/trackingnumbers"
            track_resp = requests.post(
                track_url,
                json={"includeDetailedScans": False, "trackingInfo": [{"trackingNumberInfo": {"trackingNumber": tracking}}]},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=15,
            )
            track_resp.raise_for_status()
            data = track_resp.json()

            result = data.get("output", {}).get("completeTrackResults", [{}])[0]
            track_detail = result.get("trackResults", [{}])[0]
            latest = track_detail.get("latestStatusDetail", {})
            raw_status = latest.get("statusDescription", "")
            location = latest.get("scanLocation", {})
            loc_str = f"{location.get('city', '')}, {location.get('state', '')}".strip(", ") if location else ""

            return {
                "status": _normalize_status("fedex", raw_status),
                "details": raw_status,
                "location": loc_str,
                "estimated_delivery": track_detail.get("estimatedDeliveryTimeWindow", {}).get("window", {}).get("ends", ""),
            }

        except Exception as e:
            logger.warning("FedEx API fetch failed for %s: %s", tracking, e)

        return None


# Global instance
tracking_fetcher = TrackingFetcher()
