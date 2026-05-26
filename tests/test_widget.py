import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QFont

from src.widget import LyricsWidget


def test_widget_creates_without_crash(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    assert widget.isVisible() is False


def test_widget_flags(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    flags = widget.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_widget_uses_rounded_mask_and_rounded_panel(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert not widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert not widget.mask().isEmpty()
    assert widget._panel.objectName() == "lyricsPanel"

    panel_style = widget._panel.styleSheet()
    assert "background-color: #121212" in panel_style
    assert "border: 1px solid #1DB954" in panel_style
    assert "border-radius: 12px" in panel_style


def test_track_label_font_is_larger_and_demibold(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    font = widget._track_label.font()
    assert font.pointSize() >= 10
    assert font.weight() >= QFont.Weight.DemiBold.value


def test_update_track_info(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.update_track_info("Test Song", "Test Artist")
    assert "Test Song" in widget._track_label.text()
    assert "Test Artist" in widget._track_label.text()


def test_long_track_info_elides_without_resizing_widget(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(50)
    initial_width = widget.width()

    widget.update_track_info(
        "This Is An Extremely Long Track Name That Should Not Fit In The Widget",
        "An Extremely Long Artist Name That Should Also Be Elided",
    )
    qtbot.wait(50)

    assert widget.width() == initial_width
    assert widget._track_label.text().endswith("...")


def test_widget_height_stays_fixed_for_one_two_and_long_lyrics(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(50)
    initial_height = widget.height()
    initial_progress_y = widget._progress_bar.y()

    widget.set_lyric_text("one line")
    qtbot.wait(50)
    one_line_height = widget.height()

    widget.set_lyric_text("first line\nsecond line")
    qtbot.wait(50)
    two_line_height = widget.height()

    widget.set_lyric_text("first line\nsecond line\nthird line")
    qtbot.wait(50)

    assert one_line_height == initial_height
    assert two_line_height == initial_height
    assert widget.height() == initial_height
    assert widget._progress_bar.y() == initial_progress_y


def test_lyric_label_lane_fits_exactly_two_lines(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    line_height = widget._lyric_label.fontMetrics().lineSpacing()

    assert widget._lyric_label.minimumHeight() >= line_height * 2
    assert widget._lyric_label.maximumHeight() == widget._lyric_label.minimumHeight()


def test_show_event_refreshes_overlay_and_elided_title(qtbot, monkeypatch):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    calls = []

    def record_refresh():
        calls.append("refresh")

    def record_position():
        calls.append("position")

    monkeypatch.setattr(widget, "_refresh_track_label_text", record_refresh)
    monkeypatch.setattr(widget, "_position_overlay_controls", record_position)

    widget.show()
    qtbot.wait(50)

    assert "refresh" in calls
    assert "position" in calls


def test_force_visual_refresh_repaints_now_and_after_event_loop(qtbot, monkeypatch):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    calls = []

    monkeypatch.setattr(widget, "_repaint_visual_tree", lambda: calls.append("refresh"))

    widget.force_visual_refresh()

    assert calls == ["refresh"]
    qtbot.waitUntil(lambda: calls == ["refresh", "refresh"], timeout=500)


def test_visual_refresh_includes_labels_panel_and_window(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    refresh_targets = widget._visual_refresh_widgets()

    assert widget._track_label in refresh_targets
    assert widget._lyric_label in refresh_targets
    assert widget._progress_bar in refresh_targets
    assert widget._panel in refresh_targets
    assert widget in refresh_targets


def test_update_lyric_line(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_lyric_text("Hello world")
    assert widget._lyric_label.text() == "Hello world"


def test_update_progress_bar(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.update_progress(0.5)
    assert widget._progress_bar.value() == 50


def test_show_no_lyrics_state(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show_no_lyrics()
    assert widget._lyric_label.text() != ""


def test_show_not_playing_state(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show_not_playing()
    assert widget._lyric_label.text() != ""


def test_close_button_visible_on_hover(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget._on_enter_hover()
    assert widget._close_btn.isVisible()
    widget._on_leave_hover()
    assert not widget._close_btn.isVisible()


def test_close_event_emits_close_requested(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    signals = []
    widget.close_requested.connect(lambda: signals.append("close"))

    widget.closeEvent(QCloseEvent())

    assert signals == ["close"]


def _shown_widget(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.update_track_info("Stable Song", "Stable Artist")
    widget.set_lyric_text("Stable lyric")
    widget.show()
    qtbot.wait(50)
    return widget


def test_hover_does_not_move_track_label(qtbot):
    widget = _shown_widget(qtbot)

    before = widget._track_label.geometry()
    widget._on_enter_hover()
    qtbot.wait(50)
    after_enter = widget._track_label.geometry()
    widget._on_leave_hover()
    qtbot.wait(50)
    after_leave = widget._track_label.geometry()

    assert after_enter == before
    assert after_leave == before


def test_hover_does_not_move_lyric_label(qtbot):
    widget = _shown_widget(qtbot)

    before = widget._lyric_label.geometry()
    widget._on_enter_hover()
    qtbot.wait(50)
    after_enter = widget._lyric_label.geometry()
    widget._on_leave_hover()
    qtbot.wait(50)
    after_leave = widget._lyric_label.geometry()

    assert after_enter == before
    assert after_leave == before


def test_resync_local_timer(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_lyrics([(5000, "Line 1"), (10000, "Line 2")])
    widget.resync_local_timer(7000, True, time.monotonic())
    assert widget._last_synced_ms == 7000
    assert widget._is_playing is True


def test_offline_state_uses_lyric_lane(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget.show_offline()
    assert widget._lyric_label.text() == "offline"
    widget.hide_offline()
    assert widget._lyric_label.text() == ""


def test_offline_state_does_not_move_content(qtbot):
    widget = _shown_widget(qtbot)

    track_geometry = widget._track_label.geometry()
    lyric_geometry = widget._lyric_label.geometry()
    progress_geometry = widget._progress_bar.geometry()
    widget_size = widget.size()

    widget.show_offline()
    qtbot.wait(50)

    assert widget._track_label.geometry() == track_geometry
    assert widget._lyric_label.geometry() == lyric_geometry
    assert widget._progress_bar.geometry() == progress_geometry
    assert widget.size() == widget_size


def test_offline_state_has_no_overlay_child(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert not hasattr(widget, "_offline_label")


def test_hide_offline_does_not_clear_real_lyric(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show_offline()
    widget.set_lyric_text("new lyric after recovery")

    widget.hide_offline()

    assert widget._lyric_label.text() == "new lyric after recovery"


def test_rate_limited_state_uses_fixed_layout(qtbot):
    widget = _shown_widget(qtbot)
    track_geometry = widget._track_label.geometry()
    lyric_geometry = widget._lyric_label.geometry()

    widget.show_rate_limited(30)

    assert widget._track_label.geometry() == track_geometry
    assert widget._lyric_label.geometry() == lyric_geometry
    assert "rate limited" in widget._lyric_label.text()
