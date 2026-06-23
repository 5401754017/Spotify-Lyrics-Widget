from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from src.taskbar_host import TaskbarHostWindow


def test_taskbar_host_is_regular_top_level_window(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    flags = host.windowFlags()

    assert (flags & Qt.WindowType.WindowType_Mask) != Qt.WindowType.Tool
    assert host.windowTitle() == "Spotify Lyrics Widget"
    assert host.width() == 360
    assert host.height() == 150


def test_control_window_starts_stopped_and_hidden(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    assert host._running_label.text() == "Widget: Stopped"
    assert host._visibility_label.text() == "Widget: Hidden"
    assert host._visibility_button.text() == "Widget Disabled"
    assert host._visibility_button.isEnabled() is False
    assert host._run_close_button.text() == "Run Widget"


def test_running_visible_state_updates_labels_and_buttons(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    host.set_widget_state(is_running=True, is_visible=True)

    assert host._running_label.text() == "Widget: Running"
    assert host._visibility_label.text() == "Widget: Visible"
    assert host._visibility_button.text() == "Hide Widget"
    assert host._visibility_button.isEnabled() is True
    assert host._run_close_button.text() == "Close Widget"


def test_running_hidden_state_updates_labels_and_buttons(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    host.set_widget_state(is_running=True, is_visible=False)

    assert host._running_label.text() == "Widget: Running"
    assert host._visibility_label.text() == "Widget: Hidden"
    assert host._visibility_button.text() == "Show Widget"
    assert host._visibility_button.isEnabled() is True
    assert host._run_close_button.text() == "Close Widget"


def test_stopped_state_disables_visibility_button(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    host.set_widget_state(is_running=False, is_visible=True)

    assert host._running_label.text() == "Widget: Stopped"
    assert host._visibility_label.text() == "Widget: Hidden"
    assert host._visibility_button.text() == "Widget Disabled"
    assert host._visibility_button.isEnabled() is False
    assert host._run_close_button.text() == "Run Widget"


def test_visibility_button_emits_hide_when_visible(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    host.set_widget_state(is_running=True, is_visible=True)

    with qtbot.waitSignal(host.hide_widget_requested, timeout=1000):
        host._visibility_button.click()


def test_visibility_button_emits_show_when_hidden(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    host.set_widget_state(is_running=True, is_visible=False)

    with qtbot.waitSignal(host.show_widget_requested, timeout=1000):
        host._visibility_button.click()


def test_run_close_button_emits_run_when_stopped(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    with qtbot.waitSignal(host.run_widget_requested, timeout=1000):
        host._run_close_button.click()


def test_run_close_button_emits_close_when_running(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    host.set_widget_state(is_running=True, is_visible=True)

    with qtbot.waitSignal(host.close_widget_requested, timeout=1000):
        host._run_close_button.click()


def test_show_taskbar_entry_minimizes_host(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    calls = []
    monkeypatch.setattr(host, "showMinimized", lambda: calls.append("minimized"))

    host.show_taskbar_entry()

    assert calls == ["minimized"]


def test_close_event_emits_controller_close_and_accepts(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    event = QCloseEvent()

    with qtbot.waitSignal(host.controller_close_requested, timeout=1000):
        host.closeEvent(event)

    assert event.isAccepted()
