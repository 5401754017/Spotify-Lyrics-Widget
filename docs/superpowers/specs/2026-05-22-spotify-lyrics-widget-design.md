# Spotify Lyrics Widget Design Spec

Date: 2026-05-22

---

## Overview

A Windows desktop floating widget that displays real-time synced lyrics for the currently playing Spotify track. Single-line subtitle mode, always-on-top, with hover-to-reveal playback controls.

**Target user:** Personal use only (developer themselves). Requires Spotify Premium.

---

## Lyrics Source

- **Primary and only source:** lrclib.net (free, no auth required, ~3M tracks)
- **Primary endpoint:** `GET /api/get` with `track_name`, `artist_name`, `album_name`, `duration` for exact match
- **Secondary endpoint:** If exact match returns nothing, fallback to `GET /api/search?track_name=...&artist_name=...` for fuzzy matching. Pick the first result with `syncedLyrics`.
- **Only use `syncedLyrics`** (LRC format with timestamps). If `syncedLyrics` is null, display "no synced lyrics available" regardless of whether `plainLyrics` exists
- **No external fallback sources.** No Genius, no Musixmatch, no scraping

---

## Spotify API

### Authentication

- **Prerequisites:** User must create a Spotify App at https://developer.spotify.com/dashboard, obtain `client_id` and `client_secret`, and set redirect URI to `http://localhost:8888/callback`
- **Flow:** Authorization Code Flow (not PKCE, not Implicit)
- **Scopes required:**
  - `user-read-currently-playing` (poll current track)
  - `user-modify-playback-state` (play/pause, next, prev)
  - `playlist-modify-public` (add to playlist)
  - `playlist-modify-private` (add to playlist)
  - `playlist-read-private` (list user's playlists)
- **Token refresh:** Access token expires in 1 hour. Auto-refresh using refresh token before expiry. Refresh token itself does not expire in this flow.
- **First-time auth:** Open system browser to Spotify login page, run a temporary local HTTP server to receive the OAuth callback

### Polling

- **Endpoint:** `GET /v1/me/player/currently-playing`
- **Frequency:** Every 1 second
- **Key response fields:** `item.id`, `item.name`, `item.artists`, `item.album.name`, `item.duration_ms`, `progress_ms`, `is_playing`

### Playback Control Endpoints

- `PUT /v1/me/player/pause` — pause
- `PUT /v1/me/player/play` — resume
- `POST /v1/me/player/next` — skip to next
- `POST /v1/me/player/previous` — skip to previous
- All require `user-modify-playback-state` scope and Spotify Premium

### Playlist Endpoints

- `GET /v1/me/playlists` — list user's playlists (for playlist picker)
- `POST /v1/playlists/{playlist_id}/tracks` — add current track to playlist

---

## Architecture

### Modules

| Module | Responsibility |
|---|---|
| `auth` | Spotify OAuth flow, token storage, auto-refresh |
| `spotify_player` | Poll currently playing track every 1s, emit state-change signals (track changed, play/pause toggled, progress updated). Expose playback control methods (play, pause, next, prev) |
| `lyrics` | Query lrclib.net, parse LRC timestamps into sorted list of `(timestamp_ms, line_text)` |
| `playlist` | Fetch user's playlists, add track to playlist, manage default playlist memory |
| `config` | Read/write JSON config file: tokens, window position (x, y), default playlist ID |
| `ui` | PyQt6 frameless always-on-top draggable window, lyric display, hover controls, progress bar |

### Dependency Direction

```
ui → spotify_player, lyrics, playlist → auth, config
```

### Inter-module Communication

PyQt6 Signals/Slots:

- `spotify_player.track_changed(track_info)` → `lyrics.fetch()`, `ui.update_track_info()`
- `spotify_player.progress_updated(ms)` → `ui.update_lyric_line()`, `ui.update_progress_bar()`
- `spotify_player.playback_toggled(is_playing)` → `ui.freeze_or_resume()`

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

### Hovered State

```
+--------------------------------------------+
|         Song Name — Artist Name          ✕ |  ← close button appears top-right
|       ⏮    ⏯    ⏭    ＋    📋           |  ← control row appears
|                                            |
|        current lyric line here             |
|                                            |
|████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
+--------------------------------------------+
```

### Visual Style

- **Background:** Pure black `#000000`, fully opaque
- **Song name / artist:** White `#FFFFFF`
- **Lyrics text:** Spotify green `#1DB954`
- **Control icons:** White `#FFFFFF`
- **Progress bar:** Spotify green `#1DB954` on dark gray track
- **Close button:** White
- **Design:** Completely flat. No transparency, no reflections, no highlights, no gradients
- **Font:** System sans-serif

### Window Behavior

- Frameless (`Qt.FramelessWindowHint`)
- Always on top (`Qt.WindowStaysOnTopHint`)
- Draggable by clicking and holding anywhere on the window
- Position saved to config on close, restored on launch
- No system tray integration. Close = exit the app.

### Playlist Add Feature

- **Plus button (＋):** Adds current track to the remembered default playlist. First use requires selecting a playlist first.
- **Playlist picker button (📋):** Opens a dropdown/popup listing user's playlists. Selecting one sets it as the new default target.
- **Memory:** Default playlist ID persisted in config. Survives app restart.

---

## Data Flow

### Startup

1. Read config file (tokens, window position, default playlist ID)
2. If token exists → attempt refresh
3. If no token or refresh fails → open browser for OAuth flow
4. Auth complete → start 1-second poll timer
5. Restore window to saved position

### Per-second Poll Cycle

1. Call `GET /v1/me/player/currently-playing`
2. Compare `item.id` to previous track ID
3. **Track changed?**
   - Query lrclib: `GET /api/get?track_name=...&artist_name=...&album_name=...&duration=...`
   - `syncedLyrics` exists → parse into sorted `[(ms, text), ...]`
   - No `syncedLyrics` → set state to "no synced lyrics"
4. **is_playing = true?**
   - Binary search `progress_ms` in lyric list → find current line → display
   - Update progress bar: `progress_ms / duration_ms`
5. **is_playing = false?**
   - Freeze lyric on last displayed line, stop progress bar

### Lyric Line Matching

Binary search on the sorted timestamp list. Find the last entry where `timestamp_ms <= progress_ms`. That is the current line.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Token expired (HTTP 401) | Auto-refresh with refresh token, retry the failed request |
| Refresh token invalid | Show prompt "please re-authorize", restart OAuth flow |
| Network disconnected (cannot reach Spotify) | Freeze on last state, show offline indicator icon, retry every 5 seconds |
| lrclib query fails (timeout / 5xx) | Display "no synced lyrics", no retry (next track change will re-query) |
| Spotify not playing anything | Display "not playing", progress bar at zero, continue polling |
| Playback control API fails | Silent failure (user notices via Spotify app) |
| Add to playlist fails | Plus button flashes red briefly |
| First launch, no config file | Create default config, go straight to OAuth |

---

## Config File

`config.json` in the app directory (same folder as the script/exe):

```json
{
  "client_id": "your_spotify_app_client_id",
  "client_secret": "your_spotify_app_client_secret",
  "access_token": "...",
  "refresh_token": "...",
  "token_expires_at": 1716400000,
  "window_x": 100,
  "window_y": 100,
  "default_playlist_id": "spotify:playlist:xxxxx"
}
```

**Security note:** This file contains sensitive tokens. Must be in `.gitignore`.

---

## Tech Stack

- **Language:** Python 3.11+
- **GUI:** PyQt6
- **HTTP:** requests (or httpx)
- **Packaging:** PyInstaller → single .exe
- **Platform:** Windows only

---

## Out of Scope

- Lyrics translation
- Mac / Linux support
- System tray
- Progress bar seek (drag to position)
- Genius or other fallback lyrics sources
- plainLyrics display
- Transparency / glass effects
- Commercial distribution
