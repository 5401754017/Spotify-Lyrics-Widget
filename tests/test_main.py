from unittest.mock import MagicMock, patch

from src.main import App


def _make_app():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    widget = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        app = App()

    return app, config, widget


def test_apply_token_result_keeps_refresh_token_when_response_omits_rotation():
    app, config, _ = _make_app()

    with patch("src.main.time.time", return_value=1000):
        app._apply_token_result({"access_token": "access", "expires_in": 3600})

    assert config.access_token == "access"
    assert config.token_expires_at == 4600
    assert config.refresh_token == "existing_refresh"
    config.save.assert_called_once()


def test_lyrics_ready_ignores_stale_track_result():
    app, _, widget = _make_app()
    app._current_track_id = "current"

    app._on_lyrics_ready("old", [(5000, "stale")])
    widget.set_lyrics.assert_not_called()

    app._on_lyrics_ready("current", [(5000, "current")])
    widget.set_lyrics.assert_called_once_with([(5000, "current")])
