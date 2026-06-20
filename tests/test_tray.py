from PyQt6.QtWidgets import QSystemTrayIcon

from src.tray import TrayIcon, build_tray_icon


def _noop():
    pass


def _make_tray(**overrides):
    callbacks = dict(
        on_toggle=_noop,
        on_quit=_noop,
    )
    callbacks.update(overrides)
    return TrayIcon(**callbacks)


def test_build_tray_icon_not_null(qtbot):
    assert not build_tray_icon().isNull()


def test_build_tray_icon_uses_app_icon_asset(qtbot):
    sizes = build_tray_icon().availableSizes()

    assert any(size.width() >= 256 and size.height() >= 256 for size in sizes)


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


def test_menu_has_open_hide_and_quit(qtbot):
    tray = _make_tray()
    labels = [action.text() for action in tray._menu.actions() if action.text()]
    assert labels == ["Open / Hide", "Quit"]


def test_open_hide_menu_action_calls_on_toggle(qtbot):
    calls = []
    tray = _make_tray(on_toggle=lambda: calls.append("toggle"))

    open_hide_action = next(
        action for action in tray._menu.actions()
        if action.text() == "Open / Hide"
    )
    open_hide_action.trigger()

    assert calls == ["toggle"]


def test_quit_menu_action_calls_on_quit(qtbot):
    calls = []
    tray = _make_tray(on_quit=lambda: calls.append("quit"))

    quit_action = next(
        action for action in tray._menu.actions()
        if action.text() == "Quit"
    )
    quit_action.trigger()

    assert calls == ["quit"]
