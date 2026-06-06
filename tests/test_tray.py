from PyQt6.QtWidgets import QSystemTrayIcon

from src.tray import TrayIcon, build_tray_icon


def _noop():
    pass


def _make_tray(**overrides):
    callbacks = dict(
        on_toggle=_noop,
        on_quit=_noop,
        on_size_changed=_noop,
        size_preset="current",
    )
    callbacks.update(overrides)
    return TrayIcon(**callbacks)


def test_build_tray_icon_not_null(qtbot):
    assert not build_tray_icon().isNull()


def test_trigger_calls_on_toggle(qtbot):
    calls = []
    tray = _make_tray(on_toggle=lambda: calls.append("toggle"))
    tray._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert calls == ["toggle"]


def test_double_click_does_not_call_on_toggle(qtbot):
    calls = []
    tray = _make_tray(on_toggle=lambda: calls.append("toggle"))
    tray._on_tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert calls == []


def test_menu_has_size_and_quit(qtbot):
    tray = _make_tray()
    labels = [action.text() for action in tray._menu.actions() if action.text()]
    assert "Size" in labels
    assert "Quit" in labels
    assert "Open log file" not in labels
    assert "Hide widget" not in labels


def test_menu_has_size_submenu_with_presets(qtbot):
    tray = _make_tray(on_size_changed=lambda name: None, size_preset="small")

    size_actions = [
        action for action in tray._menu.actions()
        if action.menu() is not None and action.text() == "Size"
    ]
    assert len(size_actions) == 1

    labels = [action.text() for action in tray._size_menu.actions()]
    assert labels == ["Current", "Compact", "Small", "Mini"]
    checked = [action.text() for action in tray._size_menu.actions() if action.isChecked()]
    assert checked == ["Small"]


def test_size_action_calls_callback(qtbot):
    calls = []
    tray = _make_tray(on_size_changed=lambda name: calls.append(name))

    mini_action = next(action for action in tray._size_menu.actions() if action.text() == "Mini")
    mini_action.trigger()

    assert calls == ["mini"]
