"""Geocoding (one-time) and distance/keyword filtering (every run).

Run `python -m src.geo` once from the repo root to geocode config.KGMA_ADDRESS
and print lat/lon to paste into config.py. Don't call geocode() on every run --
that's why it's separated from the filter functions below.
"""

import math

import requests

import config

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "rental-monitor-bot/1.0 (personal apartment search script)"


def geocode(query: str) -> tuple[float, float]:
    """Look up (lat, lon) for a free-text address via Nominatim (OSM)."""
    response = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise ValueError(f"No geocoding results for query: {query!r}")
    return float(results[0]["lat"]), float(results[0]["lon"])


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in km."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def distance_from_kgma(lat: float, lon: float) -> float:
    """Distance in km from a listing's coordinates to KGMA."""
    return haversine(lat, lon, config.KGMA_LAT, config.KGMA_LON)


def within_radius(lat: float, lon: float) -> bool:
    """True if a listing's coordinates are within config.RADIUS_KM of KGMA."""
    return distance_from_kgma(lat, lon) <= config.RADIUS_KM


def matches_keywords(text: str) -> bool:
    """True if text mentions any of config.DISTRICT_KEYWORDS (case-insensitive).

    For Telegram posts, which have no coordinates.
    """
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in config.DISTRICT_KEYWORDS)


if __name__ == "__main__":
    lat, lon = geocode(config.KGMA_ADDRESS)
    print(f"KGMA_LAT = {lat}")
    print(f"KGMA_LON = {lon}")
    print("Paste these two values into config.py.")
