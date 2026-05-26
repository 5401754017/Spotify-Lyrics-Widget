# Spotify Lyrics Widget V1.4 — NetEase Lyrics Fallback (Design)

Date: 2026-05-26
Status: Approved (Claude × user brainstorm, 2026-05-26). Implementation plan exists at
`docs/superpowers/plans/2026-05-26-spotify-lyrics-widget-v1-4.md`.

## Goal

When LRCLIB has no synced lyrics for the current track, automatically fall back to NetEase
Cloud Music (网易云音乐) to fill the gap — primarily for Chinese songs, where LRCLIB
coverage is thinner. LRCLIB stays the primary source; NetEase is one optional fallback,
added per the roadmap's "one fallback at a time" rule.

## Source decision: NetEase (not the sp_dc cookie route)

The roadmap's earlier candidate was Spotify's official lyrics via an `sp_dc` cookie
(Musixmatch-sourced). It was **rejected for V1.4** in favour of NetEase:

- The user's actual gap is **Chinese songs** (mostly mainstream Mandopop, incl. Taiwanese
  artists). NetEase has strong synced-lyric coverage for mainstream Mandopop and needs
  **no cookie and no login** — sidestepping every caveat Codex flagged on the sp_dc route
  (cookie acquisition, periodic expiry/re-paste, unofficial ToS-gray auth).
- The sp_dc route's strength is Western coverage, which is the *smaller* part of the user's
  gap. It is not worth its setup/maintenance cost here.

Accepted limitation: NetEase coverage is thinner for **Taiwanese Hokkien (台語) and
indie/obscure** tracks. If that proves insufficient in practice, a **second** fallback source
can be added later (one at a time) — out of scope for V1.4.

## Behaviour

- **Default ON.** A config flag `netease_fallback` (boolean, default `True`) gates it. No
  setup friction (no cookie), so it just works on install; the flag exists only to turn it
  off.
- **Trigger condition:** fires only when LRCLIB returns a **confirmed no-result (`None`)** —
  i.e. LRCLIB reached but found no synced lyrics. It does **not** fire when LRCLIB itself
  errors/times out (that keeps the existing `lyrics_unavailable` behaviour). Rationale: the
  user's pain is "Chinese song has no lyrics", not "LRCLIB is down" — so the clean trigger is
  LRCLIB's `None`, not its exceptions.

## Architecture & components

- **New module `src/netease.py`** — single responsibility, mirrors the LRCLIB module shape:
  - `fetch_lyrics_from_netease(info: TrackInfo) -> list[tuple[int, str]] | None`
  - Flow: search by track + artist → rank candidates by track/artist/duration closeness
    (same scoring idea as the existing `rank_search_results`) → fetch the chosen song's LRC →
    `parse_lrc()` → return parsed `(timestamp_ms, line)` list, or `None` only when NetEase
    was reachable and produced a confirmed no-match/no-usable-lyric result.
  - Temporary API failures raise `NeteaseUnavailableError` instead of returning `None`.
    Examples: timeout, connection error, 429, 5xx/non-200, malformed JSON. This keeps a real
    miss separate from "fallback source is unavailable right now".
  - Uses NetEase **public endpoints** (`music.163.com/api` search + song-lyric) with a
    `Referer: https://music.163.com` and a normal User-Agent header. **No cookie / no auth.**
  - Takes only the primary LRC (`lrc.lyric`); ignores translation/romaji sub-tracks for now.
  - Maintains a small process-local cooldown for NetEase 429. This cooldown is intentionally
    global for the NetEase fallback (search and lyric endpoints both skip) because either
    endpoint returning 429 means the fallback source is pushing back. When `Retry-After` is
    present, respect it; otherwise use a short default cooldown. While cooldown is active,
    skip NetEase, log `cooldown active`, raise `NeteaseUnavailableError`, and do not call the
    endpoint.

- **`src/config.py`** — add `netease_fallback: bool = True` to the persisted defaults.

- **`src/lyrics_worker.py`** — orchestration only; keep LRCLIB and NetEase fetchers separate.
  The worker decides whether to call the fallback. The `netease_fallback` flag is read from
  config and passed into the worker (constructor arg), so the worker stays testable without
  touching global config.

## Data flow (hook point)

```
track change → LyricsWorker.run()
  cache hit  → emit cached result / no_lyrics  (unchanged)
  cache miss → fetch_lyrics_from_lrclib(info)
                 result        → cache + lyrics_ready          (unchanged)
                 None & flag on→ fetch_lyrics_from_netease(info)
                                   result → cache + lyrics_ready
                                   None   → cache NO_LYRICS + no_lyrics
                                   NeteaseUnavailableError → lyrics_unavailable, no cache
                 None & flag off→ cache NO_LYRICS + no_lyrics   (unchanged)
               LRCLIB raises (network/5xx) → lyrics_unavailable (unchanged; NO fallback)
```

## Error handling (brake + visibility)

- NetEase **confirmed misses** return `None`: no search result, no acceptable candidate, no
  LRC for the selected candidate, or parsed LRC has no timed lines.
- NetEase **temporary unavailable** states raise `NeteaseUnavailableError`: timeout,
  connection error, 429, 5xx/non-200, malformed JSON. The worker catches it, emits the same
  temporary unavailable UI state used for LRCLIB outages, and does **not** cache the failure.
- 429 handling must read `Retry-After`; if absent, use a short default cooldown. During
  cooldown, do not call NetEase again. This is the brake that prevents repeated lookups from
  hammering the endpoint. The cooldown is global for the NetEase fallback, not per endpoint.
- Log one clear line per lookup outcome with the real reason: hit, confirmed miss, HTTP
  status, timeout, malformed JSON with a capped response snippet, 429 retry window, or
  cooldown active. The UI may stay simple, but `widget.log` must preserve the real cause.

## Caching

Reuse the existing session `LyricsCache` (keyed by Spotify track ID). A NetEase hit is cached
exactly like an LRCLIB hit. A both-miss is cached as `NO_LYRICS` only when LRCLIB returned
`None` and NetEase also returned a confirmed `None`. Temporary NetEase unavailable/cooldown
states are not cached.

## Testing

- `tests/test_netease.py`:
  - candidate ranking picks the closest synced match (name/artist/duration)
  - parses returned LRC into sorted `(ms, line)` tuples
  - search with no results → `None`
  - confirmed no candidate/no lyric/unparseable timed lines → `None`
  - timeout / connection error / non-200 / malformed JSON → `NeteaseUnavailableError`
  - 429 with `Retry-After` sets cooldown; a second call during cooldown skips HTTP and raises
    `NeteaseUnavailableError`
- `tests/test_lyrics_worker.py` (extend):
  - LRCLIB `None` + flag ON → `fetch_lyrics_from_netease` is called; its hit → `lyrics_ready`
  - LRCLIB `None` + flag OFF → NetEase is **not** called → `no_lyrics`
  - LRCLIB raises → NetEase not called (still `lyrics_unavailable`)
  - LRCLIB `None` + NetEase unavailable → `lyrics_unavailable`, and no `NO_LYRICS` cache

## Risks (carry into the plan)

- NetEase public endpoints are unofficial — they may change or break. Acceptable: it is a
  fallback; if it breaks, LRCLIB (the primary) is unaffected and the user just sees the
  temporary `lyrics unavailable` behaviour.
- Region/anti-abuse: requests to `music.163.com` generally work from Taiwan, but individual
  endpoints occasionally rate-limit or block. Do not treat this as a miss: log the real
  reason, respect 429 `Retry-After`, and avoid caching.
- Coverage gap for 台語 / indie remains; revisit with a second source later if needed.

## Out of scope (V1.4)

- A second fallback source (only one at a time).
- Translation/bilingual lyric display.
- The sp_dc / Musixmatch route (rejected above).
- Any change to LRCLIB ranking or the primary path.
