import time
from unittest.mock import MagicMock, patch

import httpx

from src.spotify_worker import PlayerState, detect_changes, parse_player_state


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
        new = self._make_state(progress_ms=50000)
        changes = detect_changes(old, new)
        assert changes["seek_detected"] is True

    def test_normal_progress_no_seek(self):
        old = self._make_state(progress_ms=10000)
        new = self._make_state(progress_ms=11050)
        changes = detect_changes(old, new)
        assert changes["seek_detected"] is False

    def test_first_state_no_previous(self):
        new = self._make_state()
        changes = detect_changes(None, new)
        assert changes["track_changed"] is True


class TestSpotifyWorker401:
    @patch("src.spotify_worker.httpx.get")
    @patch("src.spotify_worker.refresh_access_token")
    def test_401_triggers_refresh_and_retry(self, mock_refresh, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_config = MagicMock()
        mock_config.access_token = "old_token"
        mock_config.refresh_token = "refresh"
        mock_config.client_id = "client"
        mock_config.token_expires_at = int(time.time()) + 3600

        mock_refresh.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_get.side_effect = [
            MagicMock(status_code=401),
            MagicMock(
                status_code=200,
                text='{"is_playing": false}',
                json=lambda: {
                    "is_playing": False,
                    "progress_ms": None,
                    "currently_playing_type": "unknown",
                    "item": None,
                },
            ),
        ]

        worker = SpotifyWorker(mock_config)
        response = worker._make_spotify_request()
        assert response.status_code == 200
        mock_refresh.assert_called()


class TestSpotifyWorkerNetworkError:
    @patch("src.spotify_worker.httpx.get")
    def test_network_error_emits_signal(self, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_get.side_effect = httpx.ConnectError("No internet")

        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        error_signals = []
        worker.network_error.connect(lambda: error_signals.append("error"))

        worker._poll_once()
        assert len(error_signals) == 1

        worker._poll_once()
        assert len(error_signals) == 1

    @patch("src.spotify_worker.httpx.get")
    def test_recovery_after_network_error(self, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_get.side_effect = [
            httpx.ConnectError("No internet"),
            MagicMock(status_code=204, text=""),
        ]

        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        error_signals = []
        recovered_signals = []
        worker.network_error.connect(lambda: error_signals.append("error"))
        worker.network_recovered.connect(
            lambda: recovered_signals.append("recovered")
        )

        worker._poll_once()
        assert len(error_signals) == 1

        worker._poll_once()
        assert len(recovered_signals) == 1


class TestSpotifyWorkerRateLimit:
    @patch("src.spotify_worker.httpx.get")
    def test_429_sets_retry_after_backoff_and_emits_signal(self, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_get.return_value = MagicMock(
            status_code=429,
            text="",
            headers={"Retry-After": "30"},
        )
        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        signals = []
        worker.rate_limited.connect(lambda seconds: signals.append(seconds))

        with patch("src.spotify_worker.time.monotonic", return_value=100.0):
            worker._poll_once()

        assert signals == [30]
        assert worker._rate_limited_until == 130.0

    @patch("src.spotify_worker.httpx.get")
    def test_rate_limit_backoff_skips_polling_until_retry_after(self, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        worker._rate_limited_until = 130.0

        with patch("src.spotify_worker.time.monotonic", return_value=120.0):
            worker._poll_once()

        mock_get.assert_not_called()

    @patch("src.spotify_worker.logging.warning")
    @patch("src.spotify_worker.httpx.get")
    def test_429_logs_retry_after(self, mock_get, log_warning):
        from src.spotify_worker import SpotifyWorker

        mock_get.return_value = MagicMock(
            status_code=429,
            text="",
            headers={"Retry-After": "15"},
        )
        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        worker._poll_once()

        log_warning.assert_called()


class TestSpotifyWorkerIdleResponse:
    @patch("src.spotify_worker.httpx.get")
    def test_204_emits_not_playing_and_resets_previous_state(self, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_get.return_value = MagicMock(status_code=204, text="")

        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        worker._previous_state = PlayerState(
            track_id="old",
            track_name="Old Song",
            track_uri="spotify:track:old",
            artist_name="Old Artist",
            album_name="Old Album",
            duration_ms=200000,
            progress_ms=10000,
            is_playing=True,
            is_track=True,
        )
        signals = []
        worker.not_playing.connect(lambda: signals.append("not_playing"))

        worker._poll_once()

        assert signals == ["not_playing"]
        assert worker._previous_state is None
