import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

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


def test_widget_uses_translucent_outer_and_rounded_panel(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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


def test_offline_indicator(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget.show_offline()
    assert widget._offline_label.isVisible()
    widget.hide_offline()
    assert not widget._offline_label.isVisible()
