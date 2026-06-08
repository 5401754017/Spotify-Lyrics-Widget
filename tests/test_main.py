import logging
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QDialog

import src.main as main_module
from src.main import App
from src.spotify_worker import PlayerState


def _make_app():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.granted_scope = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    widget = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        app = App()

    return app, config, widget


def test_start_missing_client_id_uses_onboarding_dialog():
    app, config, _ = _make_app()
    config.client_id = None
    config.size_preset = "large"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.client_id = "client-from-dialog"

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.SpotifyOnboardingDialog", return_value=dialog) as dialog_class,
        patch("src.main.TrayIcon"),
    ):
        app.start()

    dialog_class.assert_called_once_with(main_module.REDIRECT_URI)
    assert config.client_id == "client-from-dialog"
    config.save.assert_called_once()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()


def test_start_cancelled_onboarding_exits_without_starting_workers():
    app, config, _ = _make_app()
    config.client_id = None
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected

    with (
        patch("src.main.SpotifyOnboardingDialog", return_value=dialog),
        patch("src.main.sys.exit", side_effect=SystemExit) as exit_app,
        pytest.raises(SystemExit),
    ):
        app.start()

    exit_app.assert_called_once_with(1)
    config.save.assert_not_called()
    app._spotify_worker.start.assert_not_called()


def test_start_existing_client_id_skips_onboarding_dialog():
    app, config, _ = _make_app()
    config.client_id = "existing-client"
    config.size_preset = "large"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.SpotifyOnboardingDialog") as dialog_class,
        patch("src.main.TrayIcon"),
    ):
        app.start()

    dialog_class.assert_not_called()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()


def test_main_configures_logging_before_starting_qapplication():
    events = []

    with (
        patch("src.main.configure_logging", side_effect=lambda: events.append("log")),
        patch("src.main.QApplication", side_effect=lambda argv: events.append("qt") or MagicMock(exec=lambda: 0)),
        patch("src.main.load_app_font"),
        patch("src.main.App"),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.sys.exit", side_effect=lambda code=0: events.append(("exit", code))),
    ):
        guard_class.return_value.try_claim.return_value = False
        main_module.main()

    assert events[:2] == ["log", "qt"]


def test_main_loads_font_before_building_app():
    events = []
    qapp = MagicMock(exec=lambda: 0)
    qapp.setApplicationName.side_effect = lambda name: events.append("name")

    with (
        patch("src.main.configure_logging"),
        patch("src.main.QApplication", return_value=qapp),
        patch("src.main.load_app_font", side_effect=lambda: events.append("font")),
        patch("src.main.App", side_effect=lambda: events.append("app") or MagicMock()),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.sys.exit", side_effect=lambda code=0: events.append(("exit", code))),
    ):
        guard_class.return_value.try_claim.return_value = False
        main_module.main()

    assert events[:3] == ["name", "font", "app"]


def test_main_logs_and_shows_startup_failure():
    app_instance = MagicMock(exec=lambda: 0)
    controller = MagicMock()
    controller.start.side_effect = RuntimeError("boom")

    with (
        patch("src.main.configure_logging"),
        patch("src.main.QApplication", return_value=app_instance),
        patch("src.main.load_app_font"),
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


def test_track_change_updates_widget_without_forced_visual_refresh():
    app, _, widget = _make_app()
    widget.force_visual_refresh = MagicMock()
    state = PlayerState(
        track_id="new",
        track_name="New Song",
        track_uri="spotify:track:new",
        artist_name="Artist",
        album_name="Album",
        duration_ms=180000,
        progress_ms=0,
        is_playing=True,
        is_track=True,
    )

    app._on_track_changed(state)

    widget.update_track_info.assert_called_once_with("New Song", "Artist")
    widget.set_lyric_text.assert_called_once_with("")
    widget.force_visual_refresh.assert_not_called()


def test_track_change_clears_stale_lyrics():
    app, _, widget = _make_app()
    state = PlayerState(
        track_id="new",
        track_name="New Song",
        track_uri="spotify:track:new",
        artist_name="Artist",
        album_name="Album",
        duration_ms=180000,
        progress_ms=0,
        is_playing=True,
        is_track=True,
    )

    app._on_track_changed(state)

    widget.set_lyrics.assert_called_once_with([])


def test_start_creates_and_shows_tray():
    app, config, _ = _make_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.TrayIcon") as tray_class,
    ):
        tray = tray_class.return_value
        app.start()

    tray_class.assert_called_once_with(
        on_toggle=app._toggle_widget,
        on_quit=qapp.quit,
        on_size_changed=app._on_size_preset_changed,
        size_preset=config.size_preset,
    )
    tray.show.assert_called_once()


def test_toggle_widget_hides_when_visible():
    app, _, widget = _make_app()
    widget.isVisible.return_value = True

    app._toggle_widget()

    widget.hide.assert_called_once()


def test_toggle_widget_raises_when_hidden():
    app, _, widget = _make_app()
    widget.isVisible.return_value = False

    app._toggle_widget()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    widget.activateWindow.assert_called_once()


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


def test_shutdown_hides_tray_before_exit():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.config_dir = "config-dir"
    fresh_config = MagicMock()
    tray = MagicMock()

    with (
        patch("src.main.Config", side_effect=[config, fresh_config]),
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock(isRunning=lambda: False)),
    ):
        app = App()
        app._tray = tray
        app.shutdown()

    tray.hide.assert_called_once()


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


# ---- V1.5 Task 3: token pre-refresh warning ----


def test_ensure_auth_warns_when_pre_refresh_fails_then_falls_through(caplog):
    app, config, _widget = _make_app()
    config.token_expires_at = 0  # force expired so the pre-refresh branch runs
    with (
        patch("src.main.is_token_expired", return_value=True),
        patch("src.main.refresh_access_token", side_effect=RuntimeError("refresh boom")),
        patch("src.main.run_oauth_flow",
              return_value={"access_token": "new", "expires_in": 3600}),
    ):
        caplog.set_level(logging.WARNING)
        assert app._ensure_auth() is True

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("token pre-refresh failed" in r.message.lower()
               and "RuntimeError" in r.message
               and "refresh boom" in r.message
               and "oauth" in r.message.lower() for r in warnings), \
        f"expected pre-refresh fall-through warning, got: {[r.message for r in warnings]}"


def test_apply_token_result_saves_granted_scope():
    app, config, _ = _make_app()

    with patch("src.main.time.time", return_value=1000):
        app._apply_token_result(
            {
                "access_token": "access",
                "expires_in": 3600,
                "scope": (
                    "user-read-currently-playing user-modify-playback-state "
                    "user-read-playback-state"
                ),
            }
        )

    assert config.granted_scope == (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    config.save.assert_called_once()


def test_ensure_auth_reauths_when_scope_is_stale():
    app, config, _ = _make_app()
    config.client_id = "client"
    config.refresh_token = "existing_refresh"
    config.granted_scope = "user-read-currently-playing"
    config.token_expires_at = 9_999_999_999

    with (
        patch(
            "src.main.run_oauth_flow",
            return_value={
                "access_token": "access",
                "expires_in": 3600,
                "scope": (
                    "user-read-currently-playing user-modify-playback-state "
                    "user-read-playback-state"
                ),
            },
        ) as oauth,
        patch("src.main.refresh_access_token") as refresh,
    ):
        assert app._ensure_auth() is True

    oauth.assert_called_once_with(config.client_id)
    refresh.assert_not_called()


def test_connect_signals_wires_playback_controls():
    app, _, widget = _make_app()
    app._playback = MagicMock()

    app._connect_signals()

    widget.prev_clicked.connect.assert_called_once_with(app._playback.previous)
    widget.next_clicked.connect.assert_called_once_with(app._playback.next)
    widget.play_pause_clicked.connect.assert_called_once_with(app._on_play_pause_clicked)


def test_play_pause_click_uses_latest_play_state():
    app, _, widget = _make_app()
    app._playback = MagicMock()
    app._is_playing = True

    app._on_play_pause_clicked()

    app._playback.toggle.assert_called_once_with(True)
    assert app._is_playing is False
    widget.set_playing.assert_called_with(False)


def test_state_sync_updates_widget_playing_icon():
    app, _, widget = _make_app()

    app._on_state_synced(1234, True, 10.0)

    assert app._is_playing is True
    widget.set_playing.assert_called_once_with(True)


# ---- V2.03 size presets ----


def test_app_applies_config_size_preset_on_init():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.granted_scope = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    config.size_preset = "small"
    widget = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        App()

    widget.apply_size_preset.assert_called_once_with("small")


def test_start_creates_tray_with_size_preset():
    app, config, _ = _make_app()
    config.client_id = "client"
    config.size_preset = "medium"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app.start()

    tray_class.assert_called_once()
    assert tray_class.call_args.kwargs["size_preset"] == "medium"
    assert tray_class.call_args.kwargs["on_size_changed"] == app._on_size_preset_changed


def test_size_preset_change_updates_widget_and_config():
    app, config, widget = _make_app()
    app._tray = MagicMock()
    widget.apply_size_preset.reset_mock()
    config.save.reset_mock()
    widget.size_preset = "small"

    app._on_size_preset_changed("small")

    widget.apply_size_preset.assert_called_once_with("small")
    assert config.size_preset == "small"
    config.save.assert_called_once()
    app._tray.set_size_preset.assert_called_once_with("small")
