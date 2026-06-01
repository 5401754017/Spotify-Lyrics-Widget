import ctypes
import logging
import sys
import time

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCloseEvent,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPalette,
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
from src.marquee import MarqueeLabel
from src.transport_button import TransportButton


PANEL_BACKGROUND = "#121212"
WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_GRAY = "#282828"

UI_TIMER_INTERVAL_MS = 150
WIDGET_WIDTH = 420
WIDGET_HEIGHT = 112
TOP_ROW_HEIGHT = 24
LYRIC_LANE_HEIGHT = 56
CONTROLS_CLUSTER_WIDTH = 72
CONTROLS_CLUSTER_HEIGHT = 24
CLOSE_SLOT_WIDTH = 28
CORNER_RADIUS = 12

# Windows 11 DWM rounded-corner experiment (DwmSetWindowAttribute)
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_ROUND = 2
_DWMWA_BORDER_COLOR = 34
# Spotify green (#1DB954) as a Win32 COLORREF (0x00BBGGRR)
_DWM_BORDER_COLOR = 0x0054B91D


class LyricsWidget(QWidget):
    """Frameless always-on-top floating lyrics widget."""

    close_requested = pyqtSignal()
    prev_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()

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
        # Opaque window background; corners are rounded by the DWM (see showEvent)
        # instead of a jagged 1-bit QRegion mask.
        self.setStyleSheet(f"LyricsWidget {{ background-color: {PANEL_BACKGROUND}; }}")
        self.setMouseTracking(True)

    def _apply_dwm_rounding(self):
        """Ask the Windows 11 DWM to round the window corners (anti-aliased).

        Experiment replacing the jagged QRegion mask. If the frameless window
        does not honor it, corners stay square — that is the failure signal.
        """
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            corner = ctypes.c_int(_DWMWCP_ROUND)
            hr1 = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                _DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner),
                ctypes.sizeof(corner),
            )
            # The single green frame is the DWM system border; the panel draws
            # no border of its own, so this hugs the rounded corner exactly.
            border = ctypes.c_uint(_DWM_BORDER_COLOR)
            hr2 = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                _DWMWA_BORDER_COLOR,
                ctypes.byref(border),
                ctypes.sizeof(border),
            )
            logging.info(
                "DWM round hr=0x%08x, border-color hr=0x%08x",
                hr1 & 0xFFFFFFFF,
                hr2 & 0xFFFFFFFF,
            )
        except Exception as exc:
            logging.warning("DWM attribute request failed: %s", exc)

    def _setup_ui(self):
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._panel = QFrame(self)
        self._panel.setObjectName("lyricsPanel")
        self._panel.setMouseTracking(True)
        # No panel border/radius: the green frame and rounded corners are both
        # drawn by the DWM on the window itself (see _apply_dwm_rounding).
        self._panel.setStyleSheet(
            f"#lyricsPanel {{ background-color: {PANEL_BACKGROUND}; }}"
        )

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(5)
        outer_layout.addWidget(self._panel)
        self.setLayout(outer_layout)

        self._top_row = QWidget(self._panel)
        self._top_row.setFixedHeight(TOP_ROW_HEIGHT)
        top_row = QHBoxLayout(self._top_row)
        top_row.setContentsMargins(0, 0, CLOSE_SLOT_WIDTH, 0)
        top_row.setSpacing(0)
        self._track_label = MarqueeLabel("")
        self._track_label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
        self._track_label.setStyleSheet(f"color: {WHITE};")
        track_palette = self._track_label.palette()
        track_palette.setColor(QPalette.ColorRole.WindowText, QColor(WHITE))
        self._track_label.setPalette(track_palette)
        self._track_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        top_row.addWidget(self._track_label, stretch=1)

        self._close_btn = QPushButton("✕", self._panel)
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
        layout.addWidget(self._top_row)

        self._controls_cluster = QWidget(self._panel)
        self._controls_cluster.setFixedSize(
            CONTROLS_CLUSTER_WIDTH, CONTROLS_CLUSTER_HEIGHT
        )
        self._controls_cluster.setMouseTracking(True)
        controls_layout = QHBoxLayout(self._controls_cluster)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self._prev_btn = TransportButton("previous", self._controls_cluster)
        self._play_pause_btn = TransportButton("play", self._controls_cluster)
        self._next_btn = TransportButton("next", self._controls_cluster)
        controls_layout.addWidget(self._prev_btn)
        controls_layout.addWidget(self._play_pause_btn)
        controls_layout.addWidget(self._next_btn)

        self._prev_btn.clicked.connect(self.prev_clicked)
        self._play_pause_btn.clicked.connect(self.play_pause_clicked)
        self._next_btn.clicked.connect(self.next_clicked)
        self._controls_cluster.setVisible(False)

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
        self._track_label.setText(self._track_text_full)

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
            self._controls_cluster.move(
                (panel_width - CONTROLS_CLUSTER_WIDTH) // 2,
                8,
            )

    def set_playing(self, is_playing: bool):
        self._play_pause_btn.set_mode("pause" if is_playing else "play")

    def _refresh_track_label_text(self):
        self._track_label.update()

    def _on_ui_tick(self):
        if not self._is_playing:
            return

        estimated_ms = self._last_synced_ms + int(
            (time.monotonic() - self._last_sync_time) * 1000
        )
        # Progress depends only on playback, never on lyrics availability.
        if self._duration_ms > 0:
            self.update_progress(min(estimated_ms / self._duration_ms, 1.0))
        # Lyric line only advances when this track actually has synced lyrics;
        # otherwise the lyric lane keeps its status text (no lyrics / unavailable).
        if self._lyrics:
            self._update_lyric_display(estimated_ms)

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
        self._controls_cluster.setVisible(True)
        self._track_label.start_marquee()

    def _on_leave_hover(self):
        if self.underMouse():
            return
        self._close_btn.setVisible(False)
        self._controls_cluster.setVisible(False)
        self._track_label.stop_marquee()

    def enterEvent(self, event: QEnterEvent):
        self._on_enter_hover()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._on_leave_hover()
        super().leaveEvent(event)

    def showEvent(self, event):
        self._apply_dwm_rounding()
        self._position_overlay_controls()
        self._refresh_track_label_text()
        super().showEvent(event)

    def resizeEvent(self, event):
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
