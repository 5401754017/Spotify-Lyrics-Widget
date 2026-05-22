import time

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QEnterEvent, QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.lrc_parser import find_current_line


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

        self._lyrics: list[tuple[int, str]] = []
        self._current_line_idx = -1
        self._last_synced_ms = 0
        self._last_sync_time = 0.0
        self._is_playing = False
        self._duration_ms = 0
        self._drag_pos: QPoint | None = None

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(420)
        self.setStyleSheet(f"background-color: {BLACK};")
        self.setMouseTracking(True)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 10, 16, 0)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        self._track_label = QLabel("")
        self._track_label.setFont(QFont("Segoe UI", 9))
        self._track_label.setStyleSheet(f"color: {WHITE};")
        self._track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._track_label, stretch=1)

        self._close_btn = QPushButton("x")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
        top_row.addWidget(self._close_btn)
        layout.addLayout(top_row)

        self._lyric_label = QLabel("")
        self._lyric_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._lyric_label.setStyleSheet(f"color: {SPOTIFY_GREEN};")
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        self._lyric_label.setMinimumHeight(40)
        layout.addWidget(self._lyric_label)

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

    def update_track_info(self, track_name: str, artist_name: str):
        self._track_label.setText(f"{track_name} - {artist_name}")

    def set_lyrics(self, lyrics: list[tuple[int, str]]):
        self._lyrics = lyrics
        self._current_line_idx = -1

    def set_lyric_text(self, text: str):
        self._lyric_label.setText(text)

    def set_duration(self, duration_ms: int):
        self._duration_ms = duration_ms

    def update_progress(self, ratio: float):
        self._progress_bar.setValue(int(ratio * 100))

    def resync_local_timer(
        self, progress_ms: int, is_playing: bool, local_timestamp: float
    ):
        self._last_synced_ms = progress_ms
        self._last_sync_time = local_timestamp
        self._is_playing = is_playing
        if is_playing and not self._ui_timer.isActive():
            self._ui_timer.start()
        elif not is_playing:
            self._update_lyric_display(progress_ms)

    def show_no_lyrics(self):
        self._lyrics = []
        self._lyric_label.setText("no synced lyrics")

    def show_not_playing(self):
        self._lyrics = []
        self._lyric_label.setText("not playing")
        self.update_progress(0)

    def show_not_a_track(self):
        self._lyrics = []
        self._lyric_label.setText("not a track")

    def show_unavailable(self):
        self._lyrics = []
        self._lyric_label.setText("lyrics unavailable")

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
        index = find_current_line(self._lyrics, progress_ms)
        if index == self._current_line_idx:
            return

        self._current_line_idx = index
        if index >= 0:
            self._lyric_label.setText(self._lyrics[index][1])
        else:
            self._lyric_label.setText("")

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
