# Spotify Lyrics Widget V1.4 — LRCLIB Contract Hardening + Gated NetEase Fallback (Design)

Date: 2026-05-26
Status: Approved and revised (Claude × Codex consensus, 2026-05-26, 4 rounds). NetEase
endpoint **spike completed and passed** (see below). Implementation plan:
`docs/superpowers/plans/2026-05-26-spotify-lyrics-widget-v1-4.md`.

> **Scope change from the original V1.4:** V1.4 was first specced as "NetEase fallback when
> LRCLIB returns a confirmed miss." Review found the trigger contract depends on a clean
> LRCLIB `None`, but `lyrics_worker.py` currently misclassifies some transient LRCLIB
> failures as confirmed misses (and can crash silently on malformed JSON). So V1.4 now has
> two parts: (1) **harden the LRCLIB contract** (ships regardless of the spike), then (2) the
> **gated NetEase fallback** (only if the spike passes). The spike passed, so both ship.

## Goal

When LRCLIB has no synced lyrics for the current track, automatically fall back to NetEase
Cloud Music (网易云音乐) to fill the gap — primarily for Chinese songs, where LRCLIB
coverage is thinner. LRCLIB stays the primary source; NetEase is one optional fallback,
added per the roadmap's "one fallback at a time" rule.

## Source decision: NetEase (not the sp_dc cookie route)

NetEase was chosen over Spotify's `sp_dc`-cookie (Musixmatch) route because the user's gap is
**Chinese songs** (mainly mainstream Mandopop incl. Taiwanese artists). NetEase has strong
synced-lyric coverage there and needs **no cookie / no login**. The sp_dc route's strength is
Western coverage (the smaller part of the gap) and carries cookie acquisition/expiry/ToS-gray
caveats. Rejected for V1.4.

Accepted limitation: NetEase coverage is thinner for **Taiwanese Hokkien (台語) and
indie/obscure** tracks. A second fallback source can be added later (one at a time) — out of
scope for V1.4.

## Spike validation (2026-05-26) — PASSED, with three design-changing findings

Real HTTP from the user's Windows machine (Taiwan), no cookie, only `Referer` + UA, against
the planned endpoints `https://music.163.com/api/search/get/web` and
`https://music.163.com/api/song/lyric`. Three known Mandopop tracks. Results:

- **Endpoints work, no auth needed.** Both returned HTTP 200 / JSON `code:200`. "溫柔/五月天"
  (60 timed tags) and "光年之外/G.E.M.邓紫棋" (78 timed tags) returned clean standard LRC.
  3-digit-ms timestamps (`[00:00.000]`) appear and are already handled by the parser.
- **Finding A — `search[0]` is unsafe.** "晴天 周杰倫" returned a *cover* (composer A-LNK,
  3:02) as the top hit, with **zero timestamps** (plain text). Blindly taking the first
  result yields wrong/untimed lyrics. → Must rank candidates and require parsed timed lines.
- **Finding B — Traditional vs Simplified mismatch.** Spotify gives Traditional
  (周杰**倫**, 鄧紫棋); NetEase returns Simplified (周杰**伦**, 邓紫棋). Without script
  unification, most Taiwanese tracks fail to match — gutting the fallback's purpose.
  → Decision: add `zhconv` (user-approved, 2026-05-26).
- **Finding C — credit lines leak as lyrics.** NetEase prepends
  `[00:00.00] 作词 : …` / `编曲 : …` production credits with near-zero timestamps, so they
  display as the first "lyric" lines. → NetEase-only credit-line filter.
- **Finding D — multi-timestamp lines** (`[t1][t2]text`) were **not** in the 3 samples but are
  known on NetEase. Cheap insurance: handle them in `lrc_parser` now (strict superset).

## Prerequisite (ships regardless of NetEase): LRCLIB contract hardening

`LRCLIB None` must mean exactly one thing: **a valid LRCLIB response that contained no synced
lyrics.** Today `fetch_lyrics_from_lrclib` only raises `LrclibUnavailableError` on timeout and
`status_code >= 500`; a 429/403/460 on both `/get` and `/search` falls through to `return
None` (a false confirmed-miss), and a malformed 200 body makes `response.json()` raise
`JSONDecodeError`, which `run()`'s `except (httpx.ConnectError, LrclibUnavailableError)` does
**not** catch → the worker QThread dies silently, no signal emitted, UI stuck on that track.

Fix (must land before NetEase wiring):
- LRCLIB 429 → `LrclibUnavailableError` (respect `Retry-After`, consistent with the Spotify
  poller's existing backoff).
- Malformed/invalid JSON on `/get` or `/search` → `LrclibUnavailableError` (not an uncaught
  crash).
- `/get` 404 (no exact match) still falls through to `/search` (normal, unchanged).
  `/search` non-200 (other than handled cases) → unavailable, not a confirmed miss.
- Worker: any LRCLIB-unavailable → emit `lyrics_unavailable`, do **not** cache, and do **not**
  call NetEase.

## Behaviour

- **Default ON.** Config flag `netease_fallback` (boolean, default `True`). No setup friction
  (no cookie), so it just works on install; the flag exists only to turn it off.
- **Trigger condition:** fires only when LRCLIB returns a **confirmed `None`** (reached, no
  synced lyrics). It does **not** fire when LRCLIB is unavailable (now correctly classified by
  the prerequisite fix).

## Architecture & components

- **New module `src/netease.py`** — single responsibility, isolates the unofficial NetEase
  calls and matching from the worker. Takes **primitive args**
  `fetch_lyrics_from_netease(track_name, artist_name, duration_ms)` (not `TrackInfo`) so it
  does not import `lyrics_worker` (which imports this module) — one-directional, no circular
  import. (Note: the original spec said `TrackInfo`; primitives are the agreed choice.)
  - **Flow:** search → rank candidates → for each of up to **3** ranked candidates: fetch its
    LRC → `parse_lrc` → NetEase credit-filter → if timed lines remain, accept; else try the
    next candidate → if all exhausted, return confirmed `None`.
  - Uses NetEase **public endpoints** with `Referer: https://music.163.com` + a normal UA.
    **No cookie / no auth.** Takes only `lrc.lyric` (ignores translation/romaji sub-tracks).
  - Confirmed miss → `None`. Temporary failures (timeout, connection error, 429, non-200,
    malformed JSON) → `NeteaseUnavailableError`.

- **Ranking & candidate selection** (`rank_netease_songs`):
  - Normalize title/artist with **script unification via `zhconv`** (convert both Spotify and
    NetEase strings to one script) plus the existing lowercase/punctuation/version-suffix
    normalization (mirror `lyrics_worker._normalize`, incl. stripping live/remaster/edit/etc.).
  - Score by title-match + artist-match confidence, with **duration as a soft penalty /
    tiebreaker, not a hard 5s reject.** Allow larger duration drift only when title + artist
    are strong; reject weak textual matches even when duration is close (**wrong lyrics are
    worse than no lyrics**). Return ranked candidates for the fetch-and-validate loop above.

- **Traditional/Simplified (`zhconv`)** — match Traditional Spotify metadata against Simplified
  NetEase metadata by normalizing both to one script. Convert the **accepted** NetEase lyric
  text to `zh-tw` before returning it to the UI (display in Traditional).

- **Credit-line filter (NetEase-only)** — after `parse_lrc`, drop parsed lines whose text
  matches a small credit prefix set followed by `:`/`：`, e.g. `作词`, `作曲`, `编曲`,
  `制作人`, `出品`, `演唱`, `演奏`, `和声`, `混音`, `录音`, `母带`, `Producer`, `Composer`,
  `Lyricist`. Lives in the NetEase path only — LRCLIB's primary path is untouched.

- **`src/lrc_parser.py`** — extend to expand multi-timestamp lines `[t1][t2]text` into one
  `(ts, text)` entry per timestamp, then sort. Single-timestamp lines are unaffected (strict
  superset). Benefits both sources; needed for NetEase robustness.

- **`src/config.py`** — add `netease_fallback: bool = True` to persisted defaults.

- **`src/lyrics_worker.py`** — orchestration only; LRCLIB and NetEase fetchers stay separate.
  The `netease_fallback` flag is read from config and passed into the worker (constructor
  arg). The worker decides whether to call the fallback.

## Data flow (hook point)

```
track change → LyricsWorker.run()
  cache hit  → emit cached result / no_lyrics  (unchanged)
  cache miss → fetch_lyrics_from_lrclib(info)
                 result            → cache + lyrics_ready
                 None & flag on    → fetch_lyrics_from_netease(name, artist, dur_ms)
                                       result → cache + lyrics_ready
                                       None   → cache NO_LYRICS + no_lyrics
                                       NeteaseUnavailableError → lyrics_unavailable, no cache
                 None & flag off   → cache NO_LYRICS + no_lyrics
               LRCLIB unavailable (timeout/5xx/429/malformed/network)
                                   → lyrics_unavailable (NO fallback, NO cache)
```

## Error handling (brake + visibility)

- NetEase **confirmed misses** return `None`: no search result, no acceptable candidate,
  none of the (≤3) candidates yields timed lines after credit filtering.
- NetEase **temporary unavailable** → `NeteaseUnavailableError`: timeout, connection error,
  429, non-200, malformed JSON. The worker catches it, emits `lyrics_unavailable`, does
  **not** cache.
- **Unified cooldown brake (no separate circuit breaker).** A single process-local global
  NetEase cooldown is set by **any** `NeteaseUnavailableError`:
  - 429 → cooldown = `Retry-After` (or a default if missing/invalid).
  - every other unavailable (timeout / network / non-200 like 403/405/460 / malformed JSON)
    → cooldown = `DEFAULT_UNAVAILABLE_BACKOFF_S` (= 60).
  While cooldown is active, skip the NetEase HTTP call, log `cooldown active`, and raise
  `NeteaseUnavailableError`. No consecutive-failure escalation — there is no high-frequency
  auto-retry loop, and one global cooldown already prevents bursts across track changes. If
  NetEase is dead, each post-cooldown attempt fails and renews the cooldown. Sufficient for a
  single-user fallback path.
- Log one clear line per lookup outcome with the real reason: hit, confirmed miss, HTTP
  status, timeout, malformed JSON (capped snippet), 429 retry window, or cooldown active.

## Caching

Reuse the existing session `LyricsCache` (keyed by Spotify track ID). A NetEase hit is cached
like an LRCLIB hit. A both-miss is cached as `NO_LYRICS` only when LRCLIB returned a confirmed
`None` and NetEase also returned a confirmed `None`. Temporary unavailable / cooldown states
(LRCLIB or NetEase) are never cached.

## Testing

- `tests/test_lyrics_worker.py` (LRCLIB taxonomy prerequisite):
  - LRCLIB 429 → `lyrics_unavailable`, no cache, **NetEase not called**.
  - LRCLIB malformed JSON → `lyrics_unavailable`, no cache, no silent crash, NetEase not called.
  - LRCLIB `/get` 404 still falls through to `/search`.
- `tests/test_netease.py`:
  - ranking picks the closest synced match (title/artist + duration soft); rejects weak text
    matches even when duration is close.
  - **Traditional/Simplified**: Traditional query matches a Simplified NetEase result via
    `zhconv` (e.g. 周杰倫 ↔ 周杰伦, 鄧紫棋 ↔ 邓紫棋).
  - **cover/no-timed fallback**: a top candidate whose lyric has no timed lines is skipped;
    the next valid candidate is used; all-untimed → confirmed `None`.
  - **credit filter**: leading `作词/作曲/编曲 : …` lines are dropped.
  - accepted lyric is converted to `zh-tw`.
  - search no-result / no acceptable candidate → `None`.
  - timeout / connection error / non-200 / malformed JSON → `NeteaseUnavailableError`.
  - 429 with `Retry-After` sets cooldown; a second call during cooldown skips HTTP and raises.
  - a non-429 unavailable also sets the default cooldown; a call during it skips HTTP.
- `tests/test_lrc_parser.py`:
  - single-timestamp line unchanged; multi-timestamp `[t1][t2]text` expands to sorted entries.
- `tests/test_lyrics_worker.py` (fallback wiring):
  - LRCLIB `None` + flag ON → NetEase called; its hit → `lyrics_ready`.
  - LRCLIB `None` + flag OFF → NetEase not called → `no_lyrics`.
  - LRCLIB `None` + NetEase unavailable → `lyrics_unavailable`, no `NO_LYRICS` cache.
  - LRCLIB `None` + NetEase confirmed `None` → `NO_LYRICS` cached.

## Dependencies

- New: `zhconv` (pure-Python Traditional/Simplified, MediaWiki tables; no native build).
  Add to `requirements.txt`. User-approved 2026-05-26.
- No other new dependencies.

## Risks (carry into the plan)

- NetEase public endpoints are unofficial — may change or break. Acceptable: it is a fallback;
  if it breaks, LRCLIB (the primary) is unaffected and the user sees the temporary
  `lyrics unavailable` behaviour. The unified cooldown prevents hammering a dead endpoint.
- Region/anti-abuse: requests to `music.163.com` generally work from Taiwan (spike confirmed),
  but endpoints can rate-limit/block. Do not treat as a miss: log the real reason, respect 429
  `Retry-After`, cool down, avoid caching.
- `zhconv` conversion is table-based, not context-aware; rare ambiguous characters may convert
  imperfectly. Low risk for title/artist matching; acceptable for lyric display.
- Coverage gap for 台語 / indie remains; revisit with a second source later if needed.

## Out of scope (V1.4)

- A second fallback source (only one at a time).
- Translation/bilingual lyric display (we only Traditionalize the single NetEase lyric track).
- The sp_dc / Musixmatch route (rejected above).
- Any change to LRCLIB ranking or the primary path beyond the contract-hardening fix.
