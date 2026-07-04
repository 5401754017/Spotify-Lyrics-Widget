import logging
from unittest.mock import MagicMock, call, patch

import pytest
from PyQt6.QtWidgets import QDialog

import src.main as main_module
from src.main import App
from src.spotify_worker import PlayerState


def _make_controller_only_app():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.granted_scope = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    config.client_id = "existing-client"
    config.config_dir = "config-dir"
    config.netease_fallback = False
    config.size_preset = "large"
    config.language = "en"
    config.window_x = 100
    config.window_y = 200
    taskbar_host = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.TaskbarHostWindow", return_value=taskbar_host),
    ):
        app = App()

    return app, config


def _make_app():
    app, config = _make_controller_only_app()
    widget = MagicMock()
    app._widget = widget
    app._spotify_worker = MagicMock()
    app._lyrics_worker = MagicMock()
    return app, config, widget


def test_start_only_shows_controller_taskbar_entry():
    app, config = _make_controller_only_app()
    config.client_id = "client"

    app.start()

    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=False,
        is_visible=False,
    )
    app._taskbar_host.show_taskbar_entry.assert_called_once()
    assert app._widget is None
    assert app._tray is None
    assert app._spotify_worker is None
    assert app._lyrics_worker is None


def test_start_raises_controller_window_after_creating_taskbar_entry():
    app, _ = _make_controller_only_app()

    app.start()

    app._taskbar_host.show_taskbar_entry.assert_called_once()
    app._taskbar_host.showNormal.assert_called_once()
    app._taskbar_host.raise_.assert_called_once()
    app._taskbar_host.activateWindow.assert_called_once()


def test_start_missing_client_id_runs_first_run_setup():
    app, config = _make_controller_only_app()
    config.client_id = None
    app._ensure_auth = MagicMock(return_value=True)
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.client_id = "client-from-first-run"
    dialog.language = "zh_TW"

    with (
        patch("src.main.SpotifyOnboardingDialog", return_value=dialog) as dialog_class,
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
        patch("src.main.TrayIcon"),
    ):
        app.start()

    dialog_class.assert_called_once_with(main_module.REDIRECT_URI, language="en")
    assert config.client_id == "client-from-first-run"
    assert config.language == "zh_TW"
    config.save.assert_called_once()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()


def test_run_widget_missing_client_id_uses_onboarding_dialog():
    app, config = _make_controller_only_app()
    config.client_id = None
    app._ensure_auth = MagicMock(return_value=True)
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.client_id = "client-from-dialog"
    dialog.language = "zh_TW"

    with (
        patch("src.main.SpotifyOnboardingDialog", return_value=dialog) as dialog_class,
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
        patch("src.main.TrayIcon"),
    ):
        app._run_widget()

    dialog_class.assert_called_once_with(main_module.REDIRECT_URI, language="en")
    assert config.client_id == "client-from-dialog"
    assert config.language == "zh_TW"
    config.save.assert_called_once()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()


def test_run_widget_cancelled_onboarding_keeps_widget_stopped():
    app, config = _make_controller_only_app()
    config.client_id = None
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected

    with patch("src.main.SpotifyOnboardingDialog", return_value=dialog):
        app._run_widget()

    config.save.assert_not_called()
    assert app._widget is None
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=False,
        is_visible=False,
    )


def test_run_widget_existing_client_id_skips_onboarding_dialog():
    app, config = _make_controller_only_app()
    config.client_id = "existing-client"
    app._ensure_auth = MagicMock(return_value=True)

    with (
        patch("src.main.SpotifyOnboardingDialog") as dialog_class,
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
        patch("src.main.TrayIcon"),
    ):
        app._run_widget()

    dialog_class.assert_not_called()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()


def test_main_configures_logging_and_app_id_before_starting_qapplication():
    events = []

    with (
        patch("src.main.configure_logging", side_effect=lambda: events.append("log")),
        patch(
            "src.main.set_windows_app_user_model_id",
            side_effect=lambda: events.append("appid"),
        ),
        patch("src.main.QApplication", side_effect=lambda argv: events.append("qt") or MagicMock(exec=lambda: 0)),
        patch("src.main.build_app_icon"),
        patch("src.main.load_app_font"),
        patch("src.main.App"),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.sys.exit", side_effect=lambda code=0: events.append(("exit", code))),
    ):
        guard_class.return_value.try_claim.return_value = False
        main_module.main()

    assert events[:3] == ["log", "appid", "qt"]


def test_main_loads_font_before_building_app():
    events = []
    qapp = MagicMock(exec=lambda: 0)
    qapp.setApplicationName.side_effect = lambda name: events.append("name")

    with (
        patch("src.main.configure_logging"),
        patch("src.main.QApplication", return_value=qapp),
        patch("src.main.build_app_icon"),
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
        patch("src.main.build_app_icon"),
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


def test_main_single_instance_guard_activates_controller_window():
    qapp = MagicMock(exec=lambda: 0)
    controller = MagicMock()

    with (
        patch("src.main.configure_logging"),
        patch("src.main.QApplication", return_value=qapp),
        patch("src.main.build_app_icon"),
        patch("src.main.load_app_font"),
        patch("src.main.App", return_value=controller),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.sys.exit"),
    ):
        guard_class.return_value.try_claim.return_value = False
        main_module.main()

    guard_class.assert_called_once_with(on_activate=controller.show_controller)


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


def test_connect_widget_session_signals_wires_offline_indicator():
    app, _, widget = _make_app()

    app._connect_widget_session_signals()

    app._spotify_worker.network_error.connect.assert_called_once_with(
        widget.show_offline
    )
    app._spotify_worker.network_recovered.connect.assert_called_once_with(
        widget.hide_offline
    )


def test_connect_widget_session_signals_wires_rate_limit_state():
    app, _, widget = _make_app()

    app._connect_widget_session_signals()

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


def test_run_widget_creates_widget_session_and_marks_running_visible():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=True)
    widget = MagicMock()
    spotify_worker = MagicMock()
    lyrics_worker = MagicMock()

    with (
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=spotify_worker),
        patch("src.main.LyricsWorker", return_value=lyrics_worker),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app._run_widget()

    widget.apply_size_preset.assert_called_once_with("large")
    widget.move.assert_called_once_with(100, 200)
    widget.show.assert_called_once()
    tray_class.assert_called_once_with(
        on_toggle=app._toggle_widget,
        on_close_widget=app._close_widget,
    )
    tray_class.return_value.show.assert_called_once()
    spotify_worker.start.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=True,
    )


def test_run_widget_after_close_uses_position_saved_in_same_controller_session():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=True)
    first_widget = MagicMock()
    second_widget = MagicMock()
    fresh_config = MagicMock()
    first_widget.pos.return_value.x.return_value = 321
    first_widget.pos.return_value.y.return_value = 654

    with (
        patch("src.main.LyricsWidget", side_effect=[first_widget, second_widget]),
        patch("src.main.SpotifyWorker", side_effect=[MagicMock(), MagicMock()]),
        patch("src.main.LyricsWorker", side_effect=[MagicMock(), MagicMock()]),
        patch("src.main.TrayIcon"),
        patch("src.main.Config", return_value=fresh_config),
    ):
        app._run_widget()
        app._close_widget()
        app._run_widget()

    second_widget.move.assert_called_once_with(321, 654)


def test_run_widget_cancelled_auth_keeps_widget_stopped():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=False)

    app._run_widget()

    assert app._widget is None
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=False,
        is_visible=False,
    )


def test_show_widget_raises_running_widget():
    app, _, widget = _make_app()

    app._show_widget()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    widget.activateWindow.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=True,
    )


def test_hide_widget_only_hides_running_widget_and_keeps_tray():
    app, _, widget = _make_app()

    app._hide_widget()

    widget.hide.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=False,
    )


def test_toggle_widget_hides_when_visible():
    app, _, widget = _make_app()
    widget.isVisible.return_value = True

    app._toggle_widget()

    widget.hide.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=False,
    )


def test_toggle_widget_shows_when_hidden():
    app, _, widget = _make_app()
    widget.isVisible.return_value = False

    app._toggle_widget()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    widget.activateWindow.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=True,
    )


def test_widget_close_request_closes_widget_session():
    app, _, widget = _make_app()

    app._connect_widget_session_signals()

    widget.close_requested.connect.assert_called_once_with(app._close_widget)


def test_app_connects_taskbar_host_controls_to_widget_lifecycle():
    app, _ = _make_controller_only_app()
    taskbar_host = app._taskbar_host

    taskbar_host.show_widget_requested.connect.assert_called_once_with(
        app._show_widget
    )
    taskbar_host.hide_widget_requested.connect.assert_called_once_with(
        app._hide_widget
    )
    taskbar_host.run_widget_requested.connect.assert_called_once_with(
        app._run_widget
    )
    taskbar_host.close_widget_requested.connect.assert_called_once_with(
        app._close_widget
    )
    taskbar_host.controller_close_requested.connect.assert_called_once_with(
        app._close_controller
    )


def test_close_widget_stops_workers_hides_tray_and_keeps_controller():
    app, config = _make_controller_only_app()
    widget = MagicMock()
    spotify_worker = MagicMock()
    lyrics_worker = MagicMock()
    lyrics_worker.isRunning.return_value = True
    tray = MagicMock()
    fresh_config = MagicMock()
    widget.pos.return_value.x.return_value = 321
    widget.pos.return_value.y.return_value = 654
    app._widget = widget
    app._spotify_worker = spotify_worker
    app._lyrics_worker = lyrics_worker
    app._tray = tray

    with patch("src.main.Config", return_value=fresh_config):
        app._close_widget()

    tray.hide.assert_called_once()
    widget.hide.assert_called_once()
    spotify_worker.stop.assert_called_once()
    spotify_worker.wait.assert_called_once_with(2000)
    lyrics_worker.wait.assert_called_once_with(6000)
    assert fresh_config.window_x == 321
    assert fresh_config.window_y == 654
    assert fresh_config.size_preset == config.size_preset
    fresh_config.save.assert_called_once()
    app._taskbar_host.hide.assert_not_called()
    app._taskbar_host.set_widget_state.assert_has_calls(
        [
            call(is_running=True, is_visible=False, is_closing=True),
            call(is_running=False, is_visible=False),
        ]
    )
    assert app._widget is None
    assert app._tray is None


def test_close_widget_is_idempotent_when_stopped():
    app, _ = _make_controller_only_app()

    app._close_widget()

    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=False,
        is_visible=False,
    )


def test_close_controller_closes_widget_and_quits_qapplication():
    app, _ = _make_controller_only_app()
    app._close_widget = MagicMock()
    fake_qapp = MagicMock()

    with patch("src.main.QApplication.instance", return_value=fake_qapp):
        app._close_controller()

    app._close_widget.assert_called_once()
    app._taskbar_host.hide.assert_called_once()
    fake_qapp.quit.assert_called_once()


def test_show_controller_raises_taskbar_host_window():
    app, _ = _make_controller_only_app()

    app.show_controller()

    app._taskbar_host.showNormal.assert_called_once()
    app._taskbar_host.raise_.assert_called_once()
    app._taskbar_host.activateWindow.assert_called_once()


def test_shutdown_closes_widget_and_hides_taskbar_host():
    app, _ = _make_controller_only_app()
    app._close_widget = MagicMock()

    app.shutdown()

    app._close_widget.assert_called_once()
    app._taskbar_host.hide.assert_called_once()


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


def test_connect_widget_session_signals_wires_widget_hide_close_and_size_controls():
    app, _, widget = _make_app()

    app._connect_widget_session_signals()

    widget.hide_requested.connect.assert_called_once_with(app._toggle_widget)
    widget.close_requested.connect.assert_called_once_with(app._close_widget)
    widget.size_preset_requested.connect.assert_called_once_with(
        app._on_size_preset_changed
    )


def test_state_sync_resyncs_widget_timer_without_playing_icon():
    app, _, widget = _make_app()

    app._on_state_synced(1234, True, 10.0)

    assert app._is_playing is True
    widget.resync_local_timer.assert_called_once_with(1234, True, 10.0)
    widget.set_playing.assert_not_called()


# ---- V2.03 size presets ----


def test_run_widget_applies_config_size_preset():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    config.size_preset = "small"
    app._ensure_auth = MagicMock(return_value=True)
    widget = MagicMock()

    with (
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
        patch("src.main.TrayIcon"),
    ):
        app._run_widget()

    widget.apply_size_preset.assert_called_once_with("small")


def test_run_widget_creates_tray_without_size_menu_wiring():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    config.size_preset = "medium"
    app._ensure_auth = MagicMock(return_value=True)

    with (
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app._run_widget()

    tray_class.assert_called_once()
    assert "size_preset" not in tray_class.call_args.kwargs
    assert "on_size_changed" not in tray_class.call_args.kwargs


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
    app._tray.set_size_preset.assert_not_called()
