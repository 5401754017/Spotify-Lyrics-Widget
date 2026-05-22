# Spotify Lyrics Widget V1 Plan Review

Date: 2026-05-22

Target plan: `2026-05-22-spotify-lyrics-widget-v1.md`

## Verdict

The V1 plan follows the approved spec scope. It keeps playlist and playback controls out of V1, separates Spotify polling from lyrics lookup, and gives the project a useful test-first task order.

Do not execute the plan unchanged. Fix the issues below first so the implementation plan does not encode known auth and provider-failure bugs.

## Findings To Fix Before Implementation

### 1. The Spotify 401 path does not satisfy the spec

Plan references:

- Spotify worker 401 handling around lines 898-930
- Main app auth-expired handling around lines 1829-1914

Current plan behavior:

- A Spotify poll response with HTTP 401 only emits `auth_expired`.
- `App._on_auth_expired()` stops the worker, calls `_ensure_auth()`, then starts the same worker again.
- `_ensure_auth()` returns early when `token_expires_at` still says the token is valid.

Problems:

- A rejected access token can still look unexpired locally, so the app can restart with the same bad access token.
- `SpotifyWorker.stop()` sets `_running = False`, so starting that same worker instance again will not resume polling unless the plan explicitly resets or replaces the worker.
- The design spec says HTTP 401 should refresh and retry the failed request.

Plan change:

- Add tests for a 401 poll response.
- Make 401 force one refresh attempt and retry the Spotify request with the new access token.
- If refresh fails, enter the re-authorization path.
- Define worker lifecycle on re-auth: either keep refresh/retry inside the worker safely, or replace/restart the worker with an explicit running-state reset. Do not rely on the current stop/start path.

### 2. LRCLIB 5xx responses will be cached as "no lyrics"

Plan references:

- `fetch_lyrics_from_lrclib()` around lines 1219-1266
- `LyricsWorker.run()` around lines 1289-1318

Current plan behavior:

- `httpx.get()` responses are checked only for `status_code == 200`.
- Non-200 search responses fall through to `return None`.
- `LyricsWorker` treats `None` as a real no-lyrics result and negative-caches it.

Problem:

- `httpx` does not raise just because the server returned 5xx. A LRCLIB 500 or 503 response will currently become cached `"no lyrics"`, which contradicts the spec.

Plan change:

- Add tests for LRCLIB 5xx on exact lookup and fallback search.
- Keep real no-match / no-`syncedLyrics` responses separate from transient provider failures.
- Return or raise a distinct transient-unavailable result for timeout, network failure, and 5xx so the worker emits `lyrics_unavailable` without negative caching.

### 3. OAuth callback server should be listening before the browser opens

Plan reference:

- OAuth callback server around lines 1719-1755

Current plan behavior:

- Builds the authorization URL.
- Opens the browser.
- Only then binds `127.0.0.1:8888`.

Problem:

- If Spotify redirects quickly for an already logged-in and already-authorized user, the callback can race the local server bind.

Plan change:

- Bind the local callback server before opening the browser.
- Then open the browser and wait for the callback.

### 4. LRCLIB fallback ranking in the plan is weaker than the spec

Plan reference:

- `rank_search_results()` around lines 1186-1216

Current plan behavior:

- Duration filtering is present.
- Track and artist matching only use lowercase exact equality.

Problem:

- The spec asks for closest normalized track and artist matching. Exact lowercase comparison does not normalize punctuation, whitespace, or common version text, and it does not express "closest".

Plan change:

- Add small normalization tests and define the actual V1 normalization rule in the plan.
- Keep it conservative. A simple normalized comparison and duration-first score is enough for V1, but the plan should match what the spec promises.

## Smaller Plan Edits

- Task 10 adds offline behavior but only shows a widget test. Add at least one worker-level test for network error and recovery signals or narrow the plan so the untested retry behavior is not hand-waved.
- State text in the widget code examples uses decorative glyphs. Use plain text state labels for V1 unless the UI design explicitly chooses symbols later.
- The final task uses `git add -A` around line 2086. Replace it with explicit staging for the task's files, or remove the final commit step if the task commits already cover the implementation. `git add -A` can sweep in unrelated review or user files from the worktree.

## Good Parts To Keep

- V1 scope stays focused on auth, polling, synced lyrics, UI timing, config, and error states.
- Pure LRC parsing is separated from the worker and has direct tests.
- Spotify poll timing and UI interpolation are not conflated.
- Lyrics lookup has its own worker and stale-result handling remains part of the app wiring.
- V2 playback controls and playlist scopes are not pulled into V1.
