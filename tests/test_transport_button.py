from PyQt6.QtCore import QEvent, QPointF, QSize
from PyQt6.QtGui import QEnterEvent


def test_transport_button_fixed_sizes(qtbot):
    from src.transport_button import TransportButton

    previous = TransportButton("previous")
    play = TransportButton("play")
    qtbot.addWidget(previous)
    qtbot.addWidget(play)

    assert previous.size() == QSize(18, 24)
    assert play.size() == QSize(24, 24)


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
