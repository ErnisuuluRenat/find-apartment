"""Tunable constants and secrets for the rental monitor bot.

Keep all knobs here so behavior can be tuned without touching scraper/filter logic.
"""

import os

# --- Location -----------------------------------------------------------
# Geocode query used once by `python -m src.geo` to derive KGMA_LAT/KGMA_LON below.
KGMA_ADDRESS = "Bishkek, ul. Ahunbaeva 92"

# Filled in by running `python -m src.geo` once and pasting its output here.
# Do NOT re-geocode on every run -- see CLAUDE.md.
KGMA_LAT = 42.8419683
KGMA_LON = 74.6137644

# Reject listings farther than this from KGMA (km). ~1.5-2km is roughly a
# 15-minute ride.
RADIUS_KM = 1.75

# Soft sanity cap on total monthly rent (KGS), not a hard room-count filter.
# Roughly 2.5x a 1-room's going rate.
PRICE_CEILING = 45000

# District/street keywords for Telegram posts, which have no coordinates.
# Expand this once you see what people actually post.
DISTRICT_KEYWORDS = [
    "Ахунбаева",
    "Чуй",
    "Джал",
    "Восток-5",
    "Filatova",
]

# --- Telegram channels ----------------------------------------------------
# TODO: search https://kg.tgstat.com/en/sales for 3-4 more active Bishkek
# rental channels and add their handles here.
TELEGRAM_CHANNELS = [
    "arendakvartirbishkek",
]

# --- State -----------------------------------------------------------------
STATE_FILE = "state/seen_ids.json"

# --- Credentials (set as GitHub Actions secrets, never hardcoded) ---------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_API_ID = os.environ.get("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH")
TELETHON_SESSION_STRING = os.environ.get("TELETHON_SESSION_STRING")
