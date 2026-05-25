# Spotify Lyrics Widget V1.4 — NetEase Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When LRCLIB returns no synced lyrics, fall back to NetEase Cloud Music (default on) to fill the gap — primarily for Chinese songs.

**Architecture:** A new `src/netease.py` mirrors the LRCLIB fetcher shape (search → rank by name/artist/duration → fetch LRC → `parse_lrc`), using NetEase public endpoints with no cookie/auth. It takes primitive args (not `TrackInfo`) so it does not import from `lyrics_worker`, avoiding a circular import. `LyricsWorker` gains a `netease_fallback` flag and calls the fallback only when LRCLIB returns `None` (not on LRCLIB exceptions). All NetEase failures are caught inside the fetcher, logged, and surface as `None` so the main flow never breaks.

**Tech Stack:** Python 3, httpx, PyQt6, pytest + pytest-qt. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-26-spotify-lyrics-widget-v1-4-netease-fallback-design.md`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `src/config.py` | Modify | Add `netease_fallback: True` to persisted defaults |
| `src/netease.py` | Create | Search NetEase, rank candidates, fetch + parse LRC; catch-all → `None` |
| `src/lyrics_worker.py` | Modify | `netease_fallback` flag; call fallback when LRCLIB returns `None` |
| `src/main.py` | Modify | Pass `config.netease_fallback` into `LyricsWorker` |
| `tests/test_config.py` | Modify | Assert the new default |
| `tests/test_netease.py` | Create | Ranking, parse, no-match, HTTP error, exception → `None` |
| `tests/test_lyrics_worker.py` | Modify | Fallback called on LRCLIB miss when on; not called when off |

**All commands run from the project root.** `pytest.ini` sets `pythonpath = .`, `testpaths = tests`.

---

## Task 1: Add the `netease_fallback` config flag

**Files:**
- Modify: `src/config.py:9-16`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_netease_fallback_defaults_to_true(tmp_path):
    from src.config import Config

    config = Config(config_dir=tmp_path)
    assert config.netease_fallback is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_config.py::test_netease_fallback_defaults_to_true -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'netease_fallback'`.

- [ ] **Step 3: Add the default in `src/config.py`**

In `_DEFAULTS`, add after `"window_y": 100,`:

```python
        "netease_fallback": True,
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add netease_fallback config flag (default on) (V1.4)"
```

---

## Task 2: NetEase fetcher module

**Why:** Isolates the unofficial NetEase calls and matching from the worker. Pure ranking/parsing is unit-tested; all network failures are swallowed into a `None` return so the fallback can never break the main flow. Takes primitive args (no `TrackInfo`) to avoid importing `lyrics_worker` (which imports this module).

**Files:**
- Create: `src/netease.py`
- Test: `tests/test_netease.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_netease.py`:

```python
from unittest.mock import MagicMock, patch

import httpx

from src.netease import (
    fetch_lyrics_from_netease,
    rank_netease_songs,
    search_netease,
)


def _song(song_id, name, artist, duration_ms):
    return {
        "id": song_id,
        "name": name,
        "artists": [{"name": artist}],
        "duration": duration_ms,
        "album": {"name": "Album"},
    }


class TestRankNeteaseSongs:
    def test_prefers_closest_duration(self):
        songs = [_song(1, "Song", "Artist", 300000), _song(2, "Song", "Artist", 181000)]
        best = rank_netease_songs(songs, "Song", "Artist", target_duration_s=180)
        assert best["id"] == 2

    def test_rejects_duration_beyond_tolerance(self):
        songs = [_song(1, "Song", "Artist", 300000)]
        assert rank_netease_songs(songs, "Song", "Artist", target_duration_s=180) is None

    def test_prefers_exact_name(self):
        songs = [_song(1, "Hello World", "Adele", 180000), _song(2, "Hello", "Adele", 180000)]
        best = rank_netease_songs(songs, "Hello", "Adele", target_duration_s=180)
        assert best["id"] == 2

    def test_empty_returns_none(self):
        assert rank_netease_songs([], "Song", "Artist", target_duration_s=180) is None


class TestSearchNetease:
    @patch("src.netease.httpx.get")
    def test_returns_song_list(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"result": {"songs": [_song(1, "Song", "Artist", 180000)]}},
        )
        songs = search_netease("Song", "Artist")
        assert len(songs) == 1
        assert songs[0]["id"] == 1

    @patch("src.netease.httpx.get")
    def test_non_200_returns_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403, json=lambda: {})
        assert search_netease("Song", "Artist") == []

    @patch("src.netease.httpx.get")
    def test_missing_result_returns_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        assert search_netease("Song", "Artist") == []


class TestFetchLyricsFromNetease:
    @patch("src.netease.httpx.get")
    def test_end_to_end_hit(self, mock_get):
        mock_get.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {"result": {"songs": [_song(11, "Song", "Artist", 180000)]}},
            ),
            MagicMock(
                status_code=200,
                json=lambda: {"lrc": {"lyric": "[00:05.00] Ni Hao\n[00:10.00] Shi Jie"}},
            ),
        ]
        result = fetch_lyrics_from_netease("Song", "Artist", 180000)
        assert result == [(5000, "Ni Hao"), (10000, "Shi Jie")]

    @patch("src.netease.httpx.get")
    def test_no_match_returns_none(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"result": {"songs": []}}
        )
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None

    @patch("src.netease.httpx.get")
    def test_empty_lyric_returns_none(self, mock_get):
        mock_get.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {"result": {"songs": [_song(11, "Song", "Artist", 180000)]}},
            ),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": ""}}),
        ]
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None

    @patch("src.netease.httpx.get")
    def test_network_error_returns_none(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no internet")
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_netease.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.netease'`.

- [ ] **Step 3: Implement `src/netease.py`**

```python
import logging
import re

import httpx

from src.lrc_parser import parse_lrc

NETEASE_SEARCH_URL = "https://music.163.com/api/search/get/web"
NETEASE_LYRIC_URL = "https://music.163.com/api/song/lyric"
DURATION_TOLERANCE_S = 5
_HEADERS = {
    "Referer": "https://music.163.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def rank_netease_songs(
    songs: list[dict], target_track: str, target_artist: str, target_duration_s: int
) -> dict | None:
    """Return the closest NetEase song by name/artist/duration, or None."""
    normalized_track = _normalize(target_track)
    normalized_artist = _normalize(target_artist)
    candidates = []

    for song in songs:
        duration_s = song.get("duration", 0) // 1000
        duration_diff = abs(duration_s - target_duration_s)
        if duration_diff > DURATION_TOLERANCE_S:
            continue

        song_track = _normalize(song.get("name", ""))
        artists = song.get("artists") or []
        song_artist = _normalize(", ".join(a.get("name", "") for a in artists))

        name_match = (
            0
            if song_track == normalized_track
            else (5 if normalized_track in song_track or song_track in normalized_track else 10)
        )
        artist_match = (
            0
            if song_artist == normalized_artist
            else (5 if normalized_artist in song_artist or song_artist in normalized_artist else 10)
        )
        candidates.append((duration_diff + name_match + artist_match, song))

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate[0])
    return candidates[0][1]


def search_netease(track_name: str, artist_name: str) -> list[dict]:
    response = httpx.get(
        NETEASE_SEARCH_URL,
        params={"s": f"{track_name} {artist_name}", "type": 1, "limit": 10},
        headers=_HEADERS,
        timeout=5.0,
    )
    if response.status_code != 200:
        return []
    data = response.json() or {}
    return (data.get("result") or {}).get("songs") or []


def fetch_netease_lyric(song_id) -> str | None:
    response = httpx.get(
        NETEASE_LYRIC_URL,
        params={"id": song_id, "lv": -1, "kv": -1, "tv": -1},
        headers=_HEADERS,
        timeout=5.0,
    )
    if response.status_code != 200:
        return None
    return ((response.json() or {}).get("lrc") or {}).get("lyric")


def fetch_lyrics_from_netease(
    track_name: str, artist_name: str, duration_ms: int
) -> list[tuple[int, str]] | None:
    """Best-effort NetEase synced lyrics. Never raises; returns None on any failure."""
    try:
        songs = search_netease(track_name, artist_name)
        best = rank_netease_songs(songs, track_name, artist_name, duration_ms // 1000)
        if best is None:
            logging.info("NetEase fallback: no match for %s - %s", track_name, artist_name)
            return None

        lyric_text = fetch_netease_lyric(best["id"])
        if not lyric_text:
            logging.info("NetEase fallback: no lyric for %s", best.get("name"))
            return None

        parsed = parse_lrc(lyric_text)
        if not parsed:
            logging.info("NetEase fallback: unparseable lyric for %s", best.get("name"))
            return None

        logging.info("NetEase fallback hit: %s (for %s)", best.get("name"), track_name)
        return parsed
    except Exception:
        logging.exception("NetEase fallback request failed")
        return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_netease.py -v`
Expected: all PASS. (If `test_end_to_end_hit` fails on the parsed tuples, confirm `parse_lrc` returns `(ms, text)` — it does in `src/lrc_parser.py`.)

- [ ] **Step 5: Commit**

```bash
git add src/netease.py tests/test_netease.py
git commit -m "feat: add NetEase lyrics fetcher (search/rank/parse, fail-safe) (V1.4)"
```

---

## Task 3: Wire the fallback into the lyrics worker

**Why:** The worker orchestrates: try LRCLIB; if it returns `None` and the flag is on, try NetEase; otherwise keep existing behaviour. LRCLIB exceptions still go to `lyrics_unavailable` without touching NetEase.

**Files:**
- Modify: `src/lyrics_worker.py` (import, constructor, `run`)
- Modify: `src/main.py` (pass the flag)
- Test: `tests/test_lyrics_worker.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lyrics_worker.py` (it already imports `MagicMock`, `patch`, `TrackInfo`):

```python
def _pending_worker(netease_fallback):
    from src.lyrics_worker import LyricsWorker

    worker = LyricsWorker(netease_fallback=netease_fallback)
    worker._pending_track = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    worker._has_work = True
    return worker


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=[(1000, "ne")])
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_falls_back_to_netease_when_lrclib_misses(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    ready = []
    worker.lyrics_ready.connect(lambda track_id, lyrics: ready.append((track_id, lyrics)))

    worker.run()

    mock_netease.assert_called_once_with("Song", "Artist", 180000)
    assert ready == [("t1", [(1000, "ne")])]


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_netease_not_called_when_disabled(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=False)
    misses = []
    worker.no_lyrics.connect(lambda track_id: misses.append(track_id))

    worker.run()

    mock_netease.assert_not_called()
    assert misses == ["t1"]


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=[(2000, "lrclib")])
def test_netease_not_called_when_lrclib_hits(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    ready = []
    worker.lyrics_ready.connect(lambda track_id, lyrics: ready.append((track_id, lyrics)))

    worker.run()

    mock_netease.assert_not_called()
    assert ready == [("t1", [(2000, "lrclib")])]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_lyrics_worker.py -k "netease or falls_back" -v`
Expected: FAIL — `LyricsWorker.__init__` takes no `netease_fallback`; `fetch_lyrics_from_netease` is not importable from `src.lyrics_worker`.

- [ ] **Step 3: Wire the fallback in `src/lyrics_worker.py`**

Add the import after `from src.lrc_parser import parse_lrc`:

```python
from src.netease import fetch_lyrics_from_netease
```

Change the constructor (lines 178-182) to accept and store the flag:

```python
    def __init__(self, netease_fallback: bool = True):
        super().__init__()
        self._cache = LyricsCache()
        self._pending_track: TrackInfo | None = None
        self._has_work = False
        self._netease_fallback = netease_fallback
```

Replace the fetch/emit block inside `run` (lines 205-214) with:

```python
            try:
                result = fetch_lyrics_from_lrclib(info)
            except (httpx.ConnectError, LrclibUnavailableError):
                self.lyrics_unavailable.emit(info.track_id)
                return

            if not result and self._netease_fallback:
                result = fetch_lyrics_from_netease(
                    info.track_name, info.artist_name, info.duration_ms
                )

            if result:
                self._cache.set(info.track_id, result)
                self.lyrics_ready.emit(info.track_id, result)
            else:
                self._cache.set_no_lyrics(info.track_id)
                self.no_lyrics.emit(info.track_id)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_lyrics_worker.py -v`
Expected: all PASS (existing LRCLIB/cache tests + the three new ones).

- [ ] **Step 5: Pass the flag from `main.py`**

In `src/main.py` `App.__init__`, change:

```python
        self._lyrics_worker = LyricsWorker()
```
to:
```python
        self._lyrics_worker = LyricsWorker(
            netease_fallback=self._config.netease_fallback
        )
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 7: Manual verification**

Run `pythonw run.pyw` and play a Chinese song you know LRCLIB misses (previously showed "no synced lyrics"). Verify:
1. Synced lyrics now appear and scroll in time → NetEase fallback worked.
2. Open the tray "Open log file" (or `%APPDATA%/spotify-lyrics-widget/widget.log`) and confirm a line like `NetEase fallback hit: <song> (for <track>)`.
3. Set `"netease_fallback": false` in `%APPDATA%/spotify-lyrics-widget/config.json`, restart, replay the same song → it shows "no synced lyrics" again (fallback disabled).
4. Play a song with lyrics on LRCLIB → still instant (NetEase not consulted; no extra log line).

- [ ] **Step 8: Commit**

```bash
git add src/lyrics_worker.py src/main.py tests/test_lyrics_worker.py
git commit -m "feat: use NetEase fallback when LRCLIB misses (V1.4)"
```

---

## Self-Review

**Spec coverage** (against `2026-05-26-...-v1-4-netease-fallback-design.md`):
- NetEase source, search→rank→fetch→`parse_lrc`, no cookie → Task 2.
- `netease_fallback` flag, default on → Task 1; consumed in Task 3 Step 5.
- Trigger only on LRCLIB `None`, not on exceptions → Task 3 Step 3 (the `except` returns before the fallback; the fallback is in the no-exception path).
- Fail-safe (catch all, log, return `None`, never break main flow) → Task 2 Step 3 `fetch_lyrics_from_netease` try/except + per-lookup INFO logs.
- Reuse existing `LyricsCache` (hit cached like LRCLIB, both-miss → `NO_LYRICS`) → Task 3 Step 3 (unchanged cache calls).
- Tests: ranking, parse, no-match, HTTP error, exception→None, worker on/off/lrclib-hit → Tasks 2 & 3.

**Placeholder scan:** None — every step has complete code and exact commands.

**Type/name consistency:** `fetch_lyrics_from_netease(track_name, artist_name, duration_ms)` defined in Task 2 matches the call in Task 3 Step 3 and the mocked assertion in Task 3 Step 1. `rank_netease_songs(songs, target_track, target_artist, target_duration_s)` and `search_netease(track_name, artist_name)` consistent between module and tests. `netease_fallback` flag name consistent across config (Task 1), worker constructor (Task 3), and `main.py` (Task 3 Step 5). No circular import: `netease.py` imports only `lrc_parser` + `httpx`; `lyrics_worker.py` imports `netease` — one direction.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-26-spotify-lyrics-widget-v1-4.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.

**2. Inline Execution** — execute in this session with checkpoints.

**Which approach?** (Reminder: not necessarily now — you have V1.3, V2, and V1.4 plans all ready; suggest shipping in order V1.3 → V1.4 → V2.)
