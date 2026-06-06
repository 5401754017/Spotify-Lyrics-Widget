from PyQt6.QtCore import QEvent, QPointF, QSize, Qt
from PyQt6.QtGui import QEnterEvent, QImage


def test_transport_button_fixed_sizes(qtbot):
    from src.transport_button import TransportButton

    previous = TransportButton("previous")
    play = TransportButton("play")
    pause = TransportButton("pause")
    next_button = TransportButton("next")
    qtbot.addWidget(previous)
    qtbot.addWidget(play)
    qtbot.addWidget(pause)
    qtbot.addWidget(next_button)

    assert previous.size() == QSize(18, 24)
    assert play.size() == QSize(18, 24)
    assert pause.size() == QSize(18, 24)
    assert next_button.size() == QSize(18, 24)


def test_transport_button_can_apply_smaller_size(qtbot):
    from src.transport_button import TransportButton

    button = TransportButton("play")
    qtbot.addWidget(button)

    button.set_button_size(QSize(16, 22))

    assert button.size() == QSize(16, 22)


def test_play_pause_button_has_no_circle_background(qtbot):
    from src.transport_button import TransportButton

    button = TransportButton("play")
    qtbot.addWidget(button)

    image = QImage(button.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    button.render(image)

    assert image.pixelColor(9, 4).alpha() == 0


def test_play_pause_icons_fill_more_visual_space(qtbot):
    from src.transport_button import TransportButton

    play = TransportButton("play")
    pause = TransportButton("pause")
    qtbot.addWidget(play)
    qtbot.addWidget(pause)

    def painted_size(button):
        image = QImage(button.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        button.render(image)
        points = [
            (x, y)
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).alpha() > 0
        ]
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1

    play_width, play_height = painted_size(play)
    pause_width, pause_height = painted_size(pause)

    assert play_width >= 11
    assert play_height >= 12
    assert pause_width >= 9
    assert pause_height >= 12


def test_transport_button_mode_can_switch_between_play_and_pause(qtbot):
    from src.transport_button import TransportButton

    button = TransportButton("play")
    qtbot.addWidget(button)

    button.set_mode("pause")
    assert button.mode == "pause"

    button.set_mode("play")
    assert button.mode == "play"


def test_transport_button_tracks_hover_state_for_repaint(qtbot):
    from src.transport_button import TransportButton

    button = TransportButton("play")
    qtbot.addWidget(button)

    assert button._hovered is False

    button.enterEvent(QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    assert button._hovered is True

    button.leaveEvent(QEvent(QEvent.Type.Leave))
    assert button._hovered is False
