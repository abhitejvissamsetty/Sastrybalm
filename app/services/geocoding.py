"""
Geocoding service — Uses OpenStreetMap Nominatim for reverse geocoding.
Given GPS coordinates, returns address and pincode.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "SastrybalmSFA/1.0"


async def reverse_geocode(lat: float, lng: float) -> dict:
    """
    Reverse geocode GPS coordinates to an address using Nominatim.
    Returns: {"address": str, "pincode": str|None, "city": str|None, "state": str|None}
    """
    params = {
        "lat": lat,
        "lon": lng,
        "format": "json",
        "addressdetails": 1,
        "zoom": 18,
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        addr = data.get("address", {})
        display_name = data.get("display_name", "")

        return {
            "address": display_name,
            "pincode": addr.get("postcode"),
            "city": addr.get("city") or addr.get("town") or addr.get("village"),
            "state": addr.get("state"),
            "country": addr.get("country"),
        }
    except Exception as exc:
        logger.warning("Reverse geocoding failed for (%s, %s): %s", lat, lng, exc)
        return {"address": "", "pincode": None, "city": None, "state": None, "country": None}
