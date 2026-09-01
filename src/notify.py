"""Sends new-listing alerts via a plain Telegram Bot API HTTPS call."""

import requests

import config
from src import geo
from src.models import Listing

API_BASE = "https://api.telegram.org"


def _require_credentials() -> None:
    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", config.TELEGRAM_CHAT_ID),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"notify: missing required env var(s): {', '.join(missing)}"
        )


def _format_message(listing: Listing) -> str:
    lines = [listing.title.strip() or "New listing"]

    if listing.price is not None:
        currency = listing.currency or ""
        lines.append(f"Price: {listing.price:,.0f} {currency}".strip())
    if listing.rooms is not None:
        lines.append(f"Rooms: {listing.rooms}")
    if listing.lat is not None and listing.lon is not None:
        distance = geo.distance_from_kgma(listing.lat, listing.lon)
        lines.append(f"Distance from KGMA: {distance:.2f} km")
    if listing.location_text:
        lines.append(listing.location_text[:200])

    lines.append(f"Source: {listing.source}")
    lines.append(listing.url)
    return "\n".join(lines)


def send_listing(listing: Listing) -> None:
    _require_credentials()
    message = _format_message(listing)

    if listing.photo_url:
        endpoint = f"{API_BASE}/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "photo": listing.photo_url,
            "caption": message[:1024],
        }
    else:
        endpoint = f"{API_BASE}/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message}

    response = requests.post(endpoint, json=payload, timeout=15)
    response.raise_for_status()
