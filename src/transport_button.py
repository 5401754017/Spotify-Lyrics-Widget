from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QPushButton


WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
BUTTON_SIZE = QSize(18, 24)


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
        self.setFixedSize(BUTTON_SIZE)

    def set_mode(self, mode: str):
        if mode not in {"previous", "play", "pause", "next"}:
            raise ValueError(f"Unknown transport button mode: {mode}")
        self.mode = mode
        self.setFixedSize(BUTTON_SIZE)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_color = QColor(SPOTIFY_GREEN if self._hovered else WHITE)

        painter.setBrush(icon_color)
        painter.setPen(QPen(icon_color, 2))

        if self.mode == "play":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(5, 6),
                        QPointF(5, 18),
                        QPointF(16, 12),
                    ]
                )
            )
        elif self.mode == "pause":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(5, 6, 3, 12)
            painter.drawRect(12, 6, 3, 12)
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
