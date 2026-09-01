"""House.kg source: classic server-rendered HTML, not a client-fetched API.

Unlike lalafo.kg, house.kg's search results page (/snyat-kvartiru) ships no
__NEXT_DATA__ or other JSON blob -- it's PHP-rendered HTML. Each listing card
is a `<div itemscope itemtype="https://schema.org/Apartment">` with schema.org
microdata (<meta itemprop="...">) for id/rooms/photo/description, so that's
parsed directly instead of guessing at CSS classes.

No per-listing coordinates exist anywhere on this page (checked: the only
lat/lng present is a `regionsAndTowns` JS tree of district/microdistrict
centroids for the site's own filter UI, not per-ad). So, same as the Telegram
source, filtering here always falls back to district-keyword matching via
geo.matches_keywords(listing.location_text) in main.py.

Query params (found via the search form's hidden inputs):
  rooms=N          -- room count (1, 2, 3, ...)
  rental_term=3     -- "помесячно" (monthly); excludes hourly/daily-rate ads
  town=2            -- Bishkek
  page=N            -- 1-indexed pagination
"""

import re
import time

import requests
from bs4 import BeautifulSoup

from src.models import Listing

SOURCE = "house_kg"
BASE_URL = "https://www.house.kg"
SEARCH_URL = f"{BASE_URL}/snyat-kvartiru"
USER_AGENT = "rental-monitor-bot/1.0 (personal apartment search script)"

RENTAL_TERM_MONTHLY = 3
TOWN_BISHKEK = 2
CATEGORY_ROOMS = {1, 2, 3}

REQUEST_DELAY_SECONDS = 1.0  # be polite between page fetches

LISTING_ID_RE = re.compile(r"-(\d+)$")


def _fetch_html(rooms: int, page: int) -> str:
    response = requests.get(
        SEARCH_URL,
        params={
            "rooms": rooms,
            "rental_term": RENTAL_TERM_MONTHLY,
            "town": TOWN_BISHKEK,
            "page": page,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    return response.text


def _parse_price(card) -> tuple[float | None, str | None]:
    """Site always shows a USD "main" price with a KGS ("сом") addition, at
    least in testing -- prefer the KGS figure since config.PRICE_CEILING is
    in KGS; fall back to whatever the primary price is if KGS isn't present.
    """
    main = card.select_one("div.sep.main")
    if main is None:
        return None, None

    price_el = main.select_one("div.price")
    addition_el = main.select_one("div.price-addition")
    price_text = price_el.get_text(strip=True) if price_el else ""
    addition_text = addition_el.get_text(strip=True) if addition_el else ""

    for text in (price_text, addition_text):
        if "сом" in text:
            digits = re.sub(r"[^\d]", "", text)
            return (float(digits) if digits else None), "KGS"

    match = re.match(r"\$\s*([\d\s]+)", price_text)
    if match:
        return float(match.group(1).replace(" ", "")), "USD"
    return None, None


def _parse_cards(html: str, rooms: int) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.find_all("div", itemtype="https://schema.org/Apartment"):
        url_meta = card.find("meta", itemprop="url")
        if url_meta is None:
            continue
        href = url_meta.get("content", "")
        match = LISTING_ID_RE.search(href)
        if not match:
            continue
        listing_id = match.group(1)

        title_el = card.select_one("p.title a")
        title = title_el.get_text(strip=True) if title_el else ""

        address_el = card.select_one("div.address")
        address = address_el.get_text(" ", strip=True) if address_el else ""

        description_meta = card.find("meta", itemprop="description")
        description = description_meta.get("content", "") if description_meta else ""

        photo_meta = card.find("meta", itemprop="photo")
        photo_url = photo_meta.get("content") if photo_meta else None

        price, currency = _parse_price(card)
        location_text = " ".join(part for part in (title, address, description) if part)

        listings.append(
            Listing(
                source=SOURCE,
                id=listing_id,
                title=title,
                url=BASE_URL + href,
                price=price,
                currency=currency,
                rooms=rooms,
                lat=None,
                lon=None,
                photo_url=photo_url,
                location_text=location_text,
            )
        )
    return listings


def fetch_listings(rooms: int, max_pages: int = 3) -> list[Listing]:
    """Fetch and normalize monthly-rental listings for a given room count."""
    if rooms not in CATEGORY_ROOMS:
        raise ValueError(f"Unsupported room count: {rooms}")

    all_listings: list[Listing] = []
    page = 1
    while page <= max_pages:
        html = _fetch_html(rooms, page)
        listings = _parse_cards(html, rooms)
        if not listings:
            break  # no pagination metadata on this site; empty page means done
        all_listings.extend(listings)
        page += 1
        if page <= max_pages:
            time.sleep(REQUEST_DELAY_SECONDS)

    return all_listings


def fetch_all(max_pages: int = 3) -> list[Listing]:
    """Fetch listings across all tracked room counts (1, 2, 3)."""
    listings = []
    for rooms in sorted(CATEGORY_ROOMS):
        listings.extend(fetch_listings(rooms, max_pages=max_pages))
        time.sleep(REQUEST_DELAY_SECONDS)
    return listings


if __name__ == "__main__":
    for rooms in (1, 2):
        results = fetch_listings(rooms, max_pages=1)
        print(f"-- {rooms}-room: {len(results)} listings --")
        for listing in results[:5]:
            print(
                f"  [{listing.id}] {listing.price} {listing.currency} | "
                f"{listing.title[:40]!r} | {listing.location_text[:60]!r} | {listing.url}"
            )
        print()
