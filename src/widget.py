import time

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainterPath,
    QRegion,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.fonts import app_font_family
from src.lrc_parser import find_current_line


PANEL_BACKGROUND = "#121212"
WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_GRAY = "#282828"

UI_TIMER_INTERVAL_MS = 150
WIDGET_WIDTH = 420
WIDGET_HEIGHT = 112
TOP_ROW_HEIGHT = 20
LYRIC_LANE_HEIGHT = 60
OVERLAY_GUTTER_WIDTH = 92
CORNER_RADIUS = 12


class LyricsWidget(QWidget):
    """Frameless always-on-top floating lyrics widget."""

    close_requested = pyqtSignal()

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
        self._track_text_full = ""
        self._drag_pos: QPoint | None = None

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self._apply_window_mask()
        self.setMouseTracking(True)

    def _apply_window_mask(self):
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            CORNER_RADIUS,
            CORNER_RADIUS,
        )
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _setup_ui(self):
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._panel = QFrame(self)
        self._panel.setObjectName("lyricsPanel")
        self._panel.setMouseTracking(True)
        self._panel.setStyleSheet(
            f"#lyricsPanel {{ background-color: {PANEL_BACKGROUND}; "
            f"border: 1px solid {SPOTIFY_GREEN}; border-radius: 12px; }}"
        )

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(5)
        outer_layout.addWidget(self._panel)
        self.setLayout(outer_layout)

        self._top_row = QWidget(self._panel)
        self._top_row.setFixedHeight(TOP_ROW_HEIGHT)
        top_row = QHBoxLayout(self._top_row)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        self._track_label = QLabel("")
        self._track_label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
        self._track_label.setStyleSheet(f"color: {WHITE};")
        self._track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._track_label, stretch=1)
        top_row.addSpacing(OVERLAY_GUTTER_WIDTH)

        self._close_btn = QPushButton("✕", self._panel)
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
        layout.addWidget(self._top_row)

        self._lyric_label = QLabel("")
        self._lyric_label.setFont(QFont(app_font_family(), 16, QFont.Weight.Bold))
        self._lyric_label.setStyleSheet(f"color: {SPOTIFY_GREEN};")
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        self._lyric_label.setFixedHeight(LYRIC_LANE_HEIGHT)
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
        self._position_overlay_controls()

    def _setup_timer(self):
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(UI_TIMER_INTERVAL_MS)
        self._ui_timer.timeout.connect(self._on_ui_tick)

    def start_ui_timer(self):
        self._ui_timer.start()

    def stop_ui_timer(self):
        self._ui_timer.stop()

    def update_track_info(self, track_name: str, artist_name: str):
        self._track_text_full = f"{track_name} — {artist_name}"
        self._refresh_track_label_text()

    def set_lyrics(self, lyrics: list[tuple[int, str]]):
        self._lyrics = lyrics
        self._current_line_idx = -1

    def set_lyric_text(self, text: str):
        lines = text.splitlines()
        if len(lines) > 2:
            text = "\n".join(lines[:2])
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

    def show_rate_limited(self, retry_after_seconds: int):
        self._lyrics = []
        self._lyric_label.setText(
            f"rate limited - retrying in {retry_after_seconds}s"
        )

    def show_offline(self):
        self._lyrics = []
        self._lyric_label.setText("offline")

    def hide_offline(self):
        if self._lyric_label.text() == "offline":
            self._lyric_label.setText("")

    def _position_overlay_controls(self):
        if hasattr(self, "_close_btn"):
            panel_width = max(self._panel.width(), self.width())
            self._close_btn.move(panel_width - 30, 8)

    def _refresh_track_label_text(self):
        if not self._track_text_full:
            self._track_label.setText("")
            return

        width = max(
            self._track_label.width(),
            self.width() - 32 - OVERLAY_GUTTER_WIDTH,
            1,
        )
        text = self._track_label.fontMetrics().elidedText(
            self._track_text_full,
            Qt.TextElideMode.ElideRight,
            width,
        )
        if text.endswith("…"):
            text = f"{text[:-1]}..."
        self._track_label.setText(text)

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
            self.set_lyric_text(self._lyrics[index][1])
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

    def showEvent(self, event):
        self._position_overlay_controls()
        self._refresh_track_label_text()
        super().showEvent(event)

    def resizeEvent(self, event):
        self._apply_window_mask()
        self._position_overlay_controls()
        self._refresh_track_label_text()
        super().resizeEvent(event)

    def closeEvent(self, event: QCloseEvent):
        self.close_requested.emit()
        super().closeEvent(event)

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
