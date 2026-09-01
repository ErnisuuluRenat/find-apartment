"""Lalafo.kg source: server-rendered category pages, not a client-fetched API.

Each category page (e.g. .../1-bedroom) ships a `<script id="__NEXT_DATA__">`
JSON blob containing a dehydrated React Query cache. The `listingFeed` query in
that cache holds the actual ad objects -- title, price, coordinates, images --
so that's parsed directly instead of scraping rendered card markup. Most ads
carry `lat`/`lng`, so district-keyword matching (see geo.matches_keywords) is
only a fallback for the rare ad missing coordinates, or for the HTML-card
fallback path below if lalafo ever stops shipping __NEXT_DATA__.

Pagination is `?page=N`; room count is selected by category URL, not a query
param, so it's passed in explicitly rather than parsed from listing text.
"""

import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from src.models import Listing

SOURCE = "lalafo"
BASE_URL = "https://lalafo.kg"

# Realistic browser headers -- lalafo.kg is fronted by a bot-check layer
# that can serve a challenge page to non-browser-looking requests.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
    "Referer": "https://lalafo.kg/",
}

# Room count -> category URL. Room count comes from which URL was fetched,
# not from parsing listing text.
CATEGORY_URLS = {
    1: f"{BASE_URL}/bishkek/kvartiry/arenda-kvartir/dolgosrochnaya-arenda-kvartir/1-bedroom",
    2: f"{BASE_URL}/bishkek/kvartiry/arenda-kvartir/dolgosrochnaya-arenda-kvartir/2-bedrooms",
    3: f"{BASE_URL}/bishkek/kvartiry/arenda-kvartir/dolgosrochnaya-arenda-kvartir/3-bedrooms",
}

REQUEST_DELAY_SECONDS = 1.0  # be polite between page fetches

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)
# Ad links look like /bishkek/ads/<slug>-id-<digits>; city slug varies, id
# suffix does not, so match on that instead of the (build-hashed) card CSS
# classes.
AD_LINK_RE = re.compile(r"/[a-z-]+/ads/[^\"'#?]*-id-(\d+)")


def _fetch_html(url: str) -> str:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    if response.status_code != 200:
        notable_headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower().startswith(("cf-", "server"))
        }
        print(f"[lalafo] non-200 response ({response.status_code}) for {url}", file=sys.stderr)
        print(f"[lalafo] notable headers: {notable_headers}", file=sys.stderr)
        print(f"[lalafo] body preview: {response.text[:300]!r}", file=sys.stderr)
    response.raise_for_status()
    return response.text


def _extract_next_data(html: str) -> dict | None:
    match = NEXT_DATA_RE.search(html)
    if not match:
        return None
    return json.loads(match.group(1))


def _find_listing_feed_data(next_data: dict) -> dict | None:
    queries = (
        next_data.get("props", {})
        .get("pageProps", {})
        .get("dehydratedState", {})
        .get("queries", [])
    )
    for query in queries:
        if query.get("queryKey", [None])[0] == "listingFeed":
            return query.get("state", {}).get("data")
    return None


def _listing_from_json_item(item: dict, rooms: int) -> Listing:
    images = item.get("images") or []
    main_image = next(
        (img for img in images if img.get("is_main")), images[0] if images else None
    )
    district = next(
        (p["value"] for p in item.get("params", []) if p.get("name") == "Район Бишкека"),
        "",
    )
    location_text = " ".join(
        part for part in (item.get("title", ""), item.get("description", ""), district) if part
    )
    return Listing(
        source=SOURCE,
        id=str(item["id"]),
        title=item.get("title", ""),
        url=BASE_URL + item["url"],
        price=item.get("price"),
        currency=item.get("currency"),
        rooms=rooms,
        lat=item.get("lat"),
        lon=item.get("lng"),
        photo_url=(main_image or {}).get("original_url"),
        location_text=location_text,
    )


def _parse_json_page(html: str, rooms: int):
    """Returns (listings, current_page, page_count), or None if no __NEXT_DATA__."""
    next_data = _extract_next_data(html)
    if next_data is None:
        return None
    feed_data = _find_listing_feed_data(next_data)
    if feed_data is None:
        return [], 1, 1
    page = feed_data["pages"][0]
    meta = page.get("_meta", {})
    listings = [_listing_from_json_item(item, rooms) for item in page.get("items", [])]
    return listings, meta.get("currentPage", 1), meta.get("pageCount", 1)


def _parse_html_fallback(html: str, rooms: int) -> list[Listing]:
    """Best-effort card parser, used only if the __NEXT_DATA__ blob is absent.

    Unexercised against real fallback markup as of writing -- lalafo.kg has
    always shipped __NEXT_DATA__ in testing -- so treat this as a safety net,
    not a maintained primary path.
    """
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen_ids = set()
    for anchor in soup.find_all("a", href=AD_LINK_RE):
        href = anchor["href"]
        match = AD_LINK_RE.search(href)
        listing_id = match.group(1)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        container = anchor
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
        text = container.get_text(" ", strip=True)

        price_match = re.search(r"(\d[\d\s]{2,})\s*(KGS|сом|\$|USD)", text)
        price = float(price_match.group(1).replace(" ", "")) if price_match else None
        currency = None
        if price_match:
            currency = "USD" if price_match.group(2) in ("$", "USD") else "KGS"

        title = anchor.get("title") or anchor.get_text(strip=True) or text[:80]

        listings.append(
            Listing(
                source=SOURCE,
                id=listing_id,
                title=title,
                url=BASE_URL + href if href.startswith("/") else href,
                price=price,
                currency=currency,
                rooms=rooms,
                lat=None,
                lon=None,
                photo_url=None,
                location_text=text,
            )
        )
    return listings


def fetch_listings(rooms: int, max_pages: int = 3) -> list[Listing]:
    """Fetch and normalize listings for a given bedroom count (1, 2, or 3)."""
    if rooms not in CATEGORY_URLS:
        raise ValueError(f"Unsupported room count: {rooms}")

    all_listings: list[Listing] = []
    page = 1
    page_count = 1
    while page <= max_pages and page <= page_count:
        url = CATEGORY_URLS[rooms] if page == 1 else f"{CATEGORY_URLS[rooms]}?page={page}"
        html = _fetch_html(url)

        parsed = _parse_json_page(html, rooms)
        if parsed is not None:
            listings, _current_page, page_count = parsed
            all_listings.extend(listings)
        else:
            all_listings.extend(_parse_html_fallback(html, rooms))
            page_count = page  # can't tell true page count without JSON; stop here

        page += 1
        if page <= max_pages and page <= page_count:
            time.sleep(REQUEST_DELAY_SECONDS)

    return all_listings


def fetch_all(max_pages: int = 3) -> list[Listing]:
    """Fetch listings across all tracked bedroom counts (1, 2, 3)."""
    listings = []
    for rooms in sorted(CATEGORY_URLS):
        listings.extend(fetch_listings(rooms, max_pages=max_pages))
        time.sleep(REQUEST_DELAY_SECONDS)
    return listings


if __name__ == "__main__":
    for rooms in (1, 2):
        results = fetch_listings(rooms, max_pages=1)
        print(f"-- {rooms}-bedroom: {len(results)} listings --")
        for listing in results[:5]:
            coords = (
                f"{listing.lat:.4f},{listing.lon:.4f}" if listing.lat is not None else "no coords"
            )
            print(
                f"  [{listing.id}] {listing.price} {listing.currency} | {coords} | "
                f"{listing.title[:50]!r} | {listing.url}"
            )
        print()
