import logging
import time
from dataclasses import dataclass

import httpx
from PyQt6.QtCore import QThread, pyqtSignal

from src.auth import is_token_expired, refresh_access_token


CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
SEEK_THRESHOLD_MS = 3000
DEFAULT_RETRY_AFTER_SECONDS = 1


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
    """Parse Spotify currently-playing data into widget-facing state."""
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
    artists = item.get("artists", [])
    artist_name = ", ".join(artist["name"] for artist in artists) if artists else ""

    return PlayerState(
        track_id=item.get("id"),
        track_name=item.get("name", ""),
        track_uri=item.get("uri", ""),
        artist_name=artist_name,
        album_name=item.get("album", {}).get("name", ""),
        duration_ms=item.get("duration_ms", 0),
        progress_ms=data.get("progress_ms") or 0,
        is_playing=data.get("is_playing", False),
        is_track=data.get("currently_playing_type", "unknown") == "track",
    )


def detect_changes(old_state: PlayerState | None, new_state: PlayerState) -> dict:
    """Compare two player states and describe the changes relevant to the UI."""
    if old_state is None:
        return {
            "track_changed": True,
            "playback_toggled": False,
            "seek_detected": False,
        }

    track_changed = old_state.track_id != new_state.track_id
    expected_progress = old_state.progress_ms + 1500
    actual_jump = abs(new_state.progress_ms - expected_progress)

    return {
        "track_changed": track_changed,
        "playback_toggled": old_state.is_playing != new_state.is_playing,
        "seek_detected": (
            not track_changed
            and new_state.is_playing
            and actual_jump > SEEK_THRESHOLD_MS
        ),
    }


class SpotifyWorker(QThread):
    """Poll Spotify currently-playing state in a worker thread."""

    track_changed = pyqtSignal(object)
    state_synced = pyqtSignal(int, bool, float)
    playback_toggled = pyqtSignal(bool)
    not_a_track = pyqtSignal()
    not_playing = pyqtSignal()
    auth_expired = pyqtSignal()
    network_error = pyqtSignal()
    network_recovered = pyqtSignal()
    rate_limited = pyqtSignal(int)

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._running = True
        self._previous_state: PlayerState | None = None
        self._network_failed = False
        self._rate_limited_until = 0.0

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            self._poll_once()
            self.msleep(self._next_sleep_ms())

    def _next_sleep_ms(self) -> int:
        if not self._is_rate_limited():
            return 1000
        remaining_ms = int((self._rate_limited_until - time.monotonic()) * 1000)
        return max(100, min(remaining_ms, 1000))

    def _is_rate_limited(self) -> bool:
        return time.monotonic() < self._rate_limited_until

    def _refresh_token(self) -> bool:
        try:
            result = refresh_access_token(
                self._config.refresh_token, self._config.client_id
            )
            self._config.access_token = result["access_token"]
            self._config.token_expires_at = int(time.time()) + result["expires_in"]
            if "refresh_token" in result:
                self._config.refresh_token = result["refresh_token"]
            self._config.save()
            return True
        except Exception:
            logging.exception("Failed to refresh Spotify access token")
            return False

    def _make_spotify_request(self):
        """Return a currently-playing response or None after auth expiry."""
        if is_token_expired(self._config.token_expires_at):
            if not self._refresh_token():
                self.auth_expired.emit()
                return None

        response = httpx.get(
            CURRENTLY_PLAYING_URL,
            headers={"Authorization": f"Bearer {self._config.access_token}"},
            timeout=5.0,
        )

        if response.status_code == 401:
            if not self._refresh_token():
                self.auth_expired.emit()
                return None
            response = httpx.get(
                CURRENTLY_PLAYING_URL,
                headers={"Authorization": f"Bearer {self._config.access_token}"},
                timeout=5.0,
            )
            if response.status_code == 401:
                self.auth_expired.emit()
                return None

        return response

    def _poll_once(self):
        if self._is_rate_limited():
            return

        try:
            response = self._make_spotify_request()
        except (httpx.ConnectError, httpx.TimeoutException) as error:
            logging.warning(
                "Spotify currently-playing request failed: %s: %s",
                type(error).__name__,
                error,
            )
            if not self._network_failed:
                self._network_failed = True
                self.network_error.emit()
            return
        except Exception:
            logging.exception("Unexpected error while polling Spotify")
            return

        if self._network_failed:
            self._network_failed = False
            self.network_recovered.emit()

        if response is None:
            return

        if response.status_code == 204 or (
            response.status_code == 200 and not response.text
        ):
            self.not_playing.emit()
            self._previous_state = None
            return

        if response.status_code == 429:
            retry_after = self._parse_retry_after(response)
            self._rate_limited_until = time.monotonic() + retry_after
            logging.warning(
                "Spotify rate limited polling; retrying after %s seconds",
                retry_after,
            )
            self.rate_limited.emit(retry_after)
            return

        if response.status_code != 200:
            return

        data = response.json()
        state = parse_player_state(data)
        logging.info(
            "Spotify playback summary: status=%s is_playing=%s type=%s "
            "track_id=%s track=%s artist=%s progress_ms=%s",
            response.status_code,
            state.is_playing,
            data.get("currently_playing_type", "unknown"),
            state.track_id,
            state.track_name,
            state.artist_name,
            state.progress_ms,
        )
        if not state.is_track:
            self.not_a_track.emit()
            self._previous_state = state
            return

        changes = detect_changes(self._previous_state, state)
        if changes["track_changed"]:
            self.track_changed.emit(state)
        if changes["playback_toggled"]:
            self.playback_toggled.emit(state.is_playing)

        self.state_synced.emit(state.progress_ms, state.is_playing, time.monotonic())
        self._previous_state = state

    def _parse_retry_after(self, response) -> int:
        try:
            retry_after = int(response.headers.get("Retry-After", ""))
        except (TypeError, ValueError):
            retry_after = DEFAULT_RETRY_AFTER_SECONDS
        return max(DEFAULT_RETRY_AFTER_SECONDS, retry_after)
