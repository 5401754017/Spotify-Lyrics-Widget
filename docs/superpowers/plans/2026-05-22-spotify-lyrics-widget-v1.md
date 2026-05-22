# Spotify Lyrics Widget V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Windows desktop widget that displays synced lyrics for the currently playing Spotify track in real-time, one line at a time.

**Architecture:** PyQt6 frameless always-on-top window driven by two timers: a 1-second Spotify API poller (worker thread) for authoritative state, and a 150ms local UI timer (main thread) for smooth lyric interpolation. Lyrics fetched from lrclib.net in an independent worker thread. All config persisted in `%APPDATA%`.

**Tech Stack:** Python 3.11+, PyQt6, httpx (async-friendly HTTP), pytest, pytest-qt

---

## File Structure

```
spotify_widget/
├── src/
│   ├── __init__.py
│   ├── main.py                # Entry point: app bootstrap, signal wiring
│   ├── config.py              # Config read/write in %APPDATA%
│   ├── auth.py                # PKCE OAuth flow + token refresh
│   ├── spotify_worker.py      # QThread: poll Spotify every 1s
│   ├── lyrics_worker.py       # QThread: lrclib lookup + LRC parsing
│   ├── lrc_parser.py          # Pure function: parse LRC string → [(ms, text)]
│   └── widget.py              # PyQt6 UI: window, labels, progress bar, timers
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_lrc_parser.py
│   ├── test_spotify_worker.py
│   ├── test_lyrics_worker.py
│   └── test_widget.py
├── requirements.txt
├── pytest.ini
└── .gitignore
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `src/__init__.py`, `tests/__init__.py`, `requirements.txt`, `pytest.ini`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src tests
```

- [ ] **Step 2: Create requirements.txt**

```text
PyQt6>=6.6.0
httpx>=0.27.0
pytest>=8.0.0
pytest-qt>=4.4.0
```

- [ ] **Step 3: Create pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: Create __init__.py files**

`src/__init__.py` — empty file
`tests/__init__.py` — empty file

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 6: Verify pytest runs**

```bash
pytest --co
```

Expected: "no tests ran" (no collection errors)

- [ ] **Step 7: Commit**

```bash
git add src/ tests/ requirements.txt pytest.ini
git commit -m "chore: scaffold project structure with dependencies"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import json
from pathlib import Path
from src.config import Config


def test_default_config_created_when_missing(tmp_path):
    config = Config(config_dir=tmp_path)
    assert config.client_id is None
    assert config.access_token is None
    assert config.refresh_token is None
    assert config.token_expires_at == 0
    assert config.window_x == 100
    assert config.window_y == 100


def test_save_and_load_config(tmp_path):
    config = Config(config_dir=tmp_path)
    config.client_id = "test_client_id"
    config.access_token = "test_access_token"
    config.refresh_token = "test_refresh_token"
    config.token_expires_at = 1716400000
    config.window_x = 200
    config.window_y = 300
    config.save()

    config2 = Config(config_dir=tmp_path)
    assert config2.client_id == "test_client_id"
    assert config2.access_token == "test_access_token"
    assert config2.refresh_token == "test_refresh_token"
    assert config2.token_expires_at == 1716400000
    assert config2.window_x == 200
    assert config2.window_y == 300


def test_save_creates_directory(tmp_path):
    nested = tmp_path / "sub" / "dir"
    config = Config(config_dir=nested)
    config.client_id = "abc"
    config.save()
    assert (nested / "config.json").exists()


def test_partial_config_preserves_defaults(tmp_path):
    # Write a config with only client_id
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"client_id": "partial"}))

    config = Config(config_dir=tmp_path)
    assert config.client_id == "partial"
    assert config.window_x == 100  # default preserved


def test_default_appdata_path():
    config = Config()
    assert "spotify-lyrics-widget" in str(config._config_dir)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: ModuleNotFoundError (src.config does not exist)

- [ ] **Step 3: Implement config module**

```python
# src/config.py
import json
import os
from pathlib import Path


class Config:
    """Manages persistent config in %APPDATA%/spotify-lyrics-widget/config.json"""

    _DEFAULTS = {
        "client_id": None,
        "access_token": None,
        "refresh_token": None,
        "token_expires_at": 0,
        "window_x": 100,
        "window_y": 100,
    }

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            appdata = os.environ.get("APPDATA", str(Path.home()))
            config_dir = Path(appdata) / "spotify-lyrics-widget"
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._load()

    def _load(self):
        data = {}
        if self._config_file.exists():
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

        for key, default in self._DEFAULTS.items():
            setattr(self, key, data.get(key, default))

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        data = {key: getattr(self, key) for key in self._DEFAULTS}
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config module with AppData persistence"
```

---

## Task 3: LRC Parser (Pure Logic)

**Files:**
- Create: `src/lrc_parser.py`
- Test: `tests/test_lrc_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_lrc_parser.py
from src.lrc_parser import parse_lrc, find_current_line


class TestParseLrc:
    def test_basic_parsing(self):
        lrc = "[00:12.34] Hello world\n[00:15.00] Second line\n[01:00.50] Third line"
        result = parse_lrc(lrc)
        assert result == [
            (12340, "Hello world"),
            (15000, "Second line"),
            (60500, "Third line"),
        ]

    def test_strips_whitespace(self):
        lrc = "[00:05.00]  Leading spaces  \n[00:10.00]Trailing  "
        result = parse_lrc(lrc)
        assert result == [
            (5000, "Leading spaces"),
            (10000, "Trailing"),
        ]

    def test_empty_string(self):
        assert parse_lrc("") == []

    def test_none_input(self):
        assert parse_lrc(None) == []

    def test_skips_invalid_lines(self):
        lrc = "[00:05.00] Valid\nno timestamp here\n[bad] Also bad\n[00:10.00] Also valid"
        result = parse_lrc(lrc)
        assert result == [
            (5000, "Valid"),
            (10000, "Also valid"),
        ]

    def test_skips_empty_lyric_lines(self):
        lrc = "[00:05.00] Valid\n[00:10.00] \n[00:15.00] Also valid"
        result = parse_lrc(lrc)
        assert result == [
            (5000, "Valid"),
            (15000, "Also valid"),
        ]

    def test_sorted_output(self):
        lrc = "[00:20.00] Second\n[00:05.00] First"
        result = parse_lrc(lrc)
        assert result == [
            (5000, "First"),
            (20000, "Second"),
        ]

    def test_two_digit_minutes(self):
        lrc = "[12:34.56] Late in song"
        result = parse_lrc(lrc)
        assert result == [(754560, "Late in song")]


class TestFindCurrentLine:
    def test_before_first_line(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 3000) == -1

    def test_exact_match_first(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 5000) == 0

    def test_between_lines(self):
        lines = [(5000, "First"), (10000, "Second"), (15000, "Third")]
        assert find_current_line(lines, 12000) == 1

    def test_after_last_line(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 99000) == 1

    def test_empty_list(self):
        assert find_current_line([], 5000) == -1

    def test_exact_match_last(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 10000) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_lrc_parser.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Implement LRC parser**

```python
# src/lrc_parser.py
import re
from bisect import bisect_right

_LRC_PATTERN = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)")


def parse_lrc(lrc_text: str | None) -> list[tuple[int, str]]:
    """Parse LRC format string into sorted list of (timestamp_ms, lyric_text).

    Skips lines without valid timestamps or with empty text.
    """
    if not lrc_text:
        return []

    lines = []
    for raw_line in lrc_text.strip().split("\n"):
        match = _LRC_PATTERN.match(raw_line.strip())
        if not match:
            continue
        minutes, seconds, centis, text = match.groups()
        text = text.strip()
        if not text:
            continue
        # Handle both 2-digit (centiseconds) and 3-digit (milliseconds) fractional part
        if len(centis) == 2:
            ms = int(minutes) * 60000 + int(seconds) * 1000 + int(centis) * 10
        else:
            ms = int(minutes) * 60000 + int(seconds) * 1000 + int(centis)
        lines.append((ms, text))

    lines.sort(key=lambda x: x[0])
    return lines


def find_current_line(lines: list[tuple[int, str]], progress_ms: int) -> int:
    """Binary search for the current lyric line index.

    Returns the index of the last line where timestamp_ms <= progress_ms.
    Returns -1 if progress_ms is before the first line or list is empty.
    """
    if not lines:
        return -1

    # bisect_right finds insertion point; subtract 1 to get the last line <= progress_ms
    timestamps = [line[0] for line in lines]
    idx = bisect_right(timestamps, progress_ms) - 1
    return idx
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_lrc_parser.py -v
```

Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/lrc_parser.py tests/test_lrc_parser.py
git commit -m "feat: add LRC parser with timestamp parsing and binary search"
```

---

## Task 4: Auth Module

**Files:**
- Create: `src/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_auth.py
import hashlib
import base64
import time
from unittest.mock import patch, MagicMock
from src.auth import (
    generate_code_verifier,
    generate_code_challenge,
    build_auth_url,
    exchange_code_for_token,
    refresh_access_token,
    is_token_expired,
)


class TestPKCECrypto:
    def test_code_verifier_length(self):
        verifier = generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_code_verifier_charset(self):
        verifier = generate_code_verifier()
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        assert all(c in allowed for c in verifier)

    def test_code_challenge_is_s256(self):
        verifier = "test_verifier_string_that_is_long_enough_43chars"
        challenge = generate_code_challenge(verifier)
        # Manually compute expected
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected


class TestBuildAuthUrl:
    def test_contains_required_params(self):
        url = build_auth_url("test_client_id", "test_challenge", "test_state")
        assert "client_id=test_client_id" in url
        assert "code_challenge=test_challenge" in url
        assert "code_challenge_method=S256" in url
        assert "response_type=code" in url
        assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback" in url
        assert "scope=user-read-currently-playing" in url
        assert "state=test_state" in url


class TestTokenExpiry:
    def test_expired_token(self):
        expires_at = int(time.time()) - 60  # expired 60s ago
        assert is_token_expired(expires_at) is True

    def test_valid_token(self):
        expires_at = int(time.time()) + 3600  # expires in 1 hour
        assert is_token_expired(expires_at) is False

    def test_expires_within_buffer(self):
        # Token expires in 30 seconds — treat as expired (60s buffer)
        expires_at = int(time.time()) + 30
        assert is_token_expired(expires_at) is True


class TestExchangeCode:
    @patch("src.auth.httpx.post")
    def test_successful_exchange(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            },
        )
        result = exchange_code_for_token("auth_code", "verifier", "client_id")
        assert result["access_token"] == "new_access"
        assert result["refresh_token"] == "new_refresh"
        assert result["expires_in"] == 3600

    @patch("src.auth.httpx.post")
    def test_failed_exchange_raises(self, mock_post):
        mock_post.return_value = MagicMock(status_code=400, text="Bad Request")
        import pytest
        with pytest.raises(Exception, match="Token exchange failed"):
            exchange_code_for_token("bad_code", "verifier", "client_id")


class TestRefreshToken:
    @patch("src.auth.httpx.post")
    def test_refresh_returns_new_refresh_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed_access",
                "refresh_token": "new_refresh_token",
                "expires_in": 3600,
            },
        )
        result = refresh_access_token("old_refresh", "client_id")
        assert result["access_token"] == "refreshed_access"
        assert result["refresh_token"] == "new_refresh_token"

    @patch("src.auth.httpx.post")
    def test_refresh_without_new_refresh_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed_access",
                "expires_in": 3600,
            },
        )
        result = refresh_access_token("old_refresh", "client_id")
        assert result["access_token"] == "refreshed_access"
        assert "refresh_token" not in result

    @patch("src.auth.httpx.post")
    def test_refresh_failure_raises(self, mock_post):
        mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
        import pytest
        with pytest.raises(Exception, match="Token refresh failed"):
            refresh_access_token("bad_refresh", "client_id")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Implement auth module**

```python
# src/auth.py
import hashlib
import base64
import secrets
import time
from urllib.parse import urlencode

import httpx

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-read-currently-playing"

# Treat token as expired if it expires within this many seconds
_EXPIRY_BUFFER_SECONDS = 60


def generate_code_verifier() -> str:
    """Generate a random PKCE code verifier (43-128 chars, URL-safe)."""
    return secrets.token_urlsafe(64)[:128]


def generate_code_challenge(verifier: str) -> str:
    """Generate S256 code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_auth_url(client_id: str, code_challenge: str, state: str) -> str:
    """Build the Spotify authorization URL with PKCE parameters."""
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
        "scope": SCOPES,
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def is_token_expired(expires_at: int) -> bool:
    """Check if token is expired or will expire within the buffer period."""
    return time.time() >= (expires_at - _EXPIRY_BUFFER_SECONDS)


def exchange_code_for_token(code: str, code_verifier: str, client_id: str) -> dict:
    """Exchange authorization code for access token."""
    response = httpx.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.status_code} {response.text}")
    return response.json()


def refresh_access_token(refresh_token: str, client_id: str) -> dict:
    """Refresh the access token. May or may not return a new refresh_token."""
    response = httpx.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )
    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.status_code} {response.text}")
    return response.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
```

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/auth.py tests/test_auth.py
git commit -m "feat: add PKCE auth module with token management"
```

---

## Task 5: Spotify Worker

**Files:**
- Create: `src/spotify_worker.py`
- Test: `tests/test_spotify_worker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_spotify_worker.py
from unittest.mock import patch, MagicMock
from src.spotify_worker import parse_player_state, detect_changes, PlayerState


class TestParsePlayerState:
    def test_parse_track(self):
        response_data = {
            "is_playing": True,
            "progress_ms": 45000,
            "currently_playing_type": "track",
            "item": {
                "id": "track_123",
                "name": "Test Song",
                "uri": "spotify:track:track_123",
                "duration_ms": 240000,
                "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
                "album": {"name": "Test Album"},
            },
        }
        state = parse_player_state(response_data)
        assert state.track_id == "track_123"
        assert state.track_name == "Test Song"
        assert state.track_uri == "spotify:track:track_123"
        assert state.artist_name == "Artist A, Artist B"
        assert state.album_name == "Test Album"
        assert state.duration_ms == 240000
        assert state.progress_ms == 45000
        assert state.is_playing is True
        assert state.is_track is True

    def test_parse_episode(self):
        response_data = {
            "is_playing": True,
            "progress_ms": 10000,
            "currently_playing_type": "episode",
            "item": {
                "id": "ep_456",
                "name": "Podcast Episode",
                "uri": "spotify:episode:ep_456",
                "duration_ms": 3600000,
                "artists": [],
                "album": {"name": ""},
            },
        }
        state = parse_player_state(response_data)
        assert state.is_track is False

    def test_parse_no_item(self):
        response_data = {
            "is_playing": False,
            "progress_ms": None,
            "currently_playing_type": "unknown",
            "item": None,
        }
        state = parse_player_state(response_data)
        assert state.track_id is None
        assert state.is_track is False
        assert state.is_playing is False

    def test_parse_empty_response(self):
        state = parse_player_state(None)
        assert state.track_id is None
        assert state.is_playing is False
        assert state.is_track is False


class TestDetectChanges:
    def _make_state(self, track_id="t1", progress_ms=5000, is_playing=True, is_track=True):
        return PlayerState(
            track_id=track_id,
            track_name="Song",
            track_uri=f"spotify:track:{track_id}",
            artist_name="Artist",
            album_name="Album",
            duration_ms=240000,
            progress_ms=progress_ms,
            is_playing=is_playing,
            is_track=is_track,
        )

    def test_track_changed(self):
        old = self._make_state(track_id="t1")
        new = self._make_state(track_id="t2")
        changes = detect_changes(old, new)
        assert changes["track_changed"] is True

    def test_no_track_change(self):
        old = self._make_state(track_id="t1", progress_ms=5000)
        new = self._make_state(track_id="t1", progress_ms=6000)
        changes = detect_changes(old, new)
        assert changes["track_changed"] is False

    def test_playback_toggled(self):
        old = self._make_state(is_playing=True)
        new = self._make_state(is_playing=False)
        changes = detect_changes(old, new)
        assert changes["playback_toggled"] is True

    def test_seek_detected(self):
        old = self._make_state(progress_ms=10000)
        # Expected ~11000 after 1s, but jumped to 50000
        new = self._make_state(progress_ms=50000)
        changes = detect_changes(old, new)
        assert changes["seek_detected"] is True

    def test_normal_progress_no_seek(self):
        old = self._make_state(progress_ms=10000)
        new = self._make_state(progress_ms=11050)  # ~1s forward, normal
        changes = detect_changes(old, new)
        assert changes["seek_detected"] is False

    def test_first_state_no_previous(self):
        new = self._make_state()
        changes = detect_changes(None, new)
        assert changes["track_changed"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_spotify_worker.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Implement spotify_worker module**

```python
# src/spotify_worker.py
import time
from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

import httpx

from src.auth import is_token_expired, refresh_access_token

CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
SEEK_THRESHOLD_MS = 3000  # jumps larger than 3s are treated as seeks


@dataclass
class PlayerState:
    track_id: str | None
    track_name: str
    track_uri: str
    artist_name: str
    album_name: str
    duration_ms: int
    progress_ms: int
    is_playing: bool
    is_track: bool


def parse_player_state(data: dict | None) -> PlayerState:
    """Parse Spotify currently-playing response into PlayerState."""
    if data is None or data.get("item") is None:
        return PlayerState(
            track_id=None,
            track_name="",
            track_uri="",
            artist_name="",
            album_name="",
            duration_ms=0,
            progress_ms=0,
            is_playing=False,
            is_track=False,
        )

    item = data["item"]
    playing_type = data.get("currently_playing_type", "unknown")
    is_track = playing_type == "track"

    artists = item.get("artists", [])
    artist_name = ", ".join(a["name"] for a in artists) if artists else ""
    album_name = item.get("album", {}).get("name", "")

    return PlayerState(
        track_id=item.get("id"),
        track_name=item.get("name", ""),
        track_uri=item.get("uri", ""),
        artist_name=artist_name,
        album_name=album_name,
        duration_ms=item.get("duration_ms", 0),
        progress_ms=data.get("progress_ms") or 0,
        is_playing=data.get("is_playing", False),
        is_track=is_track,
    )


def detect_changes(old_state: PlayerState | None, new_state: PlayerState) -> dict:
    """Compare two player states and return what changed."""
    if old_state is None:
        return {
            "track_changed": True,
            "playback_toggled": False,
            "seek_detected": False,
        }

    track_changed = old_state.track_id != new_state.track_id
    playback_toggled = old_state.is_playing != new_state.is_playing

    # Seek detection: if progress jumped more than threshold from expected
    expected_progress = old_state.progress_ms + 1500  # ~1s poll + tolerance
    actual_jump = abs(new_state.progress_ms - expected_progress)
    seek_detected = (
        not track_changed
        and new_state.is_playing
        and actual_jump > SEEK_THRESHOLD_MS
    )

    return {
        "track_changed": track_changed,
        "playback_toggled": playback_toggled,
        "seek_detected": seek_detected,
    }


class SpotifyWorker(QThread):
    """Worker thread that polls Spotify every ~1 second."""

    track_changed = pyqtSignal(object)  # PlayerState
    state_synced = pyqtSignal(int, bool, float)  # progress_ms, is_playing, local_timestamp
    playback_toggled = pyqtSignal(bool)  # is_playing
    not_a_track = pyqtSignal()
    not_playing = pyqtSignal()
    auth_expired = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._running = True
        self._previous_state: PlayerState | None = None

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                self._poll_once()
            except Exception:
                pass  # Network errors handled silently, retry next cycle
            self.msleep(1000)

    def _poll_once(self):
        # Check token expiry and refresh if needed
        if is_token_expired(self._config.token_expires_at):
            try:
                result = refresh_access_token(
                    self._config.refresh_token, self._config.client_id
                )
                self._config.access_token = result["access_token"]
                self._config.token_expires_at = int(time.time()) + result["expires_in"]
                if "refresh_token" in result:
                    self._config.refresh_token = result["refresh_token"]
                self._config.save()
            except Exception:
                self.auth_expired.emit()
                return

        response = httpx.get(
            CURRENTLY_PLAYING_URL,
            headers={"Authorization": f"Bearer {self._config.access_token}"},
            timeout=5.0,
        )

        if response.status_code == 401:
            self.auth_expired.emit()
            return

        if response.status_code == 204 or response.status_code == 200 and not response.text:
            self.not_playing.emit()
            self._previous_state = None
            return

        if response.status_code != 200:
            return

        data = response.json()
        state = parse_player_state(data)

        if not state.is_track:
            self.not_a_track.emit()
            self._previous_state = state
            return

        changes = detect_changes(self._previous_state, state)
        local_ts = time.monotonic()

        if changes["track_changed"]:
            self.track_changed.emit(state)

        if changes["playback_toggled"]:
            self.playback_toggled.emit(state.is_playing)

        self.state_synced.emit(state.progress_ms, state.is_playing, local_ts)
        self._previous_state = state
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_spotify_worker.py -v
```

Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/spotify_worker.py tests/test_spotify_worker.py
git commit -m "feat: add Spotify polling worker with state change detection"
```

---

## Task 6: Lyrics Worker

**Files:**
- Create: `src/lyrics_worker.py`
- Test: `tests/test_lyrics_worker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_lyrics_worker.py
from unittest.mock import patch, MagicMock
from src.lyrics_worker import (
    fetch_lyrics_from_lrclib,
    rank_search_results,
    LyricsCache,
    TrackInfo,
)


class TestFetchLyrics:
    @patch("src.lyrics_worker.httpx.get")
    def test_exact_match_with_synced_lyrics(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "syncedLyrics": "[00:05.00] Hello\n[00:10.00] World",
                "plainLyrics": "Hello\nWorld",
            },
        )
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        result = fetch_lyrics_from_lrclib(info)
        assert result is not None
        assert len(result) == 2
        assert result[0] == (5000, "Hello")

    @patch("src.lyrics_worker.httpx.get")
    def test_exact_match_no_synced_lyrics_falls_to_search(self, mock_get):
        # First call: exact match returns no synced
        # Second call: search returns results
        mock_get.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {"syncedLyrics": None, "plainLyrics": "Hello"},
            ),
            MagicMock(
                status_code=200,
                json=lambda: [
                    {
                        "syncedLyrics": "[00:05.00] Found it",
                        "trackName": "Song",
                        "artistName": "Artist",
                        "duration": 180,
                    }
                ],
            ),
        ]
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        result = fetch_lyrics_from_lrclib(info)
        assert result is not None
        assert result[0] == (5000, "Found it")

    @patch("src.lyrics_worker.httpx.get")
    def test_both_fail_returns_none(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=404, json=lambda: {}),
            MagicMock(status_code=200, json=lambda: []),
        ]
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        result = fetch_lyrics_from_lrclib(info)
        assert result is None

    @patch("src.lyrics_worker.httpx.get")
    def test_network_error_raises(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("No internet")
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        import pytest
        with pytest.raises(httpx.ConnectError):
            fetch_lyrics_from_lrclib(info)


class TestRankSearchResults:
    def test_prefers_closest_duration(self):
        results = [
            {"syncedLyrics": "[00:01.00] A", "trackName": "Song", "artistName": "Artist", "duration": 300},
            {"syncedLyrics": "[00:01.00] B", "trackName": "Song", "artistName": "Artist", "duration": 181},
        ]
        best = rank_search_results(results, target_duration_s=180, target_track="Song", target_artist="Artist")
        assert best["duration"] == 181

    def test_skips_results_without_synced_lyrics(self):
        results = [
            {"syncedLyrics": None, "trackName": "Song", "artistName": "Artist", "duration": 180},
            {"syncedLyrics": "[00:01.00] B", "trackName": "Song", "artistName": "Artist", "duration": 180},
        ]
        best = rank_search_results(results, target_duration_s=180, target_track="Song", target_artist="Artist")
        assert best["syncedLyrics"] == "[00:01.00] B"

    def test_rejects_all_without_synced(self):
        results = [
            {"syncedLyrics": None, "trackName": "Song", "artistName": "Artist", "duration": 180},
        ]
        best = rank_search_results(results, target_duration_s=180, target_track="Song", target_artist="Artist")
        assert best is None

    def test_rejects_duration_beyond_tolerance(self):
        results = [
            {"syncedLyrics": "[00:01.00] A", "trackName": "Song", "artistName": "Artist", "duration": 300},
        ]
        best = rank_search_results(results, target_duration_s=180, target_track="Song", target_artist="Artist")
        assert best is None

    def test_empty_results(self):
        best = rank_search_results([], target_duration_s=180, target_track="Song", target_artist="Artist")
        assert best is None


class TestLyricsCache:
    def test_cache_hit(self):
        cache = LyricsCache()
        cache.set("t1", [(5000, "Hello")])
        assert cache.get("t1") == [(5000, "Hello")]

    def test_cache_miss(self):
        cache = LyricsCache()
        assert cache.get("unknown") is cache.MISS

    def test_cache_no_lyrics(self):
        cache = LyricsCache()
        cache.set_no_lyrics("t2")
        assert cache.get("t2") is cache.NO_LYRICS

    def test_cache_does_not_store_transient_failure(self):
        cache = LyricsCache()
        # Transient failures should not be cached — caller handles this
        assert cache.get("t3") is cache.MISS


import httpx
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_lyrics_worker.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Implement lyrics_worker module**

```python
# src/lyrics_worker.py
from dataclasses import dataclass
from enum import Enum, auto

from PyQt6.QtCore import QThread, pyqtSignal

import httpx

from src.lrc_parser import parse_lrc

LRCLIB_BASE = "https://lrclib.net/api"
DURATION_TOLERANCE_S = 5


@dataclass
class TrackInfo:
    track_id: str
    track_name: str
    artist_name: str
    album_name: str
    duration_ms: int


class LyricsCache:
    """Session cache for lyrics lookups by Spotify track ID."""

    class _Sentinel(Enum):
        MISS = auto()
        NO_LYRICS = auto()

    MISS = _Sentinel.MISS
    NO_LYRICS = _Sentinel.NO_LYRICS

    def __init__(self):
        self._store: dict[str, list[tuple[int, str]] | _Sentinel] = {}

    def get(self, track_id: str):
        return self._store.get(track_id, self.MISS)

    def set(self, track_id: str, lyrics: list[tuple[int, str]]):
        self._store[track_id] = lyrics

    def set_no_lyrics(self, track_id: str):
        self._store[track_id] = self.NO_LYRICS


def rank_search_results(
    results: list[dict],
    target_duration_s: int,
    target_track: str,
    target_artist: str,
) -> dict | None:
    """Rank lrclib search results. Return best match or None."""
    candidates = []
    for r in results:
        if not r.get("syncedLyrics"):
            continue
        duration = r.get("duration", 0)
        duration_diff = abs(duration - target_duration_s)
        if duration_diff > DURATION_TOLERANCE_S:
            continue
        # Simple scoring: lower is better
        name_match = 0 if r.get("trackName", "").lower() == target_track.lower() else 1
        artist_match = 0 if r.get("artistName", "").lower() == target_artist.lower() else 1
        score = duration_diff + name_match * 10 + artist_match * 10
        candidates.append((score, r))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def fetch_lyrics_from_lrclib(info: TrackInfo) -> list[tuple[int, str]] | None:
    """Fetch synced lyrics from lrclib.net. Returns parsed lines or None.

    Raises httpx exceptions on network errors (caller decides whether to cache).
    """
    duration_s = info.duration_ms // 1000

    # 1. Try exact match
    response = httpx.get(
        f"{LRCLIB_BASE}/get",
        params={
            "track_name": info.track_name,
            "artist_name": info.artist_name,
            "album_name": info.album_name,
            "duration": duration_s,
        },
        timeout=5.0,
    )

    if response.status_code == 200:
        data = response.json()
        synced = data.get("syncedLyrics")
        if synced:
            return parse_lrc(synced)

    # 2. Fallback: search
    response = httpx.get(
        f"{LRCLIB_BASE}/search",
        params={
            "track_name": info.track_name,
            "artist_name": info.artist_name,
        },
        timeout=5.0,
    )

    if response.status_code == 200:
        results = response.json()
        if isinstance(results, list) and results:
            best = rank_search_results(
                results,
                target_duration_s=duration_s,
                target_track=info.track_name,
                target_artist=info.artist_name,
            )
            if best and best.get("syncedLyrics"):
                return parse_lrc(best["syncedLyrics"])

    return None


class LyricsWorker(QThread):
    """Worker thread that fetches lyrics when track changes."""

    lyrics_ready = pyqtSignal(str, list)  # track_id, [(ms, text), ...]
    no_lyrics = pyqtSignal(str)  # track_id
    lyrics_unavailable = pyqtSignal(str)  # track_id (transient failure)

    def __init__(self):
        super().__init__()
        self._cache = LyricsCache()
        self._pending_track: TrackInfo | None = None
        self._has_work = False

    def request_lyrics(self, track_info: TrackInfo):
        """Queue a lyrics lookup request. Called from main thread."""
        self._pending_track = track_info
        self._has_work = True
        if not self.isRunning():
            self.start()

    def run(self):
        while self._has_work:
            self._has_work = False
            info = self._pending_track
            if info is None:
                return

            track_id = info.track_id

            # Check cache
            cached = self._cache.get(track_id)
            if cached is not LyricsCache.MISS:
                if cached is LyricsCache.NO_LYRICS:
                    self.no_lyrics.emit(track_id)
                else:
                    self.lyrics_ready.emit(track_id, cached)
                return

            # Fetch from network
            try:
                result = fetch_lyrics_from_lrclib(info)
                if result:
                    self._cache.set(track_id, result)
                    self.lyrics_ready.emit(track_id, result)
                else:
                    self._cache.set_no_lyrics(track_id)
                    self.no_lyrics.emit(track_id)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
                # Transient failure — do NOT cache
                self.lyrics_unavailable.emit(track_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_lyrics_worker.py -v
```

Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/lyrics_worker.py tests/test_lyrics_worker.py
git commit -m "feat: add lyrics worker with lrclib lookup, ranking, and session cache"
```

---

## Task 7: UI Widget

**Files:**
- Create: `src/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_widget.py
import time
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from src.widget import LyricsWidget


def test_widget_creates_without_crash(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    assert widget.isVisible() is False  # not shown until show() called


def test_widget_flags(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    flags = widget.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_update_track_info(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.update_track_info("Test Song", "Test Artist")
    assert "Test Song" in widget._track_label.text()
    assert "Test Artist" in widget._track_label.text()


def test_update_lyric_line(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_lyric_text("Hello world")
    assert widget._lyric_label.text() == "Hello world"


def test_update_progress_bar(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.update_progress(0.5)
    # Progress should be 50%
    assert widget._progress_bar.value() == 50


def test_show_no_lyrics_state(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show_no_lyrics()
    assert widget._lyric_label.text() != ""


def test_show_not_playing_state(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show_not_playing()
    assert widget._lyric_label.text() != ""


def test_close_button_visible_on_hover(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget._on_enter_hover()
    assert widget._close_btn.isVisible()
    widget._on_leave_hover()
    assert not widget._close_btn.isVisible()


def test_resync_local_timer(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_lyrics([(5000, "Line 1"), (10000, "Line 2")])
    widget.resync_local_timer(7000, True, time.monotonic())
    # After resync, estimated progress should be around 7000
    assert widget._last_synced_ms == 7000
    assert widget._is_playing is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_widget.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Implement widget module**

```python
# src/widget.py
import time

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette, QMouseEvent, QEnterEvent
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

from src.lrc_parser import find_current_line

# Colors
BLACK = "#000000"
WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_GRAY = "#282828"

UI_TIMER_INTERVAL_MS = 150


class LyricsWidget(QWidget):
    """Frameless always-on-top floating lyrics widget."""

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._setup_ui()
        self._setup_timer()

        # State
        self._lyrics: list[tuple[int, str]] = []
        self._current_line_idx: int = -1
        self._last_synced_ms: int = 0
        self._last_sync_time: float = 0.0
        self._is_playing: bool = False
        self._duration_ms: int = 0

        # Drag state
        self._drag_pos: QPoint | None = None

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # Hide from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(420)
        self.setStyleSheet(f"background-color: {BLACK};")
        self.setMouseTracking(True)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 10, 16, 0)
        layout.setSpacing(4)

        # Top row: track info + close button
        top_row = QHBoxLayout()
        self._track_label = QLabel("")
        self._track_label.setFont(QFont("Segoe UI", 9))
        self._track_label.setStyleSheet(f"color: {WHITE};")
        self._track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._track_label, stretch=1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
        top_row.addWidget(self._close_btn)

        layout.addLayout(top_row)

        # Lyric line
        self._lyric_label = QLabel("")
        self._lyric_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._lyric_label.setStyleSheet(f"color: {SPOTIFY_GREEN};")
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        self._lyric_label.setMinimumHeight(40)
        layout.addWidget(self._lyric_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(2)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {DARK_GRAY}; border: none; }}"
            f"QProgressBar::chunk {{ background-color: {SPOTIFY_GREEN}; }}"
        )
        layout.addWidget(self._progress_bar)

        self.setLayout(layout)

    def _setup_timer(self):
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(UI_TIMER_INTERVAL_MS)
        self._ui_timer.timeout.connect(self._on_ui_tick)

    def start_ui_timer(self):
        self._ui_timer.start()

    def stop_ui_timer(self):
        self._ui_timer.stop()

    # --- Public API ---

    def update_track_info(self, track_name: str, artist_name: str):
        self._track_label.setText(f"{track_name} — {artist_name}")

    def set_lyrics(self, lyrics: list[tuple[int, str]]):
        self._lyrics = lyrics
        self._current_line_idx = -1

    def set_lyric_text(self, text: str):
        self._lyric_label.setText(text)

    def set_duration(self, duration_ms: int):
        self._duration_ms = duration_ms

    def update_progress(self, ratio: float):
        self._progress_bar.setValue(int(ratio * 100))

    def resync_local_timer(self, progress_ms: int, is_playing: bool, local_timestamp: float):
        self._last_synced_ms = progress_ms
        self._last_sync_time = local_timestamp
        self._is_playing = is_playing
        if is_playing and not self._ui_timer.isActive():
            self._ui_timer.start()
        elif not is_playing:
            self._update_lyric_display(progress_ms)

    def show_no_lyrics(self):
        self._lyrics = []
        self._lyric_label.setText("♫ no synced lyrics")

    def show_not_playing(self):
        self._lyrics = []
        self._lyric_label.setText("⏸ not playing")
        self.update_progress(0)

    def show_not_a_track(self):
        self._lyrics = []
        self._lyric_label.setText("• not a track")

    def show_unavailable(self):
        self._lyrics = []
        self._lyric_label.setText("⚠ lyrics unavailable")

    # --- Private ---

    def _on_ui_tick(self):
        if not self._is_playing or not self._lyrics:
            return
        estimated_ms = self._last_synced_ms + int(
            (time.monotonic() - self._last_sync_time) * 1000
        )
        self._update_lyric_display(estimated_ms)
        if self._duration_ms > 0:
            self.update_progress(min(estimated_ms / self._duration_ms, 1.0))

    def _update_lyric_display(self, progress_ms: int):
        idx = find_current_line(self._lyrics, progress_ms)
        if idx != self._current_line_idx:
            self._current_line_idx = idx
            if idx >= 0:
                self._lyric_label.setText(self._lyrics[idx][1])
            else:
                self._lyric_label.setText("")

    # --- Hover ---

    def _on_enter_hover(self):
        self._close_btn.setVisible(True)

    def _on_leave_hover(self):
        self._close_btn.setVisible(False)

    def enterEvent(self, event: QEnterEvent):
        self._on_enter_hover()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._on_leave_hover()
        super().leaveEvent(event)

    # --- Dragging ---

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_widget.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/widget.py tests/test_widget.py
git commit -m "feat: add PyQt6 lyrics widget with timer, drag, hover"
```

---

## Task 8: OAuth Callback Server

**Files:**
- Create: `src/auth_server.py`
- Test: (manual testing — HTTP server is integration-level)

- [ ] **Step 1: Implement the local callback server**

```python
# src/auth_server.py
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread

from src.auth import (
    generate_code_verifier,
    generate_code_challenge,
    build_auth_url,
    exchange_code_for_token,
)

CALLBACK_PORT = 8888


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback."""

    auth_code: str | None = None
    received_state: str | None = None
    error: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            _CallbackHandler.error = params["error"][0]
        elif "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            _CallbackHandler.received_state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Authorization complete. You can close this tab.</h1></body></html>")

    def log_message(self, format, *args):
        pass  # Suppress console output


def run_oauth_flow(client_id: str) -> dict:
    """Run the full PKCE OAuth flow. Opens browser, waits for callback.

    Returns dict with access_token, refresh_token, expires_in.
    Raises Exception on failure.
    """
    # Reset handler state
    _CallbackHandler.auth_code = None
    _CallbackHandler.received_state = None
    _CallbackHandler.error = None

    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = secrets.token_urlsafe(16)

    auth_url = build_auth_url(client_id, challenge, state)
    webbrowser.open(auth_url)

    # Start local server and wait for callback
    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    # Block until one request is received
    server.handle_request()
    server.server_close()

    if _CallbackHandler.error:
        raise Exception(f"OAuth error: {_CallbackHandler.error}")

    if _CallbackHandler.auth_code is None:
        raise Exception("No authorization code received")

    if _CallbackHandler.received_state != state:
        raise Exception("OAuth state mismatch — possible CSRF attack")

    # Exchange code for tokens
    return exchange_code_for_token(_CallbackHandler.auth_code, verifier, client_id)
```

- [ ] **Step 2: Commit**

```bash
git add src/auth_server.py
git commit -m "feat: add OAuth callback server for PKCE flow"
```

---

## Task 9: Main Application (Integration)

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement main.py**

```python
# src/main.py
import sys
import time

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox
from PyQt6.QtCore import QObject, pyqtSlot

from src.config import Config
from src.auth import is_token_expired, refresh_access_token
from src.auth_server import run_oauth_flow
from src.spotify_worker import SpotifyWorker, PlayerState
from src.lyrics_worker import LyricsWorker, TrackInfo
from src.widget import LyricsWidget


class App(QObject):
    """Main application controller. Wires all modules together."""

    def __init__(self):
        super().__init__()
        self._config = Config()
        self._widget = LyricsWidget()
        self._spotify_worker = SpotifyWorker(self._config)
        self._lyrics_worker = LyricsWorker()
        self._current_track_id: str | None = None

    def start(self):
        """Bootstrap the app: config → auth → show widget → start polling."""
        # 1. Ensure client_id
        if not self._config.client_id:
            client_id, ok = QInputDialog.getText(
                None,
                "Spotify Lyrics Widget",
                "Paste your Spotify App client_id:"
            )
            if not ok or not client_id.strip():
                QMessageBox.critical(None, "Error", "client_id is required.")
                sys.exit(1)
            self._config.client_id = client_id.strip()
            self._config.save()

        # 2. Auth: refresh or new OAuth
        if not self._ensure_auth():
            sys.exit(1)

        # 3. Connect signals
        self._connect_signals()

        # 4. Show widget and start polling
        self._widget.move(self._config.window_x, self._config.window_y)
        self._widget.show()
        self._widget.start_ui_timer()
        self._spotify_worker.start()

    def _ensure_auth(self) -> bool:
        """Try to refresh existing token, or run OAuth flow."""
        if self._config.refresh_token and not is_token_expired(self._config.token_expires_at):
            return True  # Token still valid

        if self._config.refresh_token:
            try:
                result = refresh_access_token(
                    self._config.refresh_token, self._config.client_id
                )
                self._apply_token_result(result)
                return True
            except Exception:
                pass  # Fall through to OAuth

        # Run OAuth flow
        try:
            result = run_oauth_flow(self._config.client_id)
            self._apply_token_result(result)
            return True
        except Exception as e:
            QMessageBox.critical(None, "Auth Failed", str(e))
            return False

    def _apply_token_result(self, result: dict):
        self._config.access_token = result["access_token"]
        self._config.token_expires_at = int(time.time()) + result["expires_in"]
        if "refresh_token" in result:
            self._config.refresh_token = result["refresh_token"]
        self._config.save()

    def _connect_signals(self):
        # Spotify worker signals
        self._spotify_worker.track_changed.connect(self._on_track_changed)
        self._spotify_worker.state_synced.connect(self._on_state_synced)
        self._spotify_worker.playback_toggled.connect(self._on_playback_toggled)
        self._spotify_worker.not_a_track.connect(self._on_not_a_track)
        self._spotify_worker.not_playing.connect(self._on_not_playing)
        self._spotify_worker.auth_expired.connect(self._on_auth_expired)

        # Lyrics worker signals
        self._lyrics_worker.lyrics_ready.connect(self._on_lyrics_ready)
        self._lyrics_worker.no_lyrics.connect(self._on_no_lyrics)
        self._lyrics_worker.lyrics_unavailable.connect(self._on_lyrics_unavailable)

    @pyqtSlot(object)
    def _on_track_changed(self, state: PlayerState):
        self._current_track_id = state.track_id
        self._widget.update_track_info(state.track_name, state.artist_name)
        self._widget.set_duration(state.duration_ms)
        self._widget.set_lyric_text("")  # Clear while loading

        # Request lyrics lookup
        info = TrackInfo(
            track_id=state.track_id,
            track_name=state.track_name,
            artist_name=state.artist_name,
            album_name=state.album_name,
            duration_ms=state.duration_ms,
        )
        self._lyrics_worker.request_lyrics(info)

    @pyqtSlot(int, bool, float)
    def _on_state_synced(self, progress_ms: int, is_playing: bool, local_ts: float):
        self._widget.resync_local_timer(progress_ms, is_playing, local_ts)

    @pyqtSlot(bool)
    def _on_playback_toggled(self, is_playing: bool):
        if not is_playing:
            self._widget.stop_ui_timer()

    @pyqtSlot()
    def _on_not_a_track(self):
        self._widget.show_not_a_track()
        self._current_track_id = None

    @pyqtSlot()
    def _on_not_playing(self):
        self._widget.show_not_playing()
        self._current_track_id = None

    @pyqtSlot()
    def _on_auth_expired(self):
        self._spotify_worker.stop()
        if self._ensure_auth():
            self._spotify_worker.start()

    @pyqtSlot(str, list)
    def _on_lyrics_ready(self, track_id: str, lyrics: list):
        # Ignore stale results
        if track_id != self._current_track_id:
            return
        self._widget.set_lyrics(lyrics)

    @pyqtSlot(str)
    def _on_no_lyrics(self, track_id: str):
        if track_id != self._current_track_id:
            return
        self._widget.show_no_lyrics()

    @pyqtSlot(str)
    def _on_lyrics_unavailable(self, track_id: str):
        if track_id != self._current_track_id:
            return
        self._widget.show_unavailable()

    def shutdown(self):
        """Clean shutdown: save window position, stop workers."""
        pos = self._widget.pos()
        self._config.window_x = pos.x()
        self._config.window_y = pos.y()
        self._config.save()
        self._spotify_worker.stop()
        self._spotify_worker.wait(2000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Spotify Lyrics Widget")

    controller = App()
    controller.start()

    # Save position on quit
    app.aboutToQuit.connect(controller.shutdown)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual smoke test**

```bash
python -m src.main
```

Expected: Widget window appears. If no `client_id` configured, a dialog asks for it. After auth, widget shows current track lyrics.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: add main app integrating all V1 modules"
```

---

## Task 10: Error States & Polish

**Files:**
- Modify: `src/widget.py` (add offline indicator)
- Modify: `src/spotify_worker.py` (network retry logic)

- [ ] **Step 1: Add offline indicator to widget**

Add to `LyricsWidget._setup_ui()` after the top row:

```python
        # Offline indicator (hidden by default)
        self._offline_label = QLabel("⚠ offline")
        self._offline_label.setFont(QFont("Segoe UI", 8))
        self._offline_label.setStyleSheet(f"color: #FF6B6B;")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._offline_label.setVisible(False)
        layout.insertWidget(0, self._offline_label)
```

Add public methods:

```python
    def show_offline(self):
        self._offline_label.setVisible(True)

    def hide_offline(self):
        self._offline_label.setVisible(False)
```

- [ ] **Step 2: Connect offline state in main.py**

Add a new signal to `SpotifyWorker`:

```python
    network_error = pyqtSignal()
    network_recovered = pyqtSignal()
```

In `SpotifyWorker._poll_once()`, track consecutive failures and emit signals. In `App._connect_signals()`:

```python
        self._spotify_worker.network_error.connect(self._widget.show_offline)
        self._spotify_worker.network_recovered.connect(self._widget.hide_offline)
```

- [ ] **Step 3: Test offline indicator**

```python
# Add to tests/test_widget.py

def test_offline_indicator(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show_offline()
    assert widget._offline_label.isVisible()
    widget.hide_offline()
    assert not widget._offline_label.isVisible()
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/widget.py src/spotify_worker.py src/main.py tests/test_widget.py
git commit -m "feat: add offline indicator and network error handling"
```

---

## Task 11: Final Integration Test

- [ ] **Step 1: End-to-end manual test checklist**

Run the app and verify each scenario:

```bash
python -m src.main
```

1. First launch: client_id dialog appears
2. OAuth flow opens browser, callback works
3. Widget appears with current track info
4. Lyrics sync with music (within ~1s accuracy)
5. Progress bar advances smoothly
6. Track change: new lyrics load
7. Pause: lyrics freeze, progress stops
8. Resume: lyrics continue from correct position
9. Seek: lyrics jump to correct line
10. Song without synced lyrics: shows "no synced lyrics"
11. Podcast/episode: shows "not a track"
12. Close widget: window position saved
13. Relaunch: widget appears at saved position, no re-auth needed
14. Drag widget: moves freely

- [ ] **Step 2: Fix any issues found during manual testing**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: V1 lyrics core complete — all manual tests passing"
```
