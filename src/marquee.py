from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QLabel


MARQUEE_INTERVAL_MS = 40
MARQUEE_STEP_PX = 1
MARQUEE_GAP_PX = 40


class MarqueeLabel(QLabel):
    """Left-aligned, elided at rest; ping-pong scroll on hover if overflowing."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(MARQUEE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def setText(self, text: str):
        self._full_text = text
        self._offset = 0
        super().setText(text)
        self.update()

    def text(self) -> str:
        return self._full_text

    def start_marquee(self):
        if self._overflows():
            self._timer.start()

    def stop_marquee(self):
        self._timer.stop()
        self._offset = 0
        self.update()

    def _overflows(self) -> bool:
        if not self._full_text or self.width() <= 0:
            return False
        metrics = self.fontMetrics()
        return (
            metrics.horizontalAdvance(self._full_text) > self.width()
            or metrics.elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                self.width(),
            )
            != self._full_text
        )

    def _tick(self):
        if not self._overflows():
            self.stop_marquee()
            return

        self._offset = (self._offset + MARQUEE_STEP_PX) % self._cycle_width()
        self.update()

    def _cycle_width(self) -> int:
        return self.fontMetrics().horizontalAdvance(self._full_text) + MARQUEE_GAP_PX

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        if self._timer.isActive():
            text_width = self.fontMetrics().horizontalAdvance(self._full_text)
            cycle_width = self._cycle_width()
            x = -self._offset
            while x < self.width():
                painter.drawText(
                    x,
                    0,
                    text_width,
                    self.height(),
                    int(self.alignment()),
                    self._full_text,
                )
                x += cycle_width
            return

        elided = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            self.width(),
        )
        if elided.endswith("…"):
            elided = f"{elided[:-1]}..."
        painter.drawText(self.rect(), int(self.alignment()), elided)
