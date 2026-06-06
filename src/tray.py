from PyQt6.QtCore import Qt
from PyQt6.QtGui import QActionGroup, QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


SPOTIFY_GREEN = "#1DB954"

SIZE_ACTIONS = [
    ("Current", "current"),
    ("Compact", "compact"),
    ("Small", "small"),
    ("Mini", "mini"),
]


def build_tray_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(SPOTIFY_GREEN)))
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pixmap)


class TrayIcon:
    def __init__(
        self,
        on_activate,
        on_toggle,
        on_open_log,
        on_quit,
        on_size_changed=None,
        size_preset: str = "current",
        parent=None,
    ):
        self._on_activate = on_activate
        self._tray = QSystemTrayIcon(build_tray_icon(), parent)
        self._tray.setToolTip("Spotify Lyrics Widget")

        self._menu = QMenu()
        self._toggle_action = self._menu.addAction("Hide widget")
        self._toggle_action.triggered.connect(on_toggle)
        self._menu.addAction("Open log file").triggered.connect(on_open_log)

        self._size_menu = self._menu.addMenu("Size")
        self._size_action_group = QActionGroup(self._size_menu)
        self._size_action_group.setExclusive(True)
        self._size_actions = {}
        for label, value in SIZE_ACTIONS:
            action = self._size_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == size_preset)
            self._size_action_group.addAction(action)
            self._size_actions[value] = action
            if on_size_changed is not None:
                action.triggered.connect(
                    lambda checked=False, preset=value: on_size_changed(preset)
                )

        self._menu.addSeparator()
        self._menu.addAction("Quit").triggered.connect(on_quit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_activate()

    def set_widget_visible(self, visible: bool):
        self._toggle_action.setText("Hide widget" if visible else "Show widget")

    def set_size_preset(self, preset: str):
        if preset in self._size_actions:
            self._size_actions[preset].setChecked(True)

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
