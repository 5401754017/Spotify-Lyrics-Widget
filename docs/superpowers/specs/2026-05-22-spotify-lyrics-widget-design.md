# Spotify Lyrics Widget Design Spec

Date: 2026-05-22

---

## Overview

A Windows desktop floating widget that displays real-time synced lyrics for the currently
playing Spotify track. Compact subtitle-style display with a fixed lyric lane that can show
up to two lines, always-on-top, with hover-to-reveal playback controls.

**Target user:** Personal use only (developer themselves). Requires Spotify Premium.

---

## Lyrics Source

- **Primary source:** lrclib.net (free, no auth required, ~3M tracks)
- **Primary endpoint:** `GET /api/get` with `track_name`, `artist_name`, `album_name`, `duration`. Duration must be converted from Spotify's milliseconds to seconds (integer).
- **Secondary endpoint:** If exact match returns nothing or has no `syncedLyrics`, fallback to `GET /api/search?track_name=...&artist_name=...`. Rank results instead of taking the first one:
  1. Must have `syncedLyrics`
  2. Prefer closest duration match (within 5 seconds tolerance)
  3. Prefer closest normalized track name / artist name match
- **Session cache:** Cache successful lookups and confirmed "no lyrics" misses by Spotify track ID. Avoid redundant API calls when the user loops a song or goes back to a previous track. Do not cache temporary API/network/rate-limit failures as "no lyrics".
- **Only use `syncedLyrics`** (LRC format with timestamps). If `syncedLyrics` is null, display "no synced lyrics available" regardless of whether `plainLyrics` exists
- **V1.4 fallback (NetEase):** Optional NetEase fallback may run only after LRCLIB returns a confirmed miss. Validated by a real-endpoint spike (2026-05-26): `music.163.com/api` search + song-lyric work with no cookie/auth. NetEase specifics learned from the spike and now part of the design:
  - **Rank multiple candidates, never `search[0]`** — the top search hit can be a cover with no timestamps. Rank by normalized title/artist + duration, then fetch the lyric of the best candidate and require it to parse into timed lines; fall through up to 3 candidates before returning a confirmed miss.
  - **Traditional/Simplified unification (`zhconv`)** — Spotify metadata is Traditional, NetEase is Simplified. Normalize both sides to one script before matching, and convert the accepted NetEase lyric to `zh-tw` for display.
  - **Credit-line filter (NetEase-only)** — NetEase prepends `[00:00.xx] 作词 : …` / `编曲 : …` production credits; drop them in the NetEase path so they do not show as the first lyric lines. LRCLIB's primary path is unchanged.
  - NetEase timeout / non-200 / malformed response / 429 is temporary unavailable, must be logged with the real reason, must respect `Retry-After`, and must not be cached as a miss.
- **No private Spotify-cookie fallback in V1.4.** Do not use `sp_dc` / unofficial Spotify lyrics cookie flows for V1.4. No Genius, no Musixmatch, no scraping.

---

## Spotify API

### Authentication

- **Prerequisites:** User must create a Spotify App at https://developer.spotify.com/dashboard, obtain `client_id`, and set redirect URI to `http://127.0.0.1:8888/callback`. No `client_secret` needed.
- **Flow:** Authorization Code Flow with PKCE (S256). Desktop app cannot safely store a client secret, so PKCE is the correct choice.
- **Redirect URI:** Must use `http://127.0.0.1:8888/callback` (Spotify prohibits `localhost` since April 2025)
- **Scopes required:**
  - V1 (core): `user-read-currently-playing`
  - V2 (controls): `user-modify-playback-state` (play/pause, next, prev)
  - Playlist phase (deferred, post-V2): `playlist-modify-public`, `playlist-modify-private`, `playlist-read-private`
- **Token refresh:** Access token expires in 1 hour. Auto-refresh using refresh token before expiry. Spotify's refresh response may or may not include a new `refresh_token`. If present, save the new one. If absent, continue using the existing refresh token.
- **First-time auth:** Open system browser to Spotify login page, run a temporary local HTTP server on port 8888 to receive the OAuth callback
- **First-run bootstrap:** If no `client_id` in config, prompt user in a simple dialog to paste their `client_id` before starting OAuth

### Polling

- **Endpoint:** `GET /v1/me/player/currently-playing`
- **Frequency:** Every 1 second (resync source only; UI uses local timer between polls)
- **Key response fields:** `item.id`, `item.name`, `item.uri`, `item.artists`, `item.album.name`, `item.duration_ms`, `progress_ms`, `is_playing`, `currently_playing_type`
- **Non-track handling:** If `currently_playing_type` is `episode`, `ad`, or `unknown`, display "not a track" and skip lyrics lookup / playlist add. Only process `track` type.

### Playback Control Endpoints

- `PUT /v1/me/player/pause` — pause
- `PUT /v1/me/player/play` — resume
- `POST /v1/me/player/next` — skip to next
- `POST /v1/me/player/previous` — skip to previous
- All require `user-modify-playback-state` scope and Spotify Premium

### Playlist Endpoints (deferred phase, post-V2)

- `GET /v1/me/playlists` — list user's playlists (for playlist picker). Filter to only show playlists owned by current user (not followed/collaborative ones).
- `POST /v1/playlists/{playlist_id}/items` — add current track to playlist (uses `item.uri` from player state). The `/tracks` endpoint is deprecated.

---

## Architecture

### Modules

| Module | Phase | Responsibility |
|---|---|---|
| `auth` | V1 | Spotify PKCE OAuth flow, token storage, auto-refresh |
| `config` | V1 | Read/write JSON config file: client_id, tokens, window position (x, y). Deferred phase: default playlist ID |
| `spotify_worker` | V1 | Poll currently playing track every 1s in a worker thread. Emit state-change, playback, network, and rate-limit signals. |
| `lyrics_worker` | V1 | Query lrclib.net in a worker thread, cache results by Spotify track ID for the session, and emit lyrics/no-lyrics/unavailable signals. |
| `lrc_parser` | V1 | Parse LRC timestamps into sorted `(timestamp_ms, line_text)` tuples and find the current line. |
| `widget` | V1-V1.3 | PyQt6 frameless always-on-top draggable opaque window with Windows 11 DWM rounded corners + DWM green border, lyric display, progress bar, offline status in lyric lane. V2: hover playback controls + title marquee. |
| `logging_setup` | V1.2-V1.3 | Configure `%APPDATA%/spotify-lyrics-widget/widget.log`, rotating file handler, and uncaught-exception logging for `pythonw`. |
| `fonts` | V1.3 | Detect system CJK font (`Microsoft JhengHei UI` → `Microsoft JhengHei` → `Segoe UI`) and expose `app_font_family()`. |
| `tray` | V1.3 | System tray icon, raise/show-hide/open-log/quit menu actions. |
| `shortcuts` | V1.3 | One-shot Start-menu and desktop `.lnk` installer using Windows `WScript.Shell`. |
| `netease` | V1.4 planned | Optional NetEase fallback source after LRCLIB confirmed miss. |
| `playback` | V2 planned | Fire-and-forget Spotify playback control calls with duplicate-click and 429 brakes. |
| `marquee` | V2 planned | Dedicated title renderer: left-aligned/elided at rest, hover ping-pong marquee when overflowing. |
| `playlist` | Deferred (post-V2) | Fetch user's playlists, add track to playlist, manage default playlist memory |

### Dependency Direction

```
main/widget → spotify_worker, lyrics_worker, tray → auth, config, lrc_parser
future: lyrics_worker → netease; widget/main → playback + marquee; playlist phase adds playlist module
```

### Threading Model

All HTTP calls run off the GUI thread to prevent UI freezes:

- **Spotify polling:** Runs in a `QThread` worker. Emits signals to UI thread on state changes.
- **lrclib lookup:** Runs in a `QThread` worker. Each lookup carries the Spotify track ID it was requested for. UI ignores stale results if the user has already changed tracks.
- **Playback controls (V2):** Fire-and-forget HTTP calls in a worker thread. No UI blocking.
- **UI updates:** All UI mutations happen on the main thread via signal/slot connections.

### Inter-module Communication

PyQt6 Signals/Slots:

- `spotify_worker.track_changed(PlayerState)` → `App._on_track_changed()` updates
  `LyricsWidget`, clears the lyric lane, and calls `LyricsWorker.request_lyrics(TrackInfo)`.
  (The old forced `repaint()`/`force_visual_refresh()` workaround was removed in `4589a84`;
  the opaque window repaints correctly through normal Qt paths.)
- `spotify_worker.state_synced(progress_ms, is_playing, timestamp)` →
  `LyricsWidget.resync_local_timer()`.
- `spotify_worker.playback_toggled(is_playing)` → stop/resume local UI timer handling.
- `spotify_worker.not_playing` / `not_a_track` / `network_error` / `rate_limited` →
  corresponding status text in the lyric lane.
- `lyrics_worker.lyrics_ready(track_id, lyric_lines)` → `LyricsWidget.set_lyrics()`
  when `track_id` still matches the current track; stale results are ignored.

---

## UI Design

### Default State (not hovered)

```
+--------------------------------------------+
|         Song Name — Artist Name            |  ← white text, small font
|                                            |
|        current lyric line here             |  ← Spotify green (#1DB954), larger font, centered
|                                            |
|████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|  ← 2px green progress bar
+--------------------------------------------+
```

### Hovered State (V2)

```
0     5                        50     60          80      90 95 100
+------------------------------------------------------------------+
|     Song Name - Artist Name        [prev play next]        [X]   |
|                                                                  |
|                 current lyric / no synced lyrics / offline       |
|                                                                  |
|████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
+------------------------------------------------------------------+
```

V1/V1.2: hover shows the close button only. V1.3 moves network offline status into the lyric lane, not a right-top overlay. V2 uses fixed top-row slots: title roughly 5-50, controls roughly 60-80, close roughly 90-95. The 50-60 and 80-90 ranges are intentional buffer space, not stretch areas. The controls appear on hover inside their own slot and never share space with the title or close button. Playlist buttons are deferred out of V2 (see "Playlist Add Feature" below).

### Visual Style

- **Window surface:** Frameless **opaque** top-level window. Rounded corners and the
  Spotify-green border are both drawn by the **Windows 11 DWM** (`DwmSetWindowAttribute`:
  `DWMWCP_ROUND` + `DWMWA_BORDER_COLOR`); the inner `#121212` panel draws no border/radius of
  its own. `WA_TranslucentBackground` is intentionally NOT used — that layered-window path
  caused stale visual buffers during live track changes. An interim `QRegion` mask fixed the
  staleness but gave jagged (non-anti-aliased) corners; the DWM path is both smooth and stable
  (opaque window, no dependency on continuous repaint). The DWM corner/border attributes are
  Windows 11 APIs; on older Windows the call is a guarded no-op and the window falls back to
  square and borderless.
- **Song name / artist:** White `#FFFFFF`
- **Lyrics text:** Spotify green `#1DB954`
- **Control icons:** White `#FFFFFF`
- **Progress bar:** Spotify green `#1DB954` on dark gray track
- **Close button:** White
- **Design:** Flat panel, no reflections, highlights, gradients, or glass effects.
- **Font:** V1.3 uses system font detection: `Microsoft JhengHei UI` → `Microsoft JhengHei`
  → `Segoe UI`. The original bundled `NotoSansTC-VF.ttf` asset is retained in `assets/fonts/`
  but is not loaded because `QFontDatabase.addApplicationFont()` caused a Qt 6.11.0 access
  violation during live testing.

### Window Behavior

- Frameless (`Qt.FramelessWindowHint`)
- Always on top (`Qt.WindowStaysOnTopHint`)
- Rounded corners + green border via Windows 11 DWM (`DwmSetWindowAttribute`: `DWMWCP_ROUND` + `DWMWA_BORDER_COLOR`), not a transparent layered window or a `QRegion` mask
- Draggable by clicking and holding anywhere on the window
- Position saved to config on close, restored on launch
- System tray icon (added V1.3): running-status indicator, left-click raises the widget to
  front, right-click menu (Show/Hide, Open log file, Quit). Closing/Quit still exits the app.

### Playlist Add Feature (DEFERRED out of V2)

Split out of V2 into its own later phase (roadmap, 2026-05-25): do playback controls +
marquee first. When built later:

- **Plus button (＋):** Adds current track to the remembered default playlist. First use requires selecting a playlist first.
- **Playlist picker button (📋):** Opens a dropdown/popup listing user's playlists. Selecting one sets it as the new default target.
- **Memory:** Default playlist ID persisted in config. Survives app restart.
- Requires the playlist OAuth scopes — only requested when this phase is built, not in V2.

---

## Data Flow

### Startup

1. Read config file (client_id, tokens, window position)
2. If no `client_id` → show dialog asking user to paste it → save to config
3. If token exists → attempt refresh (save new refresh token from PKCE response)
4. If no token or refresh fails → open browser for PKCE OAuth flow
5. Auth complete → start 1-second Spotify poll timer + local UI timer (150ms)
6. Restore window to saved position

### Two-timer Architecture

| Timer | Interval | Runs on | Purpose |
|---|---|---|---|
| Spotify poll | ~1 second | Worker thread | Fetch authoritative state from API. Emit signals on track change, play/pause toggle, seek jump. |
| Local UI timer | ~150ms | Main thread | Advance estimated `progress_ms` using monotonic clock. Update lyric line and progress bar smoothly. |

The local timer interpolates between polls. Each Spotify poll resyncs the local estimate. Detected seek jumps (progress jumps > 3 seconds from expected) trigger immediate resync.

### Per-second Spotify Poll Cycle (Spotify worker thread)

1. Call `GET /v1/me/player/currently-playing`
2. If `currently_playing_type` is not `track` → emit "not a track" signal, skip everything below
3. Compare `item.id` to previous track ID
4. **Track changed?** → emit `track_changed(track_info)` signal (lyrics worker picks this up independently)
5. Emit `state_synced(progress_ms, is_playing, local_timestamp)` → UI resyncs local timer
6. Polling continues on schedule regardless of whether lyrics lookup is still pending

### Lyrics Lookup (Lyrics worker thread, triggered by track_changed signal)

1. Receive `track_changed(track_info)`
2. Check session cache by track ID. If cache hit → emit `lyrics_ready`, done.
3. Cache miss → query lrclib: `GET /api/get?track_name=...&artist_name=...&album_name=...&duration=<seconds>`
4. Has `syncedLyrics` → parse into sorted `[(ms, text), ...]`, cache result, emit `lyrics_ready`
5. No result or no `syncedLyrics` → try `GET /api/search`, rank results
6. Found acceptable match → cache result, emit `lyrics_ready`
7. Successful response but no synced lyrics anywhere → cache "no lyrics" for this track ID, emit `no_lyrics`
8. Network error / timeout / 5xx → do NOT cache. Display temporary "unavailable" state. Allow retry on next visit to this track.

### Local UI Timer Cycle (main thread, ~150ms)

1. If not playing → do nothing
2. Advance estimated progress: `estimated_ms = last_synced_ms + (now - last_sync_time)`
3. Binary search lyric list → find current line → update display if changed
4. Update progress bar: `estimated_ms / duration_ms`

### Lyric Line Matching

Binary search on the sorted timestamp list. Find the last entry where `timestamp_ms <= estimated_ms`. That is the current line.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Token expired (HTTP 401) | Auto-refresh with refresh token. If response includes new refresh_token, save it; otherwise keep existing. Retry the failed request. |
| Refresh token invalid | Show prompt "please re-authorize", restart PKCE OAuth flow |
| Network disconnected (cannot reach Spotify) | Freeze on last state, show central `offline` text in the lyric lane, retry every 5 seconds. Do not show a right-top offline overlay. |
| lrclib query fails (timeout / 5xx) | Display temporary "lyrics unavailable" state. Do NOT cache this failure. Allow retry if user returns to this track later. |
| lrclib returns success but no syncedLyrics | Cache "no lyrics" for this track ID. Display "no synced lyrics". |
| Spotify not playing anything | Display "not playing", progress bar at zero, continue polling |
| Non-track playback (podcast / ad) | Display "not a track", hide progress bar, skip lyrics/playlist logic |
| Playback control API fails (V2) | Log the HTTP status/error with a capped body snippet. For 429, respect `Retry-After` and apply a short local cooldown so repeated clicks do not hammer Spotify. UI can otherwise remain unchanged. Do not queue automatic retries for user-click controls; the next user click after cooldown dispatches normally. This applies only to playback-control clicks, not lyrics lookup retry behaviour. |
| Add to playlist fails (deferred playlist phase) | Log the HTTP status/error; playlist UI behavior is decided in the later playlist phase. |
| First launch, no config file | Create default config, prompt for `client_id`, then start OAuth |
| Stale lyrics response | If lyrics worker returns result for a track_id that is no longer current, silently discard |

---

## Config File

Location: `%APPDATA%/spotify-lyrics-widget/config.json` (per-user, standard Windows convention). During development, also add `config.json` to `.gitignore` as a safety net.

```json
{
  "client_id": "your_spotify_app_client_id",
  "access_token": "...",
  "refresh_token": "...",
  "token_expires_at": 1716400000,
  "window_x": 100,
  "window_y": 100
}
```

Notes:
- No `client_secret` (PKCE flow does not use one)
- `token_expires_at` is a Unix timestamp in seconds
- Planned future config additions:
  - V1.4: `netease_fallback` boolean, default `true`
  - V2: `granted_scope` string for one-time re-auth when scopes change
  - Deferred playlist phase: `default_playlist_id` as a bare Spotify playlist ID, not a URI

---

## Tech Stack

- **Language:** Python 3.11+
- **GUI:** PyQt6
- **HTTP:** httpx
- **Chinese script conversion (V1.4):** `zhconv` (pure-Python Traditional/Simplified, MediaWiki tables) — used to match Traditional Spotify metadata against Simplified NetEase results and to render NetEase lyrics as `zh-tw`.
- **Packaging:** PyInstaller → single .exe
- **Platform:** Windows only

---

## Implementation Phases

### V1 — Lyrics Core

Prove the main idea works end-to-end:

1. PKCE auth + token refresh
2. Current track polling (worker thread)
3. lrclib lookup with session cache (worker thread)
4. LRC parsing + binary search line matching
5. Fixed-height lyric display with local timer interpolation, capped to two lines
6. Frameless always-on-top draggable widget
7. Read-only progress bar (2px)
8. Config persistence (client_id, tokens, window position) in AppData
9. Error handling for all V1 scenarios

### V2 — Playback Controls & Title Marquee

Add after V1.3. **Scope confirmed 2026-05-25: playback controls + marquee only.**
Playlist add/picker is split out into a separate later phase (see "Playlist Add Feature"
above) — do NOT build it in V2.

1. Hover-to-reveal playback controls (play/pause, next, prev) inside the fixed controls slot
2. Additional OAuth scope: `user-modify-playback-state` only (playlist scopes deferred with
   the playlist phase)
3. Title/control layout rework (folds in a decided V1.x polish):
   - **At rest: left-align the title inside a fixed title slot.** Do not center the title
     against the whole window and do not reserve a shared right-side overlay gutter. The top
     row has explicit slots: title, controls, close.
   - **On hover: marquee the full title** per the V1.2 plan's "V2 Future Notes" (dedicated
     `MarqueeLabel`, fixed geometry, clipped painting, slow ping-pong, scroll the rendered
     full string — never substring-slice, to stay CJK/Unicode-correct). Only animate when
     the full title is wider than the available width.
   - **Controls stay in their own slot.** Previous overlay/gutter wording is rejected
     because it can collide with offline/close/title states. V1.3 already moved `offline`
     into the lyric lane, so V2 only needs title, controls, and close in the top row.
   - **Clicks have a brake.** Playback controls should drop/debounce repeated clicks while a
     request is already in flight, and 429 cooldown should block dispatch until the user
     clicks again after the cooldown expires.
   - Decided 2026-05-25: do NOT ship marquee as a standalone V1.3. The alignment fix is
     folded here because V2 reworks title rendering anyway.

### V3 — Packaging

1. PyInstaller → single .exe
2. First-run UX polish

---

## Policy Note

This is a personal tool. If published publicly on GitHub, note that Spotify's API documentation includes a policy warning about synchronizing Spotify content with visual media. Verify compliance before distributing as a public application.

---

## Out of Scope

- Lyrics translation
- Mac / Linux support
- Progress bar seek (drag to position)
- Genius or other fallback lyrics sources
- plainLyrics display
- Transparency / glass effects
- Commercial distribution
