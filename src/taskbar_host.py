from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app_icon import build_app_icon


class TaskbarHostWindow(QWidget):
    show_widget_requested = pyqtSignal()
    hide_widget_requested = pyqtSignal()
    run_widget_requested = pyqtSignal()
    close_widget_requested = pyqtSignal()
    controller_close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._is_running = False
        self._is_visible = False
        self._is_closing = False

        self.setWindowTitle("Spotify Lyrics Widget")
        self.setWindowIcon(build_app_icon())
        self.resize(360, 150)

        self._title_label = QLabel("Spotify Lyrics Widget")
        self._running_label = QLabel()
        self._visibility_label = QLabel()
        self._visibility_button = QPushButton()
        self._run_close_button = QPushButton()

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._visibility_button)
        button_layout.addWidget(self._run_close_button)

        layout = QVBoxLayout()
        layout.addWidget(self._title_label)
        layout.addWidget(self._running_label)
        layout.addWidget(self._visibility_label)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self._visibility_button.clicked.connect(self._emit_visibility_request)
        self._run_close_button.clicked.connect(self._emit_run_close_request)
        self.set_widget_state(is_running=False, is_visible=False)

    def set_widget_state(
        self,
        is_running: bool,
        is_visible: bool,
        is_closing: bool = False,
    ):
        self._is_running = is_running
        self._is_closing = bool(is_running and is_closing)
        self._is_visible = is_visible if is_running else False
        if self._is_closing:
            self._is_visible = False
            self._running_label.setText("Widget: Closing...")
            self._visibility_label.setText("Widget: Hidden")
            self._visibility_button.setText("Widget Disabled")
            self._visibility_button.setEnabled(False)
            self._run_close_button.setText("Closing...")
            self._run_close_button.setEnabled(False)
            return

        self._run_close_button.setEnabled(True)
        self._running_label.setText(
            "Widget: Running" if self._is_running else "Widget: Stopped"
        )
        self._visibility_label.setText(
            "Widget: Visible" if self._is_visible else "Widget: Hidden"
        )

        if not self._is_running:
            self._visibility_button.setText("Widget Disabled")
            self._visibility_button.setEnabled(False)
            self._run_close_button.setText("Run Widget")
            return

        self._visibility_button.setEnabled(True)
        self._visibility_button.setText(
            "Hide Widget" if self._is_visible else "Show Widget"
        )
        self._run_close_button.setText("Close Widget")

    def _emit_visibility_request(self):
        if not self._is_running or self._is_closing:
            return
        if self._is_visible:
            self.hide_widget_requested.emit()
        else:
            self.show_widget_requested.emit()

    def _emit_run_close_request(self):
        if self._is_closing:
            return
        if self._is_running:
            self.close_widget_requested.emit()
        else:
            self.run_widget_requested.emit()

    def show_taskbar_entry(self):
        self.showMinimized()

    def closeEvent(self, event):
        self.controller_close_requested.emit()
        event.accept()
