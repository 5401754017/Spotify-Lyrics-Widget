import logging
import sys
import time

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox

from src.auth import SCOPES, has_required_scopes, is_token_expired, refresh_access_token
from src.auth_server import run_oauth_flow
from src.config import Config
from src.fonts import load_app_font
from src.logging_setup import configure_logging
from src.lyrics_worker import LyricsWorker, TrackInfo
from src.playback import PlaybackController
from src.spotify_worker import PlayerState, SpotifyWorker
from src.tray import TrayIcon
from src.widget import LyricsWidget


INSTANCE_SERVER_NAME = "spotify-lyrics-widget"


class SingleInstanceGuard:
    """Focus an existing widget instead of launching a second poller."""

    def __init__(self, server_name: str = INSTANCE_SERVER_NAME, on_activate=None):
        self._server_name = server_name
        self._on_activate = on_activate
        self._server: QLocalServer | None = None
        self._sockets = []

    def try_claim(self) -> bool:
        if self._notify_existing_instance():
            return False

        QLocalServer.removeServer(self._server_name)
        self._server = QLocalServer()
        self._server.newConnection.connect(self._handle_new_connection)
        return self._server.listen(self._server_name)

    def close(self):
        for socket in list(self._sockets):
            socket.disconnectFromServer()
            socket.deleteLater()
        self._sockets.clear()

        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        QLocalServer.removeServer(self._server_name)

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(100):
            socket.abort()
            return False

        socket.write(b"raise")
        socket.flush()
        socket.waitForBytesWritten(100)
        socket.disconnectFromServer()
        return True

    def _handle_new_connection(self):
        if self._server is None:
            return

        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._sockets.append(socket)
            self._activate(socket)

    def _activate(self, socket):
        socket.readAll()
        if self._on_activate is not None:
            self._on_activate()
        socket.disconnectFromServer()
        if socket in self._sockets:
            self._sockets.remove(socket)
        socket.deleteLater()


class App(QObject):
    """Main application controller for the V1 widget."""

    def __init__(self):
        super().__init__()
        self._config = Config()
        self._widget = LyricsWidget()
        self._spotify_worker = SpotifyWorker(self._config)
        self._lyrics_worker = LyricsWorker(netease_fallback=self._config.netease_fallback)
        self._playback = PlaybackController(self._config)
        self._current_track_id: str | None = None
        self._tray: TrayIcon | None = None
        self._last_heartbeat_ts: float = 0.0
        self._is_playing = False
        self._widget.apply_size_preset(self._config.size_preset)
        self._connect_lifecycle_signals()

    def _connect_lifecycle_signals(self):
        app = QApplication.instance()
        if app is not None:
            self._widget.close_requested.connect(app.quit)

    def start(self):
        if not self._config.client_id:
            client_id, ok = QInputDialog.getText(
                None,
                "Spotify Lyrics Widget",
                "Paste your Spotify App client_id:",
            )
            if not ok or not client_id.strip():
                QMessageBox.critical(None, "Error", "client_id is required.")
                sys.exit(1)
            self._config.client_id = client_id.strip()
            self._config.save()

        if not self._ensure_auth():
            sys.exit(1)

        self._connect_signals()
        self._widget.move(self._config.window_x, self._config.window_y)
        self._widget.show()
        app = QApplication.instance()
        self._tray = TrayIcon(
            on_toggle=self._toggle_widget,
            on_quit=app.quit if app is not None else (lambda: None),
            on_size_changed=self._on_size_preset_changed,
            size_preset=self._config.size_preset,
        )
        self._tray.show()
        self._widget.start_ui_timer()
        self._spotify_worker.start()

    def _ensure_auth(self) -> bool:
        scopes_ok = has_required_scopes(self._config.granted_scope, SCOPES)

        if (
            scopes_ok
            and self._config.refresh_token
            and not is_token_expired(self._config.token_expires_at)
        ):
            return True

        if scopes_ok and self._config.refresh_token:
            try:
                result = refresh_access_token(
                    self._config.refresh_token, self._config.client_id
                )
                self._apply_token_result(result)
                return True
            except Exception as error:
                logging.warning(
                    "Token pre-refresh failed: %s: %s; falling through to OAuth",
                    type(error).__name__, error,
                )

        try:
            self._apply_token_result(run_oauth_flow(self._config.client_id))
            return True
        except Exception as error:
            QMessageBox.critical(None, "Auth Failed", str(error))
            return False

    def _apply_token_result(self, result: dict):
        self._config.access_token = result["access_token"]
        self._config.token_expires_at = int(time.time()) + result["expires_in"]
        if "refresh_token" in result:
            self._config.refresh_token = result["refresh_token"]
        if "scope" in result:
            self._config.granted_scope = result["scope"]
        self._config.save()

    def _connect_signals(self):
        self._spotify_worker.track_changed.connect(self._on_track_changed)
        self._spotify_worker.state_synced.connect(self._on_state_synced)
        self._spotify_worker.playback_toggled.connect(self._on_playback_toggled)
        self._spotify_worker.not_a_track.connect(self._on_not_a_track)
        self._spotify_worker.not_playing.connect(self._on_not_playing)
        self._spotify_worker.auth_expired.connect(self._on_auth_expired)
        self._spotify_worker.network_error.connect(self._widget.show_offline)
        self._spotify_worker.network_recovered.connect(self._widget.hide_offline)
        self._spotify_worker.rate_limited.connect(self._widget.show_rate_limited)
        self._widget.prev_clicked.connect(self._playback.previous)
        self._widget.next_clicked.connect(self._playback.next)
        self._widget.play_pause_clicked.connect(self._on_play_pause_clicked)

        self._lyrics_worker.lyrics_ready.connect(self._on_lyrics_ready)
        self._lyrics_worker.no_lyrics.connect(self._on_no_lyrics)
        self._lyrics_worker.lyrics_unavailable.connect(self._on_lyrics_unavailable)

    @pyqtSlot(object)
    def _on_track_changed(self, state: PlayerState):
        logging.info(
            "UI slot _on_track_changed fired: track_id=%s track=%s",
            state.track_id,
            state.track_name,
        )
        self._current_track_id = state.track_id
        self._widget.update_track_info(state.track_name, state.artist_name)
        self._widget.set_duration(state.duration_ms)
        self._widget.set_lyric_text("")
        self._widget.set_lyrics([])  # drop the previous track's lyrics until new ones arrive
        logging.info(
            "UI label after update: track_label='%s' lyric_label='%s' visible=%s",
            self._widget._track_label.text(),
            self._widget._lyric_label.text(),
            self._widget.isVisible(),
        )

        self._lyrics_worker.request_lyrics(
            TrackInfo(
                track_id=state.track_id,
                track_name=state.track_name,
                artist_name=state.artist_name,
                album_name=state.album_name,
                duration_ms=state.duration_ms,
            )
        )

    @pyqtSlot(int, bool, float)
    def _on_state_synced(self, progress_ms: int, is_playing: bool, local_ts: float):
        now = time.monotonic()
        if now - self._last_heartbeat_ts > 30:
            logging.info("UI heartbeat alive: progress=%s is_playing=%s", progress_ms, is_playing)
            self._last_heartbeat_ts = now
        self._is_playing = is_playing
        self._widget.set_playing(is_playing)
        self._widget.resync_local_timer(progress_ms, is_playing, local_ts)

    @pyqtSlot(bool)
    def _on_playback_toggled(self, is_playing: bool):
        self._is_playing = is_playing
        self._widget.set_playing(is_playing)
        if not is_playing:
            self._widget.stop_ui_timer()

    @pyqtSlot()
    def _on_play_pause_clicked(self):
        self._playback.toggle(self._is_playing)

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
        self._spotify_worker.wait(2000)
        if self._ensure_auth():
            self._spotify_worker = SpotifyWorker(self._config)
            self._connect_signals()
            self._spotify_worker.start()

    def _on_size_preset_changed(self, preset: str):
        self._widget.apply_size_preset(preset)
        self._config.size_preset = self._widget.size_preset
        self._config.save()
        if self._tray is not None:
            self._tray.set_size_preset(self._widget.size_preset)

    def raise_window(self):
        self._widget.showNormal()
        self._widget.raise_()
        self._widget.activateWindow()

    def _toggle_widget(self):
        if self._widget.isVisible():
            self._widget.hide()
        else:
            self.raise_window()

    @pyqtSlot(str, list)
    def _on_lyrics_ready(self, track_id: str, lyrics: list):
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
        logging.info("App.shutdown called — event loop is exiting")
        if self._tray is not None:
            self._tray.hide()
        position = self._widget.pos()
        config = Config(config_dir=self._config.config_dir)
        config.window_x = position.x()
        config.window_y = position.y()
        config.size_preset = self._config.size_preset
        config.save()
        self._spotify_worker.stop()
        self._spotify_worker.wait(2000)
        if self._lyrics_worker.isRunning():
            self._lyrics_worker.wait(6000)


def main():
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Spotify Lyrics Widget")
    load_app_font()

    guard = None
    try:
        controller = App()
        guard = SingleInstanceGuard(on_activate=controller.raise_window)
        if not guard.try_claim():
            sys.exit(0)
            return
        controller.start()
    except Exception as error:
        logging.exception("Unhandled startup error")
        QMessageBox.critical(None, "Startup Failed", str(error))
        if guard is not None:
            guard.close()
        sys.exit(1)
        return

    app.aboutToQuit.connect(controller.shutdown)
    app.aboutToQuit.connect(guard.close)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
