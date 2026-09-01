"""Orchestrates one run: fetch every source -> filter -> dedup -> notify -> save state.

Each source's fetch_all() is isolated in its own try/except: if one source
raises (blocked, credentials missing, network error, whatever), that's
logged clearly and it contributes an empty list for this run instead of
crashing the whole script -- House.kg and Telegram should still produce
notifications even if Lalafo is temporarily blocked, and vice versa.
"""

import sys

import config
from src import dedup, geo, notify
from src.models import Listing
from src.sources import house_kg, lalafo, telegram_channels


def _passes_geo_filter(listing: Listing) -> bool:
    if listing.lat is not None and listing.lon is not None:
        return geo.within_radius(listing.lat, listing.lon)
    return geo.matches_keywords(listing.location_text)


def _passes_price_filter(listing: Listing) -> bool:
    # Soft sanity cap, only enforced when the price is known to be in KGS --
    # USD-priced or unpriced listings pass through rather than guessing a
    # conversion rate.
    if listing.price is None or listing.currency != "KGS":
        return True
    return listing.price <= config.PRICE_CEILING


def _fetch_source(name: str, fetch_all) -> list[Listing]:
    try:
        return fetch_all()
    except Exception as exc:
        print(f"[main] source {name!r} failed, treating as empty: {exc}", file=sys.stderr)
        return []


def fetch_all_listings() -> list[Listing]:
    listings: list[Listing] = []
    listings.extend(_fetch_source("lalafo", lalafo.fetch_all))
    listings.extend(_fetch_source("house_kg", house_kg.fetch_all))
    listings.extend(_fetch_source("telegram", telegram_channels.fetch_all))
    return listings


def main() -> None:
    seen = dedup.load_seen()

    all_listings = fetch_all_listings()
    geo_matched = [listing for listing in all_listings if _passes_geo_filter(listing)]
    price_ok = [listing for listing in geo_matched if _passes_price_filter(listing)]
    new_listings = dedup.filter_new(price_ok, seen)

    print(
        f"[main] fetched={len(all_listings)} geo_matched={len(geo_matched)} "
        f"price_ok={len(price_ok)} new={len(new_listings)}"
    )

    for listing in new_listings:
        notify.send_listing(listing)

    dedup.mark_seen(new_listings, seen)
    dedup.save_seen(seen)


if __name__ == "__main__":
    main()
