# Spotify Lyrics Widget V1.4 — NetEase Lyrics Fallback (Design)

Date: 2026-05-26
Status: Approved (Claude × user brainstorm, 2026-05-26). Next step: writing-plans.

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
    `parse_lrc()` → return parsed `(timestamp_ms, line)` list, or `None` if nothing suitable.
  - Uses NetEase **public endpoints** (`music.163.com/api` search + song-lyric) with a
    `Referer: https://music.163.com` and a normal User-Agent header. **No cookie / no auth.**
  - Takes only the primary LRC (`lrc.lyric`); ignores translation/romaji sub-tracks for now.

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
                 None & flag off→ cache NO_LYRICS + no_lyrics   (unchanged)
               LRCLIB raises (network/5xx) → lyrics_unavailable (unchanged; NO fallback)
```

## Error handling (brake + visibility)

- All NetEase failures — timeout, connection error, non-200, malformed JSON, unparseable LRC
  — are caught inside `fetch_lyrics_from_netease`, **logged**, and turned into a `None` return
  so the worker falls through to `no_lyrics`. A fallback failure must never crash, block, or
  spam the main flow (matches the user's global rules: external-API loops need a brake;
  errors go to the log, never silently swallowed with bare `except: pass`).
- One INFO log line per lookup recording hit/miss (and the matched NetEase title on hit), so
  the user can later judge NetEase's real hit-rate on their library.

## Caching

Reuse the existing session `LyricsCache` (keyed by Spotify track ID). A NetEase hit is cached
exactly like an LRCLIB hit; a both-miss is cached as `NO_LYRICS`. No change to cache shape —
the fallback result simply flows into the same `lyrics_ready` / cache path.

## Testing

- `tests/test_netease.py`:
  - candidate ranking picks the closest synced match (name/artist/duration)
  - parses returned LRC into sorted `(ms, line)` tuples
  - search with no results → `None`
  - HTTP error / non-200 / malformed body → `None` (never raises)
- `tests/test_lyrics_worker.py` (extend):
  - LRCLIB `None` + flag ON → `fetch_lyrics_from_netease` is called; its hit → `lyrics_ready`
  - LRCLIB `None` + flag OFF → NetEase is **not** called → `no_lyrics`
  - LRCLIB raises → NetEase not called (still `lyrics_unavailable`)

## Risks (carry into the plan)

- NetEase public endpoints are unofficial — they may change or break. Acceptable: it is a
  fallback; if it breaks, LRCLIB (the primary) is unaffected and the user just sees the
  pre-V1.4 "no lyrics" behaviour.
- Region/anti-abuse: requests to `music.163.com` generally work from Taiwan, but individual
  endpoints occasionally rate-limit or block. Handled by the catch-all → treat as a miss.
- Coverage gap for 台語 / indie remains; revisit with a second source later if needed.

## Out of scope (V1.4)

- A second fallback source (only one at a time).
- Translation/bilingual lyric display.
- The sp_dc / Musixmatch route (rejected above).
- Any change to LRCLIB ranking or the primary path.
