"""Shared IP geolocation utilities for user tracking."""

import requests
from typing import Dict


def get_ip_info() -> Dict[str, str]:
    """Get detailed IP and location information."""
    try:
        response = requests.get("https://ipinfo.io/json", timeout=10)
        data = response.json()
        loc = data.get("loc", "0,0")

        approx_address = get_address_from_coords(loc)

        return {
            "ip": data.get("ip", "N/A"),
            "city": data.get("city", "N/A"),
            "region": data.get("region", "N/A"),
            "country": data.get("country", "N/A"),
            "postal": data.get("postal", "N/A"),
            "org": data.get("org", "N/A"),
            "loc": loc,
            "timezone": data.get("timezone", "N/A"),
            "approx_address": approx_address
        }
    except Exception as e:
        print(f"❌ IP info fetch error: {e}")
        return {
            "ip": "N/A", "city": "N/A", "region": "N/A",
            "country": "N/A", "postal": "N/A", "org": "N/A",
            "loc": "N/A", "timezone": "N/A", "approx_address": "N/A"
        }


def get_address_from_coords(loc: str) -> str:
    """Convert coordinates to approximate address via reverse geocoding."""
    try:
        if loc == "N/A" or "," not in loc:
            return "N/A"
        lat, lon = loc.split(",")
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
        headers = {"User-Agent": "ftid-tracker/1.0"}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        return data.get("display_name", "N/A")
    except Exception as e:
        print(f"❌ Reverse geocoding error: {e}")
        return "N/A"
