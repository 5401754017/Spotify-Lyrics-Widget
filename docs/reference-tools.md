# Reference Tools — Existing Projects We Can Reuse / Learn From

Date: 2026-05-25

Curated shortlist of existing GitHub projects relevant to **this** project: a
Python / PyQt6, Windows, desktop synced-lyrics widget. Playback controls shipped in V2;
playlist add/picker remains deferred.

**Filter used:** fit for this stack and these features, NOT GitHub star count. Stars
measure general popularity, not fit. Most high-star Spotify repos are full apps,
daemons, downloaders, or libraries in Rust/C#/Go/Swift — they do not compose into a
Python PyQt6 widget. The fitting intersection is genuinely small.

---

## 1. Spotify Web API client (playback shipped; playlist still deferred)

- **[spotipy](https://github.com/spotipy-dev/spotipy)** — de-facto Python Spotify Web
  API library. Has a `SpotifyPKCE` auth manager that matches our PKCE flow, plus
  currently-playing, playback control (play/pause/next/prev/seek), and full playlist
  management.
  - V2.01 currently uses direct `httpx` calls in `src/playback.py`. Do NOT rip out the
    existing TDD'd `auth.py`, `spotify_worker.py`, or `playback.py` just to adopt a client.
    Reconsider `spotipy` only if a future playlist feature would meaningfully reduce code.
- Alternative, more complete client: **[thlucas1/SpotifyWebApiPython](https://github.com/thlucas1/SpotifyWebApiPython)**.

## 2. Lyrics-source fallback (official lyrics route remains deferred)

V1.4 added a NetEase fallback for LRCLIB confirmed misses. If we ever want a separate
"official Spotify lyrics" fallback, this route already exists but remains rejected for the
current core path:

- **[akashrchandran/syrics](https://github.com/akashrchandran/syrics)** (CLI, saves
  `.lrc`) + **[spotify-lyrics-api](https://github.com/akashrchandran/spotify-lyrics-api)**
  (REST) — fetch Spotify's official (Musixmatch-backed) line-synced lyrics.
  - **Caveat:** requires an `sp_dc` cookie (logged-in session). Unofficial, expires,
    ToS gray area. Do not add this to the core path without a new explicit design decision.

## 3. Sync / matching + Unicode + offset — reference only

- **[raitonoberu/sptlrx](https://github.com/raitonoberu/sptlrx)** — terminal synced
  lyrics, pulls directly from LRCLIB, handles long lines & Unicode well, has a sync
  **offset** setting. Go, not Python — reference its matching logic and offset approach
  (relevant to the audio-latency offset idea and the V2 marquee's CJK correctness).

## 4. Multi-source lyrics idea — reference for any future fallback expansion

- **[SimonIT/spotifylyrics](https://github.com/SimonIT/spotifylyrics)** — fetches lyrics
  for the current track across multiple sources (and players: Spotify/Tidal/VLC).
  Reference for a multi-source strategy beyond the current LRCLIB + gated NetEase setup.
  Add sources incrementally; do not wire up many at once.

## 5. Closest desktop products — borrow UI / behavior

- **[Daniel-Grounin/Spotify-Desktop-Widget](https://github.com/Daniel-Grounin/Spotify-Desktop-Widget)**
  — **PyQt6** Spotify widget with playback controls + real-time song info (Win10). Same
  stack as us; still useful as reference for compact control-row behavior, though V2 has
  already shipped its own custom controls.
- **[PureAspiration/SpotifySurface](https://github.com/PureAspiration/SpotifySurface)**
  — Windows pinned-top synced-lyrics window; reference for control buttons and
  edge-snapping.
- **[Nicolas-Arias3142/Spotify_Lyrics_Overlay](https://github.com/Nicolas-Arias3142/Spotify_Lyrics_Overlay)**
  — always-on-top synced-lyrics overlay; concept reference.

## 6. Single-instance guard (for V1.2 Task 5 — clean shutdown / no zombie)

- **[itay-grudev/SingleApplication](https://github.com/itay-grudev/SingleApplication)** —
  Qt6 QtSingleApplication replacement. Handles the "Windows can have multiple listeners"
  gotcha our plan flagged, and lets a 2nd instance tell the 1st to focus. Standard
  pattern: `QLocalServer` + `QSharedMemory` (add a named mutex on Windows).

## 7. Future / likely-overkill

- **[librespot-org/librespot](https://github.com/librespot-org/librespot)** (and
  **[Spotifyd/spotifyd](https://github.com/Spotifyd/spotifyd)**) — open-source Spotify
  Connect **player** library (reimplements the streaming protocol). Only relevant if we
  ever want the widget to be its own player or get playback position without the official
  Spotify app. Rust, requires Premium, far heavier than a lyrics widget needs. Note for
  the future; do not adopt now.

---

**Note:** licenses, maintenance status, and exact capabilities above are from search
summaries and have NOT been individually vetted. Verify license compatibility and
activity before depending on any of these.
