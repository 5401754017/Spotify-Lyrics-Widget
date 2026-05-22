import sys
import time

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox

from src.auth import is_token_expired, refresh_access_token
from src.auth_server import run_oauth_flow
from src.config import Config
from src.lyrics_worker import LyricsWorker, TrackInfo
from src.spotify_worker import PlayerState, SpotifyWorker
from src.widget import LyricsWidget


class App(QObject):
    """Main application controller for the V1 widget."""

    def __init__(self):
        super().__init__()
        self._config = Config()
        self._widget = LyricsWidget()
        self._spotify_worker = SpotifyWorker(self._config)
        self._lyrics_worker = LyricsWorker()
        self._current_track_id: str | None = None

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
        self._widget.start_ui_timer()
        self._spotify_worker.start()

    def _ensure_auth(self) -> bool:
        if self._config.refresh_token and not is_token_expired(
            self._config.token_expires_at
        ):
            return True

        if self._config.refresh_token:
            try:
                result = refresh_access_token(
                    self._config.refresh_token, self._config.client_id
                )
                self._apply_token_result(result)
                return True
            except Exception:
                pass

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
        self._config.save()

    def _connect_signals(self):
        self._spotify_worker.track_changed.connect(self._on_track_changed)
        self._spotify_worker.state_synced.connect(self._on_state_synced)
        self._spotify_worker.playback_toggled.connect(self._on_playback_toggled)
        self._spotify_worker.not_a_track.connect(self._on_not_a_track)
        self._spotify_worker.not_playing.connect(self._on_not_playing)
        self._spotify_worker.auth_expired.connect(self._on_auth_expired)

        self._lyrics_worker.lyrics_ready.connect(self._on_lyrics_ready)
        self._lyrics_worker.no_lyrics.connect(self._on_no_lyrics)
        self._lyrics_worker.lyrics_unavailable.connect(self._on_lyrics_unavailable)

    @pyqtSlot(object)
    def _on_track_changed(self, state: PlayerState):
        self._current_track_id = state.track_id
        self._widget.update_track_info(state.track_name, state.artist_name)
        self._widget.set_duration(state.duration_ms)
        self._widget.set_lyric_text("")

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
        self._spotify_worker.wait(2000)
        if self._ensure_auth():
            self._spotify_worker = SpotifyWorker(self._config)
            self._connect_signals()
            self._spotify_worker.start()

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
        position = self._widget.pos()
        self._config.window_x = position.x()
        self._config.window_y = position.y()
        self._config.save()
        self._spotify_worker.stop()
        self._spotify_worker.wait(2000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Spotify Lyrics Widget")

    controller = App()
    controller.start()
    app.aboutToQuit.connect(controller.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
