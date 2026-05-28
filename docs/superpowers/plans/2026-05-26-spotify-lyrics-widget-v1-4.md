# Spotify Lyrics Widget V1.4 — LRCLIB Contract Hardening + Gated NetEase Fallback (Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Line numbers in this plan are indicative.** master moved on after this plan was first written (`120bfd8` rounded-mask, `4589a84` removed forced repaint), so locate edit points by **string/symbol**, not by line number.

**Goal:** (1) Make LRCLIB's `None` mean only "valid response, no synced lyrics" — transient LRCLIB failures must be *unavailable*, not a confirmed miss, and must not crash the worker. (2) When LRCLIB confirms a miss, fall back to NetEase (default on) — primarily for Chinese songs.

**Architecture:** A new `src/netease.py` mirrors the LRCLIB fetcher shape but ranks **multiple** candidates (never `search[0]`), fetches each candidate's LRC and **requires parsed timed lines** (the spike found the top hit can be an untimed cover), unifies Traditional/Simplified via `zhconv`, filters NetEase production-credit lines, and Traditionalizes the accepted lyric. It takes primitive args (not `TrackInfo`) so it does not import `lyrics_worker` (no circular import). Confirmed misses → `None`; temporary failures → `NeteaseUnavailableError`. A single global cooldown is set by **any** unavailable (429 → `Retry-After`, else 60s). `lrc_parser` is extended to expand multi-timestamp lines.

**Tech Stack:** Python 3, httpx, PyQt6, pytest + pytest-qt, **`zhconv` (new dep, user-approved 2026-05-26)**.

**Spec:** `docs/superpowers/specs/2026-05-26-spotify-lyrics-widget-v1-4-netease-fallback-design.md`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `zhconv` |
| `src/lyrics_worker.py` | Modify | LRCLIB taxonomy fix (429/malformed/non-200 → unavailable); `netease_fallback` flag; call NetEase only on LRCLIB confirmed `None` |
| `src/config.py` | Modify | Add `netease_fallback: True` to persisted defaults |
| `src/lrc_parser.py` | Modify | Expand multi-timestamp `[t1][t2]text` lines |
| `src/netease.py` | Create | Search, rank ≤3 candidates, fetch+parse+credit-filter, require timed lines, `zhconv` match + Traditionalize; confirmed miss → `None`; temporary → `NeteaseUnavailableError`; unified cooldown |
| `src/main.py` | Modify | Pass `config.netease_fallback` into `LyricsWorker` |
| `tests/test_config.py` | Modify | Assert the new default |
| `tests/test_lrc_parser.py` | Modify | Multi-timestamp expansion |
| `tests/test_lyrics_worker.py` | Modify | LRCLIB taxonomy (unavailable, no cache, no NetEase); fallback wiring |
| `tests/test_netease.py` | Create | Ranking, T/S match, cover/no-timed skip, credit filter, Traditionalize, miss vs unavailable, unified cooldown |

**All commands run from the project root.** `pytest.ini` sets `pythonpath = .`, `testpaths = tests`.

---

## Task 0: NetEase endpoint spike — DONE (2026-05-26), PASSED

Real HTTP from the user's machine (Taiwan), no cookie, against the planned endpoints. Result: endpoints work; clean timed LRC for "溫柔/五月天" and "光年之外/G.E.M.邓紫棋"; and three design-changing findings now baked into this plan:
- **A:** `search[0]` can be an untimed cover ("晴天" cover, 0 timestamps) → rank multiple candidates + require timed lines (Task 4).
- **B:** Traditional vs Simplified mismatch → `zhconv` (Tasks 2 & 4).
- **C:** credit lines (`作词/作曲/编曲 …`) leak as lyrics → NetEase-only filter (Task 4).
- **D:** multi-timestamp lines known on NetEase → handle in `lrc_parser` (Task 3).

No code to write here; recorded for traceability. (If re-validation is ever needed, a few `httpx.get` calls to the two endpoints with `Referer`+UA are enough.)

---

## Task 1: Harden the LRCLIB contract (ships regardless of NetEase)

**Why:** NetEase must trigger only on a clean LRCLIB confirmed miss. Today a LRCLIB 429/403/460 falls through to `return None` (false miss), and a malformed 200 body makes `response.json()` raise `JSONDecodeError` that `run()` does not catch → silent worker-thread death.

**Files:**
- Modify: `src/lyrics_worker.py` (`fetch_lyrics_from_lrclib`)
- Test: `tests/test_lyrics_worker.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lyrics_worker.py`:

```python
def test_lrclib_429_is_unavailable_not_miss():
    from src.lyrics_worker import LrclibUnavailableError, fetch_lyrics_from_lrclib, TrackInfo

    info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    with patch("src.lyrics_worker.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=429, headers={"Retry-After": "30"}, text="rl")
        with pytest.raises(LrclibUnavailableError):
            fetch_lyrics_from_lrclib(info)


def test_lrclib_malformed_json_is_unavailable_not_crash():
    from src.lyrics_worker import LrclibUnavailableError, fetch_lyrics_from_lrclib, TrackInfo

    info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    bad = MagicMock(status_code=200, text="<html>")
    bad.json.side_effect = ValueError("no json")
    with patch("src.lyrics_worker.httpx.get", return_value=bad):
        with pytest.raises(LrclibUnavailableError):
            fetch_lyrics_from_lrclib(info)
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_lyrics_worker.py -k "lrclib_429 or malformed_json" -v`
Expected: FAIL (429 returns None; malformed raises ValueError, not LrclibUnavailableError).

- [ ] **Step 3: Implement the taxonomy fix in `src/lyrics_worker.py`**

Add a helper near `LrclibUnavailableError`:

```python
def _lrclib_json_or_unavailable(response):
    if response.status_code == 429:
        raise LrclibUnavailableError(f"lrclib rate limited: {response.status_code}")
    if response.status_code >= 500:
        raise LrclibUnavailableError(f"lrclib server error: {response.status_code}")
    if response.status_code != 200:
        return None  # e.g. /get 404 → caller falls through to /search
    try:
        return response.json()
    except ValueError as error:
        raise LrclibUnavailableError(f"lrclib malformed JSON: {error}") from error
```

In `fetch_lyrics_from_lrclib`, replace the inline `status_code` / `.json()` handling for **both** `/get` and `/search` with `_lrclib_json_or_unavailable(response)`:

```python
    data = _lrclib_json_or_unavailable(response)        # /get
    if data:
        synced_lyrics = data.get("syncedLyrics")
        if synced_lyrics:
            return parse_lrc(synced_lyrics)
    ...
    data = _lrclib_json_or_unavailable(response)        # /search
    if isinstance(data, list) and data:
        best = rank_search_results(...)
        ...
    return None
```

Keep the existing `httpx.TimeoutException → LrclibUnavailableError` wrapping. Net effect: 429/5xx/malformed → `LrclibUnavailableError`; `/get` non-200 (e.g. 404) → falls through to `/search`; only a genuine 200-with-no-synced-lyrics yields `None`.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_lyrics_worker.py -v`
Expected: all PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add src/lyrics_worker.py tests/test_lyrics_worker.py
git commit -m "fix: classify LRCLIB 429/malformed/non-200 as unavailable, not a miss (V1.4)"
```

---

## Task 2: Add `netease_fallback` config flag + `zhconv` dependency

**Files:**
- Modify: `requirements.txt`, `src/config.py:_DEFAULTS`
- Test: `tests/test_config.py`

- [ ] **Step 1: Failing test** — add to `tests/test_config.py`:

```python
def test_netease_fallback_defaults_to_true(tmp_path):
    from src.config import Config
    assert Config(config_dir=tmp_path).netease_fallback is True
```

- [ ] **Step 2: Run** `pytest tests/test_config.py -k netease -v` → FAIL (`AttributeError`).

- [ ] **Step 3: Implement** — in `src/config.py` `_DEFAULTS`, after `"window_y": 100,` add:

```python
        "netease_fallback": True,
```

Add `zhconv` to `requirements.txt`, then install it: `pip install zhconv`.

- [ ] **Step 4: Run** `pytest tests/test_config.py -v` → PASS. Also `python -c "import zhconv; print(zhconv.convert('周杰倫','zh-cn'))"` → prints `周杰伦`.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py requirements.txt
git commit -m "feat: add netease_fallback config flag + zhconv dependency (V1.4)"
```

---

## Task 3: Expand multi-timestamp LRC lines in the parser

**Why:** NetEase (and LRC generally) allows `[t1][t2]text` for repeated lines. The current `re.match` keeps only the first tag and leaks the rest into the text. Expanding is a strict superset — single-timestamp lines are unaffected.

**Files:**
- Modify: `src/lrc_parser.py`
- Test: `tests/test_lrc_parser.py`

- [ ] **Step 1: Failing tests** — add to `tests/test_lrc_parser.py`:

```python
def test_single_timestamp_unchanged():
    from src.lrc_parser import parse_lrc
    assert parse_lrc("[00:05.00]hello") == [(5000, "hello")]


def test_multi_timestamp_line_expands_and_sorts():
    from src.lrc_parser import parse_lrc
    assert parse_lrc("[00:20.00][00:05.00]chorus") == [(5000, "chorus"), (20000, "chorus")]
```

- [ ] **Step 2: Run** `pytest tests/test_lrc_parser.py -v` → multi-timestamp test FAILS.

- [ ] **Step 3: Implement** — rewrite the parse loop in `src/lrc_parser.py`:

```python
_TS_PATTERN = re.compile(r"\[(\d{2}):(\d{2})[.:](\d{2,3})\]")


def parse_lrc(lrc_text: str | None) -> list[tuple[int, str]]:
    """Parse LRC text into a sorted list of (timestamp_ms, lyric) pairs.

    Supports multiple leading timestamps on one line ([t1][t2]text)."""
    if not lrc_text:
        return []

    lines = []
    for raw_line in lrc_text.strip().split("\n"):
        raw_line = raw_line.strip()
        timestamps = list(_TS_PATTERN.finditer(raw_line))
        if not timestamps:
            continue
        text = raw_line[timestamps[-1].end():].strip()
        if not text:
            continue
        for match in timestamps:
            minutes, seconds, frac = match.groups()
            ms = int(minutes) * 60000 + int(seconds) * 1000
            ms += int(frac) * 10 if len(frac) == 2 else int(frac)
            lines.append((ms, text))

    lines.sort(key=lambda line: line[0])
    return lines
```

(Leading metadata tags like `[ti:..]` still produce no `_TS_PATTERN` match and are skipped. The `[.:]` allows the `[mm:ss:xx]` variant too.)

- [ ] **Step 4: Run** `pytest tests/test_lrc_parser.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lrc_parser.py tests/test_lrc_parser.py
git commit -m "feat: expand multi-timestamp LRC lines in parser (V1.4)"
```

---

## Task 4: NetEase fetcher module

**Why:** Isolates the unofficial NetEase calls + matching. The spike proved single-candidate fetch is brittle (cover with no timestamps), so we rank ≤3 candidates and require timed lines. `zhconv` bridges Traditional/Simplified. Credit lines are filtered. Any temporary failure raises `NeteaseUnavailableError` and arms a single global cooldown.

**Files:**
- Create: `src/netease.py`
- Test: `tests/test_netease.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_netease.py`:

```python
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.netease import (
    NeteaseUnavailableError,
    fetch_lyrics_from_netease,
    rank_netease_songs,
    search_netease,
)


@pytest.fixture(autouse=True)
def reset_cooldown(monkeypatch):
    monkeypatch.setattr("src.netease._cooldown_until", 0.0, raising=False)


def _song(song_id, name, artist, duration_ms):
    return {"id": song_id, "name": name, "artists": [{"name": artist}],
            "duration": duration_ms, "album": {"name": "Album"}}


class TestRanking:
    def test_traditional_query_matches_simplified_result(self):
        songs = [_song(1, "晴天", "周杰伦", 269000)]
        ranked = rank_netease_songs(songs, "晴天", "周杰倫", target_duration_s=269)
        assert ranked and ranked[0]["id"] == 1

    def test_prefers_closest_duration_as_tiebreaker(self):
        songs = [_song(1, "Song", "Artist", 300000), _song(2, "Song", "Artist", 181000)]
        ranked = rank_netease_songs(songs, "Song", "Artist", target_duration_s=180)
        assert ranked[0]["id"] == 2

    def test_rejects_weak_text_match_even_if_duration_close(self):
        songs = [_song(1, "Totally Different", "Nobody", 180000)]
        assert rank_netease_songs(songs, "Song", "Artist", target_duration_s=180) == []

    def test_returns_at_most_three(self):
        songs = [_song(i, "Song", "Artist", 180000) for i in range(6)]
        assert len(rank_netease_songs(songs, "Song", "Artist", 180)) <= 3


class TestSearch:
    @patch("src.netease.httpx.get")
    def test_returns_song_list(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200,
            json=lambda: {"result": {"songs": [_song(1, "Song", "Artist", 180000)]}})
        assert search_netease("Song", "Artist")[0]["id"] == 1

    @patch("src.netease.httpx.get")
    def test_non_200_raises_unavailable(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403, text="blocked", json=lambda: {})
        with pytest.raises(NeteaseUnavailableError):
            search_netease("Song", "Artist")


class TestFetch:
    @patch("src.netease.httpx.get")
    def test_skips_untimed_cover_uses_next_candidate(self, mock_get):
        # search → 2 candidates; first lyric untimed (cover), second timed
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": {"songs": [
                _song(11, "Song", "Artist", 180000), _song(12, "Song", "Artist", 180500)]}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": "plain no timestamps"}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": "[00:05.00] 你好"}}),
        ]
        result = fetch_lyrics_from_netease("Song", "Artist", 180000)
        assert result == [(5000, "你好")]

    @patch("src.netease.httpx.get")
    def test_filters_credit_lines_and_traditionalizes(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": {"songs": [_song(11, "光年之外", "邓紫棋", 235000)]}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric":
                "[00:00.00] 作词 : 邓紫棋\n[00:05.00] 梦想"}}),
        ]
        result = fetch_lyrics_from_netease("光年之外", "鄧紫棋", 235000)
        assert result == [(5000, "夢想")]  # credit dropped, 梦→夢 Traditionalized

    @patch("src.netease.httpx.get")
    def test_no_candidate_returns_none(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"result": {"songs": []}})
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None

    @patch("src.netease.httpx.get")
    def test_all_candidates_untimed_returns_none(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": {"songs": [_song(11, "Song", "Artist", 180000)]}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": "plain"}}),
        ]
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None

    @patch("src.netease.httpx.get")
    def test_network_error_raises_unavailable(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no internet")
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)

    @patch("src.netease.httpx.get")
    def test_429_sets_cooldown_then_skips_http(self, mock_get):
        mock_get.return_value = MagicMock(status_code=429, headers={"Retry-After": "30"}, text="rl", json=lambda: {})
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.reset_mock()
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.assert_not_called()

    @patch("src.netease.httpx.get")
    def test_non_429_unavailable_also_sets_cooldown(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403, text="blocked", json=lambda: {})
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.reset_mock()
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.assert_not_called()
```

- [ ] **Step 2: Run** `pytest tests/test_netease.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `src/netease.py`**

```python
import logging
import re
import time

import httpx
import zhconv

from src.lrc_parser import parse_lrc

NETEASE_SEARCH_URL = "https://music.163.com/api/search/get/web"
NETEASE_LYRIC_URL = "https://music.163.com/api/song/lyric"
MAX_CANDIDATES = 3
DURATION_TOLERANCE_S = 5
DEFAULT_RETRY_AFTER_S = 30
DEFAULT_UNAVAILABLE_BACKOFF_S = 60
_HEADERS = {
    "Referer": "https://music.163.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}
_CREDIT_PREFIXES = {
    "作词", "作曲", "编曲", "制作人", "出品", "监制", "演唱", "演奏", "和声",
    "混音", "录音", "母带", "producer", "composer", "lyricist", "arranger", "mixing",
}
_cooldown_until = 0.0


class NeteaseUnavailableError(RuntimeError):
    """NetEase temporarily unavailable; caller must not cache this as a miss."""


def _to_simplified(text: str) -> str:
    return zhconv.convert(text or "", "zh-cn")


def _to_traditional(text: str) -> str:
    return zhconv.convert(text or "", "zh-tw")


def _normalize(text: str) -> str:
    text = _to_simplified(text).lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(remaster(ed)?|deluxe|live|remix|version|edit|original)\b", "", text)
    return text.strip()


def _cooldown_remaining() -> float:
    return max(0.0, _cooldown_until - time.monotonic())


def _set_cooldown(seconds: int) -> None:
    global _cooldown_until
    _cooldown_until = time.monotonic() + max(1, seconds)


def _retry_after_seconds(response) -> int:
    value = response.headers.get("Retry-After")
    if not value:
        return DEFAULT_RETRY_AFTER_S
    try:
        return max(1, int(value))
    except ValueError:
        return DEFAULT_RETRY_AFTER_S


def _request_json(url: str, params: dict) -> dict:
    remaining = _cooldown_remaining()
    if remaining > 0:
        logging.warning("NetEase fallback unavailable: cooldown active for %.0fs", remaining)
        raise NeteaseUnavailableError("NetEase cooldown active")
    try:
        response = httpx.get(url, params=params, headers=_HEADERS, timeout=5.0)
    except httpx.RequestError as exc:
        _set_cooldown(DEFAULT_UNAVAILABLE_BACKOFF_S)
        logging.warning("NetEase fallback unavailable: request error: %s", exc)
        raise NeteaseUnavailableError("NetEase request failed") from exc

    if response.status_code == 429:
        retry_after = _retry_after_seconds(response)
        _set_cooldown(retry_after)
        logging.warning("NetEase fallback unavailable: 429, retry after %ss", retry_after)
        raise NeteaseUnavailableError("NetEase rate limited")
    if response.status_code != 200:
        _set_cooldown(DEFAULT_UNAVAILABLE_BACKOFF_S)
        logging.warning("NetEase fallback unavailable: HTTP %s: %.120s",
                        response.status_code, response.text)
        raise NeteaseUnavailableError(f"NetEase HTTP {response.status_code}")
    try:
        return response.json() or {}
    except ValueError as exc:
        _set_cooldown(DEFAULT_UNAVAILABLE_BACKOFF_S)
        logging.warning("NetEase fallback unavailable: malformed JSON: %.120s", response.text)
        raise NeteaseUnavailableError("NetEase malformed JSON") from exc


def search_netease(track_name: str, artist_name: str) -> list[dict]:
    data = _request_json(NETEASE_SEARCH_URL,
                         params={"s": f"{track_name} {artist_name}", "type": 1, "limit": 10})
    return (data.get("result") or {}).get("songs") or []


def rank_netease_songs(songs, target_track, target_artist, target_duration_s) -> list[dict]:
    """Return up to MAX_CANDIDATES ranked songs; reject weak textual matches outright."""
    nt, na = _normalize(target_track), _normalize(target_artist)
    scored = []
    for song in songs:
        st = _normalize(song.get("name", ""))
        artists = song.get("artists") or []
        sa = _normalize(", ".join(a.get("name", "") for a in artists))
        name_match = 0 if st == nt else (5 if nt and (nt in st or st in nt) else 10)
        artist_match = 0 if sa == na else (5 if na and (na in sa or sa in na) else 10)
        text_score = name_match + artist_match
        if text_score >= 20:  # both unmatched → wrong song; wrong lyrics worse than none
            continue
        dur_diff = abs(song.get("duration", 0) // 1000 - target_duration_s)
        if dur_diff <= DURATION_TOLERANCE_S:
            dur_penalty = 0.0
        elif text_score == 0:           # exact title+artist → tolerate drift cheaply
            dur_penalty = (dur_diff - DURATION_TOLERANCE_S) * 0.2
        else:                            # weaker text → drift counts more
            dur_penalty = float(dur_diff)
        scored.append((text_score + dur_penalty, song))
    scored.sort(key=lambda item: item[0])
    return [song for _, song in scored[:MAX_CANDIDATES]]


def fetch_netease_lyric(song_id) -> str | None:
    data = _request_json(NETEASE_LYRIC_URL,
                         params={"id": song_id, "lv": -1, "kv": -1, "tv": -1})
    return (data.get("lrc") or {}).get("lyric")


def _is_credit_line(text: str) -> bool:
    match = re.match(r"\s*([^\s:：]+)\s*[:：]", text)
    return bool(match) and match.group(1).lower() in _CREDIT_PREFIXES


def _clean_lyric(parsed: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(ts, _to_traditional(text)) for ts, text in parsed if not _is_credit_line(text)]


def fetch_lyrics_from_netease(track_name, artist_name, duration_ms) -> list[tuple[int, str]] | None:
    """Best-effort NetEase synced lyrics, Traditionalized.

    None only for confirmed no-match / no-usable-lyric. Temporary failures raise
    NeteaseUnavailableError. Tries up to MAX_CANDIDATES ranked candidates and requires
    parsed timed lines (the top search hit can be an untimed cover)."""
    songs = search_netease(track_name, artist_name)
    candidates = rank_netease_songs(songs, track_name, artist_name, duration_ms // 1000)
    if not candidates:
        logging.info("NetEase fallback miss: no candidate for %s - %s", track_name, artist_name)
        return None
    for candidate in candidates:
        lyric_text = fetch_netease_lyric(candidate["id"])
        if not lyric_text:
            continue
        cleaned = _clean_lyric(parse_lrc(lyric_text))
        if cleaned:
            logging.info("NetEase fallback hit: %s (for %s)", candidate.get("name"), track_name)
            return cleaned
    logging.info("NetEase fallback miss: no timed lyric among candidates for %s", track_name)
    return None
```

The cooldown is global to the NetEase fallback (search and lyric endpoints both skip) and armed by **any** unavailable, not just 429.

- [ ] **Step 4: Run** `pytest tests/test_netease.py -v` → all PASS. (If `_to_traditional` turns 梦→夢 etc., the Traditionalize assertions pass; if a test fails on conversion, confirm `zhconv.convert(text, "zh-tw")`.)

- [ ] **Step 5: Commit**

```bash
git add src/netease.py tests/test_netease.py
git commit -m "feat: NetEase fetcher with candidate ranking, zhconv match, credit filter, cooldown (V1.4)"
```

---

## Task 5: Wire the fallback into the lyrics worker

**Why:** Try LRCLIB; if it returns a confirmed `None` and the flag is on, try NetEase; LRCLIB-unavailable still goes straight to `lyrics_unavailable` with NO fallback.

**Files:**
- Modify: `src/lyrics_worker.py` (import, constructor, `run`), `src/main.py`
- Test: `tests/test_lyrics_worker.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/test_lyrics_worker.py`:

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
    worker.lyrics_ready.connect(lambda tid, lyr: ready.append((tid, lyr)))
    worker.run()
    mock_netease.assert_called_once_with("Song", "Artist", 180000)
    assert ready == [("t1", [(1000, "ne")])]


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_netease_not_called_when_disabled(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=False)
    misses = []
    worker.no_lyrics.connect(lambda tid: misses.append(tid))
    worker.run()
    mock_netease.assert_not_called()
    assert misses == ["t1"]


# `LrclibUnavailableError` is already imported at the top of this test module (Task 1 tests).
@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", side_effect=LrclibUnavailableError("rl"))
def test_lrclib_unavailable_does_not_call_netease(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    unavailable = []
    worker.lyrics_unavailable.connect(lambda tid: unavailable.append(tid))
    worker.run()
    mock_netease.assert_not_called()
    assert unavailable == ["t1"]
    assert worker._cache.get("t1") is worker._cache.MISS


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_netease_unavailable_emits_unavailable_without_caching(mock_lrclib, mock_netease, qtbot):
    from src.netease import NeteaseUnavailableError
    mock_netease.side_effect = NeteaseUnavailableError("rl")
    worker = _pending_worker(netease_fallback=True)
    unavailable, misses = [], []
    worker.lyrics_unavailable.connect(lambda tid: unavailable.append(tid))
    worker.no_lyrics.connect(lambda tid: misses.append(tid))
    worker.run()
    assert unavailable == ["t1"] and misses == []
    assert worker._cache.get("t1") is worker._cache.MISS


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=None)
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_both_miss_caches_no_lyrics(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    worker.run()
    assert worker._cache.get("t1") is worker._cache.NO_LYRICS
```

- [ ] **Step 2: Run** `pytest tests/test_lyrics_worker.py -k "netease or falls_back or lrclib_unavailable or both_miss" -v` → FAIL (constructor takes no `netease_fallback`; import missing).

- [ ] **Step 3: Wire it in `src/lyrics_worker.py`**

After `from src.lrc_parser import parse_lrc` add:

```python
from src.netease import NeteaseUnavailableError, fetch_lyrics_from_netease
```

Constructor:

```python
    def __init__(self, netease_fallback: bool = True):
        super().__init__()
        self._cache = LyricsCache()
        self._pending_track: TrackInfo | None = None
        self._has_work = False
        self._netease_fallback = netease_fallback
```

Replace the fetch/emit block in `run` with:

```python
            try:
                result = fetch_lyrics_from_lrclib(info)
            except (httpx.ConnectError, LrclibUnavailableError):
                self.lyrics_unavailable.emit(info.track_id)
                return

            if not result and self._netease_fallback:
                try:
                    result = fetch_lyrics_from_netease(
                        info.track_name, info.artist_name, info.duration_ms
                    )
                except NeteaseUnavailableError:
                    self.lyrics_unavailable.emit(info.track_id)
                    return

            if result:
                self._cache.set(info.track_id, result)
                self.lyrics_ready.emit(info.track_id, result)
            else:
                self._cache.set_no_lyrics(info.track_id)
                self.no_lyrics.emit(info.track_id)
```

- [ ] **Step 4: Run** `pytest tests/test_lyrics_worker.py -v` → all PASS.

- [ ] **Step 5: Pass the flag from `main.py`** — change `self._lyrics_worker = LyricsWorker()` to:

```python
        self._lyrics_worker = LyricsWorker(netease_fallback=self._config.netease_fallback)
```

- [ ] **Step 6: Full suite** — `pytest -v` → all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/lyrics_worker.py src/main.py tests/test_lyrics_worker.py
git commit -m "feat: use NetEase fallback only on LRCLIB confirmed miss (V1.4)"
```

---

## Task 6: Manual verification + docs

- [ ] **Step 1:** Run `pythonw run.pyw`. Play a Chinese song LRCLIB misses (previously "no synced lyrics"), ideally a **Traditional-titled Taiwanese** track. Verify:
  1. Synced lyrics appear, scroll in time, and are shown in **Traditional**.
  2. No `作词/作曲 …` credit line shows at the start.
  3. `widget.log` shows `NetEase fallback hit: <song> (for <track>)`.
  4. A song with lyrics on LRCLIB is still instant (no NetEase log line).
  5. Set `"netease_fallback": false` in `%APPDATA%/spotify-lyrics-widget/config.json`, restart, replay → "no synced lyrics" again.
  6. If a NetEase 429/non-200 occurs, the log records it and later lookups skip NetEase until cooldown expires.
- [ ] **Step 2:** Confirm specs/roadmap already reflect this plan (they do as of 2026-05-26). No further doc edits unless behaviour changed during implementation.
- [ ] **Step 3: Commit** any doc touch-ups.

---

## Self-Review

**Spec coverage** (against `2026-05-26-…-v1-4-netease-fallback-design.md`):
- LRCLIB taxonomy (429/malformed/non-200 → unavailable; `/get` 404 → search; no silent crash) → Task 1.
- `netease_fallback` flag default on + `zhconv` dep → Task 2; consumed in Task 5 Step 5.
- Multi-timestamp parser (strict superset) → Task 3.
- NetEase: ≤3 candidate ranking (never `search[0]`), require timed lines, T/S via `zhconv`, credit filter, Traditionalize, miss vs `NeteaseUnavailableError`, unified cooldown on any unavailable → Task 4.
- Trigger only on LRCLIB confirmed `None`, never on unavailable; both-miss → `NO_LYRICS`; NetEase-unavailable not cached → Task 5.

**Placeholder scan:** None — every step has complete code and exact commands.

**Type/name consistency:** `fetch_lyrics_from_netease(track_name, artist_name, duration_ms)` matches the worker call and test mocks. `rank_netease_songs(...) -> list[dict]` (≤3) consumed by the candidate loop. `_to_simplified/_to_traditional` wrap `zhconv.convert(..., "zh-cn"/"zh-tw")`. No circular import: `netease` imports `lrc_parser` + `zhconv` + `httpx`; `lyrics_worker` imports `netease` (one direction).

---

---

## Verification recorded (2026-05-28)

**Live widget run on `feature/v1-4-netease-fallback` (HEAD `2b26a26`).** Three confirmed NetEase fallback hits in `%APPDATA%/spotify-lyrics-widget/widget.log.1`:

```
2026-05-28 20:30:10  INFO  NetEase fallback hit: 等待你那天 (for 等待你那天)
2026-05-28 20:32:00  INFO  NetEase fallback hit: 記得呼吸 (for 記得呼吸)
2026-05-28 20:35:19  INFO  NetEase fallback hit: 空拍   (for 空拍)
```

The remaining session also recorded an LRCLIB hit on a separate track (`你到底在選擇什麼`), confirming both branches of the fallback gate behave correctly. NetEase lyrics arrive in Traditional Chinese with credit lines filtered (matches `_clean_lyric` in `src/netease.py`); on-screen rendering matches log-emitted line counts.

**Symptom discovered + root cause:** an earlier attempt at `等待你那天` (00:15:25) displayed "歌詞沒辦法取得" because LRCLIB `/search` `ReadTimeout`'d under transient throttling (induced by the verification queries themselves) — the worker correctly took the unavailable branch and skipped NetEase per spec, but `lyrics_worker.run()` logs **nothing** at that branch, so the root cause was only recoverable by re-running `httpx.get` outside the widget. This visibility gap is the V1.5 trigger:

- Plan: `docs/superpowers/plans/2026-05-28-spotify-lyrics-widget-v1-5-logging-hygiene.md`

Whether the spec gate itself should change (LRCLIB-unavailable also routes to NetEase) is a **design question**, deliberately deferred from V1.5 and routed to Codex consensus per `memory/codex-consensus-and-validate-before-adopting.md`.

---

## Execution Handoff

**Plan saved. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
**2. Inline Execution** — execute in this session with checkpoints.

Task order is the execution order: Task 1 (LRCLIB fix, ships regardless) → 2 → 3 → 4 → 5 → 6. Suggested overall ship order remains V1.4 → V2.
