from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QWidget

from src.app_icon import build_app_icon


class TaskbarHostWindow(QWidget):
    activated = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Lyrics Widget")
        self.setWindowIcon(build_app_icon())
        self.resize(320, 120)

    def show_taskbar_entry(self):
        self.showMinimized()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and not self.isMinimized():
            self.activated.emit()
            self.showMinimized()
        super().changeEvent(event)

    def closeEvent(self, event):
        self.close_requested.emit()
        event.accept()
