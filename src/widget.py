import ctypes
from dataclasses import dataclass
import logging
import math
import sys
import time

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCloseEvent,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.fonts import app_font_family
from src.lyric_clamp import clamp_lyric_text
from src.lrc_parser import find_current_line, should_blank_incomplete_tail
from src.marquee import MarqueeLabel


PANEL_BACKGROUND = "#121212"
WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_GRAY = "#282828"

MUSIC_NOTE = "♪"  # lyrics loaded but none to show now (intro/outro/incomplete tail)

UI_TIMER_INTERVAL_MS = 150
WIDGET_WIDTH = 420
WIDGET_HEIGHT = 112
TOP_ROW_HEIGHT = 24
LYRIC_LANE_HEIGHT = 56
CONTROL_SLOT_WIDTH = 12
CONTROL_SLOT_HEIGHT = 12
CONTROL_GAP = 2
HOVER_CONTROL_COUNT = 3
TOP_ROW_RIGHT_RESERVE = (
    CONTROL_SLOT_WIDTH * HOVER_CONTROL_COUNT
    + CONTROL_GAP * (HOVER_CONTROL_COUNT - 1)
)
CORNER_RADIUS = 12


@dataclass(frozen=True)
class WidgetSizePreset:
    name: str
    width: int
    height: int
    top_padding: int
    top_row_height: int
    gap_after_top: int
    lyric_lane_height: int
    gap_after_lyric: int
    progress_height: int
    bottom_padding: int
    left_margin: int
    title_width: int
    title_control_gap: int
    control_width: int
    control_height: int
    control_gap: int
    right_margin: int
    title_font_pt: int
    lyric_font_pt: int
    lyric_lines: int
    control_font_px: int


SIZE_PRESETS = {
    "small": WidgetSizePreset(
        "small",
        300,
        74,
        6,
        18,
        2,
        41,
        2,
        1,
        4,
        10,
        204,
        40,
        12,
        12,
        2,
        6,
        8,
        10,
        2,
        12,
    ),
    "medium": WidgetSizePreset(
        "medium",
        360,
        90,
        8,
        21,
        4,
        48,
        3,
        1,
        5,
        13,
        242,
        40,
        12,
        12,
        2,
        9,
        9,
        13,
        2,
        13,
    ),
    "large": WidgetSizePreset(
        "large",
        420,
        112,
        12,
        24,
        5,
        56,
        5,
        2,
        8,
        16,
        288,
        40,
        12,
        12,
        2,
        10,
        10,
        16,
        2,
        14,
    ),
}
DEFAULT_SIZE_PRESET = "large"

# Windows 11 DWM rounded-corner experiment (DwmSetWindowAttribute)
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_ROUND = 2
_DWMWA_BORDER_COLOR = 34
# Spotify green (#1DB954) as a Win32 COLORREF (0x00BBGGRR)
_DWM_BORDER_COLOR = 0x0054B91D


class HoverIconButton(QPushButton):
    def __init__(self, icon_name: str, parent=None, icon_fill_ratio: float = 0.86):
        super().__init__("", parent)
        self.icon_name = icon_name
        self.icon_fill_ratio = icon_fill_ratio
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVisible(False)

    def enterEvent(self, event: QEnterEvent):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(SPOTIFY_GREEN if self.underMouse() else WHITE)
        pen_width = max(1.3, min(self.width(), self.height()) * 0.08)
        painter.setPen(
            QPen(
                color,
                pen_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)

        side = min(self.width(), self.height())
        icon_side = side * self.icon_fill_ratio
        center = QPointF(self.width() / 2, self.height() / 2)

        if self.icon_name == "settings":
            self._paint_settings_icon(painter, center, icon_side)
        elif self.icon_name == "hide":
            half = icon_side * 0.42
            painter.drawLine(
                QPointF(center.x() - half, center.y()),
                QPointF(center.x() + half, center.y()),
            )
        elif self.icon_name == "close":
            half = icon_side * 0.36
            painter.drawLine(
                QPointF(center.x() - half, center.y() - half),
                QPointF(center.x() + half, center.y() + half),
            )
            painter.drawLine(
                QPointF(center.x() + half, center.y() - half),
                QPointF(center.x() - half, center.y() + half),
            )

    def _paint_settings_icon(self, painter: QPainter, center: QPointF, icon_side: float):
        color = painter.pen().color()
        outer_radius = icon_side * 0.48
        inner_tooth_radius = icon_side * 0.36
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)

        for index in range(16):
            angle = -math.pi / 2 + index * math.pi / 8
            radius = outer_radius if index % 2 == 0 else inner_tooth_radius
            point = QPointF(
                center.x() + math.cos(angle) * radius,
                center.y() + math.sin(angle) * radius,
            )
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()

        hole_radius = icon_side * 0.2
        path.addEllipse(
            QRectF(
                center.x() - hole_radius,
                center.y() - hole_radius,
                hole_radius * 2,
                hole_radius * 2,
            )
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)


class LyricsWidget(QWidget):
    """Frameless always-on-top floating lyrics widget."""

    close_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    size_preset_requested = pyqtSignal(str)

    _UNSET = -3  # _current_line_idx sentinel: fresh lyrics, force first paint
    _TAIL_BLANKED = -2  # _current_line_idx sentinel: past an incomplete source's end

    def __init__(self):
        super().__init__()
        self._size_preset_name = DEFAULT_SIZE_PRESET
        self._max_lyric_visual_lines = SIZE_PRESETS[DEFAULT_SIZE_PRESET].lyric_lines
        self._setup_window()
        self._setup_ui()
        self._setup_timer()

        self._lyrics: list[tuple[int, str]] = []
        self._current_line_idx = self._UNSET
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

        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(16, 12, 16, 8)
        self._panel_layout.setSpacing(5)
        outer_layout.addWidget(self._panel)
        self.setLayout(outer_layout)

        self._top_row = QWidget(self._panel)
        self._top_row.setFixedHeight(TOP_ROW_HEIGHT)
        self._top_row_layout = QHBoxLayout(self._top_row)
        self._top_row_layout.setContentsMargins(0, 0, TOP_ROW_RIGHT_RESERVE, 0)
        self._top_row_layout.setSpacing(0)
        self._track_label = MarqueeLabel("")
        self._track_label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
        self._track_label.setStyleSheet(f"color: {WHITE};")
        track_palette = self._track_label.palette()
        track_palette.setColor(QPalette.ColorRole.WindowText, QColor(WHITE))
        self._track_label.setPalette(track_palette)
        self._track_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._top_row_layout.addWidget(self._track_label, stretch=1)

        def make_control_button(icon_name: str) -> HoverIconButton:
            return HoverIconButton(icon_name, self._panel)

        self._settings_btn = make_control_button("settings")
        self._hide_btn = make_control_button("hide")
        self._close_btn = make_control_button("close")

        self._size_menu = QMenu(self)
        for label, value in (("Small", "small"), ("Medium", "medium"), ("Large", "large")):
            action = self._size_menu.addAction(label)
            action.setData(value)
            action.triggered.connect(
                lambda checked=False, preset=value: self.size_preset_requested.emit(
                    preset
                )
            )

        self._settings_btn.clicked.connect(
            lambda checked=False: self._size_menu.popup(
                self._settings_btn.mapToGlobal(self._settings_btn.rect().bottomLeft())
            )
        )
        self._hide_btn.clicked.connect(self.hide_requested.emit)
        self._close_btn.clicked.connect(self.close)
        self._panel_layout.addWidget(self._top_row)

        self._lyric_label = QLabel("")
        self._lyric_label.setFont(QFont(app_font_family(), 16, QFont.Weight.Bold))
        self._lyric_label.setStyleSheet(f"color: {SPOTIFY_GREEN};")
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        self._lyric_label.setFixedHeight(LYRIC_LANE_HEIGHT)
        self._panel_layout.addWidget(self._lyric_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(2)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {DARK_GRAY}; border: none; }}"
            f"QProgressBar::chunk {{ background-color: {SPOTIFY_GREEN}; }}"
        )
        self._panel_layout.addWidget(self._progress_bar)
        self.apply_size_preset(DEFAULT_SIZE_PRESET)

    def _setup_timer(self):
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(UI_TIMER_INTERVAL_MS)
        self._ui_timer.timeout.connect(self._on_ui_tick)

    @property
    def size_preset(self) -> str:
        return self._size_preset_name

    def apply_size_preset(self, name: str):
        preset = SIZE_PRESETS.get(name, SIZE_PRESETS[DEFAULT_SIZE_PRESET])
        self._size_preset_name = preset.name
        self._max_lyric_visual_lines = preset.lyric_lines

        self._panel_layout.setContentsMargins(
            preset.left_margin,
            preset.top_padding,
            preset.right_margin,
            preset.bottom_padding,
        )
        self._panel_layout.setSpacing(preset.gap_after_top)
        self._top_row.setFixedHeight(preset.top_row_height)

        top_row_right_reserve = (
            preset.title_control_gap
            + preset.control_width * HOVER_CONTROL_COUNT
            + preset.control_gap * (HOVER_CONTROL_COUNT - 1)
        )
        self._top_row_layout.setContentsMargins(0, 0, top_row_right_reserve, 0)

        self._track_label.setFont(
            QFont(app_font_family(), preset.title_font_pt, QFont.Weight.DemiBold)
        )
        self._lyric_label.setFont(
            QFont(app_font_family(), preset.lyric_font_pt, QFont.Weight.Bold)
        )
        self._lyric_label.setFixedHeight(preset.lyric_lane_height)
        self._progress_bar.setFixedHeight(preset.progress_height)
        control_style = (
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; "
            f"font-size: {preset.control_font_px}px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        for button in (self._settings_btn, self._hide_btn, self._close_btn):
            button.setFixedSize(preset.control_width, preset.control_height)
            button.setStyleSheet(control_style)
        self._panel_layout.activate()
        self._top_row_layout.activate()
        self.setFixedSize(preset.width, preset.height)
        self._position_overlay_controls()
        self.set_lyric_text(self._lyric_label.text())

    def start_ui_timer(self):
        self._ui_timer.start()

    def stop_ui_timer(self):
        self._ui_timer.stop()

    def update_track_info(self, track_name: str, artist_name: str):
        self._track_text_full = f"{track_name} — {artist_name}"
        self._track_label.setText(self._track_text_full)

    def set_lyrics(self, lyrics: list[tuple[int, str]]):
        self._lyrics = lyrics
        self._current_line_idx = self._UNSET
        if not self._is_playing:
            self._update_lyric_display(self._last_synced_ms)

    def set_lyric_text(self, text: str):
        width = max(self._lyric_label.width(), self.width() - 32, 1)
        text = clamp_lyric_text(
            text,
            self._lyric_label.font(),
            width,
            max_lines=self._max_lyric_visual_lines,
        )
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
            self._ui_timer.stop()
            self._update_lyric_display(progress_ms)

    def show_no_lyrics(self):
        self._lyrics = []
        self._lyric_label.setText("no synced lyrics")

    def show_not_playing(self):
        self._ui_timer.stop()
        self._lyrics = []
        self._lyric_label.setText("not playing")
        self.update_progress(0)

    def show_not_a_track(self):
        self._ui_timer.stop()
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
        if not hasattr(self, "_close_btn"):
            return

        preset = SIZE_PRESETS.get(
            self._size_preset_name,
            SIZE_PRESETS[DEFAULT_SIZE_PRESET],
        )
        title_right = self._track_label.mapTo(
            self._panel,
            self._track_label.rect().topRight(),
        ).x()
        x = title_right + preset.title_control_gap + 1
        y = preset.top_padding
        self._settings_btn.move(x, y)
        self._hide_btn.move(x + preset.control_width + preset.control_gap, y)
        self._close_btn.move(
            x + (preset.control_width + preset.control_gap) * 2,
            y,
        )

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
        if should_blank_incomplete_tail(progress_ms, self._lyrics, self._duration_ms):
            if self._current_line_idx == self._TAIL_BLANKED:
                return
            self._current_line_idx = self._TAIL_BLANKED
            self._lyric_label.setText(MUSIC_NOTE)
            return

        index = find_current_line(self._lyrics, progress_ms)
        if index == self._current_line_idx:
            return

        self._current_line_idx = index
        if index >= 0:
            self.set_lyric_text(self._lyrics[index][1])
        elif self._lyrics:
            self._lyric_label.setText(MUSIC_NOTE)  # lyrics loaded, before the first line
        else:
            self._lyric_label.setText("")

    def _on_enter_hover(self):
        self._settings_btn.setVisible(True)
        self._hide_btn.setVisible(True)
        self._close_btn.setVisible(True)
        self._track_label.start_marquee()

    def _on_leave_hover(self):
        if self.underMouse():
            return
        self._settings_btn.setVisible(False)
        self._hide_btn.setVisible(False)
        self._close_btn.setVisible(False)
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
