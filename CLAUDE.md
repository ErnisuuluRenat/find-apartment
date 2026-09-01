# Rental Monitor Bot — Project Brief

## Goal
Every ~15 minutes, check Lalafo.kg, House.kg, and a handful of Bishkek Telegram
rental channels for new listings near KGMA (Kyrgyz State Medical Academy,
ul. Ahunbaeva 92, Bishkek), and push new matches to a personal Telegram chat
via bot. Three people are splitting the rent, so there's no hard room-count
filter — location is the primary filter, price/rooms are shown in the alert
so they can be judged by eye. Zero ongoing hosting cost.

## Why this architecture
Railway's free tier as of 2026 isn't enough for an always-on background
worker (0.5 GB RAM, $1/mo credit cap after trial) — no real "free VPS"
option exists among the popular platforms anymore. Instead of a server, run
everything as a stateless script triggered by GitHub Actions cron (free,
unlimited minutes on a public repo, 5-minute minimum interval). This also
removes the need for a persistent Telegram listener: just poll each
channel's recent history for messages since the last run, same as the
scraper sources.

Known tradeoff: GitHub Actions doesn't guarantee exact timing — runs can be
delayed 5–30 minutes under load. Acceptable here; "roughly every 15 minutes"
is fine for an apartment hunt.

## Data sources
1. **Lalafo.kg** — a JS single-page app, which almost certainly calls an
   internal JSON API. Find it via browser devtools → Network tab while
   manually applying district/price filters on the site. Prefer that JSON
   endpoint over scraping raw HTML — far more stable.
2. **House.kg** — the other major Kyrgyz classifieds site. Same
   reverse-engineering approach.
3. **Telegram channels** — must be read via a *user* session (Telethon),
   not the bot — bots cannot read channel history. Start with:
   - `@arendakvartirbishkek` ("Аренда квартир в Бишкеке", ~12K subscribers)
   - Search https://kg.tgstat.com/en/sales for 3–4 more active channels and
     add their handles to `config.py`.

## Location filter
- Geocode `"Bishkek, ul. Ahunbaeva 92"` once via Nominatim (OSM, free, no
  key) to get a lat/lon constant — don't re-geocode every run.
- For listings with coordinates (Lalafo/House.kg usually include them):
  haversine distance, reject anything beyond `RADIUS_KM` (start around
  1.5–2 km, roughly a 15-minute ride).
- For Telegram posts (no coordinates): keyword filter on street/district
  names — "Ахунбаева", "Чуй", "Джал", "Восток-5", "Filatova", etc. Keep this
  list in config and expand it once you see what people actually post.
- No hard room-count filter. Soft price ceiling as a sanity cap, not a hard
  rule — roughly 2.5x a 1-room's going rate (~35,000 KGS/mo) is a reasonable
  starting ceiling (~90,000 KGS/mo total) to filter out obvious luxury
  outliers, but make it an easy constant to tune.

## Dedup / state
Keep `state/seen_ids.json` (`source + listing_id → first_seen timestamp`) in
the repo. After each run, commit it back via the Action using the built-in
`GITHUB_TOKEN`. No external database needed at this scale.

## Notification
Plain Telegram Bot API `sendMessage` HTTPS call — no library needed. Include:
price, rooms, area/address, distance from KGMA, source name, listing link,
and a photo if available.

## Credentials
| Variable | Where to get it | Status |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather | already have |
| `TELEGRAM_CHAT_ID` | message your bot once, then `GET https://api.telegram.org/bot<TOKEN>/getUpdates`, read `chat.id` | still needed |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | https://my.telegram.org → API development tools | still needed |
| `TELETHON_SESSION_STRING` | generate once locally: log in interactively with Telethon's `StringSession`, print it, store as a GitHub secret | generate after api_id/hash |

All of these belong in the GitHub repo under Settings → Secrets and
variables → Actions — never committed in code.

## Suggested repo structure
```
rental-monitor/
  .github/workflows/check.yml     # cron trigger
  src/
    sources/lalafo.py
    sources/house_kg.py
    sources/telegram_channels.py
    geo.py                        # geocode + haversine + keyword filter
    dedup.py                      # seen_ids.json read/write
    notify.py                     # Telegram Bot API sender
    main.py                       # orchestrates the above
  state/seen_ids.json
  config.py                       # RADIUS_KM, PRICE_CEILING, channels, keywords
  requirements.txt
  CLAUDE.md                       # this file
```

## Build order
1. Scaffold repo, `config.py`, `requirements.txt`.
2. `geo.py`: geocode KGMA once, haversine function, keyword matcher.
3. `sources/lalafo.py`: call the real JSON endpoint, normalize results into
   a common `Listing` shape (id, price, rooms, lat, lon, url, source, photo_url).
4. `sources/house_kg.py`: same normalization.
5. `sources/telegram_channels.py`: Telethon `StringSession` login, fetch
   messages since the last stored message id per channel, keyword-filter,
   normalize into the same `Listing` shape (no coordinates — geo comes from
   keywords only for this source).
6. `dedup.py`: load/save `state/seen_ids.json`.
7. `notify.py`: format and send the Telegram message.
8. `main.py`: pull all sources → filter → dedup → notify → save state.
9. `.github/workflows/check.yml`: cron `*/15 * * * *`, checkout, setup-python,
   install deps, run `main.py` with secrets as env vars, commit
   `state/seen_ids.json` back if it changed.
10. Test the whole pipeline locally before relying on the schedule.

## Notes
- Scrape politely: normal user-agent, no aggressive concurrency, prefer the
  JSON API over raw HTML wherever one exists.
- Keep `RADIUS_KM`, `PRICE_CEILING`, the channel list, and the district
  keyword list all in `config.py` so they're easy to tune without touching
  logic.
