"""Shared data shape that every source normalizes its listings into."""

from dataclasses import dataclass


@dataclass
class Listing:
    source: str
    id: str
    title: str
    url: str
    price: float | None = None
    currency: str | None = None
    rooms: int | None = None
    lat: float | None = None
    lon: float | None = None
    photo_url: str | None = None
    # Title + description + district text, for keyword matching when lat/lon
    # isn't available (see geo.matches_keywords).
    location_text: str = ""
