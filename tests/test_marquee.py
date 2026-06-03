def test_marquee_elides_at_rest(qtbot):
    from src.marquee import MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.setText("a very long title that cannot fit")

    assert label.text() == "a very long title that cannot fit"
    assert label._offset == 0
    assert not label._timer.isActive()


def test_start_marquee_only_animates_when_overflowing(qtbot):
    from src.marquee import MarqueeLabel

    short = MarqueeLabel()
    qtbot.addWidget(short)
    short.resize(300, 24)
    short.setText("short")
    short.start_marquee()
    assert not short._timer.isActive()

    long = MarqueeLabel()
    qtbot.addWidget(long)
    long.resize(80, 24)
    long.setText("這是一首非常非常長的歌名")
    long.start_marquee()
    assert long._timer.isActive()


def test_stop_marquee_resets_offset(qtbot):
    from src.marquee import MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.setText("a very long title that cannot fit")
    label.start_marquee()
    label._offset = 12

    label.stop_marquee()

    assert label._offset == 0
    assert not label._timer.isActive()


def test_marquee_tick_scrolls_by_pixel_offset(qtbot):
    from src.marquee import MARQUEE_STEP_PX, MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.setText("這是一首非常非常長的歌名")
    label.start_marquee()

    label._tick()

    assert label._offset == MARQUEE_STEP_PX


def test_start_marquee_uses_same_overflow_boundary_as_rest_elision(qtbot):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    from src.fonts import app_font_family
    from src.marquee import MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
    label.setText("So Far Away - Acoustic — Adam Christopher")
    boundary_width = label.fontMetrics().horizontalAdvance(label.text())
    label.resize(boundary_width, 24)

    assert (
        label.fontMetrics().elidedText(
            label.text(),
            Qt.TextElideMode.ElideRight,
            label.width(),
        )
        != label.text()
    )

    label.start_marquee()

    assert label._timer.isActive()


def test_marquee_wraps_forward_after_text_and_gap(qtbot):
    from src.marquee import MARQUEE_GAP_PX, MARQUEE_STEP_PX, MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.setText("a very long title that cannot fit")
    label.start_marquee()
    cycle_width = label.fontMetrics().horizontalAdvance(label.text()) + MARQUEE_GAP_PX
    label._offset = cycle_width - MARQUEE_STEP_PX

    label._tick()

    assert label._offset == 0
    assert label._timer.isActive()
