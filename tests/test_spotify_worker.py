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
