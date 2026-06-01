from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QPushButton


WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_CIRCLE = "#282828"


class TransportButton(QPushButton):
    """Spotify-style fixed-size transport icon button."""

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        if mode not in {"previous", "play", "pause", "next"}:
            raise ValueError(f"Unknown transport button mode: {mode}")
        self.mode = mode
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setFlat(True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFixedSize(QSize(24, 24) if mode in {"play", "pause"} else QSize(18, 24))

    def set_mode(self, mode: str):
        if mode not in {"previous", "play", "pause", "next"}:
            raise ValueError(f"Unknown transport button mode: {mode}")
        self.mode = mode
        self.setFixedSize(QSize(24, 24) if mode in {"play", "pause"} else QSize(18, 24))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_color = QColor(SPOTIFY_GREEN if self._hovered else WHITE)

        if self.mode in {"play", "pause"}:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(DARK_CIRCLE))
            painter.drawEllipse(0, 0, 24, 24)

        painter.setBrush(icon_color)
        painter.setPen(QPen(icon_color, 2))

        if self.mode == "play":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(10, 7),
                        QPointF(10, 17),
                        QPointF(17, 12),
                    ]
                )
            )
        elif self.mode == "pause":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(8, 7, 3, 10, 1, 1)
            painter.drawRoundedRect(14, 7, 3, 10, 1, 1)
        elif self.mode == "previous":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(3, 7, 2, 10)
            painter.drawPolygon(
                QPolygonF([QPointF(15, 7), QPointF(15, 17), QPointF(6, 12)])
            )
        elif self.mode == "next":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(13, 7, 2, 10)
            painter.drawPolygon(
                QPolygonF([QPointF(3, 7), QPointF(3, 17), QPointF(12, 12)])
            )

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)
