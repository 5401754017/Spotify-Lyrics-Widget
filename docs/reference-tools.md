# Reference Tools — Existing Projects We Can Reuse / Learn From

Date: 2026-05-25

Curated shortlist of existing GitHub projects relevant to **this** project: a
Python / PyQt6, Windows, desktop synced-lyrics widget (V1), later adding playback
controls + playlist (V2).

**Filter used:** fit for this stack and these features, NOT GitHub star count. Stars
measure general popularity, not fit. Most high-star Spotify repos are full apps,
daemons, downloaders, or libraries in Rust/C#/Go/Swift — they do not compose into a
Python PyQt6 widget. The fitting intersection is genuinely small.

---

## 1. Spotify Web API client (for V2 playback control + playlist)

- **[spotipy](https://github.com/spotipy-dev/spotipy)** — de-facto Python Spotify Web
  API library. Has a `SpotifyPKCE` auth manager that matches our PKCE flow, plus
  currently-playing, playback control (play/pause/next/prev/seek), and full playlist
  management.
  - Use for the **new V2 endpoints**. Do NOT rip out our existing TDD'd `auth.py` /
    `spotify_worker.py` for V1 — only adopt spotipy where it saves writing new V2 calls.
- Alternative, more complete client: **[thlucas1/SpotifyWebApiPython](https://github.com/thlucas1/SpotifyWebApiPython)**.

## 2. Lyrics-source fallback (fills LRCLIB gaps — the "official lyrics" we deferred)

V1 decided LRCLIB-only and accepted "missing synced lyrics" as a limitation. If we ever
want to fill that gap, this already exists:

- **[akashrchandran/syrics](https://github.com/akashrchandran/syrics)** (CLI, saves
  `.lrc`) + **[spotify-lyrics-api](https://github.com/akashrchandran/spotify-lyrics-api)**
  (REST) — fetch Spotify's official (Musixmatch-backed) line-synced lyrics.
  - **Caveat:** requires an `sp_dc` cookie (logged-in session). Unofficial, expires,
    ToS gray area. Use only as an **optional fallback when LRCLIB misses**, never the
    primary source.

## 3. Sync / matching + Unicode + offset — reference only

- **[raitonoberu/sptlrx](https://github.com/raitonoberu/sptlrx)** — terminal synced
  lyrics, pulls directly from LRCLIB, handles long lines & Unicode well, has a sync
  **offset** setting. Go, not Python — reference its matching logic and offset approach
  (relevant to the audio-latency offset idea and the V2 marquee's CJK correctness).

## 4. Multi-source lyrics idea — reference for a future V1.4 enhancement

- **[SimonIT/spotifylyrics](https://github.com/SimonIT/spotifylyrics)** — fetches lyrics
  for the current track across multiple sources (and players: Spotify/Tidal/VLC).
  Reference for a multi-source strategy. Add sources incrementally; do not wire up many
  at once.

## 5. Closest desktop products — borrow UI / behavior

- **[Daniel-Grounin/Spotify-Desktop-Widget](https://github.com/Daniel-Grounin/Spotify-Desktop-Widget)**
  — **PyQt6** Spotify widget with playback controls + real-time song info (Win10). Same
  stack as us; most direct reference/borrow target for the V2 control row.
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
