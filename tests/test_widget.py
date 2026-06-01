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


def test_widget_uses_dwm_rounding_and_opaque_panel(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    # Opaque window (not translucent); rounded corners AND the green frame are
    # drawn by the Windows DWM, not a QRegion mask or a panel border.
    assert not widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert widget.mask().isEmpty()
    assert "background-color: #121212" in widget.styleSheet()

    # Panel has no border/radius of its own — just the dark fill.
    assert widget._panel.objectName() == "lyricsPanel"
    assert "background-color: #121212" in widget._panel.styleSheet()


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


def test_widget_has_no_forced_visual_refresh_api(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert not hasattr(widget, "force_visual_refresh")


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


def test_progress_updates_without_lyrics(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_duration(200000)
    widget.set_lyrics([])  # no synced lyrics for this track
    widget.resync_local_timer(100000, True, time.monotonic())

    widget._on_ui_tick()

    assert widget._progress_bar.value() > 0


def test_unavailable_keeps_status_text_and_updates_progress(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_duration(200000)
    widget.show_unavailable()
    widget.resync_local_timer(100000, True, time.monotonic())

    widget._on_ui_tick()

    assert widget._progress_bar.value() > 0
    assert widget._lyric_label.text() == "lyrics unavailable"


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


def test_transport_controls_are_hover_only_and_do_not_move_title(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update_track_info("A very long song title that needs eliding", "Artist")

    title_before = widget._track_label.geometry()
    assert not widget._controls_cluster.isVisible()

    widget._on_enter_hover()
    title_hover = widget._track_label.geometry()

    assert widget._controls_cluster.isVisible()
    assert title_hover == title_before

    widget._on_leave_hover()
    assert not widget._controls_cluster.isVisible()
    assert widget._track_label.geometry() == title_before


def test_transport_controls_have_own_center_slot_and_close_has_own_slot(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget._on_enter_hover()

    controls = widget._controls_cluster.geometry()
    close = widget._close_btn.geometry()

    assert 170 <= controls.left() <= 180
    assert controls.width() == 72
    assert close.left() >= 360
    assert controls.right() < close.left()


def test_title_label_elides_before_close_button_slot(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    title_right = widget._track_label.mapTo(
        widget._panel,
        widget._track_label.rect().topRight(),
    ).x()

    assert title_right < widget._close_btn.geometry().left()


def test_play_pause_button_reflects_playing_state(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    widget.set_playing(True)
    assert widget._play_pause_btn.mode == "pause"

    widget.set_playing(False)
    assert widget._play_pause_btn.mode == "play"


def test_transport_buttons_emit_widget_level_signals(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.prev_clicked, timeout=1000):
        widget._prev_btn.click()

    with qtbot.waitSignal(widget.play_pause_clicked, timeout=1000):
        widget._play_pause_btn.click()

    with qtbot.waitSignal(widget.next_clicked, timeout=1000):
        widget._next_btn.click()
