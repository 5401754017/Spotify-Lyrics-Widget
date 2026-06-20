from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from src.app_icon import build_app_icon


def build_tray_icon() -> QIcon:
    return build_app_icon()


class TrayIcon:
    def __init__(
        self,
        on_toggle,
        on_quit,
        parent=None,
    ):
        self._on_toggle = on_toggle
        self._tray = QSystemTrayIcon(build_tray_icon(), parent)
        self._tray.setToolTip("Spotify Lyrics Widget")

        self._menu = QMenu()
        self._menu.addAction("Open / Hide").triggered.connect(on_toggle)
        self._menu.addAction("Quit").triggered.connect(on_quit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_toggle()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
