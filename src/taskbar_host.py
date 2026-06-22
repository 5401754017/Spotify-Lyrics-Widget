from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app_icon import build_app_icon


class TaskbarHostWindow(QWidget):
    toggle_widget_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Lyrics Widget")
        self.setWindowIcon(build_app_icon())
        self.resize(320, 140)

        self._title_label = QLabel("Spotify Lyrics Widget")
        self._status_label = QLabel()
        self._toggle_button = QPushButton()
        self._quit_button = QPushButton("Quit")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._toggle_button)
        button_layout.addWidget(self._quit_button)

        layout = QVBoxLayout()
        layout.addWidget(self._title_label)
        layout.addWidget(self._status_label)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self._toggle_button.clicked.connect(self.toggle_widget_requested.emit)
        self._quit_button.clicked.connect(self.quit_requested.emit)
        self.set_widget_visible(False)

    def set_widget_visible(self, is_visible: bool):
        if is_visible:
            self._status_label.setText("Widget: Visible")
            self._toggle_button.setText("Hide Widget")
        else:
            self._status_label.setText("Widget: Hidden")
            self._toggle_button.setText("Show Widget")

    def show_taskbar_entry(self):
        self.showMinimized()

    def closeEvent(self, event):
        event.ignore()
        self.showMinimized()
