from PyQt6.QtGui import QActionGroup, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from src.app_icon import build_app_icon

SIZE_ACTIONS = [
    ("Small", "small"),
    ("Medium", "medium"),
    ("Large", "large"),
]


def build_tray_icon() -> QIcon:
    return build_app_icon()


class TrayIcon:
    def __init__(
        self,
        on_toggle,
        on_quit,
        on_size_changed=None,
        size_preset: str = "large",
        parent=None,
    ):
        self._on_toggle = on_toggle
        self._tray = QSystemTrayIcon(build_tray_icon(), parent)
        self._tray.setToolTip("Spotify Lyrics Widget")

        self._menu = QMenu()

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
            self._on_toggle()

    def set_size_preset(self, preset: str):
        if preset in self._size_actions:
            self._size_actions[preset].setChecked(True)

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
