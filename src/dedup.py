"""Load/save state/seen_ids.json: "{source}:{listing_id}" -> first_seen timestamp."""

import json
import os
import time

import config
from src.models import Listing


def load_seen() -> dict[str, float]:
    if not os.path.exists(config.STATE_FILE):
        return {}
    with open(config.STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen: dict[str, float]) -> None:
    os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)


def _key(listing: Listing) -> str:
    return f"{listing.source}:{listing.id}"


def filter_new(listings: list[Listing], seen: dict[str, float]) -> list[Listing]:
    return [listing for listing in listings if _key(listing) not in seen]


def mark_seen(listings: list[Listing], seen: dict[str, float]) -> None:
    now = time.time()
    for listing in listings:
        seen.setdefault(_key(listing), now)
