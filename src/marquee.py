from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QLabel


MARQUEE_INTERVAL_MS = 40
MARQUEE_STEP_PX = 1
MARQUEE_END_PAUSE_TICKS = 18


class MarqueeLabel(QLabel):
    """Left-aligned, elided at rest; ping-pong scroll on hover if overflowing."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._offset = 0
        self._direction = 1
        self._pause_ticks = 0
        self._timer = QTimer(self)
        self._timer.setInterval(MARQUEE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def setText(self, text: str):
        self._full_text = text
        self._offset = 0
        self._direction = 1
        self._pause_ticks = 0
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
        self._direction = 1
        self._pause_ticks = 0
        self.update()

    def _overflows(self) -> bool:
        return self.fontMetrics().horizontalAdvance(self._full_text) > self.width()

    def _tick(self):
        if not self._overflows():
            self.stop_marquee()
            return
        if self._pause_ticks > 0:
            self._pause_ticks -= 1
            return

        max_offset = max(
            0,
            self.fontMetrics().horizontalAdvance(self._full_text) - self.width(),
        )
        self._offset += self._direction * MARQUEE_STEP_PX
        if self._offset >= max_offset:
            self._offset = max_offset
            self._direction = -1
            self._pause_ticks = MARQUEE_END_PAUSE_TICKS
        elif self._offset <= 0:
            self._offset = 0
            self._direction = 1
            self._pause_ticks = MARQUEE_END_PAUSE_TICKS
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        if self._timer.isActive():
            painter.drawText(
                -self._offset,
                0,
                self.fontMetrics().horizontalAdvance(self._full_text),
                self.height(),
                int(self.alignment()),
                self._full_text,
            )
            return

        elided = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            self.width(),
        )
        if elided.endswith("…"):
            elided = f"{elided[:-1]}..."
        painter.drawText(self.rect(), int(self.alignment()), elided)
