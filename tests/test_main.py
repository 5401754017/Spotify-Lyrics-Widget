from unittest.mock import MagicMock, patch

import src.main as main_module
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


def test_main_configures_logging_before_starting_qapplication():
    events = []

    with (
        patch("src.main.configure_logging", side_effect=lambda: events.append("log")),
        patch("src.main.QApplication", side_effect=lambda argv: events.append("qt") or MagicMock(exec=lambda: 0)),
        patch("src.main.App"),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.sys.exit", side_effect=lambda code=0: events.append(("exit", code))),
    ):
        guard_class.return_value.try_claim.return_value = False
        main_module.main()

    assert events[:2] == ["log", "qt"]


def test_main_logs_and_shows_startup_failure():
    app_instance = MagicMock(exec=lambda: 0)
    controller = MagicMock()
    controller.start.side_effect = RuntimeError("boom")

    with (
        patch("src.main.configure_logging"),
        patch("src.main.QApplication", return_value=app_instance),
        patch("src.main.App", return_value=controller),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.logging.exception") as log_exception,
        patch("src.main.QMessageBox.critical") as critical,
        patch("src.main.sys.exit", side_effect=lambda code=0: None),
    ):
        guard_class.return_value.try_claim.return_value = True
        main_module.main()

    log_exception.assert_called()
    critical.assert_called_once()


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


def test_connect_signals_wires_offline_indicator():
    app, _, widget = _make_app()

    app._connect_signals()

    app._spotify_worker.network_error.connect.assert_called_once_with(
        widget.show_offline
    )
    app._spotify_worker.network_recovered.connect.assert_called_once_with(
        widget.hide_offline
    )


def test_connect_signals_wires_rate_limit_state():
    app, _, widget = _make_app()

    app._connect_signals()

    app._spotify_worker.rate_limited.connect.assert_called_once_with(
        widget.show_rate_limited
    )


def test_widget_close_request_quits_qapplication():
    fake_qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=fake_qapp),
        patch("src.main.Config", return_value=MagicMock(refresh_token="refresh")),
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        app = App()

    app._widget.close_requested.connect.assert_called_once_with(fake_qapp.quit)


def test_shutdown_reloads_config_before_saving_window_position():
    initial_config = MagicMock()
    initial_config.refresh_token = "old_refresh"
    initial_config.config_dir = "config-dir"
    fresh_config = MagicMock()
    widget = MagicMock()
    widget.pos.return_value.x.return_value = 321
    widget.pos.return_value.y.return_value = 654

    with (
        patch("src.main.Config", side_effect=[initial_config, fresh_config]),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        app = App()
        app.shutdown()

    assert fresh_config.window_x == 321
    assert fresh_config.window_y == 654
    fresh_config.save.assert_called_once()
    initial_config.save.assert_not_called()


def test_shutdown_stops_workers_before_exit():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.config_dir = "config-dir"
    fresh_config = MagicMock()
    widget = MagicMock()
    spotify_worker = MagicMock()
    lyrics_worker = MagicMock()
    lyrics_worker.isRunning.return_value = True

    with (
        patch("src.main.Config", side_effect=[config, fresh_config]),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=spotify_worker),
        patch("src.main.LyricsWorker", return_value=lyrics_worker),
    ):
        app = App()
        app.shutdown()

    spotify_worker.stop.assert_called_once()
    spotify_worker.wait.assert_called_once_with(2000)
    lyrics_worker.wait.assert_called_once_with(6000)


def test_single_instance_guard_activates_existing_instance(qtbot):
    from uuid import uuid4

    from src.main import SingleInstanceGuard

    activations = []
    name = f"spotify-widget-test-{uuid4()}"
    first = SingleInstanceGuard(name, lambda: activations.append("raise"))
    second = SingleInstanceGuard(name, lambda: None)

    try:
        assert first.try_claim() is True
        assert second.try_claim() is False
        qtbot.waitUntil(lambda: activations == ["raise"], timeout=1000)
    finally:
        first.close()
        second.close()
