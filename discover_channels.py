"""One-off script to find candidate Bishkek rental Telegram channels.

Not part of the main pipeline -- run manually, review the printed list, and
add whichever handles look good to config.TELEGRAM_CHANNELS yourself. Uses
the same Telethon user session as src/sources/telegram_channels.py (bots
can't use contacts.search).

Usage: python -m discover_channels   (from repo root, with the five
Telegram env vars set, e.g. `set -a; source .env; set +a`)
"""

import time

from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel

import config

QUERIES = [
    "аренда квартир бишкек",
    "сдам квартиру бишкек",
    "снять квартиру бишкек",
    "жилье бишкек",
]

SEARCH_LIMIT_PER_QUERY = 50
REQUEST_DELAY_SECONDS = 0.5  # be polite between GetFullChannelRequest calls


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
            f"discover_channels: missing required env var(s): {', '.join(missing)}"
        )


def _search_channels(client: TelegramClient, query: str) -> list[Channel]:
    result = client(SearchRequest(q=query, limit=SEARCH_LIMIT_PER_QUERY))
    return [
        chat
        for chat in result.chats
        if isinstance(chat, Channel) and chat.username
    ]


def _full_info(client: TelegramClient, channel: Channel) -> tuple[int | None, str | None]:
    try:
        full = client(GetFullChannelRequest(channel))
        return full.full_chat.participants_count, full.full_chat.about or None
    except Exception as exc:
        print(f"  (couldn't fetch full info for @{channel.username}: {exc})")
        return None, None


def main() -> None:
    _require_credentials()

    with TelegramClient(
        StringSession(config.TELETHON_SESSION_STRING),
        int(config.TELEGRAM_API_ID),
        config.TELEGRAM_API_HASH,
    ) as client:
        candidates: dict[str, Channel] = {}
        for query in QUERIES:
            for channel in _search_channels(client, query):
                candidates.setdefault(channel.username.lower(), channel)

        print(f"Found {len(candidates)} de-duplicated candidate channel(s).\n")

        rows = []
        for channel in candidates.values():
            count, about = _full_info(client, channel)
            rows.append((channel.username, channel.title, count, about))
            time.sleep(REQUEST_DELAY_SECONDS)

    rows.sort(key=lambda row: row[2] if row[2] is not None else -1, reverse=True)

    for username, title, count, about in rows:
        count_str = f"{count:,}" if count is not None else "n/a"
        print(f"@{username} | {title} | {count_str} subscribers")
        if about:
            print(f"    {about[:200]}")
        print()


if __name__ == "__main__":
    main()
