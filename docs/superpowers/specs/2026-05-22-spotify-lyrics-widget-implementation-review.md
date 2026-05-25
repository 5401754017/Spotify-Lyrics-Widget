# Spotify Lyrics Widget Spec - Implementation Review

Date: 2026-05-22

Target spec: `2026-05-22-spotify-lyrics-widget-design.md`

## Verdict

The design direction is workable, and removing the old Genius/plain-lyrics fallback is a good fit for a single-line synced-lyrics widget.

Do not start implementation from the current spec unchanged. Revise the auth flow, first-run flow, playlist contract, network execution model, and lyrics matching rules first.

## Must Fix Before Implementation

### 1. Change OAuth to PKCE and fix the redirect URI

Current spec:

- Uses Authorization Code Flow with `client_secret`
- Registers `http://localhost:8888/callback`

Problems:

- Spotify no longer allows `localhost` as a redirect URI. Use an explicit loopback IP such as `http://127.0.0.1:8888/callback`.
- This is a desktop app. A bundled executable cannot safely keep a client secret, so PKCE is the better default flow.

Spec change:

- Use Authorization Code Flow with PKCE.
- Use `http://127.0.0.1:8888/callback` as the initial callback URI.
- Keep `client_id` in config.
- Remove `client_secret` from the normal runtime config and auth flow.

### 2. Define the first-run credential bootstrap

Current spec says:

1. If no config exists, create a default config.
2. Then go straight to OAuth.

That cannot work unless `client_id` already exists.

Spec change:

- On first run, ask for `client_id` before starting OAuth, then persist it.
- Keep this simple because the target user is the developer.

### 3. Fix the playlist API and stored identifiers

Current spec:

- Uses `POST /v1/playlists/{playlist_id}/tracks`
- Stores `default_playlist_id` with an example value like `spotify:playlist:xxxxx`
- The currently-playing fields do not include the track URI needed for add-to-playlist

Problems:

- The current Spotify endpoint is `POST /v1/playlists/{playlist_id}/items`.
- A field named `default_playlist_id` should store a bare playlist ID, not a Spotify URI.
- Add-items needs the current track URI.

Spec change:

- Use `POST /v1/playlists/{playlist_id}/items`.
- Store `default_playlist_id` as the bare ID.
- Include `item.uri` in the player state used by the playlist module.
- Decide whether the playlist picker shows only writable playlists. `GET /me/playlists` can include playlists the user follows but cannot modify.

### 4. Add an explicit background network model

Current architecture lists PyQt signals and slots but does not state where HTTP calls run.

If Spotify polling or LRCLIB lookup runs synchronously on the GUI thread, the floating window will freeze during network latency.

Spec change:

- Spotify polling runs off the GUI thread.
- LRCLIB lookup runs off the GUI thread.
- UI updates arrive through signals.
- Every lyric lookup result carries the Spotify track ID it was requested for.
- Ignore stale lyric results if the user has already changed tracks.

### 5. Tighten currently-playing state handling

Current spec assumes the current item is always a Spotify track with all listed fields.

Spec change:

- Define behavior for no active item / no content response.
- Define behavior for podcast episodes or other non-track playback.
- Do not run lyrics lookup or add-to-playlist logic for non-track items.
- Treat Spotify poll responses as authoritative for track changes, pause/resume, seek jumps, and progress resync.

### 6. Separate API polling from lyric display timing

The one-second Spotify poll cadence is fine as a resync source, but it should not be the only UI clock.

Spec change:

- Poll Spotify roughly once per second.
- Store the last known `progress_ms`, `is_playing`, and local observation time.
- While playing, advance the displayed progress from a local monotonic timer around every `100-250ms`.
- Resync from the next Spotify poll.
- Freeze on pause and jump immediately on detected seek/track change.

This keeps API traffic low while making lyric line changes and the progress bar feel smoother.

### 7. Make LRCLIB matching less naive

Current spec:

- Uses LRCLIB exact lookup first.
- For search fallback, takes the first result with `syncedLyrics`.

Problems:

- Spotify provides `duration_ms`; LRCLIB expects duration in seconds.
- Search results can contain live, remaster, alternate, or same-name matches.

Spec change:

- Explicitly convert Spotify duration milliseconds to seconds for LRCLIB exact lookup.
- For fallback search, rank results instead of taking the first synced result.
- Prefer synced lyrics with a close duration and close normalized track / artist / album metadata.
- Cache successful and failed lyric lookups by Spotify track ID for the session.

## Recommended V1 Scope

Implement the lyrics widget core first:

1. PKCE auth
2. Current track polling
3. LRCLIB lookup and LRC parsing
4. One-line lyric display with local progress timing
5. Frameless always-on-top draggable widget
6. Config persistence for auth tokens and window position

Move playlist add / playlist picker after the lyric widget core works. It adds scopes, UI state, writable-playlist edge cases, and extra failure paths without proving the main idea.

## Config Recommendation

Do not store runtime config beside the script or packaged exe by default.

Use a per-user app-data location for:

- `client_id`
- tokens
- window position
- default playlist ID if playlist support remains

Keeping `config.json` in `.gitignore` is still useful during development, but `.gitignore` is not the runtime security or packaging strategy.

## Policy Note Before Public Release

This is described as a personal tool. If it will be published as a public app or portfolio project, verify Spotify policy first. The currently-playing API documentation includes a policy warning about synchronizing Spotify content with visual media, so do not assume a public synced-lyrics widget is automatically acceptable.

## Follow-up Review After Spec Revision

The revised design spec now fixes the major implementation blockers from the first review:

- PKCE replaces the client-secret desktop auth flow.
- The redirect URI uses `127.0.0.1`.
- First run asks for `client_id` before OAuth.
- LRCLIB lookup now converts duration, ranks fallback search results, and adds a session cache.
- Spotify polling and local UI timing are separated.
- HTTP work is explicitly off the GUI thread.
- V1 lyrics core and V2 controls / playlist work are separated.
- Runtime config moved to AppData.

Keep the LRCLIB-only lyrics source decision. Missing synced lyrics are an accepted limitation for this version; do not add Spotify reverse engineering, scraping, Genius, Musixmatch, or local `.lrc` fallback to the current spec.

Before implementing V1, make these remaining spec edits:

### A. Do not require refresh-token rotation on every PKCE refresh

Current revised spec says PKCE returns a new refresh token on each refresh and the old token becomes invalid.

That is too strict. Spotify's refresh-token documentation says a refreshed response may or may not include `refresh_token`.

Spec change:

- If the refresh response includes a new `refresh_token`, save it.
- If it does not include one, keep using the existing refresh token.

Update every place that currently says to always save a new PKCE refresh token.

### B. Keep Spotify polling separate from LRCLIB fetch execution

The revised architecture correctly gives Spotify polling and LRCLIB lookup separate workers, but the revised per-second poll cycle still performs the LRCLIB lookup inside the Spotify poll flow.

That can stall state polling when LRCLIB is slow.

Spec change:

- Spotify poll worker only fetches Spotify state, detects track change, and emits `track_changed(track_info)`.
- Lyrics worker receives track changes, checks cache, queries LRCLIB, parses lyrics, and emits lyric results.
- Spotify polling continues on schedule while lyrics lookup is pending.

### C. Do not negative-cache transient LRCLIB failures

Current revised error handling caches LRCLIB timeout / 5xx as `"no lyrics"` for the track.

That mixes a temporary provider failure with a real no-synced-lyrics result.

Spec change:

- Cache a no-lyrics result when LRCLIB lookup succeeds but no acceptable `syncedLyrics` result exists.
- Do not cache timeout, network failure, or 5xx as no-lyrics for the whole session.
- Display a temporary no-lyrics / unavailable state for that attempt and allow a later return to the same track to query again.

### D. Resolve two small spec inconsistencies

- V1 hover state says the close button appears on hover, while the V2 phase list also says to add the close button. Pick one phase and keep the UI spec consistent.
- If V2 intentionally shows only playlists owned by the current user, say `owned playlists only`. Do not call that the full set of writable playlists because collaborative playlist behavior is separate.

## Official References Checked

- Spotify Redirect URIs: https://developer.spotify.com/documentation/web-api/concepts/redirect_uri
- Spotify Authorization Code with PKCE: https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow
- Spotify Refreshing Tokens: https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
- Spotify Get Currently Playing Track: https://developer.spotify.com/documentation/web-api/reference/get-the-users-currently-playing-track
- Spotify Add Items to Playlist: https://developer.spotify.com/documentation/web-api/reference/add-tracks-to-playlist
- Spotify Get Current User's Playlists: https://developer.spotify.com/documentation/web-api/reference/get-a-list-of-current-users-playlists
- Spotify Rate Limits: https://developer.spotify.com/documentation/web-api/concepts/rate-limits
- LRCLIB API docs: https://lrclib.net/docs
