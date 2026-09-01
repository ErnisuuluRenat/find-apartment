"""Telegram channel source: read via a *user* session (Telethon), not the bot
-- bots can't read channel history.

Rather than persisting a last-seen message id per channel, this simply
re-fetches each channel's most recent MESSAGES_PER_CHANNEL messages every run
and lets dedup.py's global seen-id store filter out repeats. Simpler than a
second piece of state, and correct as long as a channel doesn't post more
than MESSAGES_PER_CHANNEL messages in one ~15-minute poll interval.

No coordinates are available for free-text channel posts, so geo filtering
for this source is keyword-only (see geo.matches_keywords), same as
house_kg. Price/room parsing from free text isn't attempted -- left None so
they're judged by eye in the alert, per CLAUDE.md.
"""

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

import config
from src.models import Listing

SOURCE = "telegram"
MESSAGES_PER_CHANNEL = 50


def _require_credentials() -> None:
    missing = [
        name
        for name, value in (
            ("TELEGRAM_API_ID", config.TELEGRAM_API_ID),
            ("TELEGRAM_API_HASH", config.TELEGRAM_API_HASH),
            ("TELETHON_SESSION_STRING", config.TELETHON_SESSION_STRING),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"telegram_channels: missing required env var(s): {', '.join(missing)}"
        )


def _listing_from_message(channel: str, message) -> Listing | None:
    text = (message.message or "").strip()
    if not text:
        return None
    return Listing(
        source=SOURCE,
        id=f"{channel}:{message.id}",
        title=text.splitlines()[0][:120],
        url=f"https://t.me/{channel}/{message.id}",
        rooms=None,
        lat=None,
        lon=None,
        photo_url=None,
        location_text=text,
    )


def fetch_all() -> list[Listing]:
    """Fetch recent messages from every channel in config.TELEGRAM_CHANNELS."""
    _require_credentials()

    listings: list[Listing] = []
    with TelegramClient(
        StringSession(config.TELETHON_SESSION_STRING),
        int(config.TELEGRAM_API_ID),
        config.TELEGRAM_API_HASH,
    ) as client:
        for channel in config.TELEGRAM_CHANNELS:
            for message in client.iter_messages(channel, limit=MESSAGES_PER_CHANNEL):
                listing = _listing_from_message(channel, message)
                if listing is not None:
                    listings.append(listing)

    return listings


if __name__ == "__main__":
    results = fetch_all()
    print(f"-- {len(results)} messages --")
    for listing in results[:5]:
        print(f"  [{listing.id}] {listing.location_text[:60]!r} | {listing.url}")
